class MeasurementModel(object):
    def __init__(self, gyro_z, acc_x, acc_y, direction, bridged_distance, distance_since_start, timestamp, speed):
        self.gyro_z = gyro_z
        self.acc_x = acc_x
        self.acc_y = acc_y
        self.direction = direction
        self.bridged_distance = bridged_distance
        self.distance_since_start = distance_since_start
        self.timestamp = timestamp
        self.speed = speed

    def to_dict(self):
        return {
            'gyro_z': self.gyro_z,
            'acc_x': self.acc_x,
            'acc_y': self.acc_y,
            'direction': self.direction,
            'distance': self.bridged_distance,
            'distance_since_start': self.distance_since_start,
            'timestamp': self.timestamp,
            'speed': self.speed
        }
