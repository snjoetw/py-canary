"""Login handler for Canary."""
import logging

from requests import exceptions

from canary import util
from canary.const import ATTR_TOKEN, COOKIE_SSESYRANAC, COOKIE_XSRF_TOKEN
from canary.model import CanaryBadResponse, UnauthorizedError

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
        self.login_response = None
        self.is_errored = False
        self.no_prompt = no_prompt
        self.otp = None
        self._ssesyranac = None
        self._xsrf_token = None

    @property
    def login_attributes(self):
        """Return a dictionary of login attributes."""
        self._data["username"] = self.username
        self._data["password"] = self.password
        self._data["token"] = self.token
        return self._data

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def token(self):
        return self._token

    @property
    def xsrf_token(self):
        return self._xsrf_token

    def validate_login(self):
        """Check login information and prompt if not available."""
        self._data["username"] = self._data.get("username", None)
        self._data["password"] = self._data.get("password", None)
        if not self.no_prompt:
            self._data = util.prompt_login_data(self._data)

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
            error_message = self.login_response.get("error", "")
            if "mfa_required" in error_message:
                return True
        except (KeyError, TypeError):
            pass
        return False

    def api_cookies(self):
        return {
            COOKIE_XSRF_TOKEN: self._xsrf_token,
            COOKIE_SSESYRANAC: self._ssesyranac,
        }

    def set_login_token(self):
        self._token = self.login_response.get(ATTR_TOKEN, None)

    def parse_cookies(self, cookies):
        self._ssesyranac = cookies[COOKIE_SSESYRANAC]
        self._xsrf_token = cookies[COOKIE_XSRF_TOKEN]
