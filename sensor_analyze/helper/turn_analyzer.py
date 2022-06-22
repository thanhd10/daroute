from _collections import deque
from typing import Tuple

import numpy as np

from attack_parameters import TURN_THRESHOLD

######################################################################

# angle needed, when current turn is recognized as "slow moving"
TURN_START_SLOW_MOVEMENT_THRESHOLD = 20
# angle needed for normal turn during a trip
TURN_START_THRESHOLD = TURN_THRESHOLD
# if vehicle is moving slower than this threshold in the time check window, start recognizing "slow turn"
DISTANCE_SLOW_MOVEMENT_THRESHOLD = 15.0

# time window to validate, if vehicle is driving straight again/finished turn
TIME_LEAVE_CORNER_CHECK = 1.5
# during a slow turn, angle has to be exceeded continuously to still be in turn
TURN_END_SLOW_MOVEMENT_THRESHOLD = 5
# during a normal turn, angle has to be exceeded continuously to still be in turn
TURN_END_THRESHOLD = 10
# min distance bridged during valdiation window
MIN_DISTANCE_FOR_CORNER_END = 3


######################################################################

class TurnCalculatorDistanceHeading(object):

    def __init__(self, time_window_angle_validation: float, frequency_measurements: float):
        self._frequency_measurements = frequency_measurements

        self._enter_corner_buffer_size = int(time_window_angle_validation * frequency_measurements)
        self._leave_corner_buffer_size = int(TIME_LEAVE_CORNER_CHECK * frequency_measurements)

        self._buffer_angle_change = deque([])
        self._buffer_distance = deque([])

        self._is_currently_left_turn = False
        self._is_currently_right_turn = False

        self._is_slowly_turning = False

    def __clear(self):
        num_elements_to_clear = len(self._buffer_angle_change) - self._leave_corner_buffer_size
        for i in range(num_elements_to_clear):
            self.__popleft()

    def __popleft(self):
        self._buffer_angle_change.popleft()
        self._buffer_distance.popleft()

    def __append(self, angle_change: float, distance: float):
        self._buffer_angle_change.append(angle_change)
        self._buffer_distance.append(distance)

    def add_measurement(self, angle_change: float, distance: float):
        self.__append(angle_change, distance)

        if len(self._buffer_angle_change) >= self._enter_corner_buffer_size and not (
                self._is_currently_left_turn or self._is_currently_right_turn):
            self.__popleft()

    def is_in_corner(self) -> bool:
        if self._is_currently_left_turn or self._is_currently_right_turn:
            return self.__is_still_in_corner()
        else:
            return self.__is_entering_corner()

    def __is_still_in_corner(self) -> bool:
        angle_change = np.sum(list(self._buffer_angle_change)[-self._leave_corner_buffer_size:])

        if self._is_slowly_turning:
            turn_end_thresh = TURN_END_SLOW_MOVEMENT_THRESHOLD
        else:
            turn_end_thresh = TURN_END_THRESHOLD

        # check if vehicle isn't driving straight
        if self._is_currently_right_turn and angle_change > turn_end_thresh:
            return True
        elif self._is_currently_left_turn and angle_change < -turn_end_thresh:
            return True
        else:
            # check movement of vehicle in turn; might stand still in turn e.g. waiting for pedestrians
            distance_bridged = np.sum(list(self._buffer_distance)[-self._leave_corner_buffer_size:])
            if distance_bridged > MIN_DISTANCE_FOR_CORNER_END:
                return False
            else:
                return True

    def __is_entering_corner(self) -> bool:
        angle_change = np.sum(list(self._buffer_angle_change))
        distance_bridged = np.sum(list(self._buffer_distance))

        # depending on speed the turn threshold is chosen
        if distance_bridged > DISTANCE_SLOW_MOVEMENT_THRESHOLD:
            start_turn_thresh = TURN_START_THRESHOLD
            self._is_slowly_turning = False
        else:
            start_turn_thresh = TURN_START_SLOW_MOVEMENT_THRESHOLD
            self._is_slowly_turning = True

        if angle_change > start_turn_thresh:
            self._is_currently_right_turn = True
            return True
        elif angle_change < -start_turn_thresh:
            self._is_currently_left_turn = True
            return True
        else:
            return False

    def calc_angle_and_clear_buffer(self) -> Tuple[float, float]:
        turn_angle = float(np.sum(self._buffer_angle_change))
        time_doing_turn = len(self._buffer_angle_change) / float(self._frequency_measurements)

        self.__clear()
        self._is_currently_right_turn = False
        self._is_currently_left_turn = False

        return turn_angle, time_doing_turn


class TurnCalculatorHeading(object):
    """
    Buffer the angle changes of the last x passed second and use a moving average to validate, if a given time window
    a turn was passed.
    """

    def __init__(self, time_window_angle_validation: float, frequency_measurements: int):
        # buffer size should have the number of measurements, that can be collected i a specific time frame
        self.buffer_size = int(time_window_angle_validation * frequency_measurements)
        self.frequency_measurements = frequency_measurements

        self.buffer_angle_change = deque([])
        # variable used to track, whether the buffers are currently in a turn to calculate exact angle of turn
        self.is_currently_left_turn = False
        self.is_currently_right_turn = False

    def __pop_left(self):
        self.buffer_angle_change.popleft()

    def __clear(self):
        self.buffer_angle_change.clear()

    def __append(self, angle_change: float):
        self.buffer_angle_change.append(angle_change)

    def add_measurement(self, angle_change: float, distance: float):
        self.__append(angle_change)
        if len(self.buffer_angle_change) >= self.buffer_size and not (
                self.is_currently_left_turn or self.is_currently_right_turn):
            self.__pop_left()

    def is_in_corner(self):
        # check the last x seconds for angle change
        angle_change = np.sum(list(self.buffer_angle_change)[-self.buffer_size:])
        # TODO might add special exit condition when in turn already and turn needs longer to finish

        if angle_change > TURN_THRESHOLD:
            self.is_currently_right_turn = True
            return True
        elif angle_change < -TURN_THRESHOLD:
            self.is_currently_left_turn = True
            return True
        else:
            return False

    def calc_angle_and_clear_buffer(self):
        # TODO differentiate between left and right turn values for angle calculation, as two successively
        #  following turns could negate each other
        angle = np.sum(self.buffer_angle_change)
        # calculate back the duration of doing the turn maneuver in ms with the number of elements in buffer
        time_doing_turn = (len(self.buffer_angle_change) / float(self.frequency_measurements)) * 1000
        self.__clear()
        self.is_currently_left_turn = False
        self.is_currently_right_turn = False
        return angle, time_doing_turn
