import timeit
from multiprocessing import Pool
from typing import Tuple

import geopy.distance

from attack_parameters import TURN_THRESHOLD
from graph_preparation.database_parameters import THRESHOLD_DISTANCE_FOR_POINTS, MINIMUM_DISTANCE_FOR_SPLIT
from graph_preparation.schema.RoadElements import RoadSegmentElement, IntersectionConnectionElement, \
    NodeOnIntersectionConnectionElement
from utils.angle_helper import calc_binary_direction_to_north, calc_turn_angle
from utils.functions import flatten_list


def find_first_point_after_start(nodes_on_segment: [NodeOnIntersectionConnectionElement]) -> Tuple[float, float]:
    """ find a point, that is at least x meters after the start of the node list for better angle calculation """
    curr_distance = 0.0
    for node in nodes_on_segment[1:]:
        curr_distance += node.distance
        if curr_distance >= THRESHOLD_DISTANCE_FOR_POINTS:
            return node.position

    # no point found between two intersections, that is more then the threshold away from, so return end of segment
    return nodes_on_segment[-1].position


def find_last_point_before_end(nodes_on_segment: [NodeOnIntersectionConnectionElement]) -> Tuple[float, float]:
    """ find a point, that is at least x meters before the end of the node list for better angle calculation """
    curr_distance = 0.0
    for node_start, node_next in zip(reversed(nodes_on_segment[1:]), reversed(nodes_on_segment[:-1])):
        curr_distance += node_start.distance
        if curr_distance >= THRESHOLD_DISTANCE_FOR_POINTS:
            return node_next.position

    # no point found between two intersections, that is more then the threshold away from, so return start of segment
    return nodes_on_segment[0].position


def calc_road_curvature(nodes_on_segment: [NodeOnIntersectionConnectionElement]) -> float:
    road_curvature = 0

    for i in range(2, len(nodes_on_segment)):
        road_curvature += calc_turn_angle(nodes_on_segment[i - 2].position,
                                          nodes_on_segment[i - 1].position,
                                          nodes_on_segment[i].position)
    return road_curvature


def find_traffic_light(nodes_on_segment: [NodeOnIntersectionConnectionElement]) -> float:
    """ Get the distance of a possible traffic light no a road segment """

    # ignore start intersection as traffic light, otherwise later re-connection of segments will lead to considering
    # traffic lights on intersections twice
    distance_bridged = nodes_on_segment[0].distance
    for node in nodes_on_segment[1:]:
        distance_bridged += node.distance
        if node.is_traffic_light:
            return distance_bridged

    # no traffic light on segment
    return -1


# noinspection PyMethodMayBeStatic
class RoadSegmentCreator(object):

    def __init__(self):
        self.new_turning_points = []

    def create_road_segment(self, connection: IntersectionConnectionElement) -> [RoadSegmentElement]:
        # a connection has 2 points at minimum (start and end)
        if len(connection.nodes_on_connection) == 2:
            # Create a Segment with a direct connection between two Intersection
            return [self.__create_direct_segment(connection)]
        else:
            # Create a Segment with multiple nodes on it
            nodes_on_segment = connection.nodes_on_connection

            split_index = self.__check_for_turn_on_segment(nodes_on_segment)
            if split_index != -1:
                turning_node = nodes_on_segment[split_index].node_id
                self.new_turning_points.append(turning_node)

                # split segment at split_index and recall create_road_segment for both sub segments
                return flatten_list([
                    self.create_road_segment(IntersectionConnectionElement(
                        start_id=connection.start_id,
                        end_id=turning_node,
                        nodes_on_connection=nodes_on_segment[:split_index + 1])),
                    self.create_road_segment(IntersectionConnectionElement(
                        start_id=turning_node,
                        end_id=connection.end_id,
                        nodes_on_connection=nodes_on_segment[split_index:]))
                ])
            else:
                return [self.__create_normal_segment(connection)]

    def __check_for_turn_on_segment(self, nodes_on_segment: [NodeOnIntersectionConnectionElement]):
        max_split_point = -1
        max_split_point_angle = 0

        """ Check for possible turning maneuvers on a road segment """
        for i in range(2, len(nodes_on_segment)):
            split_point = nodes_on_segment[i - 1]
            point_before_split = find_last_point_before_end(nodes_on_segment[:i])
            point_after_split = find_first_point_after_start(nodes_on_segment[i - 1:])

            current_curvature = calc_turn_angle(point_before_split,
                                                split_point.position,
                                                point_after_split)

            if abs(current_curvature) >= TURN_THRESHOLD \
                    and self.__is_min_split_distance(split_point.position, nodes_on_segment[0].position) \
                    and self.__is_min_split_distance(split_point.position, nodes_on_segment[-1].position):
                # found a node, where a turn could be recognized
                if abs(current_curvature) > max_split_point_angle:
                    max_split_point = i - 1
                    max_split_point_angle = abs(current_curvature)

        # no turn on segment found
        return max_split_point

    def __is_min_split_distance(self, split_position: Tuple[float, float], position: Tuple[float, float]) -> bool:
        return geopy.distance.distance(split_position, position).m > MINIMUM_DISTANCE_FOR_SPLIT

    def __create_normal_segment(self, connection: IntersectionConnectionElement) -> RoadSegmentElement:
        """Segment with multiple subnodes"""
        nodes_on_segment = connection.nodes_on_connection
        # retrieve segment attributes
        first_point_after_start = find_first_point_after_start(nodes_on_segment)
        driving_direction = calc_binary_direction_to_north(nodes_on_segment[0].position, first_point_after_start)
        # don't consider first node of segment for distance calculation, as that's the starting point
        summed_distance = sum([node.distance for node in nodes_on_segment[1:]])
        road_curvature = calc_road_curvature(nodes_on_segment)
        distance_to_traffic_light = find_traffic_light(nodes_on_segment)

        return RoadSegmentElement(connection.start_id, connection.end_id, summed_distance, driving_direction,
                                  road_curvature, nodes_on_segment, distance_to_traffic_light)

    def __create_direct_segment(self, connection: IntersectionConnectionElement) -> RoadSegmentElement:
        """no nodes between two intersections, so create RoadSegment without further processing"""
        start_node = connection.nodes_on_connection[0]
        end_node = connection.nodes_on_connection[-1]

        driving_direction = calc_binary_direction_to_north(start_node.position, end_node.position)
        distance_to_traffic_light = find_traffic_light(connection.nodes_on_connection)
        return RoadSegmentElement(connection.start_id, connection.end_id, end_node.distance,
                                  driving_direction, 0.0, connection.nodes_on_connection, distance_to_traffic_light)


def create_all_road_segments(intersection_connections: [IntersectionConnectionElement]) -> [RoadSegmentElement]:
    """
    Endpoint for creating a list of RoadSegments for the given data
    """
    print('Start creating Road Segments:')
    start_time = timeit.default_timer()

    road_segment_creator = RoadSegmentCreator()
    with Pool() as pool:
        road_segments = pool.map(road_segment_creator.create_road_segment, intersection_connections)
    road_segments = flatten_list(road_segments)

    # Assign each segment a unique id sequentially after creating them due to multiprocessing
    for segment in road_segments:
        segment.assign_id()

    end_time = timeit.default_timer()
    print('Created %d Road Segments in %.4f seconds.' % (len(road_segments), (end_time - start_time)))
    return road_segments
