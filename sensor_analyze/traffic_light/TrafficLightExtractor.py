import os
from typing import List

# ignore verbose info (1) and warning (2) messages from tensorflow:
# https://stackoverflow.com/questions/35911252/disable-tensorflow-debugging-information
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import pandas as pd
import tensorflow as tf
from p_tqdm import p_map
from definitions import WINDOW_ID_COL_NAME, TIMESTAMP_COL
from utils.sliding_windows import create_sliding_windows, DISTANCE_BASED_WINDOW, split_in_seconds_frames
from utils.functions import flatten_list
from sensor_analyze.traffic_light.feature_calculation.create_feature_matrix import \
    create_traffic_light_feature_matrix
from schema.sensor_models import TemporaryTrafficLight
from definitions import ROOT_DIR

######################################################################

# File paths for Roundabout model
TRAFFIC_LIGHT_KERAS_MODEL_PATH = ROOT_DIR + '/sensor_analyze/traffic_light/keras_model'

# Sliding Window Parameters
DISTANCE_WINDOW_SIZE_IN_METERS = 300
SLIDING_FACTOR = 0.6
WINDOW_FUNCTION = DISTANCE_BASED_WINDOW

NO_TRAFFIC_LIGHT_LABEL = 0

STANDING_PHASE_THRESHOLD = 5
GYRO_Z_STANDING_PHASE_THRESHOLD = 0.009

IS_STANDING = 'is_standing'
TIME_MIN = 'time_min'
TIME_MAX = 'time_max'


######################################################################

def create_sub_windows_on_standing_phases(window: pd.DataFrame) -> List[pd.DataFrame]:
    """
    Each automatically created sliding window is checked for standing phases.
    Only sliding windows are further considered, that contain standing phases.
    Windows with multiple standing phases are split in sub-windows.
    :param window: Automatically created sliding window
    :return: a list of windows to analyze
    """
    standing_phases = find_standing_phases(window)
    if len(standing_phases.index) == 0:
        # window can't contain a traffic light without a standing phase
        return []
    elif len(standing_phases.index) == 1:
        return [window]
    else:
        return __split_window_by_standing_phases(window, standing_phases)


def find_standing_phases(window: pd.DataFrame) -> pd.DataFrame:
    """
    Find all standing phases within the given window.
    :param window: a given window of timeseries data, that should be checked
    :return: a dataFrame, where each row contains a standing phase within the window with its timeframe and duration
    """
    # create one second timestep windows from current window
    window_in_seconds = split_in_seconds_frames(window)

    # TODO adjust is_standing logic
    # check, whether a one second window was recognized as 'standing'
    sub_window_stats = window_in_seconds.agg(time_min=(TIMESTAMP_COL, np.min),
                                             time_max=(TIMESTAMP_COL, np.max),
                                             is_standing=('distance', lambda x: x.sum() < 1.0))

    # differentiate between alternating phases 'standing' and 'not standing'
    sub_window_stats['phase_id'] = sub_window_stats.groupby(sub_window_stats[IS_STANDING].ne(
        (sub_window_stats[IS_STANDING].shift())).cumsum()).ngroup()

    # prepare stats about the alternating phases 'standing' and 'not standing'
    window_phases = sub_window_stats.groupby('phase_id').agg(time_min=(TIME_MIN, np.min),
                                                             time_max=(TIME_MAX, np.max),
                                                             is_standing=(IS_STANDING, lambda x: x.mode()),
                                                             duration=('phase_id', 'count'))

    # only interested in phases, that are 'standing' and their duration exceeding a given threshold
    return window_phases[window_phases[IS_STANDING] & (window_phases['duration'] >= STANDING_PHASE_THRESHOLD)]


def __split_window_by_standing_phases(window: pd.DataFrame, standing_phases: pd.DataFrame
                                      ) -> List[pd.DataFrame]:
    """
    Split a given window into sub-windows, so each sub-window only contains a single standing phase
    :param window: The automatically created sliding window
    :param standing_phases: All recognized standing phases within the given window
    :return: a list of tuples, where each sliding window is labeled in the form of (window, label)
    """
    splitted_windows = []
    while len(standing_phases) > 1:
        # next window with current standing phase ends, when next following standing phase starts
        curr_window = window[window[TIMESTAMP_COL] <= standing_phases.iloc[1][TIME_MIN]]
        splitted_windows.append(curr_window)

        # remove beginning of the window until the end of the current standing phase
        window = window[window[TIMESTAMP_COL] >= standing_phases.iloc[0][TIME_MAX]]
        # remove first standing phase, as a sub-window was created for it already
        standing_phases.drop(standing_phases.index[:1], inplace=True)

    # append a window around the last standing phase
    splitted_windows.append(window)

    return splitted_windows


class TrafficLightExtractor(object):
    def __init__(self, trip_df: pd.DataFrame):
        self._keras_model = tf.keras.models.load_model(TRAFFIC_LIGHT_KERAS_MODEL_PATH)

        self.trips_df = trip_df

    def find_traffic_lights(self) -> List[TemporaryTrafficLight]:
        sliding_windows = create_sliding_windows(trip_df=self.trips_df,
                                                 max_window_size=DISTANCE_WINDOW_SIZE_IN_METERS,
                                                 sliding_factor=SLIDING_FACTOR,
                                                 window_function=DISTANCE_BASED_WINDOW)
        # format windows into a list of dataframes for multiprocess
        sliding_windows = [x for _, x in sliding_windows.groupby(WINDOW_ID_COL_NAME)]
        candiate_windows = flatten_list(p_map(create_sub_windows_on_standing_phases, sliding_windows))

        # empty list, as no standing phase
        if not candiate_windows:
            return []

        # windows to check for traffic lights
        data_pred = self.__reassign_window_ids(candiate_windows)
        # windows represented as feature vector
        traffic_light_features = create_traffic_light_feature_matrix(data_pred)

        # prediction of windows depending on their features
        class_predictions = np.argmax(self._keras_model.predict(traffic_light_features), axis=1)
        traffic_light_indices = np.where(class_predictions != NO_TRAFFIC_LIGHT_LABEL)[0]

        # create a traffic light for each window, that was classified as such
        return [self.__create_traffic_light(data_pred[data_pred[WINDOW_ID_COL_NAME] == window_id])
                for window_id in traffic_light_indices]

    def __create_traffic_light(self, traffic_light_window: pd.DataFrame) -> TemporaryTrafficLight:
        # TODO handle overlapping time frames
        standing_phase = find_standing_phases(traffic_light_window)
        if len(standing_phase) != 1:
            raise Exception("Window should contain exactly one standing phase.")

        start_time = standing_phase.iloc[0][TIME_MIN]
        end_time = standing_phase.iloc[0][TIME_MAX]

        return TemporaryTrafficLight(start_time, end_time)

    def __reassign_window_ids(self, windows: List[pd.DataFrame]) -> pd.DataFrame:
        """ Each window should contain a unique id """
        window_id_helper = 0
        for window in windows:
            window.loc[:, WINDOW_ID_COL_NAME] = window_id_helper
            window_id_helper += 1

        return pd.concat(windows, ignore_index=True)


if __name__ == '__main__':
    trip = pd.read_csv(ROOT_DIR + "/test/measurements/Measurements_Route_N3.csv")
    traffic_light_extractor = TrafficLightExtractor(trip)
    predictions = traffic_light_extractor.find_traffic_lights()

    for pred in predictions:
        print("Start=%.2f seconds, End=%.2f seconds. Duration=%.2f seconds."
              % (pred.start_time / 1000, pred.end_time / 1000, (pred.end_time - pred.start_time) / 1000))
