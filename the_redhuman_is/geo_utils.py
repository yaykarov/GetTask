# -*- coding: utf-8 -*-

import codecs
import json
import os
import pyproj

from django.conf import settings

from shapely.geometry import Polygon
from shapely.geometry import Point

# https://proj.org/operations/projections/index.html
# https://proj.org/operations/projections/merc.html
_PROJ = pyproj.Proj(proj='merc', ellps='WGS84', datum='WGS84')

_GEOD = pyproj.Geod(ellps='WGS84')


class GeoUtilError(Exception):
    pass


class ZoneMismatch(GeoUtilError, ValueError):
    pass


# in meters
def distance(lon1, lat1, lon2, lat2):
    _, _, dst = _GEOD.inv(lon1, lat1, lon2, lat2)
    return dst


def xy_to_lonlat(x, y):
    return _PROJ(x, y, inverse=True)


MKAD_LON_LAT = [
    (37.369053, 55.762936),
    (37.369188, 55.75435),
    (37.370248, 55.744789),
    (37.374991, 55.735201),
    (37.378369, 55.728581),
    (37.383283, 55.718273),
    (37.388969, 55.709657),
    (37.397952, 55.702805),
    (37.407528, 55.695697),
    (37.414868, 55.686873),
    (37.418712, 55.67994),
    (37.42598, 55.670701),
    (37.434424, 55.660424),
    (37.441125, 55.654675),
    (37.448195, 55.648794),
    (37.456864, 55.641041),
    (37.469925, 55.630207),
    (37.474668, 55.625801),
    (37.484846, 55.617424),
    (37.49391, 55.609685),
    (37.502274, 55.60249),
    (37.516108, 55.594728),
    (37.526366, 55.5922),
    (37.545132, 55.587509),
    (37.555732, 55.585143),
    (37.571938, 55.581271),
    (37.586536, 55.5778),
    (37.60107, 55.575816),
    (37.616719, 55.574732),
    (37.633419, 55.573928),
    (37.647765, 55.573093),
    (37.668911, 55.571999),
    (37.683167, 55.574019),
    (37.696256, 55.578834),
    (37.709425, 55.583983),
    (37.723062, 55.589234),
    (37.734785, 55.594143),
    (37.747945, 55.599677),
    (37.758725, 55.604956),
    (37.771139, 55.611755),
    (37.781928, 55.617713),
    (37.794235, 55.623758),
    (37.802473, 55.62913),
    (37.814564, 55.637347),
    (37.824787, 55.643713),
    (37.833842, 55.650053),
    (37.839348, 55.658667),
    (37.837597, 55.667752),
    (37.834605, 55.675945),
    (37.831353, 55.68529),
    (37.829512, 55.694287),
    (37.83262, 55.703048),
    (37.837121, 55.712203),
    (37.83916, 55.721939),
    (37.840175, 55.730482),
    (37.841217, 55.739103),
    (37.841828, 55.747399),
    (37.842627, 55.755723),
    (37.842789, 55.76522),
    (37.842762, 55.774558),
    (37.841576, 55.785017),
    (37.840965, 55.793991),
    (37.840004, 55.802781),
    (37.838926, 55.811599),
    (37.837148, 55.821072),
    (37.829754, 55.828789),
    (37.822819, 55.832707),
    (37.800586, 55.844167),
    (37.788522, 55.850383),
    (37.765992, 55.861979),
    (37.741261, 55.874698),
    (37.735791, 55.877501),
    (37.723636, 55.883555),
    (37.712363, 55.889094),
    (37.698807, 55.893884),
    (37.681721, 55.894868),
    (37.667878, 55.895449),
    (37.647648, 55.896973),
    (37.635961, 55.898533),
    (37.619603, 55.901637),
    (37.604637, 55.905472),
    (37.590344, 55.909257),
    (37.575531, 55.910907),
    (37.559577, 55.909388),
    (37.543443, 55.907687),
    (37.527597, 55.90526),
    (37.513206, 55.899578),
    (37.5016, 55.894232),
    (37.48861, 55.888897),
    (37.473096, 55.884625),
    (37.459065, 55.882828),
    (37.443596, 55.881091),
    (37.429429, 55.877041),
    (37.416601, 55.872703),
    (37.405588, 55.867051),
    (37.397314, 55.858801),
    (37.393056, 55.850141),
    (37.394709, 55.840376),
    (37.395275, 55.83251),
    (37.393236, 55.823606),
    (37.390397, 55.814629),
    (37.386876, 55.805796),
    (37.379824, 55.79723),
    (37.372943, 55.789542),
    (37.369853, 55.779722),
    (37.369619, 55.771444),
]


SOCHI_LON_LAT = [
    (39.668673, 43.643982),
    (39.669081, 43.645579),
    (39.667632, 43.647083),
    (39.668512, 43.647691),
    (39.670550, 43.647862),
    (39.678061, 43.646974),
    (39.682817, 43.644874),
    (39.682817, 43.644276),
    (39.683606, 43.644002),
    (39.685767, 43.644450),
    (39.692464, 43.642329),
    (39.695984, 43.642578),
    (39.698455, 43.644299),
    (39.700330, 43.644064),
    (39.703365, 43.655168),
    (39.707657, 43.655293),
    (39.711776, 43.641955),
    (39.728428, 43.642329),
    (39.738041, 43.630360),
    (39.747997, 43.653174),
    (39.759327, 43.658035),
    (39.760872, 43.653423),
    (39.757953, 43.630360),
    (39.768596, 43.628490),
    (39.721904, 43.558247),
]


def _polygon_xy_data(polygon):
    xy = []
    for lon, lat in polygon:
        x, y = _PROJ(lon, lat)
        xy.append((x, y))

    min_x, min_y = xy[0]
    max_x = min_x
    max_y = min_y

    for x, y in xy[1:]:
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y

    polygon = Polygon(xy)

    if not polygon.is_valid:
        raise ValueError('WARNING: Polygon is not valid')

    return min_x, max_x, min_y, max_y, polygon


MKAD_DATA = _polygon_xy_data(MKAD_LON_LAT)
SOCHI_DATA = _polygon_xy_data(SOCHI_LON_LAT)


def _is_point_inside(lat, lon, polygon_data):
    MIN_X, MAX_X, MIN_Y, MAX_Y, POLYGON = polygon_data

    x, y = _PROJ(lon, lat)

    if x < MIN_X or MAX_X < x:
        return False
    if y < MIN_Y or MAX_Y < y:
        return False

    return POLYGON.contains(Point(x, y))


def _distance_to(lat, lon, polygon_lon_lat):
    tmp_lon, tmp_lat = polygon_lon_lat[0]
    min_dst = distance(tmp_lon, tmp_lat, lon, lat)

    for tmp_lon, tmp_lat in polygon_lon_lat[1:]:
        dst = distance(tmp_lon, tmp_lat, lon, lat)
        if dst < min_dst:
            min_dst = dst

    return min_dst


# Todo: remove this, use common ZONES dict
def is_point_inside_MKAD(lat, lon):
    return _is_point_inside(lat, lon, MKAD_DATA)


# Todo: remove this, use common ZONES dict
def distance_to_MKAD(lat, lon):
    return _distance_to(lat, lon, MKAD_LON_LAT)


# Todo: remove this, use common ZONES dict
def is_point_inside_Sochi(lat, lon):
    return _is_point_inside(lat, lon, SOCHI_DATA)


# Todo: remove this, use common ZONES dict
def distance_to_Sochi(lat, lon):
    return _distance_to(lat, lon, SOCHI_LON_LAT)


ZONES = {
    'msk': (MKAD_DATA, MKAD_LON_LAT),
    'sochi': (SOCHI_DATA, SOCHI_LON_LAT)
}


def _parse_zones():
    for entry in os.scandir(os.path.join(settings.BASE_DIR, 'the_redhuman_is/geo_zones')):
        zone = os.path.splitext(entry.name)[0]
        with codecs.open(entry.path, encoding='utf-8') as f:
            geojson = json.load(f)
            # Todo: some asserts
            coordinates = geojson['features'][0]['geometry']['coordinates'][0]
            lon_lat = [(c[0], c[1]) for c in coordinates]
            ZONES[zone] = (_polygon_xy_data(lon_lat), lon_lat)


_parse_zones()


_HIDDEN_ZONES = (
    'dmitrov',
    'vyborg',
    'serpukhov',
)


def is_point_inside_zone(lat, lon, zone):
    return _is_point_inside(lat, lon, ZONES[zone][0])


# Todo: check if there is a library method
def distance_to_zone(lat, lon, zone):
    return _distance_to(lat, lon, ZONES[zone][1])


def get_zone(lat, lon):
    if is_point_inside_MKAD(lat, lon):
        return 'msk', 0

    if is_point_inside_Sochi(lat, lon):
        return 'sochi', 0

    min_dst = distance_to_MKAD(lat, lon)
    min_zone = 'msk'

    dst = distance_to_Sochi(lat, lon)
    if dst < min_dst:
        min_dst = dst
        min_zone = 'sochi'

    for zone in ZONES.keys():
        if zone in _HIDDEN_ZONES:
            continue

        if is_point_inside_zone(lat, lon, zone):
            return zone, 0

        dst = distance_to_zone(lat, lon, zone)
        if dst < min_dst:
            min_dst = dst
            min_zone = zone

    return min_zone, min_dst


def max_distance_to_zone(coordinates):
    def _get_zone(*args):
        try:
            return get_zone(*args)
        except Exception as e:
            raise GeoUtilError from e

    lat, lon = coordinates[0]
    first_zone, max_dst = _get_zone(lat, lon)

    for lat, lon in coordinates[1:]:
        zone, dst = _get_zone(lat, lon)
        if zone != first_zone:
            raise ZoneMismatch(f'В группе координат не совпадают зоны: {first_zone} != {zone}')
        if dst > max_dst:
            max_dst = dst

    return first_zone, max_dst


# bounding box and polygon
def zone_bb_lonlat(zone):
    MIN_X, MAX_X, MIN_Y, MAX_Y, POLYGON = ZONES[zone][0]
    lon1, lat1 = xy_to_lonlat(MIN_X, MIN_Y)
    lon2, lat2 = xy_to_lonlat(MAX_X, MAX_Y)

    return (min(lon1, lon2), min(lat1, lat2)), (max(lon1, lon2), max(lat1, lat2)), ZONES[zone][1]


def _scale(polygon, k):
    center_lon, center_lat = polygon[0]

    for lon, lat in polygon[1:]:
        center_lon += lon
        center_lat += lat

    center_lon /= len(polygon)
    center_lat /= len(polygon)

    scaled = []

    for lon, lat in polygon:
        scaled.append((
            center_lon + k * (lon - center_lon),
            center_lat + k * (lat - center_lat)
        ))

    return scaled


def test_mkad():
    inner = _scale(MKAD_LON_LAT, 0.999)
    for lon, lat in inner:
        if not is_point_inside_MKAD(lat, lon):
            raise Exception('{}, {} treated as not inside MKAD, but it is'.format(lon, lat))

    outer = _scale(MKAD_LON_LAT, 1.001)
    for lon, lat in outer:
        if is_point_inside_MKAD(lat, lon):
            raise Exception('{}, {} treated as inside MKAD, but it is not'.format(lon, lat))

