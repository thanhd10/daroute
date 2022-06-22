import csv
import math

from numpy import dot, matrix

from narain_attack.sensor_data_processing.constants import START_IDLE_TIME
from narain_attack.sensor_data_processing.utils import FileUtils
from sensor import Sensors, SensorData

__author__ = 'sashank'


class Accelerometer(Sensors):
    """
    This class represents attributes and methods specific to processing of accelerometer data
    """

    def __init__(self, area, source_directory, output_directory, file_name):
        # Call init of superclass
        super(Accelerometer, self).__init__(area, source_directory, output_directory, file_name)

        # Load the accelerometer data
        self.__load()

    def __load(self):
        """
        Load the Accelerometer.csv file, iterate through all the rows to save to our lists
        """
        idle_time = START_IDLE_TIME

        # Read and iterate through all the rows of the csv file
        for row in FileUtils.readCsv(self.source_file, trunc_columns=[1, 2]):
            # Calculate the magnitude
            mag = math.sqrt(float(row[1]) ** 2 + float(row[2]) ** 2 + float(row[3]) ** 2)

            # Create a SensorData object for this row and add to recorded list
            sensor_data = SensorData(system_time=int(row[0]), x_axis=float(row[1]), y_axis=float(row[2]),
                                     z_axis=float(row[3]), magnitude=mag)
            self.recorded.append(sensor_data)

            # If time is less than idle time, count as idle
            if sensor_data.system_time < (idle_time * 1000):
                self.num_idle += 1

        # Overwrite the current data to work with
        self.current = self.recorded

    def getRotationMatrix(self):
        """
        The function calculates the x and y tilt of the device and creates a rotation matrix from the x and y rotation
        angles. The final rotation matrix is a product of the individual rotation matrices.
        """
        # Initialize the sums (x and y axis and magnitude)
        x_sum, y_sum, mag_sum = 0., 0., 0.
        # Iterate through all the recorded objects
        for index, sensor in enumerate(self.current):
            # Break if the index reaches the number of required idle samples
            if index == self.num_idle:
                break
            # Add the x, y and magnitude values to the sums
            x_sum += sensor.x_axis
            y_sum += sensor.y_axis
            mag_sum += sensor.magnitude

        # Calculate the x, y and magnitude means
        x_mean = x_sum / (self.num_idle - 1)
        y_mean = y_sum / (self.num_idle - 1)
        self.idle_mag = mag_sum / (self.num_idle - 1)  # Save the mean of magnitude for future

        # Calculate the x and y rotation angles
        x_angle = math.asin(y_mean / self.idle_mag)
        y_angle = math.asin(x_mean / self.idle_mag)

        # Create the x and y rotation matrices
        x_matrix = matrix(
            [[1, 0, 0], [0, math.cos(x_angle), -math.sin(x_angle)], [0, math.sin(x_angle), math.cos(x_angle)]])
        y_matrix = matrix(
            [[math.cos(y_angle), 0, -math.sin(y_angle)], [0, 1, 0], [math.sin(y_angle), 0, math.cos(y_angle)]])

        # Multiply the 2 to obtain final rotation matrix
        return dot(x_matrix, y_matrix)

    def csv(self):
        """
        Write the resampled data to a csv file
        """
        with open(self.output_csv, "w") as fd:
            writer = csv.writer(fd)

            header = ['System Time', 'X Axis', 'Y Axis', 'Z Axis']
            writer.writerow(header)
            # Iterate through all the rotated data and save to file
            for sensor in self.rotated:
                line = [sensor.system_time, sensor.x_axis, sensor.y_axis, sensor.z_axis]
                writer.writerow(line)
