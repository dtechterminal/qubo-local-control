"""Base entity for QUBO devices."""
from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .device import QuboDevice


class QuboEntity(Entity):
    """An entity that follows the values its device reports."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Device services this entity reads
    services: tuple[str, ...] = ()

    def __init__(self, device: QuboDevice, key: str) -> None:
        self.device = device
        self._attr_unique_id = f"{device.device_uuid}_{key}"
        self._attr_device_info = device.device_info

    @property
    def available(self) -> bool:
        return self.device.available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for service in self.services:
            if values := self.device.values.get(service):
                self._handle_values(service, values)
        self.async_on_remove(self.device.async_add_listener(self._async_device_updated))

    @callback
    def _async_device_updated(self, service: str | None) -> None:
        if service is None:
            self.async_write_ha_state()
        elif service in self.services:
            self._handle_values(service, self.device.values[service])
            self.async_write_ha_state()

    def _handle_values(self, service: str, values: dict[str, Any]) -> None:
        """Apply values a device service reported."""
        raise NotImplementedError
