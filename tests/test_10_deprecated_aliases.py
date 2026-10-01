"""Collection of unit tests for the deprecated gNMI alias arguments"""
# Modules
import warnings
import pytest
from pygnmi.client import gNMIclient, ALIASES_REMOVED


# Statics
SUBSCRIPTION = {
    "subscription": [{"path": "/interfaces/interface[name=Ethernet1]", "mode": "on_change"}],
    "mode": "stream",
    "encoding": "json",
}


# Tests
def _client():
    """The constructor does not connect, so request building needs no device"""
    return gNMIclient(target=("127.0.0.1", 57400), insecure=True)


def test_subscribe_without_use_aliases_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        request = _client()._build_subscriptionrequest(dict(SUBSCRIPTION))

    assert request.subscribe.subscription[0].path.elem[0].name == "interfaces"


def test_use_aliases_false_warns_and_is_ignored():
    with pytest.warns(DeprecationWarning, match="use_aliases is deprecated"):
        request = _client()._build_subscriptionrequest({**SUBSCRIPTION, "use_aliases": False})

    assert request.subscribe.subscription[0].path.elem[0].name == "interfaces"


def test_use_aliases_true_is_rejected():
    with pytest.raises(ValueError, match=ALIASES_REMOVED):
        _client()._build_subscriptionrequest({**SUBSCRIPTION, "use_aliases": True})


def test_subscribe_aliases_argument_is_rejected():
    with pytest.raises(ValueError, match=ALIASES_REMOVED):
        _client().subscribe(aliases=[("/interfaces", "#interfaces")])
