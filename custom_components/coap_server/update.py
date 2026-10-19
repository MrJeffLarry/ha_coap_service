"""Firmware update entities for CoAP devices."""

from homeassistant.components.update import UpdateEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyConfigEntry
from .const import DOMAIN
from .coordinator import ExampleCoordinator
from .entity import get_device_info
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

    def __init__(self, coordinator: ExampleCoordinator, device: CoAPDevice) -> None:
        """Initialize the firmware update entity."""
        super().__init__(coordinator)
        self._firmware_url = device.firmware_url
        self._attr_unique_id = f"{device.id}_firmware_update"
        self._attr_device_info = get_device_info(coordinator, device)
        self._attr_installed_version = device.sw_version
        self._attr_release_url = device.firmware_url

    @property
    def has_update(self) -> bool:
        """Return whether the device registered an available firmware image."""
        return bool(self._firmware_url)
