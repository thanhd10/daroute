import pickle
import timeit

import pandas as pd

from definitions import LAT_COL_NAME, LNG_COL_NAME, NODE_ID_COL_NAME, OSM_ID_COL_NAME, ROOT_DIR
from sensor_analyze.preprocess_trip import SensorPreprocessor
from trajectory_attack.create_route_candidates import RouteCandidateCreator
from trajectory_attack.rank_route_candidates import get_ranked_route_candidates
from utils.eval_helper import create_osm_path

JSON_FILE_PATH = ROOT_DIR + "/data/Files/Sensors/DaRoute/boston_test/Sample_Route2.json"
INITIAL_HEADING = 65.25
TARGET_LOCATION = "Boston"

AREA_TARGET_PATH = ROOT_DIR + "/data/target_maps/" + TARGET_LOCATION


def map_turns_to_intersection_id(route_candidates: [[int]], turns_df: pd.DataFrame) -> [[int]]:
    """ Get the corresponding intersection_ids for a sequence of turn_ids """
    turn_to_intersection_id = turns_df.to_dict()['intersection_id']
    return [[turn_to_intersection_id[node] for node in route] for route in route_candidates]


if __name__ == '__main__':
    # Step 1: Load street network information
    turns_df = pd.read_csv(AREA_TARGET_PATH + "/db/turns_df.csv")
    segments_df = pd.read_csv(AREA_TARGET_PATH + "/db/road_segments_df.csv")

    # Some helper variables to debug and/or display geographical locations in lat+lng
    nodes_df = pd.read_csv(AREA_TARGET_PATH + "/csv/nodes.csv")
    node_to_osm_id = nodes_df.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
    node_id_to_latlng = nodes_df.set_index(NODE_ID_COL_NAME)[[LAT_COL_NAME, LNG_COL_NAME]].apply(
        tuple, axis=1).to_dict()
    with open(AREA_TARGET_PATH + '/db/segment_to_osm_ids.pickle', 'rb') as dump_file:
        segment_to_osm_ids = pickle.load(dump_file)

    # Step 2: Preprocess sensor readings
    start_time = timeit.default_timer()
    sensor_preprocessor = SensorPreprocessor(JSON_FILE_PATH, INITIAL_HEADING)
    sensor_preprocessor.preprocess()
    measurements = sensor_preprocessor.get_measurements_as_trip_df()
    turn_sequence, traffic_light_sequence = sensor_preprocessor.get_sensor_turns_and_traffic_lights()
    end_time = timeit.default_timer()
    print("Found %d turns and %d traffic lights in %.4f seconds."
          % (len(turn_sequence), len(traffic_light_sequence), (end_time - start_time)))

    # Step 3: Retrieve route candidates
    start_time = timeit.default_timer()
    route_candidates_creator = RouteCandidateCreator(turn_sequence, turns_df)
    route_candidates = route_candidates_creator.create_new_route_candidates()
    end_time = timeit.default_timer()
    print("Created %d route candidates in %.4f seconds." % (len(route_candidates), (end_time - start_time)))

    # Step 4: Rank route candidates
    start_time = timeit.default_timer()
    ranked_route_candidates = get_ranked_route_candidates(route_candidates,
                                                          route_candidates_creator.turn_pair_to_segment_route,
                                                          turn_sequence,
                                                          traffic_light_sequence,
                                                          measurements,
                                                          turns_df,
                                                          segments_df)
    end_time = timeit.default_timer()
    print("Ranked %d route candidates in %.4f seconds." % (len(ranked_route_candidates), (end_time - start_time)))

    rank = 1
    for candidate in ranked_route_candidates[:20]:
        # Format route candidates into osm nodes and geographical representation
        route_candidate_as_osm_nodes = create_osm_path(candidate.segment_ids, segment_to_osm_ids)
        route_candidate_as_lat_lng = [node_id_to_latlng[node]
                                      for node in map_turns_to_intersection_id([candidate.turn_ids], turns_df)[0]]

        print("Details of route with rank %d:" % rank)
        print("OSM nodes of route = %s" % route_candidate_as_osm_nodes)
        print("Coordinates of route = %s" % route_candidate_as_lat_lng)
        rank += 1
