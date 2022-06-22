import pandas as pd

from definitions import ROOT_DIR, ACC_X_COL, ACC_Y_COL, ACC_Z_COL, GYRO_X_COL, GYRO_Y_COL, GYRO_Z_COL, SPEED_COL, \
    TIME_COL, LAT_COL, LNG_COL
from utils.file_reader import convert_json_to_iterator
from utils.functions import average_reduce

"""Convert collected trip from either the SensorPace App or the Roth Miner App into a unified data format"""
######################################################################

USE_COL = [ACC_X_COL, ACC_Y_COL, ACC_Z_COL, GYRO_X_COL, GYRO_Y_COL, GYRO_Z_COL, SPEED_COL, TIME_COL, LAT_COL, LNG_COL]

ROADR_COLUMN_DICT = {'accX': ACC_X_COL, 'accY': ACC_Y_COL, 'accZ': ACC_Z_COL,
                     'gyroX': GYRO_X_COL, 'gyroY': GYRO_Y_COL, 'gyroZ': GYRO_Z_COL,
                     'speed': SPEED_COL, 'timedifference': TIME_COL, 'latitude': LAT_COL, 'longitude': LNG_COL}

CAR_DATA_RECORDER_COLUMN_DICT = {'accpitch': ACC_X_COL, 'accyaw': ACC_Y_COL, 'accroll': ACC_Z_COL,
                                 'gyropitch': GYRO_X_COL, 'gyroyaw': GYRO_Y_COL, 'gyroroll': GYRO_Z_COL,
                                 'speed': SPEED_COL, 'timedifference': TIME_COL, 'lat': LAT_COL, 'lng': LNG_COL}

SENSOR_PACE_ACC_X = 'rotatedAccX'
SENSOR_PACE_ACC_Y = 'rotatedAccY'
SENSOR_PACE_ACC_Z = 'rotatedAccZ'
SENSOR_PACE_GYRO_X = 'rotatedGyrX'
SENSOR_PACE_GYRO_Y = 'rotatedGyrY'
SENSOR_PACE_GYRO_Z = 'rotatedGyrZ'
SENSOR_PACE_SPEED = 'gpsSpeed'
SENSOR_PACE_TIME = 'millioffset'

SENSOR_PACE_FREQUENCY = 200
UNIFIED_FREQUENCY = 25
# value indicating, how many measurements are buffered to calculate new measurement
BUFFER_FOR_FREQUENCY_REDUCTION = round(SENSOR_PACE_FREQUENCY / UNIFIED_FREQUENCY)


######################################################################

class SensorPaceMeasurement(object):
    def __init__(self, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, speed, time_offset, lat=None, lng=None):
        self.acc_x = acc_x
        self.acc_y = acc_y
        self.acc_z = acc_z
        self.gyro_x = gyro_x
        self.gyro_y = gyro_y
        self.gyro_z = gyro_z
        self.speed = speed
        self.time_offset = time_offset
        self.lat = lat
        self.lng = lng

    def to_dict(self):
        return {
            ACC_X_COL: self.acc_x,
            ACC_Y_COL: self.acc_y,
            ACC_Z_COL: self.acc_z,
            GYRO_X_COL: self.gyro_x,
            GYRO_Y_COL: self.gyro_y,
            GYRO_Z_COL: self.gyro_z,
            SPEED_COL: self.speed,
            TIME_COL: self.time_offset,
            LAT_COL: self.lat,
            LNG_COL: self.lng
        }


def handle_roadr_format(file_path: str, target_path: str):
    trip = pd.read_csv(file_path, sep=";", decimal=",")
    trip = trip.rename(columns=ROADR_COLUMN_DICT)
    # convert timeunit in seconds to milliseconds
    trip[TIME_COL] = trip[TIME_COL].apply(lambda t: t * 1000)
    trip = trip[USE_COL]
    trip.to_json(target_path, orient="records")


def handle_car_data_recorder_format(file_path: str, target_path: str):
    trip = pd.read_csv(file_path, sep=";", decimal=",")
    trip = trip.rename(columns=CAR_DATA_RECORDER_COLUMN_DICT)
    # convert timeunit in seconds to milliseconds
    trip[TIME_COL] = trip[TIME_COL].apply(lambda t: t * 1000)
    trip = trip[USE_COL]
    trip.to_json(target_path, orient="records")


def handle_sensorpace_format(file_path: str, target_path: str):
    trip_iterator = convert_json_to_iterator(file_path)
    reduced_measurements: [SensorPaceMeasurement] = []

    # keep buffering measurements to reduce frequency
    measurement_window_buffer: [SensorPaceMeasurement] = []

    # loop through measurements to reduce frequency
    for iteration in trip_iterator:
        measurement_window_buffer.append(SensorPaceMeasurement(iteration[SENSOR_PACE_ACC_X],
                                                               iteration[SENSOR_PACE_ACC_Y],
                                                               iteration[SENSOR_PACE_ACC_Z],
                                                               iteration[SENSOR_PACE_GYRO_X],
                                                               iteration[SENSOR_PACE_GYRO_Y],
                                                               iteration[SENSOR_PACE_GYRO_Z],
                                                               iteration[SENSOR_PACE_SPEED],
                                                               iteration[SENSOR_PACE_TIME]))

        if len(measurement_window_buffer) == BUFFER_FOR_FREQUENCY_REDUCTION:
            reduced_measurements.append(__reduce_frequency(measurement_window_buffer))
            measurement_window_buffer.clear()

    # store reformatted data
    processed_trip = pd.DataFrame.from_records([measurement.to_dict() for measurement in reduced_measurements])
    processed_trip.to_json(target_path, orient='records')


def __reduce_frequency(measurement_buffer: []) -> SensorPaceMeasurement:
    acc_x = average_reduce([measurement.acc_x for measurement in measurement_buffer])
    acc_y = average_reduce([measurement.acc_y for measurement in measurement_buffer])
    acc_z = average_reduce([measurement.acc_z for measurement in measurement_buffer])
    gyro_x = average_reduce([measurement.gyro_x for measurement in measurement_buffer])
    gyro_y = average_reduce([measurement.gyro_y for measurement in measurement_buffer])
    gyro_z = average_reduce([measurement.gyro_z for measurement in measurement_buffer])
    speed = average_reduce([measurement.speed for measurement in measurement_buffer])
    time = measurement_buffer[-1].time_offset

    return SensorPaceMeasurement(acc_x=acc_x, acc_y=acc_y, acc_z=acc_z, gyro_x=gyro_x, gyro_y=gyro_y, gyro_z=gyro_z,
                                 speed=speed, time_offset=time)


if __name__ == '__main__':
    handle_car_data_recorder_format(ROOT_DIR + "/data/raw_trips/Testfahrten Alex B/Burgweinting-Wohnheim.csv",
                                    ROOT_DIR + "/data/prep_trips/Route_A28.json")
