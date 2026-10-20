import logging
from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyConfigEntry
from .coordinator import ExampleCoordinator
from .entity import async_setup_entity_entry_helper, get_device_info
from .models import CoAPDevice, CoAPSensor, LightDeviceClass

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lights."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        CoAPLight,
        LightDeviceClass,
        async_add_entities,
    )


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        return 0


class CoAPLight(CoordinatorEntity, LightEntity, RestoreEntity):
    """Representation of a CoAP light (on/off, brightness or RGB)."""

    def __init__(
        self, coordinator: ExampleCoordinator, device: CoAPDevice, sensor: CoAPSensor
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self.sensor = sensor
        self.device_id = device.id
        self.id = sensor.id
        self._light_class = sensor.type
        if self._light_class == LightDeviceClass.RGB:
            self._attr_supported_color_modes = {ColorMode.RGB}
            self._attr_color_mode = ColorMode.RGB
        elif self._light_class == LightDeviceClass.BRIGHTNESS:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF
        self._attr_unique_id = f"{self.device_id}_{self.id}"
        self._attr_device_info = get_device_info(coordinator, device)
        self._apply_state(sensor.state)

    def _apply_state(self, state: Any) -> None:
        value = _to_int(state)
        self._attr_is_on = value != 0
        if self._light_class == LightDeviceClass.RGB:
            value &= 0xFFFFFF
            self._attr_is_on = value != 0
            if value:
                r, g, b = (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF
                peak = max(r, g, b)
                # HA expects rgb_color at full intensity and brightness separately
                self._attr_brightness = peak
                self._attr_rgb_color = (
                    round(r * 255 / peak),
                    round(g * 255 / peak),
                    round(b * 255 / peak),
                )
        elif self._light_class == LightDeviceClass.BRIGHTNESS:
            if value:
                self._attr_brightness = max(0, min(255, value))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the light with the latest data from the coordinator."""
        sensor = self.coordinator.get_sensor_by_id(self.device_id, self.id)
        if sensor is None:
            _LOGGER.debug(
                "No coordinator data for device %s sensor %s; keeping last known state",
                self.device_id,
                self.id,
            )
            return
        self.sensor = sensor
        self._apply_state(sensor.state)
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self.sensor.name

    def _push(self, value: int) -> None:
        self.coordinator.update_sensor_data(self.device_id, self.id, value)
        self._apply_state(value)
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if self._light_class == LightDeviceClass.RGB:
            color = kwargs.get(ATTR_RGB_COLOR)
            brightness = kwargs.get(ATTR_BRIGHTNESS)
            if color is None:
                color = getattr(self, "_attr_rgb_color", None) or (255, 255, 255)
                if brightness is None:
                    brightness = getattr(self, "_attr_brightness", None) or 255
            if brightness is not None:
                peak = max(color) or 1
                color = tuple(round(c * brightness / peak) for c in color)
            r, g, b = (max(0, min(255, int(c))) for c in color)
            value = (r << 16) | (g << 8) | b
            if value == 0:
                value = 0xFFFFFF
        elif self._light_class == LightDeviceClass.BRIGHTNESS:
            value = (
                kwargs.get(ATTR_BRIGHTNESS)
                or getattr(self, "_attr_brightness", None)
                or 255
            )
        else:
            value = 1
        self._push(int(value))

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._push(0)
