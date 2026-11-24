"""
Device tests for the 0.10.0 changes, run against a real gNMI target.

Skipped unless PYGNMI_HOST is set (see conftest.py). scripts/device-lab.sh sets
every variable for its one-switch cEOS lab. PYGNMI_PLAIN_PORT is a plaintext
gNMI transport on the same target, for the insecure-channel tests.

Every change is made on a dedicated loopback, which a fixture deletes again.
"""

import os
import time

import pytest

from pygnmi.client import gNMIclient, gNMIException

HOST = os.getenv("PYGNMI_HOST")
PORT = os.getenv("PYGNMI_PORT")
PLAIN_PORT = os.getenv("PYGNMI_PLAIN_PORT")
USER = os.getenv("PYGNMI_USER")
PASSWORD = os.getenv("PYGNMI_PASS")
CERT = os.getenv("PYGNMI_CERT")

LOOPBACK = "Loopback52"
LOOPBACK_PATH = f"openconfig:interfaces/interface[name={LOOPBACK}]"
DESCRIPTION_PATH = f"{LOOPBACK_PATH}/config/description"

# Short, so a rollback test waits seconds rather than a minute
ROLLBACK_SECONDS = 5


def tls_client():
    return gNMIclient(target=(HOST, PORT), username=USER, password=PASSWORD, path_cert=CERT)


def loopback_config(description):
    return {"name": LOOPBACK, "type": "softwareLoopback", "description": description, "enabled": True}


def read_description(gc):
    """The loopback's description, or None when the loopback does not exist."""
    try:
        result = gc.get(path=[DESCRIPTION_PATH])
    except gNMIException:
        return None
    for notification in result.get("notification", []):
        for update in notification.get("update", []):
            val = update["val"]
            # Targets answer either with the bare leaf or wrapped in its name
            if isinstance(val, dict):
                val = next(iter(val.values()))
            return val
    return None


def commit(action, **params):
    return {"commit": {"id": "pygnmi-device-test", action: params}}


@pytest.fixture
def gc():
    """A TLS client, with the test loopback removed afterwards."""
    with tls_client() as client:
        yield client
        try:
            client.set(delete=[LOOPBACK_PATH])
        except gNMIException:
            pass


@pytest.fixture
def baseline(gc):
    """The loopback exists with a known description before the test starts."""
    gc.set(update=[(LOOPBACK_PATH, {"config": loopback_config("baseline")})])
    assert read_description(gc) == "baseline"
    return gc


# ---- insecure channel ---------------------------------------------------------


def test_insecure_channel_authenticates_with_metadata():
    """Credentials travel as call metadata only; a correct pair is accepted."""
    with gNMIclient(target=(HOST, PLAIN_PORT), username=USER, password=PASSWORD, insecure=True) as client:
        assert client.capabilities()["gnmi_version"]
        assert client.get(path=["openconfig:system/config/hostname"])["notification"]


def test_insecure_channel_rejects_wrong_password():
    """The metadata really is what authenticates: a wrong password fails.

    connect() calls Capabilities, so that is where the rejection surfaces."""
    client = gNMIclient(target=(HOST, PLAIN_PORT), username=USER, password="wrong", insecure=True)
    try:
        with pytest.raises(gNMIException, match="Authentication failed"):
            client.connect()
    finally:
        client.close()


# ---- union_replace ------------------------------------------------------------


def test_union_replace_with_the_full_cli_config(gc):
    """union_replace replaces the target's whole configuration with what is sent.

    On EOS (with `operation set namespace`) a fragment would wipe everything else,
    users and gNMI transports included. So the test sends the full running
    config, read through the CLI origin, with one loopback added, then checks
    the loopback arrived and the rest survived.
    """
    running = gc.get(path=["cli:show running-config"], encoding="ascii")["notification"][0]["update"][0]["val"]
    assert running.rstrip().endswith("end")
    config = running.rstrip()[: -len("end")] + f"interface {LOOPBACK}\n   description union-replace\n!\nend\n"

    result = gc.set(union_replace=[("cli://", config)], encoding="ascii")

    assert result["response"][0]["op"] == "UNION_REPLACE"
    # Reading back over the same TLS client proves users and transports survived
    assert read_description(gc) == "union-replace"
    hostname = gc.get(path=["openconfig:system/config/hostname"])["notification"][0]["update"][0]["val"]
    assert hostname == "ceos1"


# ---- commit confirmed ---------------------------------------------------------


def test_commit_confirmed_then_confirm_keeps_the_change(baseline):
    baseline.set(
        update=[(DESCRIPTION_PATH, "confirmed")],
        extension=commit("commit", rollback_duration=ROLLBACK_SECONDS),
    )
    baseline.set(extension=commit("confirm"))

    time.sleep(ROLLBACK_SECONDS + 3)
    assert read_description(baseline) == "confirmed"


def test_commit_confirmed_without_confirm_rolls_back(baseline):
    baseline.set(
        update=[(DESCRIPTION_PATH, "rolled-back")],
        extension=commit("commit", rollback_duration=ROLLBACK_SECONDS),
    )
    assert read_description(baseline) == "rolled-back"

    time.sleep(ROLLBACK_SECONDS + 3)
    assert read_description(baseline) == "baseline"


def test_commit_confirmed_cancel_rolls_back_at_once(baseline):
    baseline.set(
        update=[(DESCRIPTION_PATH, "cancelled")],
        extension=commit("commit", rollback_duration=60),
    )
    baseline.set(extension=commit("cancel"))

    assert read_description(baseline) == "baseline"


def test_set_with_retry_passes_the_extension(baseline):
    baseline.set_with_retry(
        update=[(DESCRIPTION_PATH, "retry-confirmed")],
        extension=commit("commit", rollback_duration=60),
    )
    baseline.set(extension=commit("confirm"))

    assert read_description(baseline) == "retry-confirmed"


# ---- leaf-lists -----------------------------------------------------------------


def test_leaflist_of_strings_decodes_to_a_list():
    """A leaf-list streamed as leaflist_val arrives as a Python list of strings."""
    domains = ["a.example", "b.example"]
    path = "openconfig:system/dns/config"
    with tls_client() as client:
        client.set(update=[(path, {"search": domains})])
        try:
            subscription = {
                "subscription": [{"path": "/system/dns/config/search", "mode": "target_defined"}],
                "mode": "once",
            }
            values = []
            for message in client.subscribe2(subscribe=subscription):
                if message.get("sync_response"):
                    break
                for update in message.get("update", {}).get("update", []):
                    values.append(update["val"])
        finally:
            client.set(delete=[f"{path}/search"])

    assert values, "the target streamed no value for the search leaf-list"
    assert sorted(values[-1]) == domains
