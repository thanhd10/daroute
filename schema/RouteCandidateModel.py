from attack_parameters import DISTANCE_WEIGHT, ANGLE_WEIGHT, HEADING_CHANGE_WEIGHT, TRAFFIC_LIGHT_WEIGHT, \
    CURVATURE_WEIGHT


class RouteCandidateModel(object):

    def __init__(self,
                 turn_ids: [int],
                 segment_ids: [int],
                 distance_score: float,
                 angle_score: float,
                 heading_change_score: float,
                 traffic_light_score: float,
                 curvature_score: float,
                 is_filtered_heading: bool = False,
                 is_filtered_traffic_light: bool = False,
                 heading_change_errors: [float] = [],
                 turn_angle_errors: [float] = []):
        self.turn_ids = turn_ids
        self.segment_ids = segment_ids

        self.distance_score = distance_score
        self.angle_score = angle_score
        self.heading_change_score = heading_change_score
        self.curvature_score = curvature_score
        self.traffic_light_score = traffic_light_score

        self.normalized_distance_score = 0
        self.normalized_angle_score = 0
        self.normalized_heading_change_score = 0
        self.normalized_curvature_score = 0

        self.is_filtered_heading = is_filtered_heading
        self.is_filtered_traffic_light = is_filtered_traffic_light

        # TODO remove again
        self.heading_change_errors = heading_change_errors
        self.turn_angle_errors = turn_angle_errors

    def calc_general_score(self) -> float:
        return DISTANCE_WEIGHT * self.distance_score + \
               ANGLE_WEIGHT * self.angle_score + \
               HEADING_CHANGE_WEIGHT * self.heading_change_score + \
               CURVATURE_WEIGHT * self.curvature_score + \
               TRAFFIC_LIGHT_WEIGHT * self.traffic_light_score

    def normalize_distance_score(self, x_min: float, x_max: float):
        self.normalized_distance_score = (self.distance_score - x_min) / (x_max - x_min)

    def normalize_angle_score(self, x_min: float, x_max: float):
        self.normalized_angle_score = (self.angle_score - x_min) / (x_max - x_min)

    def normalize_heading_change_score(self, x_min: float, x_max: float):
        self.normalized_heading_change_score = (self.heading_change_score - x_min) / (x_max - x_min)

    def normalize_curvature_score(self, x_min: float, x_max: float):
        self.normalized_curvature_score = (self.curvature_score - x_min) / (x_max - x_min)

    def calc_general_normalized_score(self) -> float:
        return DISTANCE_WEIGHT * self.normalized_distance_score + \
               ANGLE_WEIGHT * self.normalized_angle_score + \
               HEADING_CHANGE_WEIGHT * self.normalized_heading_change_score + \
               CURVATURE_WEIGHT * self.normalized_curvature_score + \
               TRAFFIC_LIGHT_WEIGHT * self.traffic_light_score  # Traffic Light score does not need normalization
