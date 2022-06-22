import os

import pandas as pd

from definitions import OSM_ID_COL_NAME, LAT_COL_NAME, LNG_COL_NAME
from definitions import ROOT_DIR
from schema.TestRouteModel import TestRouteModel
from sensor_analyze.preprocess_trip import SensorPreprocessor

"""
Set Name of trip and the initial heading to preprocess sensor readings
"""

######################################################################

NARAIN_TARGET_DIR = ROOT_DIR + "/narain_attack/Files/Sensors/Samples/regensburg/"

TARGET_LOCATION = "Regensburg_20x20"
FILE_TARGET_DIR = ROOT_DIR + "/data/target_maps/" + TARGET_LOCATION


######################################################################

def convert_to_narain_data_format(test_route_model: TestRouteModel):
    route_dir = NARAIN_TARGET_DIR + test_route_model.test_id
    if not os.path.exists(route_dir):
        os.makedirs(route_dir)

    processor = SensorPreprocessor(ROOT_DIR + test_route_model.prep_file_path, test_route_model.heading_start)
    processor.preprocess()
    preprocessed_trip = processor.get_measurements_as_trip_df()

    raw_trip = pd.read_json(ROOT_DIR + test_route_model.prep_file_path)

    __create_accelerometer_csv(route_dir, raw_trip)
    __create_gyroscope_csv(route_dir, raw_trip)
    __create_locations_csv(route_dir, raw_trip)

    # need preprocessed dataframe, as it contains heading values
    __create_magnetometer_csv(route_dir, preprocessed_trip)

    __create_osm_nodes_txt_file(route_dir, test_route_model)


def __create_osm_nodes_txt_file(route_dir: str, test_route_model: TestRouteModel):
    nodes_df = pd.read_csv(FILE_TARGET_DIR + "/csv/nodes.csv")
    osm_id_to_latlng = nodes_df.set_index(OSM_ID_COL_NAME)[[LAT_COL_NAME, LNG_COL_NAME]].apply(
        tuple, axis=1).to_dict()

    with open(route_dir + "/OSM_Nodes.txt", 'a') as file:
        file.write('(-1, 0, 0, (0, 0, 0))\n')

        # TODO validate, whether turn angle is relevant for evaluation, as its not the angle from street network
        for i, node in enumerate(test_route_model.osm_id_path):
            next_line = '(-1, %.4f, 0, (\'%d\', \'%.6f\', \'%.6f\'))\n' % (test_route_model.new_sensor_turns[i].angle,
                                                                           node,
                                                                           osm_id_to_latlng[node][0],
                                                                           osm_id_to_latlng[node][1])
            file.write(next_line)


def __normalize_heading(heading: float) -> float:
    while heading >= 360:
        heading -= 360
    while heading < 0:
        heading += 360

    return heading


def __create_magnetometer_csv(route_dir: str, data_preprocessed: pd.DataFrame):
    magnetometer_df = pd.DataFrame(data_preprocessed['timestamp'].values, columns=['System Time'])
    magnetometer_df['Sensor'] = 'Magnetometer'
    # not available, grant default value
    magnetometer_df['Accuracy'] = 0
    # not available, grant default value
    magnetometer_df['Z Axis'] = 0.0
    # set Strength and Heading to the same values
    magnetometer_df['Strength'] = data_preprocessed['direction'].apply(lambda x: __normalize_heading(x))
    magnetometer_df['Heading'] = magnetometer_df['Strength']

    magnetometer_df.to_csv(route_dir + "/Magnetometer.csv", index=False)


def __create_accelerometer_csv(route_dir: str, data: pd.DataFrame):
    data_dict = {'System Time': data['offset_in_ms'].values,
                 'Sensor': 'Accelerometer',
                 'Accuracy': 0,  # not available, set to 0
                 'X Axis': data['acc_x'].values,
                 'Y Axis': data['acc_y'].values,
                 'Z Axis': data['acc_z'].values
                 }

    accelerometer_df = pd.DataFrame(data_dict)
    accelerometer_df.to_csv(route_dir + "/Accelerometer.csv", index=False)


def __create_gyroscope_csv(route_dir: str, data: pd.DataFrame):
    data_dict = {'System Time': data['offset_in_ms'].values,
                 'Sensor': 'Gyroscope',
                 'Accuracy': 0,  # not available, set to 0
                 'X Axis': data['gyro_x'].values,
                 'Y Axis': data['gyro_y'].values,
                 'Z Axis': data['gyro_z'].values}

    gyroscope_df = pd.DataFrame(data_dict)
    gyroscope_df.to_csv(route_dir + "/Gyroscope.csv", index=False)


def __create_locations_csv(route_dir: str, data: pd.DataFrame):
    data_dict = {"System Time": data['offset_in_ms'].values,
                 "Accuracy": 0.0,  # not available, set to 0
                 "Latitude": data['lat'].values,
                 "Longitude": data['lng'].values,
                 "Altitude": 0.0  # not available, set to 0
                 }

    locations_df = pd.DataFrame(data_dict)
    locations_df.to_csv(route_dir + "/Locations.csv", index=False)
