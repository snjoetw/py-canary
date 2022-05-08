import logging
from datetime import datetime, timedelta, date

import requests

from canary.const import (
    URL_LOGIN_API,
    ATTR_USERNAME,
    ATTR_PASSWORD,
    ATTR_CLIENT_ID,
    ATTR_VALUE_CLIENT_ID,
    ATTR_VALUE_CLIENT_SECRET,
    ATTR_CLIENT_SECRET,
    ATTR_GRANT_TYPE,
    ATTR_VALUE_SCOPE,
    ATTR_VALUE_GRANT_TYPE,
    ATTR_SCOPE,
    HEADER_USER_AGENT,
    HEADER_VALUE_USER_AGENT,
    ATTR_TOKEN,
    URL_MODES_API,
    ATTR_OBJECTS,
    URL_LOCATIONS_API,
    URL_LOCATION_API,
    DATETIME_FORMAT,
    URL_READINGS_API,
    HEADER_AUTHORIZATION,
    HEADER_VALUE_AUTHORIZATION,
    DATETIME_FORMAT_NOTZ,
)
from canary.live_stream_api import LiveStreamApi, LiveStreamSession
from canary.model import Mode, Location, Reading

_LOGGER = logging.getLogger(__name__)


class Api:
    def __init__(self, username, password, timeout=10, token=None):
        self._username = username
        self._password = password
        self._timeout = timeout
        self._token = token
        self._modes_by_name = {}
        self._live_stream_api = None

        if self._token is None:
            self.login()
        else:
            self._modes_by_name = {mode.name: mode for mode in self.get_modes()}

    def login(self):
        response = requests.post(
            URL_LOGIN_API,
            {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
                ATTR_CLIENT_ID: ATTR_VALUE_CLIENT_ID,
                ATTR_CLIENT_SECRET: ATTR_VALUE_CLIENT_SECRET,
                ATTR_GRANT_TYPE: ATTR_VALUE_GRANT_TYPE,
                ATTR_SCOPE: ATTR_VALUE_SCOPE,
            },
            timeout=self._timeout,
            headers={HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT},
        )

        _LOGGER.debug(
            "Received login response: %d, %s", response.status_code, response.content
        )

        response.raise_for_status()

        self._token = response.json()[ATTR_TOKEN]
        self._modes_by_name = {mode.name: mode for mode in self.get_modes()}

    def get_modes(self):
        json = self._call_api("get", URL_MODES_API).json()[ATTR_OBJECTS]
        return [Mode(data) for data in json]

    def get_locations(self):
        json = self._call_api("get", URL_LOCATIONS_API).json()[ATTR_OBJECTS]
        return [Location(data, self._modes_by_name) for data in json]

    def get_location(self, location_id):
        url = f"{URL_LOCATION_API}{location_id}/"
        json = self._call_api("get", url).json()
        return Location(json, self._modes_by_name)

    def set_location_mode(self, location_id, mode_name, is_private=False):
        url = f"{URL_LOCATION_API}{location_id}/"
        self._call_api(
            "patch",
            url,
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
        json = self._call_api(
            "get",
            URL_READINGS_API,
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
        if self._live_stream_api is None:
            self._live_stream_api = LiveStreamApi(
                self._username, self._password, self._timeout, self._token
            )

        utc_offset = datetime.utcnow() - datetime.now()
        today = date.today()
        begintime = today.strftime("%Y-%m-%d 00:00:00")
        utc_begintime = datetime.strptime(begintime, DATETIME_FORMAT_NOTZ) + utc_offset
        endtime = today.strftime("%Y-%m-%d 23:59:59")
        utc_endtime = datetime.strptime(endtime, DATETIME_FORMAT_NOTZ) + utc_offset

        return self._live_stream_api.get_entries(
            location_id,
            {
                "end": f"{utc_endtime.strftime(DATETIME_FORMAT)}",
                "start": f"{utc_begintime.strftime(DATETIME_FORMAT)}",
            },
        )

    def get_live_stream_session(self, device):
        if self._live_stream_api is None:
            self._live_stream_api = LiveStreamApi(
                self._username, self._password, self._timeout
            )
        return LiveStreamSession(self._live_stream_api, device)

    def _call_api(self, method, url, params=None, **kwargs):
        _LOGGER.debug("About to call %s with %s", url, params)

        response = requests.request(
            method,
            url,
            params=params,
            timeout=self._timeout,
            headers=self._api_headers(),
            **kwargs,
        )

        _LOGGER.debug(
            "Received API response: %d, %s", response.status_code, response.content
        )

        response.raise_for_status()

        return response

    def _api_headers(self):
        return {
            HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT,
            HEADER_AUTHORIZATION: f"{HEADER_VALUE_AUTHORIZATION} {self._token}",
        }
