import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from ha_coap_service.switch import CoapSwitch
from ha_coap_service.const import DOMAIN
from aiocoap.numbers.codes import Code


def test_coap_switch_init():
    """Test CoapSwitch initialization."""
    switch = CoapSwitch("device_123", "fd00::1234")
    assert switch._device_id == "device_123"
    assert switch._ip_address == "fd00::1234"
    assert switch._attr_unique_id == f"{DOMAIN}_device_123_switch"
    assert switch.is_on is False


@pytest.mark.asyncio
async def test_coap_switch_turn_on_no_instance():
    """Test turn_on with no coap instance."""
    switch = CoapSwitch("device_123", "fd00::1234")
    switch.hass = MagicMock()
    switch.hass.data = {DOMAIN: {"instances": {}}}
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()
    assert switch.is_on is False
    switch.async_write_ha_state.assert_not_called()


@pytest.mark.asyncio
async def test_coap_switch_turn_on_with_instance():
    """Test turn_on with coap instance."""
    switch = CoapSwitch("device_123", "fd00::1234")
    switch.hass = MagicMock()
    mock_instance = MagicMock()
    switch.hass.data = {DOMAIN: {"instances": {"device_123": mock_instance}}}
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()
    assert switch.is_on is True
    mock_instance.update_state_from_ha.assert_called_once_with("ON")
    switch.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_coap_switch_turn_off_no_instance():
    """Test turn_off with no coap instance."""
    switch = CoapSwitch("device_123", "fd00::1234")
    switch.hass = MagicMock()
    switch.hass.data = {DOMAIN: {"instances": {}}}
    switch._state = True
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_off()
    assert switch.is_on is True
    switch.async_write_ha_state.assert_not_called()


@pytest.mark.asyncio
async def test_coap_switch_turn_off_with_instance():
    """Test turn_off with coap instance."""
    switch = CoapSwitch("device_123", "fd00::1234")
    switch.hass = MagicMock()
    mock_instance = MagicMock()
    switch.hass.data = {DOMAIN: {"instances": {"device_123": mock_instance}}}
    switch._state = True
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_off()
    assert switch.is_on is False
    mock_instance.update_state_from_ha.assert_called_once_with("OFF")
    switch.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
@patch("aiocoap.Context.create_client_context", new_callable=AsyncMock)
async def test_send_coap_command_success(mock_create_client_context):
    """Test sending CoAP command successfully."""
    # Mock CoAP protocol context
    mock_protocol = MagicMock()
    mock_request_instance = MagicMock()
    
    # We mock the sequence: protocol.request(request).response
    response_future = AsyncMock()
    mock_response = MagicMock()
    response_future.response = mock_response
    mock_protocol.request.return_value = response_future
    mock_create_client_context.return_value = mock_protocol

    switch = CoapSwitch("device_123", "fd00::1234")
    
    # Execute the send command
    await switch._send_coap_command("ON")

    mock_create_client_context.assert_called_once()
    mock_protocol.request.assert_called_once()


@pytest.mark.asyncio
@patch("aiocoap.Context.create_client_context", new_callable=AsyncMock)
async def test_send_coap_command_failure(mock_create_client_context):
    """Test sending CoAP command handles exception gracefully."""
    # Mock CoAP protocol context to raise exception
    mock_protocol = MagicMock()
    mock_protocol.request.side_effect = Exception("Connection timed out")
    mock_create_client_context.return_value = mock_protocol

    switch = CoapSwitch("device_123", "fd00::1234")
    
    # Execute the send command should not raise any exceptions
    await switch._send_coap_command("ON")

    mock_create_client_context.assert_called_once()
