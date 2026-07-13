from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([CoapSensor(hass)])

class CoapSensor(SensorEntity):
    def __init__(self, hass):
        self._state = None
        self.hass = hass

    async def async_added_to_hass(self):
        # Register a listener for the signal coming from your CoAP resource
        self.async_on_remove(
            async_dispatcher_connect(self.hass, "coap_update_signal", self._update_callback)
        )

    def _update_callback(self, new_value):
        self._state = new_value
        self.async_write_ha_state() # Notify HA that the state changed
