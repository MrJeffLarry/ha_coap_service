import pytest
from .models import CoAPSensor, CoAPDevice

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

# Try importing real Home Assistant classes; fall back to safe mocks if running in isolation
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
