from definitions import ROOT_DIR

TARGET_LOCATION = "Boston_Waltereit"
AREA = 'boston_test'

# Directories, were preprocessed and transformed data of Narain will be stored
PROCESSED_DIRECTORY = ROOT_DIR + "/data/Files/Sensors/Processed/" + AREA
DAROUTE_FORMAT_DIR = ROOT_DIR + "/data/Files/Sensors/DaRoute/" + AREA

AREA_TARGET_PATH = ROOT_DIR + '/data/target_maps/' + TARGET_LOCATION

LOG_TARGET_DIR = ROOT_DIR + "/waltereit_attack/test/logs/"
TEST_RESULT_TARGET_DIR = ROOT_DIR + "/waltereit_attack/test/results/"

TOP_RANK_MEDIUM = 10
TOP_RANK_HARD = 5
TOP_RANK = 1

PERCENTAGE_MATCH = 0.8
