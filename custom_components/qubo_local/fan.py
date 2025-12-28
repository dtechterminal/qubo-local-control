"""Fan platform for QUBO Air Purifier."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import (
    CONF_DEVICE_TYPE,
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_UNIT_UUID,
    DEVICE_TYPE_AIR_PURIFIER,
    DOMAIN,
    ENTITY_FAN,
    PURIFIER_MODE_AUTO,
    PURIFIER_MODE_MANUAL,
    PURIFIER_SPEED_HIGH,
    PURIFIER_SPEED_LOW,
    PURIFIER_SPEED_MEDIUM,
    TOPIC_CONTROL_FAN_MODE,
    TOPIC_CONTROL_FAN_SPEED,
    TOPIC_CONTROL_SWITCH,
    TOPIC_MONITOR_AQI,
    TOPIC_MONITOR_FAN_MODE,
    TOPIC_MONITOR_FAN_SPEED,
    TOPIC_MONITOR_FILTER,
    TOPIC_MONITOR_SWITCH,
)

_LOGGER = logging.getLogger(__name__)

# Ordered speed levels for percentage calculation
ORDERED_NAMED_FAN_SPEEDS = [PURIFIER_SPEED_LOW, PURIFIER_SPEED_MEDIUM, PURIFIER_SPEED_HIGH]

# Preset modes
PRESET_MODE_AUTO = "Auto"
PRESET_MODE_MANUAL = "Manual"
PRESET_MODES = [PRESET_MODE_AUTO, PRESET_MODE_MANUAL]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up QUBO Air Purifier fan from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device_info = data["device_info"]
    config = data["config"]

    # Only add fan entity for air purifiers
    if config.get(CONF_DEVICE_TYPE) != DEVICE_TYPE_AIR_PURIFIER:
        return

    async_add_entities([QuboAirPurifier(hass, config_entry, device_info, config)])


class QuboAirPurifier(FanEntity, RestoreEntity):
    """Representation of a QUBO Air Purifier."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
    _attr_preset_modes = PRESET_MODES
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_info,
        config: dict[str, Any],
    ) -> None:
        """Initialize the QUBO Air Purifier."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_device_info = device_info
        self._config = config

        self._device_uuid = config[CONF_DEVICE_UUID]
        self._entity_uuid = config[CONF_ENTITY_UUID]
        self._unit_uuid = config[CONF_UNIT_UUID]

        self._attr_unique_id = f"{self._device_uuid}_{ENTITY_FAN}"
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_preset_mode = PRESET_MODE_AUTO
        self._current_speed = PURIFIER_SPEED_LOW

        # Extra attributes for purifier-card compatibility
        self._pm25: int | None = None
        self._filter_life_remaining: float | None = None

        # MQTT topics - Control
        self._control_switch_topic = TOPIC_CONTROL_SWITCH.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._control_speed_topic = TOPIC_CONTROL_FAN_SPEED.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._control_mode_topic = TOPIC_CONTROL_FAN_MODE.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )

        # MQTT topics - Monitor
        self._monitor_switch_topic = TOPIC_MONITOR_SWITCH.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_speed_topic = TOPIC_MONITOR_FAN_SPEED.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_mode_topic = TOPIC_MONITOR_FAN_MODE.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_aqi_topic = TOPIC_MONITOR_AQI.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_filter_topic = TOPIC_MONITOR_FILTER.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for purifier-card compatibility."""
        attrs = {
            "speed": self._current_speed,
            "speed_list": ORDERED_NAMED_FAN_SPEEDS,
        }
        if self._pm25 is not None:
            attrs["pm25"] = self._pm25
            attrs["aqi"] = self._pm25  # Alias for purifier-card
        if self._filter_life_remaining is not None:
            attrs["filter_life_remaining"] = self._filter_life_remaining
            attrs["filter_hours_remaining"] = self._filter_life_remaining
        return attrs

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when added to hass."""
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == "on"
            if last_state.attributes.get("percentage") is not None:
                self._attr_percentage = last_state.attributes["percentage"]
            if last_state.attributes.get("preset_mode") is not None:
                self._attr_preset_mode = last_state.attributes["preset_mode"]
            _LOGGER.debug(
                "Restored purifier state: on=%s, percentage=%s, mode=%s",
                self._attr_is_on, self._attr_percentage, self._attr_preset_mode
            )

        @callback
        def power_message_received(msg):
            """Handle power state messages."""
            try:
                payload = json.loads(msg.payload)
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                switch_service = services.get("lcSwitchControl", {})
                events = switch_service.get("events", {})
                state_changed = events.get("stateChanged", {})
                power_state = state_changed.get("power")

                if power_state is not None:
                    self._attr_is_on = power_state.lower() == "on"
                    if self._attr_is_on:
                        # Set percentage based on current speed when turning on
                        if self._attr_percentage == 0:
                            self._attr_percentage = ordered_list_item_to_percentage(
                                ORDERED_NAMED_FAN_SPEEDS, self._current_speed
                            )
                    else:
                        # Xiaomi-Miot pattern: 0% when off
                        self._attr_percentage = 0
                    self.async_write_ha_state()
                    _LOGGER.debug("Purifier power state: %s, percentage: %s", self._attr_is_on, self._attr_percentage)

            except (json.JSONDecodeError, KeyError) as err:
                _LOGGER.error("Error processing power state: %s", err)

        @callback
        def speed_message_received(msg):
            """Handle fan speed messages."""
            try:
                payload = json.loads(msg.payload)
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                speed_service = services.get("fanSpeedControl", {})
                events = speed_service.get("events", {})
                state_changed = events.get("stateChanged", {})
                speed = state_changed.get("speed")

                if speed is not None:
                    self._current_speed = speed
                    # Only update percentage if on (Xiaomi-Miot pattern)
                    if self._attr_is_on:
                        self._attr_percentage = ordered_list_item_to_percentage(
                            ORDERED_NAMED_FAN_SPEEDS, speed
                        )
                        self.async_write_ha_state()
                    _LOGGER.debug("Purifier speed: %s (is_on=%s)", speed, self._attr_is_on)

            except (json.JSONDecodeError, KeyError) as err:
                _LOGGER.error("Error processing speed: %s", err)

        @callback
        def mode_message_received(msg):
            """Handle fan mode messages."""
            try:
                payload = json.loads(msg.payload)
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                mode_service = services.get("fanControlMode", {})
                events = mode_service.get("events", {})
                state_changed = events.get("stateChanged", {})
                mode = state_changed.get("state")

                if mode is not None:
                    if mode == PURIFIER_MODE_AUTO:
                        self._attr_preset_mode = PRESET_MODE_AUTO
                    else:
                        self._attr_preset_mode = PRESET_MODE_MANUAL
                    self.async_write_ha_state()
                    _LOGGER.debug("Purifier mode: %s", mode)

            except (json.JSONDecodeError, KeyError) as err:
                _LOGGER.error("Error processing mode: %s", err)

        @callback
        def aqi_message_received(msg):
            """Handle AQI/PM2.5 messages."""
            try:
                payload = json.loads(msg.payload)
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                aqi_service = services.get("aqiStatus", {})
                events = aqi_service.get("events", {})
                state_changed = events.get("stateChanged", {})
                pm25 = state_changed.get("PM25")

                if pm25 is not None:
                    self._pm25 = int(pm25)
                    self.async_write_ha_state()
                    _LOGGER.debug("PM2.5: %s", self._pm25)

            except (json.JSONDecodeError, KeyError, ValueError) as err:
                _LOGGER.error("Error processing AQI: %s", err)

        @callback
        def filter_message_received(msg):
            """Handle filter life messages."""
            try:
                payload = json.loads(msg.payload)
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                filter_service = services.get("filterReset", {})
                events = filter_service.get("events", {})
                state_changed = events.get("stateChanged", {})
                time_remaining = state_changed.get("timeRemaining")

                if time_remaining is not None:
                    # Value is already in hours
                    self._filter_life_remaining = int(time_remaining)
                    self.async_write_ha_state()
                    _LOGGER.debug("Filter life: %s hours", self._filter_life_remaining)

            except (json.JSONDecodeError, KeyError, ValueError) as err:
                _LOGGER.error("Error processing filter: %s", err)

        # Subscribe to monitor topics
        await mqtt.async_subscribe(self.hass, self._monitor_switch_topic, power_message_received, 1)
        await mqtt.async_subscribe(self.hass, self._monitor_speed_topic, speed_message_received, 1)
        await mqtt.async_subscribe(self.hass, self._monitor_mode_topic, mode_message_received, 1)
        await mqtt.async_subscribe(self.hass, self._monitor_aqi_topic, aqi_message_received, 1)
        await mqtt.async_subscribe(self.hass, self._monitor_filter_topic, filter_message_received, 1)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the purifier with optional speed/mode."""
        # Turn on if not already on
        if not self._attr_is_on:
            await self._publish_power_command("on")
            # Optimistic update
            self._attr_is_on = True
            if self._attr_percentage == 0:
                self._attr_percentage = ordered_list_item_to_percentage(
                    ORDERED_NAMED_FAN_SPEEDS, self._current_speed
                )

        # Set speed if provided (like Xiaomi-Miot pattern)
        if percentage is not None and percentage > 0:
            speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
            await self._publish_speed_command(speed)
            # Optimistic update
            self._attr_percentage = percentage
            self._current_speed = speed

        # Set mode if provided
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the purifier."""
        await self._publish_power_command("off")
        # Optimistic update (Xiaomi-Miot pattern: 0% when off)
        self._attr_is_on = False
        self._attr_percentage = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # Turn on first if not on (Xiaomi-Miot pattern)
        if not self._attr_is_on:
            await self._publish_power_command("on")
            self._attr_is_on = True

        # Convert percentage to speed level and publish
        speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        await self._publish_speed_command(speed)

        # Optimistic update
        self._attr_percentage = percentage
        self._current_speed = speed
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if preset_mode == PRESET_MODE_AUTO:
            await self._publish_mode_command(PURIFIER_MODE_AUTO)
        else:
            await self._publish_mode_command(PURIFIER_MODE_MANUAL)
        # Optimistic update
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def _publish_power_command(self, power_state: str) -> None:
        """Publish MQTT command to control power."""
        payload = json.dumps(
            {
                "command": {
                    "devices": {
                        "deviceUUID": self._device_uuid,
                        "entityUUID": self._entity_uuid,
                        "services": {
                            "lcSwitchControl": {
                                "attributes": {"power": power_state},
                                "instanceId": 0,
                            }
                        },
                    }
                }
            }
        )
        await mqtt.async_publish(self.hass, self._control_switch_topic, payload, qos=1)
        _LOGGER.debug("Published power command: %s", power_state)

    async def _publish_speed_command(self, speed: str) -> None:
        """Publish MQTT command to set fan speed."""
        payload = json.dumps(
            {
                "command": {
                    "devices": {
                        "deviceUUID": self._device_uuid,
                        "entityUUID": self._entity_uuid,
                        "services": {
                            "fanSpeedControl": {
                                "attributes": {"speed": speed},
                                "instanceId": 0,
                            }
                        },
                    }
                }
            }
        )
        await mqtt.async_publish(self.hass, self._control_speed_topic, payload, qos=1)
        _LOGGER.debug("Published speed command: %s", speed)

    async def _publish_mode_command(self, mode: str) -> None:
        """Publish MQTT command to set fan mode."""
        payload = json.dumps(
            {
                "command": {
                    "devices": {
                        "deviceUUID": self._device_uuid,
                        "entityUUID": self._entity_uuid,
                        "services": {
                            "fanControlMode": {
                                "attributes": {"state": mode},
                                "instanceId": 0,
                            }
                        },
                    }
                }
            }
        )
        await mqtt.async_publish(self.hass, self._control_mode_topic, payload, qos=1)
        _LOGGER.debug("Published mode command: %s", mode)
