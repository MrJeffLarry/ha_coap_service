"""Config flow for Integration 101 Template integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_PSK_IDENTITY,
    CONF_PSK_KEY,
    CONF_USE_DTLS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT, description={"suggested_value": 5683}): int,
        vol.Optional(CONF_USE_DTLS, default=False): bool,
        vol.Optional(CONF_PSK_IDENTITY, description={"suggested_value": ""}): str,
        vol.Optional(CONF_PSK_KEY, description={"suggested_value": ""}): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    if data[CONF_PORT] < 0 or data[CONF_PORT] > 65535:
        raise PortOutOfRange
    if data.get(CONF_USE_DTLS):
        if not (data.get(CONF_PSK_IDENTITY) and data.get(CONF_PSK_KEY)):
            raise PSKRequired
        try:
            import DTLSSocket  # noqa: F401
        except ImportError as err:
            raise DTLSNotAvailable from err

    return {"title": f"CoAP Server on :{data[CONF_PORT]}"}


class ExampleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Example Integration."""

    VERSION = 2
    _input_data: dict[str, Any]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        # Remove this method and the ExampleOptionsFlowHandler class
        # if you do not want any options for your integration.
        return ExampleOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Called when you initiate adding an integration via the UI
        errors: dict[str, str] = {}

        if user_input is not None:
            # The form has been filled in and submitted, so process the data provided.
            try:
                # Validate that the setup data is valid and if not handle errors.
                # The errors["base"] values match the values in your strings.json and translation files.
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except PortOutOfRange:
                errors["base"] = "port_out_of_range"
            except PSKRequired:
                errors["base"] = "psk_required"
            except DTLSNotAvailable:
                errors["base"] = "dtls_unavailable"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                # Validation was successful, so create a unique id for this instance of your integration
                # and create the config entry.
                await self.async_set_unique_id(info.get("title"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        # Show initial form.
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry."""
        # This methid displays a reconfigure option in the integration and is
        # different to options.
        # It can be used to reconfigure any of the data submitted when first installed.
        # This is optional and can be removed if you do not want to allow reconfiguration.
        errors: dict[str, str] = {}
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if user_input is not None:
            try:
                if not user_input.get(CONF_PSK_KEY):
                    # Preserve the existing PSK if the user left it blank
                    # (e.g. only toggling DTLS on/off).
                    user_input[CONF_PSK_KEY] = config_entry.data.get(CONF_PSK_KEY, "")
                merged_input = {**config_entry.data, **user_input}
                await validate_input(self.hass, merged_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except PortOutOfRange:
                errors["base"] = "port_out_of_range"
            except PSKRequired:
                errors["base"] = "psk_required"
            except DTLSNotAvailable:
                errors["base"] = "dtls_unavailable"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    config_entry,
                    unique_id=config_entry.unique_id,
                    data=merged_input,
                    reason="reconfigure_successful",
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_USE_DTLS,
                        default=config_entry.data.get(CONF_USE_DTLS, False),
                    ): bool,
                    vol.Optional(
                        CONF_PSK_IDENTITY,
                        default=config_entry.data.get(CONF_PSK_IDENTITY, ""),
                    ): str,
                    vol.Optional(
                        CONF_PSK_KEY,
                        description={"suggested_value": ""},
                    ): str,
                }
            ),
            errors=errors,
        )


class ExampleOptionsFlowHandler(OptionsFlow):
    """Handles the options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            options = self.config_entry.options | user_input
            return self.async_create_entry(title="", data=options)

        # It is recommended to prepopulate options fields with default values if available.
        # These will be the same default values you use on your coordinator for setting variable values
        # if the option has not been set.
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): (vol.All(vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL))),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class AlreadyConfigured(HomeAssistantError):
    """Error to indicate the device is already configured."""

class PortOutOfRange(HomeAssistantError):
    """Error to indicate the port is out of range."""

class PSKRequired(HomeAssistantError):
    """Error to indicate a PSK identity/key is required when DTLS is enabled."""

class DTLSNotAvailable(HomeAssistantError):
    """Error to indicate the DTLSSocket package is not installed/available."""
