from unittest.mock import MagicMock, PropertyMock


def mock_device(device_id, name, is_online=True, device_type_name=None, uuid=None):
    """Mock Canary Device class."""
    device = MagicMock()
    type(device).device_id = PropertyMock(return_value=device_id)
    type(device).name = PropertyMock(return_value=name)
    type(device).is_online = PropertyMock(return_value=is_online)
    type(device).device_type = PropertyMock(
        return_value={"id": 1, "name": device_type_name}
    )
    type(device).uuid = PropertyMock(return_value=uuid)

    return device
