"""
General parameters about the creation of the database can be set here
"""

""" Parameters for Road Segment splitting """
# to estimate the first/last point of a segment, they should be x meters before a node of the
# road segment or rather x meters after a node of the road segment
THRESHOLD_DISTANCE_FOR_POINTS = 15.0
# avoid splitting Road segments directly before/after an intersection
MINIMUM_DISTANCE_FOR_SPLIT = 5

""" Parameters for turn angle calculation"""
# angles have to exceed this threshold to count as small angles on a segment
SMALL_ANGLE_THRESHOLD = 5.0
# nodes, that are too close to each other, are considered as the same for turn angle calculation
MIN_DISTANCE_OF_ADJACENT_NODES = 5.0
# if the distance in meters between the turning point and the start/end is larger this threshold,
# the turn maneuver might start/end here
MIN_DISTANCE_STRAIGHT_TRAVEL = 10.0

""" Parameters for turns over three segments"""
# road segments, that are smaller than this threshold are short road segments, were two successively following turns
# before and after the segment are too close to each other to be distincted as two turns
SHORT_SEGMENT_LENGTH_THRESHOLD = 30.0
SHORT_SEGMENT_TURN_THRESHOLD = 15.0
