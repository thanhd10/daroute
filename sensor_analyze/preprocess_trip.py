from typing import List, Tuple

import pandas as pd
from tqdm import tqdm

from attack_parameters import TURN_THRESHOLD
from definitions import TIME_COL, SPEED_COL, GYRO_Z_COL, ACC_X_COL, ACC_Y_COL
from schema.MeasurementModel import MeasurementModel
from schema.sensor_models import TemporaryVersionTurn, SensorTurnModel, TemporaryRoundabout, \
    TrafficLightModel
from sensor_analyze.helper.create_sensor_output import create_all_path_sections, create_traffic_lights
from sensor_analyze.helper.turn_analyzer import TurnCalculatorHeading, TurnCalculatorDistanceHeading
from sensor_analyze.roundabout.RoundaboutExtractor import RoundaboutClassifier
from sensor_analyze.traffic_light.TrafficLightExtractor import TrafficLightExtractor
from utils.angle_helper import calc_angle_change
from utils.file_reader import convert_json_to_iterator

######################################################################

# used frequency of data collection
SENSOR_DATA_FREQUENCY = 25

# time window in seconds that is used to validate, if currently driving in a corner
TIME_ENTER_CORNER_CHECK = 3.0

# Every x meters changes to the corner status should be validated
CORNER_CHECK_THRESHOLD = 1.0

USE_TURN_DISTANCE_HEADING = True

OVERLAP_EXTRA_RANGE = 1000


######################################################################


class SensorPreprocessor(object):
    """
    Preprocess raw data by doing following tasks:
    - find turning maneuvers and provide a list of SensorTurns
    - calculate driving direction at a given timestamp
    - calculate distance bridged between two measurements
    """

    def __init__(self, file_path: str, start_direction: int):
        # read in raw sensor data
        self.__json_iterator = convert_json_to_iterator(file_path)
        # setup direction of vehicle at the start of the trip
        self.__direction = start_direction
        self.__last_timestamp = 0
        # distance bridged since start of measurement
        self.__distance_since_start = 0

        if USE_TURN_DISTANCE_HEADING:
            self.__turn_calculator = TurnCalculatorDistanceHeading(TIME_ENTER_CORNER_CHECK, SENSOR_DATA_FREQUENCY)
        else:
            self.__turn_calculator = TurnCalculatorHeading(TIME_ENTER_CORNER_CHECK, SENSOR_DATA_FREQUENCY)

        self.__all_turns: [TemporaryVersionTurn] = []
        self.__all_measurements: [MeasurementModel] = []

    def preprocess(self):
        # distance bridged since last corner check
        current_distance_for_next_corner_check = 0
        # helper variable to find out, when a turn was finished
        is_last_measurement_in_corner = False

        for iteration in tqdm(self.__json_iterator, desc='Preprocess raw data'):
            bridged_distance = self.__calc_distance(iteration)
            self.__distance_since_start += bridged_distance
            current_distance_for_next_corner_check += bridged_distance

            self.__update_current_vehicle_position(bridged_distance, iteration)

            # after a specific distance, validate corner status again; reduces runtime massively
            if current_distance_for_next_corner_check >= CORNER_CHECK_THRESHOLD:
                is_last_measurement_in_corner = self.__check_corner_status(is_last_measurement_in_corner)
                current_distance_for_next_corner_check = 0

            # update timestamp for next iteration calculations
            self.__last_timestamp = iteration[TIME_COL]

            self.__all_measurements.append(MeasurementModel(iteration[GYRO_Z_COL], iteration[ACC_X_COL],
                                                            iteration[ACC_Y_COL],
                                                            self.__direction, bridged_distance,
                                                            self.__distance_since_start,
                                                            self.__last_timestamp,
                                                            iteration[SPEED_COL]))

    def __check_corner_status(self, is_last_measurement_in_corner: bool):
        # check if a turning maneuver is finished to create a new turn with angle and time frame
        is_currently_in_corner = self.__turn_calculator.is_in_corner()

        if is_last_measurement_in_corner & (not is_currently_in_corner):
            angle, time_in_turn = self.__turn_calculator.calc_angle_and_clear_buffer()

            if angle > TURN_THRESHOLD or angle < -TURN_THRESHOLD:
                self.__all_turns.append(
                    TemporaryVersionTurn(direction_before=self.__direction - angle,
                                         direction_after=self.__direction,
                                         angle=angle,
                                         start_time=self.__last_timestamp - time_in_turn,
                                         end_time=self.__last_timestamp)
                )
        return is_currently_in_corner

    def __update_current_vehicle_position(self, bridged_distance: float, iteration: []):
        """
        update direction and position of vehicle, if vehicle moved; also add value to turn calculator
        checking whether the vehicle moved to consider measurement reduces noise created while standing still
        """
        if bridged_distance != 0.0:
            angle = calc_angle_change(gyro_z=iteration[GYRO_Z_COL],
                                      time=iteration[TIME_COL] - self.__last_timestamp)
            self.__direction += angle
            self.__turn_calculator.add_measurement(angle, bridged_distance)

    def __calc_distance(self, iteration: []):
        """
        formula: passed time in seconds * current speed in km/h
        """
        return (iteration[TIME_COL] - self.__last_timestamp) / 1000 * iteration[SPEED_COL]

    def get_measurements_as_trip_df(self) -> pd.DataFrame:
        return pd.DataFrame.from_records([measurement.to_dict() for measurement in self.__all_measurements])

    def get_sensor_turns_and_traffic_lights(self) -> Tuple[List[SensorTurnModel], List[TrafficLightModel]]:
        # find roundabouts
        measurements_df = self.get_measurements_as_trip_df()
        roundabout_classifier = RoundaboutClassifier(measurements_df)
        roundabouts = roundabout_classifier.find_roundabouts()

        # combine turns and roundabouts to a unified sequence
        aggregated_turns = self.__aggregate_roundabouts_and_turns(roundabouts)
        path_sections = create_all_path_sections(aggregated_turns, measurements_df)

        # extract traffic lights
        traffic_light_classifier = TrafficLightExtractor(measurements_df)
        temporary_traffic_lights = traffic_light_classifier.find_traffic_lights()
        traffic_lights = create_traffic_lights(path_sections, temporary_traffic_lights, measurements_df)

        return path_sections, traffic_lights

    def __aggregate_roundabouts_and_turns(self, roundabouts: [TemporaryRoundabout]) -> [TemporaryVersionTurn]:
        turns_to_filter = set()
        for roundabout in roundabouts:
            # query all temporary turns, that overlap with a roundabout
            turns_to_filter.update([turn for turn in self.__all_turns
                                    if self.__check_time_frame_overlap(roundabout.start_time, roundabout.end_time,
                                                                       turn.start_time, turn.end_time)])

        # remove all turns, that overlap in time with a roundabout
        turns = list(set(self.__all_turns) - turns_to_filter)
        turns.extend(roundabouts)
        turns.sort(key=lambda x: x.start_time)
        return turns

    def __check_time_frame_overlap(self, start_time_roundabout: int, end_time_roundabout: int,
                                   start_time_turn: int, end_time_turn: int) -> bool:
        """ Check whether the time frames of a recognized roundabout and turn overlaps """
        return ((start_time_turn > start_time_roundabout - OVERLAP_EXTRA_RANGE) &
                (start_time_turn < start_time_roundabout + OVERLAP_EXTRA_RANGE)) | \
               ((end_time_turn > start_time_roundabout - OVERLAP_EXTRA_RANGE) &
                (end_time_turn < end_time_roundabout + OVERLAP_EXTRA_RANGE))
