"""The tests for the Canary sensor platform."""
import os
import unittest

import pytest
import requests_mock

from canary.api import Api
from canary.auth import Auth
from canary.const import (
    COOKIE_SSESYRANAC,
    COOKIE_XSRF_TOKEN,
    URL_LOCATIONS_API,
    URL_LOGIN_API,
    URL_LOGIN_PAGE,
    URL_MODES_API,
    URL_READINGS_API,
    URL_WATCHLIVE_BASE,
)
from canary.model import SensorType

from tests import mock_device

COOKIE_XSRF_VAL = "xsrf"
COOKIE_COOKIE_SSESYRANAC_VAL = "ssesyranac"

FIXED_DATE_RANGE = (
    "?end=2022-05-05T23%3A59%3A59.999Z&start=2022-05-05T00%3A00%3A00.000Z"
)
URL_ENTRY_API = f"https://my.canary.is/api/entries/tl2/70001{FIXED_DATE_RANGE}"

OTP_USED = False


def load_fixture(filename):
    """Load a fixture."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(path) as fptr:
        return fptr.read()


def _mfa_callback(request, context):
    global OTP_USED
    if OTP_USED:
        context.status_code = 200
        print(200)
        return load_fixture("api_login.json")
    print(403)
    context.status_code = 403
    return load_fixture("api_login_2fa.json")


def _setup_responses(mock, enable_2fa=False):
    if enable_2fa:
        mock.register_uri("POST", URL_LOGIN_API, text=_mfa_callback)
        mock.register_uri(
            "POST", "https://my.canary.is/mfa/challenge/login", text="timeout"
        )
    else:
        mock.register_uri("POST", URL_LOGIN_API, text=load_fixture("api_login.json"))

    mock.register_uri("GET", URL_MODES_API, text=load_fixture("api_modes.json"))

    mock.register_uri("GET", URL_LOCATIONS_API, text=load_fixture("api_locations.json"))

    mock.register_uri(
        "GET", f"{URL_LOCATIONS_API}20/", text=load_fixture("api_location_20.json")
    )

    mock.register_uri(
        "PATCH", f"{URL_LOCATIONS_API}20/", text=load_fixture("api_location_20.json")
    )

    mock.register_uri(
        "GET", URL_READINGS_API, text=load_fixture("api_readings_80005.json")
    )

    mock.register_uri(
        "GET",
        URL_LOGIN_PAGE,
        cookies={
            COOKIE_XSRF_TOKEN: COOKIE_XSRF_VAL,
            COOKIE_SSESYRANAC: COOKIE_COOKIE_SSESYRANAC_VAL,
        },
    )

    mock.register_uri(
        "GET",
        URL_ENTRY_API,
        text=load_fixture("api_entries_70001.json"),
    )

    mock.register_uri(
        "POST",
        f"{URL_WATCHLIVE_BASE}f1f2/session",
        text='{"sessionId": "1"}',
    )

    mock.register_uri(
        "POST",
        f"{URL_WATCHLIVE_BASE}f1f2/send",
        text='{"message": "success"}',
    )

    mock.register_uri(
        "POST",
        f"{URL_WATCHLIVE_BASE}f1f2/stop",
        text='{"message": "success"}',
    )


class TestApi(unittest.TestCase):
    @requests_mock.Mocker()
    def test_locations(self, mock):
        """Test the Canary locations API."""
        _setup_responses(mock)
        auth = Auth({"username": "user", "password": "pass"})
        api = Api(auth)

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
    def test_get_location(self, mock):
        """Test the Canary locations API."""
        _setup_responses(mock)
        auth = Auth({"username": "user", "password": "pass"})
        api = Api(auth)

        location = api.get_location(location_id=20)
        self.assertFalse(location.is_recording)
        self.assertFalse(location.is_private)
        self.assertFalse(location.is_celsius)
        self.assertEqual(1, len(location.customers))
        self.assertEqual("home", location.mode.name)
        self.assertEqual("standby", location.current_mode.name)
        self.assertEqual(20, location.location_id)

    @requests_mock.Mocker()
    def test_set_location_mode(self, mock):
        """Test the Canary locations API."""
        _setup_responses(mock)
        auth = Auth({"username": "user", "password": "pass"})
        api = Api(auth)

        urls_called = mock.call_count
        api.set_location_mode(location_id=20, mode_name="away")
        self.assertTrue(mock.called)
        self.assertEqual(urls_called + 1, mock.call_count)

    @pytest.mark.freeze_time("2022-05-05")
    @requests_mock.Mocker()
    def test_location_with_motion_entry(self, mock):
        """Test the Canary entries API."""
        _setup_responses(mock)
        auth = Auth({"username": "user", "password": "pass"})
        api = Api(auth)

        entries = api.get_entries(70001)
        self.assertEqual(2, len(entries))

        entry = entries[0]
        self.assertEqual("00000000-0000-0000-0001-000000000000", entry.entry_id)
        self.assertEqual("2022-05-06 00:08:14+00:00", str(entry.start_time))
        self.assertEqual(False, entry.starred)
        self.assertEqual(False, entry.selected)
        self.assertEqual(1, len(entry.thumbnails))
        self.assertEqual(1, len(entry.device_uuids))

        thumbnail = entry.thumbnails[0]
        self.assertEqual("https://image_url.com", thumbnail.image_url)

        device_uuid = entry.device_uuids[0]
        self.assertEqual("fffffffffeedffffffffffffffffffff", device_uuid)

        entries = api.get_latest_entries(70001)
        for entry in entries:
            self.assertEqual("00000000-0000-0000-0001-000000000000", entry.entry_id)
            self.assertEqual("2022-05-06 00:08:14+00:00", str(entry.start_time))
            self.assertEqual(False, entry.starred)
            self.assertEqual(False, entry.selected)
            self.assertEqual(1, len(entry.thumbnails))
            self.assertEqual(1, len(entry.device_uuids))

            thumbnail = entry.thumbnails[0]
            self.assertEqual("https://image_url.com", thumbnail.image_url)

            device_uuid = entry.device_uuids[0]
            self.assertEqual("fffffffffeedffffffffffffffffffff", device_uuid)

    @requests_mock.Mocker()
    def test_device_with_readings(self, mock):
        """Test the Canary entries API."""
        _setup_responses(mock)
        auth = Auth({"username": "user", "password": "pass"})
        api = Api(auth)

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

    @requests_mock.Mocker()
    def test_get_live_stream_session(self, mock):
        """Test the Canary entries API."""
        _setup_responses(mock)
        auth = Auth({"username": "user", "password": "pass"})
        api = Api(auth)

        device = mock_device(device_id=20, name="Living Room", uuid="f1f2")

        lss = api.get_live_stream_session(device)

        self.assertEqual(api.auth_token, lss.auth_token)

        lss.stop_session()

    @requests_mock.Mocker()
    def test_2fa_login(self, mock):
        global OTP_USED
        """Test the Canary locations API."""
        _setup_responses(mock, enable_2fa=True)
        auth = Auth({"username": "user", "password": "pass"}, no_prompt=True)
        api = Api(auth)

        api._auth.otp = "1234"
        self.assertEqual(auth.otp, "1234")
        OTP_USED = True
        api.login()

        self.assertIsNone(auth.otp)
