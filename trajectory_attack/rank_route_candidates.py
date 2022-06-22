from multiprocessing import Pool
from typing import Dict, List, Tuple

import pandas as pd

from attack_parameters import TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT, \
    DISTANCE_ERROR_TOLERANCE, TRAFFIC_LIGHT_MAX_SPEED_LIMIT
from schema.RouteCandidateModel import RouteCandidateModel
from schema.sensor_models import SensorTurnModel, TrafficLightModel
from utils.functions import average_reduce


class RouteCandidateRanker(object):
    def __init__(self,
                 sensor_turns: [SensorTurnModel],
                 discovered_traffic_lights: [TrafficLightModel],
                 trip_df: pd.DataFrame,
                 turns_df: pd.DataFrame,
                 segments_df: pd.DataFrame):
        self.sensor_turns = sensor_turns
        self.traffic_lights = discovered_traffic_lights
        self.trip_df = trip_df[['distance', 'direction', 'timestamp']]

        self.turn_to_angle = turns_df['angle']
        self.segment_start_and_target_to_heading_change = turns_df.set_index(
            ['segment_start_id', 'segment_target_id']).to_dict()['heading_change']

        self.segments_df = segments_df[['distance', 'distance_to_traffic_light', 'speed_limit']]

    def rank_route_candidate(self, route_candidate: [int], road_section_paths: [[int]]) -> RouteCandidateModel:
        """
        Calculate likelihood and filter route candidates after defined rules.
        """
        full_route = []

        sum_distance_penalty = 0
        sum_heading_change_penalty = 0
        num_traffic_lights = 0
        # summed penalty is devided by number of curvature samples in the end
        sum_curvature_penalty = 0
        curvature_samples = 0

        # TODO remove again
        heading_change_errors = []

        # validate two turn directions at each step
        for i in range(len(route_candidate) - 1):
            # get all complete paths between two turns
            route_section_path = road_section_paths[i]

            # Adjust Traffic Light Score
            found_tls = self.__get_found_traffic_lights(route_section_path, i)
            if found_tls == -1:
                # filter out candidate, as traffic light is not allowed to occur at specific speed limit
                return RouteCandidateModel(route_candidate, [], 0, 0, 0, 0, 0, is_filtered_traffic_light=True)
            else:
                num_traffic_lights += found_tls

            # Adjust Distance Score
            expected_distance = sum([self.segments_df.loc[segment_id]['distance'] for segment_id in route_section_path])
            sum_distance_penalty += self.__calc_distance_deviation(self.sensor_turns[i].distance_after,
                                                                   expected_distance)

            # Adjust Heading Score
            sum_heading_change_penalty += self.__calc_heading_change_deviation(
                (self.sensor_turns[i + 1].direction_before - self.sensor_turns[i].direction_after), route_section_path)

            # Adjust Curvature Score
            next_curvature_penalty, next_curvature_samples = self.__get_curvature_deviation(route_section_path,
                                                                                            i,
                                                                                            expected_distance)
            sum_curvature_penalty += next_curvature_penalty
            curvature_samples += next_curvature_samples

            # Store segment route section
            full_route.extend(route_section_path)

            # TODO remove again
            heading_change_errors.append(
                self.get_heading_error(
                    (self.sensor_turns[i + 1].direction_before - self.sensor_turns[i].direction_after),
                    route_section_path))

        # average summed penalty afterward
        distance_score = sum_distance_penalty / (len(route_candidate) - 1)
        heading_change_score = sum_heading_change_penalty / (len(route_candidate) - 1)
        curvature_score = self.__calc_curvature_score(sum_curvature_penalty, curvature_samples)
        angle_score = self.__calc_angle_score(route_candidate)
        traffic_light_score = self.__calc_traffic_light_score(num_traffic_lights)

        return RouteCandidateModel(route_candidate, full_route, distance_score, angle_score,
                                   heading_change_score, traffic_light_score, curvature_score,
                                   heading_change_errors=heading_change_errors,
                                   turn_angle_errors=self.get_angle_errors(route_candidate))

    def __get_curvature_deviation(self, road_segments: [int], turn_start_index: int,
                                  expected_distance: float) -> Tuple[float, int]:
        """
        After each road segment, take a curvature deviation sample by comparing the current heading change within
        the measurements with the expected heading change due to the road.
        :return the summed heading deviation samples + the number of taken samples.
        """
        # retrieve measurements between current turns
        trip_for_turns = self.trip_df[(self.trip_df['timestamp'] >= self.sensor_turns[turn_start_index].turn_end) &
                                      (self.trip_df['timestamp'] <= self.sensor_turns[turn_start_index + 1].turn_start)]
        # distance deviates slightly from measurement between two intersections, as df contains measurements
        # after finishing the turn and before starting the next turn for more precise direction values
        measured_distance = trip_for_turns['distance'].sum()

        # remove initial heading after the start turn from heading samples to retrieve the absolute heading change
        initial_measurement_heading = trip_for_turns['direction'].iloc[0]

        # store the current heading change within the map route
        curr_expected_heading_change = 0

        sum_curvature_deviation = 0
        curvature_samples = 0

        curr_distance_bridged = 0
        for segment_a, segment_b in zip(road_segments[:-1], road_segments[1:]):
            # 'Move' forward on segment route to compare with sensor data
            curr_distance_bridged += self.segments_df.loc[segment_a]['distance']
            curr_expected_heading_change += self.segment_start_and_target_to_heading_change[(segment_a, segment_b)]

            # get measured heading at approximate position of current road segment and then the current heading change
            next_measurement_heading = trip_for_turns[
                trip_for_turns['distance'].cumsum() >= (curr_distance_bridged / expected_distance) * measured_distance][
                'direction'].iloc[0]
            heading_change = next_measurement_heading - initial_measurement_heading

            # values to return and to later average
            sum_curvature_deviation += abs(heading_change - curr_expected_heading_change)
            curvature_samples += 1

        return sum_curvature_deviation, curvature_samples

    def __get_found_traffic_lights(self, road_segments: [int], turn_start_index: int) -> int:
        """ Receive the number of correctly found traffic lights. In the end, a penalty score should be determined. """
        # retrieve current traffic lights
        curr_traffic_lights = [traffic_light for traffic_light in self.traffic_lights
                               if traffic_light.start_turn == turn_start_index
                               if traffic_light.end_turn == turn_start_index + 1]

        num_traffic_lights = 0
        # traffic lights are ordered, so no need to iterate over all segments again, when traffic lights can't occur
        # in previous, already passed segments
        num_segments_iterated = 0
        curr_distance_bridged = 0

        for light in curr_traffic_lights:
            # a traffic light should be positioned between these two distances (estimates through sensor data)
            latest_traffic_light_position = light.distance_after_start_turn + \
                                            light.distance_after_start_turn * DISTANCE_ERROR_TOLERANCE + \
                                            TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT
            min_traffic_light_position = light.distance_after_start_turn - \
                                         light.distance_after_start_turn * DISTANCE_ERROR_TOLERANCE

            for segment in road_segments[num_segments_iterated:]:
                if curr_distance_bridged > latest_traffic_light_position:
                    # passed traffic light already
                    break
                elif self.segments_df.loc[segment]['distance_to_traffic_light'] != -1:
                    # estimate position of traffic light on route for comparison with sensor data
                    next_traffic_light_position = curr_distance_bridged + self.segments_df.loc[segment][
                        'distance_to_traffic_light']

                    if next_traffic_light_position > latest_traffic_light_position:
                        # estimated position passed possible traffic light already, continue with the next one
                        break
                    elif next_traffic_light_position > min_traffic_light_position:
                        # traffic light found, continue with the next one
                        num_traffic_lights += 1
                        break
                    else:
                        # move on to the next segment
                        curr_distance_bridged += self.segments_df.loc[segment]['distance']
                        num_segments_iterated += 1

                elif curr_distance_bridged > min_traffic_light_position and \
                        self.segments_df.loc[segment]['speed_limit'] >= TRAFFIC_LIGHT_MAX_SPEED_LIMIT:
                    # filter out candidate, as traffic light is not allowed to occur at this speed limit
                    return -1
                else:
                    # move on to the next segment
                    curr_distance_bridged += self.segments_df.loc[segment]['distance']
                    num_segments_iterated += 1

        return num_traffic_lights

    def __calc_curvature_score(self, sum_curvature_penalty: float, curvature_samples: int) -> float:
        if curvature_samples != 0:
            return sum_curvature_penalty / curvature_samples
        else:
            print("Warning: No curvature samples found.")
            return 0

    def __calc_traffic_light_score(self, num_traffic_lights_matched: int) -> float:
        """ Get the error rate of traffic light matches. """
        if len(self.traffic_lights) != 0:
            # calculate a penalty score to minimize
            return 1 - (num_traffic_lights_matched / len(self.traffic_lights))
        else:
            return 0

    def __calc_heading_change_deviation(self, measured_heading_change: float, road_segments: [int]) -> float:
        """
        Calc deviation of each heading change between two turns.
        Intuitively, it might be faster to combine this calculation with taking curvature samples.
        But separating both score calculations was way faster due to early filtering of route candidates,
        as repeated pandas lookups in taking curvature samples is quite expensive.
        """
        expected_heading_change = 0
        next_heading_change = 0
        for segment_a, segment_b in zip(road_segments[:-1], road_segments[1:]):
            next_heading_change = self.segment_start_and_target_to_heading_change[(segment_a, segment_b)]
            expected_heading_change += next_heading_change

        # remove last heading change, as beginning of the next turn influences it
        expected_heading_change -= next_heading_change

        return abs(measured_heading_change - expected_heading_change)

    def __calc_distance_deviation(self, measured_distance: float, expected_distance) -> float:
        """ Calc deviation of each distance between two turns """
        return abs(measured_distance - expected_distance)

    def __calc_angle_score(self, route_candidate: [int]) -> float:
        """ Calc deviation for each turn and return average deviation """
        expected_angles = [abs(self.turn_to_angle.loc[turn]) for turn in route_candidate]
        measured_angles = [abs(sensor_turn.angle) for sensor_turn in self.sensor_turns]

        return average_reduce([abs(measured - expected)
                               for measured, expected in zip(measured_angles, expected_angles)])

    # TODO remove again
    def get_angle_errors(self, route_candidate: [int]) -> List[float]:
        expected_angles = [self.turn_to_angle.loc[turn] for turn in route_candidate]
        measured_angles = [sensor_turn.angle for sensor_turn in self.sensor_turns]

        return [measured - expected
                for measured, expected in zip(measured_angles, expected_angles)]

    # TODO remove again
    def get_heading_error(self, measured_heading_change: float, road_segments: [int]) -> float:
        expected_heading_change = 0
        next_heading_change = 0
        for segment_a, segment_b in zip(road_segments[:-1], road_segments[1:]):
            next_heading_change = self.segment_start_and_target_to_heading_change[(segment_a, segment_b)]
            expected_heading_change += next_heading_change

        # remove last heading change, as beginning of the next turn influences it
        expected_heading_change -= next_heading_change

        return measured_heading_change - expected_heading_change


def __normalize_scores(route_candidates: [RouteCandidateModel]):
    """ After multiprocessing, the scores of the candidates should be normalized between 0 and 1. """
    all_distance_scores = [route.distance_score for route in route_candidates]
    all_angle_scores = [route.angle_score for route in route_candidates]
    all_heading_change_scores = [route.heading_change_score for route in route_candidates]
    all_curvature_scores = [route.curvature_score for route in route_candidates]

    # Extract parameters for Normalization equation: (X - X_min) / (X_max - X_min)
    try:
        x_dist_min = min(all_distance_scores)
        x_dist_max = max(all_distance_scores)
        x_angle_min = min(all_angle_scores)
        x_angle_max = max(all_angle_scores)
        x_heading_change_min = min(all_heading_change_scores)
        x_heading_change_max = max(all_heading_change_scores)
        x_curvature_min = min(all_curvature_scores)
        x_curvature_max = max(all_curvature_scores)
    except (ValueError, TypeError):
        print("Warning: Error while retrieving min and max values for score normalization.")
        # all candidates filtered out, return
        return

    for route in route_candidates:
        try:
            route.normalize_distance_score(x_dist_min, x_dist_max)
            route.normalize_angle_score(x_angle_min, x_angle_max)
            route.normalize_heading_change_score(x_heading_change_min, x_heading_change_max)
            route.normalize_curvature_score(x_curvature_min, x_curvature_max)
        except ZeroDivisionError:
            print("Warning: ZeroDivisionError found while normalizing.")
            pass


def get_segment_paths(route_candidate: [int], turn_pair_to_segments_route_dict: [int]) -> [[int]]:
    """ Get segment paths between each turn pair as a list """
    section_paths = []
    for i in range(len(route_candidate) - 1):
        next_turn_pair = (route_candidate[i], route_candidate[i + 1])
        section_paths.append(turn_pair_to_segments_route_dict[next_turn_pair])
    return section_paths


def get_ranked_route_candidates(route_candidates: [[int]],
                                turn_pair_to_segments_route_dict: Dict[Tuple[int, int], List[int]],
                                sensor_turns: [SensorTurnModel],
                                discovered_traffic_lights: [TrafficLightModel],
                                measurements_df: pd.DataFrame,
                                turns_df: pd.DataFrame,
                                segments_df: pd.DataFrame) -> [RouteCandidateModel]:
    """
     Parallelized Function to receive a sorted list of route candidates.
     Method is defined as function and not part of RouteCandidateRanker, as multiprocessing wouldn't work like that.
     :return: a list of ranked route candidates
     """

    if not route_candidates:
        return []

    full_route_creator = RouteCandidateRanker(sensor_turns,
                                              discovered_traffic_lights,
                                              measurements_df,
                                              turns_df,
                                              segments_df)

    # retrieve segment paths between turns already, so intensive copying of dict is not done in multiprocessing
    section_paths_for_routes = [get_segment_paths(candidate, turn_pair_to_segments_route_dict) for candidate in
                                route_candidates]

    with Pool() as pool:
        route_candidates = pool.starmap(full_route_creator.rank_route_candidate,
                                        zip(route_candidates, section_paths_for_routes))

    # filter and sort candidates
    route_candidates = [route for route in route_candidates
                        if not route.is_filtered_heading
                        if not route.is_filtered_traffic_light]
    __normalize_scores(route_candidates)
    route_candidates.sort(key=lambda x: x.calc_general_normalized_score(), reverse=False)

    return route_candidates


def get_ranked_route_candidates_with_filtered(route_candidates: [[int]],
                                              turn_pair_to_segments_route_dict: Dict[Tuple[int, int], List[int]],
                                              sensor_turns: [SensorTurnModel],
                                              discovered_traffic_lights: [TrafficLightModel],
                                              measurements_df: pd.DataFrame,
                                              turns_df: pd.DataFrame,
                                              segments_df: pd.DataFrame) -> Tuple[List[RouteCandidateModel],
                                                                                  List[RouteCandidateModel]]:
    """
     Function also returns the route candidates, that were filtered for Evaluation purposes.
     Parallelized Function to receive a sorted list of route candidates.
     Method is defined as function and not part of RouteCandidateRanker, as multiprocessing wouldn't work like that.
     :return: a list of ranked route candidates
     """

    if not route_candidates:
        return [], []

    full_route_creator = RouteCandidateRanker(sensor_turns,
                                              discovered_traffic_lights,
                                              measurements_df,
                                              turns_df,
                                              segments_df)

    # retrieve segment paths between turns already, so intensive copying of dict is not done in multiprocessing
    section_paths_for_routes = [get_segment_paths(candidate, turn_pair_to_segments_route_dict) for candidate in
                                route_candidates]

    with Pool() as pool:
        route_candidates = pool.starmap(full_route_creator.rank_route_candidate,
                                        zip(route_candidates, section_paths_for_routes))

    # filter and sort candidates
    route_candidates_filtered = [route for route in route_candidates
                                 if not route.is_filtered_heading
                                 if not route.is_filtered_traffic_light]
    __normalize_scores(route_candidates_filtered)
    route_candidates_filtered.sort(key=lambda x: x.calc_general_normalized_score(), reverse=False)

    return route_candidates_filtered, route_candidates
