# OpenClash Shared Proxy For DevBox And LAN Design

## Goal

Extend the current `OpenClash` deployment so that one shared proxy entrypoint can be used by:

- the internal host itself
- the `DevBox` container and other Docker containers on the same machine
- other devices on the local LAN
- other devices on the tailnet

At the same time, keep the dashboard publishing model unchanged:

- dashboard remains public only through `NestGate`
- dashboard continues to use existing gateway Basic Auth

## Why This Change

The current deployment intentionally keeps the mixed proxy port bound to host loopback only.

That is good for isolation, but it prevents:

- `DevBox` runtime processes from using `OpenClash`
- future containers on the same machine from reusing the same proxy
- LAN devices from pointing at this machine as their proxy
- tailnet devices from using the same shared entrypoint

The user now wants one shared, no-auth proxy endpoint that all of those clients can reuse.

## Non-Goals

This design does not include:

- exposing the proxy through `NestGate`
- adding proxy authentication
- restricting the proxy to a subset of LAN devices
- creating a second dedicated shared-proxy port
- changing the dashboard public URL away from `https://gate.teraai.cn/openclash/`

## Chosen Approach

Reuse the existing `mihomo` mixed proxy port `9981` as the shared entrypoint.

The deployment will move from:

- `allow-lan: false`
- `127.0.0.1:${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}`

to:

- `allow-lan: true`
- explicit bind to `0.0.0.0`
- `${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}`

This keeps one stable proxy address and avoids having separate “local only” and “shared” ports.

For `DevBox`, split the current single proxy variable into two independent concerns:

- build-time proxy
- runtime proxy

That allows `DevBox` runtime traffic to switch to `OpenClash` without forcing image builds to use the same proxy endpoint.

## Resulting Network Model

After rollout, the shared proxy endpoint will be reachable as:

- host-local: `127.0.0.1:9981`
- LAN-facing: `<internal-host-lan-ip>:9981`
- tailnet-facing: `100.101.7.100:9981`
- container-facing from `DevBox`: `host.docker.internal:9981`

The controller/dashboard model stays:

- controller/UI on port `9097`
- internal direct path for verification: `http://100.101.7.100:9097/ui/`
- public path via `NestGate`: `https://gate.teraai.cn/openclash/`

## Security Model

This design intentionally creates a shared proxy with no authentication.

That means any device that can reach the machine’s LAN IP or tailnet IP on port `9981` can use the proxy.

This is an explicit product decision for convenience, not an accidental side effect.

The dashboard remains protected separately by the gateway.

## OpenClash Changes

### Runtime Config

`render_openclash_config.py` should change deployment-owned proxy behavior from:

- `allow-lan: false`

to:

- `allow-lan: true`
- explicit `bind-address: "*"` or `0.0.0.0`-equivalent behavior as supported by the generated Clash/Mihomo config

Deployment-owned fields should continue to control:

- mixed port
- controller port
- external UI path
- log level
- geodata download endpoints

### Compose Publishing

`docker-compose.yml` should publish the mixed port without the loopback-only host IP prefix.

Current:

- `127.0.0.1:${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}`

Target:

- `${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}`

Controller publishing on `9097` should stay as-is.

### Documentation

`README.md` should be updated to reflect that the proxy is now a shared entrypoint for:

- the host
- Docker containers
- LAN clients
- tailnet clients

It should clearly call out the no-auth exposure model.

## DevBox Changes

### Environment Contract

Replace the current single runtime/build proxy coupling:

- `PROXY`

with a split model:

- `BUILD_PROXY`
- `RUNTIME_PROXY`

Suggested defaults:

- keep `BUILD_PROXY` aligned with the current external proxy until explicitly changed
- set `RUNTIME_PROXY=http://host.docker.internal:9981`

### Compose Runtime Environment

In `DevBox/devbox/docker-compose.yml`, the container runtime environment should source:

- `http_proxy`
- `https_proxy`
- `all_proxy`
- `HTTP_PROXY`
- `HTTPS_PROXY`
- `ALL_PROXY`

from `RUNTIME_PROXY`.

### Build Arguments

Build args in the same compose file should source:

- `http_proxy`
- `https_proxy`
- `all_proxy`
- `HTTP_PROXY`
- `HTTPS_PROXY`
- `ALL_PROXY`

from `BUILD_PROXY`.

This preserves the current image-build flexibility while moving all default runtime processes onto `OpenClash`.

## Alternatives Considered

### Option 1: Keep loopback-only proxy and add a DevBox-only forwarder

Pros:

- preserves the most restrictive default exposure

Cons:

- does not satisfy the broader LAN and tailnet sharing goal cleanly
- adds extra moving parts for a need that is now explicitly broader than `DevBox`

### Option 2: Add a second shared proxy port

Pros:

- clearer separation between local-only and shared access

Cons:

- more operational overhead
- user explicitly prefers reusing the existing port

### Option 3: Publish the proxy through NestGate

Pros:

- centralized public exposure layer

Cons:

- wrong topology for a raw proxy service
- unnecessary public exposure
- not requested

## Verification Requirements

### OpenClash

Verify:

- `docker compose --env-file .env config` succeeds
- `openclash` container starts and stays up
- `100.101.7.100:9981` accepts proxy connections
- `100.101.7.100:9097/ui/` still returns success

### DevBox

Verify:

- runtime environment variables inside `DevBox` point to `RUNTIME_PROXY`
- build args still point to `BUILD_PROXY`
- a no-proxy-disabled runtime HTTP request from inside `DevBox` can successfully use `host.docker.internal:9981`

### LAN / Tailnet

Verify:

- a LAN client can reach `<lan-ip>:9981`
- a tailnet client can reach `100.101.7.100:9981`

### Gateway

Verify:

- `https://gate.teraai.cn/openclash/` still redirects to `/openclash/ui/`
- `https://gate.teraai.cn/openclash/ui/` still requires gateway auth

## Risks And Mitigations

### Risk: No-auth proxy is broadly reachable

Mitigation:

- document this explicitly
- avoid accidental public publishing through `NestGate`

### Risk: DevBox builds regress if runtime and build proxy are still coupled

Mitigation:

- split `BUILD_PROXY` and `RUNTIME_PROXY`
- keep build behavior independent from runtime behavior

### Risk: Existing local-only assumptions become stale

Mitigation:

- update `OpenClash` README and examples
- update `DevBox` `.env` examples and compose comments

## Success Criteria

The rollout is successful when:

- `OpenClash` proxy port `9981` is usable from host, LAN, tailnet, and `DevBox`
- `DevBox` default runtime processes automatically inherit `OpenClash` as their proxy
- `DevBox` build-time proxy remains separately configurable
- `OpenClash` dashboard continues to work through `NestGate`
