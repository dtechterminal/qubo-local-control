"""Sensor platform for QUBO smart plugs and air purifiers."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import protocol
from .device import QuboConfigEntry, QuboDevice
from .entity import QuboEntity


@dataclass(frozen=True, kw_only=True)
class QuboSensorDescription(SensorEntityDescription):
    """Where a sensor's value comes from."""

    service: str
    field: str
    convert: Callable[[Any], float | int] = lambda value: round(float(value), 3)


PLUG_SENSORS = (
    QuboSensorDescription(
        key="power", name="Power", service=protocol.SERVICE_METERING, field="power",
        device_class=SensorDeviceClass.POWER, state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    QuboSensorDescription(
        key="voltage", name="Voltage", service=protocol.SERVICE_METERING, field="voltage",
        device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    QuboSensorDescription(
        # The plug reports milliamps
        key="current", name="Current", service=protocol.SERVICE_METERING, field="current",
        convert=lambda value: round(float(value) / 1000, 3),
        device_class=SensorDeviceClass.CURRENT, state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    QuboSensorDescription(
        key="energy", name="Energy", service=protocol.SERVICE_METERING, field="consumption",
        device_class=SensorDeviceClass.ENERGY, state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
)

PURIFIER_SENSORS = (
    QuboSensorDescription(
        key="pm25", name="PM2.5", service=protocol.SERVICE_AQI, field="PM25", convert=int,
        device_class=SensorDeviceClass.PM25, state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    QuboSensorDescription(
        # The purifier reports hours
        key="filter_life", name="Filter Life", service=protocol.SERVICE_FILTER,
        field="timeRemaining", convert=int, icon="mdi:air-filter",
        state_class=SensorStateClass.MEASUREMENT, native_unit_of_measurement=UnitOfTime.HOURS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device's sensors."""
    device = entry.runtime_data
    descriptions = PURIFIER_SENSORS if device.is_purifier else PLUG_SENSORS
    async_add_entities(QuboSensor(device, description) for description in descriptions)


class QuboSensor(QuboEntity, SensorEntity):
    """A value reported by a QUBO device."""

    entity_description: QuboSensorDescription

    def __init__(self, device: QuboDevice, description: QuboSensorDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description
        self.services = (description.service,)

    def _handle_values(self, service: str, values: dict[str, Any]) -> None:
        if (value := values.get(self.entity_description.field)) is None:
            return
        try:
            self._attr_native_value = self.entity_description.convert(value)
        except (TypeError, ValueError):
            pass  # Keep the last good reading
