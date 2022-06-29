import timeit
from typing import Tuple

import geopy.distance
import pandas as pd

from definitions import LAT_COL_NAME, LNG_COL_NAME, NODE_ID_COL_NAME, OSM_ID_COL_NAME
from definitions import ROOT_DIR
from schema.RouteCandidateModel import RouteCandidateModel
from schema.sensor_models import SensorTurnModel, TrafficLightModel, RoundaboutTurnModel
from trajectory_attack.create_route_candidates import RouteCandidateCreator
from trajectory_attack.rank_route_candidates import get_ranked_route_candidates
from utils.eval_helper import create_osm_path

"""
Set turns, traffic lights and name of sensor readings that should be inferred
Also set street network area
"""
######################################################################

# Set Input for testing the script here
sensor_turns = [
    RoundaboutTurnModel(0, -99.48, 113.35, 13.87, float('inf'), 637.70, 18030, 12063, 23997),
    SensorTurnModel(1, -77.16, -47.18, 637.70, 947.82, 141857, 141853, 141861),
    SensorTurnModel(2, -30.28, -80.77, 947.82, 1679.32, 301614, 301612, 301617),
    SensorTurnModel(3, 89.47, 37.50, 1679.32, 1405.69, 462952, 462948, 462956),
    SensorTurnModel(4, -73.13, -67.30, 1405.69, 124.33, 637278, 637275, 637282),
    SensorTurnModel(5, -92.27, -139.76, 124.33, 182.27, 653951, 653948, 653955),
    SensorTurnModel(6, -87.39, -199.10, 182.27, float('inf'), 682702, 682698, 682706)
]
sensor_traffic_lights = [
    TrafficLightModel(0, 1, 585.79, 83367, 127341),
    TrafficLightModel(2, 3, 732.00, 362344, 378307),
    TrafficLightModel(3, 4, 417.02, 503875, 544816)
]
ROUTE_NAME = "Route_A28"

# Set target location name - a folder with that name should exist inside /data/target_maps/
TARGET_LOCATION = "Q1_Regensburg"
FILE_TARGET_DIR = ROOT_DIR + "/data/target_maps/" + TARGET_LOCATION
measurements = pd.read_csv(ROOT_DIR + "/test/measurements/Measurements_" + ROUTE_NAME + ".csv")

######################################################################
""" Utility functions for debugging purposes """


def map_turns_to_intersection_id(route_candidates: [[int]], turns_df: pd.DataFrame) -> [[int]]:
    """ Get the corresponding intersection_ids for a sequence of turn_ids """
    turn_to_intersection_id = turns_df.to_dict()['intersection_id']
    return [[turn_to_intersection_id[node] for node in route] for route in route_candidates]


# noinspection PyTypeChecker
def get_near_intersections(turns_df: pd.DataFrame, point: Tuple[float, float]) -> pd.DataFrame:
    near_turns_mask = pd.Series([geopy.distance.distance(point, center).m
                                 for center in zip(turns_df['intersection_lat'], turns_df['intersection_lng'])])
    return turns_df[near_turns_mask < 20.0]


def get_ranked_route(all_ranked_routes: [RouteCandidateModel],
                     route_of_interest: [int],
                     turns_df: pd.DataFrame) -> [RouteCandidateModel]:
    """ Return a RouteCandidateModel depending on a sequence of intersections """
    turn_to_intersection_id = turns_df.to_dict()['intersection_id']
    return [route for route in all_ranked_routes if
            [turn_to_intersection_id[node] for node in candidate.turn_ids] == route_of_interest]


# noinspection DuplicatedCode

######################################################################

if __name__ == '__main__':
    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    # database creation
    turns = pd.read_csv(FILE_TARGET_DIR + "/db/turns_df.csv")
    nodes_df = pd.read_csv(FILE_TARGET_DIR + "/csv/nodes.csv")
    segments_df = pd.read_csv(FILE_TARGET_DIR + "/db/road_segments_df.csv")

    # helper dicts for debugging
    node_to_osm_id = nodes_df.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
    osm_to_node_id = nodes_df.set_index(OSM_ID_COL_NAME)[NODE_ID_COL_NAME].to_dict()
    node_id_to_latlng = nodes_df.set_index(NODE_ID_COL_NAME)[[LAT_COL_NAME, LNG_COL_NAME]].apply(
        tuple, axis=1).to_dict()
    import pickle

    with open(FILE_TARGET_DIR + '/db/segment_to_osm_ids.pickle', 'rb') as dump_file:
        segment_to_osm_ids = pickle.load(dump_file)

    start_time = timeit.default_timer()
    route_candidates_creator = RouteCandidateCreator(sensor_turns, turns)
    new_route_candidates = route_candidates_creator.create_new_route_candidates()
    end_time = timeit.default_timer()
    print("Created %d route candidates in %.4f seconds." % (len(new_route_candidates), (end_time - start_time)))

    start_time = timeit.default_timer()
    ranked_route_candidates = get_ranked_route_candidates(new_route_candidates,
                                                          route_candidates_creator.turn_pair_to_segment_route,
                                                          sensor_turns,
                                                          sensor_traffic_lights,
                                                          measurements,
                                                          turns,
                                                          segments_df)
    end_time = timeit.default_timer()
    print("Created %d full route candidates in %.4f seconds." % (len(ranked_route_candidates), (end_time - start_time)))

    new_route_candidates = map_turns_to_intersection_id(new_route_candidates, turns)
    rank = 1
    for candidate in ranked_route_candidates[:20]:
        print("Rank = %d for candidate = %s" % (rank, map_turns_to_intersection_id([candidate.turn_ids], turns)))
        print("General score: %.4f | %.4f, Angle score : %.4f | %.4f , "
              "Distance score: %.4f | %.4f, Heading change score: %.4f | %.4f, "
              "TrafficLight Score: %.4f, "
              "Curvature Score: %.4f | %.4f"
              % (candidate.calc_general_score(), candidate.calc_general_normalized_score(),
                 candidate.angle_score, candidate.normalized_angle_score,
                 candidate.distance_score, candidate.normalized_distance_score,
                 candidate.heading_change_score, candidate.normalized_heading_change_score,
                 candidate.traffic_light_score,
                 candidate.curvature_score, candidate.normalized_curvature_score))
        rank += 1

    route_candidates_in_osm = [create_osm_path(route.segment_ids, segment_to_osm_ids) for route in
                               ranked_route_candidates]