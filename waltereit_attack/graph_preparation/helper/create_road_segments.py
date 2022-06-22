import timeit
from multiprocessing import Pool

from attack_parameters import TURN_THRESHOLD
from waltereit_attack.graph_preparation.schema.RoadElements import RoadSegmentElement, \
    IntersectionConnectionElement, NodeOnIntersectionConnectionElement
from utils.angle_helper import calc_turn_angle
from utils.functions import flatten_list


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
        """ Check for possible turning maneuvers on a road segment """
        for i in range(2, len(nodes_on_segment)):
            split_point = nodes_on_segment[i - 1].position
            point_before_split = nodes_on_segment[i - 2].position
            point_after_split = nodes_on_segment[i].position

            current_angle = calc_turn_angle(point_before_split,
                                            split_point,
                                            point_after_split)

            if abs(current_angle) > TURN_THRESHOLD:
                # found a node, where a turn could be recognized
                return i - 1

        # no turn on segment found
        return -1

    def __create_normal_segment(self, connection: IntersectionConnectionElement) -> RoadSegmentElement:
        """Segment with multiple subnodes"""
        nodes_on_segment = connection.nodes_on_connection
        # retrieve segment attributes
        # don't consider first node of segment for distance calculation, as that's the starting point
        summed_distance = sum([node.distance for node in nodes_on_segment[1:]])

        return RoadSegmentElement(connection.start_id, connection.end_id, summed_distance, nodes_on_segment)

    def __create_direct_segment(self, connection: IntersectionConnectionElement) -> RoadSegmentElement:
        """no nodes between two intersections, so create RoadSegment without further processing"""
        end_node_dist = connection.nodes_on_connection[-1].distance
        return RoadSegmentElement(connection.start_id, connection.end_id, end_node_dist, connection.nodes_on_connection)


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
