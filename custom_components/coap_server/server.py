import asyncio
import datetime
import json
import logging

from aiocoap import Context, Message, error, resource
from aiocoap.credentials import DTLS as DTLSCredential
from aiocoap.credentials import CredentialsMap
from aiocoap.numbers.codes import Code
from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.resource import ObservableResource
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant

from .models import CoAPDevice, CoAPObserveRequest, CoAPObserveResponse
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DTLSNotAvailable(RuntimeError):
    """Raised when DTLS is requested but the DTLSSocket package is unavailable."""


class CoAPServer:
    """Class to handle Integration Services."""

    def __init__(
        self,
        host: str,
        port: int,
        hass,
        coordinator,
        use_dtls: bool = False,
        psk_identity: str | None = None,
        psk_key: str | None = None) -> None:
        """Initialise services."""
        self.hass = hass
        self.host = host
        self.port = port
        self.coordinator = coordinator
        self.use_dtls = use_dtls
        self.psk_identity = psk_identity
        self.psk_key = psk_key

    async def setup_services(self) -> Context:
        """Setup CoAP server and register services."""
        root = resource.Site()
        root.add_resource(["whoami"], WhoAmI(self.hass, self.coordinator))
        root.add_resource(["device"], EndpointDevice(self.hass, self.coordinator))
        root.add_resource(["device", "data"], EndpointDeviceData(self.hass, self.coordinator))
        root.add_resource(["device", "observe"], EndpointDeviceObserveEntity(self.hass, self.coordinator))

        server_credentials = None
        transports = None

        if self.use_dtls:
            if not (self.psk_identity and self.psk_key):
                raise ValueError(
                    "DTLS is enabled but psk_identity/psk_key were not provided"
                )

            try:
                import DTLSSocket  # noqa: F401
            except ImportError as err:
                raise DTLSNotAvailable(
                    "DTLS was requested, but the DTLSSocket Python package is "
                    "not installed (or failed to build) in this environment. "
                    "It wraps the tinydtls C library and typically needs to be "
                    "compiled from source, requiring build tools such as "
                    "autoconf, automake, libtool and a C compiler on the host. "
                    "Install those system packages and then run "
                    "pip install DTLSSocket, or disable DTLS in the integration "
                    "options."
                ) from err

            server_credentials = CredentialsMap()
            server_credentials["coaps://*"] = DTLSCredential(
                psk=self.psk_key.encode("utf-8"),
                client_identity=self.psk_identity.encode("utf-8"),
            )
            # tinydtls_server is not selected by default (see aiocoap's
            # transports/tinydtls_server.py), so it must be requested
            # explicitly. Using it exclusively means the server only speaks
            # coaps:// (DTLS-secured) rather than plain coap://.
            transports = ["tinydtls_server"]

        return await Context.create_server_context(
            root,
            bind=(self.host, self.port),
            server_credentials=server_credentials,
            transports=transports,
        )  # 5683 (or 5684 for coaps://)

#        self.hass.data[DOMAIN][self.config_entry.entry_id][COAP_CONTEXT] = context


class WhoAmI(resource.Resource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator

    async def render_get(self, request: message.Message) -> Message:
        """Get information about the CoAP server and the request."""
        _LOGGER.warning("Request: GET /WhoAmI")
        text = [f"Used protocol: {request.remote.scheme}."]
#        text.append(
#            f"Last reload {self.hass.data[DOMAIN][self.entry.entry_id]['load_time']}"
#        )
#        text.append(
#            f"Devices {len(self.hass.data[DOMAIN][self.entry.entry_id]['discovered'])}"
#        )

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


def json_pare(payload: bytes | None) -> tuple[CoAPDevice, bytes | None]:
    """Parse JSON payload from device and return Device object."""
    device: CoAPDevice = CoAPDevice(id=None)

    if payload is None:
        return device, b"Missing payload"

    try:
        # 1. Decode bytes to string and parse JSON
        raw_payload = payload.decode("utf-8")
        data = json.loads(raw_payload)
        device = CoAPDevice.from_dict(data)

        if device.id is None:
            return device, b"Missing id in payload"
        else:
            return device, None

    except json.JSONDecodeError, UnicodeDecodeError:
        # If the payload isn"t valid JSON
        return device, b"could not parse json"


# If device does not exist in HA it register here or at startup
class EndpointDevice(resource.Resource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator

    # New device, get information about it and all its sensors to publich to HA
    async def render_post(self, request: message.Message):
        device, err = json_pare(request.payload)
        if err is not None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if self.coordinator.push_device_data(device):
            return Message(code=Code.CREATED)

        return Message(code=Code.CHANGED)  # or 2.04 if you want to swallow it temporarily

    async def render_put(self, request: message.Message):
        device, err = json_pare(request.payload)
        if err is not None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if self.coordinator.update_device_data(device):
            return Message(code=Code.CHANGED)

        return Message(code=Code.NOT_FOUND, payload=b"Device not found")


# device send data to HA, send back register new device if not exist
class EndpointDeviceData(resource.Resource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator

    async def render_put(self, request: message.Message):
        device, err = json_pare(request.payload)
        if err is not None:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if self.coordinator.update_device_data(device):
            return Message(code=Code.CHANGED)

        return Message(code=Code.NOT_FOUND, payload=b"Device not found")

# listen for device events from HA -> Device
class EndpointDeviceObserveEntity(resource.ObservableResource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator
        self.handle = None

    def notify(self):
        _LOGGER.debug("Notify observers of /device/observe")
        self.updated_state()
#        self.reschedule()

#    def reschedule(self):
#        _LOGGER.debug("Rescheduling notify for /device/observe")
#        self.handle = asyncio.get_running_loop().call_later(5, self.notify)

    def update_observation_count(self, newcount):
        _LOGGER.debug("Observation count changed to %d for /device/observe", newcount)
        if newcount and self.handle is None:
            _LOGGER.debug("Scheduling notify for /device/observe")
#            self.reschedule()
        if newcount == 0 and self.handle:
            _LOGGER.debug("Cancelling notify for /device/observe")
#            self.handle.cancel()
#            self.handle = None

    async def render_get(self, request: Message):
        _LOGGER.debug("GET /device/observe %s", request)
        payload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").encode("ascii")
        return Message(payload=payload, content_format=ContentFormat.TEXT)

    async def render_post(self, request: Message):
        _LOGGER.debug("POST /device/observe %s", request)

        try:
            raw_payload = request.payload.decode("utf-8")
            data = json.loads(raw_payload)
            sub_data = self.coordinator.get_subscribe_data(data, self.notify)
            return Message(
                payload=json.dumps(CoAPObserveResponse.to_dict(sub_data)).encode("utf-8"),
                content_format=ContentFormat.JSON
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Message(code=Code.BAD_REQUEST, payload=b"could not parse json")

        return Message(code=Code.BAD_REQUEST, payload=b"could not parse json")
