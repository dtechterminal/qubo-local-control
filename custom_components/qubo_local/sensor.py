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
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    CONF_DEVICE_UUID,
    CONF_HANDLE_NAME,
    CONF_UNIT_UUID,
    DEVICE_TYPE_AIR_PURIFIER,
    DEVICE_TYPE_SMART_PLUG,
    DOMAIN,
    ENTITY_CURRENT,
    ENTITY_ENERGY,
    ENTITY_FILTER_LIFE,
    ENTITY_PM25,
    ENTITY_POWER,
    ENTITY_VOLTAGE,
    TOPIC_CONTROL_AQI_REFRESH,
    TOPIC_CONTROL_FILTER_STATUS,
    TOPIC_MONITOR_AQI,
    TOPIC_MONITOR_ENERGY,
    TOPIC_MONITOR_FILTER,
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
    device_type = config.get(CONF_DEVICE_TYPE, DEVICE_TYPE_SMART_PLUG)

    sensors = []

    if device_type == DEVICE_TYPE_AIR_PURIFIER:
        # Air Purifier sensors
        aqi_topic = TOPIC_MONITOR_AQI.format(
            unit_uuid=unit_uuid, device_uuid=device_uuid
        )
        filter_topic = TOPIC_MONITOR_FILTER.format(
            unit_uuid=unit_uuid, device_uuid=device_uuid
        )

        sensors = [
            QuboAQISensor(
                hass,
                config_entry,
                device_info,
                config,
                aqi_topic,
            ),
            QuboFilterSensor(
                hass,
                config_entry,
                device_info,
                config,
                filter_topic,
            ),
        ]
    else:
        # Smart Plug sensors
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
        # Energy sensors need TOTAL_INCREASING, others use MEASUREMENT
        if device_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
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


class QuboAQISensor(SensorEntity):
    """Representation of a QUBO Air Purifier PM2.5 sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.PM25
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_name = "PM2.5"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_info,
        config: dict[str, Any],
        monitor_topic: str,
    ) -> None:
        """Initialize the QUBO AQI sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_device_info = device_info
        self._config = config
        self._monitor_topic = monitor_topic

        device_uuid = config[CONF_DEVICE_UUID]
        self._attr_unique_id = f"{device_uuid}_{ENTITY_PM25}"
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when added to hass."""

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                payload = json.loads(msg.payload)
                _LOGGER.debug("Received AQI data: %s", payload)

                # Extract PM2.5 from the response
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                aqi_service = services.get("aqiStatus", {})
                events = aqi_service.get("events", {})
                state_changed = events.get("stateChanged", {})

                pm25_value = state_changed.get("PM25")

                if pm25_value is not None:
                    self._attr_native_value = int(pm25_value)
                    self.async_write_ha_state()
                    _LOGGER.debug("PM2.5 updated to: %s", self._attr_native_value)

            except (json.JSONDecodeError, KeyError, ValueError) as err:
                _LOGGER.error("Error processing AQI data: %s", err)

        # Subscribe to monitor topic
        await mqtt.async_subscribe(
            self.hass, self._monitor_topic, message_received, 1
        )


class QuboFilterSensor(SensorEntity):
    """Representation of a QUBO Air Purifier filter life sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_name = "Filter Life"
    _attr_icon = "mdi:air-filter"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_info,
        config: dict[str, Any],
        monitor_topic: str,
    ) -> None:
        """Initialize the QUBO filter sensor."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_device_info = device_info
        self._config = config
        self._monitor_topic = monitor_topic

        self._device_uuid = config[CONF_DEVICE_UUID]
        self._unit_uuid = config[CONF_UNIT_UUID]
        self._handle_name = config[CONF_HANDLE_NAME]

        self._attr_unique_id = f"{self._device_uuid}_{ENTITY_FILTER_LIFE}"
        self._attr_native_value = None

        # Topic for requesting filter status
        self._control_topic = TOPIC_CONTROL_FILTER_STATUS.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when added to hass."""

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                payload = json.loads(msg.payload)
                _LOGGER.debug("Received filter data: %s", payload)

                # Extract filter time remaining from the response
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                filter_service = services.get("filterReset", {})
                events = filter_service.get("events", {})
                state_changed = events.get("stateChanged", {})

                time_remaining = state_changed.get("timeRemaining")

                if time_remaining is not None:
                    # Value is already in hours
                    self._attr_native_value = int(time_remaining)
                    self.async_write_ha_state()
                    _LOGGER.debug("Filter life updated to: %s hours", self._attr_native_value)

            except (json.JSONDecodeError, KeyError, ValueError) as err:
                _LOGGER.error("Error processing filter data: %s", err)

        # Subscribe to monitor topic
        await mqtt.async_subscribe(
            self.hass, self._monitor_topic, message_received, 1
        )

        # Request initial filter status
        await self._request_filter_status()

    async def _request_filter_status(self) -> None:
        """Request filter status from the device."""
        payload = json.dumps({
            "command": {
                "devices": {
                    "deviceUUID": self._device_uuid,
                    "handleName": self._handle_name,
                    "services": {
                        "filterReset": {
                            "commands": {
                                "getCurrentStatus": {
                                    "instanceId": 0,
                                    "parameters": {}
                                }
                            }
                        }
                    }
                }
            }
        })

        await mqtt.async_publish(self.hass, self._control_topic, payload, qos=1)
        _LOGGER.debug("Requested filter status")
