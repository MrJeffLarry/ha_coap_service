import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ExampleCoordinator
from .models import CoAPDevice

_LOGGER = logging.getLogger(__name__)


def get_device_info(coordinator: ExampleCoordinator, device: CoAPDevice) -> DeviceInfo:
    """Return the registry information for a CoAP device."""
    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                f"{coordinator.data.controller_name}-{device.id}",
            )
        },
        name=device.name or device.id or "CoAP device",
        manufacturer=device.manufacturer,
        model=device.model,
        sw_version=device.sw_version,
        hw_version=device.hw_version,
    )


@callback
def async_setup_entity_entry_helper(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_class: type[CoordinatorEntity],
    entity_type: type | tuple[type, ...],
    async_add_entities: AddEntitiesCallback,
) -> None:

    coordinator: ExampleCoordinator = config_entry.runtime_data.coordinator
    sensors = []
    for device in coordinator.data.devices:
        for sensor in device.sensors:
            if isinstance(sensor.type, entity_type):
                _LOGGER.info(
                    "Adding new device data for sensor: %s type %s match %s",
                    sensor.name,
                    type(sensor.type).__name__,
                    entity_class.__name__,
                )
                sensors.append(entity_class(coordinator, device, sensor))
            else:
                _LOGGER.debug(
                    "Skipping sensor: %s type %s does not match %s",
                    sensor.name,
                    type(sensor.type).__name__,
                    entity_class.__name__,
                )

    _LOGGER.info(
        "Adding new device data for %s sensors: %s",
        len(sensors),
        [sensor.name for sensor in sensors],
    )

    # Create the sensors.
    async_add_entities(sensors)

    # Callback to dynamically add new entities
    async def _add_new_device(device):
        if not device.id or not device.sensors:
            return

        new_entities = []
        for sensor in device.sensors:
            if isinstance(sensor.type, entity_type):
                _LOGGER.info(
                    "Adding new device data for sensor: %s type %s match %s",
                    sensor.name,
                    type(sensor.type).__name__,
                    entity_class.__name__,
                )
                new_entities.append(entity_class(coordinator, device, sensor))
            else:
                _LOGGER.debug(
                    "Skipping sensor: %s type %s does not match %s",
                    sensor.name,
                    type(sensor.type).__name__,
                    entity_class.__name__,
                )
        async_add_entities(new_entities)

    # Signal is scoped to this config entry, and the subscription is torn down
    # when the entry unloads/reloads - otherwise listeners from stale/previous
    # setups of this integration keep firing and try to add entities against
    # config entries that no longer exist.
    unsub = async_dispatcher_connect(
        hass, f"{DOMAIN}_{config_entry.entry_id}_new_device", _add_new_device
    )
    config_entry.async_on_unload(unsub)
