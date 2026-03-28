# OpenClash Mihomo Gateway

This repository builds a custom `mihomo` image with the `metacubexd` dashboard and a bootstrap flow that renders a runtime `config.yaml` from your subscription URL plus deployment overrides.

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

## Local Proxy Usage

The mixed proxy port is bound to host loopback only. Use `127.0.0.1:${OPENCLASH_MIXED_PORT}` from the host to access the proxy.

`mihomo` requires the external UI path to live under its safe home directory. The default state/UI paths therefore use `/root/.config/mihomo` inside the container.

## Public Dashboard

The dashboard is published through NestGate at `https://gate.teraai.cn/openclash/`.

## Startup

```bash
cd /Projects/Repos/OpenClash
cp .env.example .env
docker compose --env-file .env config
docker compose --env-file .env build
docker compose --env-file .env up -d --remove-orphans
```

If you are building from mainland China and official upstreams are slow, you can override the two build-time source URLs in `.env` before running `docker compose build`.

## Verification

```bash
docker compose --env-file .env ps
curl -sS -D - -o /tmp/openclash-controller.html http://127.0.0.1:${OPENCLASH_CONTROLLER_PORT}/ | sed -n '1,20p'
```
