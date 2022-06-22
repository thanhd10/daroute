import timeit
from multiprocessing import Pool
from typing import List

import pandas as pd

from graph_preparation.database_parameters import SHORT_SEGMENT_TURN_THRESHOLD, SHORT_SEGMENT_LENGTH_THRESHOLD
from graph_preparation.helper.create_road_segments import RoadSegmentElement
from graph_preparation.schema.RoadElements import TurnElement
from utils.functions import flatten_list


class TurnOverShortSegmentCreator(object):
    def __init__(self, turns_df: pd.DataFrame):
        self.turns_df = turns_df

    def get_long_stretching_turn_over_short_segment(self, short_segment: RoadSegmentElement) -> [TurnElement]:
        """
        Combine turns over short segments, that might be recognized as a single steering movement.
        """
        # get all turns before and after this segment
        turns_before = self.turns_df[self.turns_df['segment_target_id'] == short_segment.segment_id]
        turns_after = self.turns_df[self.turns_df['segment_start_id'] == short_segment.segment_id]

        return self.__get_possible_right_turn(turns_before, turns_after) + self.__get_possible_left_turn(turns_before,
                                                                                                         turns_after)

    def get_long_stretching_turn_over_two_very_short_segments(self,
                                                              first_short_segment_id: int,
                                                              second_short_segment_id: int) -> [TurnElement]:
        """
        Edge-Case: Two successively following segments could be very short and their combined length could
        still be considered as a short segment. Add turn units, where a steering movement could happen over
        them.
        """
        # get all turns before and after this segment
        turns_before = self.turns_df[self.turns_df['segment_target_id'] == first_short_segment_id]
        turns_after = self.turns_df[self.turns_df['segment_start_id'] == second_short_segment_id]

        return self.__get_possible_right_turn(turns_before, turns_after) + self.__get_possible_left_turn(turns_before,
                                                                                                         turns_after)

    def __get_possible_right_turn(self, turns_before: pd.DataFrame, turns_after: pd.DataFrame) -> List[TurnElement]:
        # check for long stretching right turn
        if len(turns_before[turns_before['angle'] > SHORT_SEGMENT_TURN_THRESHOLD]) > 0 and \
                len(turns_after[turns_after['angle'] > SHORT_SEGMENT_TURN_THRESHOLD]) > 0:
            turns = []
            # add new turn unit with cumulated turn maneuver
            for i, turn_before in turns_before[turns_before['angle'] > SHORT_SEGMENT_TURN_THRESHOLD].iterrows():
                for j, turn_after in turns_after[turns_after['angle'] > SHORT_SEGMENT_TURN_THRESHOLD].iterrows():
                    turns.append(self.__add_turn_over_three_segments(turn_before, turn_after))
            return turns
        else:
            return []

    def __get_possible_left_turn(self, turns_before: pd.DataFrame, turns_after: pd.DataFrame) -> List[TurnElement]:
        # check for long stretching left turn
        if len(turns_before[turns_before['angle'] < -SHORT_SEGMENT_TURN_THRESHOLD]) > 0 and \
                len(turns_after[turns_after['angle'] < -SHORT_SEGMENT_TURN_THRESHOLD]) > 0:
            turns = []
            # add new turn unit with cumulated turn maneuver
            for i, turn_before in turns_before[turns_before['angle'] < -SHORT_SEGMENT_TURN_THRESHOLD].iterrows():
                for j, turn_after in turns_after[turns_after['angle'] < -SHORT_SEGMENT_TURN_THRESHOLD].iterrows():
                    turns.append(self.__add_turn_over_three_segments(turn_before, turn_after))
            return turns
        else:
            return []

    # noinspection PyMethodMayBeStatic
    def __add_turn_over_three_segments(self, turn_before: pd.Series, turn_after: pd.Series) -> TurnElement:
        """ Create a turning maneuver, where one intersection is skipped, that might not be recognized separately"""
        return TurnElement(
            seg_start_id=int(turn_before['segment_start_id']),
            seg_target_id=int(turn_after['segment_target_id']),
            intersection_id=int(turn_after['intersection_id']),
            angle=turn_before['angle'] + turn_after['angle'],
            end_direction=int(turn_after['end_direction']),
            distance_before=turn_before['distance_before'] + (turn_before['distance_after'] / 2),
            distance_after=(turn_after['distance_before'] / 2) + turn_after['distance_after'],
            start=(turn_before['start_lat'], turn_before['start_lng']),
            center=(turn_after['intersection_lat'], turn_after['intersection_lng']),
            end=(turn_after['end_lat'], turn_after['end_lng']),
            curvature=turn_before['heading_change'] + turn_after['heading_change'],
            is_segment_skipping=True
        )


def get_additional_turns_over_short_segments(all_segments: [RoadSegmentElement], all_turns: [TurnElement]) \
        -> [TurnElement]:
    """
    AFTER creating the turn database add additional turns, that could occur when a turning maneuver starts before
    a short road segment and another turning maneuver in the same direction starts after a short road segment
    """
    print("Start finding long stretching turns over multiple intersections:")
    start_time = timeit.default_timer()
    # Retrieve all segments, that are short and could be part of a longer stretching turn
    short_segments = [segment for segment in all_segments if segment.distance <= SHORT_SEGMENT_LENGTH_THRESHOLD]
    turns_df = pd.DataFrame.from_records([turn.to_dict() for turn in all_turns])

    short_segment_turn_creator = TurnOverShortSegmentCreator(turns_df)
    with Pool() as pool:
        short_segment_turns = pool.map(short_segment_turn_creator.get_long_stretching_turn_over_short_segment,
                                       short_segments)
    short_segment_turns = flatten_list(short_segment_turns)

    # two very short segments could also be a unit. if their length is below the threshold, they are considered as one
    # segment
    short_straight_segments = turns_df[(turns_df['distance_before'] + turns_df['distance_after'] <
                                        SHORT_SEGMENT_LENGTH_THRESHOLD) &
                                       (turns_df['start_lng'] != turns_df['end_lng']) &
                                       (turns_df['start_lat'] != turns_df['end_lng'])]
    with Pool() as pool:
        combined_short_segment_turns = pool.starmap(
            short_segment_turn_creator.get_long_stretching_turn_over_two_very_short_segments,
            zip(short_straight_segments['segment_start_id'], short_straight_segments['segment_target_id'])
        )
    combined_short_segment_turns = flatten_list(combined_short_segment_turns)

    end_time = timeit.default_timer()
    print('Created %d short segment turns and %d very short segment turns in %.4f seconds.'
          % (len(short_segment_turns), len(combined_short_segment_turns), (end_time - start_time)))

    return short_segment_turns + combined_short_segment_turns
