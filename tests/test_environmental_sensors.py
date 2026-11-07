"""Tests for generic environmental sensor registration, restoration, and updates."""

from enum import StrEnum
from unittest.mock import MagicMock, Mock

import pytest
from aiocoap import Message
from aiocoap.numbers.codes import Code
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CONF_PORT

from custom_components.coap_server import coap_pb2, entity, models, sensor
from custom_components.coap_server.coordinator import ExampleAPIData, ExampleCoordinator
from custom_components.coap_server.models import CoAPCustomSensorClass, CoAPDevice
from custom_components.coap_server.server import EndpointDevice


MEASUREMENTS = [
    ("temperature", "Temperature", "°C", 21.5, "temperature"),
    ("humidity", "Humidity", "%", 45.0, "humidity"),
    ("pm1", "PM1.0", "μg/m³", 1.0, "pm1"),
    ("pm25", "PM2.5", "μg/m³", 2.5, "pm25"),
    ("pm4", "PM4.0", "μg/m³", 4.0, "pm4"),
    ("pm10", "PM10", "μg/m³", 10.0, "pm10"),
    ("voc_index", "VOC index", "", 100.0, None),
    ("nox_index", "NOx index", "", 1.0, None),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["SEN65", "Another model", None])
async def test_environmental_measurements_registration_restore_and_update(
    monkeypatch: pytest.MonkeyPatch, model: str | None
) -> None:
    """Expose measurements regardless of device model, even when it is omitted."""
    raw_device = coap_pb2.NewDevice(id="environment")
    if model is not None:
        raw_device.model = model
    for entity_id, (sub_type, name, unit, value, _) in enumerate(MEASUREMENTS, 1):
        raw_device.entities.add(
            id=entity_id,
            type=coap_pb2.ENTITY_TYPE_SENSOR,
            sub_type=sub_type,
            name=name,
            unit=unit,
            value=value,
        )
    raw_device.entities.add(
        id=9, type=coap_pb2.ENTITY_TYPE_SENSOR, sub_type="unrecognized"
    )
    coordinator = MagicMock()
    coordinator.data.controller_name = "CoAP"
    coordinator.push_device_data.return_value = False
    response = await EndpointDevice(None, coordinator).render_post(
        Message(payload=raw_device.SerializeToString())
    )
    assert response.code == Code.CREATED
    registered = coordinator.push_device_data.call_args.args[0]
    restored = CoAPDevice.from_dict(CoAPDevice.to_dict(registered))
    assert [item.type for item in restored.sensors] == [
        item.type for item in registered.sensors
    ]

    coordinator.data.devices = [restored]
    config_entry = MagicMock()
    config_entry.runtime_data.coordinator = coordinator
    connect = Mock(return_value=Mock())
    monkeypatch.setattr(entity, "async_dispatcher_connect", connect)
    add_entities = Mock()
    await sensor.async_setup_entry(MagicMock(), config_entry, add_entities)

    entities = add_entities.call_args.args[0]
    assert len(entities) == 8
    for created, (sub_type, name, unit, value, device_class) in zip(
        entities, MEASUREMENTS, strict=True
    ):
        assert created.name == name
        assert created.native_value == value
        assert created.device_class == device_class
        assert created.native_unit_of_measurement == (unit or None)
        if sub_type in ("voc_index", "nox_index"):
            assert created.state_class == SensorStateClass.MEASUREMENT

    callback = connect.call_args.args[2]
    await callback(registered)
    assert len(add_entities.call_args.args[0]) == 8

    for created in entities:
        updated_sensor = restored.sensors[created.id - 1]
        updated_sensor.state += 1
        coordinator.get_sensor_by_id.return_value = updated_sensor
        created.async_write_ha_state = Mock()
        created._handle_coordinator_update()
        assert created.native_value == updated_sensor.state
        created.async_write_ha_state.assert_called_once()


def test_pm4_falls_back_when_home_assistant_has_no_device_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep PM4 available on Home Assistant versions without its device class."""

    class OlderSensorDeviceClass(StrEnum):
        TEMPERATURE = "temperature"

    monkeypatch.setattr(models, "SensorDeviceClass", OlderSensorDeviceClass)
    proto = coap_pb2.NewDevice(id="environment")
    proto.entities.add(
        id=1,
        type=coap_pb2.ENTITY_TYPE_SENSOR,
        sub_type="pm4",
        unit="μg/m³",
        value=4.0,
    )
    device = CoAPDevice.from_coap_raw_new_proto(proto.SerializeToString())
    restored = CoAPDevice.from_dict(CoAPDevice.to_dict(device))
    assert restored.sensors[0].type is CoAPCustomSensorClass.PM4

    coordinator = MagicMock()
    coordinator.data.controller_name = "CoAP"
    created = sensor.CoAPSensorEntity(coordinator, restored, restored.sensors[0])
    assert created.device_class is None
    assert created.native_unit_of_measurement == "μg/m³"
    assert created.native_value == 4.0
    assert created.state_class == SensorStateClass.MEASUREMENT


@pytest.mark.asyncio
async def test_environmental_put_updates_coordinator_and_entities(hass) -> None:
    """Apply protobuf PUT values to the registered measurement entities."""
    config_entry = MagicMock()
    config_entry.data = {CONF_PORT: 5683}
    config_entry.options = {}
    coordinator = ExampleCoordinator(hass, config_entry)
    coordinator.async_set_updated_data(ExampleAPIData(coordinator.name, []))
    coordinator._async_save_devices = Mock()
    endpoint = EndpointDevice(hass, coordinator)
    raw_device = coap_pb2.NewDevice(id="environment")
    for entity_id, (sub_type, name, unit, value, _) in enumerate(MEASUREMENTS, 1):
        raw_device.entities.add(
            id=entity_id,
            type=coap_pb2.ENTITY_TYPE_SENSOR,
            sub_type=sub_type,
            name=name,
            unit=unit,
            value=value,
        )
    response = await endpoint.render_post(
        Message(payload=raw_device.SerializeToString())
    )
    assert response.code == Code.CREATED
    device = coordinator.get_device_by_id("environment")
    entities = [
        sensor.CoAPSensorEntity(coordinator, device, item) for item in device.sensors
    ]
    update = coap_pb2.UpdateDevice(id="environment")
    for entity_id, (_, _, _, value, _) in enumerate(MEASUREMENTS, 1):
        update.entities.add(id=entity_id, value=value + 10)
    response = await endpoint.render_put(Message(payload=update.SerializeToString()))
    assert response.code == Code.CHANGED
    for created, (_, _, _, value, _) in zip(entities, MEASUREMENTS, strict=True):
        created.async_write_ha_state = Mock()
        created._handle_coordinator_update()
        assert created.native_value == value + 10
        created.async_write_ha_state.assert_called_once()
