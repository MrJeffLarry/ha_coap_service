"""Data models shared across the ha_coap_service integration."""

from dataclasses import dataclass, field
from typing import Callable, Any
from enum import StrEnum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.typing import StateType
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.helpers.typing import StateType

def _coerce_binary_state(value) -> bool:
    """Coerce an incoming raw sensor value into a bool for binary sensors."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "on", "open", "yes", "detected")
    return bool(value)

class CoAPSensorType(StrEnum):
    """High-level device types reported by the CoAP node."""

    SENSOR = "sensor"
    BINARY_SENSOR = "binary"
    SWITCH = "switch"
    LIGHT = "light"
    OTHER = "other"


def _safe_enum_lookup(enum_cls: type[Any], value: str | None) -> Any | None:
    """Safely convert a string to a Home Assistant DeviceClass enum, avoiding ValueError crashes."""
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None


class CoAPSensorConvert:
    """Centralized registry for converting CoAP types to Home Assistant device classes.

    To expand in the future, simply add a new rule to this dictionary.
    """

    _CONVERTERS: dict[CoAPSensorType, Callable[[str | None], Any]] = {
        CoAPSensorType.SENSOR: lambda sub: _safe_enum_lookup(SensorDeviceClass, sub),
        CoAPSensorType.BINARY_SENSOR: lambda sub: _safe_enum_lookup(BinarySensorDeviceClass, sub),
        CoAPSensorType.SWITCH: lambda sub: _safe_enum_lookup(SwitchDeviceClass, sub),
        CoAPSensorType.LIGHT: lambda _: None,   # Handled by light platform if needed
        CoAPSensorType.OTHER: lambda _: None,
    }

    @classmethod
    def convert(
        cls, sensor_type: CoAPSensorType | str, sub_type: str | None = None
    ) -> SensorDeviceClass | BinarySensorDeviceClass | SwitchDeviceClass | None:
        """Convert coarse sensor type and sub-type into a native HA Device Class."""
        try:
            enum_type = CoAPSensorType(sensor_type)
        except ValueError:
            return None

        converter = cls._CONVERTERS.get(enum_type)
        return converter(sub_type) if converter else None


@dataclass
class CoAPSensor:
    """Structured representation of a CoAP node sensor."""

    id: int | None
    state: StateType
    name: str | None = None
    type: SensorDeviceClass | BinarySensorDeviceClass | SwitchDeviceClass | None = None
    unit: str | None = None
    state_class: SensorStateClass | None = None

    @classmethod
    def from_dict(cls, raw_data: dict[str, Any]) -> CoAPSensor:
        """Factory method to parse a raw JSON sensor payload cleanly."""
        sensor_type_str = raw_data.get("type")
        sub_type = raw_data.get("sub_type")

        resolved_device_class = CoAPSensorConvert.convert(sensor_type_str, sub_type)

        return cls(
            id=raw_data.get("id"),
            state=raw_data.get("value"),
            name=raw_data.get("name"),
            type=resolved_device_class,
            unit=raw_data.get("unit"),
            state_class=_safe_enum_lookup(SensorStateClass, raw_data.get("state_class")),
        )

    @classmethod
    def to_dict(cls, sensor: CoAPSensor) -> dict[str, Any]:
        """Convert a CoAPSensor instance back to a dictionary."""
        # Determine the coarse category type based on what class the device class belongs to
        sensor_type_str = CoAPSensorType.OTHER.value  # Default to "other"
        if isinstance(sensor.type, SensorDeviceClass):
            sensor_type_str = CoAPSensorType.SENSOR.value
        elif isinstance(sensor.type, BinarySensorDeviceClass):
            sensor_type_str = CoAPSensorType.BINARY_SENSOR.value
        elif isinstance(sensor.type, SwitchDeviceClass):
            sensor_type_str = CoAPSensorType.SWITCH.value

        return {
            "id": sensor.id,
            "value": sensor.state,
            "name": sensor.name,
            "type": sensor_type_str,
            "sub_type": sensor.type.value if sensor.type else None,
            "unit": sensor.unit,
            "state_class": sensor.state_class.value if sensor.state_class else None,
        }

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

    @classmethod
    def from_dict(cls, raw_data: dict[str, Any]) -> CoAPDevice:
        """Factory method to parse a raw JSON device payload cleanly."""
        return cls(
            id=raw_data.get("id"),
            unique_id=raw_data.get("unique_id"),
            name=raw_data.get("name"),
            model=raw_data.get("model"),
            manufacturer=raw_data.get("manufacturer"),
            sw_version=raw_data.get("sw_version"),
            hw_version=raw_data.get("hw_version"),
            sensors=[CoAPSensor.from_dict(sensor) for sensor in raw_data.get("sensors", [])]
        )

    @classmethod
    def to_dict(cls, device: CoAPDevice) -> dict[str, Any]:
        """Convert a CoAPDevice instance back to a dictionary."""
        return {
            "id": device.id,
            "unique_id": device.unique_id,
            "name": device.name,
            "model": device.model,
            "manufacturer": device.manufacturer,
            "sw_version": device.sw_version,
            "hw_version": device.hw_version,
            "sensors": [CoAPSensor.to_dict(sensor) for sensor in device.sensors],
        }

@dataclass
class CoAPObserveValue:
    """Structured representation of a CoAP observe value."""

    id: int | None
    state: StateType

    @classmethod
    def from_dict(cls, raw_data: dict[Any, Any]) -> CoAPObserveValue:
        """Factory method to parse a raw JSON observe value payload cleanly."""
        id=raw_data.get("id")
        if id is None:
            raise ValueError("Observe value must contain an 'id' field.")
        if not isinstance(id, int):
            raise ValueError(f"Observe value 'id' must be an integer, got {type(id).__name__}.")
        return cls(
            id=int(id),
            state=raw_data.get("value", None)
        )

@dataclass
class CoAPObserveResponse:
    """Structured representation of a CoAP observe response."""

    id: str | None
    sensors: list[CoAPObserveValue] = field(default_factory=list)

    @classmethod
    def from_device(cls, device: CoAPDevice) -> CoAPObserveResponse:
        """Factory method to create an observe response from a CoAPDevice."""
        sensors = device.sensors if device.sensors else []
        return cls(
            id=device.id,
            sensors=[CoAPObserveValue(id=sensor.id, state=sensor.state) for sensor in sensors]
        )

    @classmethod
    def to_dict(cls, response: CoAPObserveResponse) -> dict[str, Any]:
        """Convert a CoAPObserveResponse instance back to a dictionary."""
        return {
            "id": response.id,
            "sensors": [{"id": sensor.id, "value": sensor.state} for sensor in response.sensors],
        }

@dataclass
class CoAPObserveRequest:
    """Structured representation of a CoAP observe request."""

    id: str | None
    sensors: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw_data: dict[str, Any]) -> CoAPObserveRequest:
        """Factory method to parse a raw JSON observe request payload cleanly."""
        return cls(
            id=raw_data.get("id"),
            sensors=[CoAPObserveValue.from_dict(sensor) for sensor in raw_data.get("sensors", [])]
        )
