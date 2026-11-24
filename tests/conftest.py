"""
Shared test setup.

Two kinds of test live here. Most modules talk to a real gNMI device described
by the PYGNMI_* environment variables; they are skipped when PYGNMI_HOST is not
set, so a plain `pytest` run works anywhere. The fake-target tests need nothing
and always run.
"""

import os
from pathlib import Path

import pytest

from pygnmi.client import gNMIclient
from tests.fake_target import RunningTarget

# Modules that need a real device through PYGNMI_HOST and friends
DEVICE_MODULES = {
    "test_02_address_types.py",
    "test_03_connect_methods.py",
    "test_04_functionality.py",
    "test_05_subscription.py",
    "test_06_compare_diff.py",
    "test_07_certificate_download.py",
    "test_08_test_cipher_change.py",
    "test_09_authentication.py",
    "test_12_device_0_10.py",
}


def pytest_collection_modifyitems(config, items):
    if os.getenv("PYGNMI_HOST"):
        return
    skip = pytest.mark.skip(reason="needs a gNMI device: set PYGNMI_HOST and the other PYGNMI_* variables")
    for item in items:
        if Path(str(item.fspath)).name in DEVICE_MODULES:
            item.add_marker(skip)


@pytest.fixture
def fake():
    """A running fake target; tests set its canned responses before calling."""
    with RunningTarget() as running:
        yield running


@pytest.fixture
def client(fake):
    """A gNMIclient connected to the fake target over a plaintext channel."""
    gc = gNMIclient(target=("127.0.0.1", fake.port), username="admin", password="secret", insecure=True)
    gc.connect()
    try:
        yield gc
    finally:
        gc.close()
