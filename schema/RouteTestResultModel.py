class RouteTestResultModel(object):
    def __init__(self,
                 test_id: str,
                 num_turns: int,
                 num_roundabouts: int,
                 total_distance: float,
                 num_traffic_lights: int,
                 num_candidates: int,
                 num_filtered: int,
                 rank_of_perfect_route: int,
                 rank_of_partical_route: int,
                 runtime_preprocess: float,
                 runtime_candidates: float,
                 runtime_ranking: float):
        self.test_id = test_id
        self.num_turns = num_turns
        self.num_roundabouts = num_roundabouts
        self.total_distance = total_distance
        self.num_traffic_lights = num_traffic_lights
        self.num_candidates = num_candidates
        self.num_filtered = num_filtered
        self.rank_of_perfect_route = rank_of_perfect_route
        self.rank_of_partial_route = rank_of_partical_route
        self.runtime_preprocess = runtime_preprocess
        self.runtime_candidates = runtime_candidates
        self.runtime_ranking = runtime_ranking

    def to_dict(self):
        return {
            'test_id': self.test_id,
            'num_turns': self.num_turns,
            'num_roundabouts': self.num_roundabouts,
            'total_distance': self.total_distance,
            'num_traffic_lights': self.num_traffic_lights,
            'num_candidates': self.num_candidates,
            'num_filtered': self.num_filtered,
            'rank_of_perfect_route': self.rank_of_perfect_route,
            'rank_of_partial_route': self.rank_of_partial_route,
            'runtime_preprocess': self.runtime_preprocess,
            'runtime_candidates': self.runtime_candidates,
            'runtime_ranking': self.runtime_ranking
        }
