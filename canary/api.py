import logging
from datetime import datetime, timedelta
from enum import Enum

import requests

from canary.live_stream_api import LiveStreamApi, LiveStreamSession

HEADER_AUTHORIZATION = "Authorization"
HEADER_USER_AGENT = "User-Agent"

HEADER_VALUE_AUTHORIZATION = "Bearer {}"
HEADER_VALUE_USER_AGENT = "Canary/2.10.0 (iPhone; iOS 11.2; Scale/3.00)"

URL_LOGIN_API = "https://api.canaryis.com/o/access_token/"
URL_LOCATIONS_API = "https://api.canaryis.com/v1/locations/"
URL_LOCATION_API = "https://api.canaryis.com/v1/locations/{}/"
URL_MODES_API = "https://api.canaryis.com/v1/modes/"
URL_ENTRIES_API = "https://api.canaryis.com/v1/entries/"
URL_READINGS_API = "https://api.canaryis.com/v1/readings/"

ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"
ATTR_CLIENT_ID = "client_id"
ATTR_CLIENT_SECRET = "client_secret"
ATTR_GRANT_TYPE = "grant_type"
ATTR_SCOPE = "scope"

ATTR_VALUE_CLIENT_ID = "a183323eab0544d83808"
ATTR_VALUE_CLIENT_SECRET = "ba883a083b2d45fa7c6a6567ca7a01e473c3a269"
ATTR_VALUE_GRANT_TYPE = "password"
ATTR_VALUE_SCOPE = "write"

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_LOGGER = logging.getLogger(__name__)

LOCATION_MODE_HOME = "home"
LOCATION_MODE_AWAY = "away"
LOCATION_MODE_NIGHT = "night"

LOCATION_STATE_ARMED = "armed"
LOCATION_STATE_DISARMED = "disarmed"
LOCATION_STATE_PRIVACY = "privacy"
LOCATION_STATE_STANDBY = "standby"

RECORDING_STATES = [LOCATION_STATE_ARMED, LOCATION_STATE_DISARMED]


class Api:
    def __init__(self, username, password, timeout=10):
        self._username = username
        self._password = password
        self._timeout = timeout
        self._token = None
        self._modes_by_name = {}
        self._live_stream_api = None

        self.login()

    def login(self):
        response = requests.post(URL_LOGIN_API, {
            ATTR_USERNAME: self._username,
            ATTR_PASSWORD: self._password,
            ATTR_CLIENT_ID: ATTR_VALUE_CLIENT_ID,
            ATTR_CLIENT_SECRET: ATTR_VALUE_CLIENT_SECRET,
            ATTR_GRANT_TYPE: ATTR_VALUE_GRANT_TYPE,
            ATTR_SCOPE: ATTR_VALUE_SCOPE,
        }, timeout=self._timeout, headers={
            HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT
        })

        _LOGGER.debug("Received login response: %s, %s", response.status_code,
                      response.content)

        response.raise_for_status()

        self._token = response.json()["access_token"]
        self._modes_by_name = {mode.name: mode for mode in self.get_modes()}

    def get_modes(self):
        json = self._call_api("get", URL_MODES_API).json()["objects"]
        return [Mode(data) for data in json]

    def get_locations(self):
        json = self._call_api("get", URL_LOCATIONS_API).json()["objects"]
        return [Location(data, self._modes_by_name) for data in json]

    def get_location(self, location_id):
        url = URL_LOCATION_API.format(location_id)
        json = self._call_api("get", url).json()
        return Location(json, self._modes_by_name)

    def set_location_mode(self, location_id, mode_name, is_private=False):
        url = URL_LOCATION_API.format(location_id)
        self._call_api("patch", url, json={
            "mode": self._modes_by_name[mode_name].resource_uri,
            "is_private": is_private
        })
        return None

    def get_readings(self, device_id):
        end = datetime.utcnow()
        start = end - timedelta(hours=2)
        created_range = "{},{}".format(start.strftime(DATETIME_FORMAT),
                                       end.strftime(DATETIME_FORMAT))
        json = self._call_api("get", URL_READINGS_API, {
            "created__range": created_range,
            "device": device_id,
            "resolution": "10m",
            "limit": 0
        }).json()["objects"]
        return [Reading(data) for data in json]

    def get_latest_readings(self, device_id):
        readings = self.get_readings(device_id)
        readings_by_type = {}

        for reading in readings:
            if reading.sensor_type not in readings_by_type:
                readings_by_type[reading.sensor_type] = reading

        return readings_by_type.values()

    def get_entries(self, location_id, entry_type="motion", limit=1,
                    last_modified=None):
        if last_modified is None:
            last_modified = datetime.utcnow() - timedelta(days=3)

        json = self._call_api("get", URL_ENTRIES_API, {
            "last_modified__gt": last_modified.strftime(DATETIME_FORMAT),
            "include_deleted": "True",
            "offset": "0",
            "location": location_id,
            "limit": limit,
            "entry_type": entry_type,
        }).json()["objects"]
        return [Entry(data) for data in json]

    def get_live_stream_session(self, device):
        if self._live_stream_api is None:
            self._live_stream_api = LiveStreamApi(self._username,
                                                  self._password,
                                                  self._timeout)
        return LiveStreamSession(self._live_stream_api, device)

    def _call_api(self, method, url, params=None, **kwargs):
        _LOGGER.debug("About to call %s with %s", url, params)

        response = requests.request(method, url, params=params,
                                    timeout=self._timeout,
                                    headers=self._api_headers(), **kwargs)

        _LOGGER.debug("Received API response: %s, %s", response.status_code,
                      response.content)

        response.raise_for_status()

        return response

    def _api_headers(self):
        return {
            HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT,
            HEADER_AUTHORIZATION: HEADER_VALUE_AUTHORIZATION.format(
                self._token)
        }


class Customer:
    def __init__(self, data):
        self._id = data["id"]
        self._first_name = data["first_name"]
        self._last_name = data["last_name"]
        self._is_celsius = data["celsius"]

    @property
    def customer_id(self):
        return self._id

    @property
    def first_name(self):
        return self._first_name

    @property
    def last_name(self):
        return self._last_name

    @property
    def is_celsius(self):
        return self._is_celsius


class Location:
    def __init__(self, data, modes_by_name):
        self._id = data["id"]
        self._name = data["name"]
        self._is_private = data["is_private"]
        self._devices = []
        self._customers = []

        mode_name = data.get("mode", {}).get("name", None)
        self._mode = modes_by_name.get(mode_name, None)

        current_mode_name = data.get("current_mode", {}).get("name", None)
        self._current_mode = modes_by_name.get(current_mode_name, None)

        for device_data in data["devices"]:
            self._devices.append(Device(device_data))

        for customer_data in data["customers"]:
            self._customers.append(Customer(customer_data))

    @property
    def location_id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def mode(self):
        return self._mode

    @property
    def current_mode(self):
        return self._current_mode

    @property
    def devices(self):
        return self._devices

    @property
    def customers(self):
        return self._customers

    @property
    def is_private(self):
        return self._is_private

    @property
    def is_recording(self):
        if self.current_mode is None:
            return False

        return self.current_mode.name in RECORDING_STATES

    @property
    def is_celsius(self):
        for customer in self._customers:
            if customer is not None and customer.is_celsius:
                return True

        return False


class Device:
    def __init__(self, data):
        self._id = data["id"]
        self._uuid = data["uuid"]
        self._name = data["name"]
        self._device_mode = None
        self._is_online = data["online"]
        self._device_type = data["device_type"]

    @property
    def device_id(self):
        return self._id

    @property
    def uuid(self):
        return self._uuid

    @property
    def name(self):
        return self._name

    @property
    def device_mode(self):
        return self._device_mode

    @property
    def is_online(self):
        return self._is_online

    @property
    def device_type(self):
        return self._device_type


class Reading:
    def __init__(self, data):
        self._sensor_type = SensorType(data["sensor_type"]["name"])
        self._value = data["value"]

    @property
    def sensor_type(self):
        return self._sensor_type

    @property
    def value(self):
        return self._value


class SensorType(Enum):
    AIR_QUALITY = "air_quality"
    HUMIDITY = "humidity"
    TEMPERATURE = "temperature"
    BATTERY = "battery"
    WIFI = "wifi"


class Entry:
    def __init__(self, data):
        self._entry_id = data["id"]
        self._description = data.get('description', '')
        self._entry_type = data.get('entry_type', '')
        self._start_time = data.get('start_time', '')
        self._end_time = data.get('end_time', '')
        self._thumbnails = []

        for thumbnail_data in data.get('thumbnails', []):
            self._thumbnails.append(Thumbnail(thumbnail_data))

    @property
    def entry_id(self):
        return self._entry_id

    @property
    def description(self):
        return self._description

    @property
    def entry_type(self):
        return self._entry_type

    @property
    def start_time(self):
        return self._start_time

    @property
    def end_time(self):
        return self._end_time

    @property
    def thumbnails(self):
        return self._thumbnails


class Thumbnail:
    def __init__(self, data):
        self._image_url = data["image_url"]

    @property
    def image_url(self):
        return self._image_url


class Mode:
    def __init__(self, data):
        self._id = data["id"]
        self._name = data["name"]
        self._resource_uri = data["resource_uri"]

    def __repr__(self):
        return "Mode(id={}, name={})".format(self.mode_id, self.name)

    @property
    def mode_id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def resource_uri(self):
        return self._resource_uri
