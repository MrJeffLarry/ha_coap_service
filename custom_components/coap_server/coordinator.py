"""Integration 101 Template integration using DataUpdateCoordinator."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .api import API, APIAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import CoAPDevice, CoAPDeviceType, CoAPSensor

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def _sensor_to_dict(sensor: CoAPSensor) -> dict:
    """Serialise a CoAPSensor for storage."""
    return {
        "id": sensor.id,
        "name": sensor.name,
        "type": sensor.type.value if sensor.type else None,
        "unit": sensor.unit,
        "state": sensor.state,
        "state_class": sensor.state_class.value if sensor.state_class else None,
    }


def _sensor_from_dict(data: dict) -> CoAPSensor:
    """Deserialise a CoAPSensor from storage."""
    sensor_type: SensorDeviceClass | BinarySensorDeviceClass | None = None
    raw_type = data.get("type")
    if raw_type:
        try:
            sensor_type = SensorDeviceClass(raw_type)
        except ValueError:
            try:
                sensor_type = BinarySensorDeviceClass(raw_type)
            except ValueError:
                sensor_type = None

    state_class: SensorStateClass | None = None
    if data.get("state_class"):
        try:
            state_class = SensorStateClass(data["state_class"])
        except ValueError:
            state_class = None

    return CoAPSensor(
        id=data.get("id"),
        name=data.get("name"),
        type=sensor_type,
        unit=data.get("unit"),
        state=data.get("state"),
        state_class=state_class,
    )


def _device_to_dict(device: CoAPDevice) -> dict:
    """Serialise a CoAPDevice for storage."""
    return {
        "id": device.id,
        "unique_id": device.unique_id,
        "name": device.name,
        "model": device.model,
        "manufacturer": device.manufacturer,
        "sw_version": device.sw_version,
        "hw_version": device.hw_version,
        "sensors": [_sensor_to_dict(sensor) for sensor in device.sensors],
    }


def _device_from_dict(data: dict) -> CoAPDevice:
    """Deserialise a CoAPDevice from storage."""
    device = CoAPDevice(
        id=data.get("id"),
        unique_id=data.get("unique_id"),
        name=data.get("name"),
        model=data.get("model"),
        manufacturer=data.get("manufacturer"),
        sw_version=data.get("sw_version"),
        hw_version=data.get("hw_version"),
    )
    device.sensors = [
        _sensor_from_dict(sensor_data) for sensor_data in data.get("sensors", [])
    ]
    return device


@dataclass
class ExampleAPIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[CoAPDevice]


class ExampleCoordinator(DataUpdateCoordinator):
    """My example coordinator."""

    data: ExampleAPIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        # Set variables from values entered in config flow setup
        self.hass = hass
        self.host = config_entry.data[CONF_HOST]
        self.port = config_entry.data[CONF_PORT]
        self.user = config_entry.data[CONF_USERNAME]
        self.pwd = config_entry.data[CONF_PASSWORD]
        self.name = f"{DOMAIN} ({config_entry.unique_id})"
        self.entry_id = config_entry.entry_id

        _LOGGER.info(f"Initializing {self.name} with host {self.host}:{self.port} devices {config_entry}")

        # set variables from options.  You need a default here incase options have not been set
        self.poll_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Initialise DataUpdateCoordinator. Passing config_entry explicitly avoids
        # relying on HA's ContextVar-based fallback (config_entries.current_entry),
        # which is fragile when many entries are being set up concurrently, e.g.
        # during a full HA restart.
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=self.name,
            # Method to call on every update interval.
            #update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            # Using config option here but you can just use a value.
            #update_interval=timedelta(seconds=self.poll_interval),
        )

        # Persistent storage so known devices survive HA/coap_server restarts.
        self._store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{config_entry.entry_id}_devices"
        )
        self._restored_from_storage = False

        # Initialise your api here
#        self.api = API(host=self.host, user=self.user, pwd=self.pwd)

    async def _async_restore_devices(self) -> list[CoAPDevice]:
        """Load previously known devices from storage."""
        stored = await self._store.async_load()
        if not stored:
            return []

        devices = [
            _device_from_dict(device_data)
            for device_data in stored.get("devices", [])
        ]
        _LOGGER.info("Restored %d device(s) from storage", len(devices))
        for device in devices:
            async_dispatcher_send(
                self.hass, f"{DOMAIN}_{self.entry_id}_new_device", device
            )
        return devices

    def _devices_payload(self) -> dict:
        """Build the JSON-serialisable payload representing all known devices."""
        return {"devices": [_device_to_dict(device) for device in self.data.devices]}

    def _async_save_devices(self) -> None:
        """Persist the current device list immediately (e.g. when a device is added)."""
        if not self.data:
            return
        self.hass.async_create_task(self._store.async_save(self._devices_payload()))

    def _async_save_devices_debounced(self) -> None:
        """Persist the current device list, debounced to limit disk writes on frequent sensor updates."""
        if not self.data:
            return
        self._store.async_delay_save(self._devices_payload, 5)

    def _add_devices(self, new_devices: list[CoAPDevice]) -> bool:
        """Add devices to the coordinator."""
        devices = self.data.devices if self.data else []
        for device in new_devices:
            found = False
            # Update the device in the list if it exists, otherwise add it
            for i, existing_device in enumerate(devices):
                if existing_device.id == device.id:
                    _LOGGER.info(
                        "Refreshing device data for %s %s",
                        device.name,
                        device.unique_id,
                    )
                    devices[i] = device
                    found = True
                    break

            if not found:
                _LOGGER.info(
                    "Adding new device data for %s %s",
                    device.name,
                    device.unique_id,
                )
                devices.append(device)
                async_dispatcher_send(
                    self.hass, f"{DOMAIN}_{self.entry_id}_new_device", device
                )

        self.async_set_updated_data(
            ExampleAPIData(
                controller_name=self.name,
                devices=devices,
            ) # pyright: ignore[reportArgumentType]
        )
        self._async_save_devices()
        return True

    def async_remove_device(self, device_id: str) -> bool:
        """Remove a device (e.g. deleted via the UI) from the coordinator and storage."""
        if not self.data:
            return False

        devices = [d for d in self.data.devices if d.id != device_id]
        if len(devices) == len(self.data.devices):
            return False

        _LOGGER.info("Removing device %s from coordinator", device_id)
        self.async_set_updated_data(
            ExampleAPIData(
                controller_name=self.name,
                devices=devices,
            ) # pyright: ignore[reportArgumentType]
        )
        self._async_save_devices()
        return True

    def _update_device(self, device: CoAPDevice) -> bool:
        """Update device in the coordinator."""
        devices = self.data.devices if self.data else []
        _LOGGER.debug(
            "PUT update received on entry %s for device %s (known device ids: %s)",
            self.entry_id,
            device.id,
            [d.id for d in devices],
        )
        updated = False
        for i, existing_device in enumerate(devices):
            if existing_device.id == device.id:
                matched_sensor_ids = []
                unmatched_sensor_ids = []
                for sensor in device.sensors:
                    sensor_found = False
                    for existing_sensor in existing_device.sensors:
                        if existing_sensor.id == sensor.id:
                            existing_sensor.state = sensor.state
                            matched_sensor_ids.append(sensor.id)
                            sensor_found = True
                            break
                    if not sensor_found:
                        unmatched_sensor_ids.append(sensor.id)
                if unmatched_sensor_ids:
                    _LOGGER.warning(
                        "PUT update for device %s had sensor id(s) %s that don't match "
                        "any known sensor (known sensor ids: %s)",
                        device.id,
                        unmatched_sensor_ids,
                        [s.id for s in existing_device.sensors],
                    )
                _LOGGER.info(
                    "Updated device %s sensor(s) %s", device.id, matched_sensor_ids
                )
                devices[i] = existing_device
                updated = True
                break

        if not updated:
            _LOGGER.warning(
                "PUT update for unknown device %s ignored (known device ids: %s)",
                device.id,
                [d.id for d in devices],
            )

        if updated:
            self.async_set_updated_data(
                ExampleAPIData(
                    controller_name=self.name,
                    devices=devices,
                ) # pyright: ignore[reportArgumentType]
            )
            self._async_save_devices_debounced()
        return updated

    def push_device_data(self, device: CoAPDevice) -> bool:
        """
        Called by the CoAP API to push updated device data into the coordinator.

        This triggers all subscribed entities to refresh their state.
        """
        return self._add_devices([device])

    def update_device_data(self, device: CoAPDevice) -> bool:
        """
        Called by the CoAP API to update device data into the coordinator.

        This triggers all subscribed entities to refresh their state.
        """
        return self._update_device(device)

    async def _async_update_data(self):
        if self.data:
            devices = self.data.devices
        elif not self._restored_from_storage:
            self._restored_from_storage = True
            devices = await self._async_restore_devices()
        else:
            devices = []

        return ExampleAPIData(
            controller_name=self.name,
            devices=devices)

    def get_device_by_id(self, device_id: str) -> CoAPDevice | None:
        """Return device by device id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        try:
            return [
                device
                for device in self.data.devices
                if device.id == device_id
            ][0]
        except IndexError:
            return None

    def get_sensor_by_id(self, device_id: str, sensor_id: int) -> CoAPSensor | None:
        """Return sensor by device id and sensor id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        for device in self.data.devices:
            if device.id == device_id:
                for sensor in device.sensors:
                    if sensor.id == sensor_id:
                        return sensor
        _LOGGER.warning("Sensor with id %s not found for device %s", sensor_id, device_id)
        return None
