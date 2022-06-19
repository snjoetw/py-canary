"""Tools and utility calls for py-canary."""
from datetime import date, datetime
from getpass import getpass
import logging

import requests

from canary.const import (
    DATETIME_MS_FORMAT_NOTZ,
    HEADER_AUTHORIZATION,
    HEADER_USER_AGENT,
    HEADER_VALUE_AUTHORIZATION,
    HEADER_VALUE_USER_AGENT,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def prompt_login_data(data):
    """Prompt user for username and password."""
    if data["username"] is None:
        data["username"] = input("Username:")
    if data["password"] is None:
        data["password"] = getpass("Password:")

    return data


def call_api(method, url, auth, params=None, **kwargs):
    _LOGGER.debug("About to call %s with %s", url, params)

    response = requests.request(
        method,
        url,
        params=params,
        timeout=TIMEOUT,
        headers=api_headers(auth.token),
        **kwargs,
    )

    _LOGGER.debug(
        "Received API response: %d, %s", response.status_code, response.content
    )

    response.raise_for_status()

    return response


def api_headers(token: str):
    if token is None:
        return None

    return {
        HEADER_USER_AGENT: HEADER_VALUE_USER_AGENT,
        HEADER_AUTHORIZATION: f"{HEADER_VALUE_AUTHORIZATION} {token}",
    }


def get_todays_date_range_utc():
    utc_offset = datetime.utcnow() - datetime.now()
    today = date.today()
    beginning = today.strftime("%Y-%m-%d 00:00:00.0001")
    utc_beginning = datetime.strptime(beginning, DATETIME_MS_FORMAT_NOTZ) + utc_offset
    ending = today.strftime("%Y-%m-%d 23:59:59.99999")
    utc_ending = datetime.strptime(ending, DATETIME_MS_FORMAT_NOTZ) + utc_offset
    return utc_beginning, utc_ending
