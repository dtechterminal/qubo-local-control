<p align="center">
  <img src="https://d29rw3zaldax51.cloudfront.net/assets/images/footer/black-theam.png" alt="QUBO Logo" width="200">
</p>

# QUBO Local Control - Home Assistant Integration

Home Assistant custom integration for local control of QUBO Smart Plugs and Air Purifiers via MQTT.

## Features

### Smart Plug
- **Automatic Device Discovery** - Automatically detects QUBO devices on your network via MQTT
- **100% Local Control** - No cloud dependency, complete privacy
- **Real-time Switch Control** - Turn devices on/off instantly
- **Energy Monitoring** - Track power consumption, voltage, current, and total energy
- **Automatic Updates** - Energy data refreshed every 60 seconds

### Air Purifier
- **Fan Control** - Turn on/off with speed levels (Low, Medium, High)
- **Preset Modes** - Auto and Manual modes
- **Air Quality Monitoring** - Real-time PM2.5 readings
- **Filter Life Tracking** - Monitor remaining filter life in hours
- **Automatic Updates** - AQI data refreshed every 30 seconds

### General
- **Device Integration** - All entities grouped under a single device in Home Assistant
- **Auto Device Type Detection** - Automatically identifies Smart Plugs (HSP) and Air Purifiers (HPH)

## Requirements

- Home Assistant with MQTT integration configured
- Local MQTT broker (e.g., Mosquitto) with TLS/SSL support
- Router or DNS server with custom DNS entry support
- QUBO Smart Plug and/or Air Purifier

## Setup Local MQTT Redirect

To enable local control, you need to redirect the QUBO device's cloud MQTT connection to your local broker:

### DNS Redirect Method (Recommended)

Configure your router or DNS server to resolve `mqtt.platform.quboworld.com` to your local MQTT broker's IP address.

**Steps:**
1. Access your router's DNS settings (or Pi-hole, AdGuard Home, etc.)
2. Add a custom DNS entry:
   - **Hostname:** `mqtt.platform.quboworld.com`
   - **IP Address:** Your local MQTT broker IP (e.g., `192.168.1.68`)
3. Save the DNS configuration
4. Power cycle your QUBO device:
   - Unplug the device from power
   - Wait 10 seconds
   - Plug it back in
5. The device will now connect to your local broker instead of the cloud

**Verify Connection:**
```bash
# Monitor for device heartbeat on your local broker
mosquitto_sub -h YOUR_MQTT_BROKER -p 1883 -u USERNAME -P PASSWORD \
  -t '/monitor/+/+/heartbeat' -v
```

You should see heartbeat messages from your device within a minute of power cycling.

## Installation

### Option 1: Manual Installation

1. Copy the `custom_components/qubo_local` directory to your Home Assistant `custom_components` directory:
   ```bash
   cd /path/to/homeassistant/config
   mkdir -p custom_components
   cp -r /path/to/qubo-local-control/custom_components/qubo_local custom_components/
   ```

2. Restart Home Assistant

### Option 2: Git Clone

```bash
cd /path/to/homeassistant/config/custom_components
git clone https://github.com/dtechterminal/qubo-local-control.git
mv qubo-local-control/custom_components/qubo_local .
rm -rf qubo-local-control
```

## Configuration

### Automatic Discovery (Recommended)

The integration can automatically discover QUBO devices on your network by listening to MQTT heartbeat messages. It automatically detects whether a device is a Smart Plug or Air Purifier based on the device ID prefix.

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "QUBO Local Control"
4. Select **Automatic Discovery (Recommended)**
5. Wait up to 30 seconds for device discovery
6. Select your device from the dropdown
7. Click **Submit**

The integration will automatically extract all required information (UUIDs, MAC address, device type) from the device's MQTT messages.

### Manual Configuration

If automatic discovery doesn't work, you can manually configure the integration:

#### Step 1: Find Your Device UUIDs

Subscribe to MQTT heartbeat topic to see your device information:

```bash
mosquitto_sub -h YOUR_MQTT_BROKER -p 1883 -u USERNAME -P PASSWORD -t '/monitor/+/+/heartbeat' -v
```

The JSON payload will contain:
```json
{
  "devices": {
    "deviceUUID": "your-device-uuid",
    "entityUUID": "your-entity-uuid",
    "unitUUID": "your-unit-uuid",
    "userUUID": "your-user-uuid",
    "srcDeviceId": "HSP_CC:8D:A2:DC:F3:BC"
  }
}
```

**Device Type Identification:**
- `HSP_` prefix = Smart Plug
- `HPH_` prefix = Air Purifier

#### Step 2: Add Integration in Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "QUBO Local Control"
4. Select **Manual Configuration**
5. Enter the device information:
   - Device UUID
   - Entity UUID
   - Unit UUID
   - Handle Name (userUUID)
   - Device Name (optional, friendly name)
   - Device MAC Address (optional)
   - Device Type (Smart Plug or Air Purifier)
6. Click **Submit**

## Entities Created

### Smart Plug

| Entity | Type | Description |
|--------|------|-------------|
| Switch | `switch` | Controls the power state |
| Power | `sensor` | Current power consumption (W) |
| Voltage | `sensor` | Current voltage (V) |
| Current | `sensor` | Current draw (A) |
| Energy | `sensor` | Total energy consumption (kWh) |

### Air Purifier

| Entity | Type | Description |
|--------|------|-------------|
| Fan | `fan` | On/Off, Speed (Low/Medium/High), Mode (Auto/Manual) |
| PM2.5 | `sensor` | Air quality reading (µg/m³) |
| Filter Life | `sensor` | Remaining filter life (hours) |

#### Fan Entity Attributes

The fan entity exposes additional attributes for dashboard cards:

| Attribute | Description |
|-----------|-------------|
| `percentage` | Current speed as percentage (0-100) |
| `preset_mode` | Current mode (Auto/Manual) |
| `preset_modes` | Available modes list |
| `pm25` | Current PM2.5 reading (µg/m³) |
| `aqi` | Alias for pm25 (for card compatibility) |
| `filter_life_remaining` | Filter hours remaining |
| `speed` | Current speed level (1/2/3) |
| `speed_list` | Available speed levels |

## MQTT Topics

### Smart Plug Topics

#### Control (Publish)
- `/control/{unit_uuid}/{device_uuid}/lcSwitchControl` - Switch control
- `/control/{unit_uuid}/{device_uuid}/meteringRefresh` - Energy monitoring refresh

#### Monitor (Subscribe)
- `/monitor/{unit_uuid}/{device_uuid}/lcSwitchControl` - Switch state updates
- `/monitor/{unit_uuid}/{device_uuid}/plugMetering` - Energy data updates
- `/monitor/{unit_uuid}/{device_uuid}/heartbeat` - Device heartbeat

### Air Purifier Topics

#### Control (Publish)
- `/control/{unit_uuid}/{device_uuid}/lcSwitchControl` - Power control
- `/control/{unit_uuid}/{device_uuid}/fanSpeedControl` - Fan speed (1/2/3)
- `/control/{unit_uuid}/{device_uuid}/fanControlMode` - Mode (auto/manual)
- `/control/{unit_uuid}/{device_uuid}/aqiRefresh` - AQI data refresh
- `/control/{unit_uuid}/{device_uuid}/filterReset` - Filter status request

#### Monitor (Subscribe)
- `/monitor/{unit_uuid}/{device_uuid}/lcSwitchControl` - Power state updates
- `/monitor/{unit_uuid}/{device_uuid}/fanSpeedControl` - Speed state updates
- `/monitor/{unit_uuid}/{device_uuid}/fanControlMode` - Mode state updates
- `/monitor/{unit_uuid}/{device_uuid}/aqiStatus` - PM2.5 readings
- `/monitor/{unit_uuid}/{device_uuid}/filterReset` - Filter life remaining
- `/monitor/{unit_uuid}/{device_uuid}/heartbeat` - Device heartbeat

## Lovelace Dashboard Cards

### Purifier Card (Recommended)

This integration is compatible with [purifier-card](https://github.com/denysdovhan/purifier-card) for a beautiful air purifier UI.

**Installation:**
1. Install purifier-card via HACS or manually
2. Add the card to your dashboard

**Example Configuration:**
```yaml
type: custom:purifier-card
entity: fan.qubo_air_purifier
show_name: true
show_state: true
show_toolbar: true

# AQI display (reads from fan entity attribute)
aqi:
  attribute: aqi
  unit: 'µg/m³'

# Stats display
stats:
  - attribute: pm25
    unit: 'µg/m³'
    subtitle: PM2.5
  - attribute: filter_life_remaining
    unit: 'hours'
    subtitle: Filter Life

# Quick shortcuts
shortcuts:
  - name: Low
    icon: mdi:fan-speed-1
    percentage: 33
  - name: Medium
    icon: mdi:fan-speed-2
    percentage: 66
  - name: High
    icon: mdi:fan-speed-3
    percentage: 100
  - name: Auto
    icon: mdi:brightness-auto
    preset_mode: Auto
  - name: Manual
    icon: mdi:hand-back-right
    preset_mode: Manual
```

### Standard Fan Card

You can also use the built-in fan card:
```yaml
type: fan
entity: fan.qubo_air_purifier
name: Air Purifier
```

## Troubleshooting

### No Energy Data (Smart Plug)

If energy sensors are not updating:

1. Check that MQTT broker is accessible
2. Verify device is connected to local MQTT broker
3. Check Home Assistant logs for errors:
   ```
   Settings → System → Logs
   ```

### No AQI Data (Air Purifier)

If PM2.5 sensor is not updating:

1. Verify device is connected to local MQTT broker
2. Check if heartbeat messages are being received
3. The purifier reports AQI every ~3 seconds when running

### Switch/Fan Not Responding

1. Verify MQTT topics are correct
2. Check device UUIDs match your device
3. Monitor MQTT traffic to see if commands are being sent:
   ```bash
   mosquitto_sub -h YOUR_MQTT_BROKER -p 1883 -t '/control/#' -v
   ```

### Device Already Configured Error

Each device can only be added once. To reconfigure:
1. Go to **Settings** → **Devices & Services**
2. Find "QUBO Local Control"
3. Click the three dots menu → **Delete**
4. Add the integration again

## Development

The integration is structured as follows:

```
custom_components/qubo_local/
├── __init__.py          # Main integration setup
├── config_flow.py       # Configuration UI
├── const.py             # Constants and configuration keys
├── fan.py               # Air Purifier fan platform
├── manifest.json        # Integration metadata
├── sensor.py            # Energy and AQI sensors
├── strings.json         # UI strings
├── switch.py            # Switch platform
└── translations/
    └── en.json          # English translations
```

## Protocol Details

### Power Control (Both Devices)
```json
{
  "command": {
    "devices": {
      "deviceUUID": "device-uuid",
      "entityUUID": "entity-uuid",
      "services": {
        "lcSwitchControl": {
          "attributes": {
            "power": "on"
          },
          "instanceId": 0
        }
      }
    }
  }
}
```

### Fan Speed Control (Air Purifier)
```json
{
  "command": {
    "devices": {
      "deviceUUID": "device-uuid",
      "entityUUID": "entity-uuid",
      "services": {
        "fanSpeedControl": {
          "attributes": {
            "speed": "3"
          },
          "instanceId": 0
        }
      }
    }
  }
}
```
Speed values: `1` (Low), `2` (Medium), `3` (High)

### Fan Mode Control (Air Purifier)
```json
{
  "command": {
    "devices": {
      "deviceUUID": "device-uuid",
      "entityUUID": "entity-uuid",
      "services": {
        "fanControlMode": {
          "attributes": {
            "state": "auto"
          },
          "instanceId": 0
        }
      }
    }
  }
}
```
Mode values: `auto`, `manual`

### Energy Refresh (Smart Plug)
```json
{
  "command": {
    "devices": {
      "deviceUUID": "device-uuid",
      "handleName": "user-uuid",
      "services": {
        "meteringRefresh": {
          "attributes": {
            "duration": "60"
          },
          "instanceId": 0
        }
      }
    }
  }
}
```

### AQI Status Response (Air Purifier)
```json
{
  "devices": {
    "services": {
      "aqiStatus": {
        "events": {
          "stateChanged": {
            "PM25": "5"
          }
        },
        "instanceId": "0"
      }
    }
  }
}
```

### Filter Status Response (Air Purifier)
```json
{
  "devices": {
    "services": {
      "filterReset": {
        "events": {
          "stateChanged": {
            "timeRemaining": "8997"
          }
        },
        "instanceId": "0"
      }
    }
  }
}
```
`timeRemaining` is in hours.

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Credits

Developed by [@dtechterminal](https://github.com/dtechterminal)

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/dtechterminal/qubo-local-control/issues).
