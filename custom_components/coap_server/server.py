import asyncio
import datetime
import json
import logging
import collections

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

ObservationKey = collections.namedtuple("ObservationKey", ["token", "remote"])

class DTLSNotAvailable(RuntimeError):
    """Raised when DTLS is requested but the DTLSSocket package is unavailable."""


class CoAPServer:
    """Class to handle Integration Services."""

    def __init__(
        self,
        port: int,
        hass,
        coordinator,
        use_dtls: bool = False,
        psk_identity: str | None = None,
        psk_key: str | None = None) -> None:
        """Initialise services."""
        self.hass = hass
        self.port = port
        self.coordinator = coordinator
        self.use_dtls = use_dtls
        self.psk_identity = psk_identity
        self.psk_key = psk_key

    async def setup_services(self) -> Context:
        """Setup CoAP server and register services."""

        # Pre-load modules that perform blocking disk I/O on import (like filelock)
        # inside an executor thread pool to avoid event loop warnings.
        await self.hass.async_add_executor_job(self._preload_dependencies)

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

        _LOGGER.info("Starting CoAP server on %s:%d (DTLS: %s)", "0.0.0.0", self.port, self.use_dtls)

        return await Context.create_server_context(
            root,
            bind=("0.0.0.0", self.port),
            server_credentials=server_credentials,
            transports=transports,
        )  # 5683 (or 5684 for coaps://)

    @staticmethod
    def _preload_dependencies() -> None:
        """Pre-load libraries that perform blocking filesystem probes on import."""
        try:
            import filelock  # noqa: F401
        except ImportError:
            pass
        import aiocoap.defaults
        import aiocoap.protocol


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
        self.device_id = None
        # Maps device_id -> set of observation keys
        self.device_observers = collections.defaultdict(set)
        # Maps observation key -> actual aiocoap ServerObservation object
        self.observations = {}

        # Register the callback with the coordinator on init
        # This assumes your coordinator can call: callback(device_id)
        if hasattr(self.coordinator, "async_add_notifyer"):
            self._unregister_callback = self.coordinator.async_add_notifyer(self.notify)

    async def add_observation(self, request, server_observation):
        """Called automatically by aiocoap when a client requests observation."""
        _LOGGER.debug("Observation requested for /device/observe %s", request)
        if server_observation is None:
            return

        # 1. Look for the 'id' parameter inside the URI query string
        device_id = None
        sensor_id = None
        uri = request.get_request_uri() # Returns something like 'id=device_123'
        query_string = request.opt.uri_query if request.opt else None

        _LOGGER.debug("Query string: %s", query_string)

        for query in query_string or []:
            if query.startswith("id="):
                device_id = query.split("=", 1)[1]
            elif query.startswith("sensor_id="):
                sensor_id = query.split("=", 1)[1]

        _LOGGER.debug("Extracted device_id: %s, sensor_id: %s", device_id, sensor_id)

        if not device_id or not sensor_id:
            _LOGGER.error("Rejected observation request: No 'id' parameter found in URI query string.")
            return

        unique_key = f"{device_id}:{sensor_id[0]}"

        # Generate a unique key for this specific connection
        key = ObservationKey(request.token, request.remote)

        if unique_key:
            self.device_observers[unique_key].add(key)
            self.observations[key] = server_observation

            # 3. Clean up when the client cancels or disconnects
            def on_observation_cancelled():
                _LOGGER.debug("Observation cancelled for client %s on device %s", request.remote, device_id)
                # send disconnect message to device if needed
                response = Message(payload=b"Observation cancelled", content_format=ContentFormat.TEXT)

                obs = self.observations.get(key)
                if obs:
                    obs.trigger(response)

                self.device_observers[device_id].discard(key)
                self.observations.pop(key, None)
                if not self.device_observers[device_id]:
                    del self.device_observers[device_id]

            # In aiocoap, accept() is enough to handle all teardown/cancellation scenarios
            server_observation.accept(on_observation_cancelled)
#            server_observation.register_errback(lambda _: on_observation_cancelled())
#            server_observation.accept(on_observation_cancelled)

    def notify(self, device_id=None, sensor_id=None):
        """Triggers updates ONLY for clients registered to this device_id."""
        _LOGGER.debug("Targeted notify for device %s", device_id)
        unique_key = f"{device_id}:{sensor_id}" if device_id and sensor_id else None
        if not unique_key or unique_key not in self.device_observers:
             return

        if sensor_id is None:
            return

        sub_data = self.coordinator.get_subscribe_data(device_id, sensor_id)
        _LOGGER.debug("Subscribe data: %s", sub_data)
        response = Message(
            code=Code.CONTENT,
            payload=json.dumps(CoAPObserveResponse.to_dict(sub_data)).encode("utf-8"),
            content_format=ContentFormat.JSON
        )
#         response = Message(payload=payload, content_format=ContentFormat.TEXT)

        # Loop through and update only the subscribers tied to this device_id
        for key in list(self.device_observers[unique_key]):
            obs = self.observations.get(key)
            if obs:
                obs.trigger(response)

    def update_observation_count(self, newcount):
        _LOGGER.debug("Observation count changed to %d for /device/observe", newcount)

    async def render_get(self, request: Message):
        _LOGGER.debug("GET /device/observe %s", request)

        payload = datetime.datetime.now().strftime("%Y-%m-%d %H:%M").encode("ascii")
        return Message(payload=payload, content_format=ContentFormat.TEXT)
