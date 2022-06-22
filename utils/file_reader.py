import csv
import json

import pandas as pd


def read_osm_csv_files(ways_csv, nodes_csv, traffic_lights_csv):
    """
     Parameters should be file paths to csv files
     @:returns
        1. ways.csv read in as a list of tuples to efficiently iterate over instances,
        as iterating over a dataFrame is quiet slow
        2. nodes.csv read in as a dataFrame to use efficient and simple queries
        3. traffic_lights.csv read in as a dataFrame to use efficient and simple queries
    """
    return convert_csv_to_list(ways_csv), pd.read_csv(nodes_csv), pd.read_csv(traffic_lights_csv)


def convert_csv_to_list(csv_file):
    """
    :param csv_file: file_path to a csv file that should be parsed
    :return: a list of tuples where a tuple is a single row of the csv file
    """
    result = []
    with open(csv_file) as read_file:
        reader = csv.reader(read_file)
        for row in reader:
            result.append(row)
    read_file.close()
    # skip first row, as these only contain column names
    return result[1:]


def convert_json_to_iterator(json_file):
    """
    :param json_file: file_path to a json file that should be converted to an iterator
    :return: an iterator for the json file
    """
    with open(json_file) as json_file:
        json_object = json.load(json_file)
        json_file.close()
    return iter(json_object)
