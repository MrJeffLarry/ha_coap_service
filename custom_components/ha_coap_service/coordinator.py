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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import Device, DeviceType

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

        # Initialise DataUpdateCoordinator (push-based: no polling interval)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
        )

        # Seed with empty data so async_config_entry_first_refresh() succeeds
        #self.async_set_updated_data(APIData(controller_name="ha_coap_service", devices=[]))

    def push_device_data(self, device: Device) -> bool:
        """Called by the CoAP API to push updated device data into the coordinator.

        This triggers all subscribed entities to refresh their state.
        """
        devices = self.data.devices if self.data else []
        found = False
        # Update the device in the list if it exists, otherwise add it
        for i, existing_device in enumerate(devices):
            if (
                existing_device.device_type == device.device_type
                and existing_device.device_id == device.device_id
            ):
                devices[i] = device
                found = True
                break
            else:
                devices.append(device)
        self.async_set_updated_data(APIData(controller_name="ha_coap_service", devices=devices))
        return found


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
