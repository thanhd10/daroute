import pickle
from typing import Dict, List

import pandas as pd

from definitions import NODE_ID_COL_NAME, ROOT_DIR, OSM_ID_COL_NAME
from waltereit_attack.graph_preparation.create_turns_database import create_all_possible_turns
from waltereit_attack.graph_preparation.helper.connections_between_intersections import \
    create_connections_between_intersections
from waltereit_attack.graph_preparation.helper.create_road_segments import RoadSegmentElement, create_all_road_segments

""" 
For Usage, set the TARGET_LOCATION directory, that was created previously with csv_creator.py (exporter for osm)
"""

######################################################################

# Set target location name - a folder with that name should exist inside /data/target_maps/
TARGET_LOCATION = "Boston_Waltereit"

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
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
    # data format from osm_to_csv or sensor_to_csv
    ways = pd.read_csv(FILE_TARGET_DIR + '/csv/ways.csv')
    ways.drop_duplicates(inplace=True)
    nodes = pd.read_csv(FILE_TARGET_DIR + '/csv/nodes.csv')
    traffic_lights = pd.read_csv(FILE_TARGET_DIR + '/csv/traffic_lights.csv')
    roundabouts = pd.read_csv(FILE_TARGET_DIR + '/csv/roundabouts.csv')

    # run script to create database
    all_intersection_connections = create_connections_between_intersections(ways, nodes)
    all_road_segments = create_all_road_segments(all_intersection_connections)
    turns = create_all_possible_turns(all_road_segments, nodes)

    # store turns database for attack
    turns.to_csv(FILE_TARGET_DIR + '/db/turns_df.csv', index=False)
    # store road_segments database for attack
    road_segments_df = pd.DataFrame.from_records([road_segment.to_dict() for road_segment in all_road_segments])
    road_segments_df.set_index('segment_id', inplace=True)
    road_segments_df.to_csv(FILE_TARGET_DIR + '/db/road_segments_df.csv', index=False)
    # store a dict to retrieve all osm ids on road segments
    node_to_osm_id = nodes.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
    segments_to_osm_nodes = __create_segment_id_to_osm_nodes_map(all_road_segments, node_to_osm_id)
    with open(FILE_TARGET_DIR + SEGMENT_TO_OSM_DICT_NAME, 'wb') as dump_file:
        pickle.dump(segments_to_osm_nodes, dump_file)


