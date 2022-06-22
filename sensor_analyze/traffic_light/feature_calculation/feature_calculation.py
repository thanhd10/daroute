import numpy as np
import pandas as pd
from tsfresh.feature_extraction.feature_calculators import first_location_of_minimum, \
    first_location_of_maximum

from definitions import ACC_Y_COL, GYRO_Z_COL

######################################################################

IDLE_THRESHOLD_SECONDS = 5
IDLE_THRESHOLD_GYRO_Z = 0.009


######################################################################


def get_min_before_idle(second_frames, start, sensor):
    if start > 0:
        sliced_time_series = pd.concat(second_frames[:start])[sensor].to_numpy()
        return min(sliced_time_series)
    return 0


def get_acceleration_sum_maxima_accY(second_frames, start, stop):
    sum_max = 0
    if 0 < stop < len(second_frames) and stop - start >= IDLE_THRESHOLD_SECONDS:
        sliced_time_series = pd.concat(second_frames[stop:])[ACC_Y_COL].to_numpy()
        for i in range(3):
            max_pos = first_location_of_maximum(sliced_time_series)
            if not np.isnan(max_pos):
                max_val = sliced_time_series[int(max_pos * len(sliced_time_series))]
                sum_max = sum_max + max_val
                if len(sliced_time_series) > 1:
                    sliced_time_series = sliced_time_series[int(max_pos * len(sliced_time_series)) + 1:]
                else:
                    break
    return sum_max


def get_acceleration_sum_minima_accY(second_frames, start, stop):
    sum_min = 0.0
    if 0 < stop < len(second_frames) and stop - start >= IDLE_THRESHOLD_SECONDS:
        sliced_time_series = pd.concat(second_frames[stop:])[ACC_Y_COL].to_numpy()
        for i in range(3):
            min_pos = first_location_of_minimum(sliced_time_series)
            if not np.isnan(min_pos):
                min_val = sliced_time_series[int(min_pos * len(sliced_time_series))]
                sum_min = sum_min + min_val
                if len(sliced_time_series) > 1:
                    sliced_time_series = sliced_time_series[int(min_pos * len(sliced_time_series)) + 1:]
    return sum_min


def get_first_maximum_after_idle(second_frames, start, stop, sensor):
    if 0 < stop < len(second_frames) and stop - start >= IDLE_THRESHOLD_SECONDS:
        sliced_time_series = pd.concat(second_frames[stop:])[sensor].to_numpy()
        first_max = first_location_of_maximum(sliced_time_series)
        first_max = sliced_time_series[int(first_max * len(sliced_time_series))]
        return first_max
    return 0.0


def get_first_peak_after_idle(second_frames, start, stop, sensor):
    if 0 < stop < len(second_frames) and stop - start >= IDLE_THRESHOLD_SECONDS:
        sliced_time_series = pd.concat(second_frames[stop:])[sensor].to_numpy()

        first_max = first_location_of_maximum(sliced_time_series)
        first_min = first_location_of_minimum(sliced_time_series)
        if first_min < first_max:
            # min_val
            return sliced_time_series[int(first_min * len(sliced_time_series))]
        else:
            # max_val
            return sliced_time_series[int(first_max * len(sliced_time_series))]
    return 0.0


def get_indices_of_longest_idle_time_gyroZ(second_frames):
    max_streak = 0
    streak = 0
    start_index = 0
    stop_index = 0
    i = 0
    for frame in second_frames:
        if len(frame) != 0:
            gyroZ = np.average(frame[GYRO_Z_COL])
            if abs(gyroZ) <= IDLE_THRESHOLD_GYRO_Z:
                streak += 1
                if streak > max_streak:
                    max_streak = streak
                    stop_index = i
                    start_index = stop_index - max_streak
            else:
                streak = 0
        i += 1
    return start_index, stop_index
