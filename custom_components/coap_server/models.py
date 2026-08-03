"""Data models shared across the ha_coap_service integration."""

from dataclasses import dataclass, field
from enum import StrEnum

from homeassistant.components.sensor import SensorStateClass
from homeassistant.helpers.typing import StateType


class CoAPDeviceType(StrEnum):
    """Device types."""

    TEMP_SENSOR = "temp_sensor"
    DOOR_SENSOR = "door_sensor"
    OTHER = "other"


class CoAPSensor:
    """Device sensor."""

    name: str
    type: SensorStateClass
    state: StateType


@dataclass
class CoAPDevice:
    """API device."""

    device_id: int | None
    device_unique_id: str
    device_type: CoAPDeviceType = CoAPDeviceType.OTHER
    name: str = "Unknown Device"
    model: str = "Unknown Model"
    manufacturer: str = "hagerman"
    sw_version: str = "1.0.0"
    hw_version: str = "1.0.0"
    state: int | bool = 0
    sensors: list[CoAPSensor] = field(default_factory=list)
