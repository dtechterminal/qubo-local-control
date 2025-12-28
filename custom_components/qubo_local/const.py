"""Constants for the QUBO Local Control integration."""

DOMAIN = "qubo_local"
MANUFACTURER = "QUBO"
MODEL = "Smart Plug"
MODEL_AIR_PURIFIER = "Air Purifier"

# Configuration keys
CONF_DEVICE_UUID = "device_uuid"
CONF_ENTITY_UUID = "entity_uuid"
CONF_UNIT_UUID = "unit_uuid"
CONF_HANDLE_NAME = "handle_name"
CONF_DEVICE_NAME = "device_name"
CONF_DEVICE_MAC = "device_mac"
CONF_DEVICE_TYPE = "device_type"

# Device types
DEVICE_TYPE_SMART_PLUG = "smart_plug"
DEVICE_TYPE_AIR_PURIFIER = "air_purifier"

# Device type prefixes (from srcDeviceId)
DEVICE_PREFIX_PLUG = "HSP"  # Hero Smart Plug
DEVICE_PREFIX_PURIFIER = "HPH"  # Hero Purifier Hub

# Default values
DEFAULT_NAME = "QUBO Smart Plug"
DEFAULT_NAME_PURIFIER = "QUBO Air Purifier"
DEFAULT_REFRESH_INTERVAL = 60  # seconds
DEFAULT_AQI_REFRESH_INTERVAL = 30  # seconds

# MQTT topics patterns - Smart Plug
TOPIC_CONTROL_SWITCH = "/control/{unit_uuid}/{device_uuid}/lcSwitchControl"
TOPIC_CONTROL_METERING_REFRESH = "/control/{unit_uuid}/{device_uuid}/meteringRefresh"
TOPIC_MONITOR_SWITCH = "/monitor/{unit_uuid}/{device_uuid}/lcSwitchControl"
TOPIC_MONITOR_ENERGY = "/monitor/{unit_uuid}/{device_uuid}/plugMetering"
TOPIC_MONITOR_HEARTBEAT = "/monitor/{unit_uuid}/{device_uuid}/heartbeat"

# MQTT topics patterns - Air Purifier
TOPIC_CONTROL_FAN_SPEED = "/control/{unit_uuid}/{device_uuid}/fanSpeedControl"
TOPIC_CONTROL_FAN_MODE = "/control/{unit_uuid}/{device_uuid}/fanControlMode"
TOPIC_CONTROL_AQI_REFRESH = "/control/{unit_uuid}/{device_uuid}/aqiRefresh"
TOPIC_CONTROL_FILTER_STATUS = "/control/{unit_uuid}/{device_uuid}/filterReset"
TOPIC_MONITOR_FAN_SPEED = "/monitor/{unit_uuid}/{device_uuid}/fanSpeedControl"
TOPIC_MONITOR_FAN_MODE = "/monitor/{unit_uuid}/{device_uuid}/fanControlMode"
TOPIC_MONITOR_AQI = "/monitor/{unit_uuid}/{device_uuid}/aqiStatus"
TOPIC_MONITOR_FILTER = "/monitor/{unit_uuid}/{device_uuid}/filterReset"

# Air Purifier modes
PURIFIER_MODE_AUTO = "auto"
PURIFIER_MODE_MANUAL = "manual"

# Air Purifier speed levels
PURIFIER_SPEED_LOW = "1"
PURIFIER_SPEED_MEDIUM = "2"
PURIFIER_SPEED_HIGH = "3"

# Entity IDs - Smart Plug
ENTITY_SWITCH = "switch"
ENTITY_POWER = "power"
ENTITY_VOLTAGE = "voltage"
ENTITY_CURRENT = "current"
ENTITY_ENERGY = "energy"

# Entity IDs - Air Purifier
ENTITY_FAN = "fan"
ENTITY_PM25 = "pm25"
ENTITY_FILTER_LIFE = "filter_life"
