import math

from narain_attack.sensor_data_processing.constants import START_IDLE_TIME
from narain_attack.sensor_data_processing.utils import FileUtils
from sensor import Sensors, SensorData
import csv

__author__ = 'sashank'


class Gyroscope(Sensors):
    """
    This class represents attributes and methods specific to processing of gyroscope data
    """

    def __init__(self, area, source_directory, output_directory, file_name):
        # Call init of superclass
        super(Gyroscope, self).__init__(area, source_directory, output_directory, file_name)

        self.x_drift = 0.
        self.y_drift = 0.
        self.z_drift = 0.
        self.time_delta = 0

        # Load the gyroscope data
        self.__load()

    def __load(self):
        """
        Load the Gyroscope.csv file, iterate through all the rows, convert them to angles from rate and to save to our
        lists.
        """
        idle_time = START_IDLE_TIME

        # Initialize the cumulative angles
        x_angle, y_angle, z_angle = 0., 0., 0.
        # Read and iterate through all the rows of the csv file
        for row in FileUtils.readCsv(self.source_file, trunc_columns=[1, 2]):
            # If this is not the first row, convert the rates to angles
            if self.recorded:
                # Get the previous sensor value
                prev_row = self.recorded[-1]

                # Calculate the time delta between this and prev sensor (in seconds)
                time_delta = (int(row[0]) - prev_row.system_time) / 1000.
                # Calculate the new x, y and z angles using the rate and time delta
                x_angle = float(row[1])
                y_angle = float(row[2])
                z_angle = float(row[3])

            # Create a SensorData object for this row and add to recorded list
            sensor_data = SensorData(system_time=int(row[0]), x_axis=x_angle, y_axis=y_angle, z_axis=z_angle)
            self.recorded.append(sensor_data)

            # If time is less than idle time, count as idle
            if sensor_data.system_time < (idle_time * 1000):
                self.num_idle += 1

        # Overwrite the current data to work with
        self.current = self.recorded

    def calibrate(self):
        """
        Calibrate / reduce the gyroscope drift by calculating and subtracting the drift value
        """
        # Get the idle sensor objects
        first_idle = self.current[0]
        last_idle = self.current[self.num_idle - 1]

        # Calculate the x, y and z drift
        self.time_delta = last_idle.system_time - first_idle.system_time
        self.x_drift = (last_idle.x_axis - first_idle.x_axis) / self.time_delta
        self.y_drift = (last_idle.y_axis - first_idle.y_axis) / self.time_delta
        self.z_drift = (last_idle.z_axis - first_idle.z_axis) / self.time_delta

        # Iterate through all the recorded objects
        for sensor in self.current:
            # Cancel out the x, y and z drift value from this object
            time_delta = sensor.system_time - first_idle.system_time
            x_angle = sensor.x_axis - (self.x_drift * time_delta)
            y_angle = sensor.y_axis - (self.y_drift * time_delta)
            z_angle = sensor.z_axis - (self.z_drift * time_delta)

            # Create a SensorData object for this row and add to calibrated list
            sensor_data = SensorData(system_time=sensor.system_time, x_axis=x_angle, y_axis=y_angle, z_axis=z_angle)
            self.calibrated.append(sensor_data)

        # Overwrite the current data to work with
        self.current = self.calibrated

    def csv(self):
        """
        Write the resampled data to a csv file
        """
        with open(self.output_csv, "w") as fd:
            writer = csv.writer(fd)

            header = ['System Time','X Axis','Y Axis','Z Axis']
            writer.writerow(header)
            # Iterate through all the rotated data and save to file
            for sensor in self.rotated:
                line = [sensor.system_time, sensor.x_axis, sensor.y_axis, sensor.z_axis]
                writer.writerow(line)
