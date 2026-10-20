"""Tests for the CoAP firmware update platform."""

# ruff: noqa: S101

from unittest.mock import MagicMock, Mock

import pytest

from custom_components.coap_server import update
from custom_components.coap_server.models import CoAPDevice


@pytest.mark.asyncio
async def test_update_entities_are_created_only_for_devices_with_firmware_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test initial and dynamic firmware update entity creation."""
    coordinator = MagicMock()
    coordinator.data.controller_name = "CoAP Server"
    coordinator.data.devices = [
        CoAPDevice(id="without_url"),
        CoAPDevice(
            id="with_url",
            firmware_url="https://example.com/firmware.bin",
            sw_version="1.0.0",
        ),
    ]
    config_entry = MagicMock()
    config_entry.entry_id = "entry"
    config_entry.runtime_data.coordinator = coordinator
    unsubscribe = Mock()
    connect = Mock(return_value=unsubscribe)
    monkeypatch.setattr(update, "async_dispatcher_connect", connect)
    add_entities = Mock()

    await update.async_setup_entry(MagicMock(), config_entry, add_entities)

    entities = list(add_entities.call_args.args[0])
    assert len(entities) == 1
    assert entities[0].unique_id == "with_url_firmware_update"
    assert entities[0].installed_version == "1.0.0"
    assert entities[0].latest_version == "1.1.0"
    assert entities[0].release_url == "https://example.com/firmware.bin"
    config_entry.async_on_unload.assert_called_once_with(unsubscribe)

    callback = connect.call_args.args[2]
    callback(CoAPDevice(id="registered", firmware_url="https://example.com/new.bin"))
    dynamic_entities = list(add_entities.call_args.args[0])
    assert len(dynamic_entities) == 1
    assert dynamic_entities[0].unique_id == "registered_firmware_update"
