# py-canary [![Build Status](https://travis-ci.org/snjoetw/py-canary.svg?branch=master)](https://travis-ci.org/snjoetw/py-canary)[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)![PyPI](https://img.shields.io/pypi/v/py-canary)
Python API for Canary Security Camera.  This is used in [Home Assistant](https://home-assistant.io) but should be generic enough that can be used elsewhere.

**Disclaimer:**
Published under the MIT license - See LICENSE file for more details.

Canary Pro, Canary Flex and Canary View, see www.canary.is for more information.
We are in no way affiliated with Canary Connect, Inc.


## Breaking Change
Version 0.6.0 changes the way the Api and LiveStreamApi classes are created.

Pre 0.6.0, py-canary's Api class was created by
```python
from canary.api import Api
from canary.api import LiveStreamApi

canary = Api(username="<your username>", password="<your password>")

live_stream = LiveStreamApi(username="<your username>", password="<your password>")
```

Now there is an Auth class that handles logins and utilizes tokens for the LiveStreamApi to no trigger
a new login. So the new method to create a Canary Api instance is as follows:

```python
from canary.api import Api
from canary.auth import Auth
from canary.api import LiveStreamApi

# Can set no_prompt when initializing auth handler
auth = Auth({"username": "<your username>", "password": "<your password>"}, no_prompt=True)
canary = Api(auth)

# if 2FA is enabled a code will be sent out.
# Update the canary.auth.otp property to the code received and login again.
canary.auth.otp = "<otp code>"
canary.auth.login()

live_stream = LiveStreamApi(token=canary.auth.token)
```


## Installation
``pip install py-canary``

### Installing Development Version

To install the current development version, perform the following steps.  Note that the following will
create a py-canary directory in your home area:

```bash
$ cd ~
$ git clone https://github.com/snjoetw/py-canary.git
$ cd py-canary
$ rm -rf build dist
$ python3 -m build
$ pip3 install --upgrade dist/*.whl
```

## Purpose
This library was built with the intention of allowing easy communication with Canary camera systems,
specifically to support the [Canary component](https://home-assistant.io/components/canary) in
[homeassistant](https://home-assistant.io/).

# Quick Start
The simplest way to use this package from a terminal is to run the sample script ``python3 run_api.py``
which will prompt for your Canary username and password, as well as a 2FA code if your account is set up
to use one, and then log you in.

```python
from canary.api import Api
from canary.auth import Auth


auth = Auth()
canary = Api(auth)
```


This flow will prompt you for your username and password.  Once entered, if your account is 2FA protected,
a code will be sent to your phone number from Canary's servers. This code will need to be entered at the
*OTP:* prompt.

### Starting py-canary without a prompt
In some cases, having an interactive command-line session is not desired.  In this case, you will need to
set the ``Auth.no_prompt`` value to ``True``.  In addition, since you will not be prompted with a username
and password, you must supply the login data to the blink authentication handler.  This is best done by
instantiating your own auth handler with a dictionary containing at least your username and password.

```python
from canary.api import Api
from canary.auth import Auth

# Can set no_prompt when initializing auth handler
auth = Auth({"username": <your username>, "password": <your password>}, no_prompt=True)
canary = Api(auth)

# if 2FA is enabled a code will be sent out.
# Update the canary.auth.otp property to the code received and login again.
canary.auth.otp = "<otp code>"
canary.auth.login()
```


Since you will not be prompted for any 2FA pin, you must wait to proceed until the OTP code is set in auth.
