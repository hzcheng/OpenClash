# OpenClash Mihomo Gateway Design

## Goal

Build an `OpenClash` deployment that:

- runs the proxy core only on the internal host
- exposes the proxy port only to the host itself, not to LAN or public internet
- exposes the monitoring/configuration dashboard publicly through `NestGate`
- generates the final `mihomo` runtime configuration at container startup from a Clash-compatible subscription URL plus local environment overrides

Public dashboard URL target:

- `https://gate.teraai.cn/openclash/`

Deployment topology target:

- `OpenClash` runs on the internal machine
- `NestGate` runs on the cloud host
- `NestGate` reverse-proxies dashboard traffic to the internal machine over the tailnet
- the proxy mixed port remains host-local only

## Non-Goals

This design does not include:

- exposing proxy ports through `NestGate`
- allowing LAN devices to use the proxy
- adding a second independent dashboard stack
- building a generic subscription conversion service
- persisting generated config through host bind mounts from the dev container

## Chosen Approach

Use:

- `mihomo` as the proxy core
- `metacubexd` as the dashboard UI
- a custom image that embeds:
  - `mihomo`
  - the UI assets
  - a bootstrap script
  - the small runtime tools needed to fetch and rewrite the subscription YAML

The container startup flow will:

1. read runtime values from `.env`
2. fetch the Clash/Mihomo subscription URL
3. validate that the subscription payload is usable Clash YAML
4. merge in required local overrides for ports, controller, UI path, and logging
5. write the final `config.yaml` inside the container-managed state directory
6. start `mihomo` with that generated config

## Why This Approach

This design fits the current environment constraints:

- the development environment is itself a container and should not depend on fragile host bind-mount paths for generated runtime config
- the OpenClaw work in this session already proved that single-file bind mounts can become unreliable in this topology
- embedding bootstrap logic into the image keeps the deployment reproducible and self-contained
- using a Docker named volume for state is compatible with the current environment while avoiding host path assumptions

`metacubexd` is preferred over classic `yacd` because it is the better fit for the current `mihomo` ecosystem and gives a more current operational UI.

## Repository Structure

The `OpenClash` repository should gain a minimal but explicit deployment layout:

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `README.md`
- `scripts/bootstrap-openclash.sh`
- `scripts/render-openclash-config.py`
- optional helper scripts for local verification

No host bind-mounted generated config file should be required for normal startup.

## Runtime Configuration Model

### Environment Variables

The deployment should be driven by a small, high-signal set of environment variables:

- `OPENCLASH_SUBSCRIPTION_URL`
- `OPENCLASH_MIXED_PORT`
- `OPENCLASH_CONTROLLER_PORT`
- `OPENCLASH_LOG_LEVEL`
- `OPENCLASH_UI_PATH`
- `OPENCLASH_UI_DIR`
- `OPENCLASH_STATE_DIR`
- optional UI update control such as `OPENCLASH_AUTO_UPDATE_UI`

Recommended defaults:

- `OPENCLASH_UI_PATH=/openclash/`
- `OPENCLASH_MIXED_PORT=9981`
- `OPENCLASH_CONTROLLER_PORT=9097`
- `OPENCLASH_LOG_LEVEL=warning`
- `OPENCLASH_UI_DIR=/var/lib/openclash/ui`
- `OPENCLASH_STATE_DIR=/var/lib/openclash`

### Subscription Input

The provided subscription URL is already Clash-compatible YAML and should be treated as the base config input, not as a generic provider format needing an external conversion service.

### Config Merge Rules

Preserve subscription-owned behavior:

- `proxies`
- `proxy-groups`
- `rules`
- subscription-provided DNS and related policy content unless explicitly overridden for deployment safety

Force deployment-owned behavior:

- `mixed-port: ${OPENCLASH_MIXED_PORT}`
- `allow-lan: false`
- `external-controller: 0.0.0.0:${OPENCLASH_CONTROLLER_PORT}`
- `external-ui: ${OPENCLASH_UI_DIR}`
- `log-level: ${OPENCLASH_LOG_LEVEL}`

Set defaults only when absent:

- `mode`
- `ipv6`
- minimal `profile` or similar low-risk runtime defaults

Deployment-owned fields must not be allowed to drift based on subscription content.

## Container Design

### Image

The custom image should include:

- `mihomo` binary or official base image runtime
- `metacubexd` static UI assets
- the bootstrap and config-rendering scripts
- a YAML-capable toolchain, preferably Python with `PyYAML`, or an equally simple parser approach

### Startup Flow

Container command should run the bootstrap script, which must:

1. validate required env vars
2. create the container-internal state directory
3. fetch the subscription YAML
4. render the final config into `${OPENCLASH_STATE_DIR}/config.yaml`
5. start `mihomo -f ${OPENCLASH_STATE_DIR}/config.yaml`

### Persistence

Use a Docker named volume mounted to the container state directory.

This volume may hold:

- rendered config
- UI assets cache if needed
- runtime state generated by `mihomo`

Do not rely on host bind mounts for generated config in the normal deployment path.

## Compose Design

Use a single primary service:

- service name: `openclash`

Port exposure model:

- proxy mixed port bound to host loopback only:
  - `127.0.0.1:${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}`
- controller/dashboard port bound to host network interface reachable from `NestGate` over the tailnet:
  - `${OPENCLASH_CONTROLLER_PORT}:${OPENCLASH_CONTROLLER_PORT}`

This means:

- the host machine itself can use the proxy on `127.0.0.1:${OPENCLASH_MIXED_PORT}`
- the dashboard/controller is reachable from `NestGate`
- the proxy port is not reachable from LAN devices unless the host deliberately forwards it

## Dashboard Publishing Through NestGate

`NestGate` should publish a new service at:

- path: `/openclash`
- upstream: `http://100.101.7.100:${OPENCLASH_CONTROLLER_PORT}`

Initial proxy strategy:

- `websocket: true`
- keep the dashboard public entrypoint at `https://gate.teraai.cn/openclash/`

Path handling strategy:

- first preference: let the dashboard/controller stack work cleanly under `/openclash/`
- fallback: if `metacubexd` subpath behavior proves unreliable, allow `NestGate` to strip the prefix instead of forcing subpath-native UI behavior

The implementation must verify this behavior empirically before finalizing the proxy rule.

## Authentication Model

Authentication for public dashboard access should rely on the existing `NestGate` gateway auth.

This rollout should not add a second public-facing auth UX for the dashboard.

That said, the internal controller should still be treated as an internal service and not intentionally exposed beyond the tailnet-reachable path required by `NestGate`.

## Verification Requirements

### Local Validation

Before claiming success, verify:

- `docker compose config` renders successfully
- container starts successfully
- `mihomo` process stays up
- host-local proxy endpoint is reachable on `127.0.0.1:${OPENCLASH_MIXED_PORT}`
- controller endpoint is reachable on `${OPENCLASH_CONTROLLER_PORT}`

### Gateway Validation

Before cloud rollout, verify:

- local `NestGate` config tests pass
- generated `nginx` config includes the `/openclash` route

### Public Validation

After cloud rollout, verify:

- `https://gate.teraai.cn/openclash/` returns success
- dashboard static assets also return success
- `NestGate` logs do not show new `502` or `504` errors for `/openclash/`

## Risks And Mitigations

### Risk: UI subpath compatibility

Some dashboard assets or API calls may assume root-path hosting.

Mitigation:

- explicitly test `/openclash/` behavior
- allow `strip_prefix` fallback in `NestGate` if needed

### Risk: subscription overrides deployment settings

If subscription content controls ports or controller fields, the deployment can become unreachable or unsafe.

Mitigation:

- deployment-owned fields are always overwritten by bootstrap rendering

### Risk: dev-container mount assumptions break runtime

Generated files mounted from the dev container into host Docker are fragile in this environment.

Mitigation:

- generate config inside the runtime container
- persist only through Docker named volumes when needed

## Success Criteria

The design is successful when:

- `OpenClash` can start from only `.env` + subscription URL
- proxy traffic is available only on host loopback
- dashboard is reachable at `https://gate.teraai.cn/openclash/`
- dashboard public access is protected by existing `NestGate` auth
- no generated runtime config file needs to be host bind-mounted from the dev container
