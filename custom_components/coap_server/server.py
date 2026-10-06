import asyncio
import collections
import logging

from aiocoap import Context, Message, error, resource
from aiocoap.credentials import DTLS as DTLSCredential
from aiocoap.credentials import CredentialsMap
from aiocoap.numbers.codes import Code
from aiocoap.numbers.contentformat import ContentFormat
from aiocoap.resource import ObservableResource

from .const import DOMAIN
from .models import CoAPDevice, CoAPObserveResponse

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
        root.add_resource(["device", "ack"], EndpointDeviceAck(self.hass, self.coordinator))
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

    async def render_get(self, request: Message) -> Message:
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

def uri_query(request: Message) -> dict[str, str] | None:
    """Extract device_id and sensor_id from the URI query string."""
    # This function assumes you have access to the request object
    # If not, you may need to pass it as a parameter
    request.get_request_uri() # Populates request.opt.uri_query
    query_string = request.opt.uri_query if request.opt else None

    items: dict[str, str] = {}
    for query in query_string or []:
        key, value = query.split("=", 1)
        items[key] = value
    return items

# If device does not exist in HA it register here or at startup
class EndpointDevice(resource.Resource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator

    # New device, get information about it and all its sensors to publich to HA
    async def render_post(self, request: Message):
        try:
            device = CoAPDevice.from_coap_raw_new_proto(request.payload)
        except Exception as err:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if self.coordinator.push_device_data(device):
            return Message(code=Code.CHANGED, payload=b"Device updated successfully")  # or 2.04 if you want to swallow it temporarily
        return Message(code=Code.CREATED, payload=b"Device registered successfully")

    async def render_put(self, request: Message):
        try:
            device = CoAPDevice.from_coap_raw_update_proto(request.payload)
        except Exception as err:
            return Message(code=Code.BAD_REQUEST, payload=err)

        if self.coordinator.update_device_data(device):
            return Message(code=Code.CHANGED, payload=b"Device updated successfully")

        return Message(code=Code.NOT_FOUND, payload=b"Device not found")

# Device acknowledges the values it received through observe
class EndpointDeviceAck(resource.Resource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator

    async def render_put(self, request: Message):
        try:
            device = CoAPDevice.from_coap_raw_update_proto(request.payload)
        except Exception as err:
            return Message(code=Code.BAD_REQUEST, payload=str(err).encode())

        result = self.coordinator.ack_device_data(device)
        if result is None:
            return Message(code=Code.NOT_FOUND, payload=b"Device not found")
        if result["mismatched"] or result["unknown"]:
            return Message(code=Code.PRECONDITION_FAILED,
                           payload=b"Ack does not match requested state")
        return Message(code=Code.CHANGED, payload=b"Ack confirmed")

    render_post = render_put


# listen for device events from HA -> Device
class EndpointDeviceObserveEntity(resource.ObservableResource):
    def __init__(self, hass, coordinator):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator
        # Maps device_id -> set of observation keys
        self.device_observers = collections.defaultdict(set)
        # Maps observation key -> actual aiocoap ServerObservation object
        self.observations = {}
        self.handle: dict[str, asyncio.TimerHandle] = {}
        self.keep_alive_interval = 10  # seconds

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
        device_id: str|None = None
        sensor_id: int|None = None
        items = uri_query(request)
        if items:
            device_id = items.get("id")
            sensor_id_str = items.get("sensor_id")
            if sensor_id_str is not None:
                try:
                    sensor_id = int(sensor_id_str)
                except ValueError:
                    _LOGGER.error("Invalid sensor_id value: %s", sensor_id_str)
                    return

        _LOGGER.debug("Extracted device_id: %s, sensor_id: %s", device_id, sensor_id)

        if not device_id or sensor_id is None:
            _LOGGER.error("Rejected observation request: No 'id' parameter found in URI query string.")
            return

        unique_key = f"{device_id}:{sensor_id}"

        # Generate a unique key for this specific connection
        key = ObservationKey(request.token, request.remote)

        self.device_observers[unique_key].add(key)
        self.observations[key] = server_observation

        # Start the 5-second recurring notification loop
        self.reschedule(device_id=device_id, sensor_id=sensor_id)

        # 3. Clean up when the client cancels or disconnects
        def on_observation_cancelled():
            _LOGGER.debug("Observation cancelled for client %s on device %s", request.remote, device_id)

            # Cancel the pending 5-second timer handle to stop looping
            timer_handle = self.handle.pop(unique_key, None)
            if timer_handle:
                timer_handle.cancel()

            # send disconnect message to device if needed
            response = Message(payload=b"Observation cancelled", content_format=ContentFormat.TEXT)

            obs = self.observations.get(key)
            if obs:
                obs.trigger(response)

            self.device_observers[unique_key].discard(key)
            self.observations.pop(key, None)
            if not self.device_observers[unique_key]:
                del self.device_observers[unique_key]

        # In aiocoap, accept() is enough to handle all teardown/cancellation scenarios
        server_observation.accept(on_observation_cancelled)
#            server_observation.register_errback(lambda _: on_observation_cancelled())
#            server_observation.accept(on_observation_cancelled)

    def reschedule(self, device_id: str|None=None, sensor_id: int|None=None):
        unique_key = f"{device_id}:{sensor_id}"

        # Cancel any existing active timer to prevent duplicate overlapping schedules
        if unique_key in self.handle:
            self.handle[unique_key].cancel()

        self.handle[unique_key] = asyncio.get_running_loop().call_later(
            self.keep_alive_interval,
            self.notify_health, device_id, sensor_id)

    def notify_health(self, device_id: str|None=None, sensor_id: int|None=None):
        """Periodic keep-alive (OBSERVE_TYPE_HEALTH_CHECK); carries no entity values."""
        unique_key = f"{device_id}:{sensor_id}" if device_id and sensor_id is not None else None
        if not unique_key or unique_key not in self.device_observers:
            return

        _LOGGER.debug("Health check notify for device %s sensor %s", device_id, sensor_id)
        self.reschedule(device_id=device_id, sensor_id=sensor_id)

        response = Message(
            code=Code.CONTENT,
            payload=CoAPObserveResponse(id=device_id).to_proto_health(),
            content_format=ContentFormat.OCTETSTREAM
        )
        for key in list(self.device_observers[unique_key]):
            obs = self.observations.get(key)
            if obs:
                obs.trigger(response)

    def notify(self, device_id: str|None=None, sensor_id: int|None=None):
        """Triggers an OBSERVE_TYPE_UPDATE carrying the changed value to clients observing this entity."""
        _LOGGER.debug("Targeted notify for device %s", device_id)

        unique_key = f"{device_id}:{sensor_id}" if device_id and sensor_id is not None else None
        if not unique_key or unique_key not in self.device_observers:
             return

        if sensor_id is None:
            return

        sub_data = self.coordinator.get_subscribe_data(device_id, sensor_id)
        _LOGGER.debug("Subscribe data: %s", sub_data)

        if sub_data is None:
            _LOGGER.warning("No subscribe data found for device %s and sensor %s", device_id, sensor_id)
            return

        response = Message(
            code=Code.CONTENT,
            payload=CoAPObserveResponse.to_proto(sub_data),
            content_format=ContentFormat.OCTETSTREAM
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
        device_id: str|None = None
        sensor_id: int|None = None
        items = uri_query(request)
        if items:
            device_id = items.get("id")
            sensor_id_str = items.get("sensor_id")
            if sensor_id_str is not None:
                try:
                    sensor_id = int(sensor_id_str)
                except ValueError:
                    _LOGGER.error("Invalid sensor_id value: %s", sensor_id_str)
                    return

        sub_data = self.coordinator.get_subscribe_data(device_id, sensor_id)
        _LOGGER.debug("Subscribe data: %s", sub_data)

        self.reschedule(device_id=device_id, sensor_id=sensor_id)

        if sub_data is None:
            _LOGGER.warning("No subscribe data found for device %s and sensor %s", device_id, sensor_id)
            return

        return Message(
            code=Code.CONTENT,
            payload=CoAPObserveResponse.to_proto(sub_data),
            content_format=ContentFormat.OCTETSTREAM
        )
