"""Integration 101 Template integration using DataUpdateCoordinator."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
    CONF_HOST,
    CONF_PASSWORD,
#    CONF_SCAN_INTERVAL,
#    CONF_USERNAME,
)
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

#from .api import API, APIAuthError, Device, DeviceType
#from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class APIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[Device]


class DataCoordinator(DataUpdateCoordinator):
    """My example coordinator."""

    data: APIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Set variables from values entered in config flow setup
        self.port = config_entry.data[CONF_PORT]
        self.host = config_entry.data[CONF_HOST]
        self.pwd = config_entry.data[CONF_PASSWORD]

        # set variables from options.  You need a default here incase options have not been set
#        self.poll_interval = config_entry.options.get(
#            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
#        )

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            # Method to call on every update interval.
#            update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            # Using config option here but you can just use a value.
#            update_interval=timedelta(seconds=self.poll_interval),
        )

        # Initialise your api here
        self.api = API(host=self.host, user=self.user, pwd=self.pwd)

    def get_device_by_id(
        self, device_type: DeviceType, device_id: int
    ) -> Device | None:
        """Return device by device id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        try:
            return [
                device
                for device in self.data.devices
                if device.device_type == device_type and device.device_id == device_id
            ][0]
        except IndexError:
            return None
