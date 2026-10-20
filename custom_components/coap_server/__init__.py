"""The Integration 101 Template integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aiocoap import Context
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import ExampleCoordinator
from .server import CoAPServer, DTLSNotAvailable
from .const import (
    CONF_HEALTH_INTERVAL,
    CONF_PSK_IDENTITY,
    CONF_PSK_KEY,
    CONF_USE_DTLS,
    COAP_CONTEXT as COAP_CONTEXT,
    DEFAULT_HEALTH_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

type MyConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator
    serverContext: Context | None = None
    server: CoAPServer | None = None


async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    # Initialise the coordinator that manages data updates from your api.
    # This is defined in coordinator.py
    coordinator = ExampleCoordinator(hass, config_entry)

    # Perform an initial data load from api.
    # async_config_entry_first_refresh() is special in that it does not log errors if it fails
    await coordinator.async_config_entry_first_refresh()

    # Initialise a listener for config flow options changes.
    # This will be removed automatically if the integraiton is unloaded.
    # See config_flow for defining an options setting that shows up as configure
    # on the integration.
    # If you do not want any config flow options, no need to have listener.
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    server = CoAPServer(
        coordinator.port,
        hass,
        coordinator,
        use_dtls=config_entry.data.get(CONF_USE_DTLS, False),
        psk_identity=config_entry.data.get(CONF_PSK_IDENTITY),
        psk_key=config_entry.data.get(CONF_PSK_KEY),
        health_interval=config_entry.options.get(
            CONF_HEALTH_INTERVAL,
            config_entry.data.get(CONF_HEALTH_INTERVAL, DEFAULT_HEALTH_INTERVAL),
        ),
    )

    # Add the coordinator and update listener to config runtime data to make
    # accessible throughout your integration
    try:
        coap_context = await server.setup_services()
    except DTLSNotAvailable as err:
        raise ConfigEntryNotReady(str(err)) from err

    config_entry.runtime_data = RuntimeData(coordinator, coap_context, server)

    # Setup platforms (based on the list of entity types in PLATFORMS defined above)
    # This calls the async_setup method in each of your entity type files.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # setup event listeners
    async def on_hass_stop(event: Event) -> None:
        """Handle incoming stop event from Home Assistant."""
        await coap_context.shutdown()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    # Return true to denote a successful setup.
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry):
    """Handle config options update."""
    # Reload the integration when the options change.
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: MyConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    # Adding this function shows the delete device option in the UI.
    coordinator: ExampleCoordinator = config_entry.runtime_data.coordinator
    if not coordinator.data:
        return True

    controller_name = coordinator.data.controller_name
    for device in list(coordinator.data.devices):
        expected_identifier = (DOMAIN, f"{controller_name}-{device.id}")
        if expected_identifier in device_entry.identifiers:
            coordinator.async_remove_device(device.id)
            break

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Unload a config entry."""
    # 1. Forward the unload to the sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # 2. Shutdown the CoAP context. This must always run, even if platform
    # unload fails, otherwise the old aiocoap server keeps the UDP socket
    # bound and keeps routing device traffic to this (now stale) coordinator
    # after the config entry has been reloaded/removed and a new one takes
    # its place on the same host/port.
    server = config_entry.runtime_data.server
    if server:
        server.stop_health_checks()
    coap_context = config_entry.runtime_data.serverContext
    if coap_context:
        try:
            await coap_context.shutdown()
        except Exception:
            _LOGGER.exception(
                "Error shutting down CoAP context for %s", config_entry.entry_id
            )

    return unload_ok
