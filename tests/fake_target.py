"""
An in-process gNMI target for tests that need no network device.

FakeTarget implements the bundled gNMI servicer and answers with canned
messages that each test sets. Every request it receives is recorded, so a test
can assert on exactly what the client sent. A status code set in `errors`
makes that RPC fail, which is how error handling is exercised.
"""

from concurrent import futures

import grpc

from pygnmi.spec.v0100.gnmi_pb2 import (
    CapabilityResponse,
    Encoding,
    GetResponse,
    ModelData,
    SetResponse,
    SubscriptionList,
)
from pygnmi.spec.v0100.gnmi_pb2_grpc import gNMIServicer, add_gNMIServicer_to_server


class FakeTarget(gNMIServicer):
    """Canned responses in, recorded requests out."""

    def __init__(self):
        self.requests = {"Capabilities": [], "Get": [], "Set": [], "Subscribe": []}
        self.metadata = []
        # RPC name -> (grpc.StatusCode, details)
        self.errors = {}

        self.capabilities_response = CapabilityResponse(
            supported_models=[ModelData(name="openconfig-interfaces", organization="OpenConfig", version="3.0.0")],
            supported_encodings=[Encoding.JSON, Encoding.JSON_IETF],
            gNMI_version="0.10.0",
        )
        self.get_response = GetResponse()
        self.set_response = SetResponse()
        # Sent after the initial SubscribeRequest, and again after each Poll
        self.subscribe_responses = []

    def _record(self, rpc, request, context):
        self.requests[rpc].append(request)
        self.metadata.append(dict(context.invocation_metadata()))
        if rpc in self.errors:
            code, details = self.errors[rpc]
            context.abort(code, details)

    def Capabilities(self, request, context):
        self._record("Capabilities", request, context)
        return self.capabilities_response

    def Get(self, request, context):
        self._record("Get", request, context)
        return self.get_response

    def Set(self, request, context):
        self._record("Set", request, context)
        return self.set_response

    def Subscribe(self, request_iterator, context):
        first = next(request_iterator)
        self._record("Subscribe", first, context)
        yield from self.subscribe_responses

        if first.subscribe.mode == SubscriptionList.ONCE:
            return

        # STREAM and POLL stay open until the client half-closes, which is what
        # a subscriber's close() does. Each Poll is answered with the same canned set.
        for request in request_iterator:
            self.requests["Subscribe"].append(request)
            if request.HasField("poll"):
                yield from self.subscribe_responses


class RunningTarget:
    """A FakeTarget served on a free localhost port, plaintext."""

    def __init__(self):
        self.target = FakeTarget()
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
        add_gNMIServicer_to_server(self.target, self.server)
        self.port = self.server.add_insecure_port("127.0.0.1:0")

    def __enter__(self):
        self.server.start()
        return self

    def __exit__(self, *exc):
        self.server.stop(grace=None)
