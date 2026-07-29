from unittest.mock import MagicMock, patch

import pytest
from conftest import MockConfigEntry
from ha_coap_service.const import DOMAIN
from ha_coap_service.sensor import CoapSensor, async_setup_entry


@pytest.mark.asyncio
async def test_sensor_setup_entry():
    """Test setting up sensor platform."""
    hass = MagicMock()
    entry = MockConfigEntry(entry_id="test_entry_id")
    async_add_entities = MagicMock()

    # Capture the dispatcher callback registered
    dispatcher_callback = None

    def mock_connect(h, signal, target):
        nonlocal dispatcher_callback
        if signal == f"{DOMAIN}_new_device":
            dispatcher_callback = target

    with patch(
        "ha_coap_service.sensor.async_dispatcher_connect", side_effect=mock_connect
    ):
        await async_setup_entry(hass, entry, async_add_entities)

    assert dispatcher_callback is not None

    # Call the callback with dummy data
    device_data = {
        "client_id": "test_device_1",
        "sensors": [{"type": "temperature"}, {"type": "humidity"}],
    }
    await dispatcher_callback(device_data)

    # Check if correct entities were added
    assert async_add_entities.call_count == 1
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 2
    assert all(isinstance(e, CoapSensor) for e in added_entities)
    assert added_entities[0]._device_id == "test_device_1"
    assert added_entities[0]._attr_device_class == "temperature"
    assert added_entities[1]._attr_device_class == "humidity"


def test_coap_sensor_properties():
    """Test CoapSensor properties."""
    sensor_def = {"type": "temperature"}
    sensor = CoapSensor("device_abc", "hagerman", sensor_def)

    assert sensor.state is None
    assert sensor._attr_device_class == "temperature"
    assert sensor._attr_unique_id == f"{DOMAIN}_device_abc_temperature"
    assert sensor._attr_name == "Temperature"
    assert sensor.device_info == {
        "identifiers": {(DOMAIN, "device_abc")},
        "name": "CoAP Device device_abc",
        "manufacturer": "hagerman",
    }


@pytest.mark.asyncio
async def test_coap_sensor_added_to_hass():
    """Test CoapSensor added to Home Assistant."""
    sensor_def = {"type": "temperature"}
    sensor = CoapSensor("device_abc", "hagerman", sensor_def)
    sensor.hass = MagicMock()
    sensor.async_on_remove = MagicMock()

    # Mock dispatcher connect
    with patch("ha_coap_service.sensor.async_dispatcher_connect") as mock_connect:
        await sensor.async_added_to_hass()
        mock_connect.assert_called_once()
        sensor.async_on_remove.assert_called_once()


def test_coap_sensor_update_callback():
    """Test CoapSensor update callback."""
    sensor_def = {"type": "temperature"}
    sensor = CoapSensor("device_abc", "hagerman", sensor_def)
    sensor.async_write_ha_state = MagicMock()

    sensor._update_callback(25.4)
    assert sensor.state == 25.4
    sensor.async_write_ha_state.assert_called_once()
