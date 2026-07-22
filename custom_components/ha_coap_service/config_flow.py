"""Adds config flow for CoAP Service."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

@config_entries.HANDLERS.register(DOMAIN)
class CoapFlowHandler(config_entries.ConfigFlow):
    """Config flow for CoAP Service."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a user initiated set up flow to create a webhook."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self.hass.data.get(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="CoAP Service", data={})

# class CoapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
#     """Handle a config flow for CoAP integration."""

#     VERSION = 1

#     def __init__(self):
#         self.client_id = None

#     async def async_step_coap(self, discovery_info):
#         """Handle a packet received from an unmanaged CoAP device."""
#         self.client_id = discovery_info["client_id"]

#         # Ensure we don't open duplicate flow popups for the same device
#         await self.async_set_unique_id(self.client_id)
#         self._abort_if_unique_id_configured()

#         # Set the title dynamically for the UI prompt
#         self.context["title_placeholders"] = {"client_id": self.client_id}

#         # Move to the user input step to collect the DTLS-PSK
#         return await self.async_step_psk()

#     async def async_step_psk(self, user_input=None):
#         """Prompt the user for the device-specific DTLS-PSK key."""
#         errors = {}

#         if user_input is not None:
#             # Optional: Validate the PSK format (e.g., must be a valid hex string)
#             psk = user_input.get("dtls_psk", "").strip()
#             if len(psk) < 8:
#                 errors["dtls_psk"] = "invalid_psk_length"
#             else:
#                 return self.async_create_entry(
#                     title=f"CoAP Device ({self.client_id})",
#                     data={
#                         "client_id": self.client_id,
#                         "dtls_psk": psk,
#                     },
#                 )

#         return self.async_show_form(
#             step_id="psk",
#             data_schema=vol.Schema({
#                 vol.Required("dtls_psk"): str,
#             }),
#             errors=errors,
#             description_placeholders={"client_id": self.client_id},
#         )

#     async def async_step_user(self, user_input=None):
#         """Allow manual addition if user prefers."""
#         if user_input is not None:
#             self.client_id = user_input["client_id"]
#             await self.async_set_unique_id(self.client_id)
#             self._abort_if_unique_id_configured()
#             return await self.async_step_psk()

#         return self.async_show_form(
#             step_id="user",
#             data_schema=vol.Schema({
#                 vol.Required("client_id"): str,
#             }),
#         )