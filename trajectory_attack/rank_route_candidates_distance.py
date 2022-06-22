from multiprocessing import Pool
from typing import Dict, List, Tuple

import pandas as pd

from schema.RouteCandidateModel import RouteCandidateModel
from schema.sensor_models import SensorTurnModel


class RouteCandidateRankerDistance(object):
    """
    Simplified Version of Ranking Route Candidates only based on distance.
    Version is used to simulate the attack of the Route Derivation Paper with less computational overhead.
    """
    def __init__(self,
                 sensor_turns: [SensorTurnModel],
                 segments_df: pd.DataFrame):
        self.sensor_turns = sensor_turns
        self.segments_distance = segments_df['distance']

    def rank_route_candidate_distance_only(self, route_candidate: [int],
                                           road_section_paths: [[int]]) -> RouteCandidateModel:
        full_route = []
        sum_distance_penalty = 0

        for i in range(len(route_candidate) - 1):
            # get all complete paths between two turns
            route_section_path = road_section_paths[i]

            # Adjust Distance Score
            expected_distance = sum([self.segments_distance.loc[segment_id] for segment_id in route_section_path])
            sum_distance_penalty += self.__calc_distance_deviation(self.sensor_turns[i].distance_after,
                                                                   expected_distance)

            # Store segment route section
            full_route.extend(route_section_path)

        # average summed penalty afterward
        distance_score = sum_distance_penalty / (len(route_candidate) - 1)

        return RouteCandidateModel(turn_ids=route_candidate,
                                   segment_ids=full_route,
                                   distance_score=distance_score,
                                   angle_score=0,
                                   heading_change_score=0,
                                   traffic_light_score=0,
                                   curvature_score=0)

    def __calc_distance_deviation(self, measured_distance: float, expected_distance) -> float:
        """ Calc deviation of each distance between two turns """
        return abs(measured_distance - expected_distance)


def get_segment_paths(route_candidate: [int], turn_pair_to_segments_route_dict: [int]) -> [[int]]:
    """ Get segment paths between each turn pair as a list """
    section_paths = []
    for i in range(len(route_candidate) - 1):
        next_turn_pair = (route_candidate[i], route_candidate[i + 1])
        section_paths.append(turn_pair_to_segments_route_dict[next_turn_pair])
    return section_paths


def __normalize_distance_score(route_candidates: [RouteCandidateModel]):
    """ After multiprocessing, the scores of the candidates should be normalized between 0 and 1. """
    all_distance_scores = [route.distance_score for route in route_candidates]

    # Extract parameters for Normalization equation: (X - X_min) / (X_max - X_min)
    try:
        x_dist_min = min(all_distance_scores)
        x_dist_max = max(all_distance_scores)
    except (ValueError, TypeError):
        print("Warning: Error while retrieving min and max values for score normalization.")
        # all candidates filtered out, return
        return

    for route in route_candidates:
        try:
            route.normalize_distance_score(x_dist_min, x_dist_max)
        except ZeroDivisionError:
            print("Warning: ZeroDivisionError found while normalizing distance.")
            pass


def get_ranked_route_candidates_distance(route_candidates: [[int]],
                                         turn_pair_to_segments_route_dict: Dict[Tuple[int, int], List[int]],
                                         sensor_turns: [SensorTurnModel],
                                         segments_df: pd.DataFrame) -> List[RouteCandidateModel]:
    """
     Function also returns the route candidates, that were filtered for Evaluation purposes.
     Parallelized Function to receive a sorted list of route candidates.
     Method is defined as function and not part of RouteCandidateRanker, as multiprocessing wouldn't work like that.
     :return: a list of ranked route candidates
     """

    if not route_candidates:
        return []

    full_route_creator = RouteCandidateRankerDistance(sensor_turns,
                                                      segments_df)

    # retrieve segment paths between turns already, so intensive copying of dict is not done in multiprocessing
    section_paths_for_routes = [get_segment_paths(candidate, turn_pair_to_segments_route_dict) for candidate in
                                route_candidates]

    with Pool() as pool:
        route_candidates = pool.starmap(full_route_creator.rank_route_candidate_distance_only,
                                        zip(route_candidates, section_paths_for_routes))

    __normalize_distance_score(route_candidates)
    route_candidates.sort(key=lambda x: x.calc_general_normalized_score(), reverse=False)

    return route_candidates
