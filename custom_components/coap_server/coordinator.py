"""Integration 101 Template integration using DataUpdateCoordinator."""

import copy
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import CoAPDevice, CoAPSensor, CoAPObserveResponse, CoAPObserveValue

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


@dataclass
class ExampleAPIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[CoAPDevice]
    coap_notify_callback: Callable[[str, int], Callable] | None = field(
        default=None, repr=False
    )


class ExampleCoordinator(DataUpdateCoordinator):
    """My example coordinator."""

    data: ExampleAPIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        # Set variables from values entered in config flow setup
        self.hass = hass
        self.port = config_entry.data[CONF_PORT]
        self.name = f"{DOMAIN} ({config_entry.unique_id})"
        self.entry_id = config_entry.entry_id

        _LOGGER.info(
            f"Initializing {self.name} with host 0.0.0.0:{self.port} devices {config_entry}"
        )

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
            # update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            # Using config option here but you can just use a value.
            # update_interval=timedelta(seconds=self.poll_interval),
        )

        # Persistent storage so known devices survive HA/coap_server restarts.
        self._store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_{config_entry.entry_id}_devices"
        )
        self._restored_from_storage = False

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
            devices=devices,
            coap_notify_callback=self.data.coap_notify_callback if self.data else None,
        )

    async def _async_restore_devices(self) -> list[CoAPDevice]:
        """Load previously known devices from storage."""
        stored = await self._store.async_load()
        if not stored:
            return []

        devices = [
            CoAPDevice.from_dict(device_data)
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
        return {"devices": [CoAPDevice.to_dict(device) for device in self.data.devices]}

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
        all_replaced = True
        for device in new_devices:
            replaced = False
            # Replace an existing device entirely so stale sensors/entities don't linger
            for i, existing_device in enumerate(devices):
                if existing_device.id == device.id:
                    _LOGGER.info(
                        "Replacing device data for %s %s",
                        device.name,
                        device.unique_id,
                    )
                    del devices[i]
                    self._remove_registry_device(device.id)
                    replaced = True
                    break

            if not replaced:
                _LOGGER.info(
                    "Adding new device data for %s %s",
                    device.name,
                    device.unique_id,
                )
            devices.append(device)
            async_dispatcher_send(
                self.hass, f"{DOMAIN}_{self.entry_id}_new_device", device
            )
            all_replaced = all_replaced and replaced

        self.async_set_updated_data(
            ExampleAPIData(
                controller_name=self.name,
                devices=devices,
                coap_notify_callback=self.data.coap_notify_callback
                if self.data
                else None,
            )  # pyright: ignore[reportArgumentType]
        )
        self._async_save_devices()
        return all_replaced

    def _remove_registry_device(self, device_id: str) -> None:
        """Remove the HA device (and its entities) so it can be recreated from scratch."""
        registry = dr.async_get(self.hass)
        identifier = (DOMAIN, f"{self.name}-{device_id}")
        entry = registry.async_get_device(identifiers={identifier})
        if entry is not None:
            registry.async_remove_device(entry.id)

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
                            changed = existing_sensor.state != sensor.state
                            existing_sensor.state = sensor.state
                            matched_sensor_ids.append(sensor.id)
                            sensor_found = True
                            # Only notify observers on a real change, otherwise a device
                            # echoing the observed value back would loop forever.
                            if changed and self.data.coap_notify_callback is not None:
                                self.data.coap_notify_callback(device.id, sensor.id)
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
                    coap_notify_callback=self.data.coap_notify_callback
                    if self.data
                    else None,
                )  # pyright: ignore[reportArgumentType]
            )
            # Maybe remove this one, we might not need this one...
        #            self._async_save_devices_debounced()
        return updated

    #
    #
    # Public methods called by the CoAP API to push data into the coordinator
    #
    #

    def async_add_notifyer(self, listener) -> callable:
        """Add a listener to the coordinator."""
        self.data.coap_notify_callback = listener
        return self.async_unregister_notifyer

    def async_unregister_notifyer(self) -> None:
        """Remove a listener from the coordinator."""
        self.data.coap_notify_callback = None

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
                coap_notify_callback=self.data.coap_notify_callback
                if self.data
                else None,
            )  # pyright: ignore[reportArgumentType]
        )
        self._async_save_devices()
        return True

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

    def update_sensor_data(
        self, device_id: str, sensor_id: int, state: float | int | str | bool
    ) -> bool:
        """
        Called by switch.py to update sensor data into the coordinator.
        """
        device = self.get_device_by_id(device_id)
        if not device:
            _LOGGER.warning("Device with id %s not found", device_id)
            return False

        sensor = self.get_sensor_by_id(device_id, sensor_id)
        if not sensor:
            _LOGGER.warning(
                "Sensor with id %s not found for device %s", sensor_id, device_id
            )
            return False

        # Don't mutate the stored sensor here; _update_device compares against it
        # to decide whether observers need a notification.
        update = copy.copy(sensor)
        update.state = state
        return self._update_device(CoAPDevice(id=device.id, sensors=[update]))

    def get_device_by_id(self, device_id: str) -> CoAPDevice | None:
        """Return device by device id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        for device in self.data.devices:
            if device.id == device_id:
                return device
        return None

    def get_sensor_by_id(self, device_id: str, sensor_id: int) -> CoAPSensor | None:
        """Return sensor by device id and sensor id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        for device in self.data.devices:
            if device.id == device_id:
                for sensor in device.sensors:
                    if sensor.id == sensor_id:
                        return sensor
        _LOGGER.warning(
            "Sensor with id %s not found for device %s", sensor_id, device_id
        )
        return None

    def get_subscribe_data(
        self, device_id: str, sensor_id: int
    ) -> CoAPObserveResponse | None:
        """Return True if a sensor is  notify_callback subscribed to the coordinator."""

        sensor = self.get_sensor_by_id(device_id, sensor_id)
        if not sensor:
            _LOGGER.warning(
                "Sensor with id %s not found for device %s", sensor_id, device_id
            )
            return None
        return CoAPObserveResponse(
            id=device_id, sensors=[CoAPObserveValue(id=sensor.id, state=sensor.state)]
        )
