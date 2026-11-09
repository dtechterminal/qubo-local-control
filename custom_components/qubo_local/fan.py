"""Fan platform for QUBO air purifiers."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import protocol
from .device import QuboConfigEntry
from .entity import QuboEntity

SPEEDS = ["1", "2", "3"]  # Low, medium, high
MODE_AUTO = "auto"
MODE_MANUAL = "manual"
PRESET_AUTO = "Auto"
PRESET_MANUAL = "Manual"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QuboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the purifier's fan."""
    async_add_entities([QuboAirPurifier(entry.runtime_data, "fan")])


class QuboAirPurifier(QuboEntity, FanEntity, RestoreEntity):
    """A QUBO air purifier."""

    _attr_name = None  # Use the device name
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(SPEEDS)
    _attr_preset_modes = [PRESET_AUTO, PRESET_MANUAL]
    _attr_is_on = False
    _attr_percentage = 0
    _attr_preset_mode = PRESET_AUTO
    services = (
        protocol.SERVICE_SWITCH,
        protocol.SERVICE_FAN_SPEED,
        protocol.SERVICE_FAN_MODE,
        protocol.SERVICE_AQI,
        protocol.SERVICE_FILTER,
    )

    _speed = SPEEDS[0]
    _pm25: int | None = None
    _filter_hours: int | None = None

    # FanEntity derives these from cached properties; read the live values
    @property
    def is_on(self) -> bool | None:
        return self._attr_is_on

    @property
    def percentage(self) -> int | None:
        return self._attr_percentage

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes used by the purifier-card."""
        attrs: dict[str, Any] = {"speed": self._speed, "speed_list": SPEEDS}
        if self._pm25 is not None:
            attrs["pm25"] = attrs["aqi"] = self._pm25
        if self._filter_hours is not None:
            attrs["filter_life_remaining"] = attrs["filter_hours_remaining"] = self._filter_hours
        return attrs

    async def async_added_to_hass(self) -> None:
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == "on"
            if (percentage := last.attributes.get("percentage")) is not None:
                self._attr_percentage = percentage
            if (preset := last.attributes.get("preset_mode")) in self._attr_preset_modes:
                self._attr_preset_mode = preset
            if (speed := last.attributes.get("speed")) in SPEEDS:
                self._speed = speed
        await super().async_added_to_hass()

    def _speed_percentage(self) -> int:
        return ordered_list_item_to_percentage(SPEEDS, self._speed)

    def _handle_values(self, service: str, values: dict[str, Any]) -> None:
        if service == protocol.SERVICE_SWITCH:
            if isinstance(power := values.get("power"), str):
                self._attr_is_on = power.lower() == "on"
                self._attr_percentage = self._speed_percentage() if self._attr_is_on else 0
        elif service == protocol.SERVICE_FAN_SPEED:
            if (speed := values.get("speed")) in SPEEDS:
                self._speed = speed
                if self._attr_is_on:
                    self._attr_percentage = self._speed_percentage()
        elif service == protocol.SERVICE_FAN_MODE:
            if (mode := values.get("state")) is not None:
                self._attr_preset_mode = PRESET_AUTO if mode == MODE_AUTO else PRESET_MANUAL
        elif service == protocol.SERVICE_AQI:
            self._pm25 = _int(values.get("PM25"), self._pm25)
        elif service == protocol.SERVICE_FILTER:
            self._filter_hours = _int(values.get("timeRemaining"), self._filter_hours)

    async def _async_power(self, on: bool) -> None:
        await self.device.async_set(protocol.SERVICE_SWITCH, power="on" if on else "off")
        self._attr_is_on = on
        self._attr_percentage = self._speed_percentage() if on else 0

    async def _async_speed(self, percentage: int) -> None:
        speed = percentage_to_ordered_list_item(SPEEDS, percentage)
        await self.device.async_set(protocol.SERVICE_FAN_SPEED, speed=speed)
        self._speed = speed
        self._attr_percentage = percentage

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on, optionally at a speed or preset."""
        if not self._attr_is_on:
            await self._async_power(True)
        if percentage:
            await self._async_speed(percentage)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_power(False)
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        if not self._attr_is_on:
            await self._async_power(True)
        await self._async_speed(percentage)
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.device.async_set(
            protocol.SERVICE_FAN_MODE, state=MODE_AUTO if preset_mode == PRESET_AUTO else MODE_MANUAL)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()


def _int(value: Any, default: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
