import numpy as np
import pandas as pd
from pandas.core.groupby.generic import DataFrameGroupBy

from definitions import WINDOW_ID_COL_NAME

######################################################################

TIMESTAMP_COL = 'timestamp'
DISTANCE_COL = 'distance'
DISTANCE_BASED_WINDOW = 'distance_window'
TIME_BASED_WINDOW = 'time_window'

ONE_SECOND_STEP = 1000


######################################################################

def split_in_seconds_frames(window: pd.DataFrame) -> DataFrameGroupBy:
    """ Utility function to split a sliding window into one-second-inteval windows """
    return window.groupby(pd.cut(x=window[TIMESTAMP_COL],
                                 bins=np.arange(start=window[TIMESTAMP_COL].min(),
                                                stop=window[TIMESTAMP_COL].max() + 1,
                                                step=ONE_SECOND_STEP)))


def create_sliding_windows(trip_df: pd.DataFrame, max_window_size: float, sliding_factor: float,
                           window_function: str) -> pd.DataFrame:
    if window_function == DISTANCE_BASED_WINDOW:
        return __create_windows_distance(trip_df, window_size=max_window_size, sliding_factor=sliding_factor)
    elif window_function == TIME_BASED_WINDOW:
        return __create_windows_time(trip_df, window_size=max_window_size, sliding_factor=sliding_factor)
    else:
        raise Exception("Invalid window_function provided.")


def __create_windows_time(data: pd.DataFrame, window_size: float, sliding_factor: float) -> pd.DataFrame:
    """
    create a DataFrame, that transforms the raw time series data of a 'ride' into windows depending
    on the passed time
    every row in the DataFrame will be assigned a value for the 'time_id_column' to indicate,
    which window the row belongs to

    :param data: the raw data of a 'ride' with the distance column already calculated
    :param window_size: the time in seconds a sliding window covers
    :param sliding_factor: a percentage that determines, how much the sliding windows should overlap
    :return: the transformed DataFrame containing the raw data of a 'ride' in sliding windows
    """
    result = []
    time_id = 0
    while True:
        data.reset_index(inplace=True, drop=True)
        curr_window_start_time = data[TIMESTAMP_COL].iloc[0]
        values_after_curr_window = data[data[TIMESTAMP_COL] - curr_window_start_time > window_size]

        data[WINDOW_ID_COL_NAME] = time_id

        if values_after_curr_window.empty:
            result.append(data)
            # no windows to create left, so exit
            break
        else:
            curr_window_end = values_after_curr_window.index[0]
            curr_window_frame = data.head(curr_window_end + 1)
            result.append(curr_window_frame)

            # remove values of previous window depending on overlapping factor
            data = data.drop(data.index[: int(np.round(curr_window_end * sliding_factor))])
            # increase index for next sliding window
            time_id += 1

    return pd.concat(result, axis=0, ignore_index=True)


def __create_windows_distance(data: pd.DataFrame, window_size: float, sliding_factor: float) -> pd.DataFrame:
    """
    create a DataFrame, that transforms the raw time series data of a 'ride' into windows depending
    on the bridged distance
    every row in the DataFrame will be assigned a value for the 'time_id_column' to indicate,
    which window the row belongs to

    :param data: the raw data of a 'ride' with the distance column already calculated
    :param window_size: the distance a sliding window bridges
    :param sliding_factor: a percentage that determines, how much the sliding windows should overlap
    :return: the transformed DataFrame containing the raw data of a 'ride' in sliding windows
    """
    result = []
    time_id = 0
    while True:
        data.reset_index(inplace=True, drop=True)
        values_after_curr_window = data[data[DISTANCE_COL].cumsum() > window_size]

        data[WINDOW_ID_COL_NAME] = time_id

        if values_after_curr_window.empty:
            result.append(data)
            # no further window to process
            break
        else:
            curr_window_end = values_after_curr_window.index[0]
            curr_window_frame = data.head(curr_window_end + 1)
            result.append(curr_window_frame)

            # remove values of previous window depending on overlapping factor
            data = data.drop(data.index[: int(np.round(curr_window_end * sliding_factor))])
            # increase index for next sliding window
            time_id += 1

    return pd.concat(result, axis=0, ignore_index=True)
