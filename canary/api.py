import logging
from datetime import datetime, timedelta, date

from canary import util
from canary.const import (
    URL_MODES_API,
    ATTR_OBJECTS,
    URL_LOCATIONS_API,
    URL_LOCATION_API,
    DATETIME_FORMAT,
    URL_READINGS_API,
    DATETIME_MS_FORMAT,
    DATETIME_MS_FORMAT_NOTZ,
    TIMEOUT,
    URL_ENTRIES_API,
)
from canary.live_stream_api import LiveStreamApi, LiveStreamSession
from canary.model import Mode, Location, Reading, Entry
from canary.auth import Auth

_LOGGER = logging.getLogger(__name__)


class Api:
    def __init__(self, auth: Auth, timeout=TIMEOUT):
        self._auth = auth
        self._timeout = timeout
        self._modes_by_name = {}
        self._live_stream_api = None

        if self._auth.login_attributes["token"] is None:
            self._auth.login()

        self._modes_by_name = {mode.name: mode for mode in self.get_modes()}

    def get_modes(self):
        json = util.call_api("get", URL_MODES_API, self._auth).json()[ATTR_OBJECTS]
        return [Mode(data) for data in json]

    def get_locations(self):
        json = util.call_api("get", URL_LOCATIONS_API, self._auth).json()[ATTR_OBJECTS]
        return [Location(data, self._modes_by_name) for data in json]

    def get_location(self, location_id):
        url = f"{URL_LOCATION_API}{location_id}/"
        json = util.call_api("get", url, self._auth).json()
        return Location(json, self._modes_by_name)

    def set_location_mode(self, location_id, mode_name, is_private=False):
        url = f"{URL_LOCATION_API}{location_id}/"
        util.call_api(
            "patch",
            url,
            self._auth,
            json={
                "mode": self._modes_by_name[mode_name].resource_uri,
                "is_private": is_private,
            },
        )

    def get_readings(self, device_id):
        end = datetime.utcnow()
        start = end - timedelta(minutes=40)
        created_range = (
            f"{start.strftime(DATETIME_FORMAT)},{end.strftime(DATETIME_FORMAT)}"
        )
        json = util.call_api(
            "get",
            URL_READINGS_API,
            self._auth,
            {
                "created__range": created_range,
                "device": device_id,
                "resolution": "10m",
                "limit": 0,
            },
        ).json()[ATTR_OBJECTS]
        return [Reading(data) for data in json]

    def get_latest_readings(self, device_id):
        readings = self.get_readings(device_id)
        readings_by_type = {}

        for reading in readings:
            if reading.sensor_type not in readings_by_type:
                readings_by_type[reading.sensor_type] = reading

        return readings_by_type.values()

    def get_entries(self, location_id):
        utc_beginning, utc_ending = self._get_todays_date_range_utc()

        json = util.call_api(
            "get",
            f"{URL_ENTRIES_API}{location_id}",
            self._auth,
            params={
                "end": f"{utc_ending.strftime(DATETIME_MS_FORMAT)[:-3]}Z",
                "start": f"{utc_beginning.strftime(DATETIME_MS_FORMAT)[:-3]}Z",
            },
        ).json()

        return [Entry(data) for data in json]

    def get_latest_entries(self, location_id):
        entries = self.get_entries(location_id)
        entries_by_device_uuid = {}

        for entry in entries:
            for device_uuid in entry.device_uuids:
                if device_uuid not in entries_by_device_uuid:
                    entries_by_device_uuid[device_uuid] = entry

        return entries_by_device_uuid.values()

    def get_live_stream_session(self, device):
        if self._live_stream_api is None:
            self._live_stream_api = LiveStreamApi(self._auth.token, self._timeout)
        return LiveStreamSession(self._live_stream_api, device)

    def _get_todays_date_range_utc(self):
        utc_offset = datetime.utcnow() - datetime.now()
        today = date.today()
        beginning = today.strftime("%Y-%m-%d 00:00:00.0001")
        utc_beginning = (
            datetime.strptime(beginning, DATETIME_MS_FORMAT_NOTZ) + utc_offset
        )
        ending = today.strftime("%Y-%m-%d 23:59:59.99999")
        utc_ending = datetime.strptime(ending, DATETIME_MS_FORMAT_NOTZ) + utc_offset
        return utc_beginning, utc_ending

    @property
    def auth_token(self):  # -> str | None:
        return self._auth.token
