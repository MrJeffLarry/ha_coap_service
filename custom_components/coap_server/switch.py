import logging
from typing import Any, override

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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass, SwitchEntityDescription

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
        CoAPSwitch,
        SwitchDeviceClass,
        async_add_entities,
    )

class CoAPSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Representation of a switch that can be toggled using MQTT."""

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
        self._attr_unique_id = f"{DOMAIN}-{device.unique_id}-{sensor.id}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.data.controller_name}-{self.device_id}",
                )
            }
        )

#    _default_name = DEFAULT_NAME
#    _entity_id_format = switch.ENTITY_ID_FORMAT

#    _optimistic: bool
#    _is_on_map: dict[str | bytes | bytearray, bool | None]
#    _command_template: Callable[[PublishPayloadType], PublishPayloadType]
#    _value_template: Callable[[ReceivePayloadType], ReceivePayloadType]

#    @staticmethod
#    @override
#    def config_schema() -> vol.Schema:
#        """Return the config schema."""
#        return DISCOVERY_SCHEMA

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
        self._attr_is_on = sensor.state
        self.async_write_ha_state()

#    @callback
#    def _state_message_received(self, msg: ReceiveMessage) -> None:
#        """Handle new MQTT state messages."""
#        if (payload := self._value_template(msg.payload)) in self._is_on_map:
#            self._attr_is_on = self._is_on_map[payload]

#    @callback
#    @override
#    def _prepare_subscribe_topics(self) -> None:
#        """(Re)Subscribe to topics."""
#        if not self.add_subscription(
#            CONF_STATE_TOPIC, self._state_message_received, {"_attr_is_on"}
#        ):
#            # Force into optimistic mode.
#            self._optimistic = True
#            return

#    @override
#    async def _subscribe_topics(self) -> None:
#        """(Re)Subscribe to topics."""
#        subscription.async_subscribe_topics_internal(self.hass, self._sub_state)
#
#        if self._optimistic and (last_state := await self.async_get_last_state()):
#            self._attr_is_on = last_state.state == STATE_ON

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.sensor.name

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on.

        This method is a coroutine.
        """
#        payload = self._command_template(self._config[CONF_PAYLOAD_ON])
#        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)
#        if self._optimistic:
            # Optimistically assume that switch has changed state.
        self._attr_is_on = True
        self.coordinator.update_sensor_data(self.device_id, self.id, True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off.

        This method is a coroutine.
        """
#        payload = self._command_template(self._config[CONF_PAYLOAD_OFF])
#        await self.async_publish_with_config(self._config[CONF_COMMAND_TOPIC], payload)
#        if self._optimistic:
            # Optimistically assume that switch has changed state.
        self._attr_is_on = False
        self.coordinator.update_sensor_data(self.device_id, self.id, False)
        self.async_write_ha_state()
