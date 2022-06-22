import geopy.distance
import numpy as np
import pandas as pd

from definitions import ACC_X_COL, ACC_Y_COL, ACC_Z_COL, GYRO_X_COL, GYRO_Y_COL, GYRO_Z_COL, SPEED_COL, \
    TIME_COL, LAT_COL, LNG_COL

FREQUENCY = 25

SAMPLING_DELAY = 1000 / FREQUENCY

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


class MeasurementReading(object):
    def __init__(self, offset_in_ms, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, speed, lat, lng):
        self.offset_in_ms = offset_in_ms
        self.acc_x = acc_x
        self.acc_y = acc_y
        self.acc_z = acc_z
        self.gyro_x = gyro_x
        self.gyro_y = gyro_y
        self.gyro_z = gyro_z
        self.speed = speed
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
            TIME_COL: self.offset_in_ms,
            LAT_COL: self.lat,
            LNG_COL: self.lng
        }


class LocationReading(object):
    def __init__(self, offset_in_ms, lat, lng, speed):
        self.offset_in_ms = offset_in_ms
        self.lat = lat
        self.lng = lng
        self.speed = speed


def prep_location_readings(file_path: str) -> [LocationReading]:
    location_data = pd.read_csv(file_path)
    # fix bug of some readings, where measurements are not sorted by time ascending
    location_data.sort_values(by=["System Time"], inplace=True)
    location_data = location_data.values.tolist()

    last_location = LocationReading(location_data[0][0],
                                    location_data[0][2],
                                    location_data[0][3],
                                    0.0)
    location_readings = [last_location]

    curr_travel_speed = 0.0

    for curr_location_reading in location_data[1:]:

        if curr_location_reading[2] == last_location.lat and curr_location_reading[3] == last_location.lng:
            last_location = LocationReading(curr_location_reading[0],
                                            curr_location_reading[2],
                                            curr_location_reading[3],
                                            curr_travel_speed)

            location_readings.append(last_location)
            continue

        distance_bridged = geopy.distance.distance((last_location.lat, last_location.lng),
                                                   (curr_location_reading[2], curr_location_reading[3])).m
        # convert in seconds
        time_passed = (curr_location_reading[0] - last_location.offset_in_ms) / 1000

        travel_speed = distance_bridged / time_passed

        # might be GPS reading error
        if travel_speed > 40:
            continue
        else:
            curr_travel_speed = travel_speed

        last_location = LocationReading(curr_location_reading[0],
                                        curr_location_reading[2],
                                        curr_location_reading[3],
                                        curr_travel_speed)

        location_readings.append(last_location)

    return location_readings


def convert_from_narain_format(route_id: str,
                               route_dir: str,
                               target_dir: str):
    locations = prep_location_readings(route_dir + "/Locations.csv")
    acc = pd.read_csv(route_dir + "/Accelerometer.csv")
    gyro = pd.read_csv(route_dir + "/Gyroscope.csv")
    acc_data = acc.values.tolist()
    gyro_data = gyro.values.tolist()

    measurement_readings = []
    current_sampling = SAMPLING_DELAY

    last_known_location = locations[0]

    curr_acc = (acc_data[0][1], acc_data[0][2], acc_data[0][3])
    curr_gyro = (gyro_data[0][1], gyro_data[0][2], gyro_data[0][3])

    while acc_data[-1][0] > current_sampling and gyro_data[-1][0] > current_sampling:

        next_acc_values = [value for value in acc_data
                           if value[0] > (current_sampling - SAMPLING_DELAY) if value[0] <= current_sampling]
        next_gyro_values = [value for value in gyro_data
                            if value[0] > (current_sampling - SAMPLING_DELAY) if value[0] <= current_sampling]

        if next_acc_values:
            curr_acc = (np.mean([acc[1] for acc in next_acc_values]),
                        np.mean([acc[2] for acc in next_acc_values]),
                        np.mean([acc[3] for acc in next_acc_values]))
        if next_gyro_values:
            curr_gyro = (np.mean([acc[1] for acc in next_gyro_values]),
                         np.mean([acc[2] for acc in next_gyro_values]),
                         np.mean([acc[3] for acc in next_gyro_values]))

        last_loc = [location for location in locations if location.offset_in_ms <= current_sampling]
        if last_loc:
            last_known_location = last_loc[-1]

        measurement_readings.append(MeasurementReading(offset_in_ms=current_sampling,
                                                       acc_x=curr_acc[0],
                                                       acc_y=curr_acc[1],
                                                       acc_z=curr_acc[2],
                                                       gyro_x=curr_gyro[0],
                                                       gyro_y=curr_gyro[1],
                                                       gyro_z=curr_gyro[2],
                                                       speed=last_known_location.speed,
                                                       lat=last_known_location.lat,
                                                       lng=last_known_location.lng))

        current_sampling += SAMPLING_DELAY

    measurements_df = pd.DataFrame.from_records([reading.to_dict() for reading in measurement_readings])
    measurements_df.to_json(target_dir + "/" + route_id + ".json", orient="records")

    # for sample in gyro_data:
    #     if len(acc[acc['System Time'] <= sample[0]]) != 0:
    #         curr_acc = acc[acc['System Time'] <= sample[0]].iloc[-1]
    #     else:
    #         curr_acc = acc.iloc[0]
    #
    #     last_loc = [location for location in locations if location.offset_in_ms <= sample[0]]
    #     if last_loc:
    #         last_known_location = last_loc[-1]
    #
    #     measurement_readings.append(MeasurementReading(offset_in_ms=sample[0],
    #                                                    acc_x=curr_acc['X Axis'],
    #                                                    acc_y=curr_acc['Y Axis'],
    #                                                    acc_z=curr_acc['Z Axis'],
    #                                                    gyro_x=sample[3],
    #                                                    gyro_y=sample[4],
    #                                                    gyro_z=sample[5],
    #                                                    speed=last_known_location.speed,
    #                                                    lat=last_known_location.lat,
    #                                                    lng=last_known_location.lng))
