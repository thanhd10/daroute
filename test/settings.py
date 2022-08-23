from definitions import ROOT_DIR

""" 
For Usage, set 
    a) the variable TARGET_LOCATION: the directory name, where the street network 
       was created with create_street_network.py
    b) the variable AREA: the directory name (no path), in which the data in DaRoute format is located
"""

TARGET_LOCATION = "Regensburg"
AREA = 'regensburg'
SAMPLES_DIRECTORY = ROOT_DIR + "/data/" + AREA

AREA_TARGET_PATH = ROOT_DIR + '/data/target_maps/' + TARGET_LOCATION

LOG_TARGET_DIR = ROOT_DIR + "/test/logs/"
TEST_RESULT_TARGET_DIR = ROOT_DIR + "/test/results/"

TOP_RANK_MEDIUM = 10
TOP_RANK_HARD = 5
TOP_RANK = 1

PERCENTAGE_MATCH = 0.8
