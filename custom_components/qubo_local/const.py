"""Constants for the QUBO Local Control integration."""

DOMAIN = "qubo_local"
MANUFACTURER = "QUBO"
MODEL = "Smart Plug"

# Configuration keys
CONF_DEVICE_UUID = "device_uuid"
CONF_ENTITY_UUID = "entity_uuid"
CONF_UNIT_UUID = "unit_uuid"
CONF_HANDLE_NAME = "handle_name"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_MAC = "device_mac"

# Default values
DEFAULT_NAME = "QUBO Smart Plug"
DEFAULT_REFRESH_INTERVAL = 60  # seconds

# MQTT topics patterns
TOPIC_CONTROL_SWITCH = "/control/{unit_uuid}/{device_uuid}/lcSwitchControl"
TOPIC_CONTROL_METERING_REFRESH = "/control/{unit_uuid}/{device_uuid}/meteringRefresh"
TOPIC_MONITOR_SWITCH = "/monitor/{unit_uuid}/{device_uuid}/lcSwitchControl"
TOPIC_MONITOR_ENERGY = "/monitor/{unit_uuid}/{device_uuid}/plugMetering"
TOPIC_MONITOR_HEARTBEAT = "/monitor/{unit_uuid}/{device_uuid}/heartbeat"

# Entity IDs
ENTITY_SWITCH = "switch"
ENTITY_POWER = "power"
ENTITY_VOLTAGE = "voltage"
ENTITY_CURRENT = "current"
ENTITY_ENERGY = "energy"
