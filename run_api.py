import json
import logging
import re

from canary.api import Api

# This will open a watch live session to get the URL and allow time
# to open the m3u8 file in VLC
LIVE_STREAM = True
# This will redact out sensitive data for sending data to devs
REDACT = True


def write_config(canary: Api):
    # Data to be written
    dictionary = {
        "username": canary._username,
        "password": canary._password,
        "token": canary._token,
    }
    # Serializing json
    json_object = json.dumps(dictionary, indent=4)
    # Writing to sample.json
    with open("./env/variables.json", "w") as outfile:
        outfile.write(json_object)


def read_settings():
    with open("./env/variables.json") as openfile:
        # Reading from json file
        json_object = json.load(openfile)
        try:
            if json_object["token"] == "":
                json_object["token"] = None
        except KeyError:
            json_object["token"] = None
        return json_object


def print_entries(entries):
    for entry in entries:
        logger.info(
            "id: %s - device_uuid: %s - date: %s",
            entry.entry_id[-3:] if REDACT else entry.entry_id,
            entry.device_uuids[0][-4:] if REDACT else entry.device_uuids[0],
            entry.start_time,
        )
        for thumbnail in entry.thumbnails:
            logger.info("-- %s", "was set" if REDACT else thumbnail.image_url)


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    # set logging level

    settings = read_settings()

    canary = Api(
        username=settings["username"],
        password=settings["password"],
        token=settings["token"],
    )

    write_config(canary)
    locations_by_id = {}
    readings_by_device_id = {}

    for location in canary.get_locations():
        location_id = location.location_id
        locations_by_id[location_id] = location

        for device in location.devices:
            logger.info(
                "device %s is a %s and is %s",
                device.name,
                device.device_type["name"],
                "online" if device.is_online else "offline",
            )
            logger.info("-- watch live? %s", device.watch_live)
            logger.info("-- firmware v%s", device.firmware_version)
            logger.info(
                "-- serial number %s",
                device.serial_number[0:3] if REDACT else device.serial_number,
            )
            if device.is_online:
                readings_by_device_id[device.device_id] = canary.get_latest_readings(
                    device.device_id
                )
                # below requires a new login as well, since there are new
                # cookies that need to be set.
                if LIVE_STREAM:
                    lss = canary.get_live_stream_session(device=device)

                    logger.info(
                        "device %s live stream session url = %s",
                        device.name,
                        re.sub(
                            r"watchlive/\d+/[a-z\d]+/",
                            "watchlive/--loc_id--/--hash--/",
                            lss.live_stream_url,
                        )
                        if REDACT
                        else lss.live_stream_url,
                    )
                    input(
                        "Press Enter to close the live stream session and continue..."
                    )
                    lss.stop_session()
                    logger.info("live stream session closed")

        logger.info("Getting the day's entries...")
        entries = canary.get_entries(location_id=location_id)
        print_entries(entries)

        logger.info("Getting a single entry by device...")
        entries = canary.get_latest_entries(location_id)
        print_entries(entries)

        logger.info("Latest Readings by device...")
        for key in readings_by_device_id:
            for reading in readings_by_device_id[key]:
                # yes this loop is not really needed,
                # but to anonymize the device id's we need it
                for device in location.devices:
                    if device.device_id == key:
                        logger.info(
                            "device %s - sensor: %s value: %s",
                            device.name,
                            reading.sensor_type.name,
                            reading.value,
                        )
