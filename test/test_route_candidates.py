import logging
import pickle
import timeit
import unittest
from datetime import datetime
from typing import List, Tuple, Dict

import pandas as pd

import test.constants.test_routes_already_available as available_routes
import test.constants.test_routes_december as december_routes
import test.constants.test_routes_february as february_routes
import test.constants.test_routes_january as january_routes
import test.constants.test_routes_march as march_routes
import test.constants.test_routes_november as november_routes
import test.constants.test_routes_participants as participant_routes
from attack_parameters import TURN_THRESHOLD, STRAIGHT_DRIVE_THRESHOLD, TURN_ANGLE_ERROR_TOLERANCE, \
    DISTANCE_ERROR_TOLERANCE, MAGNETOMETER_DIRECTION_ERROR, DISTANCE_WEIGHT, ANGLE_WEIGHT, HEADING_CHANGE_WEIGHT, \
    MAX_HEADING_CHANGE_DEVIATION, TRAFFIC_LIGHT_WEIGHT, TRAFFIC_LIGHT_MAX_SPEED_LIMIT, \
    TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT, CURVATURE_WEIGHT, ROAD_WIDTH_THRESHOLD
from definitions import ROOT_DIR, NODE_ID_COL_NAME, OSM_ID_COL_NAME
from graph_preparation.database_parameters import SMALL_ANGLE_THRESHOLD, MIN_DISTANCE_STRAIGHT_TRAVEL, \
    MINIMUM_DISTANCE_FOR_SPLIT, THRESHOLD_DISTANCE_FOR_POINTS, \
    SHORT_SEGMENT_LENGTH_THRESHOLD, SHORT_SEGMENT_TURN_THRESHOLD
from schema.RouteCandidateModel import RouteCandidateModel
from schema.RouteTestResultModel import RouteTestResultModel
from schema.TestRouteModel import TestRouteModel
from schema.sensor_models import SensorTurnModel, TrafficLightModel, RoundaboutTurnModel
from sensor_analyze.preprocess_trip import SensorPreprocessor
from trajectory_attack.create_route_candidates import RouteCandidateCreator
from trajectory_attack.rank_route_candidates import get_ranked_route_candidates_with_filtered
from trajectory_attack.rank_route_candidates_distance import get_ranked_route_candidates_distance
from utils import log
from utils.eval_helper import create_osm_path, is_perfect_path_match, is_percentage_match, \
    create_osm_path_with_only_intersections

################################################################################################################
TEST_COMMENT = "Test attack with new routes."

AREA_DIR = "Q1_Regensburg"

IS_TEST_RAW_DATA_ACTIVATED = True

IS_ROUTE_DERIVATION_PAPER_ATTACK = False

TOP_RANK_MEDIUM = 10
TOP_RANK_HARD = 5
TOP_RANK = 1

PERCENTAGE_MATCH = 0.8

AREA_TARGET_PATH = ROOT_DIR + '/data/target_maps/' + AREA_DIR
LOG_TARGET_DIR = ROOT_DIR + "/test/logs/"
TEST_RESULT_TARGET_DIR = ROOT_DIR + "/test/results/"

CORRECT_ROUTE_CANDIDATE_DIR = ROOT_DIR + "/correct_route_candidates/"

COLUMN_CAST_DOWN_DICT = {'segment_start_id': 'int32', 'segment_target_id': 'int32', 'intersection_id': 'int32',
                         'angle': 'float32', 'end_direction': 'int16', 'distance_before': 'float32',
                         'distance_after': 'float32', 'start_lat': 'float32', 'start_lng': 'float32',
                         'intersection_lat': 'float32', 'intersection_lng': 'float32',
                         'end_lat': 'float32', 'end_lng': 'float32', 'heading_change': 'float32'}


################################################################################################################

# noinspection SpellCheckingInspection
class TestRouteCandidates(unittest.TestCase):
    # store statistics for each route
    test_results = []
    test_run_start = datetime.now().strftime('%d_%m_%Y_%H_%M')

    @classmethod
    def setUpClass(cls) -> None:
        super(TestRouteCandidates, cls).setUpClass()

        # Setup databases for given area
        cls.turns_df = pd.read_csv(AREA_TARGET_PATH + "/db/turns_df.csv").astype(COLUMN_CAST_DOWN_DICT)
        cls.nodes_df = pd.read_csv(AREA_TARGET_PATH + "/csv/nodes.csv")
        cls.node_id_to_osm_id = cls.nodes_df.set_index(NODE_ID_COL_NAME)[OSM_ID_COL_NAME].to_dict()
        cls.segments_df = pd.read_csv(AREA_TARGET_PATH + "/db/road_segments_df.csv")
        with open(AREA_TARGET_PATH + '/db/segment_to_osm_ids.pickle', 'rb') as dump_file:
            cls.segment_to_osm_path = pickle.load(dump_file)

        log.setup(log_filename=LOG_TARGET_DIR + "test_routes_" + cls.test_run_start + ".log")
        cls.logger = logging.getLogger(__name__)
        cls.logger.info(TEST_COMMENT)

        if IS_ROUTE_DERIVATION_PAPER_ATTACK:
            cls.logger.info("WARNING: RUN ROUTE DERIVATION PAPER ATTACK.")

        # Parameters about database
        cls.logger.info("Area of test: %s" % AREA_DIR)
        cls.logger.info("Number of turn units in db = %d" % len(cls.turns_df))
        cls.logger.info("Number of road segments in db = %d" % len(cls.segment_to_osm_path.keys()))
        cls.logger.info("Road Segments split with THRESHOLD_DISTANCE_FOR_POINTS = %d" % THRESHOLD_DISTANCE_FOR_POINTS)
        cls.logger.info("Road Segments split with MINIMUM_DISTANCE_SPLIT = %d" % MINIMUM_DISTANCE_FOR_SPLIT)
        cls.logger.info("SMALL_ANGLE_THRESHOLD = %d" % SMALL_ANGLE_THRESHOLD)
        cls.logger.info("MIN_DISTANCE_STRAIGHT_TRAVEL = %d" % MIN_DISTANCE_STRAIGHT_TRAVEL)
        cls.logger.info("SHORT_SEGMENT_LENGTH_THRESHOLD = %d" % SHORT_SEGMENT_LENGTH_THRESHOLD)
        cls.logger.info("SHORT_SEGMENT_TURN_THRESHOLD = %d" % SHORT_SEGMENT_TURN_THRESHOLD)

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

    def test_route_n1(self):
        test_route_in_given_map(self, self.turns_df, november_routes.TEST_ROUTE_N1)

    def test_route_n2(self):
        test_route_in_given_map(self, self.turns_df, november_routes.TEST_ROUTE_N2)

    def test_route_n3(self):
        test_route_in_given_map(self, self.turns_df, november_routes.TEST_ROUTE_N3)

    def test_route_n4(self):
        test_route_in_given_map(self, self.turns_df, november_routes.TEST_ROUTE_N4)

    ###################################################################################################################

    def test_route_d1(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D1)

    def test_route_d2(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D2)

    def test_route_d3(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D3)

    def test_route_d4(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D4)

    def test_route_d5(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D5)

    def test_route_d6(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D6)

    def test_route_d7(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D7)

    def test_route_d8(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D8)

    def test_route_d9(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D9)

    def test_route_d10(self):
        test_route_in_given_map(self, self.turns_df, december_routes.TEST_ROUTE_D10)

    ###################################################################################################################

    def test_routes_j1(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J1)

    def test_routes_j2(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J2)

    def test_routes_j3(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J3)

    def test_routes_j4(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J4)

    def test_routes_j5(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J5)

    def test_routes_j6(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J6)

    def test_routes_j7(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J7)

    def test_routes_j8(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J8)

    def test_routes_j9(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J9)

    def test_routes_j10(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J10)

    def test_routes_j11(self):
        test_route_in_given_map(self, self.turns_df, january_routes.TEST_ROUTE_J11)

    ###################################################################################################################

    def test_routes_f1(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F1)

    def test_routes_f2(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F2)

    def test_routes_f3(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F3)

    def test_routes_f4(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F4)

    def test_routes_f5(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F5)

    def test_routes_f6(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F6)

    def test_routes_f7(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F7)

    def test_routes_f8(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F8)

    def test_routes_f9(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F9)

    def test_routes_f10(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F10)

    def test_routes_f11(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F11)

    def test_routes_f12(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F12)

    def test_routes_f13(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F13)

    def test_routes_f14(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F14)

    def test_routes_f15(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F15)

    def test_routes_f16(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F16)

    def test_routes_f17(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F17)

    def test_routes_f18(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F18)

    def test_routes_f19(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F19)

    def test_routes_f20(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F20)

    def test_routes_f21(self):
        test_route_in_given_map(self, self.turns_df, february_routes.TEST_ROUTE_F21)

    ###################################################################################################################

    def test_route_m1(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M1)

    def test_route_m2(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M2)

    def test_route_m3(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M3)

    def test_route_m4(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M4)

    def test_route_m5(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M5)

    def test_route_m6(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M6)

    def test_route_m7(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M7)

    def test_route_m8(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M8)

    def test_route_m9(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M9)

    def test_route_m10(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M10)

    def test_route_m11(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M11)

    def test_route_m12(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M12)

    def test_route_m13(self):
        test_route_in_given_map(self, self.turns_df, march_routes.TEST_ROUTE_M13)

    ###################################################################################################################

    def test_route_a1(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A1)

    def test_route_a2(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A2)

    def test_route_a3(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A3)

    def test_route_a4(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A4)

    def test_route_a5(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A5)

    def test_route_a6(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A6)

    def test_route_a7(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A7)

    def test_route_a8(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A8)

    def test_route_a9(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A9)

    def test_route_a10(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A10)

    def test_route_a11(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A11)

    def test_route_a12(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A12)

    def test_route_a13(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A13)

    def test_route_a14(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A14)

    def test_route_a15(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A15)

    def test_route_a16(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A16)

    def test_route_a17(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A17)

    def test_route_a18(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A18)

    def test_route_a19(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A19)

    def test_route_a20(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A20)

    def test_route_a21(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A21)

    def test_route_a22(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A22)

    def test_route_a23(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A23)

    def test_route_a24(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A24)

    def test_route_a25(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A25)

    def test_route_a26(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A26)

    def test_route_a27(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A27)

    def test_route_a28(self):
        test_route_in_given_map(self, self.turns_df, available_routes.TEST_ROUTE_A28)

    ###################################################################################################################

    def test_route_pa1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PA1)

    def test_route_pa2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PA2)

    def test_route_pa3(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PA3)

    def test_route_pa4(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PA4)

    def test_route_pa5(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PA5)

    def test_route_pa6(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PA6)

    ###################################################################################################################

    def test_route_pf1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF1)

    def test_route_pf2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF2)

    def test_route_pf3(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF3)

    def test_route_pf4(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF4)

    def test_route_pf5(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF5)

    def test_route_pf6(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF6)

    def test_route_pf7(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF7)

    def test_route_pf8(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF8)

    def test_route_pf9(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF9)

    def test_route_pf10(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF10)

    def test_route_pf11(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF11)

    def test_route_pf12(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PF12)

    ###################################################################################################################

    def test_route_pm1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM1)

    def test_route_pm2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM2)

    def test_route_pm3(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM3)

    def test_route_pm4(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM4)

    def test_route_pm5(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM5)

    def test_route_pm6(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM6)

    def test_route_pm7(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM7)

    def test_route_pm8(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM8)

    def test_route_pm9(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM9)

    def test_route_pm10(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM10)

    def test_route_pm11(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM11)

    def test_route_pm12(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM12)

    def test_route_pm13(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM13)

    def test_route_pm14(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM14)

    def test_route_pm15(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PM15)

    ###################################################################################################################

    def test_route_pb1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PB1)

    def test_route_pb2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PB2)

    ###################################################################################################################

    def test_route_pj1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ1)

    def test_route_pj2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ2)

    def test_route_pj3(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ3)

    def test_route_pj4(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ4)

    def test_route_pj5(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ5)

    def test_route_pj6(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ6)

    def test_route_pj7(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ7)

    def test_route_pj8(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ8)

    def test_route_pj9(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJ9)

    ###################################################################################################################

    def test_route_pjh1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJH1)

    def test_route_pjh2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJH2)

    def test_route_pjh3(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJH3)

    def test_route_pjh4(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJH4)

    def test_route_pjh5(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJH5)

    def test_route_pjh6(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PJH6)

    ###################################################################################################################

    def test_route_pak1(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PAK1)

    def test_route_pak2(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PAK2)

    def test_route_pak3(self):
        test_route_in_given_map(self, self.turns_df, participant_routes.TEST_ROUTE_PAK3)


def get_total_distance(turn_sequence: [SensorTurnModel]) -> float:
    # distance before first turn not considered
    # skipped last turn, as we don't consider distance after the last turn right now
    return sum([turn.distance_after for turn in turn_sequence[:-1]])


def run_sensor_preprocess(test_route: TestRouteModel) -> Tuple[List[SensorTurnModel],
                                                               List[TrafficLightModel],
                                                               pd.DataFrame,
                                                               float]:
    """
    Two options are available to retrieve the test input:
    1. Parsing the raw data file for the current test route and returning the output.
    2. Returning the default values in the test_route previously extracted from the preprocessing step.
    :return: - a sequence of turns
             - a sequence of traffic lights
             - a dataFrame containing all measurements with additional values of the route
    """
    start = timeit.default_timer()
    if IS_TEST_RAW_DATA_ACTIVATED:
        # run the sensor preproessor
        json_file_path = ROOT_DIR + "/data/prep_trips/" + test_route.test_id + ".json"
        sensor_preprocessor = SensorPreprocessor(json_file_path, test_route.heading_start)
        sensor_preprocessor.preprocess()
        # receive the output of the preprocessing step and return it
        measurements = sensor_preprocessor.get_measurements_as_trip_df()
        turns, traffic_lights = sensor_preprocessor.get_sensor_turns_and_traffic_lights()
        end = timeit.default_timer()
        return turns, traffic_lights, measurements, (end - start)
    else:
        measurements_file_path = ROOT_DIR + "/test/measurements/Measurements_" + test_route.test_id + ".csv"
        trip_df = pd.read_csv(measurements_file_path)
        end = timeit.default_timer()
        return test_route.new_sensor_turns, test_route.traffic_lights, trip_df, (end - start)


def run_route_candidates_retrieval(unit_test: TestRouteCandidates,
                                   turns_df: pd.DataFrame,
                                   turn_sequence: [SensorTurnModel]) -> Tuple[List[RouteCandidateModel],
                                                                              Dict[Tuple[int, int], List[int]],
                                                                              float]:
    """
    1. Create all route candidates and log result number
    @:return a) a list of route candidates each consisting of a sequence of turn ids
             b) turn pair to segments dict
             c) time duration to run this step
    """
    # create route candidates
    start_time = timeit.default_timer()
    route_candidates_creator = RouteCandidateCreator(turn_sequence, turns_df)
    route_candidates = route_candidates_creator.create_new_route_candidates()
    end_time = timeit.default_timer()
    unit_test.logger.info("Found %d candidates in %.4f seconds." % (len(route_candidates), (end_time - start_time)))

    return route_candidates, route_candidates_creator.turn_pair_to_segment_route, (end_time - start_time)


def run_route_candidates_ranking(unit_test: TestRouteCandidates,
                                 turns_df: pd.DataFrame,
                                 turn_sequence: [SensorTurnModel],
                                 traffic_light_sequence: [TrafficLightModel],
                                 measurements: pd.DataFrame,
                                 route_candidates: [[int]],
                                 turn_pair_to_segment_route: Dict[Tuple[int, int], List[int]]
                                 ) -> Tuple[List[RouteCandidateModel], float]:
    start_time = timeit.default_timer()
    ranked_route_candidates, candidates_with_filtered = get_ranked_route_candidates_with_filtered(
        route_candidates, turn_pair_to_segment_route, turn_sequence, traffic_light_sequence, measurements,
        turns_df, unit_test.segments_df)
    end_time = timeit.default_timer()

    # TODO log if ground truth is filtered out
    unit_test.logger.info("Filtered %d routes with traffic lights."
                          % len([route for route in candidates_with_filtered if route.is_filtered_traffic_light]))
    unit_test.logger.info("Filtered %d routes with no-turn heading."
                          % len([route for route in candidates_with_filtered if route.is_filtered_heading]))
    unit_test.logger.info("Ranked routes in %.4f seconds." % (end_time - start_time))
    unit_test.logger.info("Filtered out %d routes" % (len(route_candidates) - len(ranked_route_candidates)))

    return ranked_route_candidates, (end_time - start_time)


def run_route_candidate_route_derivation_paper(unit_test: TestRouteCandidates,
                                               turn_sequence: [SensorTurnModel],
                                               route_candidates: [[int]],
                                               turn_pair_to_segment_route: Dict[Tuple[int, int], List[int]]
                                               ) -> Tuple[List[RouteCandidateModel], float]:
    start_time = timeit.default_timer()
    ranked_route_candidates = get_ranked_route_candidates_distance(
        route_candidates, turn_pair_to_segment_route, turn_sequence, unit_test.segments_df)
    end_time = timeit.default_timer()

    unit_test.logger.info("Ranked routes in %.4f seconds." % (end_time - start_time))

    return ranked_route_candidates, (end_time - start_time)


def get_route_ranking(unit_test: TestRouteCandidates, route_matching_results: [bool], is_perfect_match: bool):
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
    unit_test.logger.info("%s within Top %d = %s"
                          % (match_type, TOP_RANK_HARD, rank_position <= TOP_RANK_HARD and rank_position != -1))
    unit_test.logger.info("%s within Top %d = %s"
                          % (match_type, TOP_RANK, rank_position == TOP_RANK and rank_position != -1))

    return rank_position


def run_evaluation(unit_test: TestRouteCandidates, test_route: TestRouteModel,
                   ranked_route_candidates: List[RouteCandidateModel]) -> Tuple[int, int, List[bool]]:
    # 1. Convert Routes into Evaluation format and result and run check for perfect Top Ranking
    candidates_in_osm = [create_osm_path(route.segment_ids, unit_test.segment_to_osm_path) for route in
                         ranked_route_candidates]
    perfect_matching_results = [is_perfect_path_match(test_route.osm_id_path, candidate_path)
                                for candidate_path in candidates_in_osm]
    rank_of_perfect_route = get_route_ranking(unit_test, perfect_matching_results, is_perfect_match=True)

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

        # ADDITIONALLY store the ground truth route candidate for evaluation purposes
        with open(CORRECT_ROUTE_CANDIDATE_DIR + "Candidate_%s.pickle" % test_route.test_id, 'wb') as dump_file:
            pickle.dump(ranked_route_candidates[perfect_matching_results.index(True)], dump_file)
    else:
        rank_of_percentage_route = -1
        unit_test.logger.info("No stored full osm path for this route available.")

    # return the corresponding ranks and the results for perfect matching
    return rank_of_perfect_route, rank_of_percentage_route, perfect_matching_results


def test_route_in_given_map(unit_test: TestRouteCandidates, turns_df: pd.DataFrame, test_route: TestRouteModel):
    # Run Sensor Data Preprocessing step
    turn_sequence, traffic_light_sequence, measurements, duration_preprocess = run_sensor_preprocess(test_route)
    unit_test.logger.info('-' * 80)
    unit_test.logger.info("Start attack for %s with %d turns, %.2f meters and %d traffic lights:"
                          % (test_route.test_id, len(turn_sequence), get_total_distance(turn_sequence),
                             len(traffic_light_sequence)))

    # Run Attack
    route_candidates, turn_pair_to_segment_route, duration_candidates = run_route_candidates_retrieval(unit_test,
                                                                                                       turns_df,
                                                                                                       turn_sequence)
    if IS_ROUTE_DERIVATION_PAPER_ATTACK:
        ranked_route_candidates, duration_ranking = run_route_candidate_route_derivation_paper(unit_test,
                                                                                               turn_sequence,
                                                                                               route_candidates,
                                                                                               turn_pair_to_segment_route)
    else:
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
                             runtime_preprocess=duration_preprocess,
                             runtime_candidates=duration_candidates,
                             runtime_ranking=duration_ranking))
    # Run Unit-Test
    unit_test.assertTrue(any(perfect_matching_results), test_route.notes)


if __name__ == '__main__':
    unittest.main()
