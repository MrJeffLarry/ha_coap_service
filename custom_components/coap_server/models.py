"""Data models shared across the ha_coap_service integration."""

from dataclasses import dataclass, field
from enum import StrEnum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.helpers.typing import StateType


class CoAPDeviceType(StrEnum):
    """Device types."""

    TEMP_SENSOR = "temp_sensor"
    DOOR_SENSOR = "door_sensor"
    OTHER = "other"


@dataclass
class CoAPSensor:
    """Device sensor."""

    id: int
    name: str
    type: SensorDeviceClass | BinarySensorDeviceClass
    state: StateType


@dataclass
class CoAPDevice:
    """API device."""

    id: str | None
    unique_id: str
    name: str = "Unknown Device"
    model: str = "Unknown Model"
    manufacturer: str = "hagerman"
    sw_version: str = "1.0.0"
    hw_version: str = "1.0.0"
    sensors: list[CoAPSensor] = field(default_factory=list)
