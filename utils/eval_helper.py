import pickle
from itertools import groupby
from typing import Dict, List

from utils.functions import flatten_list


def store_osm_path(osm_path: [int], target_dir: str):
    with open(target_dir, 'wb') as dump_file:
        pickle.dump(osm_path, dump_file)


def get_segment_to_osm_ids_dict(file_target_dir: str) -> Dict[int, List[int]]:
    """ Load a pickled segment_to_osm_ids dict and return it """
    with open(file_target_dir + '/db/segment_to_osm_ids.pickle', 'rb') as dump_file:
        segment_to_osm_ids = pickle.load(dump_file)
        return segment_to_osm_ids


def create_osm_path(segment_ids: [int], segment_to_osm_id_map: Dict[int, List[int]]) -> [int]:
    """ Map the segment_ids of a route candidate to a full osm_id path """
    osm_path = flatten_list([segment_to_osm_id_map[segment_id] for segment_id in segment_ids])
    # remove consecutive duplicates, as segments overlap at an intersection
    return [x[0] for x in groupby(osm_path)]


def create_osm_path_with_only_intersections(segment_ids, segment_to_osm_id_map: Dict[int, List]) -> [int]:
    """ Get the corresponding intersection osm_ids for a sequence of segment_ids """
    # take the start intersection of every segment
    osm_path = [segment_to_osm_id_map[segment_id][0] for segment_id in segment_ids]
    # take the last intersection of the last segment
    last_corner = [segment_to_osm_id_map[segment_ids[0]][-1]]
    return osm_path + last_corner


def is_perfect_path_match(ground_truth_osm_path: [int], candidate_osm_path: [int]) -> bool:
    """
    A perfect match occurs, if
        1. all intersections, where turns happened, are within the path
        2. the start is correct
        3. the end is correct
    """
    return set(ground_truth_osm_path).issubset(candidate_osm_path) and \
           candidate_osm_path[0] == ground_truth_osm_path[0] and \
           candidate_osm_path[-1] == ground_truth_osm_path[-1]


def is_start_and_end_match(ground_truth_osm_path: [int], candidate_osm_path: [int]) -> bool:
    """ Only start and end point have to match """
    return candidate_osm_path[0] == ground_truth_osm_path[0] and \
           candidate_osm_path[-1] == ground_truth_osm_path[-1]


def is_percentage_match(full_ground_truth_osm_path: [int], candidate_osm_path: [int], percentage: float) -> bool:
    """
    NOTE: full path of ground truth needed, not only intersection ids
    https://stackoverflow.com/questions/29929074/percentage-overlap-of-two-lists
    """
    # create a set, where all overlapping elements are within
    overlap = set(full_ground_truth_osm_path) & set(candidate_osm_path)
    # create a set with all unique elements from both sets
    universe = set(full_ground_truth_osm_path) | set(candidate_osm_path)
    return float(len(overlap) / len(universe)) >= percentage
