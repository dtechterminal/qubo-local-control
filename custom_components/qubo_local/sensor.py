"""Sensor platform for QUBO Local Control integration."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_UUID,
    CONF_UNIT_UUID,
    DOMAIN,
    ENTITY_CURRENT,
    ENTITY_ENERGY,
    ENTITY_POWER,
    ENTITY_VOLTAGE,
    TOPIC_MONITOR_ENERGY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up QUBO sensors from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device_info = data["device_info"]
    config = data["config"]

    device_uuid = config[CONF_DEVICE_UUID]
    unit_uuid = config[CONF_UNIT_UUID]

    monitor_topic = TOPIC_MONITOR_ENERGY.format(
        unit_uuid=unit_uuid, device_uuid=device_uuid
    )

    sensors = [
        QuboEnergySensor(
            hass,
            config_entry,
            device_info,
            config,
            monitor_topic,
            ENTITY_POWER,
            "Power",
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            "power",
        ),
        QuboEnergySensor(
            hass,
            config_entry,
            device_info,
            config,
            monitor_topic,
            ENTITY_VOLTAGE,
            "Voltage",
            SensorDeviceClass.VOLTAGE,
            UnitOfElectricPotential.VOLT,
            "voltage",
        ),
        QuboEnergySensor(
            hass,
            config_entry,
            device_info,
            config,
            monitor_topic,
            ENTITY_CURRENT,
            "Current",
            SensorDeviceClass.CURRENT,
            UnitOfElectricCurrent.AMPERE,
            "current",
        ),
        QuboEnergySensor(
            hass,
            config_entry,
            device_info,
            config,
            monitor_topic,
            ENTITY_ENERGY,
            "Energy",
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
            "consumption",
        ),
    ]

    async_add_entities(sensors)


class QuboEnergySensor(SensorEntity):
    """Representation of a QUBO energy monitoring sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_info,
        config: dict[str, Any],
        monitor_topic: str,
        entity_id: str,
        name: str,
        device_class: SensorDeviceClass,
        unit: str,
        data_key: str,
    ) -> None:
        """Initialize the QUBO sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_device_info = device_info
        self._config = config
        self._monitor_topic = monitor_topic
        self._data_key = data_key

        device_uuid = config[CONF_DEVICE_UUID]
        self._attr_unique_id = f"{device_uuid}_{entity_id}"
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when added to hass."""

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                payload = json.loads(msg.payload)
                _LOGGER.debug("Received energy data: %s", payload)

                # Extract energy metrics from the response
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                metering_service = services.get("plugMetering", {})
                events = metering_service.get("events", {})
                state_changed = events.get("stateChanged", {})

                value = state_changed.get(self._data_key)

                if value is not None:
                    # Convert string to float
                    numeric_value = float(value)

                    # Convert current from mA to A
                    if self._data_key == "current":
                        numeric_value = numeric_value / 1000.0

                    self._attr_native_value = round(numeric_value, 3)
                    self.async_write_ha_state()
                    _LOGGER.debug(
                        "%s updated to: %s %s",
                        self._attr_name,
                        self._attr_native_value,
                        self._attr_native_unit_of_measurement,
                    )

            except (json.JSONDecodeError, KeyError, ValueError) as err:
                _LOGGER.error("Error processing energy data: %s", err)

        # Subscribe to monitor topic
        await mqtt.async_subscribe(
            self.hass, self._monitor_topic, message_received, 1
        )
