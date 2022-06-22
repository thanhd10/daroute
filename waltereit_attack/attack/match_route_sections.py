from multiprocessing import Pool

import pandas as pd

from waltereit_attack.attack.schema import RouteSectionModel, RouteSectionCandidateModel
from waltereit_attack.attack_parameters import IS_LEFT, IS_RIGHT, IS_STRAIGHT, DISTANCE_ERROR_TOLERANCE, \
    MAX_FN_COUNTER, MAX_FP_COUNTER, ROAD_WIDTH_THRESHOLD, DISTANCE_PEN_WEIGHT, PENALTY_THRESHOLD
from utils.functions import flatten_list

######################################################################

USE_COLS = ['segment_start_id', 'segment_target_id', 'intersection_id', 'distance_after', 'connection_type']


######################################################################


class PathConnection(object):
    def __init__(self,
                 segment_ids: [int],
                 fn_counter: int,
                 distance: float):
        self.segment_ids = segment_ids
        self.fn_counter = fn_counter
        self.distance = distance


class RouteSectionMatcher(object):
    def __init__(self,
                 turn_candidates_b: [RouteSectionCandidateModel],
                 distance_a_b: float,
                 distance_a_b_star: float,
                 turns_df: pd.DataFrame,
                 route_length: int):
        self.travel_options = turns_df[USE_COLS]

        self.turn_candidates_b = turn_candidates_b
        # segments desired to reach, as here the next turn would start
        self.start_segments_of_turn_b = self.travel_options.loc[
            [cand.turn_indices[0] for cand in self.turn_candidates_b]]['segment_start_id']

        self.distance_a_b = distance_a_b
        self.lower_bound_distance = distance_a_b / (1 + DISTANCE_ERROR_TOLERANCE)
        self.upper_bound_distance = distance_a_b_star / (1 - DISTANCE_ERROR_TOLERANCE) + ROAD_WIDTH_THRESHOLD

        # used for penalty calculation
        self.route_length = route_length

    def match_turn_to_candidates(self, route_section_cand_a: RouteSectionCandidateModel) \
            -> [RouteSectionCandidateModel]:
        # store all routes, that can be taken, when driving straight along the road from intersection
        # start_id to center_id. start_id should be the turn whose valid matches are being searched for
        possible_routes_from_current_a = []

        # extract information of route_section_candidate from turn in database
        curr_turn_index = route_section_cand_a.turn_indices[-1]
        curr_turn_unit = self.travel_options.loc[curr_turn_index]
        target_seg = int(curr_turn_unit['segment_target_id'])
        distance_start_center = curr_turn_unit['distance_after']

        # store the current route taken from 'a' to track the route to a corresponding target
        current_route_to_candidate = [target_seg]

        self.__find_intersections_by_distance(fn_counter=route_section_cand_a.fn_counter,
                                              next_start_segment=target_seg,
                                              curr_distance_bridged=0.0,
                                              distance_to_target=distance_start_center,
                                              possible_routes_from_a=possible_routes_from_current_a,
                                              current_route_node_path=current_route_to_candidate,
                                              passed_intersections=[])

        connected_route_sections = []

        # TODO check, if this is faster, or removing this line and directly looping over possible_routes_from_current_a
        # return all routes with turns, that are reachable from 'a' and are possible turn candidates for 'b'
        valid_candidates = [route for route in possible_routes_from_current_a if
                            route.segment_ids[-1] in self.start_segments_of_turn_b.unique()]

        for valid_candidate_path in valid_candidates:
            # get all potential turns, that are reachable from the current path
            target_turn_ids = self.start_segments_of_turn_b.index[
                self.start_segments_of_turn_b == valid_candidate_path.segment_ids[-1]]

            # check for every reachable turn, whether a new route section should be created
            for target_turn_id in target_turn_ids:
                # TODO might take the first one of these (should be only one, except edge cases)
                candidates_b = [candidate for candidate in self.turn_candidates_b if
                                candidate.turn_indices[0] == target_turn_id]

                for candidate_b in candidates_b:
                    new_fn_counter = route_section_cand_a.fn_counter + candidate_b.fn_counter + valid_candidate_path.fn_counter
                    new_fp_counter = route_section_cand_a.fp_counter + candidate_b.fp_counter
                    if (new_fn_counter <= MAX_FN_COUNTER) and (new_fp_counter <= MAX_FP_COUNTER):

                        # sum of new distance error AND previous distance errors
                        new_distance_error = abs((self.distance_a_b / valid_candidate_path.distance) - 1)
                        summed_distance_error = route_section_cand_a.distance_error + candidate_b.distance_error + new_distance_error

                        # calculate partial penalties
                        distance_penalty = summed_distance_error / ((self.route_length - 1) * DISTANCE_ERROR_TOLERANCE)
                        if MAX_FN_COUNTER == 0 and MAX_FP_COUNTER == 0:
                            fn_fp_penalty = 0
                        else:
                            fn_fp_penalty = (new_fn_counter + new_fp_counter) / (MAX_FN_COUNTER + MAX_FP_COUNTER)

                        # weighted score to discard unlikely candidates and rank route candidates
                        penalty = (DISTANCE_PEN_WEIGHT * distance_penalty) + ((1 - DISTANCE_PEN_WEIGHT) * fn_fp_penalty)

                        # filter route section, if penalty threshold is exceeded
                        if penalty < PENALTY_THRESHOLD:
                            connected_route_sections.append(RouteSectionCandidateModel(
                                turn_indices=route_section_cand_a.turn_indices + candidate_b.turn_indices,
                                segment_ids=route_section_cand_a.segment_ids + valid_candidate_path.segment_ids + candidate_b.segment_ids,
                                distance_error=summed_distance_error,
                                penalty=penalty,
                                fn_counter=new_fn_counter,
                                fp_counter=new_fp_counter))

        return connected_route_sections

    def __find_intersections_by_distance(self,
                                         fn_counter: int,
                                         next_start_segment: int,
                                         curr_distance_bridged: float,
                                         distance_to_target: float,
                                         possible_routes_from_a: [PathConnection],
                                         current_route_node_path: [int],
                                         passed_intersections: [int]):
        # add the bridged distance between the two current intersections
        curr_distance_bridged += distance_to_target

        # add all intersections, that are reachable from candidate 'a' and fulfill condition, that:
        # distance d is between (d_a_b - thresh) and (d_a_b + thresh) and heading change does not exceed filter
        if curr_distance_bridged > self.upper_bound_distance:
            return
        elif curr_distance_bridged > self.lower_bound_distance:
            # deep copy route from 'a' to potential 'b', so later changes don't affect the already added routes
            possible_routes_from_a.append(PathConnection(segment_ids=[node for node in current_route_node_path],
                                                         fn_counter=fn_counter,
                                                         distance=curr_distance_bridged))

        # get all intersections, that can be reached without turning
        next_targets = self.travel_options[self.travel_options['segment_start_id'] == next_start_segment]

        # helper variable to potentially decrease counter again
        fn_counter_increased = False

        # recursive call; recursion also stops, when no intersection is reachable without a turn
        for next_target, next_intersection, next_distance, connection_type in zip(next_targets['segment_target_id'],
                                                                                  next_targets['intersection_id'],
                                                                                  next_targets['distance_after'],
                                                                                  next_targets['connection_type']):
            # don't allow loops when 'driving straight', as it's unlikely with the high straight travel threshold
            if next_intersection in passed_intersections:
                continue

            # undected turn, increase fn_counter
            if connection_type != IS_STRAIGHT:
                fn_counter += 1
                fn_counter_increased = True

            # check if max allowed FN's exceeded
            if fn_counter > MAX_FN_COUNTER:
                fn_counter -= 1
                fn_counter_increased = False
                continue

            # traverse forward by storing traversed path
            current_route_node_path.append(next_target)
            passed_intersections.append(next_intersection)

            self.__find_intersections_by_distance(fn_counter=fn_counter,
                                                  next_start_segment=next_target,
                                                  curr_distance_bridged=curr_distance_bridged,
                                                  distance_to_target=next_distance,
                                                  possible_routes_from_a=possible_routes_from_a,
                                                  current_route_node_path=current_route_node_path,
                                                  passed_intersections=passed_intersections)
            # 'backtrack' one step from current route path originating from 'a'
            current_route_node_path.pop()
            passed_intersections.pop()

            # decrease fn_counter again, if in this loop iteration the counter was incremented
            if fn_counter_increased:
                fn_counter -= 1
                fn_counter_increased = False


def match_all_route_sections_a_b(turn_pair_matcher: RouteSectionMatcher,
                                 turn_candidates_a: [RouteSectionCandidateModel]) \
        -> [RouteSectionCandidateModel]:
    """
    Match all turn candidates for turn a and all turn candidates for turn b with each other, that are set in
    turn_pair_matcher. Method is defined as function and not part of the class TurnPairMatcher, as multiprocessing
    wouldn't work like that.
    :param turn_candidates_a: turn candidates, from where all possible paths are traversed
    :param turn_pair_matcher: an instance of TurnPairMatcher used to run the matching
    :return: a list of turn-pairs created from the candidates of turn a + b
    """
    with Pool() as pool:
        matched_turns = pool.map(turn_pair_matcher.match_turn_to_candidates,
                                 turn_candidates_a)
    return flatten_list(matched_turns)


def get_turn_candidates(turns_df: pd.DataFrame, route_section: RouteSectionModel) -> pd.DataFrame:
    """
    Depending on the input parameters suitable turn candidates should be queried in the dataframe:
        1. the angle of a valid turn should be inside the given threshold
        2. the end_direction after the turn should be inside the given magnetometer threshold
        3. the distance BEFORE taking the turn can't be higher than the measured distance between the last intersection
           and the intersection, where the turn is taking place
        4. the distance AFTER taking the turn to the next intersection can't be higher than the measured distance
           between intersection, where the turn is taking place and the next intersection
    """

    max_distance_before = route_section.d_before_star / (1 - DISTANCE_ERROR_TOLERANCE)
    max_distance_after = route_section.d_after_star / (1 - DISTANCE_ERROR_TOLERANCE)

    return turns_df[(turns_df['distance_before'] < max_distance_before) &
                    (turns_df['distance_after'] < max_distance_after) &
                    (turns_df['connection_type'] == route_section.turn_type)]


def filter_turns_df_to_only_turns(turns_df: pd.DataFrame) -> pd.DataFrame:
    """
    as turns_df contains all possible routes that can be taken at an intersection, a pre-filtering can be done before
    calling get_turn_candidates to reduce the search space even more
    """
    return turns_df[(turns_df['connection_type'] == IS_LEFT) | (turns_df['connection_type'] == IS_RIGHT)]


if __name__ == '__main__':
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    turns = pd.read_csv("/home/tdinh/persistent/attack_sensor_route/data/target_maps/Q1_Regensburg/db/turns_df.csv")
    nodes = pd.read_csv("/home/tdinh/persistent/attack_sensor_route/data/target_maps/Q1_Regensburg/csv/nodes.csv")

    import pickle

    with open('/home/tdinh/persistent/attack_sensor_route/data/target_maps/Q1_Regensburg/db/segment_to_osm_ids.pickle',
              'rb') as dump_file:
        segment_to_osm_path = pickle.load(dump_file)

    # test route M2
    # turn_a = SensorTurnModel(0, 88.94, 249.67, float('inf'), 1077.99, 96398, 96394, 96402)
    # turn_b = SensorTurnModel(1, -92.28, 299.70, 1077.99, 310.14, 246318, 246315, 246321)

    route_section_a = RouteSectionModel(d_before_star=float('inf'),
                                        d_before=float('inf'),
                                        d_after=1077.99,
                                        d_after_star=1077.99 + 310.14,
                                        turn_type=IS_RIGHT)

    route_section_b = RouteSectionModel(d_before_star=float('inf'),
                                        d_before=1077.99,
                                        d_after=310.14,
                                        d_after_star=310.14 + 396.19,
                                        turn_type=IS_LEFT)

    candidates_a_2 = get_turn_candidates(turns, route_section_a)
    candidates_b_2 = get_turn_candidates(turns, route_section_b)

    candidates_a_2 = [RouteSectionCandidateModel([turn]) for turn in candidates_a_2.index]
    candidates_b_2 = [RouteSectionCandidateModel([turn]) for turn in candidates_b_2.index]

    import timeit

    start_time = timeit.default_timer()
    pair_matcher = RouteSectionMatcher(candidates_b_2,
                                       route_section_a.d_after,
                                       route_section_a.d_after_star,
                                       turns)

    turn_pairs = match_all_route_sections_a_b(pair_matcher, candidates_a_2)
    end_time = timeit.default_timer()
    print("Matched turns in %.4f seconds." % (end_time - start_time))

    from definitions import NODE_ID_COL_NAME, OSM_ID_COL_NAME

    node_id_to_osm_id = nodes.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
    turn_to_intersection_id = turns.to_dict()['intersection_id']

    osm_id_pairs = [[node_id_to_osm_id[turn_to_intersection_id[turn_pair.turn_indices[0]]],
                     node_id_to_osm_id[turn_to_intersection_id[turn_pair.turn_indices[-1]]]] for turn_pair in
                    turn_pairs]

    print([3643195517, 1591325730] in osm_id_pairs)
