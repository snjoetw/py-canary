# py-canary [![Build Status](https://travis-ci.org/snjoetw/py-canary.svg?branch=master)](https://travis-ci.org/snjoetw/py-canary)
Python API for Canary Security Camera.  This is used in [Home Assistant](https://home-assistant.io) but should be generic enough that can be used elsewhere.

## TAG 0.5.2.B1
- Fixes: Temperature readings are now returned for Canary Pro
- Fixes: Live Streaming from Canary Pro and Canary Flex.  Canary View is untested, but _should_ work too
- drops the range for getting readings from 2 hours to 40 minutes to allow the Canary API to return data for the possible 5 sensor type readings
- updates canary's user agent header app version and iOS version to current values


### Development changes
- pytest now works with the changes to the live stream api changes
- adds pre-commit (dev tool)
- adds pytest config data
