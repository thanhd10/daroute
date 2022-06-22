import json
import os
from typing import Tuple, Union

# ignore verbose info (1) and warning (2) messages from tensorflow:
# https://stackoverflow.com/questions/35911252/disable-tensorflow-debugging-information
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import pandas as pd
import tensorflow as tf
from tsfresh import extract_features
from tsfresh.utilities.dataframe_functions import impute

from definitions import WINDOW_ID_COL_NAME, ROOT_DIR, GYRO_Z_COL, TIMESTAMP_COL
from schema.sensor_models import TemporaryRoundabout
from utils.sliding_windows import TIME_BASED_WINDOW, create_sliding_windows, split_in_seconds_frames

######################################################################

# File paths for Roundabout model
ROUNDABOUT_KERAS_MODEL_PATH = ROOT_DIR + '/sensor_analyze/roundabout/model_files/keras_model'
ROUNDABOUT_FEATURES_PATH = ROOT_DIR + '/sensor_analyze/roundabout/model_files/features/roundabout_features_dict.json'
FEATURE_ORDER_PATH = ROOT_DIR + '/sensor_analyze/roundabout/model_files/features/feature_order_150_features.csv'
SCALE_MEANS_PATH = ROOT_DIR + '/sensor_analyze/roundabout/model_files/features/tf_150_mean.txt'
SCALE_STDS_PATH = ROOT_DIR + '/sensor_analyze/roundabout/model_files/features/tf_150_std.txt'

# Sliding Window Parameters
TIME_WINDOW_SIZE_IN_MS = 20000
SLIDING_FACTOR = 0.6
WINDOW_FUNCTION = TIME_BASED_WINDOW

# possible candidate time frames threshold for roundabout phases
GYRO_Z_ROUNDABOUT_ENTER_OR_EXIT_THRESHOLD = -0.1
GYRO_Z_ROUNDABOUT_PEAK_THRESHOLD = 0.15
# delay before/after roundabout entering/exiting in ms
TIME_DELAY_STRAIGHT_TRAVEL = 1000.0

NO_ROUNDABOUT_LABEL = 0
FIRST_EXIT_LABEL = 1

# helper column names for roundabout phases
IS_ENTER_OR_EXIT_ROUNDABOUT_COL = 'is_enter_or_exit'
IS_POSSIBLE_ROUNDABOUT_PEAK_COL = 'is_roundabout_peak'
TIME_MIN_COL = 'time_min'
TIME_MAX_COL = 'time_max'


######################################################################


class RoundaboutClassifier(object):
    def __init__(self, trip_df: pd.DataFrame):
        self._keras_model = tf.keras.models.load_model(ROUNDABOUT_KERAS_MODEL_PATH)

        self.feature_order = pd.read_csv(FEATURE_ORDER_PATH).columns
        self.means = np.loadtxt(SCALE_MEANS_PATH)
        self.stds = np.loadtxt(SCALE_STDS_PATH)

        self.trip_df = trip_df

    def find_roundabouts(self) -> [TemporaryRoundabout]:
        sliding_windows = create_sliding_windows(trip_df=self.trip_df,
                                                 max_window_size=TIME_WINDOW_SIZE_IN_MS,
                                                 sliding_factor=SLIDING_FACTOR,
                                                 window_function=WINDOW_FUNCTION)
        roundabout_features = self.__extract_roundabout_features(sliding_windows)
        scaled_features = self.__scale_roundabout_features(roundabout_features)

        class_predictions = np.argmax(self._keras_model.predict(scaled_features), axis=1)

        roundabout_indices = np.where((class_predictions != NO_ROUNDABOUT_LABEL) &
                                      (class_predictions != FIRST_EXIT_LABEL))[0]
        if roundabout_indices.size == 0:
            return []

        # https://stackoverflow.com/questions/7352684/how-to-find-the-groups-of-consecutive-elements-in-a-numpy-array
        # every roundabout is represented by an array of window_ids, as the same roundabout can occur
        # in multiple, successively following windows
        roundabout_indices = np.split(roundabout_indices, np.where(np.diff(roundabout_indices) != 1)[0] + 1)

        return [r for r in
                [self.__create_temporary_roundabout(sliding_windows, indices) for indices in roundabout_indices]
                if r is not None]

    def __extract_roundabout_features(self, sliding_windows: pd.DataFrame) -> pd.DataFrame:
        with open(ROUNDABOUT_FEATURES_PATH) as json_file:
            fc_parameters = json.load(json_file)
            roundabout_features = extract_features(timeseries_container=sliding_windows,
                                                   column_id=WINDOW_ID_COL_NAME,
                                                   kind_to_fc_parameters=fc_parameters)
            roundabout_features = impute(roundabout_features)

        # set feature order to expected order of model
        roundabout_features = roundabout_features.reindex(self.feature_order, axis=1)

        return roundabout_features

    def __scale_roundabout_features(self, roundabout_features: pd.DataFrame) -> pd.DataFrame:
        # StandardScaler is used for feature scaling. Equation : x_scaled = (x - mean) / std
        return (roundabout_features - self.means) / self.stds

    def __create_temporary_roundabout(self, sliding_windows: pd.DataFrame,
                                      window_ids: np.ndarray) -> Union[TemporaryRoundabout, None]:
        start_time, end_time = self.__get_roundabout_time_interval(sliding_windows, window_ids)

        # discard roundabout
        if start_time == -1 and end_time == -1:
            return None

        direction_before = self.trip_df[self.trip_df[TIMESTAMP_COL] > start_time].iloc[0]['direction']
        direction_after = self.trip_df[self.trip_df[TIMESTAMP_COL] > end_time].iloc[0]['direction']

        return TemporaryRoundabout(start_time=start_time, end_time=end_time, direction_before=direction_before,
                                   direction_after=direction_after)

    def __get_roundabout_time_interval(self, sliding_windows: pd.DataFrame, window_ids: np.ndarray) -> Tuple[int, int]:
        """
        Determine a more precise time window, where the vehicle is driving within a roundabout.
        In most cases, a sliding window contains enter/exit phases, one for entering and one for exiting a roundabout.
        But in some cases, shortly before/after a roundabout a turn/lane change could occur, so multiple phases occur.
        These have to be handled separately by validating possible peaking phases within a roundabout.
        """
        window = sliding_windows[sliding_windows[WINDOW_ID_COL_NAME].isin(window_ids)]

        window_phases = self.__find_possible_roundabout_phases(window)
        try:
            if len(window_phases[window_phases[IS_POSSIBLE_ROUNDABOUT_PEAK_COL]]) == 0:
                print("Warning: No Roundabout Peak found, discard detected roundabout.")
                return -1, -1
        except TypeError:
            print("Type error at a window. Might be caused by a [True, False], instead of single bool.")
            print(window_phases[IS_POSSIBLE_ROUNDABOUT_PEAK_COL])

        enter_or_exit_phases = window_phases[window_phases[IS_ENTER_OR_EXIT_ROUNDABOUT_COL]]

        # exact two phases: start and enter of roundabout
        if len(enter_or_exit_phases.index) == 2:
            return enter_or_exit_phases.iloc[0][TIME_MIN_COL] - TIME_DELAY_STRAIGHT_TRAVEL, \
                   enter_or_exit_phases.iloc[1][TIME_MAX_COL] + TIME_DELAY_STRAIGHT_TRAVEL
        elif len(enter_or_exit_phases) > 2:
            # search for roundabout peak between possible enter/exit phases
            for start_index, end_index in zip(enter_or_exit_phases.index[:-1], enter_or_exit_phases.index[1:]):
                if window_phases.loc[start_index:end_index][IS_ENTER_OR_EXIT_ROUNDABOUT_COL].any():
                    return window_phases.loc[start_index][TIME_MIN_COL] - TIME_DELAY_STRAIGHT_TRAVEL, \
                           window_phases.loc[end_index][TIME_MAX_COL] + TIME_DELAY_STRAIGHT_TRAVEL
        elif len(enter_or_exit_phases) < 2:
            # TODO if more data is found for this case, then might investigate it more
            print("Warning: No exit and enter found, discard detected roundabout.")
            return -1, -1

        raise Exception('Missing roundabout peak phase. Investigate this case.')

    def __find_possible_roundabout_phases(self, window: pd.DataFrame) -> pd.DataFrame:
        """
        Determine the possible enter and exit time frames for a roundabout by validating time-second windows.
        Further, possible peaking phases within a roundabout are found.
        """
        # create one second timestep windows from current window
        window_in_seconds = split_in_seconds_frames(window)

        # determine enter/exit phases of roundabout
        sub_window_stats = window_in_seconds.agg(time_min=(TIMESTAMP_COL, np.min),
                                                 time_max=(TIMESTAMP_COL, np.max),
                                                 is_enter_or_exit=(GYRO_Z_COL, lambda x:
                                                 np.mean(x) < GYRO_Z_ROUNDABOUT_ENTER_OR_EXIT_THRESHOLD),
                                                 is_roundabout_peak=(GYRO_Z_COL, lambda x:
                                                 np.mean(x) > GYRO_Z_ROUNDABOUT_PEAK_THRESHOLD))

        # helper column to group alternating phases
        sub_window_stats['phase_id'] = sub_window_stats.groupby(sub_window_stats[IS_ENTER_OR_EXIT_ROUNDABOUT_COL].ne(
            (sub_window_stats[IS_ENTER_OR_EXIT_ROUNDABOUT_COL].shift())).cumsum()).ngroup()
        # receive enter/exit phases
        return sub_window_stats.groupby('phase_id').agg(time_min=(TIME_MIN_COL, np.min),
                                                        time_max=(TIME_MAX_COL, np.max),
                                                        is_enter_or_exit=(
                                                            IS_ENTER_OR_EXIT_ROUNDABOUT_COL, lambda x: x.mode()),
                                                        is_roundabout_peak=(
                                                            IS_POSSIBLE_ROUNDABOUT_PEAK_COL, lambda x: x.mode()))


if __name__ == '__main__':
    trip = pd.read_csv(ROOT_DIR + "/test/measurements/Measurements_Route_FX.csv")
    roundabout_classifier = RoundaboutClassifier(trip)
    roundabouts = roundabout_classifier.find_roundabouts()

    for roundabout in roundabouts:
        print("Enter roundabout at %.d milliseconds. Exit roundabout at %.d milliseconds."
              % (roundabout.start_time, roundabout.end_time))
