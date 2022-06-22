from typing import List, Tuple

import pandas as pd
from tqdm import tqdm

from waltereit_attack.attack.match_route_sections import RouteSectionMatcher, match_all_route_sections_a_b, \
    get_turn_candidates, filter_turns_df_to_only_turns
from waltereit_attack.attack.schema import RouteSectionModel, RouteSectionCandidateModel

######################################################################

USE_COLS = ['segment_start_id', 'segment_target_id', 'distance_before', 'distance_after', 'intersection_id',
            'connection_type']


######################################################################

class RouteCandidateCreator(object):
    """
    Route candidates are created by this class, where each candidate is a sequence of turns representing the route.
    Each element in a candidate is an index refering to the turn within the turns_df.
    """

    def __init__(self, turn_sequence: [RouteSectionModel], turns_df: pd.DataFrame):
        self.turns_df = turns_df[USE_COLS]
        self.turn_sequence = turn_sequence

    def create_new_route_candidates(self) -> [RouteSectionCandidateModel]:
        part_route_candidates = self.__init_part_route_section_candidates()

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
                start_index, target_index = self.__determine_current_turn_indices(part_route_index,
                                                                                  curr_part_route_length)

                connected_route_sections = self.__connect_turns_to_pairs(part_route_candidates, part_route_index,
                                                                         start_index, target_index)
                new_routes_per_iteration.append(connected_route_sections)

            # with an uneven number of turns no pair-wise matching can be done until the very end
            if len(part_route_candidates) % 2 != 0:
                new_routes_per_iteration.append(part_route_candidates[-1])
            # assign reduced part routes from combining
            part_route_candidates = new_routes_per_iteration

            # as part routes are combined pairwise, their length is doubled after each step
            curr_part_route_length *= 2

        # no part routes left, so index the list of complete route candidates and sort after penalty
        potential_routes = part_route_candidates[0]
        potential_routes.sort(key=lambda x: x.penalty, reverse=False)
        return potential_routes

    # noinspection PyMethodMayBeStatic
    def __init_part_route_section_candidates(self) -> List[List[RouteSectionCandidateModel]]:
        # should contain a list (with length equals to number of turns in turn_sequence) of list of part routes,
        # that will be connected successively

        route_section_sets = []
        only_turns_df = filter_turns_df_to_only_turns(self.turns_df)

        for turn in self.turn_sequence:
            turn_candidates = get_turn_candidates(only_turns_df, turn)
            route_section_candidates = [RouteSectionCandidateModel([turn_index]) for turn_index in turn_candidates.index]
            route_section_sets.append(route_section_candidates)

        return route_section_sets

    # noinspection PyMethodMayBeStatic
    def __determine_current_turn_indices(self, part_route_index: int, curr_part_route_length: int) -> Tuple[int, int]:
        # calculate and take the last turn index in dict from the first part-route-candidate
        # subtract - 1, as dict-indices start with 0
        start = curr_part_route_length * (1 + part_route_index) - 1
        # take the first turn index in dict from the second part-route-candidate
        end = start + 1
        return start, end

    def __connect_turns_to_pairs(self, part_route_candidates: [[RouteSectionCandidateModel]],
                                 part_route_index: int,
                                 start_turn_index: int,
                                 target_turn_index: int) \
            -> [RouteSectionCandidateModel]:

        # match the last turns of the first part-routes with the first turns of the second part-routes
        pair_matcher = RouteSectionMatcher(part_route_candidates[part_route_index + 1],
                                           self.turn_sequence[start_turn_index].d_after,
                                           self.turn_sequence[start_turn_index].d_after_star,
                                           self.turns_df,
                                           len(self.turn_sequence))
        print(
            "Turn index = %d, Route section a number = %d, Route section b number = %d, d_after = %.2f, d_after_star = %.2f"
            % (start_turn_index,
               len(part_route_candidates[part_route_index]),
               len(part_route_candidates[part_route_index + 1]),
               self.turn_sequence[start_turn_index].d_after,
               self.turn_sequence[start_turn_index].d_after_star))

        return match_all_route_sections_a_b(pair_matcher, part_route_candidates[part_route_index])


def get_all_route_candidates(turn_sequence: [RouteSectionModel], turns_df: pd.DataFrame) -> [RouteSectionCandidateModel]:
    """
        High-Level Interface to receive all route candidates for the given turn_sequence
        Get the full route of every route_candidate, if the route_candidate has a valid direction.
        Method is defined as function and not part of the class RouteCandidateCreator, as multiprocessing
        wouldn't work like that.
        :return: a list of route_candidates where each candidate contains ALL intersections on the path.
    """
    route_candidate_creator = RouteCandidateCreator(turn_sequence, turns_df)
    return route_candidate_creator.create_new_route_candidates()


if __name__ == '__main__':
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    turns = pd.read_csv("/home/tdinh/persistent/attack_sensor_route/data/target_maps/Q1_Regensburg_Route_Derivation/db/turns_df.csv")
    nodes = pd.read_csv("/home/tdinh/persistent/attack_sensor_route/data/target_maps/Q1_Regensburg_Route_Derivation/csv/nodes.csv")

    # SensorTurnModel(0, 88.94, 249.67, float('inf'), 1077.99, 96398, 96394, 96402),
    # SensorTurnModel(1, -92.28, 299.70, 1077.99, 310.14, 246318, 246315, 246321),
    # SensorTurnModel(2, 82.10, 396.74, 310.14, 396.19, 277918, 277915, 277921),
    # SensorTurnModel(3, -84.90, 276.54, 396.19, 1303.81, 341199, 341196, 341203),
    # SensorTurnModel(4, 81.23, 386.01, 1303.81, float('inf'), 474319, 474316, 474323)

    from route_derivation_attack.attack_parameters import IS_LEFT, IS_RIGHT

    route_section_a = RouteSectionModel(d_before_star=float('inf'),
                                        d_before=float('inf'),
                                        d_after=1077.99,
                                        d_after_star=1077.99,
                                        turn_type=IS_RIGHT)

    route_section_b = RouteSectionModel(d_before_star=float('inf'),
                                        d_before=1077.99,
                                        d_after=310.14,
                                        d_after_star=310.14,
                                        turn_type=IS_LEFT)

    route_section_c = RouteSectionModel(d_before_star=1077.99 + 310.14,
                                        d_before=310.14,
                                        d_after=396.19,
                                        d_after_star=396.19,
                                        turn_type=IS_RIGHT)

    route_section_d = RouteSectionModel(d_before_star=310.14 + 276.54,
                                        d_before=276.54,
                                        d_after=1303.81,
                                        d_after_star=1303.81,
                                        turn_type=IS_LEFT)

    route_section_e = RouteSectionModel(d_before_star=276.54 + 386.01,
                                        d_before=386.01,
                                        d_after=float('inf'),
                                        d_after_star=float('inf'),
                                        turn_type=IS_RIGHT)

    route_section_sequence = [route_section_a, route_section_b, route_section_c, route_section_d, route_section_e]

    import timeit

    start_time = timeit.default_timer()

    route_candidates = get_all_route_candidates(route_section_sequence, turns)
    end_time = timeit.default_timer()
    print("Matched turns in %.4f seconds." % (end_time - start_time))

    import pickle

    with open('/home/tdinh/persistent/attack_sensor_route/data/target_maps/Q1_Regensburg_Route_Derivation/db/segment_to_osm_ids.pickle',
              'rb') as dump_file:
        segment_to_osm_path = pickle.load(dump_file)

    from utils.eval_helper import create_osm_path, is_perfect_path_match

    candidates_in_osn = [create_osm_path(route.segment_ids, segment_to_osm_path) for route in route_candidates]
    perfect_matching_results = [
        is_perfect_path_match([3643195517, 1591325730, 33210232, 367944201, 32323640], candidate_path) for
        candidate_path in candidates_in_osn]
    print("Rank of route = %d " % (perfect_matching_results.index(True) + 1))
