import logging
import os
import pickle
import timeit
import unittest
from datetime import datetime
from typing import List, Tuple, Dict

import pandas as pd

from attack_parameters import TURN_THRESHOLD, STRAIGHT_DRIVE_THRESHOLD, TURN_ANGLE_ERROR_TOLERANCE, \
    DISTANCE_ERROR_TOLERANCE, MAGNETOMETER_DIRECTION_ERROR, ROAD_WIDTH_THRESHOLD, DISTANCE_WEIGHT, ANGLE_WEIGHT, \
    HEADING_CHANGE_WEIGHT, CURVATURE_WEIGHT, TRAFFIC_LIGHT_WEIGHT, TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT, \
    TRAFFIC_LIGHT_MAX_SPEED_LIMIT, MAX_HEADING_CHANGE_DEVIATION
from definitions import NODE_ID_COL_NAME, OSM_ID_COL_NAME
from narain_attack.convert_from_narain_format import convert_from_narain_format
from narain_attack.sensor_data_processing.utils import FileUtils
from narain_attack.settings import PROCESSED_DIRECTORY, DAROUTE_FORMAT_DIR, TEST_RESULT_TARGET_DIR, \
    LOG_TARGET_DIR, TARGET_LOCATION, AREA_TARGET_PATH
from schema.RouteCandidateModel import RouteCandidateModel
from schema.RouteTestResultModel import RouteTestResultModel
from schema.TestRouteModel import TestRouteModel
from schema.sensor_models import SensorTurnModel, TrafficLightModel, RoundaboutTurnModel
from sensor_analyze.preprocess_trip import SensorPreprocessor
from trajectory_attack.create_route_candidates import RouteCandidateCreator
from trajectory_attack.rank_route_candidates import get_ranked_route_candidates_with_filtered
from utils import log
from utils.test_utils import run_evaluation, get_total_distance


class TestRouteCandidatesNarainData(unittest.TestCase):
    # Store all test results here
    test_results = []
    test_run_start = datetime.now().strftime('%d_%m_%Y_%H_%M')

    @classmethod
    def setUpClass(cls) -> None:
        super(TestRouteCandidatesNarainData, cls).setUpClass()

        if not os.path.exists(LOG_TARGET_DIR):
            os.makedirs(LOG_TARGET_DIR)
        if not os.path.exists(TEST_RESULT_TARGET_DIR):
            os.makedirs(TEST_RESULT_TARGET_DIR)

        if not os.path.exists(DAROUTE_FORMAT_DIR):
            os.makedirs(DAROUTE_FORMAT_DIR)

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
        cls.logger.info("Area of test: %s" % TARGET_LOCATION)
        cls.logger.info("Number of turn units in db = %d" % len(cls.turns_df))
        cls.logger.info("Number of road segments in db = %d" % len(cls.segment_to_osm_path.keys()))

        cls.logger.info('-' * 80)
        cls.logger.info("TURN_THRESHOLD = %.1f" % TURN_THRESHOLD)
        cls.logger.info("STRAIGHT_DRIVE_THRESHOLD = %.1f" % STRAIGHT_DRIVE_THRESHOLD)

        # error parameters for turn pair matching
        cls.logger.info("TURN_ANGLE_ERROR_TOLERANCE = %d" % TURN_ANGLE_ERROR_TOLERANCE)
        cls.logger.info("DISTANCE_ERROR_TOLERANCE = %.2f" % DISTANCE_ERROR_TOLERANCE)
        cls.logger.info("MAGNETOMETER_DIRECTION_ERROR = %d" % MAGNETOMETER_DIRECTION_ERROR)
        cls.logger.info("ROAD_WIDTH_THRESHOLD = %d " % ROAD_WIDTH_THRESHOLD)

        # parameters for ranking and filtering
        cls.logger.info("DISTANCE_WEIGHT = %.2f" % DISTANCE_WEIGHT)
        cls.logger.info("ANGLE_WEIGHT = %.2f" % ANGLE_WEIGHT)
        cls.logger.info("HEADING_CHANGE_WEIGHT = %.2f" % HEADING_CHANGE_WEIGHT)
        cls.logger.info("CURVATURE_WEIGHT = %.2f" % CURVATURE_WEIGHT)
        cls.logger.info("TRAFFIC_LIGHT_WEIGHT = %.2f" % TRAFFIC_LIGHT_WEIGHT)
        cls.logger.info("TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT = %d" % TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT)
        cls.logger.info("TRAFFIC_LIGHT_MAX_SPEED_LIMIT = %d" % TRAFFIC_LIGHT_MAX_SPEED_LIMIT)
        cls.logger.info("MAX_HEADING_CHANGE_DEVIATION = %d" % MAX_HEADING_CHANGE_DEVIATION)

    @classmethod
    def tearDownClass(cls) -> None:
        all_results_df = pd.DataFrame.from_records([test_result.to_dict() for test_result in cls.test_results])
        all_results_df.to_csv(TEST_RESULT_TARGET_DIR + "test_results_" + cls.test_run_start + ".csv", index=False)

    def test_all_routes(self):
        if len(FileUtils.allDirectories(PROCESSED_DIRECTORY, file_filter="Accelerometer.csv")) == 0:
            raise Exception("Could not find any route in directory %s. "
                            "Did you forget to preprocess Narain data with "
                            "the script narain_attack/sensor_data_processing/process.py?"
                            "Or check file paths in narain_attack/settings.py."
                            % PROCESSED_DIRECTORY)

        for directory in FileUtils.allDirectories(PROCESSED_DIRECTORY, file_filter="Accelerometer.csv"):
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

    unit_test.logger.info("Created TestRouteModel %s with heading = %.2f and osm_path=%s"
                          % (output_dir, initial_heading, osm_nodes))

    return TestRouteModel(test_id=route_id,
                          prep_file_path=output_dir,
                          heading_start=initial_heading,
                          test_device="",
                          notes="",
                          new_sensor_turns=[],
                          traffic_lights=[],
                          osm_id_path=osm_nodes)


def test_route_narain(unit_test: TestRouteCandidatesNarainData,
                      turns_df: pd.DataFrame,
                      test_route: TestRouteModel):
    convert_from_narain_format(test_route.test_id, test_route.prep_file_path, DAROUTE_FORMAT_DIR + "/")
    turn_sequence, traffic_light_sequence, measurements, duration_preprocess = run_sensor_preprocess(test_route)
    unit_test.logger.info("Start attack for %s with %d turns, %.2f meters and %d traffic lights:"
                          % (test_route.test_id, len(turn_sequence), get_total_distance(turn_sequence),
                             len(traffic_light_sequence)))

    route_candidates, turn_pair_to_segment_route, duration_candidates = run_route_candidates_retrieval(unit_test,
                                                                                                       turns_df,
                                                                                                       turn_sequence)
    ranked_route_candidates, duration_ranking = run_route_candidates_ranking(unit_test,
                                                                             turns_df,
                                                                             turn_sequence,
                                                                             traffic_light_sequence,
                                                                             measurements,
                                                                             route_candidates,
                                                                             turn_pair_to_segment_route)

    rank_of_perfect_route, rank_of_percentage_route, perfect_matching_results = run_evaluation(unit_test,
                                                                                               test_route,
                                                                                               ranked_route_candidates)

    unit_test.test_results.append(
        RouteTestResultModel(test_id=test_route.test_id,
                             num_turns=len(turn_sequence),
                             num_roundabouts=len([t for t in turn_sequence if isinstance(t, RoundaboutTurnModel)]),
                             total_distance=get_total_distance(turn_sequence),
                             num_traffic_lights=len(traffic_light_sequence),
                             num_candidates=len(route_candidates),
                             num_filtered=len(route_candidates) - len(ranked_route_candidates),
                             rank_of_perfect_route=rank_of_perfect_route,
                             rank_of_partical_route=rank_of_percentage_route,
                             runtime_preprocess=-duration_preprocess,
                             runtime_candidates=duration_candidates,
                             runtime_ranking=duration_ranking))


def run_sensor_preprocess(test_route: TestRouteModel) -> Tuple[List[SensorTurnModel],
                                                               List[TrafficLightModel],
                                                               pd.DataFrame,
                                                               float]:
    start = timeit.default_timer()

    json_file_path = DAROUTE_FORMAT_DIR + "/" + test_route.test_id + ".json"
    sensor_preprocessor = SensorPreprocessor(json_file_path, test_route.heading_start)
    sensor_preprocessor.preprocess()

    measurements = sensor_preprocessor.get_measurements_as_trip_df()
    turn_sequence, traffic_light_sequence = sensor_preprocessor.get_sensor_turns_and_traffic_lights()

    end = timeit.default_timer()

    return turn_sequence, traffic_light_sequence, measurements, (end - start)


def run_route_candidates_retrieval(unit_test: TestRouteCandidatesNarainData,
                                   turns_df: pd.DataFrame,
                                   turn_sequence: [SensorTurnModel]) -> Tuple[List[RouteCandidateModel],
                                                                              Dict[Tuple[int, int], List[int]],
                                                                              float]:
    # create route candidates
    start_time = timeit.default_timer()
    route_candidates_creator = RouteCandidateCreator(turn_sequence, turns_df)
    route_candidates = route_candidates_creator.create_new_route_candidates()
    end_time = timeit.default_timer()

    unit_test.logger.info("Found %d candidates in %.4f seconds." % (len(route_candidates), (end_time - start_time)))
    return route_candidates, route_candidates_creator.turn_pair_to_segment_route, (end_time - start_time)


def run_route_candidates_ranking(unit_test: TestRouteCandidatesNarainData,
                                 turns_df: pd.DataFrame,
                                 turn_sequence: [SensorTurnModel],
                                 traffic_light_sequence: [TrafficLightModel],
                                 measurements: pd.DataFrame,
                                 route_candidates: [[int]],
                                 turn_pair_to_segment_route: Dict[Tuple[int, int], List[int]]
                                 ) -> Tuple[List[RouteCandidateModel], float]:
    # run ranking of candidate routes
    start_time = timeit.default_timer()
    ranked_route_candidates, candidates_with_filtered = get_ranked_route_candidates_with_filtered(
        route_candidates, turn_pair_to_segment_route, turn_sequence, traffic_light_sequence, measurements,
        turns_df, unit_test.segments_df)
    end_time = timeit.default_timer()

    unit_test.logger.info("Ranked routes in %.4f seconds." % (end_time - start_time))
    unit_test.logger.info("Filtered out %d routes" % (len(route_candidates) - len(ranked_route_candidates)))
    return ranked_route_candidates, (end_time - start_time)


if __name__ == '__main__':
    unittest.main()
