"""Login handler for Canary."""
import logging

import requests
from requests import exceptions

from canary import util
from canary.const import (
    ATTR_CLIENT_ID,
    ATTR_GRANT_TYPE,
    ATTR_PASSWORD,
    ATTR_SCOPE,
    ATTR_TOKEN,
    ATTR_USERNAME,
    ATTR_VALUE_CLIENT_ID,
    ATTR_VALUE_GRANT_TYPE,
    ATTR_VALUE_SCOPE,
    COOKIE_SSESYRANAC,
    COOKIE_XSRF_TOKEN,
    HEADER_USER_AGENT,
    HEADER_VALUE_USER_AGENT,
    HEADER_XSRF_TOKEN,
    TIMEOUT,
    URL_LOGIN_API,
    URL_LOGIN_PAGE,
)

_LOGGER = logging.getLogger(__name__)


class Auth:
    """Class to handle login communication."""

    def __init__(self, login_data=None, no_prompt=False):
        """
        Initialize auth handler.
        :param login_data: dictionary for login data
                           must contain the following:
                             - username
                             - password
        :param no_prompt: Should any user input prompts
                          be suppressed? True/FALSE
        """
        if login_data is None:
            login_data = {}
        self._data = login_data
        self._username = login_data.get("username", None)
        self._password = login_data.get("password", None)
        self._token = login_data.get("token", None)
        self._login_response = None
        self.is_errored = False
        self.no_prompt = no_prompt
        self.otp = None
        self._ssesyranac = None
        self._xsrf_token = None

    @property
    def login_attributes(self):
        """Return a dictionary of login attributes."""
        self._data["username"] = self._username
        self._data["password"] = self._password
        self._data["token"] = self._token
        return self._data

    @property
    def token(self):
        return self._token

    def validate_login(self):
        """Check login information and prompt if not available."""
        self._data["username"] = self._data.get("username", None)
        self._data["password"] = self._data.get("password", None)
        if not self.no_prompt:
            self._data = util.prompt_login_data(self._data)

    def pre_login(self):
        response = requests.get(URL_LOGIN_PAGE)

        xsrf_token = response.cookies[COOKIE_XSRF_TOKEN]
        ssesyranac = response.cookies[COOKIE_SSESYRANAC]

        self._ssesyranac = ssesyranac
        self._xsrf_token = xsrf_token

    def login(self):
        self.validate_login()

        self.pre_login()

        headers = {
            HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT,
            "accept": "application/json",
        }
        if self.otp:
            headers["X-OTP"] = self.otp

        response = requests.post(
            URL_LOGIN_API,
            {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
                ATTR_CLIENT_ID: ATTR_VALUE_CLIENT_ID,
                ATTR_GRANT_TYPE: ATTR_VALUE_GRANT_TYPE,
                ATTR_SCOPE: ATTR_VALUE_SCOPE,
            },
            timeout=TIMEOUT,
            headers=headers,
        )

        _LOGGER.debug(
            "Received login response: %d, %s", response.status_code, response.content
        )

        self._login_response = self.validate_response(response, True)
        # response.raise_for_status()

        if self.check_key_required():
            # MFA is enabled...
            headers["content-type"] = "application/json"
            headers[HEADER_XSRF_TOKEN] = self._xsrf_token
            try:
                response = requests.post(
                    "https://my.canary.is/mfa/challenge/login",
                    json={
                        ATTR_USERNAME: self._username,
                        ATTR_PASSWORD: self._password,
                    },
                    timeout=5,
                    headers=headers,
                    cookies=self._api_cookies(),
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

            if not self.no_prompt:
                self.otp = input("OTP:")

                self.login()
            return

        self.otp = None
        self._token = self._login_response.get(ATTR_TOKEN, None)

    def validate_response(self, response, json_resp):
        """Check for valid response."""
        if not json_resp:
            self.is_errored = False
            return response
        self.is_errored = True
        try:
            if response.status_code in [101, 401]:
                raise UnauthorizedError
            if response.status_code == 404:
                raise exceptions.ConnectionError
            json_data = response.json()
            self.is_errored = False
            return json_data
        except KeyError:
            pass
        except (AttributeError, ValueError) as error:
            raise CanaryBadResponse from error
        return None

    def check_key_required(self):
        """Check if 2FA key is required."""
        try:
            error_message = self._login_response.get("error", "")
            if "mfa_required" in error_message:
                return True
        except (KeyError, TypeError):
            pass
        return False

    def _api_cookies(self):
        return {
            COOKIE_XSRF_TOKEN: self._xsrf_token,
            COOKIE_SSESYRANAC: self._ssesyranac,
        }


class CanaryBadResponse(Exception):
    """Class to throw bad json response exception."""


class UnauthorizedError(Exception):
    """Class to throw an unauthorized access error."""
