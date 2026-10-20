"""Firmware update entities for CoAP devices."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import get_device_info

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import MyConfigEntry
    from .coordinator import ExampleCoordinator
    from .models import CoAPDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up firmware update entities for registered devices."""
    coordinator: ExampleCoordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        CoAPFirmwareUpdate(coordinator, device)
        for device in coordinator.data.devices
        if device.firmware_url
    )

    @callback
    def _add_new_device(device: CoAPDevice) -> None:
        if device.firmware_url:
            async_add_entities([CoAPFirmwareUpdate(coordinator, device)])

    unsub = async_dispatcher_connect(
        hass, f"{DOMAIN}_{config_entry.entry_id}_new_device", _add_new_device
    )
    config_entry.async_on_unload(unsub)


class CoAPFirmwareUpdate(CoordinatorEntity, UpdateEntity):
    """Expose a firmware update link registered by a CoAP device."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, coordinator: ExampleCoordinator, device: CoAPDevice) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self.device = device
        self.device_id = device.id
        self._firmware_url = device.firmware_url
        self._attr_unique_id = f"{device.id}_firmware_update"
        self._attr_device_info = get_device_info(coordinator, device)
        self._attr_installed_version = device.sw_version
        self._attr_release_url = device.firmware_url

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest data from the coordinator."""
        device = self.coordinator.get_device_by_id(self.device_id)
        if device is None:
            _LOGGER.debug(
                "No coordinator data for device %s update entity; keeping last known state",
                self.device_id,
            )
            return
        self.device = device
        self.async_write_ha_state()

    # @property
    # def has_update(self) -> bool:
    #     """Return whether the device registered an available firmware image."""
    #     return True #self.device.sw_version != self.device.latest_sw_version

    @property
    def installed_version(self) -> str | None:
        """Return the installed firmware version."""
        return self.device.sw_version

    @property
    def latest_version(self) -> str | None:
        """Return the newest firmware version."""
        return self.device.latest_sw_version

    @property
    def in_progress(self) -> bool:
        """Return whether the firmware is being installed."""
        return self.device.update_in_progress

    @property
    def update_percentage(self) -> int | None:
        """Return the install progress."""
        return self.device.update_progress

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if not self.device.firmware_url:
            _LOGGER.error(
                "Device %s does not have a firmware URL; cannot install update",
                self.device_id,
            )
            return
        await self.coordinator.install_firmware(self.device, self.device.firmware_url)
