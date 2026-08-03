"""Integration 101 Template integration using DataUpdateCoordinator."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import API, APIAuthError, Device, DeviceType
from .models import CoAPDevice, CoAPDeviceType, CoAPSensor
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class ExampleAPIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[Device]
    coap_devices: list[CoAPDevice]


class ExampleCoordinator(DataUpdateCoordinator):
    """My example coordinator."""

    data: ExampleAPIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Set variables from values entered in config flow setup
        self.host = config_entry.data[CONF_HOST]
        self.port = config_entry.data[CONF_PORT]
        self.user = config_entry.data[CONF_USERNAME]
        self.pwd = config_entry.data[CONF_PASSWORD]
        self.name = f"{DOMAIN} ({config_entry.unique_id})"

        # set variables from options.  You need a default here incase options have not been set
        self.poll_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass,
            _LOGGER,
            name=self.name,
            # Method to call on every update interval.
            update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            # Using config option here but you can just use a value.
            update_interval=timedelta(seconds=self.poll_interval),
        )

        # Initialise your api here
        self.api = API(host=self.host, user=self.user, pwd=self.pwd)

    def push_device_data(self, device: CoAPDevice) -> bool:
        """Called by the CoAP API to push updated device data into the coordinator.

        This triggers all subscribed entities to refresh their state.
        """
        devices = self.data.coap_devices if self.data else []
        found = False
        # Update the device in the list if it exists, otherwise add it
        for i, existing_device in enumerate(devices):
            if (
                existing_device.device_type == device.device_type
                and existing_device.device_unique_id == device.device_unique_id
            ):
                devices[i] = device
                found = True
                _LOGGER.info(
                    "Updated device data for %s %s",
                    device.device_type,
                    device.device_unique_id,
                )
                break

        if not found:
            _LOGGER.info(
                "Adding new device data for %s %s",
                device.device_type,
                device.device_unique_id,
            )
            devices.append(device)

        self.async_set_updated_data(
            ExampleAPIData(controller_name=self.api.controller_name, devices=self.data.devices, coap_devices=devices) # pyright: ignore[reportArgumentType]
        )
        return found

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            if not self.api.connected:
                await self.hass.async_add_executor_job(self.api.connect)
            devices = await self.hass.async_add_executor_job(self.api.get_devices)
        except APIAuthError as err:
            _LOGGER.error(err)
            raise UpdateFailed(err) from err
        except Exception as err:
            # This will show entities as unavailable by raising UpdateFailed exception
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # What is returned here is stored in self.data by the DataUpdateCoordinator
        return ExampleAPIData(self.api.controller_name, devices, [])

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
