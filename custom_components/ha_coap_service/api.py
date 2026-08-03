import asyncio
import datetime
import json
import logging

from aiocoap import Context, Message, error, resource
from aiocoap.numbers.codes import Code
from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.resource import ObservableResource
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .coordinator import DataCoordinator
from .models import Device, DeviceType, Sensor
from .const import (
    CO_DEVICES,
    CO_PENDING_DEVICES,
    DOMAIN,
    ID,
    COAP_CONTEXT,
)

_LOGGER = logging.getLogger(__name__)

class CoAPServiceSetup:
    """Class to handle Integration Services."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialise services."""
        self.hass = hass
        self.config_entry = config_entry
        self.coordinator: DataCoordinator = config_entry.runtime_data.coordinator

    async def setup_services(self) -> Context:
        """Setup CoAP server and register services."""
        root = resource.Site()
        root.add_resource(["whoami"], WhoAmI(self.hass, self.config_entry))
        root.add_resource(["device"], EndpointDevice(self.hass, self.config_entry))
        root.add_resource(["device", "data"], EndpointDeviceData(self.hass, self.config_entry))
        root.add_resource(["device", "observe"], EndpointDeviceObserveEntity(self.hass, self.config_entry))

        return await Context.create_server_context(root, bind=("127.0.0.1", self.config_entry.data[CONF_PORT])) # 5683

#        self.hass.data[DOMAIN][self.config_entry.entry_id][COAP_CONTEXT] = context


class WhoAmI(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    async def render_get(self, request: message.Message) -> Message:
        """Get information about the CoAP server and the request."""
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

def json_pare(payload: bytes | None) -> tuple[Device, bytes | None]:
    """Parse JSON payload from device and return Device object."""
    device: Device = Device(device_id=0, device_unique_id="")

    if payload is None:
        return device, b"Missing payload"

    try:
        # 1. Decode bytes to string and parse JSON
        raw_payload = payload.decode("utf-8")
        data = json.loads(raw_payload)
        device.device_id = data.get("device_id", None)
        device.device_unique_id = f"{device.device_id}_{data.get('device_type', 'other')}"
        device.device_type = DeviceType(data.get("device_type", "other"))
        device.manufacturer = data.get("manufacturer", "hagerman")
        device.sw_version = data.get("sw_version", "1.0.0")
        device.hw_version = data.get("hw_version", "1.0.0")
        device.sensors = data.get("sensors", [])

        if device.device_id is None:
            return device, b"Missing device_id in payload"
        else:
            return device, None

    except json.JSONDecodeError, UnicodeDecodeError:
        # If the payload isn"t valid JSON
        return device, b"could not parse json"


# If device does not exist in HA it register here or at startup
class EndpointDevice(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    # New device, get information about it and all its sensors to publich to HA
    async def render_post(self, request: message.Message):
        device, err = json_pare(request.payload)
        if err is not None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        # Also push updated data into the DataCoordinator so CoordinatorEntity
        # sensors (DeviceSensor) pick up the new state.
        coordinator: DataCoordinator = self.entry.runtime_data.coordinator

        if coordinator.push_device_data(device):
            return Message(code=Code.CHANGED)

        return Message(code=Code.CREATED)  # or 2.04 if you want to swallow it temporarily

    async def render_put(self, request: message.Message):
        device, err = json_pare(request.payload)
        if err is not None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        # Also push updated data into the DataCoordinator so CoordinatorEntity
        # sensors (DeviceSensor) pick up the new state.
        coordinator: DataCoordinator = self.entry.runtime_data.coordinator

        if coordinator.push_device_data(device):
            return Message(code=Code.CHANGED)

        return Message(code=Code.CHANGED)


# device send data to HA, send back register new device if not exist
class EndpointDeviceData(resource.Resource):
    def __init__(self, hass, entry):
        super().__init__()
        self.hass = hass
        self.entry = entry

    async def render_put(self, request: message.Message):
        device, err = json_pare(request.payload)
        if err is not None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        # Also push updated data into the DataCoordinator so CoordinatorEntity
        # sensors (DeviceSensor) pick up the new state.
        coordinator: DataCoordinator = self.entry.runtime_data.coordinator

        if coordinator.push_device_data(device):
            return Message(code=Code.CHANGED)

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

#    def update_observation_count(self, newcount):
#        if newcount and self.handle is None:
#            print("Starting the clock")
#            self.reschedule()
 #       if newcount == 0 and self.handle:
  #          print("Stopping the clock")
  #          self.handle.cancel()
  #          self.handle = None

    async def render_get(self, request: message.Message):
        payload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").encode("ascii")
        return Message(payload=payload, content_format=ContentFormat.TEXT)
