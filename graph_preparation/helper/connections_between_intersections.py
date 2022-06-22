import timeit
from multiprocessing import Pool
from typing import Optional

import pandas as pd

from definitions import LABEL_COL_NAME, NODE_ID_COL_NAME, LAT_COL_NAME, LNG_COL_NAME, START_ID_COL_NAME, \
    END_ID_COL_NAME, SPEED_LIMIT_COL_NAME, AGGREGATED_DISTANCE_COL_NAME, INTERSECTION, OSM_ID_COL_NAME
from graph_preparation.schema.RoadElements import IntersectionConnectionElement, NodeOnIntersectionConnectionElement
from utils.functions import flatten_list


class IntersectionConnectionsCreator(object):

    def __init__(self, ways_df: pd.DataFrame, nodes_df: pd.DataFrame, traffic_lights_df: pd.DataFrame,
                 roundabouts_df: pd.DataFrame):
        # remove all ways within roundabouts, as roundabouts are handled separately
        roundabout_ids = roundabouts_df[OSM_ID_COL_NAME].unique()
        self.ways_df = ways_df[~ways_df[OSM_ID_COL_NAME].isin(roundabout_ids)]

        # store a set of traffic light nodes for fast checking
        self.traffic_light_nodes = set(nodes_df.merge(
            traffic_lights_df, how='inner', on=OSM_ID_COL_NAME)[NODE_ID_COL_NAME].unique())

        # map nodes from node_id to their corresponding (lat, lng)
        self.node_id_to_latlng = nodes_df.set_index(NODE_ID_COL_NAME)[[LAT_COL_NAME, LNG_COL_NAME]].apply(
            tuple, axis=1).to_dict()

        # store all node_id's of intersections in a set for faster check
        self.intersections_df = nodes_df[nodes_df[LABEL_COL_NAME] == INTERSECTION]
        self.intersections_id_set = set(self.intersections_df[NODE_ID_COL_NAME].unique())

    def create_connections_for_intersection(self, intersection_id: int) -> [IntersectionConnectionElement]:
        # receive all connections originating from current Intersection
        current_connections = self.ways_df[self.ways_df[START_ID_COL_NAME] == intersection_id]
        # select columns current_connections for numpy vectorization and index them with the position
        # re-casting to correct datatypes is needed, as selected columns will be casted to float in numpy array
        # flatten list, as two connections could be added in one call due to dead-ends
        return flatten_list([self.__add_connection_to_intersection(intersection_id, int(connection[0]),
                                                                   int(connection[1]), float(connection[2]))
                             for connection in current_connections[
                                 [END_ID_COL_NAME, SPEED_LIMIT_COL_NAME, AGGREGATED_DISTANCE_COL_NAME]].values])

    def __add_connection_to_intersection(self, curr_intersection: int, next_node_id: int, next_speed_limit: int,
                                         next_distance: float) -> [IntersectionConnectionElement]:
        nodes_on_connection = [
            NodeOnIntersectionConnectionElement(node_id=curr_intersection,
                                                speed_limit=next_speed_limit,
                                                distance=0.0,
                                                position=self.node_id_to_latlng[curr_intersection],
                                                is_traffic_light=curr_intersection in self.traffic_light_nodes),
            NodeOnIntersectionConnectionElement(node_id=next_node_id,
                                                speed_limit=next_speed_limit,
                                                distance=next_distance,
                                                position=self.node_id_to_latlng[next_node_id],
                                                is_traffic_light=next_node_id in self.traffic_light_nodes)]
        # helper variable to avoid endless loops
        previous_node_id = curr_intersection

        # create connection to another intersection/dead-end by finding the next one for this current one
        while True:
            # follow the connection by getting the next node in this direction: retrieve way, whose end_id isn't the
            # previous node to prevent endless loop; can only result to one row, if it's no intersection
            next_way = self.ways_df[
                (self.ways_df[START_ID_COL_NAME] == next_node_id) & (self.ways_df[END_ID_COL_NAME] != previous_node_id)
                ]

            # check if next_node is an intersection or dead-end
            if next_node_id in self.intersections_id_set:
                return [IntersectionConnectionElement(curr_intersection, next_node_id, nodes_on_connection)]
            elif next_way.empty:
                # Dead-End found; remove for possible None's, because of possible one-ways
                return [x for x in [IntersectionConnectionElement(curr_intersection, next_node_id, nodes_on_connection),
                                    self.__create_dead_end(curr_intersection, next_node_id, previous_node_id,
                                                           next_speed_limit,
                                                           next_distance)] if x is not None]
            else:
                # proceed with the next node, as sub-nodes of a connection between intersections should be removed
                previous_node_id = next_node_id

                # add next node between intersections
                next_node_id = next_way.iloc[0][END_ID_COL_NAME]
                next_distance = next_way.iloc[0][AGGREGATED_DISTANCE_COL_NAME]
                next_speed_limit = next_way.iloc[0][SPEED_LIMIT_COL_NAME]
                nodes_on_connection.append(
                    NodeOnIntersectionConnectionElement(node_id=next_node_id,
                                                        speed_limit=next_speed_limit,
                                                        distance=next_distance,
                                                        position=self.node_id_to_latlng[next_node_id],
                                                        is_traffic_light=next_node_id in self.traffic_light_nodes))

    def __create_dead_end(self, curr_intersection: int, dead_end: int, next_node_id: int, next_speed_limit: int,
                          next_distance: float) -> Optional[IntersectionConnectionElement]:
        nodes_starting_from_dead_end = [
            NodeOnIntersectionConnectionElement(node_id=dead_end,
                                                speed_limit=next_speed_limit,
                                                distance=0.0,
                                                position=self.node_id_to_latlng[dead_end],
                                                is_traffic_light=dead_end in self.traffic_light_nodes),
            NodeOnIntersectionConnectionElement(node_id=next_node_id,
                                                speed_limit=next_speed_limit,
                                                distance=next_distance,
                                                position=self.node_id_to_latlng[next_node_id],
                                                is_traffic_light=next_node_id in self.traffic_light_nodes)]
        previous_node_id = dead_end

        while True:
            # follow the connection by getting the next node in this direction: retrieve way, whose end_id isn't the
            # previous node to prevent endless loop; can only result to one row, if it's no intersection
            next_way = self.ways_df[
                (self.ways_df[START_ID_COL_NAME] == next_node_id) & (self.ways_df[END_ID_COL_NAME] != previous_node_id)
                ]
            if next_node_id == curr_intersection:
                return IntersectionConnectionElement(dead_end, curr_intersection, nodes_starting_from_dead_end)
            # might be one-way street, so return None
            elif next_way.empty:
                return None
            else:
                # iterate one step ahead
                previous_node_id = next_node_id
                next_node_id = next_way.iloc[0][END_ID_COL_NAME]

                nodes_starting_from_dead_end.append(
                    NodeOnIntersectionConnectionElement(node_id=next_node_id,
                                                        speed_limit=next_way.iloc[0][SPEED_LIMIT_COL_NAME],
                                                        distance=next_way.iloc[0][AGGREGATED_DISTANCE_COL_NAME],
                                                        position=self.node_id_to_latlng[next_node_id],
                                                        is_traffic_light=next_node_id in self.traffic_light_nodes))


def create_connections_between_intersections(ways_df: pd.DataFrame, nodes_df: pd.DataFrame,
                                             traffic_lights_df: pd.DataFrame,
                                             roundabouts_df: pd.DataFrame) -> [IntersectionConnectionElement]:
    """
    Endpoint to find and create all connections between intersections
    """
    database_creator = IntersectionConnectionsCreator(ways_df, nodes_df, traffic_lights_df, roundabouts_df)

    print('Find all Connections between Intersections:')
    start_time = timeit.default_timer()

    with Pool() as pool:
        results = pool.map(database_creator.create_connections_for_intersection,
                           database_creator.intersections_id_set)

    connections = flatten_list(results)
    end_time = timeit.default_timer()

    # Edge-Case: Remove Intersections connected to themselves and handle them like dead-ends
    connections = [connection for connection in connections
                   if connection.start_id != connection.end_id]
    print('Found %d Connections between Intersections in %.4f seconds.' % (len(connections), (end_time - start_time)))

    return connections
