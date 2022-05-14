import logging

import requests
from requests import HTTPError

from canary.const import (
    URL_LOGIN_PAGE,
    COOKIE_XSRF_TOKEN,
    COOKIE_SSESYRANAC,
    URL_LOGIN_API,
    ATTR_USERNAME,
    ATTR_PASSWORD,
    ATTR_CLIENT_ID,
    ATTR_VALUE_CLIENT_ID,
    ATTR_VALUE_GRANT_TYPE,
    ATTR_GRANT_TYPE,
    ATTR_SCOPE,
    ATTR_VALUE_SCOPE,
    ATTR_TOKEN,
    URL_WATCHLIVE_BASE,
    ATTR_SESSION_ID,
    URL_ENTRIES_API,
    HEADER_XSRF_TOKEN,
    HEADER_AUTHORIZATION,
    HEADER_VALUE_AUTHORIZATION,
    ATTR_DEVICE_UUID,
)
from canary.model import Entry

_LOGGER = logging.getLogger(__name__)


class LiveStreamApi:
    def __init__(self, username, password, timeout=10, token=None):
        self._username = username
        self._password = password
        self._timeout = timeout
        self._token = token
        self._ssesyranac = None
        self._xsrf_token = None

        self.pre_login()
        if token is None:
            self.login()

    def pre_login(self):
        response = requests.get(URL_LOGIN_PAGE)

        xsrf_token = response.cookies[COOKIE_XSRF_TOKEN]
        ssesyranac = response.cookies[COOKIE_SSESYRANAC]

        self._ssesyranac = ssesyranac
        self._xsrf_token = xsrf_token

    def login(self):
        response = self._call_api(
            "post",
            URL_LOGIN_API,
            params={
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
                ATTR_CLIENT_ID: ATTR_VALUE_CLIENT_ID,
                ATTR_GRANT_TYPE: ATTR_VALUE_GRANT_TYPE,
                ATTR_SCOPE: ATTR_VALUE_SCOPE,
            },
        )

        _LOGGER.debug(
            "Received API response: %d, %s", response.status_code, response.content
        )

        response.raise_for_status()

        self._token = response.json()[ATTR_TOKEN]

    def start_session(self, device_uuid):
        response = self._call_api(
            "post",
            f"{URL_WATCHLIVE_BASE}{device_uuid}/session",
            json={},  # "deviceUUID": device_uuid},
        )
        response.raise_for_status()

        session_id = response.json().get(ATTR_SESSION_ID)

        if self.renew_session(device_uuid, session_id):
            return session_id

        return None

    def renew_session(self, device_uuid, session_id):
        response = self._call_api(
            "post",
            f"{URL_WATCHLIVE_BASE}{device_uuid}/send",
            json={ATTR_SESSION_ID: session_id},
        )
        response.raise_for_status()

        json = response.json()

        return "message" in json and json["message"] == "success"

    def stop_session(self, device_uuid, session_id):
        """Ends the session"""
        response = self._call_api(
            "post",
            f"{URL_WATCHLIVE_BASE}{device_uuid}/stop",
            json={
                ATTR_DEVICE_UUID: device_uuid,
                ATTR_SESSION_ID: session_id,
                "action": "delete",
            },
        )
        response.raise_for_status()

        json = response.json()

        return "message" in json and json["message"] == "success"

    def get_entries(self, location_id, params):
        json = self._call_api(
            "get", f"{URL_ENTRIES_API}{location_id}", params=params
        ).json()

        return [Entry(data) for data in json]

    def get_live_stream_url(self, device_id, session_id):
        return f"{URL_WATCHLIVE_BASE}{device_id}/{session_id}/stream.m3u8"

    def _call_api(self, method, url, params=None, **kwargs):
        _LOGGER.debug("About to call %s with %s", url, params)

        response = requests.request(
            method,
            url,
            params=params,
            timeout=self._timeout,
            headers=self._api_headers(),
            cookies=self._api_cookies(),
            **kwargs,
        )

        _LOGGER.debug(
            "Received API response: %d, %s", response.status_code, response.content
        )

        response.raise_for_status()

        return response

    def _api_cookies(self):
        return {
            COOKIE_XSRF_TOKEN: self._xsrf_token,
            COOKIE_SSESYRANAC: self._ssesyranac,
        }

    def _api_headers(self):
        return {
            HEADER_XSRF_TOKEN: self._xsrf_token,
            HEADER_AUTHORIZATION: f"{HEADER_VALUE_AUTHORIZATION} {self._token}",
        }

    @property
    def auth_token(self):  # -> str | None:
        return self._token


class LiveStreamSession:
    def __init__(self, api, device):
        self._api = api
        self._device_uuid = device.uuid
        self._device_id = device.device_id
        self._session_id = None

        self.start_renew_session()

    def start_renew_session(self):
        if self._session_id is None:
            self._session_id = self._api.start_session(self._device_uuid)
        else:
            try:
                self._api.renew_session(self._device_uuid, self._session_id)
            except HTTPError as ex:
                if ex.response.status_code == 403:
                    self._session_id = self._api.start_session(self._device_uuid)
                else:
                    self._session_id = None
                    raise ex

    def stop_session(self) -> None:
        self._api.stop_session(self._device_uuid, self._session_id)
        self.clear_session()

    def clear_session(self) -> None:
        self._session_id = None

    @property
    def live_stream_url(self):  # -> str | None:
        if self._session_id is None:
            return None
        return self._api.get_live_stream_url(self._device_id, self._session_id)

    @property
    def auth_token(self):  # -> str | None:
        if self._api is None:
            return None
        return self._api.auth_token
