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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import (
    DOMAIN, SENSORS, ID, MANUFACTURER, SW_VERSION, HW_VERSION, JSON_TYPE, JSON_VALUE
)
from . import AppConfigEntry
from .models import Device, DeviceType, Sensor
from .coordinator import DataCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities
):

    """Set up the Sensors."""
    # This gets the data update coordinator from the config entry runtime data as specified in your __init__.py
    coordinator: DataCoordinator = config_entry.runtime_data.coordinator


    # Enumerate all the sensors in your data value from your DataUpdateCoordinator and add an instance of your sensor class
    # to a list for each one.
    # This maybe different in your specific case, depending on how your data is structured
    sensors = []

    for device in coordinator.data.devices:
        _LOGGER.info("Setting up sensors for device: %s", device.device_id)
        for sensor in device.sensors:
            sensors.append(DeviceSensor(coordinator, device, sensor))

    # Create the sensors.
    async_add_entities(sensors)

    # 1. Restore existing devices saved in config_entry.data (on HA Restart)
#    if SENSORS in config_entry.data:
#        existing_entities = [
#            CoapSensor(config_entry.data, sensor)
#            for sensor in config_entry.data[SENSORS]
#        ]
#        async_add_entities(existing_entities)

    # Callback to dynamically add new entities
    async def _add_new_device(device):
        if not device[ID]:
            return

        new_entities = []
        for sensor in device[SENSORS]:
            new_entities.append(CoapSensor(device, sensor))
        async_add_entities(new_entities)

    async_dispatcher_connect(hass, f"{DOMAIN}_new_device", _add_new_device)


class DeviceSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a sensor."""

    def __init__(self, coordinator: DataCoordinator, device: Device, sensor: Sensor) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.device = device
        self.device_id = device.device_id
        self.sensor = sensor
        self._attr_device_class = sensor.type
        self._state = sensor.state
        self.coordinator = coordinator

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        # This method is called by your DataUpdateCoordinator when a successful update runs.
        self.device = self.coordinator.get_device_by_id(
            self.device.device_type, self.device_id
        )
        _LOGGER.debug("Device: %s", self.device)
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Identifiers are what group entities into the same device.
        # If your device is created elsewhere, you can just specify the indentifiers parameter.
        # If your device connects via another device, add via_device parameter with the indentifiers of that device.
        return DeviceInfo(
            name=f"ExampleDevice{self.device.device_id}",
            manufacturer=self.device.manufacturer,
            model=self.device.model,
            sw_version=self.device.sw_version,
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.data.controller_name}-{self.device.device_id}",
                )
            },
        )

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.device.device_unique_id}"

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        # Add any additional attributes you want on your sensor.
        attrs = {}
        attrs["extra_info"] = "Extra Info"
        return attrs

class CoapSensor(SensorEntity):
    def __init__(self, device, sensor):
        self._state = sensor.get(JSON_VALUE, 0)
        self._device_id = device[ID]
        self._manufacturer = device[MANUFACTURER]
        self._sw_version = device[SW_VERSION]
        self._hw_version = device[HW_VERSION]
        self._attr_device_class = sensor[JSON_TYPE]
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{self._attr_device_class}"
        self._attr_name = f"{self._attr_device_class.capitalize()}"

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device_id)
            },  # Same identifier = Same Device Group
            "name": f"CoAP Device {self._device_id}",
            "manufacturer": self._manufacturer,
            "sw_version": self._sw_version,
            "hw_version": self._hw_version
        }

    @property
    def state(self):
        return self._state

    async def async_added_to_hass(self):
        # Listen for updates specific to this instance
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update_{self._device_id}", self._update_callback
            )
        )

    def _update_callback(self, data):
        for sensor in data.get(SENSORS):
            if sensor.get(JSON_TYPE) == self._attr_device_class:
                self._state = sensor.get(JSON_VALUE)
                self.async_write_ha_state()
                break
