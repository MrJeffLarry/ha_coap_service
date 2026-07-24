from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):

    # Callback to dynamically add new entities
    async def _add_new_device(data):
        device_id = data.get("device_id") or data.get("client_id")
        if not device_id:
            return

        new_entities = []
        for sensor in data.get("sensors", []):
            new_entities.append(CoapSensor(device_id, "hagerman", sensor))
        async_add_entities(new_entities)

    async_dispatcher_connect(hass, f"{DOMAIN}_new_device", _add_new_device)


class CoapSensor(SensorEntity):
    def __init__(self, device_id, vendor, sensor):
        self._state = sensor.get("value")
        self._device_id = device_id
        self._vendor = vendor
        self._attr_device_class = sensor.get("type")
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{self._attr_device_class}"
        self._attr_name = f"{self._attr_device_class.capitalize()}"

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device_id)
            },  # Same identifier = Same Device Group
            "name": f"CoAP Device {self._device_id}",
            "manufacturer": self._vendor,
        }

    @property
    def state(self):
        return self._state

    async def async_added_to_hass(self):
        # Listen for updates specific to this instance
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update_{self._device_id}", self._update_callback
            )
        )

    def _update_callback(self, data):
        for sensor in data.get("sensors"):
            if sensor.get("type") == self._attr_device_class:
                self._state = sensor.get("value")
                self.async_write_ha_state()
                break
