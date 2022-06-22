def get_tag(o, name, default=None):
    if hasattr(o, 'tags') and name in o.tags:
        return o.tags[name]
    return default


def get_name_from_way(way):
    # name = None
    name = get_tag(way, "name")

    if name is None:
        name = get_tag(way, "ref")

    if name is None:
        name = way.id

    return name


def is_street(w):
    valid_types = ['MOTORWAY', 'TRUNK', 'PRIMARY', 'SECONDARY', 'TERTIARY', 'UNCLASSIFIED', 'RESIDENTIAL',
                   'SERVICE', 'LIVING_STREET', 'DRIVEWAY', 'MINI_ROUNDABOUT', 'MOTORWAY_JUNCTION', 'MOTORWAY_LINK',
                   'PRIMARY_LINK', 'SECONDARY_LINK', 'TERTIARY_LINK', 'TRUNK_LINK', 'ROAD', 'LIVING_STREET',
                   # TODO might remove again; was added, as old Regensburg.osm file contains old constructions
                   'CONSTRUCTION']

    return 'highway' in w.tags and w.tags['highway'].upper() in valid_types


def is_oneway(w):
    way_oneway = get_tag(w, "oneway", "no")
    if way_oneway == "yes":
        return True
    else:
        return False
