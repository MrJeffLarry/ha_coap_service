import os
import sys
import types
from unittest.mock import MagicMock, AsyncMock

# The repository root directory (ha_coap_service) itself is the package.
# To import ha_coap_service, we must add its parent directory (two levels up from this file) to sys.path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Create Home Assistant mock classes and modules
class MockEntity:
    def __init__(self, *args, **kwargs):
        self.hass = None
        self._state = None

    def async_on_remove(self, callback):
        pass

    def async_write_ha_state(self):
        pass


class MockSensorEntity(MockEntity):
    pass


class MockSwitchEntity(MockEntity):
    pass


class MockConfigFlow:
    VERSION = 1
    def __init__(self, *args, **kwargs):
        self.hass = MagicMock()
        self._errors = {}

    def _async_current_entries(self):
        return []

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}

    def async_show_form(self, step_id, user_input=None):
        return {"type": "form", "step_id": step_id}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}


class MockConfigEntry:
    def __init__(self, entry_id="mock_entry_id", unique_id="mock_unique_id", data=None):
        self.entry_id = entry_id
        self.unique_id = unique_id
        self.data = data or {}


# Set up mocks
mock_core = types.ModuleType('homeassistant.core')
mock_core.HomeAssistant = MagicMock

mock_config_entries = types.ModuleType('homeassistant.config_entries')
mock_config_entries.ConfigFlow = MockConfigFlow
mock_config_entries.ConfigEntry = MockConfigEntry
mock_config_entries.ConfigFlowResult = dict
mock_config_entries.CONN_CLASS_LOCAL_PUSH = "local_push"
mock_config_entries.HANDLERS = MagicMock()
mock_config_entries.HANDLERS.register = lambda domain: lambda cls: cls

mock_er = types.ModuleType('homeassistant.helpers.entity_registry')
mock_er.async_get = MagicMock(return_value=MagicMock())
mock_er.async_entries_for_config_entry = MagicMock(return_value=[])

mock_dispatcher = types.ModuleType('homeassistant.helpers.dispatcher')
mock_dispatcher.async_dispatcher_send = MagicMock()
mock_dispatcher.async_dispatcher_connect = MagicMock()

mock_sensor = types.ModuleType('homeassistant.components.sensor')
mock_sensor.SensorEntity = MockSensorEntity

mock_switch = types.ModuleType('homeassistant.components.switch')
mock_switch.SwitchEntity = MockSwitchEntity

# Setup module hierarchy
homeassistant = types.ModuleType('homeassistant')
homeassistant.core = mock_core
homeassistant.config_entries = mock_config_entries
homeassistant.helpers = types.ModuleType('homeassistant.helpers')
homeassistant.helpers.entity_registry = mock_er
homeassistant.helpers.dispatcher = mock_dispatcher
homeassistant.components = types.ModuleType('homeassistant.components')
homeassistant.components.sensor = mock_sensor
homeassistant.components.switch = mock_switch

# Inject modules into sys.modules
sys.modules['homeassistant'] = homeassistant
sys.modules['homeassistant.core'] = mock_core
sys.modules['homeassistant.config_entries'] = mock_config_entries
sys.modules['homeassistant.helpers'] = homeassistant.helpers
sys.modules['homeassistant.helpers.entity_registry'] = mock_er
sys.modules['homeassistant.helpers.dispatcher'] = mock_dispatcher
sys.modules['homeassistant.components'] = homeassistant.components
sys.modules['homeassistant.components.sensor'] = mock_sensor
sys.modules['homeassistant.components.switch'] = mock_switch
