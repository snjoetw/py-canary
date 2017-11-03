import logging
from enum import Enum

import requests

COOKIE_XSRF_TOKEN = "XSRF-TOKEN"
COOKIE_SSESYRANAC = "ssesyranac"

COOKIE_VALUE_SSESYRANAC = "token={}"

HEADER_XSRF_TOKEN = "X-XSRF-TOKEN"
HEADER_SSESYRANAC = "ssesyranac"
HEADER_AUTHORIZATION = "Authorization"

HEADER_VALUE_AUTHORIZATION = "Bearer {}"

URL_LOGIN_PAGE = "https://my.canary.is/login"
URL_LOGIN_API = "https://my.canary.is/api/auth/login"
URL_ME_API = "https://my.canary.is/api/customers/me?email={}"
URL_LOCATIONS_API = "https://my.canary.is/api/locations"
URL_READINGS_API = "https://my.canary.is/api/readings?deviceId={}&type={}"
URL_ENTRIES_API = "https://my.canary.is/api/entries/{}?entry_type={}&limit={}&offset=0"

ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"

_LOGGER = logging.getLogger(__name__)


class Api:
    def __init__(self, username, password, timeout=10):
        self._username = username
        self._password = password
        self._timeout = timeout
        self._token = None
        self._xsrf_token = None

    def login(self):
        r = requests.get(URL_LOGIN_PAGE)

        xsrf_token = r.cookies[COOKIE_XSRF_TOKEN]
        ssesyranac = r.cookies[COOKIE_SSESYRANAC]

        r = requests.post(URL_LOGIN_API, {
            ATTR_USERNAME: self._username,
            ATTR_PASSWORD: self._password
        }, headers={
            HEADER_XSRF_TOKEN: xsrf_token
        }, cookies={
            COOKIE_XSRF_TOKEN: xsrf_token,
            COOKIE_SSESYRANAC: ssesyranac
        })

        self._token = r.json()["access_token"]
        self._xsrf_token = xsrf_token

    def get_me(self):
        r = requests.get(URL_ME_API.format(self._username),
                         headers=self._api_headers(),
                         cookies=self._api_cookies())
        r.raise_for_status()

        _LOGGER.debug("Received get_me API response: {}".format(r.json()))

        return Customer(r.json())

    def get_locations(self):
        r = requests.get(URL_LOCATIONS_API,
                         headers=self._api_headers(),
                         cookies=self._api_cookies())
        r.raise_for_status()

        _LOGGER.debug(
            "Received get_locations API response: {}".format(r.json()))

        return [Location(data) for data in r.json()]

    def get_readings(self, device):
        r = requests.get(
            URL_READINGS_API.format(device.device_id, device.device_type),
            headers=self._api_headers(),
            cookies=self._api_cookies())
        r.raise_for_status()

        _LOGGER.debug(
            "Received get_readings API response: {}".format(r.json()))

        return [Reading(data) for data in r.json()]

    def get_entries(self, location_id, entry_type="motion", limit=6):
        r = requests.get(
            URL_ENTRIES_API.format(location_id, entry_type, limit),
            headers=self._api_headers(),
            cookies=self._api_cookies())
        r.raise_for_status()

        _LOGGER.debug("Received get_entries API response: {}".format(r.json()))

        return [Entry(data) for data in r.json()]

    def _api_cookies(self):
        return {
            COOKIE_XSRF_TOKEN: self._xsrf_token,
            COOKIE_SSESYRANAC: COOKIE_VALUE_SSESYRANAC.format(self._token)
        }

    def _api_headers(self):
        return {
            HEADER_XSRF_TOKEN: self._xsrf_token,
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
    def __init__(self, data):
        self._id = data["id"]
        self._name = data["name"]
        self._resource_uri = data["resource_uri"]
        self._location_mode = None if data["mode"] is None \
            else LocationMode(data["mode"])
        self._is_private = data["is_private"]
        self._devices = []

        for device_data in data["devices"]:
            self._devices.append(Device(device_data))

    @property
    def location_id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def location_mode(self):
        return self._location_mode

    @property
    def resource_uri(self):
        return self._resource_uri

    @property
    def devices(self):
        return self._devices

    @property
    def is_private(self):
        return self._is_private


class LocationMode(Enum):
    AWAY = "away"
    HOME = "home"
    NIGHT = "night"


class Device:
    def __init__(self, data):
        self._id = data["id"]
        self._uuid = data["uuid"]
        self._name = data["name"]
        self._device_mode = None if data["device_mode"] is None \
            else DeviceMode(data["device_mode"])
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


class DeviceMode(Enum):
    DISARMED = "disarmed"
    ARMED = "armed"
    PRIVACY = "privacy"


class Reading:
    def __init__(self, data):
        self._sensor_type = SensorType(data["sensor_type"])
        self._status = data["status"]
        self._value = data["value"]

    @property
    def sensor_type(self):
        return self._sensor_type

    @property
    def status(self):
        return self._status

    @property
    def value(self):
        return self._value


class SensorType(Enum):
    AIR_QUALITY = "air_quality"
    HUMIDITY = "humidity"
    TEMPERATURE = "temperature"


class Entry:
    def __init__(self, data):
        self._entry_id = data["id"]
        self._description = data["description"]
        self._device_uuids = data["device_uuids"]
        self._entry_type = data["entry_type"]
        self._start_time = data["start_time"]
        self._end_time = data["end_time"]
        self._thumbnails = []

        for thumbnail_data in data["thumbnails"]:
            self._thumbnails.append(Thumbnail(thumbnail_data))

    @property
    def entry_id(self):
        return self._entry_id

    @property
    def description(self):
        return self._description

    @property
    def device_uuids(self):
        return self._device_uuids

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
        self._device_uuid = data["device_uuid"]
        self._image_url = data["image_url"]

    @property
    def device_uuid(self):
        return self._device_uuid

    @property
    def image_url(self):
        return self._image_url
