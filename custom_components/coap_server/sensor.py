import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
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
    """Set up the sensors."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        CoAPSensorEntity,
        SensorDeviceClass,
        async_add_entities,
    )


class CoAPSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a CoAP sensor."""

    def __init__(
        self, coordinator: ExampleCoordinator, device: CoAPDevice, sensor: CoAPSensor
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.sensor = sensor
        self.device_id = device.id
        self.id = sensor.id
        self._attr_device_class = sensor.type.value
        self._attr_unique_id = f"{self.device_id}_{self.id}"
        self._attr_device_info = get_device_info(coordinator, device)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC if self.sensor.type.value == SensorDeviceClass.BATTERY else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest data from the coordinator."""
        sensor = self.coordinator.get_sensor_by_id(self.device_id, self.id)
        if sensor is None:
            _LOGGER.debug(
                "No coordinator data for device %s sensor %s; keeping last known state",
                self.device_id,
                self.id,
            )
            return
        self.sensor = sensor
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self.sensor is not None

    @property
    def device_class(self) -> str | None:
        """Return the device class."""
        if self.sensor and self.sensor.type:
            return self.sensor.type.value
        return None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.sensor.name

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        return self.sensor.state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self.sensor.unit
