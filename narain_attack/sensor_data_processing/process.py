import os

from tqdm import tqdm

from accelerometer import Accelerometer
from gyroscope import Gyroscope
from narain_attack.sensor_data_processing.utils import FileUtils
from narain_attack.settings import SAMPLES_DIRECTORY, PROCESSED_DIRECTORY, AREA

if __name__ == '__main__':

    # Iterate through all the paths directory in the samples directory that are not already processed
    for source_directory in tqdm(FileUtils.allDirectories(SAMPLES_DIRECTORY, file_filter="Accelerometer.csv"),
                                 "Rotate data"):
        # Create output directory name
        output_directory = source_directory.replace(SAMPLES_DIRECTORY, PROCESSED_DIRECTORY)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # Create an accelerometer object and load the csv file
        accelerometer = Accelerometer(AREA, source_directory, output_directory, "Accelerometer.csv")
        # Calculate the rotation matrix
        rotation_matrix = accelerometer.getRotationMatrix()
        # Rotate the accelerometer
        accelerometer.rotate(rotation_matrix)

        # Create a gyroscope object and load the csv file
        gyroscope = Gyroscope(AREA, source_directory, output_directory, "Gyroscope.csv")
        # Calibrate the gyroscope
        # gyroscope.calibrate()
        # Rotate the gyroscope
        gyroscope.rotate(rotation_matrix)

        accelerometer.csv()
        gyroscope.csv()

        from shutil import copyfile

        copyfile(source_directory + "/Locations.csv", output_directory + "/Locations.csv")
        copyfile(source_directory + "/OSM_Nodes.txt.txt", output_directory + "/OSM_Nodes.txt.txt")
        copyfile(source_directory + "/Magnetometer.csv", output_directory + "/Magnetometer.csv")
        if os.path.exists(source_directory + "/Start_Heading.txt.txt"):
            copyfile(source_directory + "/Start_Heading.txt.txt", output_directory + "/Start_Heading.txt.txt")
