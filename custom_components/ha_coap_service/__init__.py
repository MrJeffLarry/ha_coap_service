import asyncio
import datetime
import json
import logging

from dataclasses import dataclass

from aiocoap import Context, Message, error, resource
from aiocoap.numbers.codes import Code
from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.resource import ObservableResource, Resource
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
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

from .coordinator import ExampleCoordinator

from .const import (
    CO_DEVICE_ID,
    CO_DEVICES,
    CO_PENDING_DEVICES,
    CO_PENDING_PAYLOADS,
    DOMAIN,
    HW_VERSION,
    ID,
    SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    # Platform.BINARY_SENSOR,
    # Platform.CLIMATE,
    Platform.SENSOR,
    # Platform.SWITCH,
    # Platform.WATER_HEATER,
]

type MyConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator


class WhoAmI(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    async def render_get(self, request):
        _LOGGER.warning("Request: GET /WhoAmI")
        text = [f"Used protocol: {request.remote.scheme}."]
        text.append(
            f"Last reload {self.hass.data[DOMAIN][self.entry.entry_id]['load_time']}"
        )
        text.append(
            f"Devices {len(self.hass.data[DOMAIN][self.entry.entry_id]['discovered'])}"
        )

        try:
            text.append(f"Request came from {request.remote.hostinfo}.")
            text.append(f"The server address used {request.remote.hostinfo_local}.")
        except error.AnonymousHost:
            text.append(f"Network peer: {request.remote}")

        claims = list(request.remote.authenticated_claims)
        if claims:
            text.append(
                f"Authenticated claims of the client: {', '.join(repr(c) for c in claims)}."
            )
        else:
            text.append("No claims authenticated.")

        return Message(
            payload="\n".join(text).encode("utf8"),
            content_format=ContentFormat.TEXT,
        )

def jsonPare(payload):
    try:
        # 1. Decode bytes to string and parse JSON
        raw_payload = payload.decode("utf-8")
        data = json.loads(raw_payload)

        device = {
            "id": data.get("device_id", None),
            "manufacturer": data.get("manufacturer", "hagerman"),
            "sw_version": data.get("sw_version", "1.0.0"),
            "hw_version": data.get("hw_version", "1.0.0"),
            "sensors": data.get("sensors", []),
        }

        if device[ID] == None:
            return None, b"Missing device_id in payload"

        return device, None

    except json.JSONDecodeError, UnicodeDecodeError:
        # If the payload isn"t valid JSON
        return None, b"could not parse json"


# If device does not exist in HA it register here or at startup
class EndpointDevice(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    # New device, get information about it and all its sensors to publich to HA
    async def render_post(self, request):
        device, err = jsonPare(request.payload)
        if err != None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if device[ID] not in self.hass.data[DOMAIN][self.entry.entry_id][CO_DEVICES]:
            pending_devices = self.hass.data[DOMAIN][self.entry.entry_id][
                CO_PENDING_DEVICES
            ]

            if device[ID] in pending_devices:
                return Message(code=Code.VALID)

            self.hass.data[DOMAIN][self.entry.entry_id][CO_DEVICES].add(device[ID])
            # Tell sensor.py to add a new entity
            async_dispatcher_send(self.hass, f"{DOMAIN}_new_device", device)

            return Message(
                code=Code.CREATED
            )  # or 2.04 if you want to swallow it temporarily

        # Update existing entity
        async_dispatcher_send(self.hass, f"{DOMAIN}_update_{device[ID]}", device)

        return Message(code=Code.CHANGED)


# device send data to HA, send back register new device if not exist
class EndpointDeviceData(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    async def render_put(self, request):
        device, err = jsonPare(request.payload)
        if err != None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if device[ID] not in self.hass.data[DOMAIN][self.entry.entry_id][CO_DEVICES]:
            pending_devices = self.hass.data[DOMAIN][self.entry.entry_id][
                CO_PENDING_DEVICES
            ]

            return Message(code=Code.UNAUTHORIZED)

        # Update existing entity
        async_dispatcher_send(self.hass, f"{DOMAIN}_update_{device[ID]}", device)

        return Message(code=Code.CHANGED)


# listen for device events from HA -> Device
class EndpointDeviceObserveEntity(resource.ObservableResource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry
        self.handle = None

    def notify(self):
        self.updated_state()
        self.reschedule()

    def reschedule(self):
        self.handle = asyncio.get_running_loop().call_later(5, self.notify)

    def update_observation_count(self, count):
        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

    async def render_get(self, request):
        payload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").encode("ascii")
        return Message(payload=payload, content_format=ContentFormat.TEXT)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):


    # Initialise the coordinator that manages data updates from your api.
    # This is defined in coordinator.py
    coordinator = ExampleCoordinator(hass, entry)

    # Perform an initial data load from api.
    # async_config_entry_first_refresh() is special in that it does not log errors if it fails
    await coordinator.async_config_entry_first_refresh()


    # Load existing devices from Registry to avoid re-discovering them
    registry = er.async_get(hass)
    known_devices = set(entry.data.get(CO_DEVICES, []))
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        prefix = f"{DOMAIN}_"
        if unique_id and unique_id.startswith(prefix):
            # unique_id format: <domain>_<device_id>_<sensor_type>
            tail = unique_id[len(prefix) :]
            if "_" in tail:
                known_devices.add(tail.rsplit("_", 1)[0])

    load_time = datetime.datetime.now(datetime.UTC)

    # Store it in hass.data so the sensor can read it
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "load_time": load_time,
        CO_PENDING_DEVICES: [],
        CO_PENDING_PAYLOADS: {},
        CO_DEVICES: known_devices,
        "discovered": known_devices,
        "instances": {},
    }

    # Setup CoAP Server
    root = resource.Site()
    root.add_resource(["whoami"], WhoAmI(hass, entry))
    root.add_resource(["device"], EndpointDevice(hass, entry))
    root.add_resource(["device", "data"], EndpointDeviceData(hass, entry))
    root.add_resource(["device", "observe"], EndpointDeviceObserveEntity(hass, entry))

    context = await Context.create_server_context(root, bind=("127.0.0.1", entry.data[CONF_PORT])) # 5683

    hass.data[DOMAIN][entry.entry_id]["coap_context"] = context
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # 1. Forward the unload to the sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # 2. Shutdown the CoAP context
    if unload_ok:
        coap_context = hass.data[DOMAIN][entry.entry_id].get("coap_context")
        if coap_context:
            await coap_context.shutdown()  # This is the critical cleanup step

        if hass.services.has_service(DOMAIN, "approve_device"):
            hass.services.async_remove(DOMAIN, "approve_device")

        # 3. Clean up hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: CastConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    return True
