#!/usr/bin/env bash
# Regenerate the bundled gNMI protobuf modules from an openconfig/gnmi release.
#
# Usage: scripts/regen_protos.sh v0.14.1
#
# Requires grpcio-tools in the active Python. Output goes to
# pygnmi/spec/v<gNMI specification version>, read from the gnmi_service option
# in gnmi.proto, so the directory names the specification and not the release
# it came from: v0.14.1 declares specification 0.10.0 -> pygnmi/spec/v0100.
#
# Two rewrites make the generated code importable from inside this package:
#   - gnmi.proto imports gnmi_ext.proto by its Go module path; it is rewritten
#     to a bare "gnmi_ext.proto" before generation, which also keeps the
#     descriptor file names ("gnmi.proto", "gnmi_ext.proto") the same as in the
#     older bundled specs.
#   - protoc emits top-level imports ("import gnmi_ext_pb2"); they are rewritten
#     to absolute imports under pygnmi.spec.<dir>.
set -euo pipefail

TAG="${1:?usage: $0 <openconfig/gnmi tag, e.g. v0.14.1>}"
PYTHON="${PYTHON:-python3}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="https://raw.githubusercontent.com/openconfig/gnmi/${TAG}/proto"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

curl -sfL "${BASE}/gnmi/gnmi.proto" -o "${WORK}/gnmi.proto"
curl -sfL "${BASE}/gnmi_ext/gnmi_ext.proto" -o "${WORK}/gnmi_ext.proto"

SPEC_VERSION="$(sed -n 's/^option (gnmi_service) = "\([0-9.]*\)";$/\1/p' "${WORK}/gnmi.proto")"
[[ -n "${SPEC_VERSION}" ]] || { echo "no gnmi_service option in gnmi.proto ${TAG}" >&2; exit 1; }
SPEC_DIR="v$(echo "${SPEC_VERSION}" | tr -d .)"
OUT="${REPO_ROOT}/pygnmi/spec/${SPEC_DIR}"
PKG="pygnmi.spec.${SPEC_DIR}"

sed -i.bak 's|import "github.com/openconfig/gnmi/proto/gnmi_ext/gnmi_ext.proto";|import "gnmi_ext.proto";|' \
  "${WORK}/gnmi.proto"
grep -q '^import "gnmi_ext.proto";' "${WORK}/gnmi.proto" \
  || { echo "gnmi_ext import not found in gnmi.proto ${TAG}" >&2; exit 1; }

WELL_KNOWN="$("${PYTHON}" -c 'import grpc_tools, os; print(os.path.join(os.path.dirname(grpc_tools.__file__), "_proto"))')"

mkdir -p "${OUT}"
"${PYTHON}" -m grpc_tools.protoc \
  -I "${WORK}" -I "${WELL_KNOWN}" \
  --python_out="${OUT}" --grpc_python_out="${OUT}" \
  "${WORK}/gnmi_ext.proto" "${WORK}/gnmi.proto"

# gnmi_ext_pb2 is not a gRPC service, so its _grpc module is an empty stub.
rm -f "${OUT}/gnmi_ext_pb2_grpc.py"

sed -i.bak "s|^import gnmi_ext_pb2 as|import ${PKG}.gnmi_ext_pb2 as|" "${OUT}/gnmi_pb2.py"
sed -i.bak "s|^import gnmi_pb2 as|import ${PKG}.gnmi_pb2 as|" "${OUT}/gnmi_pb2_grpc.py"
rm -f "${OUT}"/*.bak

grep -q "^import ${PKG}.gnmi_ext_pb2 as" "${OUT}/gnmi_pb2.py" \
  || { echo "import rewrite failed in gnmi_pb2.py" >&2; exit 1; }
grep -q "^import ${PKG}.gnmi_pb2 as" "${OUT}/gnmi_pb2_grpc.py" \
  || { echo "import rewrite failed in gnmi_pb2_grpc.py" >&2; exit 1; }

echo "generated ${OUT} (gNMI specification ${SPEC_VERSION}) from openconfig/gnmi ${TAG}"
