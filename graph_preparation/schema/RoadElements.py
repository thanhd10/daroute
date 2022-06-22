import itertools
from typing import Tuple, List


class NodeOnIntersectionConnectionElement(object):
    def __init__(self, node_id: int, speed_limit: int, distance: float, position: Tuple[float, float],
                 is_traffic_light: bool):
        self.node_id = node_id
        self.speed_limit = speed_limit
        # distance is between last node and this node on a connection between intersections
        self.distance = distance
        self.position = position

        self.is_traffic_light = is_traffic_light


class IntersectionConnectionElement(object):
    def __init__(self, start_id: int, end_id: int, nodes_on_connection: [NodeOnIntersectionConnectionElement]):
        self.start_id = start_id
        self.end_id = end_id
        # all nodes between two intersections including the two intersections itselves
        self.nodes_on_connection = nodes_on_connection


class RoadSegmentElement(object):
    # store the next id to assign a road segment
    id_iterator = itertools.count()

    def __init__(self, start_id: int, end_id: int, distance: float, driving_direction: int, road_curvature: float,
                 nodes_on_segment: List[NodeOnIntersectionConnectionElement], distance_to_traffic_light: float):
        self.start_id = start_id
        self.end_id = end_id
        self.distance = distance
        self.driving_direction = driving_direction
        self.road_curvature = road_curvature
        self.nodes_on_segment = nodes_on_segment
        self.distance_to_traffic_light = distance_to_traffic_light

        self.first_node_after_start = self.nodes_on_segment[1].position
        self.last_node_before_end = self.nodes_on_segment[-2].position
        try:
            self.speed_limit = min([node.speed_limit for node in self.nodes_on_segment if node.speed_limit != -1])
        except (ValueError, TypeError):
            self.speed_limit = 0

    # noinspection PyAttributeOutsideInit
    def assign_id(self):
        """ Assignment after initializing all road segments needed due to multiprocessing """
        self.segment_id = next(RoadSegmentElement.id_iterator)

    def to_dict(self):
        return {
            'segment_id': self.segment_id,
            'start_id': self.start_id,
            'end_id': self.end_id,
            'distance': self.distance,
            'road_curvature': self.road_curvature,
            'driving_direction': self.driving_direction,
            'distance_to_traffic_light': self.distance_to_traffic_light,
            'speed_limit': self.speed_limit,
            'first_node_after_start': self.first_node_after_start,
            'last_node_before_end': self.last_node_before_end
        }


class TurnElement(object):
    def __init__(self, seg_start_id: int, seg_target_id: int, intersection_id: int,
                 angle: float, end_direction: int, start: Tuple[float, float], center: Tuple[float, float],
                 end: Tuple[float, float], distance_before: float, distance_after: float, curvature: float,
                 is_segment_skipping: bool = False):
        self.seg_start_id = seg_start_id
        self.seg_target_id = seg_target_id
        self.intersection_id = intersection_id
        self.angle = angle
        self.end_direction = end_direction
        self.distance_before = distance_before
        self.distance_after = distance_after
        self.start = start
        self.center = center
        self.end = end
        self.heading_change = curvature
        self.is_segment_skipping = is_segment_skipping

    def to_dict(self):
        return {
            'segment_start_id': self.seg_start_id,
            'segment_target_id': self.seg_target_id,
            'intersection_id': self.intersection_id,
            'angle': self.angle,
            'end_direction': self.end_direction,
            'distance_before': self.distance_before,
            'distance_after': self.distance_after,
            'start_lat': self.start[0],
            'start_lng': self.start[1],
            'intersection_lat': self.center[0],
            'intersection_lng': self.center[1],
            'end_lat': self.end[0],
            'end_lng': self.end[1],
            'heading_change': self.heading_change,
            'is_segment_skipping': self.is_segment_skipping
        }

    def __eq__(self, other):
        return type(self) is type(other) and self.angle == other.angle and self.end_direction == other.end_direction \
               and self.distance_before == other.distance_before and self.distance_after == other.distance_after and \
               self.center == other.center

    def __hash__(self):
        return hash((self.angle, self.end_direction, self.distance_before, self.distance_after,
                     self.start, self.center, self.end))


class RoundaboutElement(TurnElement):
    def __init__(self, seg_start_id: int, seg_target_id: int,
                 intersection_id: int, angle: float, end_direction: int,
                 start: Tuple[float, float], center: Tuple[float, float], end: Tuple[float, float],
                 distance_before: float, distance_after: float):
        super().__init__(seg_start_id, seg_target_id, intersection_id, angle, end_direction, start, center, end,
                         distance_before, distance_after, angle)
