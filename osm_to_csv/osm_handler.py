import csv
import os

import osmium
from tqdm import tqdm

from osm_to_csv import osm_helper
from osm_to_csv.osm_properties import TrafficLight, Way, Node, Location, Roundabout, RoadWork

###########################################################################
WAYS_CSV_NAME = 'ways.csv'
WAYS_TYPE_NAME = 'LEADS_TO'
NODES_CSV_NAME = 'nodes.csv'
WAY_PROGRESS = 500

TRAFFIC_LIGHT_CSV_NAME = 'traffic_lights.csv'

NODE_TRAFFIC_LIGHT_TAG_KEY = 'highway'
NODE_TRAFFIC_LIGHT_TAG_VALUE = 'traffic_signals'

ROUNDABOUT_CSV_NAME = 'roundabouts.csv'

WAY_ROUNDABOUT_TAG_KEY = 'junction'
WAY_ROUNDABOUT_TAG_VALUE = 'roundabout'

ROAD_WORK_CSV_NAME = 'road_works.csv'

WAY_ROAD_WORK_TAG_KEY = 'highway'
WAY_ROAD_WORK_TAG_VALUE = 'construction'


###########################################################################


class NodeMonitor(object):

    def __init__(self):
        self._nodes = {}
        self._seen_nodes = {}
        self._marked_nodes = {}

    def occurrence(self, node):
        osm_id = node.osm_id

        if osm_id not in self._nodes:
            self._seen_nodes[osm_id] = 0
            self._nodes[osm_id] = node

        self._seen_nodes[osm_id] += 1

    def mark(self, node):
        unique_id = node.unique_id

        if unique_id in self._marked_nodes:
            return False
        else:
            self._marked_nodes[unique_id] = True
            return True

    def __getitem__(self, osm_id):
        if osm_id in self._nodes:
            return self._nodes[osm_id]
        else:
            return None

    def is_intersection(self, node):
        osm_id = node.osm_id

        return osm_id in self._seen_nodes and self._seen_nodes[osm_id] > 1


class WayHandler(osmium.SimpleHandler):

    def __init__(self, filename, output_dir, log):
        super(WayHandler, self).__init__()
        self.log = log
        self.ways_processed = 0
        self.node_monitor = NodeMonitor()
        self._ways = []
        self._output_dir = output_dir

        self.log.info(f"Output directory: {self._output_dir}")
        self.log.info(f"Input file: {filename}")

        print(f"Reading ways from {filename}")
        self.apply_file(filename, locations=True, idx='sparse_mem_array')

        self.log.info(f"Found {len(self.ways)} ways")

        self.write_csv()

    @property
    def ways(self):
        return self._ways

    def way(self, way):
        self.ways_processed += 1
        if not osm_helper.is_street(way): return

        way_id = way.id
        way_name = osm_helper.get_name_from_way(way)
        way_speedlimit = osm_helper.get_tag(way, "maxspeed")
        way_oneway = osm_helper.is_oneway(way)

        node_objs = []

        for i, node in enumerate(way.nodes):
            existing_node = self.node_monitor[node.ref]
            if existing_node is None:
                osm_id = node.ref
                node_location = Location(lat=node.location.lat, lng=node.location.lon)
                existing_node = Node(osm_id, node_location)

            node_objs.append(existing_node)
            self.node_monitor.occurrence(existing_node)

        way_obj = Way(way_id, way_name, node_objs, way_speedlimit, way_oneway)
        self._ways.append(way_obj)

        if not len(self._ways) % WAY_PROGRESS:
            print('-', end='')
            if not len(self._ways) % (WAY_PROGRESS * 100):
                print("")

    def write_csv(self):
        if not os.path.exists(self._output_dir):
            os.mkdir(self._output_dir)

        ways = self._ways
        nodes = set()
        for way in ways:
            for node in way.nodes:
                nodes.add(node)

        way_csv_file = open(os.path.join(self._output_dir, WAYS_CSV_NAME), 'w', encoding='utf-8', newline="")
        nodes_csv_file = open(os.path.join(self._output_dir, NODES_CSV_NAME), 'w', encoding='utf-8', newline="")

        self.__way_csv = csv.writer(way_csv_file, doublequote=False, escapechar='\\')
        self.__nodes_csv = csv.writer(nodes_csv_file, doublequote=False, escapechar='\\')

        self.__way_csv.writerow(
            [':START_ID', ':END_ID', ':TYPE', 'distance:string', 'aggregated_distance:double', 'name:string',
             'type:string', 'speedlimit:int', 'osm_id:string'])
        self.__nodes_csv.writerow(['node_id:ID', 'osm_id:string', ':LABEL', 'lat:float', 'lng:float'])

        for node in tqdm(nodes, unit="node", desc="Creating nodes"):
            if self.node_monitor.mark(node):
                intersection_label = "INTERSECTION" if self.node_monitor.is_intersection(node) else "CONNECTION"
                self.__nodes_csv.writerow(
                    [node.unique_id, node.osm_id, intersection_label, node.location.lat, node.location.lng])

        for way in tqdm(ways, unit="way", desc="Creating ways"):
            nodes_in_way = way.nodes
            prev_node = nodes_in_way[0]

            for current_node in nodes_in_way[1:]:
                # temporary way
                tmp_way = Way(way.way_id, way.name, [prev_node, current_node], way.speedlimit, way.oneway)

                self.__way_csv.writerow(
                    [tmp_way.start_node.unique_id, tmp_way.end_node.unique_id, WAYS_TYPE_NAME, tmp_way.length,
                     tmp_way.length, tmp_way.name, tmp_way.type, tmp_way.speedlimit, way.way_id])
                # filter ways, if direction is unilateral
                if not tmp_way.oneway:
                    self.__way_csv.writerow(
                        [tmp_way.end_node.unique_id, tmp_way.start_node.unique_id, WAYS_TYPE_NAME, tmp_way.length,
                         tmp_way.length, tmp_way.name, tmp_way.type, tmp_way.speedlimit, way.way_id])

                prev_node = current_node

        way_csv_file.close()
        nodes_csv_file.close()


class TrafficLightHandler(osmium.SimpleHandler):

    def __init__(self, filename, output_dir, log):
        super(TrafficLightHandler, self).__init__()
        self.log = log
        self._traffic_lights = []
        self._output_dir = output_dir

        self.log.info(f"Output directory: {self._output_dir}")
        self.log.info(f"Input file: {filename}")

        print(f"Parsing nodes for traffic lights from {filename}")
        self.apply_file(filename, locations=True, idx='sparse_mem_array')

        self.log.info(f"Found {len(self.traffic_lights)} traffic lights")

        self.write_csv()

    @property
    def traffic_lights(self):
        return self._traffic_lights

    # TODO remove comment; only for later understanding implementation for RoundaboutHandler
    """
    Beim Aufruf von apply_file werden alle Nodes in der .osm-Datei geparsed
    Dabei wird hier überall geprüft, ob in einem Tag des Nodes das Label NODE_TRAFFIC_LIGHT_TAG_VALUE 
    ist. Wenn ja wird dieser Node berücksichtigt, indem er in die Liste "traffic_lights" angehängt wird
    """

    def node(self, node):
        if node.tags.get(NODE_TRAFFIC_LIGHT_TAG_KEY) == NODE_TRAFFIC_LIGHT_TAG_VALUE:
            node_location = Location(lat=node.location.lat, lng=node.location.lon)
            traffic_light = TrafficLight(node.id, node_location)
            self._traffic_lights.append(traffic_light)

    def write_csv(self):
        tl_csv_file = open(os.path.join(self._output_dir, TRAFFIC_LIGHT_CSV_NAME), 'w', encoding='utf-8', newline="")

        self.__tl_csv = csv.writer(tl_csv_file, doublequote=False)
        self.__tl_csv.writerow(['traffic_light_id:ID', 'osm_id:string', ':LABEL', 'lat:float', 'lng:float'])

        for node in tqdm(self.traffic_lights, unit="traffic light", desc="Creating traffic lights"):
            self.__tl_csv.writerow([node.unique_id, node.osm_id, 'TRAFFIC_LIGHT', node.location.lat, node.location.lng])

        tl_csv_file.close()


class RoundaboutHandler(osmium.SimpleHandler):

    def __init__(self, filename, output_dir, log):
        super(RoundaboutHandler, self).__init__()
        self.log = log
        self._roundabouts = []
        self._output_dir = output_dir

        self.log.info(f"Output directory: {self._output_dir}")
        self.log.info(f"Input file: {filename}")

        print(f"Parsing ways for roundabouts from {filename}")
        self.apply_file(filename, locations=True, idx='sparse_mem_array')

        self.log.info(f"Found {len(self._roundabouts)} roundabouts")

        self.write_csv()

    def way(self, way):
        if not osm_helper.is_street(way):
            return

        if way.tags.get(WAY_ROUNDABOUT_TAG_KEY) == WAY_ROUNDABOUT_TAG_VALUE:
            roundabout = Roundabout(way.id)
            self._roundabouts.append(roundabout)

    def write_csv(self):
        roundabout_csv_file = open(os.path.join(self._output_dir, ROUNDABOUT_CSV_NAME), 'w', encoding='utf-8',
                                   newline="")

        roundabout_csv = csv.writer(roundabout_csv_file, doublequote=False)
        roundabout_csv.writerow(['osm_id:string', ':LABEL'])

        for roundabout in tqdm(self._roundabouts, unit="roundabout", desc="Creating roundabouts"):
            roundabout_csv.writerow([roundabout.osm_id, 'ROUNDABOUT'])

        roundabout_csv_file.close()


class RoadWorkHandler(osmium.SimpleHandler):

    def __init__(self, filename, output_dir, log):
        super(RoadWorkHandler, self).__init__()
        self.log = log
        self._road_works = []
        self._output_dir = output_dir

        self.log.info(f"Output directory: {self._output_dir}")
        self.log.info(f"Input file: {filename}")

        print(f"Parsing ways for road works from {filename}")
        self.apply_file(filename, locations=True, idx='sparse_mem_array')

        self.log.info(f"Found {len(self._road_works)} road works")

        self.write_csv()

    def way(self, way):
        if way.tags.get(WAY_ROAD_WORK_TAG_KEY) == WAY_ROAD_WORK_TAG_VALUE:
            road_work = RoadWork(way.id)
            self._road_works.append(road_work)

    def write_csv(self):
        road_work_csv_file = open(os.path.join(self._output_dir, ROAD_WORK_CSV_NAME), 'w', encoding='utf-8',
                                  newline="")

        road_work_csv = csv.writer(road_work_csv_file, doublequote=False)
        road_work_csv.writerow(['osm_id:string', ':LABEL'])

        for road_work in tqdm(self._road_works, unit="road_work", desc="Creating road works"):
            road_work_csv.writerow([road_work.osm_id, 'ROAD_WORK'])

        road_work_csv_file.close()
