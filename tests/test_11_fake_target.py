"""
Client behaviour against the in-process fake target: no device needed.

Each test sets the target's canned response, calls the client, and checks both
what came back and the exact request the target received.
"""

import json
import logging

import grpc
import pytest

import pygnmi.client
from pygnmi.client import gNMIclient, gNMIException, telemetryParser
from pygnmi.create_gnmi_path import gnmi_path_degenerator, gnmi_path_generator
from pygnmi.spec.v0100.gnmi_pb2 import (
    CapabilityResponse,
    Encoding,
    GetResponse,
    Notification,
    ScalarArray,
    SetResponse,
    SubscribeResponse,
    SubscriptionList,
    TypedValue,
    Update,
    UpdateResult,
)


def _notification(path, value, timestamp=1700000000000000000):
    return Notification(
        timestamp=timestamp,
        update=[Update(path=gnmi_path_generator(path), val=TypedValue(json_val=json.dumps(value).encode()))],
    )


# ---- connection and capabilities -----------------------------------------


def test_connect_sends_credentials_as_metadata(client, fake):
    assert len(fake.target.requests["Capabilities"]) == 1
    assert fake.target.metadata[0]["username"] == "admin"
    assert fake.target.metadata[0]["password"] == "secret"


def test_capabilities_are_decoded(client):
    caps = client.capabilities()

    assert caps["gnmi_version"] == "0.10.0"
    assert caps["supported_encodings"] == ["json", "json_ietf"]
    assert caps["supported_models"][0]["name"] == "openconfig-interfaces"


def test_encoding_follows_capabilities(fake):
    # A target without JSON makes json_ietf the first preference it supports
    fake.target.capabilities_response = CapabilityResponse(supported_encodings=[Encoding.JSON_IETF])
    with gNMIclient(target=("127.0.0.1", fake.port), insecure=True) as gc:
        gc.get(path=["/interfaces"])

    assert fake.target.requests["Get"][0].encoding == Encoding.JSON_IETF


def test_insecure_channel_options_carry_no_credentials(fake, monkeypatch):
    seen = {}
    real = grpc.insecure_channel

    def spy(target, options=None, *args, **kwargs):
        seen["options"] = options
        return real(target, options, *args, **kwargs)

    monkeypatch.setattr(pygnmi.client.grpc, "insecure_channel", spy)
    with gNMIclient(target=("127.0.0.1", fake.port), username="admin", password="secret", insecure=True):
        pass

    assert all(key not in ("username", "password") for key, _ in seen["options"])


def test_connect_survives_capabilities_failure(fake, monkeypatch):
    # capabilities() returns None on a non-gRPC failure; connect keeps the default encoding
    monkeypatch.setattr(gNMIclient, "capabilities", lambda self: None)
    with gNMIclient(target=("127.0.0.1", fake.port), insecure=True) as gc:
        gc.get(path=["/system"])

    assert fake.target.requests["Get"][0].encoding == Encoding.JSON


# ---- get --------------------------------------------------------------------


def test_get_request_and_response(client, fake):
    fake.target.get_response = GetResponse(
        notification=[_notification("/interfaces/interface[name=eth1]/config", {"mtu": 1500})]
    )

    result = client.get(path=["/interfaces/interface[name=eth1]/config"], datatype="config")

    sent = fake.target.requests["Get"][0]
    assert gnmi_path_degenerator(sent.path[0]) == "interfaces/interface[name=eth1]/config"
    assert sent.type == sent.CONFIG
    update = result["notification"][0]["update"][0]
    assert update["path"] == "interfaces/interface[name=eth1]/config"
    assert update["val"] == {"mtu": 1500}


def _leaflist(*elements):
    return TypedValue(leaflist_val=ScalarArray(element=list(elements)))


def test_get_leaflist_of_strings(client, fake):
    fake.target.get_response = GetResponse(
        notification=[
            Notification(
                timestamp=1,
                update=[
                    Update(
                        path=gnmi_path_generator("/system/dns/config/search"),
                        val=_leaflist(TypedValue(string_val="a.example"), TypedValue(string_val="b.example")),
                    )
                ],
            )
        ]
    )

    result = client.get(path=["/system/dns/config/search"])

    assert result["notification"][0]["update"][0]["val"] == ["a.example", "b.example"]


def test_get_leaflist_of_json_objects_keeps_merged_shape(client, fake):
    fake.target.get_response = GetResponse(
        notification=[
            Notification(
                timestamp=1,
                update=[
                    Update(
                        path=gnmi_path_generator("/a"),
                        val=_leaflist(TypedValue(json_val=b'{"x": 1}'), TypedValue(json_val=b'{"y": 2}')),
                    )
                ],
            )
        ]
    )

    assert client.get(path=["/a"])["notification"][0]["update"][0]["val"] == {"x": 1, "y": 2}


def test_telemetry_leaflist_of_mixed_scalars():
    message = SubscribeResponse(
        update=Notification(
            timestamp=1,
            update=[
                Update(
                    path=gnmi_path_generator("/a"),
                    val=_leaflist(TypedValue(string_val="x"), TypedValue(uint_val=7), TypedValue(bool_val=True)),
                )
            ],
        )
    )

    assert telemetryParser(message)["update"]["update"][0]["val"] == ["x", 7, True]


def test_grpc_error_keeps_status_code(client, fake):
    fake.target.errors["Get"] = (grpc.StatusCode.PERMISSION_DENIED, "not for you")

    with pytest.raises(gNMIException) as excinfo:
        client.get(path=["/system"])

    assert excinfo.value.orig_exc.code() == grpc.StatusCode.PERMISSION_DENIED
    assert "not for you" in str(excinfo.value)


# ---- set --------------------------------------------------------------------


def test_set_update_replace_delete(client, fake):
    client.set(
        delete=["/system/config/motd-banner"],
        replace=[("/system/config", {"hostname": "leaf1"})],
        update=[("/interfaces/interface[name=eth1]/config", {"mtu": 9000})],
    )

    sent = fake.target.requests["Set"][0]
    assert gnmi_path_degenerator(sent.delete[0]) == "system/config/motd-banner"
    assert json.loads(sent.replace[0].val.json_val) == {"hostname": "leaf1"}
    assert json.loads(sent.update[0].val.json_val) == {"mtu": 9000}
    assert not sent.union_replace
    assert not sent.HasField("prefix")
    assert not sent.extension


def test_set_union_replace(client, fake):
    fake.target.set_response = SetResponse(
        response=[UpdateResult(path=gnmi_path_generator("/system"), op=UpdateResult.UNION_REPLACE)]
    )

    result = client.set(union_replace=[("/system", {"config": {"hostname": "spine1"}})])

    sent = fake.target.requests["Set"][0]
    assert len(sent.union_replace) == 1
    assert gnmi_path_degenerator(sent.union_replace[0].path) == "system"
    assert json.loads(sent.union_replace[0].val.json_val) == {"config": {"hostname": "spine1"}}
    assert result["response"][0]["op"] == "UNION_REPLACE"


def test_set_with_prefix_and_target(client, fake):
    client.set(update=[("config", {"mtu": 9000})], prefix="/interfaces/interface[name=eth1]", target="leaf1")

    sent = fake.target.requests["Set"][0]
    assert sent.prefix.target == "leaf1"
    assert gnmi_path_degenerator(sent.prefix) == "interfaces/interface[name=eth1]"


def test_set_commit_confirmed_extension(client, fake):
    client.set(
        update=[("/system/config", {"hostname": "leaf1"})],
        extension={"commit": {"id": "change-42", "commit": {"rollback_duration": 300}}},
    )

    commit = fake.target.requests["Set"][0].extension[0].commit
    assert commit.id == "change-42"
    assert commit.commit.rollback_duration.seconds == 300


def test_set_with_retry_retries_once_and_keeps_arguments(client, fake, monkeypatch):
    monkeypatch.setattr("pygnmi.client.time.sleep", lambda seconds: None)
    fake.target.errors["Set"] = (grpc.StatusCode.FAILED_PRECONDITION, "locked")

    with pytest.raises(gNMIException):
        client.set_with_retry(
            update=[("config", {"mtu": 9000})],
            prefix="/interfaces/interface[name=eth1]",
            target="leaf1",
            extension={"commit": {"id": "change-42", "commit": {}}},
        )

    sent = fake.target.requests["Set"]
    assert len(sent) == 2
    for request in sent:
        assert request.prefix.target == "leaf1"
        assert request.extension[0].commit.id == "change-42"


# ---- subscribe ----------------------------------------------------------------


SUBSCRIPTION = {"subscription": [{"path": "/interfaces/interface[name=eth1]/state/counters", "mode": "sample"}]}


def _counters(value, timestamp=1700000000000000000):
    return SubscribeResponse(update=_notification("/interfaces/interface[name=eth1]/state/counters", value, timestamp))


def test_subscribe_once(client, fake):
    fake.target.subscribe_responses = [_counters({"in-octets": 10}), SubscribeResponse(sync_response=True)]

    received = list(client.subscribe_once(subscribe=dict(SUBSCRIPTION, mode="once")))

    assert fake.target.requests["Subscribe"][0].subscribe.mode == SubscriptionList.ONCE
    assert received[0]["update"]["update"][0]["val"] == {"in-octets": 10}
    assert received[-1] == {"sync_response": True}


def test_subscribe_stream_coalesces_until_sync(client, fake):
    fake.target.subscribe_responses = [
        _counters({"in-octets": 10}),
        _counters({"out-octets": 20}),
        SubscribeResponse(sync_response=True),
    ]

    subscriber = client.subscribe_stream(subscribe=dict(SUBSCRIPTION))
    try:
        first = subscriber.get_update(timeout=5)
    finally:
        subscriber.close()

    assert first["sync_response"] is True
    assert [u["val"] for u in first["update"]["update"]] == [{"in-octets": 10}, {"out-octets": 20}]


def test_subscribe_poll_answers_each_poll(client, fake):
    fake.target.subscribe_responses = [_counters({"in-octets": 10}), SubscribeResponse(sync_response=True)]

    subscriber = client.subscribe_poll(subscribe=dict(SUBSCRIPTION, mode="poll"))
    try:
        # The first answer follows the subscription itself; each later one follows a Poll
        subscriber.get_update(timeout=5)
        second = subscriber.get_update(timeout=5)
    finally:
        subscriber.close()

    polls = [r for r in fake.target.requests["Subscribe"] if r.HasField("poll")]
    assert len(polls) >= 1
    assert second["update"]["update"][0]["val"] == {"in-octets": 10}


def test_update_with_zero_timestamp_is_not_dropped(client, fake):
    fake.target.subscribe_responses = [_counters({"in-octets": 10}, timestamp=0), SubscribeResponse(sync_response=True)]

    received = list(client.subscribe_once(subscribe=dict(SUBSCRIPTION, mode="once")))

    assert received[0]["update"]["timestamp"] == 0
    assert received[0]["update"]["update"][0]["val"] == {"in-octets": 10}


def test_legacy_subscribe_default_timeout_is_no_deadline(client, fake):
    """subscribe()'s default timeout of 0.0 once became an expired deadline."""
    fake.target.subscribe_responses = [_counters({"in-octets": 10}), SubscribeResponse(sync_response=True)]
    fake.target.subscribe_delay = 0.2

    stream = client.subscribe(subscribe=dict(SUBSCRIPTION, mode="once"))
    try:
        first = telemetryParser(next(stream))
    finally:
        stream.cancel()

    assert first["update"]["update"][0]["val"] == {"in-octets": 10}


def test_subscribe_rejects_a_non_boolean_poll(client):
    with pytest.raises(ValueError):
        client.subscribe(poll="yes")


def test_subscribe_without_a_request_is_an_error(client):
    with pytest.raises(gNMIException):
        client.subscribe()


# ---- logging ------------------------------------------------------------------


def test_library_adds_no_output_handler():
    handlers = logging.getLogger("pygnmi.client").handlers
    assert all(isinstance(h, logging.NullHandler) for h in handlers)
