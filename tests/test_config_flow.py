import pytest
from unittest.mock import MagicMock
from ha_coap_service.config_flow import CoapFlowHandler
from ha_coap_service.const import DOMAIN


@pytest.mark.asyncio
async def test_config_flow_show_form():
    """Test the config flow shows a form when user_input is None."""
    handler = CoapFlowHandler()
    handler.hass = MagicMock()
    handler.hass.data = {}
    handler._async_current_entries = MagicMock(return_value=[])

    result = await handler.async_step_user(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_config_flow_create_entry():
    """Test the config flow creates an entry when user_input is provided."""
    handler = CoapFlowHandler()
    handler.hass = MagicMock()
    handler.hass.data = {}
    handler._async_current_entries = MagicMock(return_value=[])

    result = await handler.async_step_user(user_input={"dummy": "data"})
    assert result["type"] == "create_entry"
    assert result["title"] == "CoAP Service"
    assert result["data"] == {}


@pytest.mark.asyncio
async def test_config_flow_abort_if_existing_entries():
    """Test the config flow aborts if there are already configured entries."""
    handler = CoapFlowHandler()
    handler.hass = MagicMock()
    handler.hass.data = {}
    handler._async_current_entries = MagicMock(return_value=["some_entry"])

    result = await handler.async_step_user(user_input=None)
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_config_flow_abort_if_domain_in_data():
    """Test the config flow aborts if the domain is already in hass.data."""
    handler = CoapFlowHandler()
    handler.hass = MagicMock()
    handler.hass.data = {DOMAIN: "active"}
    handler._async_current_entries = MagicMock(return_value=[])

    result = await handler.async_step_user(user_input=None)
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
