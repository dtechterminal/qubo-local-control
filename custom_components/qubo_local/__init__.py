"""The QUBO Local Control integration."""
import asyncio
import json
import logging
from datetime import timedelta

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_DEVICE_MAC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_HANDLE_NAME,
    CONF_UNIT_UUID,
    DEFAULT_REFRESH_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    TOPIC_CONTROL_METERING_REFRESH,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up QUBO Local Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_DEVICE_UUID])},
        name=entry.data[CONF_DEVICE_NAME],
        manufacturer=MANUFACTURER,
        model=MODEL,
        sw_version="1.0.0",
        connections={("mac", entry.data[CONF_DEVICE_MAC])} if CONF_DEVICE_MAC in entry.data else None,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "device_info": device_info,
        "config": entry.data,
    }

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up energy monitoring refresh
    async def async_refresh_energy_monitoring(now=None):
        """Send meteringRefresh command to keep energy data flowing."""
        device_uuid = entry.data[CONF_DEVICE_UUID]
        unit_uuid = entry.data[CONF_UNIT_UUID]
        handle_name = entry.data[CONF_HANDLE_NAME]

        topic = TOPIC_CONTROL_METERING_REFRESH.format(
            unit_uuid=unit_uuid,
            device_uuid=device_uuid
        )

        payload = json.dumps({
            "command": {
                "devices": {
                    "deviceUUID": device_uuid,
                    "handleName": handle_name,
                    "services": {
                        "meteringRefresh": {
                            "attributes": {
                                "duration": str(DEFAULT_REFRESH_INTERVAL)
                            },
                            "instanceId": 0
                        }
                    }
                }
            }
        })

        await mqtt.async_publish(hass, topic, payload, qos=1)
        _LOGGER.debug("Sent meteringRefresh command to %s", device_uuid)

    # Trigger initial refresh after 5 seconds
    async def async_initial_refresh(_):
        await async_refresh_energy_monitoring()

    hass.loop.call_later(5, lambda: asyncio.create_task(async_initial_refresh(None)))

    # Set up periodic refresh
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            async_refresh_energy_monitoring,
            timedelta(seconds=DEFAULT_REFRESH_INTERVAL)
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
