"""Adds config flow for CoAP Service."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CO_DEVICE_ID,
    CO_DEVICES,
    CO_PENDING_DEVICES,
    CO_PENDING_PAYLOADS,
    DOMAIN,
)


_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class CoapFlowHandler(config_entries.ConfigFlow):
    """Config flow for CoAP Service."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize."""
        self._errors = {}
        self._coap_discovery_data = None
        self._coap_device_id = None

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

    async def async_step_coap(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle device announcements from the CoAP endpoint."""
        _LOGGER.debug(
            "CoAP discovery step entered: context=%s user_input=%s",
            self.context,
            user_input,
        )
        entries = self._async_current_entries()
        if not entries:
            _LOGGER.warning(
                "CoAP discovery received but integration has no active config entry"
            )
            return self.async_abort(reason="not_configured")

        entry = entries[0]
        runtime_data = self.hass.data.get(DOMAIN, {}).get(entry.entry_id)

        # First call from discovery carries the device payload.
        if self._coap_discovery_data is None:
            discovery_data = user_input or {}
            if not discovery_data and runtime_data:
                context_device_id = self.context.get("device_id")
                if context_device_id:
                    discovery_data = runtime_data.get(CO_PENDING_PAYLOADS, {}).get(
                        context_device_id,
                        {CO_DEVICE_ID: context_device_id},
                    )

            device_id = (
                discovery_data.get(CO_DEVICE_ID)
                or discovery_data.get("client_id")
                or self.context.get("device_id")
            )
            if not device_id:
                _LOGGER.warning(
                    "CoAP discovery payload missing device id: %s", discovery_data
                )
                return self.async_abort(reason="invalid_discovery_info")

            approved_devices = set(entry.data.get(CO_DEVICES, []))
            if runtime_data:
                approved_devices.update(runtime_data.get(CO_DEVICES, set()))

            if device_id in approved_devices:
                _LOGGER.info(
                    "CoAP discovery ignored; device already approved: %s", device_id
                )
                return self.async_abort(reason="already_configured")

            self._coap_discovery_data = discovery_data
            self._coap_device_id = device_id
            self.context["title_placeholders"] = {"device_id": device_id}
            _LOGGER.info("Showing CoAP approval form for device_id=%s", device_id)

            return self.async_show_form(
                step_id="coap",
                data_schema=vol.Schema({vol.Required("approve", default=True): bool}),
                description_placeholders={"device_id": device_id},
            )

        # Second call is the user's approval decision.
        if not user_input or not user_input.get("approve"):
            if (
                runtime_data
                and self._coap_device_id
                and self._coap_device_id in runtime_data[CO_PENDING_DEVICES]
            ):
                runtime_data[CO_PENDING_DEVICES].remove(self._coap_device_id)
                runtime_data[CO_PENDING_PAYLOADS].pop(self._coap_device_id, None)
            _LOGGER.info(
                "CoAP device approval rejected for device_id=%s", self._coap_device_id
            )
            if self._coap_device_id:
                persistent_notification.async_dismiss(
                    self.hass, f"{DOMAIN}_pending_{self._coap_device_id}"
                )
            return self.async_abort(reason="device_not_approved")

        device_id = self._coap_device_id
        approved_devices = list(entry.data.get(CO_DEVICES, []))
        if device_id not in approved_devices:
            approved_devices.append(device_id)

        self.hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CO_DEVICES: approved_devices,
            },
        )

        if runtime_data:
            runtime_data[CO_DEVICES].add(device_id)
            runtime_data["discovered"].add(device_id)
            if device_id in runtime_data[CO_PENDING_DEVICES]:
                runtime_data[CO_PENDING_DEVICES].remove(device_id)
            runtime_data[CO_PENDING_PAYLOADS].pop(device_id, None)

            _LOGGER.info("CoAP device approved: %s", device_id)
            persistent_notification.async_dismiss(
                self.hass, f"{DOMAIN}_pending_{device_id}"
            )

            async_dispatcher_send(
                self.hass, f"{DOMAIN}_new_device", self._coap_discovery_data
            )
            async_dispatcher_send(
                self.hass, f"{DOMAIN}_update_{device_id}", self._coap_discovery_data
            )

        return self.async_abort(reason="device_approved")

    async def async_step_integration_discovery(
        self, discovery_info: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle Home Assistant integration discovery source."""
        return await self.async_step_coap(discovery_info)


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
