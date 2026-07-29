# import logging
# from homeassistant import config_entries
# import voluptuous as vol

# _LOGGER = logging.getLogger(__name__)

# # @config_entries.HANDLERS.register(DOMAIN)
# class CoapFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
#     """Config flow for CoAP Service."""

#     VERSION = 1
#     CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

#     def __init__(self) -> None:
#         """Initialize."""
#         self._errors = {}
#         self._coap_port = DEFAULT_PORT

#     async def async_step_user(
#         self, user_input: dict | None = None
#     ) -> config_entries.ConfigFlowResult:

#         if user_input is not None:
#             pass  # TODO: process info

#         """Handle a user initiated set up flow to create a webhook."""
#         if self._async_current_entries():
#             return self.async_abort(reason="single_instance_allowed")
#         if self.hass.data.get(DOMAIN):
#             return self.async_abort(reason="single_instance_allowed")

#         if user_input is None:
#             return self.async_show_form(step_id="user")
#         # return self.async_create_entry(title="CoAP Service", data={})

#         return self.async_show_form(
#             step_id="user", data_schema=vol.Schema({vol.Required("password"): str})
#         )

#
#
#################
#
#

# from http import HTTPStatus
# import socket
import logging
from typing import Any, override

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

# CLOUD_API_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_TOKEN): str,
#     }
# )

LOCAL_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): int,
        # vol.Required(CONF_USERNAME): str,
        # vol.Required(CONF_PASSWORD): str,
    }
)

class CoAPServiceConfigFlow(ConfigFlow, domain=DOMAIN):

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:

        return self.async_show_menu(
            step_id="user",
            menu_options=["local_api"],
        )

    async def async_step_local_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Version 3 configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_PORT: user_input[CONF_PORT],
                    # CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )

                # await self.async_set_unique_id(response["data"]["UID"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Local server :{user_input[CONF_PORT]}", data=user_input
            )

        return self.async_show_form(
            step_id="local_api", errors=errors, data_schema=LOCAL_API_SCHEMA
        )