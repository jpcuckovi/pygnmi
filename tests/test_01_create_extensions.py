"""Collection of unit tests to test the generation of Extensions"""
# Modules
import datetime
import pytest
from pygnmi.create_gnmi_extension import get_gnmi_extension
from pygnmi.spec.v0100.gnmi_ext_pb2 import Extension


# Statics
EXT1 = {
        'history': {
            'snapshot_time': 1626166020000000000
        }
       }

EXT2 = {
        'history': {
            'snapshot_time': '2021-07-13T09:47:00Z'
        }
       }

EXT3 = {
        'history': {
            'range': {
                'start': '2021-07-13T09:47:00Z',
                'end': '2021-07-13T09:51:00Z'
            }
        }
       }

EXT4 = {
        'history': {
            'range': {
                'start': 1626166020000000000,
                'end': 1626166260000000000
            }
        }
       }

EXT5 = {}

EXT6 = None


# Tests
def test_extension_history_snapshot_time_ns(ext=EXT1):
    """Unit test to verify time provied in ns is properly set
    for /extension/history/snapshot_time key"""
    gnmi_ext = get_gnmi_extension(ext)
    assert isinstance(gnmi_ext.history.snapshot_time, int)


def test_extension_history_snapshot_time_str(ext=EXT2):
    """Unit test to verify time provied as a string is properly set
    for /extension/history/snapshot_time key"""
    gnmi_ext = get_gnmi_extension(ext)
    assert isinstance(gnmi_ext.history.snapshot_time, int)


def test_extension_history_range_ns(ext=EXT3):
    """Unit test to verify time provied in ns is properly set
    for /extension/history/range/{start,end} keys"""
    gnmi_ext = get_gnmi_extension(ext)
    assert isinstance(gnmi_ext.history.range.start, int)
    assert isinstance(gnmi_ext.history.range.end, int)


def test_extension_history_range_str(ext=EXT4):
    """Unit test to verify time provied as a sting is properly set
    for /extension/history/range/{start,end} keys"""
    gnmi_ext = get_gnmi_extension(ext)
    assert isinstance(gnmi_ext.history.range.start, int)
    assert isinstance(gnmi_ext.history.range.end, int)


def test_extension_empty_dict(ext=EXT5):
    """Unit test to verify /extension is not created
    for empty dict"""
    gnmi_ext = get_gnmi_extension(ext)
    assert not gnmi_ext


def test_extension_empty_none(ext=EXT6):
    """Unit test to verify /extension is not created
    for None"""
    gnmi_ext = get_gnmi_extension(ext)
    assert not gnmi_ext


def _roundtrip(gnmi_ext):
    """Encodes and decodes the extension, so assertions check what goes on the wire"""
    return Extension.FromString(gnmi_ext.SerializeToString())


def test_extension_commit_request_with_rollback_seconds():
    """Unit test to verify a commit request carries the id and rollback duration"""
    gnmi_ext = _roundtrip(get_gnmi_extension({"commit": {"id": "c1", "commit": {"rollback_duration": 60}}}))
    assert gnmi_ext.WhichOneof("ext") == "commit"
    assert gnmi_ext.commit.id == "c1"
    assert gnmi_ext.commit.WhichOneof("action") == "commit"
    assert gnmi_ext.commit.commit.rollback_duration.seconds == 60


def test_extension_commit_request_with_rollback_timedelta():
    """Unit test to verify rollback duration accepts datetime.timedelta"""
    gnmi_ext = _roundtrip(
        get_gnmi_extension({"commit": {"id": "c1", "commit": {"rollback_duration": datetime.timedelta(seconds=1.5)}}})
    )
    assert gnmi_ext.commit.commit.rollback_duration.seconds == 1
    assert gnmi_ext.commit.commit.rollback_duration.nanos == 500000000


def test_extension_commit_request_without_rollback():
    """Unit test to verify a commit request without rollback duration still selects the commit action"""
    gnmi_ext = _roundtrip(get_gnmi_extension({"commit": {"id": "c1", "commit": None}}))
    assert gnmi_ext.commit.WhichOneof("action") == "commit"
    assert not gnmi_ext.commit.commit.HasField("rollback_duration")


@pytest.mark.parametrize("action", ["confirm", "cancel"])
def test_extension_commit_confirm_and_cancel(action):
    """Unit test to verify confirm and cancel select their action with the id"""
    gnmi_ext = _roundtrip(get_gnmi_extension({"commit": {"id": "c1", action: {}}}))
    assert gnmi_ext.commit.id == "c1"
    assert gnmi_ext.commit.WhichOneof("action") == action


def test_extension_commit_set_rollback_duration():
    """Unit test to verify set_rollback_duration carries the new duration"""
    gnmi_ext = _roundtrip(
        get_gnmi_extension({"commit": {"id": "c1", "set_rollback_duration": {"rollback_duration": 300}}})
    )
    assert gnmi_ext.commit.WhichOneof("action") == "set_rollback_duration"
    assert gnmi_ext.commit.set_rollback_duration.rollback_duration.seconds == 300


@pytest.mark.parametrize(
    "commit",
    [
        {"commit": {}},
        {"id": "", "commit": {}},
        {"id": "c1"},
        {"id": "c1", "confirm": {}, "cancel": {}},
        {"id": "c1", "set_rollback_duration": {}},
        {"id": "c1", "commit": {"rollback_duration": "60"}},
        {"id": "c1", "commit": {"rollback_duration": True}},
        {"id": "c1", "confirm": True},
    ],
)
def test_extension_commit_invalid(commit):
    """Unit test to verify malformed commit extensions are rejected"""
    with pytest.raises(ValueError):
        get_gnmi_extension({"commit": commit})


def test_extension_commit_not_combined():
    """Unit test to verify commit is not silently dropped or dropping another extension,
    as an Extension message carries exactly one"""
    with pytest.raises(ValueError):
        get_gnmi_extension({"commit": {"id": "c1", "confirm": {}}, "history": {"snapshot_time": 1}})
