from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import DOMAIN, SENSORS, ID, MANUFACTURER, SW_VERSION, HW_VERSION, JSON_TYPE, JSON_VALUE


async def async_setup_entry(hass, config_entry, async_add_entities):

    # 1. Restore existing devices saved in config_entry.data (on HA Restart)
    if SENSORS in config_entry.data:
        existing_entities = [
            CoapSensor(config_entry.data, sensor)
            for sensor in config_entry.data[SENSORS]
        ]
        async_add_entities(existing_entities)

    # Callback to dynamically add new entities
    async def _add_new_device(device):
        if not device[ID]:
            return

        new_entities = []
        for sensor in device[SENSORS]:
            new_entities.append(CoapSensor(device, sensor))
        async_add_entities(new_entities)

    async_dispatcher_connect(hass, f"{DOMAIN}_new_device", _add_new_device)


class CoapSensor(SensorEntity):
    def __init__(self, device, sensor):
        self._state = sensor.get(JSON_VALUE, 0)
        self._device_id = device[ID]
        self._manufacturer = device[MANUFACTURER]
        self._sw_version = device[SW_VERSION]
        self._hw_version = device[HW_VERSION]
        self._attr_device_class = sensor[JSON_TYPE]
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{self._attr_device_class}"
        self._attr_name = f"{self._attr_device_class.capitalize()}"

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._device_id)
            },  # Same identifier = Same Device Group
            "name": f"CoAP Device {self._device_id}",
            "manufacturer": self._manufacturer,
            "sw_version": self._sw_version,
            "hw_version": self._hw_version
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
        for sensor in data.get(SENSORS):
            if sensor.get(JSON_TYPE) == self._attr_device_class:
                self._state = sensor.get(JSON_VALUE)
                self.async_write_ha_state()
                break
