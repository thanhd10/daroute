import pickle
import csv
import os
import shutil
import pandas as pd

class FileUtils:

    @staticmethod
    def readCsv(csv_file, header=True, trunc_columns=[]):
        """
        Read the csv file and load into a list
        """

        raw_data = pd.read_csv(csv_file)
        raw_data.drop(raw_data.columns[trunc_columns], axis=1, inplace=True)
        return raw_data.values.tolist()

    @staticmethod
    def load(file_name):
        """
        Load pickle object from the file
        """
        # Load object
        with open(file_name, "rb") as fd:
            pickle_obj = pickle.load(fd)

        return pickle_obj

    @staticmethod
    def dump(pickle_obj, file_name):
        """
        Dump object to pickle file, also create required directories
        """
        # Get the directory name and create it if does not exist
        directory = os.path.dirname(file_name)
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Dump object to file
        with open(file_name, "wb") as fd:
            pickle.dump(pickle_obj, fd, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def makeDirs(directory):
        """
        Create a directory if it does not exist
        """
        if not os.path.exists(directory):
            os.makedirs(directory)

    @staticmethod
    def copy(source, destination):
        """
        Copy source file to destination
        """
        shutil.copy(source, destination)

    @staticmethod
    def allFiles(directory, file_filter=None):
        """
        Get the set of all files in the directory and save the ones that satisfy filter
        """
        files = set()
        # Obtain and iterate through all files in the directory
        for path_name, _, file_names in os.walk(directory):
            for file_name in file_names:
                # If this directory is an experimental one and the file name is in the file filter, add to set
                if "Sample_Route" in path_name and (file_filter is None or file_name in file_filter):
                    files.add(os.path.join(path_name, file_name))

        return sorted(list(files))

    @staticmethod
    def allDirectories(directory, file_filter=None):
        """
        Get the set of all the experimental directories in the directory
        """
        directories = set()
        # Obtain and iterate through all directories and files in the directory
        for path_name, _, file_names in os.walk(directory):
            for file_name in file_names:
                # If this directory is an experimental one and the file name is in the file filter, add directory to set
                if "Sample_Route" in path_name and (file_filter is None or file_name in file_filter):
                    directories.add(path_name)

        return sorted(list(directories))
