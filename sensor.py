from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    
    # Callback to dynamically add new entities
    async def _add_new_device(device_id):
        async_add_entities([CoapSensor(device_id)])

    async_dispatcher_connect(hass, f"{DOMAIN}_new_device", _add_new_device)

class CoapSensor(SensorEntity):
    def __init__(self, device_id):
        self._attr_unique_id = f"{DOMAIN}_{device_id}"
        self._attr_name = f"CoAP Sensor {device_id}"
        self._state = None

    @property
    def state(self):
        return self._state

    async def async_added_to_hass(self):
        # Listen for updates specific to this instance
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update_{self._attr_unique_id}", self._update_callback
            )
        )

    def _update_callback(self, value):
        self._state = value
        self.async_write_ha_state()
