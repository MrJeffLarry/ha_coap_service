from enum import StrEnum
from dataclasses import dataclass, field

class OneClass(StrEnum):
    # On means low, Off means normal
    OneBat = "battery"

class TwoClass(StrEnum):
    # On means low, Off means normal
    TwoBat = "battery"

@dataclass
class FixtureSensor:
    """Device sensor."""
    id: str
    one: type | None = None
    two: type | None = None

sensor = FixtureSensor(id="sensor_1", one=OneClass.OneBat, two=OneClass)

if isinstance(sensor.one, sensor.two):
    print(f"Sensor is of type %s" % type(sensor.one).__name__)
elif isinstance(sensor.one, sensor.two):
    print(f"Sensor is of type %s" % type(sensor.one).__name__)
