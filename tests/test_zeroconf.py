from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import CONF_PORT

from custom_components.coap_server import _async_register_zeroconf_service
from custom_components.coap_server.const import CONF_USE_DTLS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("use_dtls", "service_type"),
    [
        (False, "_coap._udp.local."),
        (True, "_coaps._udp.local."),
    ],
)
async def test_register_zeroconf_service(
    hass, monkeypatch, use_dtls: bool, service_type: str
) -> None:
    """Advertise the configured CoAP endpoint using its matching DNS-SD type."""
    announce_addresses = AsyncMock(return_value=["192.0.2.1"])
    register_service = AsyncMock()
    get_zeroconf = AsyncMock(
        return_value=SimpleNamespace(async_register_service=register_service)
    )
    monkeypatch.setattr(
        "custom_components.coap_server.network.async_get_announce_addresses",
        announce_addresses,
    )
    monkeypatch.setattr(
        "custom_components.coap_server.async_get_async_instance", get_zeroconf
    )

    entry = SimpleNamespace(
        entry_id="test-entry",
        data={CONF_PORT: 5683, CONF_USE_DTLS: use_dtls},
    )

    service_info = await _async_register_zeroconf_service(hass, entry)

    assert service_info.type == service_type
    assert service_info.name == f"CoAP Server test-entry.{service_type}"
    assert service_info.port == 5683
    assert service_info.parsed_addresses() == ["192.0.2.1"]
    assert service_info.properties == {
        b"path": b"/",
        b"secure": str(use_dtls).lower().encode(),
    }
    assert service_info.server == "coap-server-test-entry.local."
    announce_addresses.assert_awaited_once_with(hass)
    register_service.assert_awaited_once_with(service_info, allow_name_change=True)
