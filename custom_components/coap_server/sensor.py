"""Interfaces with the Integration 101 Template api sensors."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyConfigEntry
from .const import DOMAIN
from .coordinator import ExampleCoordinator
from .models import CoAPDevice, CoAPSensor
from .entity import async_setup_entity_entry_helper

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Sensors."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        CoAPSensorEntity,
        SensorDeviceClass,
        async_add_entities,
    )


class CoAPSensorEntity(CoordinatorEntity, SensorEntity):
    """Implementation of a sensor."""

    def __init__(self, coordinator: ExampleCoordinator, device: CoAPDevice, sensor: CoAPSensor) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.sensor = sensor
        self.device_id = device.id
        self.manufacturer = device.manufacturer
        self.model = device.model
        self.sw_version = device.sw_version
        self._attr_device_class = sensor.type.value
        self.id = sensor.id
        self._unique_id = f"{DOMAIN}-{device.unique_id}-{sensor.id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        sensor = self.coordinator.get_sensor_by_id(self.device_id, self.id)
        if sensor is None:
            # Device/sensor no longer present in the coordinator (e.g. removed via the UI).
            # Don't null out self.sensor - that would crash native_value/device_class on
            # the next state write and show the entity as "unavailable".
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
        """Return True if entity is available."""
        return super().available and self.sensor is not None

    @property
    def device_class(self) -> str:
        """Return device class."""
        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-device-classes
        return self.sensor.type.value

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the indentifiers parameter.
        # If your device connects via another device, add via_device parameter with the indentifiers of that device.
        return DeviceInfo(
            name=f"{self.device_id}",
            manufacturer=self.manufacturer,
            model=self.model,
            sw_version=self.sw_version,
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.data.controller_name}-{self.device_id}",
                )
            },
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.sensor.name

    @property
    def native_value(self) -> StateType:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        return self.sensor.state


    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of temperature."""
        return self.sensor.unit

#    @property
#    def state_class(self) -> str | None:
#        """Return state class."""
#        # https://developers.home-assistant.io/docs/core/entity/sensor/#available-state-classes
#        return SensorStateClass.MEASUREMENT

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return self._unique_id
