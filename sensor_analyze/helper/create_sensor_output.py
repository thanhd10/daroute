from typing import Union

import pandas as pd

from schema.sensor_models import TemporaryRoundabout, TemporaryVersionTurn, SensorTurnModel, \
    RoundaboutTurnModel, TemporaryTrafficLight, TrafficLightModel


def create_all_path_sections(turn_sequence: [TemporaryVersionTurn], trip_df: pd.DataFrame) -> [SensorTurnModel]:
    """
    Convert a list of TemporaryVersionTurn to SensorTurn by adding information about distances between the turns
    """
    if len(turn_sequence) == 0:
        return []

    sensor_turns = []
    distance_before = float('inf')

    # calc distance between two turns at each iteration
    for i, (turn_a, turn_b) in enumerate(zip(turn_sequence[:-1], turn_sequence[1:])):
        distance_between_a_b = __get_distance_in_interval(trip_df, turn_a.estimated_intersection_time,
                                                          turn_b.estimated_intersection_time)

        sensor_turns.append(__create_path_section(is_roundabout=isinstance(turn_a, TemporaryRoundabout),
                                                  order=i,
                                                  angle=turn_a.angle,
                                                  direction_before=turn_a.direction_before,
                                                  direction_after=turn_a.direction_after,
                                                  distance_before=distance_before,
                                                  distance_after=distance_between_a_b,
                                                  estimated_intersection_time=int(turn_a.estimated_intersection_time),
                                                  turn_start=turn_a.start_time,
                                                  turn_end=turn_a.end_time))
        # update distance before for next following turn
        distance_before = distance_between_a_b

    # add the last turn
    turn_b = turn_sequence[-1]
    sensor_turns.append(__create_path_section(is_roundabout=isinstance(turn_b, TemporaryRoundabout),
                                              order=len(turn_sequence) - 1,
                                              angle=turn_b.angle,
                                              direction_before=turn_b.direction_before,
                                              direction_after=turn_b.direction_after,
                                              distance_before=distance_before,
                                              distance_after=float('inf'),
                                              estimated_intersection_time=turn_b.estimated_intersection_time,
                                              turn_start=turn_b.start_time,
                                              turn_end=turn_b.end_time))

    return sensor_turns


def __create_path_section(is_roundabout: bool, order: int, angle: float,
                          direction_before: float, direction_after: float,
                          distance_before: float, distance_after: float,
                          estimated_intersection_time: int,
                          turn_start: int, turn_end: int) -> Union[SensorTurnModel, RoundaboutTurnModel]:
    if is_roundabout:
        return RoundaboutTurnModel(order=order,
                                   angle=angle,
                                   direction_before=direction_before,
                                   direction_after=direction_after,
                                   distance_before=distance_before,
                                   distance_after=distance_after,
                                   estimated_intersection_time=estimated_intersection_time,
                                   turn_start=turn_start,
                                   turn_end=turn_end)
    else:
        return SensorTurnModel(order=order,
                               angle=angle,
                               direction_before=direction_before,
                               direction_after=direction_after,
                               distance_before=distance_before,
                               distance_after=distance_after,
                               estimated_intersection_time=estimated_intersection_time,
                               turn_start=turn_start,
                               turn_end=turn_end)


def __get_distance_in_interval(trip_df: pd.DataFrame, start, end) -> float:
    return trip_df[(trip_df['timestamp'] >= start) & (trip_df['timestamp'] <= end)].sum()['distance']


def create_traffic_lights(path_sections: [SensorTurnModel],
                          discovered_traffic_lights: [TemporaryTrafficLight],
                          trip_df: pd.DataFrame) -> [TrafficLightModel]:
    all_traffic_lights = []
    for traffic_light in discovered_traffic_lights:
        for turn_a, turn_b in zip(path_sections[:-1], path_sections[1:]):
            if turn_a.turn_start < traffic_light.start_time < turn_b.turn_end:
                distance_to_traffic_light = __get_distance_in_interval(trip_df,
                                                                       turn_a.estimated_intersection_time,
                                                                       traffic_light.start_time)
                all_traffic_lights.append(TrafficLightModel(start_turn=turn_a.order,
                                                            end_turn=turn_b.order,
                                                            distance_after_start_turn=distance_to_traffic_light,
                                                            start_time=traffic_light.start_time,
                                                            end_time=traffic_light.end_time))
                # created traffic light, iterate next one
                break

    return all_traffic_lights
