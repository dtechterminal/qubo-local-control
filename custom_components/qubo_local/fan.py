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
    TOPIC_MONITOR_FAN_MODE,
    TOPIC_MONITOR_FAN_SPEED,
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

        # MQTT topics
        self._control_switch_topic = TOPIC_CONTROL_SWITCH.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._control_speed_topic = TOPIC_CONTROL_FAN_SPEED.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._control_mode_topic = TOPIC_CONTROL_FAN_MODE.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_switch_topic = TOPIC_MONITOR_SWITCH.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_speed_topic = TOPIC_MONITOR_FAN_SPEED.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_mode_topic = TOPIC_MONITOR_FAN_MODE.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )

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
                    if self._attr_is_on and self._attr_percentage == 0:
                        # Default to current speed or low when turning on
                        self._attr_percentage = ordered_list_item_to_percentage(
                            ORDERED_NAMED_FAN_SPEEDS, self._current_speed
                        )
                    self.async_write_ha_state()
                    _LOGGER.debug("Purifier power state: %s", self._attr_is_on)

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
                    # Always update percentage - will show when turned on
                    self._attr_percentage = ordered_list_item_to_percentage(
                        ORDERED_NAMED_FAN_SPEEDS, speed
                    )
                    self.async_write_ha_state()
                    _LOGGER.debug("Purifier speed: %s, percentage: %s", speed, self._attr_percentage)

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

        # Subscribe to monitor topics
        await mqtt.async_subscribe(self.hass, self._monitor_switch_topic, power_message_received, 1)
        await mqtt.async_subscribe(self.hass, self._monitor_speed_topic, speed_message_received, 1)
        await mqtt.async_subscribe(self.hass, self._monitor_mode_topic, mode_message_received, 1)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the purifier."""
        await self._publish_power_command("on")

        if percentage is not None:
            await self.async_set_percentage(percentage)
        elif preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the purifier."""
        await self._publish_power_command("off")

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        # Convert percentage to speed level
        speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        await self._publish_speed_command(speed)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if preset_mode == PRESET_MODE_AUTO:
            await self._publish_mode_command(PURIFIER_MODE_AUTO)
        else:
            await self._publish_mode_command(PURIFIER_MODE_MANUAL)

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
