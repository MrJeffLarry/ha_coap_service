import asyncio
import datetime
import json
import logging

from dataclasses import dataclass

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PORT,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    Platform,
)

from .coordinator import DataCoordinator
from .api import CoAPServiceSetup

from .const import (
    CO_DEVICES,
    CO_PENDING_DEVICES,
    CO_PENDING_PAYLOADS,
    COAP_CONTEXT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    # Platform.BINARY_SENSOR,
    # Platform.CLIMATE,
    Platform.SENSOR,
    # Platform.SWITCH,
    # Platform.WATER_HEATER,
]

type AppConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: AppConfigEntry):
    """Set up your integration using UI."""
    # Initialise the coordinator that manages data updates from your api.
    # This is defined in coordinator.py
    coordinator = DataCoordinator(hass, entry)

    # Perform an initial data load from api.
    # async_config_entry_first_refresh() is special in that it does not log errors if it fails
    await coordinator.async_config_entry_first_refresh()

    # Initialise a listener for config flow options changes.
    # This will be removed automatically if the integraiton is unloaded.
    # See config_flow for defining an options setting that shows up as configure
    # on the integration.
    # If you do not want any config flow options, no need to have listener.
    entry.async_on_unload(
        entry.add_update_listener(_async_update_listener)
    )

    # Add the coordinator and update listener to config runtime data to make
    # accessible throughout your integration
    entry.runtime_data = RuntimeData(coordinator)

    # ----------------------------------------------------------------------------
    # Setup platforms (based on the list of entity types in PLATFORMS defined above)
    # This calls the async_setup method in each of your entity type files.
    # ----------------------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ----------------------------------------------------------------------------
    # Setup global services
    # This can be done here but included in a seperate file for ease of reading.
    # See also light.py for entity services examples
    # ----------------------------------------------------------------------------
    # Initialize shared hass.data store for this entry
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "load_time": datetime.datetime.now(datetime.UTC),
    }

    service = CoAPServiceSetup(hass, entry)
    hass.data[DOMAIN][entry.entry_id][COAP_CONTEXT] = await service.setup_services()

    return True


async def _async_update_listener(hass: HomeAssistant, config_entry) -> None:
    """Handle config options update."""
    # Reload the integration when the options change.
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    # Adding this function shows the delete device option in the UI.
    # Remove this function if you do not want that option.
    # You may need to do some checks here before allowing devices to be removed.
    return True

async def async_unload_entry(hass: HomeAssistant, entry: AppConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when you remove your integration or shutdown HA.
    # If you have created any custom services, they need to be removed here too.

    # 1. Forward the unload to the sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # 2. Shutdown the CoAP context
    if unload_ok:
        coap_context = hass.data[DOMAIN][entry.entry_id].get(COAP_CONTEXT)
        if coap_context:
            await coap_context.shutdown()  # This is the critical cleanup step

        # 3. Clean up hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
