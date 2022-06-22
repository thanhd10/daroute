import timeit
from multiprocessing import Pool
from typing import Tuple, List

import pandas as pd

from definitions import NODE_ID_COL_NAME, LAT_COL_NAME, LNG_COL_NAME
from waltereit_attack.graph_preparation.schema.RoadElements import TurnElement, RoadSegmentElement
from utils.angle_helper import calc_turn_angle
from utils.functions import flatten_list


class TurnDatabaseCreator(object):

    def __init__(self, road_segments: [RoadSegmentElement]):
        self.road_segments = road_segments

    def create_turns_at_intersection(self, intersection_id: int, intersection_position: Tuple[float, float]) \
            -> List[TurnElement]:
        turns_at_intersection = []

        # retrieve all intersections, that can be REACHED FROM THE current intersection
        possible_targets = [road_segment for road_segment in self.road_segments
                            if road_segment.start_id == intersection_id]
        # retrieve all intersections, FROM WHERE the current intersection can be REACHED
        possible_starts = [road_segment for road_segment in self.road_segments
                           if road_segment.end_id == intersection_id]

        for current_target in possible_targets:
            for current_start in possible_starts:
                # skip the target, as u-turn on the same road-segment is not possible
                if current_start.start_id == current_target.end_id:
                    continue

                turn_angle, start_point, end_point = self.__calc_curr_turn_angle(current_start,
                                                                                 current_target,
                                                                                 intersection_position)

                turns_at_intersection.append(
                    TurnElement(seg_start_id=current_start.segment_id,
                                seg_target_id=current_target.segment_id,
                                intersection_id=intersection_id,
                                angle=turn_angle,
                                distance_before=current_start.distance,
                                distance_after=current_target.distance,
                                start=start_point,
                                center=intersection_position,
                                end=end_point)
                )

        return turns_at_intersection

    # noinspection PyMethodMayBeStatic
    def __calc_curr_turn_angle(self, start_segment: RoadSegmentElement, target_segment: RoadSegmentElement,
                               intersection_position: Tuple[float, float]) -> Tuple[float,
                                                                                    Tuple[float, float],
                                                                                    Tuple[float, float]]:
        """

        :param start_segment: the segment from where the vehicle is coming
        :param target_segment: the segment where the vehicle is driving afterwards
        :param intersection_position: the intersection point connecting both segments
        :return: - the angle at the intersection
                 - the start of the possible turn
                 - the end of the possible turn
        """
        curr_start_position = start_segment.nodes_on_segment[-2].position
        curr_end_position = target_segment.nodes_on_segment[1].position
        # first angle between two segments
        turn_angle = calc_turn_angle(curr_start_position, intersection_position, curr_end_position)

        return turn_angle, curr_start_position, curr_end_position


def create_all_possible_turns(road_segments: [RoadSegmentElement],
                              nodes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Endpoint for creating all possible turns for the given data
    """
    print('Start creating Turn Database:')
    start_time = timeit.default_timer()
    # Retrieve all intersection_ids from the RoadSegments, as a RoadSegment always starts at an Intersection
    intersections_id_set = set([road_segment.start_id for road_segment in road_segments])

    turn_database_creator = TurnDatabaseCreator(road_segments)

    # map nodes from node_id to their corresponding (lat, lng)
    node_id_to_latlng = nodes_df.set_index(NODE_ID_COL_NAME)[[LAT_COL_NAME, LNG_COL_NAME]].apply(
        tuple, axis=1).to_dict()
    intersection_details = [(intersection_id, node_id_to_latlng[intersection_id])
                            for intersection_id in intersections_id_set]

    with Pool() as pool:
        all_turns = pool.starmap(turn_database_creator.create_turns_at_intersection,
                                 intersection_details)
    all_turns = flatten_list(all_turns)
    # remove edge case of duplicates
    all_turns = set(all_turns)

    end_time = timeit.default_timer()
    print('Created %d turns in %.4f seconds.' % (len(all_turns), (end_time - start_time)))

    # convert turns to dataFrames and set is_roundabout attribute
    normal_turns_dict = pd.DataFrame.from_records([turn.to_dict() for turn in all_turns])
    normal_turns_dict['is_roundabout'] = False

    # return unified dataframe containing all turns and roundabouts
    return normal_turns_dict
