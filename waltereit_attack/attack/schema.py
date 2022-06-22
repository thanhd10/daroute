class RouteSectionModel(object):

    def __init__(self, d_before_star: float, d_before: float, turn_type: int, d_after: float, d_after_star: float):
        self.d_before_star = d_before_star
        self.d_before = d_before
        self.turn_type = turn_type
        self.d_after = d_after
        self.d_after_star = d_after_star


class RouteSectionCandidateModel(object):

    def __init__(self,
                 turn_indices: [int],
                 segment_ids: [int] = [],
                 distance_error: float = 0,
                 penalty: float = 0,
                 fn_counter: int = 0,
                 fp_counter: int = 0,
                 offset_left: float = 0,
                 offset_right: float = 0):
        self.turn_indices = turn_indices
        self.segment_ids = segment_ids

        self.distance_error = distance_error
        self.penalty = penalty

        self.fn_counter = fn_counter
        self.fp_counter = fp_counter

        self.offset_left = offset_left
        self.offset_right = offset_right



