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
        psk_key: str | None = None,
        health_interval: int = 10) -> None:
        """Initialise services."""
        self.hass = hass
        self.port = port
        self.coordinator = coordinator
        self.use_dtls = use_dtls
        self.psk_identity = psk_identity
        self.psk_key = psk_key
        self.health_interval = health_interval
        self.observe_resource: EndpointDeviceObserveEntity | None = None

    async def setup_services(self) -> Context:
        """Setup CoAP server and register services."""

        # Pre-load modules that perform blocking disk I/O on import (like filelock)
        # inside an executor thread pool to avoid event loop warnings.
        await self.hass.async_add_executor_job(self._preload_dependencies)

        root = resource.Site()
        root.add_resource(["whoami"], WhoAmI(self.hass, self.coordinator))
        root.add_resource(["device"], EndpointDevice(self.hass, self.coordinator))
        self.observe_resource = EndpointDeviceObserveEntity(self.hass, self.coordinator, self.health_interval)
        root.add_resource(["device", "observe"], self.observe_resource)

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

    def stop_health_checks(self) -> None:
        """Stop the observe resource's timers (called on unload/reload)."""
        if self.observe_resource:
            self.observe_resource.stop_health_checks()

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

def parse_observe_query(request: Message) -> tuple[str | None, list[int]]:
    """Return the device id and de-duplicated sensor ids from the query.

    'sensor_id' may be repeated (sensor_id=1&sensor_id=2) and/or comma separated.
    """
    request.get_request_uri()
    device_id: str | None = None
    sensor_ids: list[int] = []
    for query in (request.opt.uri_query if request.opt else None) or []:
        name, _, value = query.partition("=")
        if name == "id":
            device_id = value
        elif name == "sensor_id":
            for part in value.split(","):
                sensor_id = int(part)
                if sensor_id not in sensor_ids:
                    sensor_ids.append(sensor_id)
    return device_id, sensor_ids

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

# listen for device events from HA -> Device
class EndpointDeviceObserveEntity(resource.ObservableResource):
    def __init__(self, hass, coordinator, keep_alive_interval: int = 10):
        super().__init__()
        self.hass = hass
        self.coordinator = coordinator
        # Maps device_id -> set of observation keys
        self.device_observers = collections.defaultdict(set)
        # Maps observation key -> actual aiocoap ServerObservation object
        self.observations = {}
        self.handle: dict[ObservationKey, asyncio.TimerHandle] = {}
        self.keep_alive_interval = keep_alive_interval  # seconds
        # Maps observation key -> number of health checks sent
        self.health_counters: dict[ObservationKey, int] = {}

        # Register the callback with the coordinator on init
        # This assumes your coordinator can call: callback(device_id)
        if hasattr(self.coordinator, "async_add_notifyer"):
            self._unregister_callback = self.coordinator.async_add_notifyer(self.notify)

    def stop_health_checks(self):
        """Cancel pending health-check timers so a stale resource stops notifying."""
        for handle in self.handle.values():
            handle.cancel()
        self.handle.clear()
        self.device_observers.clear()
        self.observations.clear()
        self.health_counters.clear()

    async def add_observation(self, request, server_observation):
        """Called automatically by aiocoap when a client requests observation."""
        _LOGGER.debug("Observation requested for /device/observe %s", request)
        if server_observation is None:
            return

        try:
            device_id, sensor_ids = parse_observe_query(request)
        except ValueError as err:
            _LOGGER.error("Rejected observation request: %s", err)
            return

        _LOGGER.debug("Extracted device_id: %s, sensor_ids: %s", device_id, sensor_ids)

        if not device_id or not sensor_ids:
            _LOGGER.error("Rejected observation request: 'id' and at least one 'sensor_id' are required in URI query string.")
            return

        unique_keys = [f"{device_id}:{sensor_id}" for sensor_id in sensor_ids]

        # Generate a unique key for this specific connection
        key = ObservationKey(request.token, request.remote)

        for unique_key in unique_keys:
            self.device_observers[unique_key].add(key)
        self.observations[key] = server_observation

        # Start the recurring health-check loop for this observation
        self.reschedule(key, device_id)

        # Clean up when the client cancels or disconnects
        def on_observation_cancelled():
            _LOGGER.debug("Observation cancelled for client %s on device %s", request.remote, device_id)

            # Cancel the pending timer handle to stop looping
            timer_handle = self.handle.pop(key, None)
            if timer_handle:
                timer_handle.cancel()
            self.health_counters.pop(key, None)

            # send disconnect message to device if needed
            response = Message(payload=b"Observation cancelled", content_format=ContentFormat.TEXT)

            obs = self.observations.get(key)
            if obs:
                obs.trigger(response)

            for unique_key in unique_keys:
                observers = self.device_observers.get(unique_key)
                if observers is None:
                    continue
                observers.discard(key)
                if not observers:
                    del self.device_observers[unique_key]
            self.observations.pop(key, None)

        # In aiocoap, accept() is enough to handle all teardown/cancellation scenarios
        server_observation.accept(on_observation_cancelled)

    def reschedule(self, key: ObservationKey, device_id: str):
        # Cancel any existing active timer to prevent duplicate overlapping schedules
        if key in self.handle:
            self.handle[key].cancel()

        self.handle[key] = asyncio.get_running_loop().call_later(
            self.keep_alive_interval,
            self.notify_health, key, device_id)

    def notify_health(self, key: ObservationKey, device_id: str):
        """Periodic keep-alive (OBSERVE_TYPE_HEALTH_CHECK); carries no entity values."""
        obs = self.observations.get(key)
        if obs is None:
            return

        _LOGGER.debug("Health check notify for device %s", device_id)
        self.reschedule(key, device_id)

        counter = self.health_counters.get(key, 0) + 1
        self.health_counters[key] = counter

        obs.trigger(Message(
            code=Code.CONTENT,
            payload=CoAPObserveResponse(id=device_id).to_proto_health(counter),
            content_format=ContentFormat.OCTETSTREAM
        ))

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
        try:
            device_id, sensor_ids = parse_observe_query(request)
        except ValueError as err:
            _LOGGER.error("Invalid observe request: %s", err)
            return

        sensors = []
        for sensor_id in sensor_ids:
            sub_data = self.coordinator.get_subscribe_data(device_id, sensor_id)
            _LOGGER.debug("Subscribe data: %s", sub_data)
            if sub_data is None:
                _LOGGER.warning("No subscribe data found for device %s and sensor %s", device_id, sensor_id)
                continue
            sensors.extend(sub_data.sensors)

        if not sensors:
            return

        return Message(
            code=Code.CONTENT,
            payload=CoAPObserveResponse.to_proto(CoAPObserveResponse(id=device_id, sensors=sensors)),
            content_format=ContentFormat.OCTETSTREAM
        )
