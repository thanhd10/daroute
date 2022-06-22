""" General Settings """

FONT_SIZE = 8
DPI_VALUE = 1400

COLUMN_WIDTH = 8.89 * 0.46

######################################################################

""" Color and marker style for mplleaflet route plots """

ROUTE_LINE_COLOR = 'cornflowerblue'  # 6495ED
ROUTE_LINE_WIDTH = '8'

INTERSECTION_COLOR = 'crimson'  # DC143C
INTERSECTION_DOT_MULTIPLE = 60

STANDARD_POINT_MARKER = 'o'
STANDARD_POINT_SIZE = 12
STANDARD_POINT_COLOR = 'sienna'

START_POINT_COLOR = 'black'
TARGET_POINT_COLOR = 'green'  # 008000

SUB_NODE_COLOR = 'dimgray'
SUB_NODE_DOT_MULTIPLE = 28

ACTUAL_PATH_COLOR = 'darkorange'

MAP_TILE = ("https://api.maptiler.com/maps/bright/256/{z}/{x}/{y}.png?key=Uv2KnWjGFdIk5l9oKBhC",
            '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> '
            '<a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>')

######################################################################
""" Color settings for evaluation graphics """
######################################################################

LINE_MARKER_SIZE = 5

LINESTYLE_FULL_MATCHING = '-'
LINESTYLE_PARTIAL_MATCHING = '--'


FIRST_ORDER_STYLE = {'color': 'royalblue', 'marker': 'o'}
SECOND_ORDER_STYLE = {'color': 'crimson', 'marker': 'd'}
THIRD_ORDER_STYLE = {'color': 'limegreen', 'marker': 's'}
FORTH_ORDER_STYLE = {'color': 'darkviolet', 'marker': '*'}
FIFTH_ORDER_STYLE = {'color': 'darkorange', 'marker': 'h'}
SIXTH_ORDER_STYLE = {'color': 'lightpink', 'marker': 'v'}
