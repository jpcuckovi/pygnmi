==========================
pyGNMI: Python gNMI client
==========================

.. image:: logo.png
   :width: 300
   :height: 300
   :alt: pyGNMI logo
   :align: center

|ci|_ |license|_

This repository contains pure Python implementation of the gNMI client to interact with the network functions.

===============
About this fork
===============

This is a maintained fork of `akarneliuk/pygnmi <https://github.com/akarneliuk/pygnmi>`_, which has had no release since 0.8.15 in March 2025. It is not affiliated with the original project, whose BSD 3-Clause license and copyright notices are retained. The logo is the original project's.

Since the original project, the fork has added:

- The bundled spec rebuilt for gNMI ``0.10.0`` (release 0.9.0), with ``scripts/regen_protos.sh`` to regenerate it from any ``openconfig/gnmi`` release.
- The `Commit Confirmed Extension <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-commit-confirmed.md>`_ for ``set()`` (release 0.9.0).
- ``union_replace`` for ``set()`` (unreleased, 0.10.0), the gNMI ``0.10.0`` operation that replaces the union of several paths in one transaction.
- A test suite that runs without a network device, against an in-process gNMI target, in CI on every supported Python version.

The Dev Log below has the details of each release.

Installation
------------

The fork is not on PyPI; the ``pygnmi`` package there is the original project. Install the fork from GitHub, pinned to a release tag:

.. code-block:: bash

  pip install "pygnmi @ git+https://github.com/jpcuckovi/pygnmi@v0.9.0"

The import name is unchanged, so existing code works as before:

.. code-block:: python3

  from pygnmi.client import gNMIclient

Installing the fork replaces the original ``pygnmi`` package if it is already installed.

Status
------

The latest release is 0.9.0. The ``master`` branch holds 0.10.0, which is not released yet. Its distribution name is ``pygnmi-ng``, so installing ``master`` from GitHub needs ``"pygnmi-ng @ git+https://github.com/jpcuckovi/pygnmi"``.

Tested Network Operating Systems (NOS)
--------------------------------------

The fork has been validated against:

- Arista cEOS 4.36.2F (``master``, 0.10.0): 35 of the 38 device tests pass, including union_replace, commit confirmed (confirm, rollback on timeout, cancel), leaf-list decoding, TLS with certificate download, and plaintext channels. The three failures are the target's, not the client's: two tests use a YANG module name as the path origin (``openconfig-interfaces:...``), which this EOS release rejects in favour of ``openconfig:``, and one reads ``Management1``, which cEOS names ``Management0``. ``test_08`` (cipher change) was written for Nokia SR OS and does not exercise anything on EOS.
- Nokia SR Linux 26.7.2 (release 0.9.0, including commit confirmed)

The original project reported testing on Arista EOS, Nokia SR OS, Cisco IOS XR, Juniper JUNOS, Nokia SR Linux and Cisco NX-OS, with Broadcom SONiC in progress. Those results predate the fork and have not been repeated with it.

=====
Usage
=====
Sample code example:

.. code-block:: python3

  from pygnmi.client import gNMIclient

  host = ("192.0.2.1", "57400")

  if __name__ == "__main__":
      with gNMIclient(target=host, username="admin", password="admin", insecure=True) as gc:
          result = gc.get(path=["openconfig-interfaces:interfaces", "openconfig-acl:acl"])

      print(result)

Also integration with Nornir is supported (`refer to examples <examples/nornir>`_).

Commit confirmed
----------------

``set()`` takes the `Commit Confirmed Extension <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-commit-confirmed.md>`_ as ``extension={"commit": {...}}``, with an ``id`` and exactly one action. The target rolls the change back unless it is confirmed within the rollback duration:

.. code-block:: python3

  gc.set(
      update=[("/system/config", {"hostname": "leaf1"})],
      extension={"commit": {"id": "change-42", "commit": {"rollback_duration": 300}}},
  )

  gc.set(extension={"commit": {"id": "change-42", "confirm": {}}})

``cancel`` rolls the change back at once, and ``set_rollback_duration`` changes the duration of a pending commit. The rollback duration is seconds as ``int`` or ``float``, or a ``datetime.timedelta``.

Union replace
-------------

``union_replace`` (unreleased, 0.10.0) takes the same list of tuples as ``replace``. It is meant to carry a device's complete configuration, and a target may replace everything it holds with exactly what is sent. On Arista EOS, which needs ``operation set namespace`` under ``management api gnmi`` before it accepts union_replace, a fragment removes the rest of the configuration, users and gNMI transports included. Send the whole configuration, for example the running config through the CLI origin with the intended change applied:

.. code-block:: python3

  running = gc.get(path=["cli:show running-config"], encoding="ascii")["notification"][0]["update"][0]["val"]
  gc.set(union_replace=[("cli://", updated_config)], encoding="ascii")

``set()`` applies one encoding to every value in a request, so a single union_replace cannot yet mix OpenConfig JSON and CLI text.

Video tutorial
--------------
The original project's author explains how to use pyGNMI `on YouTube <https://www.youtube.com/watch?v=NooE_uHIgys&list=PLsTgo2tBPnTwmeP9zsd8B_tZR-kbguvla>`_. The videos predate the fork.


All gNMI RPCs supported
-----------------------
- Capabilities
- Get
- Set
- Subscribe

Supported operation modes
-------------------------
- insecure gRPC channel (without encryption)
- secure gRPC channel (with encryption and authentication based on certificate)

=======
License
=======
By using the pyGNMI tool you agree with `the license <LICENSE.txt>`_.

============
Contributors
============

- `Anton Karneliuk <https://github.com/akarneliuk>`_
- `Stefan Lieberth <https://github.com/slieberth>`_
- `Prem Anand Haridoss <https://github.com/hprem>`_
- `Andrew Southard <https://github.com/andsouth44>`_
- `Jeroen van Bemme <https://github.com/jbemmel>`_
- `Frédéric Perrin <https://github.com/fperrin>`_
- `Malanovo <https://github.com/malanovo>`_
- `Sebastian Lohff <https://github.com/sebageek>`_

=======
Dev Log
=======

Release **0.10.0** (unreleased, on ``master``; validated against Arista cEOS 4.36.2F):

- Packaging moved from ``setup.py`` to ``pyproject.toml``, and the distribution is renamed ``pygnmi-ng`` to tell it apart from the original project. The import name is still ``pygnmi``.
- Added ``union_replace`` to ``set()`` and ``set_with_retry()``, with the same list-of-tuples format as ``replace``, and ``set-union_replace`` to ``pygnmicli``. A ``SetResponse`` operation of ``UNION_REPLACE`` is now reported as such instead of ``UNDEFINED``.
- **Behaviour change**: the library no longer prints its log records to stdout. It adds only a ``logging.NullHandler``, so output is up to the application, for example ``logging.basicConfig(level=logging.INFO)``. ``pygnmicli`` configures logging itself and is unaffected.
- ``set_with_retry()`` now accepts ``prefix``, ``target`` and ``extension`` (including commit confirmed), which it previously could not pass on, and uses them on both attempts. Its retry warning now shows the delay.
- Fixed streamed telemetry updates with a timestamp of ``0`` being parsed as ``None``.
- Fixed leaf-list values (``leaflist_val``) of scalars such as strings: ``get()`` raised and telemetry parsed them as ``None``. They are now a list of decoded values, for example ``["a.example", "b.example"]``. A leaf-list whose elements are all JSON objects keeps its earlier shape, the objects merged into one dict.
- Fixed ``connect()`` raising ``TypeError`` when ``capabilities()`` fails for a reason other than a gRPC error. It now keeps the default encoding and logs a warning.
- ``subscribe()`` raises ``ValueError`` for a non-boolean ``poll`` and ``gNMIException`` when given neither ``subscribe`` nor ``poll``, instead of failing with ``UnboundLocalError``.
- Insecure channels no longer pass the username and password as gRPC channel options. They are sent only as call metadata, as on secure channels.
- gRPC errors are caught through the public ``grpc.RpcError`` instead of grpcio's private classes, which change between grpcio releases.
- Fixed the legacy ``subscribe()`` ending every stream with ``DEADLINE_EXCEEDED``: its default ``timeout`` of ``0.0`` was passed to gRPC as a deadline that had already passed. It now means no deadline.
- Tests run without a device against an in-process gNMI target. The device tests still run when ``PYGNMI_HOST`` and the other ``PYGNMI_*`` variables are set, and skip otherwise. Their paths now use the ``openconfig`` origin, which current Arista EOS requires.
- Added device tests for the 0.10.0 changes (``tests/test_12_device_0_10.py``) and ``scripts/device-lab.sh``, which runs the whole device suite against a one-switch Arista cEOS lab on a Kubernetes cluster with clabernetes.
- Removed the unused gNMI ``0.7.0`` and ``0.8.0`` spec modules and the build artefacts that were committed to the repository.

Release **0.9.0**:

- **Important**: potentially breaking change. Spec is rebuilt and updated to support gNMI of version ``0.10.0``, generated from `openconfig/gnmi v0.14.1 <https://github.com/openconfig/gnmi/tree/v0.14.1/proto>`_. The generated code requires ``protobuf>=7.35.1,<8`` and ``grpcio>=1.84.0``, and therefore Python 3.10 or later.
- Added ``scripts/regen_protos.sh`` to regenerate the bundled spec from an ``openconfig/gnmi`` release.
- Implemented `Commit Confirmed Extension <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-commit-confirmed.md>`_ for ``set()``. Pass ``extension={"commit": {"id": "c1", "commit": {"rollback_duration": 60}}}`` to start a commit, then ``confirm``, ``cancel`` or ``set_rollback_duration`` with the same ``id``. Rollback duration is seconds as ``int`` or ``float``, or a ``datetime.timedelta``.
- Deprecated aliases, which are removed from the gNMI specification. ``use_aliases: False`` in a subscription is ignored with a ``DeprecationWarning``; ``use_aliases: True`` and the ``aliases`` argument of ``subscribe()`` raise ``ValueError``. The ``alias`` key of a notification is always ``None``.
- Moved ``setup.py`` from ``distutils``, which is removed in Python 3.12, to ``setuptools``.

Release **0.8.15**:

- IPv6 support: `Issue 166 <https://github.com/akarneliuk/pygnmi/pull/166>`_.
- Double support: `Issue 165 <https://github.com/akarneliuk/pygnmi/pull/165>`_.

Release **0.8.14**:

- Number of minor bug fixes and improvements.
- Adding support of `prefix` to `pygnmicli`.
- `Adding error propagation from child thread to main thread <https://github.com/akarneliuk/pygnmi/pull/142>`_
- `Changes to u_val <https://github.com/akarneliuk/pygnmi/pull/144>`_
- `Adding Master Arbitration support for Set <https://github.com/akarneliuk/pygnmi/pull/146>`_
- `Adding bytes_val and leaflist_val with string_val parsing <https://github.com/akarneliuk/pygnmi/pull/151>`_

Release **0.8.13**:

- Number of minor bug fixes and improvements.

Release **0.8.12**:

- Fixed operation of `no_qos_marking` flag for `pygnmicli`.

Release **0.8.11**:

- Previous release introduced break for telemetry in `Juniper` due to inconsistency of communicated encoudings in `Capabilities()` and what is really supported in `Subscribe()`.

Release **0.8.10**:

- Automatic detection of supported encoding and using it where applicable (e.g., in `subscribe2` method).
- Possibility to remove `qos` from `Subscribe` for platforms, which doesn't support it (e.g., `Juniper`).

Release **0.8.9**:

- Default value for ``encoding`` everywhere is set to ``None``.
- Method ``capabilities()`` now is called as part of ``connect()`` to collect supported encoding as part of session establishing.
- If ``encoding`` is not specified by user, then it is auto-set based on the list collected via ``capabilites()`` with ``json`` having the first priority follwed by ``json_ietf``.

Release **0.8.8**:

- Added new argument ``-e / --encoding`` to ``pygnmicli`` to specify the encoding, which overrides the default one. Fix for `Issue 58 <https://github.com/akarneliuk/pygnmi/issues/58>`_.
- Fixed minor bug with encoding handling inside ``get()`` and ``subscribe2()`` methods.
- Simplified the code.

Release **0.8.7**:

- Fixed bug, when returned ``json_val`` or ``json_ietf_val`` is not processed correctly if the value is empty string.  Fix for `Issue 58 <https://github.com/akarneliuk/pygnmi/issues/58>`_.

Release **0.8.6**:

- Fixed minor issue with establishing ``insecure`` channel.
- Fixed bug with inabillity to specify ``prefix`` in Subscribe messages for ``subscribe2()`` method.
- **Important**: It is recommended to use method ``subscribe2()`` instead of ``subscribe()`` for building telemetry collectors with ``pygnmi`` as this method is further developed and throroughle tested. The method ``subscribe()`` will be deprecated in future releases.
- Functionality ``qos`` is now properly supported in ``subscribe2()`` method.

Release **0.8.5**:

- Fixed some issues with telemetry representation with ``pygnmicli``.

Release **0.8.4**:

- Change logic of setting default values for some parameters to improve user experience.
- Added ``token`` authentication to ``pygnmicli``.

Release **0.8.3**:

- Changed behaviour of ``subscribe2()`` to RPC to avoid adding the empty ``Extension`` field for no extensions presenting. Fix for `Issue 83 <https://github.com/akarneliuk/pygnmi/issues/83>`_.
- Uppdated documentation with examples in GitHub.
- Added support of History extensions to ``pygnmicli``.

Release **0.8.2**:

- Implemented `History Extension <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-history.md#1-purpose>`_.
- Implemented handling of corner case, where ``--skip-verify`` was failing trying to parse certificate, `which doesn't have CN and SARs <https://github.com/akarneliuk/pygnmi/issues/71>`_.

Release **0.8.1**:

- Removed the need for ``--no-binary=protobuf`` for operation.

Release **0.8.0**:

- **Important**: potentially breaking change. The dependency is moved from ``grpcio-tools`` to ``protobuf``, which as a standalone package has a much newer serion.
- Spec is rebuilt and updated to support gNMI of version ``0.8.0``.

Release **0.7.5**:

- Amended the logic of ``ONCE`` telemetry mode to automatically terminate on receiving ``{"sync_response": True}`` message.

Release **0.7.4**:

- Feature ``skip_verify`` is now stabilised and doesn't require subject alternative names any more.

Release **0.7.3**:

- Amended the logic of ``target`` functionality to be more inline with gNMI Reference.

Release **0.7.2**:

- Minor bug fixing in the ``skip_verify`` logic. **Impotant**: for this feature to work, you need at least one subject alternative name filed (DNS, IP address, email, - any will work). It also doesn't matter which value it has, but at least one item shall present.

Release **0.7.1**:

- Added new argument ``skip_verify`` to ``gNMIclient``, which removes a need to set the ``override`` argument manually. However, the latter one still stays for the backward compatibility.
- Changed default values for arguments ``username`` and ``password`` from ``None`` to ``""``, as with token-based authentication they don't need to be specified.
- Added new argument ``target`` to ``gNMIclient.get()``, ``gNMIclient.set()``, and ``gNMIclient.subscribe2()`` methods. If provided, it adds ``target`` key to ``Path()`` per `GNMI Specification 2.2.2.1 <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md#2221-path-target>`_.

Release **0.7.0**:

- Added authentication with Token using ``Authorization: Bearer TOKEN``, where ``TOKEN`` is a variable provided as ``gNMIclient(token=TOKEN)`` key (needed for Arista CVP).
- Added functionality to change  ``GRPC_SSL_CIPHER_SUITES`` dynamically to ``HIGH`` value (needed for Nokia SR OS).

Release **0.6.9**:

- Adding new documentation for mutual TLS feature.

Release **0.6.8**:

- Minor bug-fixing.

Release **0.6.7**:

- Added new ``show_diff`` key to ``gNMIclient`` object (supported values ``print`` and ``get``). When applied, it shows the changes happened to all keys following XPath from all arguments to ``Set()`` RPC at the network devices. It is so fair tailored to OpenConfig YANG modules as it uses some architectural principles of OpenConfig YANG module to re-construct XPath.
- Added an optional timeout to ``connect()`` method.
- Minor bug-fixing.

Release **0.6.6**:

- Minor bug-fixing.

Release **0.6.5**:

- Implemented ``prefix`` and ``timestamp`` in ``SetResponse`` message.
- Implemented ``alias`` and ``atomic`` in ``Notification`` message.
- Minor bug-fixing.

Release **0.6.4**:

- Minor bug-fixing.

Release **0.6.3**:

- Implemented ``prefix`` key in the ``Update`` message.
- Added possibility to provide password in STDIN rather than key.
- Minor bug-fixing.

Release **0.6.2**:

- Added support of keepalive timer for gRPC session to prevent automatic closure each 2 hours.
- Fixed issue with ``Subscribe`` RPC not sending delete notification in case of a path is removed from the node.
- Added the CLI based tool.
- Minor bug-fixing.

Release **0.6.1**:

- Added support of origin per RFC7951.
- Added timeout to the initial setup useful for long-living connections.
- Minor bug-fixing.

Release **0.6.0**:

- Significant improvements in telemetry capabilities of the pygnmi. Now you can use ``subscribe2`` method by simply providing the a corredponding dictionary at input and all modes (STREA, ONCE, POLL) are working correctly.
- Function ``telemetryParser`` is now automatically used inside ``subscribe2``.
- Telemetry is now implemeted using ``threading``.
- Added new unit tests with ``pytest`` and added code coverage with ``coverage.py``.

Release **0.5.3**:

- Minor improvements and bug fixing.
- Full coverage of unit tests for all operations (Capabilities, Get, Set(Update, Replace, Delete), Subscribe) and all notations of GNMI Path.

Release **0.5.2**:

- Minor bug fixing.
- First release with unit tests.

Release **0.5.1**:

- Added example for non-blocking iterator for telemetry.
- Added the extra support for Juniper TLS certificates.
- Fixed regexp warnings.
- Changed the logging functionality.
- Enabled Unix domain socket.
- Added ``close()``
- Many thanks for all contributors to make this release happen.

Release **0.5.0**:

- Added possibility to extract certificate from the destination network function.

Release **0.4.8**:

- Added documentation in module regading supported the different paths naming conventions. Supported options: ``yang-module:container/container[key=value]``, ``/yang-module:container/container[key=value]``, ``/yang-module:/container/container[key=value]``, ``/container/container[key=value]``

Release **0.4.6**:

- Fixed `gNMI Path issue <https://github.com/akarneliuk/pygnmi/issues/13>`_.

Release **0.4.6**:

- Replaced the ``sys.exit`` with raising exceptions.
- Minor bug fix.
- Brought the gNMI path to the canonical format: ``/origin:element1/element2...``.
- Added possibility to omit the YANG module name, as some vendors doesn't include that in the request per their gNMI implementation: ``/element1/element2...``.

Release **0.4.5**:

- Minor bug fix.

Release **0.4.4**:

- Minor bug fix.

Release **0.4.3**:

- Added possibility to modify the timeout (default value is 5 seconds) for the session using ``gnmi_timeout`` key for ``gNMIclient`` class.

Release **0.4.2**:

- Modified the path generation to comply with `gNMI Path encoding conventions <https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-path-conventions.md>`_.
- Fixed the problem ``debug`` output, where the requests where not printed in case of response failing.

Release **0.4.1**:

- Minor bug fix.

Release **0.4.0**:

- Added support for Juniper JUNOS
- Fixed the issue with ``override`` for PKI-based certificates

Release **0.3.12**:

- Minor bug fix.

Release **0.3.11**:

- Minor bug fix.

Release **0.3.10**:

- Renamed the debug mode. Add argument ``debug=True`` upon object creation to see the Protobuf messages.

Release **0.3.9**:

- Added functionality to list the full the device configuration in case the path is empty: ``get(path[])``.

Release **0.3.8**:

- Merged the proposal how to implement TLS with override for Cisco IOS XR (tested for Cisco IOS XR, to be tested for other vendors yet)
- Merged examples with TLS

Release **0.3.7**:

- Added the argument ``encoding`` as an extra key to ``Set`` operation

Release **0.3.6**:

- Added the argument ``encoding`` to ``Get`` operation

Release **0.3.5**:

- Added the example for Nornir Integration
- Added the topology diagram
- Added links to the video tutorial

Release **0.3.4**:

- Added the ``close`` method to ``gNMIClient`` class for those, who doesn't use ``with ... as ...`` context manager.

Release **0.3.3**:

- Added the functionality to pass gRPC messages to the code execution

Release **0.3.2**:

- Minor bugs fixed.

Release **0.3.1**:

- Minor bugs fixed.
- Added examples of gNMI operations.

Release **0.3.0**:

- Added new function ``telemetryParser``, which converts Protobuf messages in Python dictionary.
- Fixed the errors with the telemetry parsing.

Release **0.2.7**:

- Modified core so that telemetry is working in ``once`` and ``stream`` mode.

Release **0.2.6**:

- Added alpha version of the ``Subscribe`` operation.

Release **0.2.5**:

- Added typing hints.

Release **0.2.4**:

- Minor bugfixing.

Release **0.2.3**:

- Added support for IPv6 transport (now you can connect to the network function over IPv6).

Release **0.2.2**:

- Added conversion of the collected information over the gNMI into a Python dictionary for Set operation.

Release **0.2.1**:

- Fixing the bugs with improper Protobuf paths generation.
- Now all ``Set`` operations (``delete``, ``replace``, and ``update``) are working properly.

Releast **0.2.0**:

- Added the ``Set`` operation from gNMI specification.

Releast **0.1.9**:

- Added the property ``datatype='all'`` to the get() request. The values are per the gNMI specification: all, config, state, operatonal.

Release **0.1.8**:

- Added conversion of the collected information over the gNMI into a Python dictionary for Get operation.

Release **0.1.7**:

- Changing packages modules.

Release **0.1.6**:

- Restructuring internal context.

Release **0.1.5**:

- Minor bugfixing.

Release **0.1.4**:

- Minor bugfixing.

Release **0.1.3**:

- Minor bugfixing.

Release **0.1.2**:

- The gNMIClient is recreated as context manger.
- Tests with Nokia SR OS done, the module is working nice for insecure channel.

Release **0.1.1**:

- Added the ``Get`` operation out of gNMI specification.

Release **0.1.0**:

- The first release.

(c)2020-2022, karneliuk.com

.. |ci| image:: https://github.com/jpcuckovi/pygnmi/actions/workflows/ci.yaml/badge.svg?branch=master
.. _ci: https://github.com/jpcuckovi/pygnmi/actions/workflows/ci.yaml
.. |license| image:: https://img.shields.io/static/v1?label=license&message=BSD-3-clause&color=success
.. _license: https://github.com/jpcuckovi/pygnmi/blob/master/LICENSE.txt
