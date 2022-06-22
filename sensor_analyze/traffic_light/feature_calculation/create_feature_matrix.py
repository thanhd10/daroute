from collections import ChainMap
from typing import List, Dict

import pandas as pd
from p_tqdm import p_map
from tsfresh.feature_extraction import feature_calculators

from definitions import ACC_Y_COL, GYRO_Z_COL
from definitions import WINDOW_ID_COL_NAME
from sensor_analyze.traffic_light.feature_calculation.feature_calculation import get_first_maximum_after_idle, \
    get_first_peak_after_idle, get_acceleration_sum_maxima_accY, \
    get_acceleration_sum_minima_accY, get_min_before_idle, get_indices_of_longest_idle_time_gyroZ
from utils.sliding_windows import split_in_seconds_frames


def __extract_features_for_window(window: pd.DataFrame) -> Dict[int, List]:
    """ Create a feature vector from window as dict with window id as key and calculated features as list """
    second_frames = [second_frame for _, second_frame in split_in_seconds_frames(window)]
    start, stop = get_indices_of_longest_idle_time_gyroZ(second_frames)

    return {window[WINDOW_ID_COL_NAME].iloc[0]: [idle_time_calculator(start, stop),
                                                 first_maximum_of_gyro_z_after_idle(second_frames, start, stop),
                                                 first_peak_of_gyro_z_after_idle(second_frames, start, stop),
                                                 acceleration_sum_maxima_acc_y(second_frames, start, stop),
                                                 acceleration_sum_minima_acc_y(second_frames, start, stop),
                                                 min_acc_y_before_idle(second_frames, start),
                                                 mean(window, ACC_Y_COL),
                                                 max_value(window, ACC_Y_COL),
                                                 max_value(window, GYRO_Z_COL),
                                                 min_value(window, GYRO_Z_COL)]}


def create_traffic_light_feature_matrix(data: pd.DataFrame) -> pd.DataFrame:
    """ Feature Extraction step: Calculate all necessary features for every sliding window """
    sliding_windows = [x for _, x in data.groupby(WINDOW_ID_COL_NAME)]
    results = p_map(__extract_features_for_window, sliding_windows)

    # merge features vectors calculated on different processes to common data structure
    feature_matrix_as_dict = dict(ChainMap(*results))
    return pd.DataFrame.from_dict(feature_matrix_as_dict,
                                  orient='index',
                                  columns=['idle_time',
                                           'first_maximum_after_idle_gyroZ',
                                           'first_peak_after_idle_gyroZ',
                                           'acceleration_sum_maxima_accY',
                                           'acceleration_sum_minima_accY',
                                           'min_accY_before_idle',
                                           'arithmetic_mean_accY',
                                           'highest_accY',
                                           'highest_gyroZ',
                                           'lowest_gyroZ']).sort_index(ascending=True)


def max_value(window, sensor):
    return feature_calculators.maximum(window[sensor])


def min_value(window, sensor):
    return feature_calculators.minimum(window[sensor])


def acceleration_sum_maxima_acc_y(second_frames, start, stop):
    return get_acceleration_sum_maxima_accY(second_frames, start, stop)


def acceleration_sum_minima_acc_y(second_frames, start, stop):
    return get_acceleration_sum_minima_accY(second_frames, start, stop)


def mean(window, sensor):
    return feature_calculators.mean(window[sensor])


def idle_time_calculator(start, stop):
    if stop > start:
        return stop - start
    return 0


def first_maximum_of_gyro_z_after_idle(second_frames, start, stop):
    return get_first_maximum_after_idle(second_frames, start, stop, GYRO_Z_COL)


def first_peak_of_gyro_z_after_idle(second_frames, start, stop):
    return get_first_peak_after_idle(second_frames, start, stop, GYRO_Z_COL)


def min_acc_y_before_idle(second_frames, start):
    return get_min_before_idle(second_frames, start, ACC_Y_COL)
