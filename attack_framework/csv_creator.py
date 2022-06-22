import logging
import os

from definitions import ROOT_DIR
from osm_to_csv.osm_handler import WayHandler, TrafficLightHandler, RoundaboutHandler
from utils import log

"""
Script to create csv-files out of "osm export files" that is exported from open street map. 
Set the variables DIR_NAME and OSM_FILE for usage.
"""
###########################################################################
# define path to the target directory where files should be stored
BASE_TARGET_DIR = ROOT_DIR + '/data/target_maps/'
CSV_DIR = '/csv'
IMAGE_DIR = '/image'
TURNS_DB_DIR = '/db'

# SET DIRECTORY NAME HERE
DIR_NAME = "Boston"
# SET OSM FILE TO PARSE HERE
OSM_FILE = ROOT_DIR + "/data/osm_exports/boston/streets.osm"

###########################################################################


if __name__ == '__main__':
    log.setup(log_filename=ROOT_DIR + "/osm_to_csv/csv_creator.log")
    log = logging.getLogger(__name__)

    # Create target dirs for csv and image files
    csv_target_dir = BASE_TARGET_DIR + DIR_NAME + CSV_DIR
    image_target_dir = BASE_TARGET_DIR + DIR_NAME + IMAGE_DIR
    db_target_dir = BASE_TARGET_DIR + DIR_NAME + TURNS_DB_DIR
    os.makedirs(csv_target_dir)
    os.makedirs(image_target_dir)
    os.makedirs(db_target_dir)

    # run parsing osm file to csv
    t = TrafficLightHandler(OSM_FILE, csv_target_dir, log)
    r = RoundaboutHandler(OSM_FILE, csv_target_dir, log)
    w = WayHandler(OSM_FILE, csv_target_dir, log)
