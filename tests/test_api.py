"""The tests for the Canary sensor platform."""
import os
import unittest

import requests_mock

from canary.api import Api, URL_LOGIN_API, URL_MODES_API, URL_LOCATIONS_API, \
    SensorType, URL_ENTRIES_API, URL_READINGS_API


def load_fixture(filename):
    """Load a fixture."""
    path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(path) as fptr:
        return fptr.read()


def _setup_responses(mock):
    mock.register_uri(
        "POST",
        URL_LOGIN_API,
        text=load_fixture("api_login.json"))

    mock.register_uri(
        "GET",
        URL_MODES_API,
        text=load_fixture("api_modes.json"))

    mock.register_uri(
        "GET",
        URL_LOCATIONS_API,
        text=load_fixture("api_locations.json"))

    mock.register_uri(
        "GET",
        URL_ENTRIES_API,
        text=load_fixture("api_entries_70001.json"))

    mock.register_uri(
        "GET",
        URL_READINGS_API,
        text=load_fixture("api_readings_80005.json"))


class TestApi(unittest.TestCase):
    @requests_mock.Mocker()
    def test_locations(self, mock):
        """Test the Canary locations API."""
        _setup_responses(mock)
        api = Api("user", "pass")

        locations = api.get_locations()
        self.assertEqual(2, len(locations))

        for location in locations:
            if location.name == "Vacation Home":
                self.assertTrue(location.is_recording)
                self.assertFalse(location.is_private)
                self.assertTrue(location.is_celsius)
                self.assertEqual(2, len(location.customers))
                self.assertEqual("away", location.mode.name)
                self.assertEqual("armed", location.current_mode.name)
                self.assertEqual(70001, location.location_id)
            elif location.name == "Home":
                self.assertFalse(location.is_recording)
                self.assertFalse(location.is_private)
                self.assertFalse(location.is_celsius)
                self.assertEqual(1, len(location.customers))
                self.assertEqual("home", location.mode.name)
                self.assertEqual("standby", location.current_mode.name)
                self.assertEqual(70002, location.location_id)

    @requests_mock.Mocker()
    def test_location_with_motion_entry(self, mock):
        """Test the Canary entries API."""
        _setup_responses(mock)
        api = Api("user", "pass")

        entries = api.get_entries(70001)
        self.assertEqual(1, len(entries))

        entry = entries[0]
        self.assertEqual(60001, entry.entry_id)
        self.assertEqual("Activity detected in away mode", entry.description)
        self.assertEqual("motion", entry.entry_type)
        self.assertEqual("2017-11-19T06:50:44", entry.start_time)
        self.assertEqual("2017-11-19T07:00:44", entry.end_time)
        self.assertEqual(1, len(entry.thumbnails))

        thumbnail = entry.thumbnails[0]
        self.assertEqual("https://image_url.com", thumbnail.image_url)

    @requests_mock.Mocker()
    def test_device_with_readings(self, mock):
        """Test the Canary entries API."""
        _setup_responses(mock)
        api = Api("user", "pass")

        readings = api.get_readings(80001)
        self.assertEqual(6, len(readings))

        readings = api.get_latest_readings(80001)
        self.assertEqual(3, len(readings))

        for reading in readings:
            if reading.sensor_type == SensorType.AIR_QUALITY:
                self.assertEqual("0.8129177689552307", reading.value)
            elif reading.sensor_type == SensorType.HUMIDITY:
                self.assertEqual("41.68813060192352", reading.value)
            elif reading.sensor_type == SensorType.TEMPERATURE:
                self.assertEqual("19.0007521446715", reading.value)
