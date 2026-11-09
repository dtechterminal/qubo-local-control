"""Constants for the QUBO Local Control integration."""
from datetime import timedelta

DOMAIN = "qubo_local"
MANUFACTURER = "QUBO"
MODEL_SMART_PLUG = "Smart Plug"
MODEL_AIR_PURIFIER = "Air Purifier"

# Config entry keys
CONF_DEVICE_UUID = "device_uuid"
CONF_ENTITY_UUID = "entity_uuid"
CONF_UNIT_UUID = "unit_uuid"
CONF_HANDLE_NAME = "handle_name"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_MAC = "device_mac"
CONF_DEVICE_TYPE = "device_type"

DEVICE_TYPE_SMART_PLUG = "smart_plug"
DEVICE_TYPE_AIR_PURIFIER = "air_purifier"

DEFAULT_NAME = "QUBO Smart Plug"
DEFAULT_NAME_PURIFIER = "QUBO Air Purifier"

METERING_REFRESH_INTERVAL = timedelta(seconds=60)
AQI_REFRESH_INTERVAL = timedelta(seconds=30)
FILTER_REFRESH_INTERVAL = timedelta(hours=1)
DISCOVERY_TIMEOUT = 30  # seconds
