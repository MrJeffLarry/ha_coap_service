"""Integration 101 Template integration using DataUpdateCoordinator."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

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

from .models import Device, DeviceType

_LOGGER = logging.getLogger(__name__)

@dataclass
class APIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[Device]


class DataCoordinator(DataUpdateCoordinator[APIData]):
    """My example coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Set variables from values entered in config flow setup
        self.port = config_entry.data[CONF_PORT]
        self.name = "Data Coordinator"
#        self.host = config_entry.data[CONF_HOST]
#        self.pwd = config_entry.data[CONF_PASSWORD]

        # set variables from options.  You need a default here incase options have not been set
#        self.poll_interval = config_entry.options.get(
#            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
#        )

        # Initialise DataUpdateCoordinator (push-based: no polling interval)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            always_update=False,
        )

        # Seed with empty data so async_config_entry_first_refresh() succeeds
        self.async_set_updated_data(
            APIData(controller_name="ha_coap_service", devices=[])
        )

    async def _async_update_data(self) -> APIData: # pyright: ignore[reportIncompatibleMethodOverride]
        """Fetch data from CoAP nodes if needed."""
        # Must return an instance of APIData here
        return self.data

    def push_device_data(self, device: Device) -> bool:
        """Push updated device data into the coordinator.

        Replaces an existing entry with the same unique id, or appends if new.
        Returns True if the device already existed, False if it was newly added.
        """
        # Work on an explicit copy so self.data.devices is never mutated in place
        devices: list[Device] = list(self.data.devices)
        for i, existing in enumerate(devices):
            if (
                existing.device_type == device.device_type
                and existing.device_unique_id == device.device_unique_id
            ):
                devices[i] = device
                _LOGGER.info(
                    "Updated device data for %s %s",
                    device.device_type,
                    device.device_unique_id,
                )
                self.async_set_updated_data(
                    APIData(controller_name="ha_coap_service", devices=devices)
                )
                return True

        _LOGGER.info(
            "Adding new device data for %s %s",
            device.device_type,
            device.device_unique_id,
        )
        devices.append(device)
        self.async_set_updated_data(
            APIData(controller_name="ha_coap_service", devices=devices)
        )
        return False


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
