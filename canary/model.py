from enum import Enum
from datetime import datetime, timezone

from canary.const import RECORDING_STATES, DATETIME_FORMAT


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
    DATE_LAST_ENTRY = "last_entry_date"
    ENTRIES_CAPTURED_TODAY = "entries_captured_today"


class Entry:
    def __init__(self, data):
        self._entry_id = data["id"]
        self._start_time = data.get("start_time", "")
        self._device_uuids = []
        self._starred = data.get("starred", False)
        self._selected = data.get("selected", False)
        self._thumbnails = []

        for device_data in data.get("device_uuids", []):
            # for whatever reason, this call has hyphens in the uuid's
            # while all others do not
            self._device_uuids.append(device_data.replace("-", ""))

        for thumbnail_data in data.get("thumbnails", []):
            self._thumbnails.append(Thumbnail(thumbnail_data))

    @property
    def entry_id(self):
        return self._entry_id

    @property
    def start_time(self):  # -> datetime | None:
        try:
            return datetime.strptime(self._start_time + "Z", DATETIME_FORMAT).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    @property
    def device_uuids(self):
        return self._device_uuids

    @property
    def starred(self):
        return self._starred

    @property
    def selected(self):
        return self._selected

    @property
    def thumbnails(self):
        return self._thumbnails


class Thumbnail:
    def __init__(self, data):
        self._image_url = data["signed_url"]

    @property
    def image_url(self):
        return self._image_url


class Mode:
    def __init__(self, data):
        self._id = data["id"]
        self._name = data["name"]
        self._resource_uri = data["resource_uri"]

    def __repr__(self):
        return f"Mode(id={self.mode_id}, name={self.name})"

    @property
    def mode_id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def resource_uri(self):
        return self._resource_uri
