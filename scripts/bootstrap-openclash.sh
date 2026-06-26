#!/bin/sh
set -eu

require_env() {
  local name="$1"
  eval "value=\${$name-}"
  if [ -z "${value}" ]; then
    echo "missing required environment variable: ${name}" >&2
    exit 1
  fi
}

normalize_ui_path() {
  local path="${1:-/openclash/}"

  if [ -z "${path}" ]; then
    path="/openclash/"
  fi

  case "${path}" in
    /*) ;;
    *) path="/${path}" ;;
  esac

  case "${path}" in
    */) ;;
    *) path="${path}/" ;;
  esac

  printf '%s\n' "${path}"
}

require_env OPENCLASH_MIXED_PORT
require_env OPENCLASH_CONTROLLER_PORT
require_env OPENCLASH_LOG_LEVEL
require_env OPENCLASH_UI_DIR
require_env OPENCLASH_STATE_DIR

OPENCLASH_CONFIG_SOURCE="${OPENCLASH_CONFIG_SOURCE:-subscription}"
OPENCLASH_UI_PATH="$(normalize_ui_path "${OPENCLASH_UI_PATH:-/openclash/}")"
export OPENCLASH_UI_PATH
OPENCLASH_BUNDLED_UI_SOURCE_DIR="${OPENCLASH_BUNDLED_UI_SOURCE_DIR:-/opt/metacubexd}"
OPENCLASH_RENDER_BIN="${OPENCLASH_RENDER_BIN:-/usr/local/bin/render_openclash_config.py}"

mkdir -p "${OPENCLASH_STATE_DIR}" "${OPENCLASH_UI_DIR}"

if [ -d "${OPENCLASH_BUNDLED_UI_SOURCE_DIR}" ]; then
  rsync -a --delete "${OPENCLASH_BUNDLED_UI_SOURCE_DIR}/" "${OPENCLASH_UI_DIR}/"
fi

if [ -f "${OPENCLASH_UI_DIR}/config.js" ]; then
  cat > "${OPENCLASH_UI_DIR}/config.js" <<EOF
window.__METACUBEXD_CONFIG__ = {
  defaultBackendURL: '${OPENCLASH_UI_PATH}',
}
EOF
fi

TMP_CONFIG="$(mktemp)"
trap 'rm -f "${TMP_CONFIG}"' EXIT

case "${OPENCLASH_CONFIG_SOURCE}" in
  subscription)
    require_env OPENCLASH_SUBSCRIPTION_URL
    curl -fsSL "${OPENCLASH_SUBSCRIPTION_URL}" -o "${TMP_CONFIG}"
    ;;
  file)
    require_env OPENCLASH_CONFIG_FILE
    if [ ! -f "${OPENCLASH_CONFIG_FILE}" ]; then
      echo "OPENCLASH_CONFIG_FILE does not exist: ${OPENCLASH_CONFIG_FILE}" >&2
      exit 1
    fi
    cp "${OPENCLASH_CONFIG_FILE}" "${TMP_CONFIG}"
    ;;
  *)
    echo "unsupported OPENCLASH_CONFIG_SOURCE: ${OPENCLASH_CONFIG_SOURCE}" >&2
    echo "expected one of: subscription, file" >&2
    exit 1
    ;;
esac

python3 "${OPENCLASH_RENDER_BIN}" \
  --input "${TMP_CONFIG}" \
  --output "${OPENCLASH_STATE_DIR}/config.yaml" \
  --mixed-port "${OPENCLASH_MIXED_PORT}" \
  --controller-port "${OPENCLASH_CONTROLLER_PORT}" \
  --ui-dir "${OPENCLASH_UI_DIR}" \
  --log-level "${OPENCLASH_LOG_LEVEL}"

if command -v mihomo >/dev/null 2>&1; then
  MIHOMO_BIN="$(command -v mihomo)"
elif [ -x /mihomo ]; then
  MIHOMO_BIN="/mihomo"
else
  echo "unable to locate mihomo binary" >&2
  exit 1
fi

exec "${MIHOMO_BIN}" -f "${OPENCLASH_STATE_DIR}/config.yaml"
