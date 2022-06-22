import timeit
from multiprocessing import Pool
from typing import Tuple, List

import geopy.distance
import pandas as pd

from definitions import NODE_ID_COL_NAME, LAT_COL_NAME, LNG_COL_NAME
from graph_preparation.helper.create_roundabouts_database import create_roundabout_units
from graph_preparation.database_parameters import SMALL_ANGLE_THRESHOLD, MIN_DISTANCE_STRAIGHT_TRAVEL, \
    MIN_DISTANCE_OF_ADJACENT_NODES
from graph_preparation.helper.create_road_segments import RoadSegmentElement
from graph_preparation.helper.create_turns_over_multiple_segments import get_additional_turns_over_short_segments
from graph_preparation.schema.RoadElements import TurnElement
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

                turn_angle, curvature_angle, start_point, end_point = self.__calc_curr_turn_angle(current_start,
                                                                                                  current_target,
                                                                                                  intersection_position)
                curvature = curvature_angle + current_target.road_curvature

                turns_at_intersection.append(
                    TurnElement(seg_start_id=current_start.segment_id, seg_target_id=current_target.segment_id,
                                intersection_id=intersection_id, angle=turn_angle,
                                end_direction=current_target.driving_direction,
                                distance_before=current_start.distance, distance_after=current_target.distance,
                                start=start_point, center=intersection_position,
                                end=end_point,
                                curvature=curvature)
                )

        return turns_at_intersection

    # noinspection PyMethodMayBeStatic
    def __calc_curr_turn_angle(self, start_segment: RoadSegmentElement, target_segment: RoadSegmentElement,
                               intersection_position: Tuple[float, float]) -> Tuple[float,
                                                                                    float,
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
        # angle from two adjacent nodes from intersection
        direct_angle = turn_angle

        # check direction of possible turn
        if turn_angle > SMALL_ANGLE_THRESHOLD:
            is_right_turn = True
        elif turn_angle < - SMALL_ANGLE_THRESHOLD:
            is_right_turn = False
        else:
            return turn_angle, direct_angle, curr_start_position, curr_end_position

        # calculate additional small angles on start segment, if needed
        angles_on_start_segment, curr_start_position = self.__get_turn_angles_on_start_segment(
            start_segment, intersection_position, curr_start_position, is_right_turn, not is_right_turn)

        # calculate additional small angles on target segment, if needed
        angles_on_end_segment, curr_end_position = self.__get_turn_angles_on_target_segment(
            target_segment, intersection_position, curr_end_position, is_right_turn, not is_right_turn)

        # add summed up angles on each of the segments
        turn_angle += angles_on_start_segment + angles_on_end_segment

        return turn_angle, direct_angle, curr_start_position, curr_end_position

    # noinspection PyMethodMayBeStatic
    def __get_turn_angles_on_start_segment(self, start_segment: RoadSegmentElement,
                                           intersection_position: Tuple[float, float],
                                           curr_start_position: Tuple[float, float], is_right_turn: bool,
                                           is_left_turn: bool) -> Tuple[float, Tuple[float, float]]:
        """
        Check all small angles on target segment. Stop summing small angles up, if:
        - angle is too small
        - change in direction occured
        - distance between center and target point exceeds a specific threshold, meaning turn started with this angle
        @:return - the summed up angle
                 - the position where the possible turn starts
        """
        angle_on_start_segment = 0.0
        # no angles on segment, if there are not at least 3 points
        if len(start_segment.nodes_on_segment) > 2:
            target_position = intersection_position
            center_position = curr_start_position
            # list has to be iterated in reverse, as this is the start segment leading to the current intersection
            for start in reversed(start_segment.nodes_on_segment[:-2]):
                if geopy.distance.distance(start.position, center_position).m < MIN_DISTANCE_OF_ADJACENT_NODES:
                    continue

                curr_start_position = start.position
                next_angle = calc_turn_angle(curr_start_position, center_position, target_position)
                # condition checks to continue calculation on segment
                if is_right_turn and next_angle > SMALL_ANGLE_THRESHOLD:
                    angle_on_start_segment += next_angle
                elif is_left_turn and next_angle < -SMALL_ANGLE_THRESHOLD:
                    angle_on_start_segment += next_angle
                else:
                    break
                # early exit condition: turn starts here, as before this angle a longer straight distance occurs
                if geopy.distance.distance(curr_start_position, center_position).m > MIN_DISTANCE_STRAIGHT_TRAVEL:
                    break

                # update helper variables
                target_position = center_position
                center_position = curr_start_position

        return angle_on_start_segment, curr_start_position

    # noinspection PyMethodMayBeStatic
    def __get_turn_angles_on_target_segment(self, target_segment: RoadSegmentElement,
                                            intersection_position: Tuple[float, float],
                                            curr_target_position: Tuple[float, float], is_right_turn: bool,
                                            is_left_turn: bool) -> Tuple[float, Tuple[float, float]]:
        """
        Check all small angles on target segment. Stop summing small angles up, if:
        - angle is too small
        - change in direction occured
        - distance between center and target point exceeds a specific threshold, meaning turn ended with this angle
        @:return - the summed up angle
                 - the position where the possible turn ends
        """
        angle_on_target_segment = 0.0
        # no angles on segment, if there are not at least 3 points
        if len(target_segment.nodes_on_segment) > 2:
            start_position = intersection_position
            center_position = curr_target_position

            for target in target_segment.nodes_on_segment[2:]:
                if geopy.distance.distance(target.position, center_position).m < MIN_DISTANCE_OF_ADJACENT_NODES:
                    continue

                curr_target_position = target.position
                next_angle = calc_turn_angle(start_position, center_position, curr_target_position)
                # condition checks to continue calculation on segment
                if is_right_turn and next_angle > SMALL_ANGLE_THRESHOLD:
                    angle_on_target_segment += next_angle
                elif is_left_turn and next_angle < -SMALL_ANGLE_THRESHOLD:
                    angle_on_target_segment += next_angle
                else:
                    break
                # early exit condition: turn ends here, as after this angle a longer straight distance occurs
                if geopy.distance.distance(center_position, curr_target_position).m > MIN_DISTANCE_STRAIGHT_TRAVEL:
                    break

                # update helper variables
                start_position = center_position
                center_position = curr_target_position

        return angle_on_target_segment, curr_target_position


def create_all_possible_turns(road_segments: [RoadSegmentElement],
                              nodes_df: pd.DataFrame,
                              ways_df: pd.DataFrame,
                              roundabouts_df: pd.DataFrame) -> pd.DataFrame:
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

    end_time = timeit.default_timer()
    print('Created %d turns in %.4f seconds.' % (len(all_turns), (end_time - start_time)))

    all_turns = all_turns + get_additional_turns_over_short_segments(road_segments, all_turns)

    all_roundabouts = create_roundabout_units(nodes_df, ways_df, roundabouts_df, road_segments)

    # remove edge case of duplicates
    all_turns = set(all_turns)
    all_roundabouts = set(all_roundabouts)

    # convert turns to dataFrames and set is_roundabout attribute
    normal_turns_dict = pd.DataFrame.from_records([turn.to_dict() for turn in all_turns])
    normal_turns_dict['is_roundabout'] = False
    roundabout_turns_dict = pd.DataFrame.from_records([roundabout.to_dict() for roundabout in all_roundabouts])
    roundabout_turns_dict['is_roundabout'] = True

    # return unified dataframe containing all turns and roundabouts
    return pd.concat([normal_turns_dict, roundabout_turns_dict], ignore_index=True)

