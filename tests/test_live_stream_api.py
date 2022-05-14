"""The tests for the Canary sensor platform."""
import os
import unittest

import requests_mock

from canary.live_stream_api import LiveStreamApi
from canary.const import (
    URL_LOGIN_API,
    URL_LOGIN_PAGE,
    COOKIE_XSRF_TOKEN,
    COOKIE_SSESYRANAC,
)

COOKIE_XSRF_VAL = "xsrf"
COOKIE_COOKIE_SSESYRANAC_VAL = "ssesyranac"


def load_fixture(filename):
    """Load a fixture."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(path) as fptr:
        return fptr.read()


def _setup_responses(mock):
    mock.register_uri(
        "POST", URL_LOGIN_API, text=load_fixture("live_stream_api_login.json")
    )
    mock.register_uri(
        "GET",
        URL_LOGIN_PAGE,
        cookies={
            COOKIE_XSRF_TOKEN: COOKIE_XSRF_VAL,
            COOKIE_SSESYRANAC: COOKIE_COOKIE_SSESYRANAC_VAL,
        },
    )


class TestLiveStreamApi(unittest.TestCase):
    @requests_mock.Mocker()
    def test_login(self, mock):
        """Test login for canary live stream api"""
        _setup_responses(mock)
        api = LiveStreamApi("user", "pass")

        api.login()

        with self.subTest("stores the token on the api object"):
            self.assertEqual(api._token, "ffffffffffffffffffffffffffffffffffffffff")

        with self.subTest("stores ssesyranac cookie on the api object"):
            self.assertEqual(api._ssesyranac, "ssesyranac")
