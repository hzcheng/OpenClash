#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
STATE_DIR="${TMP_DIR}/state"
UI_DIR="${TMP_DIR}/ui"
BUNDLED_UI_DIR="${TMP_DIR}/bundled-ui"
FAKE_BIN="${TMP_DIR}/bin"
MIHOMO_LOG="${TMP_DIR}/mihomo-invocation.log"
RENDER_BIN="/usr/local/bin/render_openclash_config.py"
RENDER_BACKUP="${TMP_DIR}/render_openclash_config.py.bak"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -f "${RENDER_BACKUP}" ]]; then
    mv "${RENDER_BACKUP}" "${RENDER_BIN}"
  else
    rm -f "${RENDER_BIN}"
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${STATE_DIR}" "${UI_DIR}" "${BUNDLED_UI_DIR}" "${FAKE_BIN}"

cat > "${BUNDLED_UI_DIR}/config.js" <<'EOF'
window.__METACUBEXD_CONFIG__ = {
  defaultBackendURL: '',
}
EOF

cat > "${FAKE_BIN}/mihomo" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "mihomo $*" >> "${MIHOMO_INVOCATION_LOG:?}"
exit 0
EOF
chmod +x "${FAKE_BIN}/mihomo"

if [[ -f "${RENDER_BIN}" ]]; then
  cp "${RENDER_BIN}" "${RENDER_BACKUP}"
fi
cp "${ROOT_DIR}/scripts/render_openclash_config.py" "${RENDER_BIN}"

PORT="$(python3 - <<'PY'
import socket

sock = socket.socket()
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
)"

python3 -m http.server "${PORT}" --bind 127.0.0.1 --directory "${ROOT_DIR}/tests/fixtures" >/dev/null 2>&1 &
SERVER_PID=$!

for _ in {1..25}; do
  if curl -fsS "http://127.0.0.1:${PORT}/subscription-base.yaml" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

export OPENCLASH_SUBSCRIPTION_URL="http://127.0.0.1:${PORT}/subscription-base.yaml"
export OPENCLASH_MIXED_PORT=9981
export OPENCLASH_CONTROLLER_PORT=9097
export OPENCLASH_LOG_LEVEL=warning
export OPENCLASH_UI_PATH=/openclash
export OPENCLASH_UI_DIR="${UI_DIR}"
export OPENCLASH_STATE_DIR="${STATE_DIR}"
export OPENCLASH_BUNDLED_UI_SOURCE_DIR="${BUNDLED_UI_DIR}"
export MIHOMO_INVOCATION_LOG="${MIHOMO_LOG}"
export PATH="${FAKE_BIN}:${PATH}"

bash "${ROOT_DIR}/scripts/bootstrap-openclash.sh"

test -f "${STATE_DIR}/config.yaml"
grep -q '^allow-lan: true$' "${STATE_DIR}/config.yaml"
grep -Eq "^bind-address: ('\\*'|\\*)$" "${STATE_DIR}/config.yaml"
grep -q '^mixed-port: 9981$' "${STATE_DIR}/config.yaml"
grep -q "defaultBackendURL: '/openclash/'" "${UI_DIR}/config.js"
grep -q "mihomo -f ${STATE_DIR}/config.yaml" "${MIHOMO_LOG}"
grep -q '^- RULE-SET,openai,OpenAI$' "${STATE_DIR}/config.yaml"
grep -q 'name: OpenAI' "${STATE_DIR}/config.yaml"
grep -q 'type: url-test' "${STATE_DIR}/config.yaml"
