"""Config flow for QUBO Local Control integration."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE_MAC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_HANDLE_NAME,
    CONF_UNIT_UUID,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DISCOVERY_TIMEOUT = 30  # seconds


class QuboLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for QUBO Local Control."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_devices = {}
        self._discovery_task = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step - choose discovery or manual."""
        if user_input is not None:
            if user_input.get("discovery_mode") == "auto":
                return await self.async_step_mqtt_discovery()
            return await self.async_step_manual()

        return self.async_show_menu(
            step_id="user",
            menu_options=["mqtt_discovery", "manual"],
        )

    async def async_step_mqtt_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Discover QUBO devices via MQTT."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User selected a discovered device
            device_id = user_input["device"]
            device_data = self._discovered_devices[device_id]

            # Set unique ID and check if already configured
            await self.async_set_unique_id(device_data[CONF_DEVICE_UUID])
            self._abort_if_unique_id_configured()

            # Create the config entry
            return self.async_create_entry(
                title=device_data[CONF_DEVICE_NAME],
                data=device_data,
            )

        # Start device discovery
        self._discovered_devices = {}

        try:
            await self._discover_devices()
        except Exception as err:
            _LOGGER.error("Error during MQTT discovery: %s", err)
            errors["base"] = "discovery_failed"

        if not self._discovered_devices:
            errors["base"] = "no_devices_found"
            # Offer manual configuration instead
            return await self.async_step_manual()

        # Show discovered devices
        device_options = {
            device_id: f"{data[CONF_DEVICE_NAME]} ({data.get(CONF_DEVICE_MAC, 'No MAC')})"
            for device_id, data in self._discovered_devices.items()
        }

        data_schema = vol.Schema(
            {
                vol.Required("device"): vol.In(device_options),
            }
        )

        return self.async_show_form(
            step_id="mqtt_discovery",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._discovered_devices))
            },
        )

    async def _discover_devices(self):
        """Listen for QUBO device heartbeats on MQTT."""
        discovery_complete = asyncio.Event()

        @callback
        def message_received(msg):
            """Handle received MQTT message."""
            try:
                payload = json.loads(msg.payload)
                devices_data = payload.get("devices", {})

                device_uuid = devices_data.get("deviceUUID")
                if not device_uuid:
                    return

                # Extract device information from heartbeat
                entity_uuid = devices_data.get("entityUUID")
                unit_uuid = devices_data.get("unitUUID")
                user_uuid = devices_data.get("userUUID")
                src_device_id = devices_data.get("srcDeviceId", "")

                # Parse MAC address from srcDeviceId (format: HSP_CC:8D:A2:DC:F3:BC)
                mac_address = src_device_id.split("_", 1)[1] if "_" in src_device_id else ""

                # Generate a friendly device name
                mac_short = mac_address.replace(":", "")[-6:] if mac_address else device_uuid[:8]
                device_name = f"QUBO Smart Plug {mac_short}"

                # Store discovered device
                self._discovered_devices[device_uuid] = {
                    CONF_DEVICE_UUID: device_uuid,
                    CONF_ENTITY_UUID: entity_uuid,
                    CONF_UNIT_UUID: unit_uuid,
                    CONF_HANDLE_NAME: user_uuid,
                    CONF_DEVICE_NAME: device_name,
                    CONF_DEVICE_MAC: mac_address,
                }

                _LOGGER.info("Discovered QUBO device: %s (%s)", device_name, mac_address)

            except (json.JSONDecodeError, KeyError) as err:
                _LOGGER.debug("Error parsing MQTT message: %s", err)

        # Subscribe to heartbeat topic
        await mqtt.async_subscribe(
            self.hass, "/monitor/+/+/heartbeat", message_received, qos=0
        )

        # Wait for discovery timeout
        try:
            await asyncio.wait_for(discovery_complete.wait(), timeout=DISCOVERY_TIMEOUT)
        except asyncio.TimeoutError:
            pass  # Timeout is expected

        _LOGGER.info("MQTT discovery completed. Found %d devices", len(self._discovered_devices))

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate unique device UUID
            await self.async_set_unique_id(user_input[CONF_DEVICE_UUID])
            self._abort_if_unique_id_configured()

            # Create the config entry
            return self.async_create_entry(
                title=user_input.get(CONF_DEVICE_NAME, DEFAULT_NAME),
                data=user_input,
            )

        # Show the form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_UUID): cv.string,
                vol.Required(CONF_ENTITY_UUID): cv.string,
                vol.Required(CONF_UNIT_UUID): cv.string,
                vol.Required(CONF_HANDLE_NAME): cv.string,
                vol.Optional(CONF_DEVICE_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_DEVICE_MAC): cv.string,
            }
        )

        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
            errors=errors,
        )
