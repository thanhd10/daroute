import timeit
from typing import Set, List

import pandas as pd

from definitions import NODE_ID_COL_NAME, LAT_COL_NAME, LNG_COL_NAME, OSM_ID_COL_NAME, START_ID_COL_NAME
from graph_preparation.helper.create_road_segments import RoadSegmentElement
from graph_preparation.schema.RoadElements import RoundaboutElement
from utils.angle_helper import calc_turn_angle, get_intersect_from_two_lines
from utils.functions import flatten_list, merge_intersecting_sets

U_TURN_ANGLE = -180.0


class RoundaboutUnitsCreator(object):
    def __init__(self,
                 nodes_df: pd.DataFrame,
                 ways_df: pd.DataFrame,
                 roundabouts_df: pd.DataFrame,
                 road_segments: [RoadSegmentElement]):

        self.node_id_to_latlng = nodes_df.set_index(NODE_ID_COL_NAME)[[LAT_COL_NAME, LNG_COL_NAME]].apply(
            tuple, axis=1).to_dict()

        self.real_roundabouts = self.__get_nodes_for_roundabouts(ways_df, roundabouts_df)
        self.road_segments = road_segments

    def __get_nodes_for_roundabouts(self, ways_df: pd.DataFrame, roundabouts_df: pd.DataFrame) -> List[Set[int]]:
        """ Store each roundabout as a set of nodes """
        roundabout_details = ways_df.merge(roundabouts_df, how='inner', on=OSM_ID_COL_NAME)
        # retrieve contiguous ways, that are roundabouts within OSM
        osm_roundabouts = [set(v.unique())
                           for k, v in roundabout_details.groupby(OSM_ID_COL_NAME)
                           [START_ID_COL_NAME]]
        # store a single roundabout by storing all nodes within a roundabout in a set
        return merge_intersecting_sets(osm_roundabouts)

    def add_roundabout_units(self,
                             current_roundabout_nodes: Set[int]) -> [RoundaboutElement]:
        roundabout_units = []

        # query segments before entering a roundabout
        start_segments = [segment for segment in self.road_segments if segment.end_id in current_roundabout_nodes]
        # query segments after exiting a roundabout
        target_segments = [segment for segment in self.road_segments if segment.start_id in current_roundabout_nodes]

        for start_segment in start_segments:
            for target_segment in target_segments:
                # check for "U-Turn Roundabout"
                if start_segment.end_id == target_segment.start_id and start_segment.start_id == target_segment.end_id:
                    roundabout_units.append(self.__create_u_turn_roundabout(start_segment, target_segment))
                else:
                    roundabout_units.append(self.__create_roundabout_exit(start_segment, target_segment))

        return roundabout_units

    def __create_roundabout_exit(self, start_segment: RoadSegmentElement,
                                 target_segment: RoadSegmentElement) -> RoundaboutElement:
        start_segment_start = self.node_id_to_latlng[start_segment.start_id]
        start_segment_end = self.node_id_to_latlng[start_segment.end_id]
        end_segment_start = self.node_id_to_latlng[target_segment.start_id]
        end_segment_end = self.node_id_to_latlng[target_segment.end_id]

        # receive a helper point for turn angle calculation
        intersect = get_intersect_from_two_lines(start_segment_start, start_segment_end, end_segment_start,
                                                 end_segment_end)

        # no intersect point of two lines is found, if lines are parallel, i.e. no angle change occurs
        if intersect == (float('inf'), float('inf')):
            angle = 0.0
        else:
            angle = calc_turn_angle(start_segment_start, intersect, end_segment_end)

        return RoundaboutElement(start_segment.segment_id, target_segment.segment_id, start_segment.end_id,
                                 angle, target_segment.driving_direction,
                                 start_segment_start,
                                 start_segment_end,
                                 end_segment_end,
                                 start_segment.distance,
                                 target_segment.distance)

    def __create_u_turn_roundabout(self, start_segment: RoadSegmentElement,
                                   target_segment: RoadSegmentElement) -> RoundaboutElement:
        return RoundaboutElement(start_segment.segment_id, target_segment.segment_id, start_segment.end_id,
                                 U_TURN_ANGLE, target_segment.driving_direction,
                                 self.node_id_to_latlng[start_segment.start_id],
                                 self.node_id_to_latlng[start_segment.end_id],
                                 self.node_id_to_latlng[target_segment.end_id],
                                 start_segment.distance, target_segment.distance)


def create_roundabout_units(nodes_df: pd.DataFrame,
                            ways_df: pd.DataFrame,
                            roundabouts_df: pd.DataFrame,
                            road_segments: [RoadSegmentElement]) -> [RoundaboutElement]:
    """ Remove Road Segments within a Roundabout and return Tuple of Roundabout-Turn units and cleaned Road Segments """

    start_time = timeit.default_timer()
    roundabout_unit_creator = RoundaboutUnitsCreator(nodes_df, ways_df, roundabouts_df, road_segments)

    all_roundabouts = [roundabout_unit_creator.add_roundabout_units(current_roundabout_nodes)
                       for current_roundabout_nodes in roundabout_unit_creator.real_roundabouts]
    all_roundabouts = flatten_list(all_roundabouts)

    end_time = timeit.default_timer()
    print("Created %d roundabout units in %.2f seconds." % (len(all_roundabouts), (end_time - start_time)))

    return all_roundabouts
