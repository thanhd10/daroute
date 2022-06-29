from definitions import ROOT_DIR

""" 
For Usage, set 
    a) the variable TARGET_LOCATION: the directory name, where the street network 
       was created with create_street_network.py
    b) the variable AREA: the directory name (no path), in which the raw Narain data 
       is located
    c) the variable SAMPLES_DIRECTORY: the path to raw Narain data
"""

TARGET_LOCATION = "Boston"
AREA = 'boston_test'
SAMPLES_DIRECTORY = ROOT_DIR + "/data/Files/Sensors/Samples/boston_test"

# Directories, were preprocessed and transformed data of Narain will be stored
PROCESSED_DIRECTORY = ROOT_DIR + "/data/Files/Sensors/Processed/" + AREA
DAROUTE_FORMAT_DIR = ROOT_DIR + "/data/Files/Sensors/DaRoute/" + AREA

AREA_TARGET_PATH = ROOT_DIR + '/data/target_maps/' + TARGET_LOCATION

LOG_TARGET_DIR = ROOT_DIR + "/narain_attack/test/logs/"
TEST_RESULT_TARGET_DIR = ROOT_DIR + "/narain_attack/test/results/"

TOP_RANK_MEDIUM = 10
TOP_RANK_HARD = 5
TOP_RANK = 1

PERCENTAGE_MATCH = 0.8
