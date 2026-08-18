"""Data models shared across the ha_coap_service integration."""
import logging
from calendar import c
from dataclasses import dataclass, field
from typing import Callable, Any
from enum import StrEnum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.typing import StateType
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.helpers.typing import StateType

from . import coap_pb2 as coap_pb2

_LOGGER = logging.getLogger(__name__)

def _coerce_binary_state(value) -> bool:
    """Coerce an incoming raw sensor value into a bool for binary sensors."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "on", "open", "yes", "detected")
    return bool(value)

def _safe_enum_lookup(enum_cls: type[Any], value: str | None) -> Any | None:
    """Safely convert a string to a Home Assistant DeviceClass enum, avoiding ValueError crashes."""
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None

def _find_enum_value(enum_cls: Any, possible_names: list[str]) -> int | None:
    """Safely find an enum integer value from a list of candidate names."""
    for name in possible_names:
        try:
            if hasattr(enum_cls, name):
                return int(getattr(enum_cls, name))
        except (ValueError, AttributeError):
            continue
    return None

class CoAPSensorConvert:
    """Centralized registry for converting CoAP types to Home Assistant device classes.

    Uses safe dynamic lookup to prevent protobuf attribute errors on import.
    """

    @classmethod
    def _get_converters(cls) -> dict[int, Callable[[str | None], Any]]:
        """Dynamically build converter map using resolved protobuf enum values."""
        converters = {}

        sensor_val = _find_enum_value(coap_pb2.EntityType, ["SENSOR", "ENTITY_SENSOR", "ENTITY_TYPE_SENSOR"])
        if sensor_val is not None:
            converters[sensor_val] = lambda sub: _safe_enum_lookup(SensorDeviceClass, sub)

        binary_val = _find_enum_value(coap_pb2.EntityType, ["BINARY_SENSOR", "ENTITY_BINARY_SENSOR", "ENTITY_TYPE_BINARY_SENSOR"])
        if binary_val is not None:
            converters[binary_val] = lambda sub: _safe_enum_lookup(BinarySensorDeviceClass, sub)

        switch_val = _find_enum_value(coap_pb2.EntityType, ["SWITCH", "ENTITY_SWITCH", "ENTITY_TYPE_SWITCH"])
        if switch_val is not None:
            converters[switch_val] = lambda sub: _safe_enum_lookup(SwitchDeviceClass, sub)

        light_val = _find_enum_value(coap_pb2.EntityType, ["LIGHT", "ENTITY_LIGHT", "ENTITY_TYPE_LIGHT"])
        if light_val is not None:
            converters[light_val] = lambda _: None

        unspecified_val = _find_enum_value(coap_pb2.EntityType, ["UNSPECIFIED", "ENTITY_TYPE_UNSPECIFIED", "ZERO"])
        if unspecified_val is not None:
            converters[unspecified_val] = lambda _: None

        return converters

    @classmethod
    def convert(
        cls, sensor_type: int, sub_type: str | None = None
    ) -> SensorDeviceClass | BinarySensorDeviceClass | SwitchDeviceClass | None:
        """Convert coarse sensor type and sub-type into a native HA Device Class."""
        converters = cls._get_converters()
        converter = converters.get(sensor_type)
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
    def from_coap_update_proto(cls, entity: EntityValue) -> CoAPSensor:
        """Factory method to parse a CoAP protobuf sensor update payload cleanly."""

        return cls(
            id=entity.id,
            state=entity.value,
            name=None,
            type=None,
            unit=None,
            state_class=None,
        )

    @classmethod
    def from_coap_proto(cls, entity: coap_pb2.NewEntity) -> CoAPSensor:
        """Factory method to parse a CoAP protobuf sensor payload cleanly."""

        return cls(
            id=entity.id,
            state=entity.value,
            name=entity.name,
            type=CoAPSensorConvert.convert(entity.type, entity.sub_type),
            unit=entity.unit,
            state_class=_safe_enum_lookup(SensorStateClass, None),
        )

    @classmethod
    def from_coap_raw_proto(cls, raw: bytes|None) -> CoAPSensor:
        """Factory method to parse a CoAP protobuf sensor payload cleanly."""
        if raw is None:
            raise ValueError("Raw protobuf data cannot be None.")
        entity = coap_pb2.NewEntity()
        entity.ParseFromString(raw)

        return cls(
            id=entity.id,
            state=entity.value,
            name=entity.name,
            type=CoAPSensorConvert.convert(entity.type, entity.sub_type),
            unit=entity.unit,
            state_class=_safe_enum_lookup(SensorStateClass, None),
        )

    @classmethod
    def from_dict(cls, raw_data: dict[str, Any]) -> CoAPSensor:
        """Factory method to parse a raw JSON sensor payload cleanly."""
        sensor_type_str = raw_data.get("type")
        sub_type = raw_data.get("sub_type")

        return cls(
            id=raw_data.get("id"),
            state=raw_data.get("value"),
            name=raw_data.get("name"),
            type=CoAPSensorConvert.convert(sensor_type_str, sub_type),
            unit=raw_data.get("unit"),
            state_class=_safe_enum_lookup(SensorStateClass, raw_data.get("state_class")),
        )

    @classmethod
    def to_dict(cls, sensor: CoAPSensor) -> dict[str, Any]:
        """Convert a CoAPSensor instance back to a dictionary."""
        # Determine the coarse category type based on what class the device class belongs to
        sensor_type_str = "sensor"  # Default to "other"
        if isinstance(sensor.type, SensorDeviceClass):
            sensor_type_str = "sensor"
        elif isinstance(sensor.type, BinarySensorDeviceClass):
            sensor_type_str = "binary_sensor"
        elif isinstance(sensor.type, SwitchDeviceClass):
            sensor_type_str = "switch"

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
    def from_coap_raw_update_proto(cls, raw: bytes|None) -> CoAPDevice:
        """Factory method to parse a CoAP protobuf device update payload cleanly."""
        if raw is None:
            raise ValueError("Raw protobuf data cannot be None.")
        proto_device = coap_pb2.UpdateDevice()
        proto_device.ParseFromString(raw)

        return cls(
            id=proto_device.id,
            unique_id=None,
            name=None,
            model=None,
            manufacturer=None,
            sw_version=None,
            hw_version=None,
            sensors=[CoAPSensor.from_coap_update_proto(entity) for entity in proto_device.entities],
        )

    @classmethod
    def from_coap_raw_new_proto(cls, raw: bytes|None) -> CoAPDevice:
        """Factory method to parse a CoAP protobuf device payload cleanly."""
        if raw is None:
            raise ValueError("Raw protobuf data cannot be None.")
        proto_device = coap_pb2.NewDevice()
        proto_device.ParseFromString(raw)

        return cls(
            id=proto_device.id,
            unique_id=proto_device.id,
            name=proto_device.id,
            model=proto_device.model,
            manufacturer=proto_device.manufacturer,
            sw_version=proto_device.fw_version,
            hw_version=proto_device.hw_version,
            sensors=[CoAPSensor.from_coap_proto(entity) for entity in proto_device.entities],
        )

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
    def from_coap_proto(cls, entity: EntityValue) -> CoAPObserveValue:
        """Factory method to parse a CoAP protobuf observe value payload cleanly."""
        return cls(
            id=entity.id,
            state=entity.value
        )

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

    @classmethod
    def to_proto(cls, response: CoAPObserveResponse) -> bytes | None:
        """Convert a CoAPObserveResponse instance to a protobuf message."""
        proto_response = coap_pb2.ObserveDeviceResponse()
        for sensor in response.sensors:
            proto_response.entities.add(id=sensor.id if sensor.id is not None else 0, value=sensor.state if sensor.state is not None else "")
        return proto_response.SerializeToString()

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

    @classmethod
    def from_proto(cls, raw: bytes | None) -> CoAPObserveRequest:
        """Factory method to parse a protobuf observe request payload cleanly."""
        if raw is None:
            raise ValueError("Raw protobuf data cannot be None.")

        proto = coap_pb2.ObserveDevice()
        proto.ParseFromString(raw)
        return cls(
            id=proto.id,
            sensors=[sensor.id for sensor in proto.entities]
        )
