from multiprocessing import Pool
from typing import Dict, List, Tuple, Union

import pandas as pd

from attack_parameters import TURN_THRESHOLD, TURN_ANGLE_ERROR_TOLERANCE, STRAIGHT_DRIVE_THRESHOLD, \
    DISTANCE_ERROR_TOLERANCE, MAGNETOMETER_DIRECTION_ERROR, ROAD_WIDTH_THRESHOLD, MAX_HEADING_CHANGE_DEVIATION
from schema.sensor_models import SensorTurnModel, RoundaboutTurnModel
from utils.angle_helper import get_binary_directions_with_tolerance
from utils.functions import merge_dicts

######################################################################

TRAVEL_OPTION_USE_COLS = ['segment_start_id', 'segment_target_id', 'distance_after', 'intersection_id',
                          'heading_change']


######################################################################

class TurnPairMatcher(object):
    def __init__(self,
                 turn_candidates_b: pd.DataFrame,
                 distance_a_b: float,
                 heading_change_a_b: float,
                 turns_df: pd.DataFrame):
        # databases for queries
        # only the rows within the "straight driving" threshold are relevant here
        # remove segment skipping units, as these don't provide additional info about paths
        self.travel_options = turns_df[(turns_df['angle'] > -STRAIGHT_DRIVE_THRESHOLD) &
                                       (turns_df['angle'] < STRAIGHT_DRIVE_THRESHOLD) &
                                       (~turns_df['is_segment_skipping'])][TRAVEL_OPTION_USE_COLS]

        # segments desired to reach, as here the next turn would start
        self.start_segments_of_turn_b = turn_candidates_b['segment_start_id']

        self.distance_error_tolerance_in_meters = distance_a_b * DISTANCE_ERROR_TOLERANCE
        self.upper_bound_distance = distance_a_b + self.distance_error_tolerance_in_meters + ROAD_WIDTH_THRESHOLD
        self.lower_bound_distance = distance_a_b - self.distance_error_tolerance_in_meters - ROAD_WIDTH_THRESHOLD

        self.heading_change_a_b = heading_change_a_b

    def match_turn_to_candidates(self, turn_id: int, target_seg: int,
                                 distance_start_center: float) -> Dict[Tuple[int, int], List[int]]:
        # store all routes, that can be taken, when driving straight along the road from intersection
        # start_id to center_id. start_id should be the turn whose valid matches are being searched for
        possible_routes_from_current_a = []
        # store the current route taken from 'a' to track the route to a corresponding target
        current_route_to_candidate = [target_seg]
        self.__find_intersections_by_distance(next_start_segment=target_seg,
                                              curr_distance_bridged=0.0,
                                              distance_to_target=distance_start_center,
                                              curr_heading_change=0.0,
                                              heading_change_to_target=0.0,
                                              possible_routes_from_a=possible_routes_from_current_a,
                                              current_route_node_path=current_route_to_candidate,
                                              passed_intersections=[])

        # return all routes with turns, that are reachable from 'a' and are possible turn candidates for 'b'
        valid_candidates = [route for route in possible_routes_from_current_a if
                            route[-1] in self.start_segments_of_turn_b.unique()]

        # create a dict, where the key is a tuple of matched turns and the value the path between them
        turn_pair_to_route_dict = dict()
        for valid_candidate in valid_candidates:
            target_turns = self.start_segments_of_turn_b.index[self.start_segments_of_turn_b == valid_candidate[-1]]
            for target_turn in target_turns:
                turn_pair_to_route_dict[(turn_id, target_turn)] = valid_candidate

        return turn_pair_to_route_dict

    def __find_intersections_by_distance(self,
                                         next_start_segment: int,
                                         curr_distance_bridged: float,
                                         distance_to_target: float,
                                         curr_heading_change: float,
                                         heading_change_to_target: float,
                                         possible_routes_from_a: [[int]],
                                         current_route_node_path: [int],
                                         passed_intersections: [int]):
        # add the bridged distance between the two current intersections
        curr_distance_bridged += distance_to_target

        # add all intersections, that are reachable from candidate 'a' and fulfill condition, that:
        # distance d is between (d_a_b - thresh) and (d_a_b + thresh) and heading change does not exceed filter
        if curr_distance_bridged > self.upper_bound_distance:
            return
        elif curr_distance_bridged > self.lower_bound_distance and \
                abs(self.heading_change_a_b - curr_heading_change) < MAX_HEADING_CHANGE_DEVIATION:
            # deep copy route from 'a' to potential 'b', so later changes don't affect the already added routes
            possible_routes_from_a.append([node for node in current_route_node_path])

        # get all intersections, that can be reached without turning
        next_targets = self.travel_options[self.travel_options['segment_start_id'] == next_start_segment]

        # do not consider heading change directly before a possible turns, so add heading_change_to_target afterward
        curr_heading_change += heading_change_to_target

        # recursive call; recursion also stops, when no intersection is reachable without a turn
        for next_target, next_intersection, next_distance, next_heading_change in zip(next_targets['segment_target_id'],
                                                                                      next_targets['intersection_id'],
                                                                                      next_targets['distance_after'],
                                                                                      next_targets['heading_change']):
            # don't allow loops when 'driving straight', as it's unlikely with the high straight travel threshold
            if next_intersection in passed_intersections:
                continue

            # traverse forward by storing traversed path
            current_route_node_path.append(next_target)
            passed_intersections.append(next_intersection)

            self.__find_intersections_by_distance(next_start_segment=next_target,
                                                  curr_distance_bridged=curr_distance_bridged,
                                                  distance_to_target=next_distance,
                                                  curr_heading_change=curr_heading_change,
                                                  heading_change_to_target=next_heading_change,
                                                  possible_routes_from_a=possible_routes_from_a,
                                                  current_route_node_path=current_route_node_path,
                                                  passed_intersections=passed_intersections)
            # 'backtrack' one step from current route path originating from 'a'
            current_route_node_path.pop()
            passed_intersections.pop()


def match_all_turn_pairs_a_b(turn_pair_matcher: TurnPairMatcher, turn_candidates_a: pd.DataFrame) \
        -> Dict[Tuple[int, int], List[int]]:
    """
    Match all turn candidates for turn a and all turn candidates for turn b with each other, that are set in
    turn_pair_matcher. Method is defined as function and not part of the class TurnPairMatcher, as multiprocessing
    wouldn't work like that.
    :param turn_candidates_a: turn candidates, from where all possible paths are traversed
    :param turn_pair_matcher: an instance of TurnPairMatcher used to run the matching
    :return: a list of turn-pairs created from the candidates of turn a + b
    """
    with Pool() as pool:
        matched_turns = pool.starmap(turn_pair_matcher.match_turn_to_candidates,
                                     zip(turn_candidates_a.index,
                                         turn_candidates_a['segment_target_id'],
                                         turn_candidates_a['distance_after'])
                                     )
    return merge_dicts(matched_turns)


def get_turn_candidates(turns_df: pd.DataFrame,
                        sensor_turn: Union[SensorTurnModel, RoundaboutTurnModel]) -> pd.DataFrame:
    """
    Depending on the input parameters suitable turn candidates should be queried in the dataframe:
        1. the angle of a valid turn should be inside the given threshold
        2. the end_direction after the turn should be inside the given magnetometer threshold
        3. the distance BEFORE taking the turn can't be higher than the measured distance between the last intersection
           and the intersection, where the turn is taking place
        4. the distance AFTER taking the turn to the next intersection can't be higher than the measured distance
           between intersection, where the turn is taking place and the next intersection
    """

    binary_directions = get_binary_directions_with_tolerance(sensor_turn.direction_after, MAGNETOMETER_DIRECTION_ERROR)

    max_distance_before = sensor_turn.distance_before + (
            sensor_turn.distance_before * DISTANCE_ERROR_TOLERANCE) + ROAD_WIDTH_THRESHOLD
    max_distance_after = sensor_turn.distance_after + (
            sensor_turn.distance_after * DISTANCE_ERROR_TOLERANCE) + ROAD_WIDTH_THRESHOLD

    max_allowed_angle = sensor_turn.angle + TURN_ANGLE_ERROR_TOLERANCE
    min_allowed_angle = sensor_turn.angle - TURN_ANGLE_ERROR_TOLERANCE

    if isinstance(sensor_turn, RoundaboutTurnModel):
        return turns_df[(turns_df['is_roundabout']) &
                        (turns_df['end_direction'].isin(binary_directions)) &
                        (turns_df['distance_before'] < max_distance_before) &
                        (turns_df['distance_after'] < max_distance_after)]
    else:
        return turns_df[(turns_df['angle'] > min_allowed_angle) &
                        (turns_df['angle'] < max_allowed_angle) &
                        (turns_df['end_direction'].isin(binary_directions)) &
                        (turns_df['distance_before'] < max_distance_before) &
                        (turns_df['distance_after'] < max_distance_after)]


def filter_turns_df_to_only_turns(turns_df: pd.DataFrame) -> pd.DataFrame:
    """
    as turns_df contains all possible routes that can be taken at an intersection, a pre-filtering can be done before
    calling get_turn_candidates to reduce the search space even more
    """
    return turns_df[
        (turns_df['angle'] >= TURN_THRESHOLD) | (turns_df['angle'] <= -TURN_THRESHOLD) | turns_df['is_roundabout']]
