import logging
from typing import Any, override

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyConfigEntry
from .coordinator import ExampleCoordinator
from .entity import async_setup_entity_entry_helper, get_device_info
from .models import CoAPDevice, CoAPSensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switches."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        CoAPSwitch,
        SwitchDeviceClass,
        async_add_entities,
    )


class CoAPSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Representation of a CoAP switch."""

    def __init__(
        self, coordinator: ExampleCoordinator, device: CoAPDevice, sensor: CoAPSensor
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.sensor = sensor
        self.device_id = device.id
        self.id = sensor.id
        self._attr_device_class = sensor.type.value
        self._attr_is_on = sensor.state
        self._attr_unique_id = f"{self.device_id}_{self.id}"
        self._attr_device_info = get_device_info(coordinator, device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the switch with the latest data from the coordinator."""
        sensor = self.coordinator.get_sensor_by_id(self.device_id, self.id)
        if sensor is None:
            _LOGGER.debug(
                "No coordinator data for device %s sensor %s; keeping last known state",
                self.device_id,
                self.id,
            )
            return
        self.sensor = sensor
        self._attr_is_on = sensor.state
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self.sensor.name

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._attr_is_on = True
        self.coordinator.update_sensor_data(self.device_id, self.id, True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._attr_is_on = False
        self.coordinator.update_sensor_data(self.device_id, self.id, False)
        self.async_write_ha_state()
