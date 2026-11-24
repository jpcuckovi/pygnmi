#!/usr/bin/env bash
#
# The cEOS device lab for pygnmi's device tests, on a cluster running
# clabernetes.
#
# Commands:
#   up        apply tests/device/ceos-topology.yml, wait for the switch, generate
#             its gNMI TLS certificate, start the port-forward
#   test [ARGS]
#             run the device tests against it; ARGS go to pytest
#   status    pods and Topology state
#   cli       an interactive EOS CLI on the switch
#   down      stop the forward, delete the namespace and wait until it is gone
#
# Environment:
#   KUBE_CONTEXT  cluster identity, required. Never inferred from the current
#                 context: a lab applied to whatever happened to be selected is
#                 a lab applied somewhere unknown.
#   CEOS_IMAGE    cEOS image reference, required by `up`. cEOS is not publicly
#                 pullable, so this is site-specific and never committed.
#   TLS_PORT      local port forwarded to gNMI over TLS   (default: 16030)
#   PLAIN_PORT    local port forwarded to plaintext gNMI  (default: 16031)
#   PYTHON        interpreter with pygnmi and pytest      (default: python3)

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOPOLOGY="${repo_root}/tests/device/ceos-topology.yml"
STATE_DIR="${repo_root}/.device-lab"

LAB_NS=pygnmi-lab
LAB_NAME=pygnmi
NODE=ceos1
TLS_PORT="${TLS_PORT:-16030}"
PLAIN_PORT="${PLAIN_PORT:-16031}"
PY="${PYTHON:-python3}"

usage() { sed -n '3,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die() { echo "device-lab.sh: $*" >&2; exit 1; }

preflight() {
    [[ -n "${KUBE_CONTEXT:-}" ]] || die "set KUBE_CONTEXT to the cluster's kubeconfig context"
    command -v kubectl >/dev/null || die "kubectl not on PATH"
    kubectl config get-contexts "$KUBE_CONTEXT" >/dev/null 2>&1 \
        || die "no kubeconfig context named '$KUBE_CONTEXT'"
    KUBECTL=(kubectl --context "$KUBE_CONTEXT" --namespace "$LAB_NS")
}

# EOS CLI on the switch: into the launcher pod, then into the nested container.
eos() {
    "${KUBECTL[@]}" exec "deploy/${NODE}" -- docker exec "$NODE" Cli -p 15 -c "$1"
}

lab_forward() {
    mkdir -p "$STATE_DIR"
    local pidfile="${STATE_DIR}/forward.pid"
    if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        return
    fi
    # To the Service, so the launcher's internal port mapping does not matter.
    # localhost binds both 127.0.0.1 and ::1, and the tests use both.
    "${KUBECTL[@]}" port-forward "svc/${NODE}" \
        "${TLS_PORT}:6030" "${PLAIN_PORT}:6031" \
        >"${STATE_DIR}/forward.log" 2>&1 &
    echo $! >"$pidfile"
    # A check that races the forward reports a healthy switch as unreachable.
    sleep 3
    echo "  ${NODE} -> localhost:${TLS_PORT} (gNMI TLS), localhost:${PLAIN_PORT} (gNMI plaintext)"
}

lab_unforward() {
    local pidfile="${STATE_DIR}/forward.pid"
    if [[ -f "$pidfile" ]]; then
        kill "$(cat "$pidfile")" 2>/dev/null || true
        rm -f "$pidfile"
    fi
}

cmd="${1:-}"; shift || true

case "$cmd" in
up)
    preflight
    [[ -n "${CEOS_IMAGE:-}" ]] || die "set CEOS_IMAGE to the cEOS image reference"
    echo "==> namespace"
    "${KUBECTL[@]}" create namespace "$LAB_NS" --dry-run=client -o yaml \
        | kubectl --context "$KUBE_CONTEXT" apply -f - >/dev/null
    echo "==> topology"
    sed "s|__CEOS_IMAGE__|${CEOS_IMAGE}|" "$TOPOLOGY" | "${KUBECTL[@]}" apply -f -
    echo "==> waiting for the switch (cEOS is slow to boot)"
    "${KUBECTL[@]}" wait --for=condition=TopologyReady "topology/${LAB_NAME}" --timeout=900s \
        || die "not ready after 900s; see: ${0##*/} status"
    # Ready means the plaintext port answers, which EOS manages before it has
    # initialized; until then every Set fails with "system not yet initialized".
    echo "==> waiting for EOS to finish initializing"
    for _ in $(seq 60); do
        eos "show logging" 2>/dev/null | grep -q SYSTEM_INITIALIZED && break
        sleep 5
    done
    eos "show logging" | grep -q SYSTEM_INITIALIZED || die "EOS did not initialize within 300s"
    echo "==> TLS certificate"
    # Generated on the switch, so the private key never leaves it. The SAN
    # covers the port-forward's address and name; ::1 is deliberately absent so
    # the tests have an address the certificate does not name.
    eos "security pki certificate generate self-signed pygnmi.crt key pygnmi.key generate rsa 2048 validity 30 parameters common-name localhost subject-alternative-name ip 127.0.0.1 dns localhost"
    # Only now can the profile reference the certificate.
    eos $'configure\nmanagement security\nssl profile pygnmi\ncertificate pygnmi.crt key pygnmi.key\nexit\nexit\nmanagement api gnmi\ntransport grpc default\nssl profile pygnmi\nend'
    eos "show management api gnmi" | grep -q "running on port 6030" \
        || { eos "show management api gnmi" >&2; die "the TLS gNMI transport did not start"; }
    echo "==> forward"
    lab_forward
    ;;

test)
    preflight
    lab_forward
    cert="${STATE_DIR}/ceos1.pem"
    # The certificate the switch presents, fetched without trusting it. It is
    # self-signed, so it is also the CA the TLS tests verify against.
    "$PY" -I -c 'import ssl, sys; print(ssl.get_server_certificate(("127.0.0.1", int(sys.argv[1]))), end="")' \
        "$TLS_PORT" >"$cert"
    cd "$repo_root"
    PYGNMI_HOST=127.0.0.1 \
    PYGNMI_NAME=localhost \
    PYGNMI_FAKE_NAME=::1 \
    PYGNMI_PORT="$TLS_PORT" \
    PYGNMI_PLAIN_PORT="$PLAIN_PORT" \
    PYGNMI_USER=admin \
    PYGNMI_PASS=admin \
    PYGNMI_CERT="$cert" \
        "$PY" -m pytest "$@"
    ;;

status)
    preflight
    "${KUBECTL[@]}" get pods 2>/dev/null || true
    "${KUBECTL[@]}" get topology "$LAB_NAME" \
        -o jsonpath='{"state="}{.status.topologyState}{" ready="}{.status.readyNodeCount}{"/"}{.status.nodeCount}{"\n"}' \
        2>/dev/null || echo "no topology"
    ;;

cli)
    preflight
    "${KUBECTL[@]}" exec -it "deploy/${NODE}" -- docker exec -it "$NODE" Cli
    ;;

down)
    preflight
    lab_unforward
    # --wait: down is done when the namespace is gone, not when deletion starts.
    kubectl --context "$KUBE_CONTEXT" delete namespace "$LAB_NS" --ignore-not-found --wait=true --timeout=300s
    rm -rf "$STATE_DIR"
    echo "  ${LAB_NS} deleted"
    ;;

*)
    usage
    [[ -z "$cmd" ]] || exit 2
    ;;
esac
