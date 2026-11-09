"""The QUBO Local Control integration."""
from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .device import QuboConfigEntry, QuboDevice

PLATFORMS_SMART_PLUG = [Platform.SWITCH, Platform.SENSOR]
PLATFORMS_AIR_PURIFIER = [Platform.FAN, Platform.SENSOR]


def _platforms(device: QuboDevice) -> list[Platform]:
    return PLATFORMS_AIR_PURIFIER if device.is_purifier else PLATFORMS_SMART_PLUG


async def async_setup_entry(hass: HomeAssistant, entry: QuboConfigEntry) -> bool:
    """Set up a QUBO device from a config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT is not available")
    device = QuboDevice(hass, entry)
    entry.runtime_data = device
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(device))
    await device.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: QuboConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry.runtime_data))
