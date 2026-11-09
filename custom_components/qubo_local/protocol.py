"""QUBO MQTT topics, command payloads and message parsing.

This module has no Home Assistant imports so it can be tested on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

PREFIX_PLUG = "HSP"  # Hero Smart Plug
PREFIX_PURIFIER = "HPH"  # Hero Purifier Hub

# Services; each is also the last segment of its /control and /monitor topic
SERVICE_SWITCH = "lcSwitchControl"
SERVICE_METERING = "plugMetering"
SERVICE_METERING_REFRESH = "meteringRefresh"
SERVICE_FAN_SPEED = "fanSpeedControl"
SERVICE_FAN_MODE = "fanControlMode"
SERVICE_AQI = "aqiStatus"
SERVICE_AQI_REFRESH = "aqiRefresh"
SERVICE_FILTER = "filterReset"
SERVICE_HEARTBEAT = "heartbeat"

# Device firmware sends numbers with leading zeros (`"msgSequenceId" : 0001`),
# which is not valid JSON. Only strip them right after an object key.
_LEADING_ZEROS = re.compile(r'(?<=")(\s*:\s*)0+(?=\d)')


def control_topic(unit_uuid: str, device_uuid: str, service: str) -> str:
    """Return the topic used to send a command to a device service."""
    return f"/control/{unit_uuid}/{device_uuid}/{service}"


def monitor_topic(unit_uuid: str, device_uuid: str, service: str = "#") -> str:
    """Return the topic a device reports a service on; `#` covers all of them."""
    return f"/monitor/{unit_uuid}/{device_uuid}/{service}"


def service_from_topic(topic: str) -> str:
    """Return the service name, the last segment of a topic."""
    return topic.rsplit("/", 1)[-1]


def loads(payload: str | bytes) -> dict[str, Any] | None:
    """Decode a device message, tolerating leading zeros in numbers."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", "replace")
    try:
        data = json.loads(payload)
    except ValueError:
        try:
            data = json.loads(_LEADING_ZEROS.sub(r"\1", payload))
        except ValueError:
            return None
    return data if isinstance(data, dict) else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def service_values(payload: str | bytes, service: str) -> dict[str, Any]:
    """Return the values a monitor message reports for a service.

    Devices report `services.<service>.events.stateChanged`; some replies carry
    `services.<service>.attributes` instead.
    """
    data = loads(payload)
    if data is None:
        return {}
    entry = _dict(_dict(_dict(data.get("devices")).get("services")).get(service))
    if changed := _dict(_dict(entry.get("events")).get("stateChanged")):
        return changed
    return _dict(entry.get("attributes"))


@dataclass(frozen=True)
class Heartbeat:
    """A device heartbeat."""

    device_uuid: str
    entity_uuid: str
    unit_uuid: str
    user_uuid: str
    prefix: str
    mac: str
    online: bool


def parse_heartbeat(payload: str | bytes) -> Heartbeat | None:
    """Parse a heartbeat; None unless it comes from a QUBO plug or purifier.

    The QUBO app also sends heartbeats, with a bare UUID as `srcDeviceId`.
    """
    data = loads(payload)
    if data is None:
        return None
    devices = _dict(data.get("devices"))
    prefix, _, mac = str(devices.get("srcDeviceId", "")).partition("_")
    if prefix not in (PREFIX_PLUG, PREFIX_PURIFIER) or not mac:
        return None
    ids = [devices.get(key) for key in ("deviceUUID", "entityUUID", "unitUUID", "userUUID")]
    if not all(isinstance(value, str) and value for value in ids):
        return None
    return Heartbeat(*ids, prefix=prefix, mac=mac,
                     online=devices.get("operationState") != "offline")


def set_command(device_uuid: str, entity_uuid: str, service: str,
                attributes: dict[str, Any]) -> str:
    """Return a command that sets attributes of a device service."""
    return json.dumps({"command": {"devices": {
        "deviceUUID": device_uuid,
        "entityUUID": entity_uuid,
        "services": {service: {"attributes": attributes, "instanceId": 0}},
    }}})


def request_command(device_uuid: str, handle_name: str, service: str, command: str) -> str:
    """Return a command that asks a device service to run a parameterless command."""
    return json.dumps({"command": {"devices": {
        "deviceUUID": device_uuid,
        "handleName": handle_name,
        "services": {service: {"commands": {command: {"instanceId": 0, "parameters": {}}}}},
    }}})


def metering_refresh_command(device_uuid: str, handle_name: str, duration: int) -> str:
    """Return a command that keeps a plug reporting energy data for `duration` seconds."""
    return json.dumps({"command": {"devices": {
        "deviceUUID": device_uuid,
        "handleName": handle_name,
        "services": {SERVICE_METERING_REFRESH: {
            "attributes": {"duration": str(duration)}, "instanceId": 0,
        }},
    }}})
