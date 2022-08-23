import logging
import os
import pickle
from typing import Dict, List

import pandas as pd

from definitions import NODE_ID_COL_NAME, ROOT_DIR, OSM_ID_COL_NAME
from graph_preparation.create_turns_database import create_all_possible_turns
from graph_preparation.helper.connections_between_intersections import create_connections_between_intersections
from graph_preparation.helper.create_road_segments import RoadSegmentElement, create_all_road_segments
from osm_to_csv.osm_handler import WayHandler, TrafficLightHandler, RoundaboutHandler
from utils import log

""" 
For Usage, set 
    a) the OSM_FILE variable: a path that refers to a raw osm dump export
    b) the TARGET_LOCATION variable: a describing name for the location of the street network like a city name
"""

######################################################################

# SET OSM FILE TO PARSE HERE
OSM_FILE = ROOT_DIR + "/data/osm_export_12_04_21/Q1_Regensburg.osm"

# Set target location name
TARGET_LOCATION = "Regensburg"


######################################################################
# define path to the target directory where files should be stored
BASE_TARGET_DIR = ROOT_DIR + '/data/target_maps/'
CSV_DIR = '/csv'
TURNS_DB_DIR = '/db'

FILE_TARGET_DIR = ROOT_DIR + "/data/target_maps/" + TARGET_LOCATION
SEGMENT_TO_OSM_DICT_NAME = '/db/segment_to_osm_ids.pickle'


######################################################################


def __create_segment_id_to_osm_nodes_map(road_segments: [RoadSegmentElement], node_id_to_osm_id: Dict[int, int]) \
        -> Dict[int, List[int]]:
    """ store all nodes on a segment and retrieve them by the segment id """
    segment_id_to_osm_nodes = dict()
    for segment in road_segments:
        osm_ids = [node_id_to_osm_id[segment_node.node_id] for segment_node in segment.nodes_on_segment]
        segment_id_to_osm_nodes[segment.segment_id] = osm_ids
    return segment_id_to_osm_nodes


if __name__ == '__main__':
    log.setup(log_filename=ROOT_DIR + "/osm_to_csv/csv_creator.log")
    log = logging.getLogger(__name__)

    # Create target dirs for csv and image files
    csv_target_dir = BASE_TARGET_DIR + TARGET_LOCATION + CSV_DIR
    db_target_dir = BASE_TARGET_DIR + TARGET_LOCATION + TURNS_DB_DIR
    if not os.path.exists(csv_target_dir):
        os.makedirs(csv_target_dir)
    if not os.path.exists(db_target_dir):
        os.makedirs(db_target_dir)

    # 1. Run parsing osm file dump to csv files that will be processed later
    t = TrafficLightHandler(OSM_FILE, csv_target_dir, log)
    r = RoundaboutHandler(OSM_FILE, csv_target_dir, log)
    w = WayHandler(OSM_FILE, csv_target_dir, log)

    # 2. Load newly created csv files
    ways = pd.read_csv(FILE_TARGET_DIR + CSV_DIR + '/ways.csv')
    ways.drop_duplicates(inplace=True)
    nodes = pd.read_csv(FILE_TARGET_DIR + CSV_DIR + '/nodes.csv')
    traffic_lights = pd.read_csv(FILE_TARGET_DIR + CSV_DIR + '/traffic_lights.csv')
    roundabouts = pd.read_csv(FILE_TARGET_DIR + CSV_DIR + '/roundabouts.csv')

    # 3. Run scripts to create the street network
    all_intersection_connections = create_connections_between_intersections(ways, nodes, traffic_lights, roundabouts)
    all_road_segments = create_all_road_segments(all_intersection_connections)
    turns = create_all_possible_turns(all_road_segments, nodes, ways, roundabouts)

    # Store turns database for attack
    turns.to_csv(FILE_TARGET_DIR + TURNS_DB_DIR + '/turns_df.csv', index=False)

    # Store road_segments database for attack
    road_segments_df = pd.DataFrame.from_records([road_segment.to_dict() for road_segment in all_road_segments])
    road_segments_df.set_index('segment_id', inplace=True)
    road_segments_df.to_csv(FILE_TARGET_DIR + TURNS_DB_DIR + '/road_segments_df.csv', index=False)

    # Store a dict to retrieve all osm ids on road segments
    node_to_osm_id = nodes.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
    segments_to_osm_nodes = __create_segment_id_to_osm_nodes_map(all_road_segments, node_to_osm_id)
    with open(FILE_TARGET_DIR + SEGMENT_TO_OSM_DICT_NAME, 'wb') as dump_file:
        pickle.dump(segments_to_osm_nodes, dump_file)
