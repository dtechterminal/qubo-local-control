<p align="center">
  <img src="https://d29rw3zaldax51.cloudfront.net/assets/images/footer/black-theam.png" alt="QUBO Logo" width="200">
</p>

# QUBO Local Control - Home Assistant Integration

[![Version](https://img.shields.io/badge/version-1.4.1-blue.svg)](https://github.com/dtechterminal/qubo-local-control/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-green.svg)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

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
- **Air Quality Monitoring** - Real-time PM2.5 readings (updated every ~3 seconds)
- **Filter Life Tracking** - Monitor remaining filter life in hours (auto-refreshed hourly)
- **Purifier Card Compatible** - Works with popular purifier-card for beautiful UI

### General
- **Device Integration** - All entities grouped under a single device in Home Assistant
- **Auto Device Type Detection** - Automatically identifies Smart Plugs (HSP) and Air Purifiers (HPH)

## Requirements

- Home Assistant with MQTT integration configured
- Local MQTT broker (e.g., Mosquitto) **with TLS/SSL enabled on port 8883**
- Router or DNS server with custom DNS entry support
- **All network clients must use your DNS server** (router DNS settings)
- QUBO Smart Plug and/or Air Purifier

> **Important:** QUBO devices connect to `mqtt.platform.quboworld.com` on **port 8883 using TLS/SSL encryption**. Your local MQTT broker must be configured with TLS certificates to accept these connections. Simple DNS redirection without TLS will not work.

## Setup Local MQTT Redirect

To enable local control, you need to redirect the QUBO device's cloud MQTT connection to your local broker. This requires two key components:

1. **TLS-enabled MQTT broker** listening on port 8883
2. **DNS override** to redirect the cloud hostname to your local broker

### Step 1: Configure Mosquitto with TLS

First, set up your MQTT broker with TLS support. Here's a complete Mosquitto configuration:

#### Generate Self-Signed Certificates

```bash
# Create directory for certificates
sudo mkdir -p /etc/mosquitto/certs
cd /etc/mosquitto/certs

# Generate CA key and certificate
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/CN=MQTT CA"

# Generate server key and certificate signing request
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=mqtt.platform.quboworld.com"

# Create extensions file for SAN (Subject Alternative Name)
cat > server.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = mqtt.platform.quboworld.com
DNS.2 = localhost
IP.1 = 192.168.1.68
EOF

# Sign the server certificate (replace IP with your broker's IP)
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out server.crt -days 3650 -extfile server.ext

# Set permissions
sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*
sudo chmod 600 /etc/mosquitto/certs/*.key
```

#### Mosquitto Configuration

Create or edit `/etc/mosquitto/conf.d/qubo.conf`:

```conf
# Standard MQTT (optional, for local testing)
listener 1883 localhost
allow_anonymous true

# TLS MQTT for QUBO devices (required)
listener 8883
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
cafile /etc/mosquitto/certs/ca.crt

# Allow connections without client certificates
require_certificate false

# Authentication (optional but recommended)
allow_anonymous true
# Or use password file:
# password_file /etc/mosquitto/passwd
# allow_anonymous false

# Logging (helpful for debugging)
log_type all
log_dest file /var/log/mosquitto/mosquitto.log
```

Restart Mosquitto:
```bash
sudo systemctl restart mosquitto
```

Verify TLS is working:
```bash
# Test TLS connection locally
mosquitto_sub -h localhost -p 8883 --cafile /etc/mosquitto/certs/ca.crt \
  -t '/monitor/#' -v

# Or without certificate verification (for testing)
mosquitto_sub -h localhost -p 8883 --insecure \
  -t '/monitor/#' -v
```

### Step 2: Configure DNS Redirect

Configure your DNS to resolve `mqtt.platform.quboworld.com` to your local MQTT broker's IP address.

> **Critical:** Your router must be configured to use your DNS server (Pi-hole, AdGuard Home, etc.) as the primary DNS for ALL clients. If devices use external DNS directly (8.8.8.8, etc.), the redirect won't work.

#### Option A: Pi-hole

1. Go to **Local DNS** → **DNS Records**
2. Add entry:
   - **Domain:** `mqtt.platform.quboworld.com`
   - **IP Address:** Your MQTT broker IP (e.g., `192.168.1.68`)
3. Ensure your router's DHCP assigns Pi-hole as the DNS server

#### Option B: AdGuard Home

1. Go to **Filters** → **DNS rewrites**
2. Add rewrite:
   - **Domain:** `mqtt.platform.quboworld.com`
   - **Answer:** Your MQTT broker IP
3. Ensure router uses AdGuard as DNS server

#### Option C: Router DNS Override

Some routers support custom DNS entries directly:
1. Access router admin panel
2. Find DNS or Host Override settings
3. Add: `mqtt.platform.quboworld.com` → `192.168.1.68`

#### Verify DNS Resolution

```bash
# From a device on your network
nslookup mqtt.platform.quboworld.com
# Should return your local MQTT broker IP, NOT the cloud IP

# Cloud IPs to watch for (these mean DNS redirect isn't working):
# 65.1.150.122 (AWS Mumbai)
# 13.x.x.x, 52.x.x.x (other AWS IPs)
```

### Step 3: Power Cycle QUBO Device

After DNS and TLS are configured:

1. Unplug the QUBO device from power
2. Wait 10-15 seconds
3. Plug it back in
4. The device will resolve the hostname via your DNS and connect to your local broker

### Step 4: Verify Connection

Monitor for device heartbeat on your local broker:

```bash
# Using TLS (recommended)
mosquitto_sub -h YOUR_MQTT_BROKER -p 8883 \
  --cafile /etc/mosquitto/certs/ca.crt \
  -t '/monitor/+/+/heartbeat' -v

# Without certificate verification (testing only)
mosquitto_sub -h YOUR_MQTT_BROKER -p 8883 --insecure \
  -t '/monitor/+/+/heartbeat' -v

# Or if you have a local non-TLS listener for HA
mosquitto_sub -h YOUR_MQTT_BROKER -p 1883 \
  -t '/monitor/+/+/heartbeat' -v
```

You should see heartbeat messages within 30-60 seconds of power cycling.

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
# Using TLS (port 8883)
mosquitto_sub -h YOUR_MQTT_BROKER -p 8883 --insecure -t '/monitor/+/+/heartbeat' -v

# Or with certificate verification
mosquitto_sub -h YOUR_MQTT_BROKER -p 8883 --cafile /etc/mosquitto/certs/ca.crt \
  -t '/monitor/+/+/heartbeat' -v

# Or on local non-TLS listener (if configured)
mosquitto_sub -h YOUR_MQTT_BROKER -p 1883 -t '/monitor/+/+/heartbeat' -v
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

### Device Not Connecting to Local Broker

This is the most common issue. Follow these steps to diagnose:

#### 1. Verify DNS Resolution

Check that the QUBO hostname resolves to your local IP:

```bash
# From a computer on the same network
nslookup mqtt.platform.quboworld.com

# Expected: Your local MQTT broker IP (e.g., 192.168.1.68)
# Problem: Cloud IP like 65.1.150.122, 13.x.x.x, 52.x.x.x
```

**If DNS returns cloud IP:**
- Ensure your router uses your DNS server (Pi-hole/AdGuard) as primary DNS
- Check that the DNS server has the correct entry
- Some routers/devices bypass local DNS - check for hardcoded DNS settings

#### 2. Verify TLS Certificate

Test your TLS setup:

```bash
# Test TLS connection to your broker
openssl s_client -connect YOUR_BROKER_IP:8883 -servername mqtt.platform.quboworld.com

# Check certificate details
openssl s_client -connect YOUR_BROKER_IP:8883 </dev/null 2>/dev/null | openssl x509 -text -noout
```

**Common TLS issues:**
- Certificate CN must match `mqtt.platform.quboworld.com`
- SAN (Subject Alternative Name) should include the hostname
- Certificate must not be expired

#### 3. Check Mosquitto Logs

```bash
# View Mosquitto logs
sudo tail -f /var/log/mosquitto/mosquitto.log

# Look for:
# - "New connection from [IP]" - device is reaching your broker
# - "Socket error" or "TLS error" - certificate/TLS issues
# - "Client disconnected" - connection but then drop
```

#### 4. Monitor Network Traffic

Use tcpdump to see if the device is reaching your broker:

```bash
# Monitor port 8883 traffic
sudo tcpdump -i any port 8883 -n

# You should see traffic from the QUBO device IP to your broker
# If traffic goes to AWS IPs (65.1.x.x, 13.x.x.x), DNS redirect isn't working
```

#### 5. Test MQTT Subscription

```bash
# Subscribe to all topics on TLS port
mosquitto_sub -h YOUR_BROKER -p 8883 --insecure -t '#' -v

# Or with certificate
mosquitto_sub -h YOUR_BROKER -p 8883 --cafile /etc/mosquitto/certs/ca.crt -t '#' -v
```

### No Heartbeat Messages

If DNS and TLS are correct but no heartbeats appear:

1. **Power cycle the device** - Unplug for 10+ seconds, then reconnect
2. **Check Mosquitto is listening on 8883:**
   ```bash
   sudo netstat -tlnp | grep mosquitto
   # Should show: 0.0.0.0:8883
   ```
3. **Verify firewall allows port 8883:**
   ```bash
   sudo ufw status  # or your firewall tool
   ```

### Certificate Pinning (Advanced)

Some QUBO firmware versions may implement certificate pinning, which validates the server certificate against a known certificate. If you suspect this:

1. Check device firmware version in the QUBO app
2. Try downgrading firmware if possible
3. The device may require the exact certificate chain from the cloud broker

> **Note:** Certificate pinning is a security feature. If the device uses it, local control may not be possible without firmware modification.

### No Energy Data (Smart Plug)

If energy sensors are not updating:

1. Check that MQTT broker is accessible
2. Verify device is connected to local MQTT broker (check heartbeats)
3. Check Home Assistant logs for errors:
   ```
   Settings → System → Logs
   ```
4. Ensure the `plugMetering` topic is being published

### No AQI Data (Air Purifier)

If PM2.5 sensor is not updating:

1. Verify device is connected to local MQTT broker
2. Check if heartbeat messages are being received
3. The purifier reports AQI every ~3 seconds when running
4. Try sending an `aqiRefresh` command manually

### Switch/Fan Not Responding

1. Verify MQTT topics are correct
2. Check device UUIDs match your device
3. Monitor MQTT traffic to see if commands are being sent:
   ```bash
   mosquitto_sub -h YOUR_MQTT_BROKER -p 8883 --insecure -t '/control/#' -v
   ```
4. Verify Home Assistant MQTT integration is configured for TLS

### Home Assistant MQTT Integration Setup

Ensure Home Assistant's MQTT integration is configured to connect to your broker:

```yaml
# configuration.yaml (if not using UI)
mqtt:
  broker: YOUR_BROKER_IP
  port: 1883  # Use non-TLS port for HA, or 8883 with certificate config
  # If using TLS for HA connection:
  # port: 8883
  # certificate: /ssl/ca.crt
```

Most setups use a non-TLS local listener (port 1883) for Home Assistant while the TLS listener (port 8883) handles QUBO devices.

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

## Changelog

### v1.4.1
- Improved documentation with detailed TLS/SSL setup instructions
- Added comprehensive Mosquitto TLS configuration guide
- Added troubleshooting section for DNS and TLS connection issues
- Clarified that QUBO devices use port 8883 with TLS (not plain MQTT)
- Added Pi-hole, AdGuard Home, and router DNS configuration examples

### v1.4.0
- Fixed fan state not updating correctly after power toggle
- Added automatic hourly filter status refresh
- Fixed energy sensor state class for proper long-term statistics

### v1.3.0
- Added Air Purifier support with fan control, PM2.5 sensor, and filter life tracking
- Added purifier-card compatibility with extra state attributes

### v1.2.0
- Added automatic device discovery via MQTT heartbeat messages
- Improved device type auto-detection (Smart Plug vs Air Purifier)

### v1.0.0
- Initial release with Smart Plug support
- Switch control and energy monitoring

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/dtechterminal/qubo-local-control/issues).
