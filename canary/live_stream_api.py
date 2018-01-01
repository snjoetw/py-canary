import requests
from requests import HTTPError

COOKIE_XSRF_TOKEN = "XSRF-TOKEN"
COOKIE_SSESYRANAC = "ssesyranac"

COOKIE_VALUE_SSESYRANAC = "token={}"

HEADER_XSRF_TOKEN = "X-XSRF-TOKEN"
HEADER_SSESYRANAC = "ssesyranac"
HEADER_AUTHORIZATION = "Authorization"

HEADER_VALUE_AUTHORIZATION = "Bearer {}"

URL_LOGIN_PAGE = "https://my.canary.is/login"
URL_LOGIN_API = "https://my.canary.is/api/auth/login"
URL_START_SESSION = "https://my.canary.is/api/watchlive/{device_uuid}/session"
URL_RENEW_SESSION = "https://my.canary.is/api/watchlive/{device_uuid}/send"
URL_LIVE_STREAM = "https://my.canary.is/api/watchlive/{device_id}/" \
                  "{session_id}/stream.m3u8"

ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"
ATTR_ACCESS_TOKEN = "access_token"
ATTR_SESSION_ID = "sessionId"


class LiveStreamApi:
    def __init__(self, username, password, timeout=10):
        self._username = username
        self._password = password
        self._timeout = timeout
        self._token = None
        self._ssesyranac = None
        self._xsrf_token = None

        self.login()

    def login(self):
        response = requests.get(URL_LOGIN_PAGE)

        xsrf_token = response.cookies[COOKIE_XSRF_TOKEN]
        ssesyranac = response.cookies[COOKIE_SSESYRANAC]

        response = requests.post(URL_LOGIN_API, {
            ATTR_USERNAME: self._username,
            ATTR_PASSWORD: self._password
        }, headers={
            HEADER_XSRF_TOKEN: xsrf_token
        }, cookies={
            COOKIE_XSRF_TOKEN: xsrf_token,
            COOKIE_SSESYRANAC: ssesyranac
        })

        self._ssesyranac = ssesyranac
        self._token = response.json()[ATTR_ACCESS_TOKEN]
        self._xsrf_token = xsrf_token

    def start_session(self, device_uuid):
        response = requests.post(
            URL_START_SESSION.format(device_uuid=device_uuid),
            headers=self._api_headers(),
            cookies=self._api_cookies(),
            json={
                "deviceUUID": device_uuid
            })
        response.raise_for_status()

        session_id = response.json().get(ATTR_SESSION_ID)

        if self.renew_session(device_uuid, session_id):
            return session_id

        return None

    def renew_session(self, device_uuid, session_id):
        response = requests.post(
            URL_RENEW_SESSION.format(device_uuid=device_uuid),
            headers=self._api_headers(),
            cookies=self._api_cookies(),
            json={
                ATTR_SESSION_ID: session_id
            })
        response.raise_for_status()

        json = response.json()

        return "message" in json and json["message"] == "success"

    def get_live_stream_url(self, device_id, session_id):
        return URL_LIVE_STREAM.format(device_id=device_id,
                                      session_id=session_id)

    def _api_cookies(self):
        return {
            COOKIE_XSRF_TOKEN: self._xsrf_token,
            COOKIE_SSESYRANAC: self._ssesyranac
        }

    def _api_headers(self):
        return {
            HEADER_XSRF_TOKEN: self._xsrf_token,
            HEADER_AUTHORIZATION: HEADER_VALUE_AUTHORIZATION.format(
                self._token)
        }


class LiveStreamSession:
    def __init__(self, api, device):
        self._api = api
        self._device_uuid = device.uuid
        self._device_id = device.device_id
        self._session_id = None

    @property
    def live_stream_url(self):
        if self._session_id is None:
            self._session_id = self._api.start_session(self._device_uuid)
        else:
            try:
                self._api.renew_session(self._device_uuid, self._session_id)
            except HTTPError as ex:
                if ex.response.status_code == 403:
                    self._session_id = self._api.start_session(
                        self._device_uuid)
                else:
                    raise ex

        return self._api.get_live_stream_url(self._device_id, self._session_id)
