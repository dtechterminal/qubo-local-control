"""Switch platform for QUBO smart plugs."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import protocol
from .device import QuboConfigEntry
from .entity import QuboEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the plug's switch."""
    async_add_entities([QuboSwitch(entry.runtime_data, "switch")])


class QuboSwitch(QuboEntity, SwitchEntity):
    """The plug's power relay."""

    _attr_name = None  # Use the device name
    _attr_is_on = False
    services = (protocol.SERVICE_SWITCH,)

    def _handle_values(self, service: str, values: dict[str, Any]) -> None:
        if isinstance(power := values.get("power"), str):
            self._attr_is_on = power.lower() == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.device.async_set(protocol.SERVICE_SWITCH, power="on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.device.async_set(protocol.SERVICE_SWITCH, power="off")
