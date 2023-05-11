from the_redhuman_is import geo_utils
from the_redhuman_is.models.delivery import (
    DeliveryZone,
    Location,
    WorkerZone,
    ZoneGroup,
)
from the_redhuman_is.models.worker import Worker


class NoWorkerZoneData(Exception):
    pass


class TooManyZones(Exception):
    pass


class ZoneDataIntegrityError(Exception):
    pass


def _get_delivery_zones():
    return {
        e['code']: e['group_id']
        for e in list(DeliveryZone.objects.values('code', 'group_id'))
    }


def get_mobile_app_zone(worker, delivery_zones=None):
    if delivery_zones is None:
        delivery_zones = _get_delivery_zones()
    lat_lon_mobile = list(
        Location.objects.filter(
            mobileappstatus__user__workeruser__worker=worker
        ).distinct(
        ).values_list('latitude', 'longitude')
    )
    zones = set()
    for lat, lon in lat_lon_mobile:
        r = geo_utils.get_zone(lat, lon)
        if r is None:
            zones.add(None)
        else:
            zones.add(r[0])
    zones.discard(None)
    if not zones:
        raise NoWorkerZoneData
    if len(zones) > 1:
        raise TooManyZones
    try:
        return delivery_zones[zones.pop()]
    except KeyError:
        raise ZoneDataIntegrityError


def get_turnout_zone(worker):
    zone = ZoneGroup.objects.filter(
        locationzonegroup__location__timesheet__worker_turnouts__worker=worker
    ).values_list('pk', flat=True).distinct().first()
    if zone is not None:
        return zone
    else:
        raise NoWorkerZoneData


def assign_workers_to_zones():
    delivery_zones = _get_delivery_zones()
    unassigned_workers = Worker.objects.all(
    ).filter_mobile(  # get delivery workers
    ).filter(
        workerzone__isnull=True,  # unassigned
    ).distinct('pk')  # prevent dupes

    for w in unassigned_workers:
        try:
            zone_group_id = get_turnout_zone(w)
        except NoWorkerZoneData:
            try:
                zone_group_id = get_mobile_app_zone(w, delivery_zones)
            except (NoWorkerZoneData, TooManyZones, ZoneDataIntegrityError):
                continue
        WorkerZone.objects.create(worker=w, zone_id=zone_group_id)
