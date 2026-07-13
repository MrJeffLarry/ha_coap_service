from homeassistant.components.switch import SwitchEntity
from aiocoap import Message, Context, Code
from .const import DOMAIN

class CoapSwitch(SwitchEntity):
    def __init__(self, device_id, ip_address):
        self._device_id = device_id
        self._ip_address = ip_address # You need to store the IP!
        self._attr_unique_id = f"{DOMAIN}_{device_id}_switch"
        self._state = False

    @property
    def is_on(self):
        return self._state

    async def async_turn_on(self, **kwargs):
        await self._send_coap_command("ON")
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._send_coap_command("OFF")
        self._state = False
        self.async_write_ha_state()

    async def _send_coap_command(self, command):
        # Create a CoAP client context
        protocol = await Context.create_client_context()
        
        # Build the URI (e.g., coap://[fd00::1234]/actuator)
        uri = f"coap://[{self._ip_address}]/actuator"
        
        # Send request
        request = Message(code=Code.PUT, payload=command.encode())
        request.set_request_uri(uri)
        
        try:
            response = await protocol.request(request).response
            # Handle response if necessary
        except Exception as e:
            # Handle network errors (device asleep, unreachable, etc)
            pass
