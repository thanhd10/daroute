from multiprocessing import Pool

from utils.functions import flatten_list


class PartRoutesConnector(object):
    def __init__(self,
                 part_route_candidates: [[int]],
                 part_route_index: int):
        self.first_half_of_part_route_candidates = part_route_candidates[part_route_index]
        self.second_half_of_part_route_candidates = part_route_candidates[part_route_index + 1]

    def connect_part_route_candidates(self, turn_pair: [int]) -> [[int]]:
        """
        connect first part-routes with second part-routes by the current turn_pair
        :param turn_pair: two turns, where the last turn can be reached from the first turn
        :return: connected part-routes, that could be connected with the current turn_pair
        """

        current_routes = []
        # retrieve possible part-route-candidates by current turn_pair
        start_routes = [route for route in self.first_half_of_part_route_candidates if
                        route[-1] == turn_pair[0]]
        end_routes = [route for route in self.second_half_of_part_route_candidates if
                      route[0] == turn_pair[-1]]

        # connect retrieved part-route-candidates
        for start_route in start_routes:
            for end_route in end_routes:
                current_routes.append(start_route + end_route)

        return current_routes


def connect_part_routes(turn_pairs: [[int]], part_route_candidates: [[int]], part_route_index: int) -> [[int]]:
    """
    Parallelized Function to connect the given part_route_candidates at the 'part_route_index' and 'part_route_index+1'
    by the given turn_pairs, if these part_routes have a common turn_pair, i.e. are connectable.
    Method is defined as function and not part of the class PartRoutesConnector, as multiprocessing wouldn't work like
    that.
    :return: a list of further connected part_route_candidates, where the part_routes at the index 'part_route_index'
             and 'part_route_index + 1' where merged with each other
    """
    part_routes_connector = PartRoutesConnector(part_route_candidates, part_route_index)
    with Pool() as pool:
        connected_part_routes = pool.map(part_routes_connector.connect_part_route_candidates, turn_pairs)
    return flatten_list(connected_part_routes)
