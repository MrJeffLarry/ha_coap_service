import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from aiocoap.numbers.codes import Code
from aiocoap import Message

from ha_coap_service import async_setup_entry, async_unload_entry
from ha_coap_service.const import DOMAIN
from conftest import MockConfigEntry


@pytest.mark.asyncio
@patch("aiocoap.Context.create_server_context", new_callable=AsyncMock)
async def test_async_setup_entry(mock_create_server_context):
    """Test successful setup of the config entry."""
    # Setup mock context
    mock_context = MagicMock()
    mock_context.shutdown = AsyncMock()
    mock_create_server_context.return_value = mock_context

    # Setup mock hass and entry
    hass = MagicMock()
    hass.data = {}
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = MockConfigEntry(entry_id="test_entry_id")

    # Call setup
    result = await async_setup_entry(hass, entry)

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert hass.data[DOMAIN][entry.entry_id]["coap_context"] == mock_context
    assert isinstance(hass.data[DOMAIN][entry.entry_id]["discovered"], set)

    # Verify server context creation was called
    mock_create_server_context.assert_called_once()
    # Verify forward platform was called
    hass.config_entries.async_forward_entry_setups.assert_called_once_with(entry, ["sensor"])


@pytest.mark.asyncio
async def test_async_unload_entry():
    """Test successful unloading of the config entry."""
    # Setup mock context
    mock_context = AsyncMock()
    mock_context.shutdown = AsyncMock()

    # Setup mock hass and entry
    hass = MagicMock()
    entry = MockConfigEntry(entry_id="test_entry_id")
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "coap_context": mock_context
            }
        }
    }

    # Mock unload_platforms to return True
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    # Call unload
    result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]
    mock_context.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_whoami_resource():
    """Test WhoAmI resource render_get."""
    from ha_coap_service import WhoAmI
    import datetime

    hass = MagicMock()
    entry = MockConfigEntry(entry_id="test_entry_id")
    load_time = datetime.datetime.now()
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "load_time": load_time,
                "discovered": {"device1", "device2"}
            }
        }
    }

    resource = WhoAmI(hass, entry)

    # Mock request
    request = MagicMock()
    request.remote.scheme = "coap"
    request.remote.hostinfo = "127.0.0.1"
    request.remote.hostinfo_local = "127.0.0.1"
    request.remote.authenticated_claims = ["claim1"]

    response = await resource.render_get(request)
    assert response is not None
    payload_str = response.payload.decode("utf-8")
    assert "Used protocol: coap." in payload_str
    assert "Devices 2" in payload_str
    assert "claim1" in payload_str


@pytest.mark.asyncio
@patch("ha_coap_service.async_dispatcher_send")
async def test_coap_resource_render_put_new_device(mock_dispatcher_send):
    """Test CoapResource render_put when a new device is discovered."""
    from ha_coap_service import CoapResource

    hass = MagicMock()
    entry = MockConfigEntry(entry_id="test_entry_id")
    discovered = set()
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "discovered": discovered
            }
        }
    }

    resource = CoapResource(hass, entry)

    # Prepare PUT request with new device
    payload = {"client_id": "new_device", "sensors": []}
    request = Message(payload=json.dumps(payload).encode("utf-8"))

    response = await resource.render_put(request)
    assert response.code == Code.CHANGED
    assert "new_device" in discovered
    
    # Verify both new_device and update dispatchers were sent
    mock_dispatcher_send.assert_any_call(hass, f"{DOMAIN}_new_device", payload)
    mock_dispatcher_send.assert_any_call(hass, f"{DOMAIN}_update_new_device", payload)


@pytest.mark.asyncio
@patch("ha_coap_service.async_dispatcher_send")
async def test_coap_resource_render_put_existing_device(mock_dispatcher_send):
    """Test CoapResource render_put when an existing device is updated."""
    from ha_coap_service import CoapResource

    hass = MagicMock()
    entry = MockConfigEntry(entry_id="test_entry_id")
    discovered = {"existing_device"}
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "discovered": discovered
            }
        }
    }

    resource = CoapResource(hass, entry)

    # Prepare PUT request with existing device
    payload = {"client_id": "existing_device", "sensors": []}
    request = Message(payload=json.dumps(payload).encode("utf-8"))

    response = await resource.render_put(request)
    assert response.code == Code.CHANGED
    assert "existing_device" in discovered
    
    # Verify only update dispatcher was sent, not new_device
    mock_dispatcher_send.assert_called_once_with(hass, f"{DOMAIN}_update_existing_device", payload)


@pytest.mark.asyncio
async def test_coap_resource_render_put_invalid_payload():
    """Test CoapResource render_put handles invalid JSON and missing client_id gracefully."""
    from ha_coap_service import CoapResource

    hass = MagicMock()
    entry = MockConfigEntry(entry_id="test_entry_id")
    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                "discovered": set()
            }
        }
    }

    resource = CoapResource(hass, entry)

    # Test invalid JSON
    request_invalid_json = Message(payload=b"invalid-json")
    response1 = await resource.render_put(request_invalid_json)
    assert response1.code == Code.BAD_REQUEST
    assert response1.payload == b"Invalid JSON"

    # Test missing client_id
    payload_missing_id = {"sensors": []}
    request_missing_id = Message(payload=json.dumps(payload_missing_id).encode("utf-8"))
    response2 = await resource.render_put(request_missing_id)
    assert response2.code == Code.BAD_REQUEST
    assert response2.payload == b"Missing client_id"
