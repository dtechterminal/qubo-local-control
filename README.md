# QUBO Local Control - Home Assistant Integration

Home Assistant custom integration for local control of QUBO Smart Plugs via MQTT.

## Features

- **100% Local Control** - No cloud dependency, complete privacy
- **Real-time Switch Control** - Turn devices on/off instantly
- **Energy Monitoring** - Track power consumption, voltage, current, and total energy
- **Automatic Updates** - Energy data refreshed every 60 seconds
- **Device Integration** - All entities grouped under a single device in Home Assistant

## Requirements

- Home Assistant with MQTT integration configured
- Local MQTT broker (e.g., Mosquitto)
- QUBO Smart Plug configured to use local MQTT broker

## Installation

### Option 1: Manual Installation

1. Copy the `custom_components/qubo_local` directory to your Home Assistant `custom_components` directory:
   ```bash
   cd /path/to/homeassistant/config
   mkdir -p custom_components
   cp -r /path/to/iot-local-control/custom_components/qubo_local custom_components/
   ```

2. Restart Home Assistant

### Option 2: Git Clone

```bash
cd /path/to/homeassistant/config/custom_components
git clone https://github.com/dtechterminal/iot-local-control.git
mv iot-local-control/custom_components/qubo_local .
rm -rf iot-local-control
```

## Configuration

### Step 1: Gather Device Information

You'll need the following UUIDs from your QUBO device. You can find these by monitoring MQTT messages from your device:

- **Device UUID** - Unique identifier for your QUBO device
- **Entity UUID** - Entity identifier from MQTT messages
- **Unit UUID** - Unit identifier from MQTT messages
- **Handle Name** - Usually your userUUID

### Step 2: Find Your Device UUIDs

Subscribe to all MQTT topics to see your device information:

```bash
mosquitto_sub -h YOUR_MQTT_BROKER -p 1883 -u USERNAME -P PASSWORD -t '#' -v
```

Look for messages on topics like:
```
/monitor/{unit_uuid}/{device_uuid}/lcSwitchControl
/monitor/{unit_uuid}/{device_uuid}/plugMetering
```

The JSON payload will contain:
```json
{
  "devices": {
    "deviceUUID": "your-device-uuid",
    "entityUUID": "your-entity-uuid",
    "unitUUID": "your-unit-uuid",
    "userUUID": "your-user-uuid"
  }
}
```

### Step 3: Add Integration in Home Assistant

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "QUBO Local Control"
4. Enter the device information:
   - Device UUID
   - Entity UUID
   - Unit UUID
   - Handle Name (userUUID)
   - Device Name (optional, friendly name)
   - Device MAC Address (optional)

5. Click **Submit**

## Entities Created

The integration creates the following entities for each device:

### Switch
- **Switch** - Controls the power state of the smart plug

### Sensors
- **Power** - Current power consumption (W)
- **Voltage** - Current voltage (V)
- **Current** - Current draw (A)
- **Energy** - Total energy consumption (kWh)

## MQTT Topics

The integration uses the following MQTT topic patterns:

### Control Topics (Publish)
- `/control/{unit_uuid}/{device_uuid}/lcSwitchControl` - Switch control
- `/control/{unit_uuid}/{device_uuid}/meteringRefresh` - Energy monitoring refresh

### Monitor Topics (Subscribe)
- `/monitor/{unit_uuid}/{device_uuid}/lcSwitchControl` - Switch state updates
- `/monitor/{unit_uuid}/{device_uuid}/plugMetering` - Energy data updates
- `/monitor/{unit_uuid}/{device_uuid}/heartbeat` - Device heartbeat

## Energy Monitoring

The integration automatically sends `meteringRefresh` commands every 60 seconds to keep energy data flowing. This mimics the behavior of the official QUBO app.

## Troubleshooting

### No Energy Data

If energy sensors are not updating:

1. Check that MQTT broker is accessible
2. Verify device is connected to local MQTT broker
3. Check Home Assistant logs for errors:
   ```
   Settings → System → Logs
   ```

### Switch Not Responding

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
├── manifest.json        # Integration metadata
├── sensor.py            # Energy monitoring sensors
├── strings.json         # UI strings
├── switch.py            # Switch platform
└── translations/
    └── en.json          # English translations
```

## Protocol Details

### Switch Command Format
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

### Energy Refresh Command Format
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

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Credits

Developed by [@dtechterminal](https://github.com/dtechterminal)

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/dtechterminal/iot-local-control/issues).
