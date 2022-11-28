from datetime import datetime, timedelta
import logging

import requests

from canary import util
from canary.auth import Auth
from canary.const import (
    ATTR_CLIENT_ID,
    ATTR_GRANT_TYPE,
    ATTR_OBJECTS,
    ATTR_PASSWORD,
    ATTR_SCOPE,
    ATTR_USERNAME,
    ATTR_VALUE_CLIENT_ID,
    ATTR_VALUE_GRANT_TYPE,
    ATTR_VALUE_SCOPE,
    DATETIME_FORMAT,
    DATETIME_MS_FORMAT,
    HEADER_USER_AGENT,
    HEADER_VALUE_USER_AGENT,
    HEADER_XSRF_TOKEN,
    TIMEOUT,
    URL_ENTRIES_API,
    URL_LOCATIONS_API,
    URL_LOGIN_API,
    URL_LOGIN_PAGE,
    URL_MODES_API,
    URL_READINGS_API,
)
from canary.live_stream_api import LiveStreamApi, LiveStreamSession
from canary.model import CanaryBadResponse, Entry, Location, Mode, Reading
from canary.util import get_todays_date_range_utc

_LOGGER = logging.getLogger(__name__)


class Api:
    def __init__(self, auth: Auth, timeout=TIMEOUT):
        self._auth = auth
        self._timeout = timeout
        self._modes_by_name = {}
        self._live_stream_api = None
        self._mfa_required = False

        self.login()

    def _pre_login(self):
        try:
            response = requests.get(URL_LOGIN_PAGE, timeout=self._timeout)
            self._auth.parse_cookies(response.cookies)
        except (requests.ConnectTimeout, requests.Timeout):
            _LOGGER.exception("Unable to get pre-login data due to a timeout")

    def login(self):
        self._auth.validate_login()

        if self._auth.login_attributes["token"] is None:
            self._pre_login()

            headers = {
                HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT,
                "accept": "application/json",
            }
            if self._auth.otp:
                headers["X-OTP"] = self._auth.otp
                # we have used the key; reset value
                self._mfa_required = False

            response = requests.post(
                URL_LOGIN_API,
                {
                    ATTR_USERNAME: self._auth.username,
                    ATTR_PASSWORD: self._auth.password,
                    ATTR_CLIENT_ID: ATTR_VALUE_CLIENT_ID,
                    ATTR_GRANT_TYPE: ATTR_VALUE_GRANT_TYPE,
                    ATTR_SCOPE: ATTR_VALUE_SCOPE,
                },
                timeout=TIMEOUT,
                headers=headers,
            )

            _LOGGER.debug(
                "Received login response: %d, %s",
                response.status_code,
                response.content,
            )

            self._auth.login_response = self._auth.validate_response(response, True)
            # response.raise_for_status()

            if self._auth.check_key_required():
                # MFA is enabled... request the key via SMS
                self._mfa_required = True
                headers["content-type"] = "application/json"
                headers[HEADER_XSRF_TOKEN] = self._auth.xsrf_token
                try:
                    response = requests.post(
                        "https://my.canary.is/mfa/challenge/login",
                        json={
                            ATTR_USERNAME: self._auth.username,
                            ATTR_PASSWORD: self._auth.password,
                        },
                        timeout=5,
                        headers=headers,
                        cookies=self._auth.api_cookies(),
                    )
                    _LOGGER.debug(
                        "Received login response: %d, %s",
                        response.status_code,
                        response.content,
                    )
                except requests.Timeout:
                    pass
                except requests.exceptions.RequestException as error:
                    raise CanaryBadResponse from error

                if not self._auth.no_prompt:
                    # if the command like prompt is on, ask for the OTP code and login
                    # else, it's handled bu the consuming script and api.is_mfa_required
                    self._auth.otp = input("OTP:")

                    self.login()
                return

            # only called if mfa is not required
            self._auth.set_login_token()

        # only called upon a successful login or if a token was passed in
        self._auth.otp = None

        # load the modes used by the various cameras
        self._modes_by_name = {mode.name: mode for mode in self.get_modes()}

    def get_modes(self):
        json = util.call_api("get", URL_MODES_API, self._auth).json()[ATTR_OBJECTS]
        return [Mode(data) for data in json]

    def get_locations(self):
        json = util.call_api("get", URL_LOCATIONS_API, self._auth).json()[ATTR_OBJECTS]
        return [Location(data, self._modes_by_name) for data in json]

    def get_location(self, location_id):
        url = f"{URL_LOCATIONS_API}{location_id}/"
        json = util.call_api("get", url, self._auth).json()
        return Location(json, self._modes_by_name)

    def set_location_mode(self, location_id, mode_name, is_private=False):
        url = f"{URL_LOCATIONS_API}{location_id}/"
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
        utc_beginning, utc_ending = get_todays_date_range_utc()

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

    @property
    def auth_token(self):  # -> str | None:
        return self._auth.token

    @property
    def is_mfa_required(self) -> bool:
        return self._mfa_required
