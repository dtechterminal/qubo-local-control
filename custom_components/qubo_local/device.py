"""One QUBO device: its MQTT subscription, latest reported values and commands."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from . import protocol
from .const import (
    AQI_REFRESH_INTERVAL,
    CONF_DEVICE_MAC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_DEVICE_UUID,
    CONF_ENTITY_UUID,
    CONF_HANDLE_NAME,
    CONF_UNIT_UUID,
    DEVICE_TYPE_AIR_PURIFIER,
    DEVICE_TYPE_SMART_PLUG,
    DOMAIN,
    FILTER_REFRESH_INTERVAL,
    MANUFACTURER,
    METERING_REFRESH_INTERVAL,
    MODEL_AIR_PURIFIER,
    MODEL_SMART_PLUG,
)

_LOGGER = logging.getLogger(__name__)

type QuboConfigEntry = ConfigEntry[QuboDevice]
# Called with the service that changed, or None when availability changed
type Listener = Callable[[str | None], None]


class QuboDevice:
    """Track one device over a single MQTT subscription."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        data = entry.data
        self.device_uuid: str = data[CONF_DEVICE_UUID]
        self.entity_uuid: str = data[CONF_ENTITY_UUID]
        self.unit_uuid: str = data[CONF_UNIT_UUID]
        self.handle_name: str = data[CONF_HANDLE_NAME]
        # Entries created before air purifier support have no device type
        self.device_type: str = data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_SMART_PLUG)
        self.available = True
        self.values: dict[str, dict[str, Any]] = {}
        self._listeners: list[Listener] = []

        mac = data.get(CONF_DEVICE_MAC)
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_uuid)},
            name=data[CONF_DEVICE_NAME],
            manufacturer=MANUFACTURER,
            model=MODEL_AIR_PURIFIER if self.is_purifier else MODEL_SMART_PLUG,
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else None,
        )

    @property
    def is_purifier(self) -> bool:
        return self.device_type == DEVICE_TYPE_AIR_PURIFIER

    async def async_start(self) -> None:
        """Subscribe to the device and keep its readings flowing."""
        self.entry.async_on_unload(await mqtt.async_subscribe(
            self.hass,
            protocol.monitor_topic(self.unit_uuid, self.device_uuid),
            self._async_message_received,
            qos=1,
        ))
        if self.is_purifier:
            self._every(AQI_REFRESH_INTERVAL, self.async_refresh_aqi)
            self._every(FILTER_REFRESH_INTERVAL, self.async_refresh_filter)
            await self.async_refresh_aqi()
            await self.async_refresh_filter()
        else:
            self._every(METERING_REFRESH_INTERVAL, self.async_refresh_metering)
            await self.async_refresh_metering()

    def _every(self, interval: timedelta, action: Callable[[], Any]) -> None:
        async def _run(_now: Any) -> None:
            await action()

        self.entry.async_on_unload(async_track_time_interval(self.hass, _run, interval))

    @callback
    def async_add_listener(self, listener: Listener) -> CALLBACK_TYPE:
        """Call `listener` when a service reports values or availability changes."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _async_message_received(self, msg: mqtt.ReceiveMessage) -> None:
        service = protocol.service_from_topic(msg.topic)
        if service == protocol.SERVICE_HEARTBEAT:
            if (beat := protocol.parse_heartbeat(msg.payload)) is not None:
                self._set_available(beat.online)
            return
        if not (values := protocol.service_values(msg.payload, service)):
            return
        _LOGGER.debug("%s %s: %s", self.device_uuid, service, values)
        self.values.setdefault(service, {}).update(values)
        self._set_available(True)
        for listener in list(self._listeners):
            listener(service)

    @callback
    def _set_available(self, available: bool) -> None:
        if available == self.available:
            return
        self.available = available
        _LOGGER.debug("%s is %s", self.device_uuid, "online" if available else "offline")
        for listener in list(self._listeners):
            listener(None)

    async def _async_publish(self, service: str, payload: str) -> None:
        await mqtt.async_publish(
            self.hass, protocol.control_topic(self.unit_uuid, self.device_uuid, service),
            payload, qos=1,
        )

    async def async_set(self, service: str, **attributes: Any) -> None:
        """Set attributes of a device service."""
        await self._async_publish(service, protocol.set_command(
            self.device_uuid, self.entity_uuid, service, attributes))

    async def async_refresh_metering(self) -> None:
        """Keep a plug reporting power, voltage, current and energy."""
        await self._async_publish(protocol.SERVICE_METERING_REFRESH,
                                  protocol.metering_refresh_command(
                                      self.device_uuid, self.handle_name,
                                      int(METERING_REFRESH_INTERVAL.total_seconds())))

    async def async_refresh_aqi(self) -> None:
        """Keep a purifier reporting PM2.5."""
        await self._async_publish(protocol.SERVICE_AQI_REFRESH, protocol.request_command(
            self.device_uuid, self.handle_name, protocol.SERVICE_AQI_REFRESH, "refresh"))

    async def async_refresh_filter(self) -> None:
        """Ask a purifier for its remaining filter life."""
        await self._async_publish(protocol.SERVICE_FILTER, protocol.request_command(
            self.device_uuid, self.handle_name, protocol.SERVICE_FILTER, "getCurrentStatus"))
