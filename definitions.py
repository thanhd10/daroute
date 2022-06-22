import os

"""
This file should be in the root level of the project and contains definitions and settings relevant
to multiple files in this project.
"""

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Column names of the unified data format for this project
ACC_X_COL = 'acc_x'
ACC_Y_COL = 'acc_y'
ACC_Z_COL = 'acc_z'
GYRO_X_COL = 'gyro_x'
GYRO_Y_COL = 'gyro_y'
GYRO_Z_COL = 'gyro_z'
SPEED_COL = 'speed'
TIME_COL = 'offset_in_ms'
LAT_COL = 'lat'
LNG_COL = 'lng'
TIMESTAMP_COL = 'timestamp'

# helper index to group rows to a sliding window
WINDOW_ID_COL_NAME = 'window_id'

# Relevant column names from a nodes.csv
NODE_ID_COL_NAME = 'node_id:ID'
OSM_ID_COL_NAME = 'osm_id:string'
LAT_COL_NAME = 'lat:float'
LNG_COL_NAME = 'lng:float'
LABEL_COL_NAME = ':LABEL'

INTERSECTION = 'INTERSECTION'
CONNECTION = 'CONNECTION'

# Relevant column indices from a ways.csv
START_ID_COL_WAYS_INDEX = 0
END_ID_COL_WAYS_INDEX = 1
SPEED_COL_WAYS_INDEX = 7

# Relevant column names for ways.csv
START_ID_COL_NAME = ':START_ID'
END_ID_COL_NAME = ':END_ID'
AGGREGATED_DISTANCE_COL_NAME = 'aggregated_distance:double'
SPEED_LIMIT_COL_NAME = 'speedlimit:int'

RADIUS_OF_EARTH = 6378.1
