"""Config flow for QUBO Local Control integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
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


class QuboLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for QUBO Local Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
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
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
