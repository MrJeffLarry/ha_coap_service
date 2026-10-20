from enum import StrEnum

import pytest

from . import coap_pb2
from .models import (
    CoAPDevice,
    CoAPObserveRequest,
    CoAPObserveResponse,
    CoAPObserveValue,
    CoAPSensor,
)

# Try importing Home Assistant classes; fall back to safe mocks in isolation.
try:
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass
    from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
    from homeassistant.components.switch import SwitchDeviceClass
    from homeassistant.helpers.typing import StateType
except ImportError:

    class SensorDeviceClass(StrEnum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        CO2 = "co2"
        BATTERY = "battery"
        PRESSURE = "atmospheric_pressure"

    class BinarySensorDeviceClass(StrEnum):
        CONNECTIVITY = "connectivity"
        MOTION = "motion"
        SAFETY = "safety"

    class SwitchDeviceClass(StrEnum):
        SWITCH = "switch"
        OUTLET = "outlet"

    class SensorStateClass(StrEnum):
        MEASUREMENT = "measurement"
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"

    type StateType = str | int | float | bool | None


def test_coap_sensor_from_and_to_dict() -> None:
    """Test serializing and deserializing a CoAPSensor."""
    raw_data = {
        "id": "sensor_temp",
        "value": 23.5,
        "name": "Indoor Temperature",
        "type": "sensor",
        "sub_type": "temperature",
        "unit": "°C",
        "state_class": "measurement",
    }

    # 1. Test from_dict
    sensor = CoAPSensor.from_dict(raw_data)
    assert sensor.id == "sensor_temp"
    assert sensor.state == 23.5
    assert sensor.name == "Indoor Temperature"
    assert sensor.type == SensorDeviceClass.TEMPERATURE
    assert sensor.unit == "°C"
    assert sensor.state_class == SensorStateClass.MEASUREMENT

    # 2. Test to_dict
    serialized = CoAPSensor.to_dict(sensor)
    assert serialized["id"] == "sensor_temp"
    assert serialized["value"] == 23.5
    assert serialized["name"] == "Indoor Temperature"
    assert serialized["sub_type"] == "temperature"
    assert serialized["unit"] == "°C"
    assert serialized["state_class"] == "measurement"


def test_coap_device_from_and_to_dict() -> None:
    """Test serializing and deserializing a CoAPDevice with nested sensors."""
    raw_data = {
        "id": "device001",
        "unique_id": "coap_device001",
        "name": "nRF52 Node",
        "model": "nRF52833",
        "manufacturer": "hagerman",
        "sw_version": "1.0.0",
        "hw_version": "1.0.0",
        "sensors": [
            {
                "id": "humidity_1",
                "value": 45,
                "name": "Humidity",
                "type": "sensor",
                "sub_type": "humidity",
                "unit": "%",
                "state_class": "measurement",
            }
        ],
    }

    # 1. Test from_dict
    device = CoAPDevice.from_dict(raw_data)
    assert device.id == "device001"
    assert device.manufacturer == "hagerman"
    assert len(device.sensors) == 1
    assert device.sensors[0].type == SensorDeviceClass.HUMIDITY

    # 2. Test to_dict
    serialized = CoAPDevice.to_dict(device)
    assert serialized["id"] == "device001"
    assert serialized["manufacturer"] == "hagerman"
    assert len(serialized["sensors"]) == 1
    assert serialized["sensors"][0]["sub_type"] == "humidity"


def test_coap_device_from_new_proto() -> None:
    """Test parsing a new device from its protobuf representation."""
    raw_device = coap_pb2.NewDevice(
        version=1,
        id="device002",
        manufacturer="Acme",
        model="Sensor Node",
        fw_version="2.0.0",
        hw_version="1.0",
    )
    raw_device.entities.add(
        id=7,
        value=23.5,
        type=coap_pb2.ENTITY_TYPE_SENSOR,
        sub_type="temperature",
        unit="°C",
        name="Temperature",
    )

    device = CoAPDevice.from_coap_raw_new_proto(raw_device.SerializeToString())

    assert device.id == "device002"
    assert device.unique_id == "device002"
    assert device.manufacturer == "Acme"
    assert device.model == "Sensor Node"
    assert device.sw_version == "2.0.0"
    assert device.hw_version == "1.0"
    assert len(device.sensors) == 1
    assert device.sensors[0].id == 7
    assert device.sensors[0].state == 23.5
    assert device.sensors[0].name == "Temperature"
    assert device.sensors[0].type == SensorDeviceClass.TEMPERATURE
    assert device.sensors[0].unit == "°C"


@pytest.mark.parametrize(
    ("entity_type", "sub_type", "expected_class"),
    [
        *[
            (coap_pb2.ENTITY_TYPE_SENSOR, device_class.value, device_class)
            for device_class in SensorDeviceClass
        ],
        *[
            (coap_pb2.ENTITY_TYPE_BINARY_SENSOR, device_class.value, device_class)
            for device_class in BinarySensorDeviceClass
        ],
        *[
            (coap_pb2.ENTITY_TYPE_SWITCH, device_class.value, device_class)
            for device_class in SwitchDeviceClass
        ],
        pytest.param(
            coap_pb2.ENTITY_TYPE_LIGHT,
            "brightness",
            None,
            id="light",
        ),
        pytest.param(
            coap_pb2.ENTITY_TYPE_UNSPECIFIED,
            "",
            None,
            id="unspecified",
        ),
    ],
)
def test_coap_device_from_new_proto_supports_all_entity_classes(
    entity_type: int,
    sub_type: str,
    expected_class: (
        SensorDeviceClass | BinarySensorDeviceClass | SwitchDeviceClass | None
    ),
) -> None:
    """Test parsing every supported Home Assistant class from a new-device protobuf."""
    raw_device = coap_pb2.NewDevice(id="device003")
    raw_device.entities.add(
        id=1,
        value=1,
        type=entity_type,
        sub_type=sub_type,
    )

    device = CoAPDevice.from_coap_raw_new_proto(raw_device.SerializeToString())

    assert device.sensors[0].type == expected_class

    json_entity_type = {
        coap_pb2.ENTITY_TYPE_SENSOR: "sensor",
        coap_pb2.ENTITY_TYPE_BINARY_SENSOR: "binary_sensor",
        coap_pb2.ENTITY_TYPE_SWITCH: "switch",
        coap_pb2.ENTITY_TYPE_LIGHT: "light",
        coap_pb2.ENTITY_TYPE_UNSPECIFIED: "unspecified",
    }[entity_type]
    restored_sensor = CoAPSensor.from_dict(
        {"id": 1, "value": 1, "type": json_entity_type, "sub_type": sub_type}
    )
    assert restored_sensor.type == expected_class


def test_coap_observe_request_from_proto() -> None:
    """Test parsing an observe request's entity IDs from protobuf."""
    raw_request = coap_pb2.ObserveDevice(
        version=1,
        id="device002",
        entity_ids=[7, 9],
    )

    request = CoAPObserveRequest.from_proto(raw_request.SerializeToString())

    assert request.id == "device002"
    assert request.sensors == [7, 9]


def test_coap_observe_response_to_proto() -> None:
    """Test serializing observe values to the protobuf response format."""
    response = CoAPObserveResponse(
        id="device002",
        sensors=[
            CoAPObserveValue(id=7, state=23.5),
            CoAPObserveValue(id=9, state=42),
        ],
    )

    raw_response = coap_pb2.ObserveDeviceResponse()
    raw_response.ParseFromString(CoAPObserveResponse.to_proto(response))

    assert [(entity.id, entity.value) for entity in raw_response.entities] == [
        (7, 23.5),
        (9, 42.0),
    ]
