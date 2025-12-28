"""Switch platform for QUBO Local Control integration."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_UNIT_UUID,
    DEVICE_TYPE_AIR_PURIFIER,
    DOMAIN,
    ENTITY_SWITCH,
    TOPIC_CONTROL_SWITCH,
    TOPIC_MONITOR_SWITCH,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up QUBO switch from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device_info = data["device_info"]
    config = data["config"]

    # Only add switch entity for smart plugs (not air purifiers)
    if config.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_AIR_PURIFIER:
        return

    async_add_entities([QuboSwitch(hass, config_entry, device_info, config)])


class QuboSwitch(SwitchEntity):
    """Representation of a QUBO Smart Plug switch."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_info,
        config: dict[str, Any],
    ) -> None:
        """Initialize the QUBO switch."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_device_info = device_info
        self._config = config

        self._device_uuid = config[CONF_DEVICE_UUID]
        self._entity_uuid = config[CONF_ENTITY_UUID]
        self._unit_uuid = config[CONF_UNIT_UUID]

        self._attr_unique_id = f"{self._device_uuid}_{ENTITY_SWITCH}"
        self._attr_is_on = False

        # MQTT topics
        self._control_topic = TOPIC_CONTROL_SWITCH.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )
        self._monitor_topic = TOPIC_MONITOR_SWITCH.format(
            unit_uuid=self._unit_uuid, device_uuid=self._device_uuid
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT topics when added to hass."""

        @callback
        def message_received(msg):
            """Handle new MQTT messages."""
            try:
                payload = json.loads(msg.payload)
                _LOGGER.debug("Received switch state: %s", payload)

                # Extract power state from the response
                devices = payload.get("devices", {})
                services = devices.get("services", {})
                switch_service = services.get("lcSwitchControl", {})
                events = switch_service.get("events", {})
                state_changed = events.get("stateChanged", {})
                power_state = state_changed.get("power")

                if power_state is not None:
                    self._attr_is_on = power_state.lower() == "on"
                    self.async_write_ha_state()
                    _LOGGER.debug("Switch state updated to: %s", self._attr_is_on)

            except (json.JSONDecodeError, KeyError) as err:
                _LOGGER.error("Error processing switch state: %s", err)

        # Subscribe to monitor topic
        await mqtt.async_subscribe(self.hass, self._monitor_topic, message_received, 1)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._publish_command("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._publish_command("off")

    async def _publish_command(self, power_state: str) -> None:
        """Publish MQTT command to control the switch."""
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

        await mqtt.async_publish(self.hass, self._control_topic, payload, qos=1)
        _LOGGER.debug("Published switch command: %s to %s", power_state, self._control_topic)
