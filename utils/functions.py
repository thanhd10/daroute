from functools import reduce
from typing import Dict, List, Set


def merge_dicts(list_of_dicts: List[Dict]) -> Dict:
    """
    merge a list of dicts into a single list
    """
    return {k: v for d in list_of_dicts for k, v in d.items()}


def flatten_list(t: List[List]) -> List:
    """
    flatten a 2-dimensional list to a 1-dimensional list
    """
    return [item for sublist in t for item in sublist]


def map_list_to_list_of_lists(values):
    return [[value] for value in values]  # map(lambda x:[x], values)


def average_reduce(lst: List[float]) -> float:
    """
    more efficient calculation of the average value in list
    """
    return reduce(lambda a, b: a + b, lst) / len(lst)


def merge_intersecting_sets(sets: List[Set]) -> List[Set[int]]:
    """
    Given a list of sets: Merge sets based on intersections
    # https://stackoverflow.com/questions/9110837/python-simple-list-merging-based-on-intersections
    """
    merged = True
    while merged:
        merged = False
        results = []
        while sets:
            common, rest = sets[0], sets[1:]
            sets = []
            for x in rest:
                if x.isdisjoint(common):
                    sets.append(x)
                else:
                    merged = True
                    common |= x
            results.append(common)
        sets = results
    return sets
