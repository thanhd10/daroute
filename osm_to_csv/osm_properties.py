from random import randint

import geopy.distance


class Location(object):

    def __init__(self, lat, lng):
        self._lat = lat
        self._lng = lng

    @property
    def lat(self):
        return self._lat

    @property
    def lng(self):
        return self._lng


class Node(object):
    IDX = 0

    def __init__(self, osm_id, location):
        Node.IDX += 1
        self._location = location
        self._osm_id = osm_id
        self._unique_id = Node.IDX

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def osm_id(self):
        return self._osm_id

    @property
    def location(self):
        return self._location

    def __eq__(self, other):
        return isinstance(other, Node) and self.osm_id == other.osm_id

    def __hash__(self):
        return self.osm_id

    def __str__(self):
        return "Node(unique_id = {}, osm_id = {})".format(self.unique_id, self.osm_id)


class TrafficLight(Node):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        return isinstance(other, TrafficLight) and self.osm_id == other.osm_id

    def __str__(self):
        return "TrafficLight(unique_id = {}, osm_id = {})".format(self.unique_id, self.osm_id)


class Roundabout(object):

    def __init__(self, osm_id):
        self.osm_id = osm_id


class RoadWork(object):

    def __init__(self, osm_id):
        self.osm_id = osm_id


class Way(object):

    def __init__(self, way_id, way_name, nodes, speedlimit, oneway, type="default"):
        if way_id is None:
            way_id = randint(100000, 999999)
        # TODO might extract and move to osm_helper later, to edit speed_limit information
        try:
            int(speedlimit)
        except:
            speedlimit = -1

        if speedlimit is None or int(speedlimit) < 0:
            speedlimit = -1

        self._speedlimit = speedlimit
        self._nodes = nodes
        self._way_name = way_name
        self._way_id = way_id
        self._oneway = oneway
        self._type = type

        self._length = 0
        prev_node = self.nodes[0]
        for current_node in self.nodes[1:]:
            prev_node_loc = (prev_node.location.lat, prev_node.location.lng)
            current_node_loc = (current_node.location.lat, current_node.location.lng)
            self._length += geopy.distance.distance(prev_node_loc, current_node_loc).m
            prev_node = current_node

    @property
    def way_id(self):
        return self._way_id

    @property
    def name(self):
        return self._way_name

    @property
    def start_node(self):
        return self._nodes[0]

    @property
    def end_node(self):
        return self._nodes[-1]

    @property
    def nodes(self):
        return self._nodes

    @property
    def speedlimit(self):
        return self._speedlimit

    @property
    def oneway(self):
        return self._oneway

    @property
    def type(self):
        return self._type

    @property
    def length(self):
        return self._length

    def __eq__(self, other):
        return isinstance(other, Way) and self.way_id == other.way_id

    def __hash__(self):
        return self.way_id

    def __str__(self):
        return "Way(id={}, name={}, nodes={}, start_node={}, end_node={}, speedlimit={}, length={})".format(
            self.way_id, self.name, len(self.nodes), self.start_node, self.end_node, self.speedlimit, self.length
        )
