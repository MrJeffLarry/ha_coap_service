"""Data models shared across the ha_coap_service integration."""

from dataclasses import dataclass, field
from enum import StrEnum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers.typing import StateType


class CoAPDeviceType(StrEnum):
    """Device types."""

    TEMP_SENSOR = "sensor"
    DOOR_SENSOR = "binary"
    OTHER = "other"


@dataclass
class CoAPSensor:
    """Device sensor."""

    id: int
    state: StateType
    name: str | None = None
    type: SensorDeviceClass | BinarySensorDeviceClass | None = None
    unit: str | None = None
    state_class: SensorStateClass | None = None


@dataclass
class CoAPDevice:
    """API device."""

    id: str | None
    unique_id: str | None = None
    name: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    sw_version: str | None = None
    hw_version: str | None = None
    sensors: list[CoAPSensor] = field(default_factory=list)
