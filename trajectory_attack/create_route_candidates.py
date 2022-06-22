from typing import Dict, List, Tuple

import pandas as pd
from tqdm import tqdm

from schema.sensor_models import SensorTurnModel, TrafficLightModel
from trajectory_attack.helper.connect_part_routes import connect_part_routes
from trajectory_attack.helper.match_turns import TurnPairMatcher, match_all_turn_pairs_a_b, \
    get_turn_candidates, filter_turns_df_to_only_turns
from trajectory_attack.rank_route_candidates import get_ranked_route_candidates
from utils.functions import map_list_to_list_of_lists

######################################################################

USE_COLS = ['segment_start_id', 'segment_target_id', 'angle', 'end_direction', 'distance_before',
            'distance_after', 'is_roundabout', 'is_segment_skipping', 'intersection_id', 'heading_change']


######################################################################

class RouteCandidateCreator(object):
    """
    Route candidates are created by this class, where each candidate is a sequence of turns representing the route.
    Each element in a candidate is an index refering to the turn within the turns_df.
    """

    def __init__(self, turn_sequence: [SensorTurnModel], turns_df: pd.DataFrame):
        self.turns_df = turns_df[USE_COLS]
        self.turn_candidates_dict = self.__init_turn_candidates_dict(turn_sequence)
        self.turn_sequence = turn_sequence

        # store turn pairs to later recreate full path of segments
        self.turn_pair_to_segment_route = dict()

    def create_new_route_candidates(self) -> [[int]]:
        part_route_candidates = self.__init_part_route_candidates(self.turn_candidates_dict.values())
        # the number of turns a part route contains after each iteration in the while-loop, except the last ones
        curr_part_route_length = 1
        # loop until all part_route_candidates are paired with each other to create route-candidates
        while len(part_route_candidates) > 1:
            new_routes_per_iteration = []

            # At each for-loop iteration two part-route-candidates should be paired -> "pair-wise" route matching
            for part_route_index in tqdm(
                    range(0, len(part_route_candidates) - 1, 2),
                    desc="Combine %d part route candidates with part route length %d"
                         % (len(part_route_candidates), curr_part_route_length)):
                # retrieve indices of the current turns that should be connected
                start_index, target_index = self.__determine_current_turn_indices(part_route_index,
                                                                                  curr_part_route_length)

                turn_pairs = self.__connect_turns_to_pairs(part_route_candidates, part_route_index,
                                                           start_index, target_index)
                self.turn_pair_to_segment_route.update(turn_pairs)
                # extract the keys to connect part routes, as each of these keys are a tuple of matched turns
                current_routes = connect_part_routes(list(turn_pairs.keys()), part_route_candidates, part_route_index)
                new_routes_per_iteration.append(current_routes)

            # with an uneven number of turns no pair-wise matching can be done until the very end
            if len(part_route_candidates) % 2 != 0:
                new_routes_per_iteration.append(part_route_candidates[-1])
            # assign reduced part routes from combining
            part_route_candidates = new_routes_per_iteration

            # as part routes are combined pairwise, their length is doubled after each step
            curr_part_route_length *= 2

        # no part routes left, so index the list of complete route candidates
        return part_route_candidates[0]

    def __init_turn_candidates_dict(self, turn_sequence: [SensorTurnModel]) -> Dict[int, pd.DataFrame]:
        turn_candidates_dict = dict()
        only_turns_df = filter_turns_df_to_only_turns(self.turns_df)
        # Query all possible turns for each "turn from sensor" and add them to a dict
        # Also take all intersection_id's for each "turn from sensor" and add them to the route_candidates
        for part_route_index, turn in enumerate(turn_sequence):
            turn_candidates_dict[part_route_index] = get_turn_candidates(only_turns_df, turn)

        return turn_candidates_dict

    # noinspection PyMethodMayBeStatic
    def __init_part_route_candidates(self, turn_candidates: [pd.DataFrame]) -> List[List[List[int]]]:
        # should contain a list (with length equals to number of turns in turn_sequence) of list of part routes,
        # that will be connected successively
        return [map_list_to_list_of_lists(current_candidates.index) for current_candidates in
                turn_candidates]

    # noinspection PyMethodMayBeStatic
    def __determine_current_turn_indices(self, part_route_index: int, curr_part_route_length: int) -> Tuple[int, int]:
        # calculate and take the last turn index in dict from the first part-route-candidate
        # subtract - 1, as dict-indices start with 0
        start = curr_part_route_length * (1 + part_route_index) - 1
        # take the first turn index in dict from the second part-route-candidate
        end = start + 1
        return start, end

    def __connect_turns_to_pairs(self, part_route_candidates: [[int]],
                                 part_route_index: int, start_turn_index: int, target_turn_index: int) -> [[int]]:

        # retrieve all possible last turns of and first turns for corresponding part-route-candidates
        last_turn_indices_of_start = [route[-1] for route in part_route_candidates[part_route_index]]
        first_turn_indices_of_end = [route[0] for route in part_route_candidates[part_route_index + 1]]
        # filter turns by reduced turn-candidates (from each part-route-connection iteration)
        self.turn_candidates_dict[start_turn_index] = \
            self.turn_candidates_dict[start_turn_index].loc[last_turn_indices_of_start]

        self.turn_candidates_dict[target_turn_index] = \
            self.turn_candidates_dict[target_turn_index].loc[first_turn_indices_of_end]

        # the heading change measured between the next turn pair
        measured_heading_change = self.turn_sequence[start_turn_index + 1].direction_before - self.turn_sequence[
            start_turn_index].direction_after

        # match the last turns of the first part-routes with the first turns of the second part-routes
        pair_matcher = TurnPairMatcher(self.turn_candidates_dict[target_turn_index],
                                       self.turn_sequence[start_turn_index].distance_after,
                                       measured_heading_change,
                                       self.turns_df)
        return match_all_turn_pairs_a_b(pair_matcher, self.turn_candidates_dict[start_turn_index])


def get_all_route_candidates(turn_sequence: [SensorTurnModel], traffic_lights: [TrafficLightModel],
                             measurements_df: pd.DataFrame,
                             turns_df: pd.DataFrame, road_segments_df: pd.DataFrame) -> [[int]]:
    """
        High-Level Interface to receive all route candidates for the given turn_sequence
        Get the full route of every route_candidate, if the route_candidate has a valid direction.
        Method is defined as function and not part of the class RouteCandidateCreator, as multiprocessing
        wouldn't work like that.
        :return: a list of route_candidates where each candidate contains ALL intersections on the path.
    """
    route_candidate_creator = RouteCandidateCreator(turn_sequence, turns_df)
    route_candidates = route_candidate_creator.create_new_route_candidates()
    return get_ranked_route_candidates(route_candidates, route_candidate_creator.turn_pair_to_segment_route,
                                       turn_sequence, traffic_lights, measurements_df, turns_df, road_segments_df)
