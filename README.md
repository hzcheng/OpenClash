# OpenClash Mihomo Gateway

This repository builds a custom `mihomo` image with the `metacubexd` dashboard and a bootstrap flow that renders a runtime `config.yaml` from your subscription URL plus deployment overrides.

## What This Deployment Does

- Runs `mihomo` on the internal machine only.
- Exposes the mixed proxy port only on host loopback.
- Publishes the dashboard through `NestGate` at `https://gate.teraai.cn/openclash/`.
- Rebuilds the runtime `config.yaml` from the subscription every time the container starts.

This means the proxy is intended for the internal host itself, while the dashboard is intended to be accessed through the gateway.

## Required `.env` Values

Set these in `.env` (see `.env.example` for defaults):

- `OPENCLASH_SUBSCRIPTION_URL`: Clash-compatible subscription URL.
- `OPENCLASH_MIXED_PORT`: Local mixed proxy port (host-loopback only).
- `OPENCLASH_CONTROLLER_PORT`: Controller/UI port (published for NestGate).
- `OPENCLASH_LOG_LEVEL`: Log level for `mihomo`.
- `OPENCLASH_UI_PATH`: Public dashboard path (keep `/openclash/`).
- `OPENCLASH_UI_DIR`: UI assets location inside the container.
- `OPENCLASH_STATE_DIR`: Runtime state directory inside the container.
- `OPENCLASH_AUTO_UPDATE_UI`: Documented no-op (UI assets are baked at build time).
- `OPENCLASH_BUILD_ALPINE_REPO`: Optional build-time Alpine mirror root, useful in mainland China.
- `OPENCLASH_BUILD_METACUBEXD_URL`: Optional build-time UI archive URL override.

Typical local values:

```dotenv
OPENCLASH_SUBSCRIPTION_URL=https://example.com/subscription.yaml
OPENCLASH_MIXED_PORT=9981
OPENCLASH_CONTROLLER_PORT=9097
OPENCLASH_LOG_LEVEL=warning
OPENCLASH_UI_PATH=/openclash/
OPENCLASH_UI_DIR=/root/.config/mihomo/ui
OPENCLASH_STATE_DIR=/root/.config/mihomo
OPENCLASH_AUTO_UPDATE_UI=false
```

## Local Proxy Usage

The mixed proxy port is bound to host loopback only. Use `127.0.0.1:${OPENCLASH_MIXED_PORT}` from the internal host to access the proxy.

Examples:

- HTTP proxy: `http://127.0.0.1:9981`
- HTTPS proxy: `http://127.0.0.1:9981`
- SOCKS-compatible client using mixed mode: `127.0.0.1:9981`

The proxy port is not intended to be reachable from LAN devices, from the cloud gateway, or from the public internet.

`mihomo` requires the external UI path to live under its safe home directory. The default state/UI paths therefore use `/root/.config/mihomo` inside the container.

## Public Dashboard

The dashboard is published through NestGate at:

- `https://gate.teraai.cn/openclash/`

Public behavior:

- `NestGate` redirects `/openclash/` to `/openclash/ui/`
- the route is protected by the existing gateway Basic Auth
- after passing gateway auth, `metacubexd` talks back to the controller through the same `/openclash/` public path

The controller root itself is API-oriented, so the UI entrypoint is `/openclash/ui/`.

## Startup

```bash
cd /Projects/Repos/OpenClash
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env build
docker compose --env-file .env up -d --remove-orphans
```

If you are building from mainland China and official upstreams are slow, you can override the two build-time source URLs in `.env` before running `docker compose build`.

## Day-To-Day Operations

### Refresh Subscription and Runtime Config

The generated `config.yaml` is recreated on container start. To pull the latest subscription and regenerate config:

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env restart
```

If you changed build-related files such as `Dockerfile`, `bootstrap-openclash.sh`, or baked UI behavior:

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env build
docker compose --env-file .env up -d --force-recreate --remove-orphans
```

### Inspect Runtime State

```bash
docker logs --tail 200 openclash
docker exec openclash sh -c 'sed -n "1,80p" /root/.config/mihomo/config.yaml'
docker exec openclash sh -c 'cat /root/.config/mihomo/ui/config.js'
```

### Stop or Start the Service

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env stop
docker compose --env-file .env start
```

## Verification

From the internal host:

```bash
docker compose --env-file .env ps
curl -sS -D - -o /tmp/openclash-ui.html http://127.0.0.1:${OPENCLASH_CONTROLLER_PORT}/ui/ | sed -n '1,20p'
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:${OPENCLASH_MIXED_PORT} || true
```

Expected:

- `openclash` container is `Up`
- `/${OPENCLASH_CONTROLLER_PORT}/ui/` returns `200`
- the proxy port is only reachable from the host itself

From another tailnet-reachable machine:

```bash
curl --noproxy '*' -sS -D - -o /tmp/openclash-tailnet-ui.html http://100.101.7.100:${OPENCLASH_CONTROLLER_PORT}/ui/ | sed -n '1,20p'
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' http://100.101.7.100:${OPENCLASH_MIXED_PORT} || true
```

Expected:

- controller/UI path returns `200`
- mixed proxy port does not answer on the tailnet address

From the public internet:

```bash
curl -k -I https://gate.teraai.cn/openclash/
curl -k -I https://gate.teraai.cn/openclash/ui/
```

Expected:

- `/openclash/` returns `302` to `/openclash/ui/`
- `/openclash/ui/` returns `401` until gateway auth is provided

## Mainland China Notes

This deployment includes two hardening choices for mainland network conditions:

- the image can build from a mirror via `OPENCLASH_BUILD_ALPINE_REPO`
- generated `mihomo` config pins `geox-url` to `testingcf.jsdelivr.net` so GEO/MMDB downloads do not stall on GitHub release endpoints

If startup logs show `Can't find MMDB, start download` for too long, check outbound connectivity first:

```bash
docker exec openclash sh -c 'curl -I --max-time 20 https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb'
```

## Troubleshooting

- If the container keeps restarting with a `SAFE_PATHS` error, verify `OPENCLASH_STATE_DIR` and `OPENCLASH_UI_DIR` are under `/root/.config/mihomo`.
- If the dashboard opens but cannot connect to the backend, verify `/root/.config/mihomo/ui/config.js` contains `defaultBackendURL: '/openclash/'`.
- If `/openclash/ui/` works on the tailnet but not publicly, check `NestGate` route rendering and gateway auth configuration.
- If the proxy works on the host but also appears reachable elsewhere, re-check the compose port binding for `OPENCLASH_MIXED_PORT`; it must stay on `127.0.0.1`.
- If a subscription update does not appear to take effect, restart or recreate the container so the bootstrap flow regenerates `config.yaml`.

## Key Files

- `docker-compose.yml`: runtime ports, restart policy, and state volume
- `Dockerfile`: custom image with `mihomo`, bootstrap tooling, and baked `metacubexd`
- `scripts/bootstrap-openclash.sh`: startup orchestration, UI sync, and config generation
- `scripts/render_openclash_config.py`: deployment-owned config overrides
- `.env.example`: deployment contract
- `README.md`: operational notes for this service
