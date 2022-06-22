"""
General parameters about the attack to retrieve Routes can be set here
"""

# An angle at an intersection has to reach this threshold to be accepted as a turn
TURN_THRESHOLD = 30.0

# Threshold where an angle still counts as driving straight
STRAIGHT_DRIVE_THRESHOLD = 65.0
# Parameters for error tolerance in sensor data
TURN_ANGLE_ERROR_TOLERANCE = 80
# a percentage to calculate from a given distance to calculate the allowed distance error
DISTANCE_ERROR_TOLERANCE = 0.2
MAGNETOMETER_DIRECTION_ERROR = 90

# Threshold to include the width of the road, that is relevant especially for short distances between two turns,
# while also left turns might need more distance
ROAD_WIDTH_THRESHOLD = 50

# Ranking Function Weight Parameters
DISTANCE_WEIGHT = 1.2
ANGLE_WEIGHT = 0.5
HEADING_CHANGE_WEIGHT = 0.5
TRAFFIC_LIGHT_WEIGHT = 0.1
CURVATURE_WEIGHT = 1.0

# A vehicle doesn't always stand directly before a traffic light, hence this parameter defines, how far before a
# traffic light a vehicle might wait
TOLERANCE_STANDING_BEFORE_TRAFFIC_LIGHT = 150

# At a possible traffic light position this speed limit can't be exceeded, as traffic lights don't occur at this
# speed limit
TRAFFIC_LIGHT_MAX_SPEED_LIMIT = 100

# Filter Thresholds
MAX_HEADING_CHANGE_DEVIATION = 80
