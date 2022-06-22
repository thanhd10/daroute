from os import path as Path

from numpy import dot, matrix

__author__ = 'sashank'


class SensorData:
    """
    This class represents attributes for columns of the sensor data
    """

    def __init__(self, system_time=0, x_axis=0., y_axis=0., z_axis=0., strength=0., bearing=0., magnitude=0.):
        self.system_time = system_time
        self.x_axis = x_axis
        self.y_axis = y_axis
        self.z_axis = z_axis
        self.strength = strength
        self.bearing = bearing
        self.magnitude = magnitude


class Sensors(object):
    """
    This class represents attributes and methods for storing all processed sensor data
    """

    def __init__(self, area, source_directory, output_directory, file_name):
        self.area = area
        self.source_file = Path.join(source_directory, file_name)
        self.output_directory = output_directory
        self.output_csv = Path.join(output_directory, file_name)

        self.num_idle = 0
        self.idle_mag = 0.

        self.current = []
        self.recorded = []
        self.calibrated = []
        self.rotated = []
        self.resampled = []

    def rotate(self, rotation_matrix):
        """
        Rotate the sensor data using the rotation matrix
        """
        # Iterate through all the SensorData objects
        for sensor in self.current:
            # Create a x, y and z axis matrix and multiply this with the rotation matrix
            rotated = dot(rotation_matrix, matrix([[sensor.x_axis], [sensor.y_axis], [sensor.z_axis]]))

            # Create a SensorData object for this rotated row and add to rotated list
            sensor_data = SensorData(system_time=sensor.system_time, x_axis=rotated.item(0), y_axis=rotated.item(1),
                                     z_axis=rotated.item(2), magnitude=sensor.magnitude)
            self.rotated.append(sensor_data)

        # Overwrite the current data to work with
        self.current = self.rotated
