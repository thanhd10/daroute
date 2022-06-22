class TemporaryVersionTurn(object):
    """
    schema only temporary when discovering turn maneuvers live in the data preprocessing step
    """

    def __init__(self, direction_before: float, direction_after: float, angle: float, start_time: int, end_time: int):
        self.direction_before = direction_before
        self.direction_after = direction_after
        self.angle = angle
        self.start_time = start_time
        self.end_time = end_time

        self.estimated_intersection_time = (start_time + end_time) / 2


class TemporaryRoundabout(TemporaryVersionTurn):
    """
    schema only temporary when discovering roundabouts without aggregating them with sensor turns.
    Further details like driving direction and distances missing
    """

    def __init__(self, direction_before: float, direction_after: float, start_time: int, end_time: int):
        angle = direction_after - direction_before
        super().__init__(direction_before, direction_after, angle, start_time, end_time)


class TemporaryTrafficLight(object):
    def __init__(self, start_time: int, end_time: int):
        self.start_time = start_time
        self.end_time = end_time


class SensorTurnModel(object):
    """
    Final schema of a turn maneuver, extracted from sensor data.
    """

    def __init__(self, order: int, angle: float,
                 direction_after: float,
                 distance_before: float, distance_after: float,
                 estimated_intersection_time: int,
                 turn_start: int = None, turn_end: int = None,
                 # TODO fix order of attributes when updating test cases after implementing traffic lights
                 direction_before: float = None):
        self.order = order
        self.angle = angle
        if direction_before is None:
            self.direction_before = direction_after - angle
        else:
            self.direction_before = direction_before

        self.direction_after = direction_after
        self.distance_before = distance_before
        self.distance_after = distance_after
        self.estimated_intersection_time = estimated_intersection_time
        self.turn_start = turn_start
        self.turn_end = turn_end


class RoundaboutTurnModel(SensorTurnModel):
    def __init__(self, order: int, angle: float, direction_before: float,
                 direction_after: float, distance_before: float, distance_after: float,
                 estimated_intersection_time: int, turn_start: int = None,
                 turn_end: int = None):
        super().__init__(order, angle, direction_after, distance_before, distance_after, estimated_intersection_time,
                         turn_start, turn_end, direction_before)


class TrafficLightModel(object):
    def __init__(self, start_turn: int, end_turn: int, distance_after_start_turn: float, start_time: int,
                 end_time: int):
        self.start_turn = start_turn
        self.end_turn = end_turn
        self.distance_after_start_turn = distance_after_start_turn
        self.start_time = start_time
        self.end_time = end_time
