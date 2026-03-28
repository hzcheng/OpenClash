#!/usr/bin/env bash
set -euo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: ${name}" >&2
    exit 1
  fi
}

normalize_ui_path() {
  local path="${1:-/openclash/}"

  if [[ -z "${path}" ]]; then
    path="/openclash/"
  fi

  if [[ "${path}" != /* ]]; then
    path="/${path}"
  fi

  if [[ "${path}" != */ ]]; then
    path="${path}/"
  fi

  printf '%s\n' "${path}"
}

require_env OPENCLASH_SUBSCRIPTION_URL
require_env OPENCLASH_MIXED_PORT
require_env OPENCLASH_CONTROLLER_PORT
require_env OPENCLASH_LOG_LEVEL
require_env OPENCLASH_UI_DIR
require_env OPENCLASH_STATE_DIR

OPENCLASH_UI_PATH="$(normalize_ui_path "${OPENCLASH_UI_PATH:-/openclash/}")"
export OPENCLASH_UI_PATH

mkdir -p "${OPENCLASH_STATE_DIR}" "${OPENCLASH_UI_DIR}"

TMP_SUBSCRIPTION="$(mktemp)"
trap 'rm -f "${TMP_SUBSCRIPTION}"' EXIT

curl -fsSL "${OPENCLASH_SUBSCRIPTION_URL}" -o "${TMP_SUBSCRIPTION}"

python3 /usr/local/bin/render_openclash_config.py \
  --input "${TMP_SUBSCRIPTION}" \
  --output "${OPENCLASH_STATE_DIR}/config.yaml" \
  --mixed-port "${OPENCLASH_MIXED_PORT}" \
  --controller-port "${OPENCLASH_CONTROLLER_PORT}" \
  --ui-dir "${OPENCLASH_UI_DIR}" \
  --log-level "${OPENCLASH_LOG_LEVEL}"

exec mihomo -f "${OPENCLASH_STATE_DIR}/config.yaml"
