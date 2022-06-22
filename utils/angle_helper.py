import logging
import math
from typing import List, Tuple

import geopy.distance
import numpy as np

log = logging.getLogger(__name__)


def calc_angle_change(gyro_z, time):
    """
    :param gyro_z: gyro-z axis value in radians
    :param time: time measured in milliseconds
    :return: changed angle between 0 and 360 degrees
    """
    # take the negative value of current gyro_z reading to "invert" it for correct geographical direction change
    # convert radians to degree and calculate the change with time in seconds
    return (-gyro_z * (180 / math.pi)) * (time / 1000)


def normalize_angle_in_interval(angle: float):
    """
    the given angle should be normalized into the interval ]0, 360[
    :param angle:
    :return:
    """
    while angle >= 360:
        angle = angle - 360
    while angle < 0:
        angle = angle + 360
    return angle


def __calc_angle_to_north(a, b, c):
    """
    Calculate angle between three points.
    https://medium.com/@manivannan_data/find-the-angle-between-three-points-from-2d-using-python-348c513e2cd
    """
    ang = math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0]))
    return ang + 360 if ang < 0 else ang


def calc_binary_direction_to_north(start_node, end_node):
    """
    Create a pseudo node that is "north" to the start_point to calculate the angle between start and end.
    :param start_node: the main point for whom a point to the north will be created
    :param end_node: the point used to calculate the angle to from north and start
    :return: a binary assignment of an angle
    """
    # get some point directly "above" of start_node to calculate direction
    north_point = (start_node[0] + 1, start_node[1])
    absolute_angle = __calc_angle_to_north(north_point, start_node, end_node)
    binary_angle = __get_binary_angle(absolute_angle)
    return binary_angle


def __get_binary_angle(degree):
    if 0 <= degree < 22.5:
        return 0
    elif 22.5 <= degree < 67.5:
        return 45
    elif 67.5 <= degree < 112.5:
        return 90
    elif 112.5 <= degree < 157.5:
        return 135
    elif 157.5 <= degree < 202.5:
        return 180
    elif 202.5 <= degree < 247.5:
        return 225
    elif 247.5 <= degree < 292.5:
        return 270
    elif 292.5 <= degree < 337.5:
        return 315
    elif 337.5 <= degree <= 360:
        return 0
    else:
        raise Exception("Invalid angle received. Convert angle to a value between 0 and 360.")


def get_binary_directions_with_tolerance(heading: float, error_tolerance: float) -> List[int]:
    """
    Calculate all possible binary compass directions after a turn considering the possible magnetometer error
    """
    compass_directions = [0, 45, 90, 135, 180, 225, 270, 315]

    # get all direction possibilities
    if error_tolerance >= 180:
        return compass_directions

    while heading < 0:
        heading += 360
    while heading > 360:
        heading -= 360

    lower_bound_degree = heading - error_tolerance
    if lower_bound_degree < 0:
        lower_bound_degree += 360
    upper_bound_degree = heading + error_tolerance
    if upper_bound_degree > 360:
        upper_bound_degree -= 360

    lower_bound_index = compass_directions.index(__get_binary_angle(lower_bound_degree))
    upper_bound_index = compass_directions.index(__get_binary_angle(upper_bound_degree))

    if lower_bound_index > upper_bound_index:
        # split up slicing, as lower_bound is higher then higher_bound, because values have to be in range of [0,360[
        return compass_directions[lower_bound_index:] + compass_directions[:upper_bound_index + 1]
    else:
        # inclusive upper bound
        return compass_directions[lower_bound_index:upper_bound_index + 1]


def get_main_angle(degree):
    if 0 <= degree < 45:
        return 0
    elif 45 <= degree < 135:
        return 90
    elif 135 <= degree < 225:
        return 180
    elif 225 <= degree < 315:
        return 270
    elif 135 <= degree <= 360:
        return 0
    else:
        return Exception("Invalid angle received. Convert angle to a value between 0 and 360.")


def calc_turn_angle(node_start, node_center, node_end):
    lat_lng_start = (node_start[0], node_start[1])
    lat_lng_center = (node_center[0], node_center[1])
    lat_lng_end = (node_end[0], node_end[1])

    dist_start_center = geopy.distance.distance(lat_lng_start, lat_lng_center).m
    dist_center_end = geopy.distance.distance(lat_lng_center, lat_lng_end).m
    dist_start_end = geopy.distance.distance(lat_lng_start, lat_lng_end).m

    z = (dist_start_center ** 2) + (dist_center_end ** 2) - (dist_start_end ** 2)
    n = 2 * dist_start_center * dist_center_end
    if not (1.000001 > z / n > -1.000001):
        log.warning("Potential floating point error detected! Assuming 0 degrees for points %s, %s, %s."
                    % (lat_lng_start, lat_lng_center, lat_lng_end))

    corner_degree = math.acos(max(min(z / n, 1), -1))

    corner_degree = 180 - math.degrees(corner_degree)
    corner_direction = __get_turn_direction(node_start, node_center, node_end)

    return corner_degree * corner_direction


def __get_turn_direction(node_start, node_center, node_end):
    # https://stackoverflow.com/a/22668810
    p_0 = (node_start[0], node_start[1])
    p_1 = (node_end[0], node_end[1])
    p_2 = (node_center[0], node_center[1])

    value = (p_1[0] - p_0[0]) * (p_2[1] - p_0[1]) - (p_2[0] - p_0[0]) * (p_1[1] - p_0[1])

    # Align direction with compass change due to angle
    if value > 0:  # right turn
        return -1
    elif value < 0:  # left turn
        return 1
    else:
        return 0


def get_intersect_from_two_lines(a1: Tuple[float, float], a2: Tuple[float, float],
                                 b1: Tuple[float, float], b2: Tuple[float, float]) -> Tuple[float, float]:
    """
    https://stackoverflow.com/questions/3252194/numpy-and-line-intersections
    Returns the point of intersection of the lines passing through a2,a1 and b2,b1.
    a1: [x, y] a point on the first line
    a2: [x, y] another point on the first line
    b1: [x, y] a point on the second line
    b2: [x, y] another point on the second line
    """
    s = np.vstack([a1, a2, b1, b2])  # s for stacked
    h = np.hstack((s, np.ones((4, 1))))  # h for homogeneous
    l1 = np.cross(h[0], h[1])  # get first line
    l2 = np.cross(h[2], h[3])  # get second line
    x, y, z = np.cross(l1, l2)  # point of intersection
    if z == 0:  # lines are parallel
        return float('inf'), float('inf')
    return x / z, y / z
