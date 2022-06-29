from typing import List, Tuple

from narain_attack.settings import TOP_RANK_MEDIUM, PERCENTAGE_MATCH
from schema.RouteCandidateModel import RouteCandidateModel
from schema.TestRouteModel import TestRouteModel
from schema.sensor_models import SensorTurnModel
from utils.eval_helper import create_osm_path, is_percentage_match, is_start_and_end_match, \
    create_osm_path_with_only_intersections


def run_evaluation(unit_test, test_route: TestRouteModel,
                   ranked_route_candidates: List[RouteCandidateModel]) -> Tuple[int, int, List[bool]]:
    # 1. Convert Routes into Evaluation format and result and run check for perfect Top Ranking
    candidates_in_osm = [create_osm_path(route.segment_ids, unit_test.segment_to_osm_path) for route in
                         ranked_route_candidates]
    perfect_matching_results = [is_start_and_end_match(test_route.osm_id_path, candidate_path)
                                for candidate_path in candidates_in_osm]
    rank_of_perfect_route = __get_route_ranking(unit_test, perfect_matching_results, is_perfect_match=True)

    is_start_correct = [route for route in candidates_in_osm if route[0] == test_route.osm_id_path[0]]
    is_end_correct = [route for route in candidates_in_osm if route[-1] == test_route.osm_id_path[-1]]

    unit_test.logger.info("Routes with correct start = %d" % len(is_start_correct))
    unit_test.logger.info("Routes with correct end = %d" % len(is_end_correct))

    # 2. Run check for percentage Top Ranking, by checking whether a similar route occurs earlier
    if rank_of_perfect_route != -1:
        # found the ground truth; check whether similar routes are higher ranked
        passed_intersections_osm = create_osm_path_with_only_intersections(
            ranked_route_candidates[perfect_matching_results.index(True)].segment_ids, unit_test.segment_to_osm_path)

        candidates_only_intersections = [
            create_osm_path_with_only_intersections(route.segment_ids, unit_test.segment_to_osm_path) for route in
            ranked_route_candidates]

        percentage_matching_results = [is_percentage_match(passed_intersections_osm, candidate_path, PERCENTAGE_MATCH)
                                       for candidate_path in candidates_only_intersections]
        rank_of_percentage_route = __get_route_ranking(unit_test, percentage_matching_results, is_perfect_match=False)
    else:
        rank_of_percentage_route = -1
        unit_test.logger.info("No stored full osm path for this route available.")

    # return the corresponding ranks and the results for perfect matching
    return rank_of_perfect_route, rank_of_percentage_route, perfect_matching_results


def __get_route_ranking(unit_test, route_matching_results: [bool], is_perfect_match: bool):
    try:
        rank_position = route_matching_results.index(True) + 1
    except ValueError:
        rank_position = -1

    # log ranking results for either partial or perfect match
    if is_perfect_match:
        match_type = "Perfect match route"
    else:
        match_type = "Percentage match route"
    unit_test.logger.info("%s rank position = %d"
                          % (match_type, rank_position))
    unit_test.logger.info("%s within Top %d = %s"
                          % (match_type, TOP_RANK_MEDIUM, rank_position <= TOP_RANK_MEDIUM and rank_position != -1))

    return rank_position


def get_total_distance(turn_sequence: [SensorTurnModel]) -> float:
    # distance before first turn not considered
    # skipped last turn, as we don't consider distance after the last turn right now
    return sum([turn.distance_after for turn in turn_sequence[:-1]])
