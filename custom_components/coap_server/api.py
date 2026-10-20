"""API Placeholder.

You should create your api seperately and have it hosted on PYPI.  This is included here for the sole purpose
of making this example code executable.
"""

from random import choice, randrange
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
import logging

from .models import CoAPDevice, CoAPDeviceType

_LOGGER = logging.getLogger(__name__)

DEVICES: list[CoAPDevice] = []


class API:
    """Class for example API."""

    def __init__(self, host: str, user: str, pwd: str) -> None:
        """Initialise."""
        self.host = host
        self.user = user
        self.pwd = pwd
        self.connected: bool = False

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.host.replace(".", "_")

    def connect(self) -> bool:
        """Connect to api."""
        if self.user == "test" and self.pwd == "1234":
            self.connected = True
            return True
        raise APIAuthError("Error connecting to api. Invalid username or password.")

    def disconnect(self) -> bool:
        """Disconnect from api."""
        self.connected = False
        return True

    def get_devices(self) -> list[CoAPDevice]:
        """Get devices on api."""
        devices = DEVICES
        for device in devices:
            for sensor in device.sensors:
                if sensor.type == SensorDeviceClass.TEMPERATURE:
                    sensor.state = randrange(15, 28)
                elif sensor.type == BinarySensorDeviceClass.DOOR:
                    sensor.state = choice([True, False])
        return devices

    def get_device_unique_id(self, device_id: str, device_type: CoAPDeviceType) -> str:
        """Return a unique device id."""
        if device_type == CoAPDeviceType.DOOR_SENSOR:
            return f"{self.controller_name}_D{device_id}"
        if device_type == CoAPDeviceType.TEMP_SENSOR:
            return f"{self.controller_name}_T{device_id}"
        return f"{self.controller_name}_Z{device_id}"

    def get_device_name(self, device_id: str, device_type: CoAPDeviceType) -> str:
        """Return the device name."""
        if device_type == CoAPDeviceType.DOOR_SENSOR:
            return f"DoorSensor{device_id}"
        if device_type == CoAPDeviceType.TEMP_SENSOR:
            return f"TempSensor{device_id}"
        return f"OtherSensor{device_id}"

    def get_device_value(
        self, device_id: str, device_type: CoAPDeviceType
    ) -> int | bool:
        """Get device random value."""
        if device_type == CoAPDeviceType.DOOR_SENSOR:
            return choice([True, False])
        if device_type == CoAPDeviceType.TEMP_SENSOR:
            return randrange(15, 28)
        return randrange(1, 10)


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""
