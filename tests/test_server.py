from unittest.mock import Mock

import pytest
from aiocoap import Message
from aiocoap.numbers.codes import Code

from custom_components.coap_server import coap_pb2
from custom_components.coap_server.models import CoAPDevice, CoAPObserveResponse, CoAPObserveValue
from custom_components.coap_server.server import EndpointDevice, EndpointDeviceObserveEntity


@pytest.mark.asyncio
async def test_device_registration_and_observe_endpoints() -> None:
    """Test protobuf registration and observe response across the CoAP endpoints."""
    raw_device = coap_pb2.NewDevice(
        version=1,
        id="device004",
        manufacturer="Acme",
        model="Sensor Node",
    )
    raw_device.entities.add(
        id=1,
        value=21.5,
        type=coap_pb2.ENTITY_TYPE_SENSOR,
        sub_type="temperature",
        unit="°C",
        name="Temperature",
    )
    raw_device.entities.add(
        id=2,
        value=1,
        type=coap_pb2.ENTITY_TYPE_BINARY_SENSOR,
        sub_type="motion",
        name="Motion",
    )
    raw_device.entities.add(
        id=3,
        value=1,
        type=coap_pb2.ENTITY_TYPE_SWITCH,
        sub_type="switch",
        name="Relay",
    )
    raw_device.entities.add(
        id=4,
        value=75,
        type=coap_pb2.ENTITY_TYPE_LIGHT,
        sub_type="brightness",
        name="Light",
    )

    coordinator = Mock()
    coordinator.push_device_data.return_value = False
    coordinator.get_subscribe_data.return_value = CoAPObserveResponse(
        id="device004",
        sensors=[CoAPObserveValue(id=1, state=21.5)],
    )

    registration = EndpointDevice(None, coordinator)
    registration_response = await registration.render_post(
        Message(payload=raw_device.SerializeToString())
    )

    assert registration_response.code == Code.CREATED
    registered_device = coordinator.push_device_data.call_args.args[0]
    assert isinstance(registered_device, CoAPDevice)
    assert registered_device.id == "device004"
    assert [sensor.id for sensor in registered_device.sensors] == [1, 2, 3, 4]
    assert [
        sensor.type.value if sensor.type else None
        for sensor in registered_device.sensors
    ] == ["temperature", "motion", "switch", "brightness"]

    observe = EndpointDeviceObserveEntity(None, coordinator)
    observe.reschedule = Mock()
    request = Message(code=Code.GET)
    request.set_request_uri("coap://localhost/device/observe?id=device004&sensor_id=1")

    observe_response = await observe.render_get(request)

    assert observe_response.code == Code.CONTENT
    coordinator.get_subscribe_data.assert_called_once_with("device004", 1)
    decoded_response = coap_pb2.ObserveDeviceResponse()
    decoded_response.ParseFromString(observe_response.payload)
    assert [(entity.id, entity.value) for entity in decoded_response.entities] == [
        (1, 21.5)
    ]
