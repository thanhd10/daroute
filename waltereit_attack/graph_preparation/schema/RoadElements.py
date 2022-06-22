import itertools
from typing import Tuple, List

from waltereit_attack.attack_parameters import TURN_THRESHOLD, IS_LEFT, IS_RIGHT, IS_STRAIGHT


class NodeOnIntersectionConnectionElement(object):
    def __init__(self, node_id: int, distance: float, position: Tuple[float, float]):
        self.node_id = node_id
        # distance is between last node and this node on a connection between intersections
        self.distance = distance
        self.position = position


class IntersectionConnectionElement(object):
    def __init__(self, start_id: int, end_id: int, nodes_on_connection: [NodeOnIntersectionConnectionElement]):
        self.start_id = start_id
        self.end_id = end_id
        # all nodes between two intersections including the two intersections itselves
        self.nodes_on_connection = nodes_on_connection


class RoadSegmentElement(object):
    # store the next id to assign a road segment
    id_iterator = itertools.count()

    def __init__(self, start_id: int, end_id: int, distance: float,
                 nodes_on_segment: List[NodeOnIntersectionConnectionElement]):
        self.start_id = start_id
        self.end_id = end_id
        self.distance = distance
        self.nodes_on_segment = nodes_on_segment

        self.first_node_after_start = self.nodes_on_segment[1].position
        self.last_node_before_end = self.nodes_on_segment[-2].position

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
            'first_node_after_start': self.first_node_after_start,
            'last_node_before_end': self.last_node_before_end
        }


class TurnElement(object):
    def __init__(self, seg_start_id: int, seg_target_id: int, intersection_id: int,
                 angle: float, start: Tuple[float, float], center: Tuple[float, float],
                 end: Tuple[float, float], distance_before: float, distance_after: float):
        self.seg_start_id = seg_start_id
        self.seg_target_id = seg_target_id
        self.intersection_id = intersection_id
        self.angle = angle
        self.distance_before = distance_before
        self.distance_after = distance_after
        self.start = start
        self.center = center
        self.end = end

        if angle > TURN_THRESHOLD:
            self.connection_type = IS_RIGHT
        elif angle < - TURN_THRESHOLD:
            self.connection_type = IS_LEFT
        else:
            self.connection_type = IS_STRAIGHT

    def to_dict(self):
        return {
            'segment_start_id': self.seg_start_id,
            'segment_target_id': self.seg_target_id,
            'intersection_id': self.intersection_id,
            'angle': self.angle,
            'connection_type': self.connection_type,
            'distance_before': self.distance_before,
            'distance_after': self.distance_after,
            'start_lat': self.start[0],
            'start_lng': self.start[1],
            'intersection_lat': self.center[0],
            'intersection_lng': self.center[1],
            'end_lat': self.end[0],
            'end_lng': self.end[1]
        }

    def __eq__(self, other):
        return type(self) is type(other) and self.angle == other.angle \
               and self.distance_before == other.distance_before and self.distance_after == other.distance_after and \
               self.center == other.center

    def __hash__(self):
        return hash((self.angle, self.distance_before, self.distance_after,
                     self.start, self.center, self.end))
