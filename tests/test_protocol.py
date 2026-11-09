"""Tests for topics, command payloads and message parsing.

Payload shapes were captured from a real plug and purifier; IDs are synthetic.
"""
import json

import pytest

from qubo import protocol

DEVICE = "11111111-1111-4111-8111-111111111111"
ENTITY = "22222222-2222-4222-8222-222222222222"
UNIT = "33333333-3333-4333-8333-333333333333"
USER = "44444444-4444-4444-8444-444444444444"


def heartbeat(src: str, state: str = "online", sequence: str = "1766926258930") -> str:
    # Formatted like the firmware: spaces around colons, bare numbers
    return (
        '{"devices" : {"action" : 140,"deviceUUID" : "%s","entityUUID" : "%s",'
        '"msgSequenceId" : %s,"operationState" : "%s","srcDeviceId" : "%s",'
        '"timestamp" : %s,"unitUUID" : "%s","userUUID" : "%s"}}'
        % (DEVICE, ENTITY, sequence, state, src, sequence, UNIT, USER)
    )


def report(service: str, values: dict, key: str = "events") -> str:
    entry = {"events": {"stateChanged": values}} if key == "events" else {"attributes": values}
    return json.dumps({"devices": {"deviceUUID": DEVICE, "services": {service: entry}}})


def test_topics():
    assert protocol.control_topic(UNIT, DEVICE, "lcSwitchControl") == (
        f"/control/{UNIT}/{DEVICE}/lcSwitchControl")
    assert protocol.monitor_topic(UNIT, DEVICE) == f"/monitor/{UNIT}/{DEVICE}/#"
    assert protocol.monitor_topic("+", "+", "heartbeat") == "/monitor/+/+/heartbeat"
    assert protocol.service_from_topic(f"/monitor/{UNIT}/{DEVICE}/aqiStatus") == "aqiStatus"


def test_plug_heartbeat_with_leading_zeros():
    # The plug's offline heartbeat has `"msgSequenceId" : 0001`, which is not valid JSON
    payload = heartbeat("HSP_AA:BB:CC:DD:EE:01", state="offline", sequence="0001")
    with pytest.raises(ValueError):
        json.loads(payload)
    beat = protocol.parse_heartbeat(payload)
    assert beat == protocol.Heartbeat(
        DEVICE, ENTITY, UNIT, USER, prefix="HSP", mac="AA:BB:CC:DD:EE:01", online=False)


def test_purifier_heartbeat_online():
    beat = protocol.parse_heartbeat(heartbeat("HPH_AA:BB:CC:DD:EE:02").encode())
    assert beat is not None
    assert (beat.prefix, beat.mac, beat.online) == ("HPH", "AA:BB:CC:DD:EE:02", True)


@pytest.mark.parametrize("src", [
    "C1621596-836D-4B9B-9F33-A7B4C06823B5",  # The QUBO app
    "HSP_",  # No MAC address
    "XYZ_AA:BB:CC:DD:EE:03",  # Unknown device family
    "",
])
def test_heartbeats_that_are_not_devices(src):
    assert protocol.parse_heartbeat(heartbeat(src)) is None


def test_heartbeat_missing_ids():
    payload = json.dumps({"devices": {"srcDeviceId": "HSP_AA:BB:CC:DD:EE:01", "deviceUUID": DEVICE}})
    assert protocol.parse_heartbeat(payload) is None


def test_leading_zero_repair_leaves_strings_alone():
    data = protocol.loads('{"id" : "x:0001", "n" : 007, "f" : 0.5, "z" : 0}')
    assert data == {"id": "x:0001", "n": 7, "f": 0.5, "z": 0}


@pytest.mark.parametrize("payload", [b"", "not json", "[1, 2]", '"text"', "{"])
def test_unreadable_messages(payload):
    assert protocol.loads(payload) is None
    assert protocol.service_values(payload, "aqiStatus") == {}
    assert protocol.parse_heartbeat(payload) is None


@pytest.mark.parametrize("payload", [
    json.dumps({"devices": "offline"}),
    json.dumps({"devices": {"services": []}}),
    json.dumps({"devices": {"services": {"aqiStatus": {"events": {"stateChanged": None}}}}}),
    json.dumps({"devices": {"services": {"aqiStatus": "x"}}}),
])
def test_unexpected_structures(payload):
    assert protocol.service_values(payload, "aqiStatus") == {}


def test_reported_values():
    metering = {"power": "12.5", "voltage": "231", "current": "54", "consumption": "3.2"}
    assert protocol.service_values(report("plugMetering", metering), "plugMetering") == metering
    assert protocol.service_values(report("aqiStatus", {"PM25": "17"}), "aqiStatus") == {"PM25": "17"}
    assert protocol.service_values(
        report("filterReset", {"timeRemaining": 3120}), "filterReset") == {"timeRemaining": 3120}
    # Another service's message is ignored
    assert protocol.service_values(report("aqiStatus", {"PM25": "17"}), "filterReset") == {}


def test_power_reported_as_attributes():
    payload = report("lcSwitchControl", {"power": "on"}, key="attributes")
    assert protocol.service_values(payload, "lcSwitchControl") == {"power": "on"}


def test_set_command_matches_device_format():
    payload = protocol.set_command(DEVICE, ENTITY, "fanSpeedControl", {"speed": "2"})
    assert payload == json.dumps({"command": {"devices": {
        "deviceUUID": DEVICE, "entityUUID": ENTITY,
        "services": {"fanSpeedControl": {"attributes": {"speed": "2"}, "instanceId": 0}},
    }}})


def test_refresh_commands_match_captured_messages():
    # Byte-for-byte what the previous release published, as seen on the broker
    assert protocol.metering_refresh_command(DEVICE, USER, 60) == (
        '{"command": {"devices": {"deviceUUID": "%s", "handleName": "%s", "services": '
        '{"meteringRefresh": {"attributes": {"duration": "60"}, "instanceId": 0}}}}}'
        % (DEVICE, USER))
    assert protocol.request_command(DEVICE, USER, "aqiRefresh", "refresh") == (
        '{"command": {"devices": {"deviceUUID": "%s", "handleName": "%s", "services": '
        '{"aqiRefresh": {"commands": {"refresh": {"instanceId": 0, "parameters": {}}}}}}}}'
        % (DEVICE, USER))
