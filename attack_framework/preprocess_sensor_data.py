import pandas as pd

from definitions import ROOT_DIR
from definitions import TIME_COL
from schema.sensor_models import RoundaboutTurnModel
from sensor_analyze.preprocess_trip import SensorPreprocessor
from visualize.visualize_route import visualize_trip
from visualize.visualize_sensor import visualize_sensor_data

"""
Set Name of trip and the initial heading to preprocess sensor readings
"""

######################################################################

FILE_NAME = "Route_A28"
START_DIRECTION = 135

JSON_SENSOR_FILE_PATH = ROOT_DIR + "/data/prep_trips/" + FILE_NAME + ".json"
GPS_TRIP_FILE_PATH = ROOT_DIR + "/data/real_trips/" + FILE_NAME + ".html"

# store measurements for test cases
MEASUREMENT_TARGET_DIR = ROOT_DIR + "/test/measurements/Measurements_" + FILE_NAME + ".csv"


######################################################################


def shorten_prep_trip(file_path: str, start: int = None, end: int = None):
    trip = pd.read_json(file_path)
    if start is None:
        start = 0
    if end is None:
        end = trip[TIME_COL].max()
    trip = trip[(trip[TIME_COL] >= start) & (trip[TIME_COL] <= end)]
    trip[TIME_COL] = trip[TIME_COL] - trip[TIME_COL].min()
    trip.to_json(file_path, orient='records')


if __name__ == '__main__':
    sensor_preprocessor = SensorPreprocessor(JSON_SENSOR_FILE_PATH, START_DIRECTION)
    sensor_preprocessor.preprocess()
    turn_sequence, all_traffic_lights = sensor_preprocessor.get_sensor_turns_and_traffic_lights()

    # TODO fix order of attributes after implementing traffic lights
    print("All SensorTurnModel's:")
    for sensor_turn in turn_sequence:
        if isinstance(sensor_turn, RoundaboutTurnModel):
            print('RoundaboutTurnModel(%d, %.2f, %.2f, %.2f, %.2f, %.2f, %d, %d, %d),' % (sensor_turn.order,
                                                                                          sensor_turn.angle,
                                                                                          sensor_turn.direction_before,
                                                                                          sensor_turn.direction_after,
                                                                                          sensor_turn.distance_before,
                                                                                          sensor_turn.distance_after,
                                                                                          sensor_turn.estimated_intersection_time,
                                                                                          sensor_turn.turn_start,
                                                                                          sensor_turn.turn_end))
        else:
            print('SensorTurnModel(%d, %.2f, %.2f, %.2f, %.2f, %.d, %d, %d),' % (sensor_turn.order,
                                                                                 sensor_turn.angle,
                                                                                 sensor_turn.direction_after,
                                                                                 sensor_turn.distance_before,
                                                                                 sensor_turn.distance_after,
                                                                                 sensor_turn.estimated_intersection_time,
                                                                                 sensor_turn.turn_start,
                                                                                 sensor_turn.turn_end))

    print("All TrafficLightModel's:")
    for traffic_light in all_traffic_lights:
        print('TrafficLightModel(%d, %d, %.2f, %.d, %.d),' % (traffic_light.start_turn,
                                                              traffic_light.end_turn,
                                                              traffic_light.distance_after_start_turn,
                                                              traffic_light.start_time,
                                                              traffic_light.end_time))

    trip_df = sensor_preprocessor.get_measurements_as_trip_df()
    # store for testing purposes
    trip_df.to_csv(MEASUREMENT_TARGET_DIR, index=False)

    visualize_trip(JSON_SENSOR_FILE_PATH, GPS_TRIP_FILE_PATH)
    visualize_sensor_data(trip_df, y_axis='direction')
