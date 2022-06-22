import logging
import os
import pickle
import timeit
import unittest
from datetime import datetime
from typing import List, Tuple

import pandas as pd

from definitions import ROOT_DIR, NODE_ID_COL_NAME, OSM_ID_COL_NAME
from narain_attack.sensor_data_processing.utils import FileUtils
from narain_attack.convert_from_narain_format import convert_from_narain_format
from schema.RouteTestResultModel import RouteTestResultModel
from schema.TestRouteModel import TestRouteModel
from schema.sensor_models import SensorTurnModel, TrafficLightModel, RoundaboutTurnModel
from sensor_analyze.preprocess_trip import SensorPreprocessor
from utils import log
from utils.eval_helper import create_osm_path, is_percentage_match, is_start_and_end_match, \
    create_osm_path_with_only_intersections
from waltereit_attack.attack.create_route_candidates import get_all_route_candidates
from waltereit_attack.attack.schema import RouteSectionModel, RouteSectionCandidateModel
from waltereit_attack.attack_parameters import IS_LEFT, IS_RIGHT, DISTANCE_ERROR_TOLERANCE, ROAD_WIDTH_THRESHOLD, \
    TURN_THRESHOLD, PENALTY_THRESHOLD

################################################################################################################
AREA_DIR = "Waltham_Waltereit"

AREA_SIMPLIFIED = AREA_DIR.replace("_Waltereit", "").lower()

TOP_RANK_MEDIUM = 10
TOP_RANK_HARD = 5
TOP_RANK = 1

PERCENTAGE_MATCH = 0.8

AREA_TARGET_PATH = ROOT_DIR + '/data/target_maps/' + AREA_DIR

LOG_TARGET_DIR = ROOT_DIR + "/waltereit_attack/test/logs/"
TEST_RESULT_TARGET_DIR = ROOT_DIR + "/waltereit_attack/test/results/"

CONVERTED_DATA_FORMAT_DIR = ROOT_DIR + "/narain_attack/Files/Sensors/Prepped_Format/" + AREA_SIMPLIFIED + "/"


################################################################################################################

class TestRouteCandidatesNarainData(unittest.TestCase):
    # Store all test results here
    test_results = []
    test_run_start = datetime.now().strftime('%d_%m_%Y_%H_%M')

    @classmethod
    def setUpClass(cls) -> None:
        super(TestRouteCandidatesNarainData, cls).setUpClass()

        # Load database information
        cls.turns_df = pd.read_csv(AREA_TARGET_PATH + "/db/turns_df.csv")
        cls.nodes_df = pd.read_csv(AREA_TARGET_PATH + "/csv/nodes.csv")
        cls.node_id_to_osm_id = cls.nodes_df.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
        cls.segments_df = pd.read_csv(AREA_TARGET_PATH + "/db/road_segments_df.csv")
        with open(AREA_TARGET_PATH + '/db/segment_to_osm_ids.pickle', 'rb') as dump_file:
            cls.segment_to_osm_path = pickle.load(dump_file)

        # Init logger
        log.setup(log_filename=LOG_TARGET_DIR + "test_routes_" + cls.test_run_start + ".log")
        cls.logger = logging.getLogger(__name__)

        # Parameters about database
        cls.logger.info("Area of test: %s" % AREA_DIR)
        cls.logger.info("Number of turn units in db = %d" % len(cls.turns_df))
        cls.logger.info("Number of road segments in db = %d" % len(cls.segment_to_osm_path.keys()))

        cls.logger.info('-' * 80)
        cls.logger.info("TURN_THRESHOLD = %.1f" % TURN_THRESHOLD)

        # attack parameters
        cls.logger.info("DISTANCE_ERROR_TOLERANCE = %.2f" % DISTANCE_ERROR_TOLERANCE)
        cls.logger.info("ROAD_WIDTH_THRESHOLD = %d " % ROAD_WIDTH_THRESHOLD)
        cls.logger.info("PENALTY THRESHOLD = %.2f" % PENALTY_THRESHOLD)

    @classmethod
    def tearDownClass(cls) -> None:
        all_results_df = pd.DataFrame.from_records([test_result.to_dict() for test_result in cls.test_results])
        all_results_df.to_csv(TEST_RESULT_TARGET_DIR + "test_results_" + cls.test_run_start + ".csv", index=False)

    def test_all_routes(self):
        processed_directory = "/home/tdinh/persistent/attack_sensor_route/narain_attack/Files/Sensors/Processed/" + AREA_SIMPLIFIED
        for directory in FileUtils.allDirectories(processed_directory, file_filter="Accelerometer.csv"):
            self.logger.info('-' * 80)
            test_route = create_next_test_route(self, directory)
            test_route_narain(self, self.turns_df, test_route)


def create_next_test_route(unit_test: TestRouteCandidatesNarainData, output_dir: str):
    # retrieve initial heading from idle phase of route
    if os.path.exists(output_dir + "/Start_Heading.txt"):
        with open(output_dir + "/Start_Heading.txt", "r") as f:
            initial_heading = int(f.readlines()[0])
    else:
        mag = pd.read_csv(output_dir + "/Magnetometer.csv")
        initial_heading = mag.iloc[50]['Heading']

    # extract route id
    string_route_id_start = output_dir.find("Sample_Route")
    string_route_id_end = output_dir.rfind("/")
    route_id = output_dir[string_route_id_start:string_route_id_end]

    # extract osm nodes as the ground truth
    osm_nodes = []
    with open(output_dir + "/OSM_Nodes.txt", "r") as fh:
        for line in fh.readlines()[1:]:
            start = line.find("('") + 2
            end = line.find("', '")
            osm_nodes.append(int(line[start:end]))

    unit_test.logger.info("Output dir: %s" % output_dir)
    unit_test.logger.info("Created TestRouteModel with heading = %.2f and osm_path=%s"
                          % (initial_heading, osm_nodes))

    return TestRouteModel(test_id=route_id,
                          prep_file_path=output_dir,
                          heading_start=initial_heading,
                          test_device="",
                          notes="",
                          new_sensor_turns=[],
                          traffic_lights=[],
                          osm_id_path=osm_nodes)


def map_sensor_turn_to_route_section(sensor_turn: SensorTurnModel):
    if sensor_turn.angle > 30:
        turn_type = IS_RIGHT
    elif sensor_turn.angle < -30:
        turn_type = IS_LEFT
    else:
        print("Invalid SensorTurnModel angle, might be a roundabout. Set to right turn, as route will not be detected")
        turn_type = IS_RIGHT

    return RouteSectionModel(d_before_star=sensor_turn.distance_before,
                             d_before=sensor_turn.distance_before,
                             d_after=sensor_turn.distance_after,
                             d_after_star=sensor_turn.distance_after,
                             turn_type=turn_type)


def test_route_narain(unit_test: TestRouteCandidatesNarainData,
                      turns_df: pd.DataFrame,
                      test_route: TestRouteModel):
    convert_from_narain_format(test_route.test_id, test_route.prep_file_path, CONVERTED_DATA_FORMAT_DIR)
    turn_sequence, traffic_light_sequence, measurements, duration_preprocess = run_sensor_preprocess(test_route)
    unit_test.logger.info("Start attack for %s with %d turns, %.2f meters and %d traffic lights:"
                          % (test_route.test_id, len(turn_sequence), get_total_distance(turn_sequence),
                             len(traffic_light_sequence)))

    route_candidates, duration_candidates = run_route_candidates_retrieval(unit_test,
                                                                           turns_df,
                                                                           turn_sequence)

    rank_of_perfect_route, rank_of_percentage_route, perfect_matching_results = run_evaluation(unit_test,
                                                                                               test_route,
                                                                                               route_candidates)

    unit_test.test_results.append(
        RouteTestResultModel(test_id=test_route.test_id,
                             num_turns=len(turn_sequence),
                             num_roundabouts=len([t for t in turn_sequence if isinstance(t, RoundaboutTurnModel)]),
                             total_distance=get_total_distance(turn_sequence),
                             num_traffic_lights=len(traffic_light_sequence),
                             num_candidates=len(route_candidates),
                             num_filtered=0,
                             rank_of_perfect_route=rank_of_perfect_route,
                             rank_of_partical_route=rank_of_percentage_route,
                             runtime_preprocess=-duration_preprocess,
                             runtime_candidates=duration_candidates,
                             runtime_ranking=-1))


def run_sensor_preprocess(test_route: TestRouteModel) -> Tuple[List[SensorTurnModel],
                                                               List[TrafficLightModel],
                                                               pd.DataFrame,
                                                               float]:
    start = timeit.default_timer()

    json_file_path = CONVERTED_DATA_FORMAT_DIR + test_route.test_id + ".json"
    sensor_preprocessor = SensorPreprocessor(json_file_path, test_route.heading_start)
    sensor_preprocessor.preprocess()

    measurements = sensor_preprocessor.get_measurements_as_trip_df()
    turn_sequence, traffic_light_sequence = sensor_preprocessor.get_sensor_turns_and_traffic_lights()

    end = timeit.default_timer()

    return turn_sequence, traffic_light_sequence, measurements, (end - start)


def run_route_candidates_retrieval(unit_test: TestRouteCandidatesNarainData,
                                   turns_df: pd.DataFrame,
                                   turn_sequence: [SensorTurnModel]) -> Tuple[List[RouteSectionCandidateModel],
                                                                              float]:
    # create route candidates
    start_time = timeit.default_timer()
    route_sections = [map_sensor_turn_to_route_section(sensor_turn) for sensor_turn in turn_sequence]
    route_candidates = get_all_route_candidates(route_sections, turns_df)
    end_time = timeit.default_timer()

    unit_test.logger.info("Found %d candidates in %.4f seconds." % (len(route_candidates), (end_time - start_time)))
    return route_candidates, (end_time - start_time)


def run_evaluation(unit_test: TestRouteCandidatesNarainData, test_route: TestRouteModel,
                   ranked_route_candidates: List[RouteSectionCandidateModel]) -> Tuple[int, int, List[bool]]:
    # 1. Convert Routes into Evaluation format and result and run check for perfect Top Ranking
    candidates_in_osm = [create_osm_path(route.segment_ids, unit_test.segment_to_osm_path) for route in
                         ranked_route_candidates]
    perfect_matching_results = [is_start_and_end_match(test_route.osm_id_path, candidate_path)
                                for candidate_path in candidates_in_osm]
    rank_of_perfect_route = get_route_ranking(unit_test, perfect_matching_results, is_perfect_match=True)

    is_start_correct = [route for route in candidates_in_osm if route[0] == test_route.osm_id_path[0]]
    is_end_correct = [route for route in candidates_in_osm if route[-1] == test_route.osm_id_path[-1]]

    unit_test.logger.info("Routes with correct start = %d" % len(is_start_correct))
    unit_test.logger.info("Routes with correct end = %d" % len(is_end_correct))

    # 2. Run check for percentage Top Ranking, by checking whether a similar route occurs earlier
    if rank_of_perfect_route != -1:
        # found the ground truth; check whether similar routes are higher ranked
        passed_intersections_osm = create_osm_path_with_only_intersections(
            ranked_route_candidates[perfect_matching_results.index(True)].segment_ids, unit_test.segment_to_osm_path)

        candidates_only_intersections = [
            create_osm_path_with_only_intersections(route.segment_ids, unit_test.segment_to_osm_path) for route in
            ranked_route_candidates]

        percentage_matching_results = [is_percentage_match(passed_intersections_osm, candidate_path, PERCENTAGE_MATCH)
                                       for candidate_path in candidates_only_intersections]
        rank_of_percentage_route = get_route_ranking(unit_test, percentage_matching_results, is_perfect_match=False)
    else:
        rank_of_percentage_route = -1
        unit_test.logger.info("No stored full osm path for this route available.")

    # return the corresponding ranks and the results for perfect matching
    return rank_of_perfect_route, rank_of_percentage_route, perfect_matching_results


def get_route_ranking(unit_test: TestRouteCandidatesNarainData, route_matching_results: [bool], is_perfect_match: bool):
    try:
        rank_position = route_matching_results.index(True) + 1
    except ValueError:
        rank_position = -1

    # log ranking results for either partial or perfect match
    if is_perfect_match:
        match_type = "Perfect match route"
    else:
        match_type = "Percentage match route"
    unit_test.logger.info("%s rank position = %d"
                          % (match_type, rank_position))
    unit_test.logger.info("%s within Top %d = %s"
                          % (match_type, TOP_RANK_MEDIUM, rank_position <= TOP_RANK_MEDIUM and rank_position != -1))

    return rank_position


def get_total_distance(turn_sequence: [SensorTurnModel]) -> float:
    # distance before first turn not considered
    # skipped last turn, as we don't consider distance after the last turn right now
    return sum([turn.distance_after for turn in turn_sequence[:-1]])


if __name__ == '__main__':
    unittest.main()
