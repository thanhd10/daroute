from schema.sensor_models import SensorTurnModel


class TestRouteModel(object):
    def __init__(self, test_id: str,
                 prep_file_path: str,
                 heading_start: int,
                 test_device: str,
                 notes: str,
                 new_sensor_turns: [SensorTurnModel],
                 osm_id_path: [int],
                 traffic_lights=None):

        self.test_id = test_id
        self.prep_file_path = prep_file_path
        self.heading_start = heading_start
        self.test_device = test_device
        self.notes = notes
        self.new_sensor_turns = new_sensor_turns
        self.osm_id_path = osm_id_path
        if traffic_lights is None:
            self.traffic_lights = []
        else:
            self.traffic_lights = traffic_lights
