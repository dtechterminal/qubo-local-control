"""Config flow for QUBO Local Control."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import protocol
from .const import (
    CONF_DEVICE_MAC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_HANDLE_NAME,
    CONF_UNIT_UUID,
    DEFAULT_NAME,
    DEFAULT_NAME_PURIFIER,
    DEVICE_TYPE_AIR_PURIFIER,
    DEVICE_TYPE_SMART_PLUG,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _entry_data(beat: protocol.Heartbeat) -> dict[str, str]:
    """Return config entry data for a discovered device."""
    purifier = beat.prefix == protocol.PREFIX_PURIFIER
    name = DEFAULT_NAME_PURIFIER if purifier else DEFAULT_NAME
    return {
        CONF_DEVICE_UUID: beat.device_uuid,
        CONF_ENTITY_UUID: beat.entity_uuid,
        CONF_UNIT_UUID: beat.unit_uuid,
        CONF_HANDLE_NAME: beat.user_uuid,
        CONF_DEVICE_NAME: f"{name} {beat.mac.replace(':', '')[-6:]}",
        CONF_DEVICE_MAC: beat.mac,
        CONF_DEVICE_TYPE: DEVICE_TYPE_AIR_PURIFIER if purifier else DEVICE_TYPE_SMART_PLUG,
    }


class QuboLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a QUBO device."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, dict[str, str]] = {}
        self._discovery_task: asyncio.Task[None] | None = None
        self._manual_errors: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose discovery or manual setup."""
        return self.async_show_menu(step_id="user", menu_options=["mqtt_discovery", "manual"])

    async def async_step_mqtt_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Listen for device heartbeats."""
        if self._discovery_task is None:
            self._discovery_task = self.hass.async_create_task(self._async_discover())
        if not self._discovery_task.done():
            return self.async_show_progress(
                step_id="mqtt_discovery",
                progress_action="discovering",
                progress_task=self._discovery_task,
            )
        self._discovery_task = None
        if not self._discovered:
            self._manual_errors = {"base": "no_devices_found"}
            return self.async_show_progress_done(next_step_id="manual")
        return self.async_show_progress_done(next_step_id="pick_device")

    async def _async_discover(self) -> None:
        configured = self._async_current_ids(include_ignore=False)
        self._discovered = {}

        @callback
        def heartbeat(msg: mqtt.ReceiveMessage) -> None:
            beat = protocol.parse_heartbeat(msg.payload)
            if beat is not None and beat.device_uuid not in configured:
                self._discovered[beat.device_uuid] = _entry_data(beat)

        unsubscribe = await mqtt.async_subscribe(
            self.hass, protocol.monitor_topic("+", "+", protocol.SERVICE_HEARTBEAT), heartbeat)
        try:
            await asyncio.sleep(DISCOVERY_TIMEOUT)
        finally:
            unsubscribe()
        _LOGGER.debug("Discovery found %d new device(s)", len(self._discovered))

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one of the discovered devices."""
        # Reached from the progress step, HA passes on that step's input ({})
        if user_input:
            data = self._discovered[user_input["device"]]
            await self.async_set_unique_id(data[CONF_DEVICE_UUID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=data[CONF_DEVICE_NAME], data=data)

        options = {
            uuid: f"{data[CONF_DEVICE_NAME]} ({data[CONF_DEVICE_MAC]})"
            for uuid, data in self._discovered.items()
        }
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required("device"): vol.In(options)}),
            description_placeholders={"device_count": str(len(options))},
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Enter a device's identifiers by hand."""
        # Reached from the progress step, HA passes on that step's input ({})
        if user_input:
            await self.async_set_unique_id(user_input[CONF_DEVICE_UUID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_DEVICE_NAME], data=user_input)

        errors, self._manual_errors = self._manual_errors, {}
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_UUID): cv.string,
                vol.Required(CONF_ENTITY_UUID): cv.string,
                vol.Required(CONF_UNIT_UUID): cv.string,
                vol.Required(CONF_HANDLE_NAME): cv.string,
                vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DEVICE_MAC): cv.string,
                vol.Optional(CONF_DEVICE_TYPE, default=DEVICE_TYPE_SMART_PLUG): vol.In({
                    DEVICE_TYPE_SMART_PLUG: "Smart Plug",
                    DEVICE_TYPE_AIR_PURIFIER: "Air Purifier",
                }),
            }),
            errors=errors,
        )
