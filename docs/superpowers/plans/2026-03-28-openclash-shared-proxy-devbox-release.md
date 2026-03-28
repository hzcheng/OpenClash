# OpenClash Shared Proxy And DevBox Runtime Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `OpenClash` into a shared no-auth proxy endpoint for host, Docker containers, LAN devices, and tailnet devices, then switch `DevBox` default runtime processes to use that shared proxy without coupling runtime and build proxy configuration.

**Architecture:** `OpenClash` will keep the same subscription-rendered bootstrap flow and dashboard publishing model, but the mixed proxy port will move from loopback-only to shared `0.0.0.0` exposure with `allow-lan: true`. `DevBox` will split its current single `PROXY` variable into `BUILD_PROXY` and `RUNTIME_PROXY`, with runtime env vars pointing at `http://host.docker.internal:9981` while build args remain independently configurable.

**Tech Stack:** Docker Compose, Python 3, Bash, `pytest`, `mihomo`, `metacubexd`

---

### Task 1: Update OpenClash tests for shared proxy mode

**Files:**
- Modify: `/Projects/Repos/OpenClash/tests/test_render_openclash_config.py`
- Modify: `/Projects/Repos/OpenClash/tests/test_bootstrap_openclash.sh`

- [ ] **Step 1: Add a failing renderer test for shared proxy behavior**

Extend `/Projects/Repos/OpenClash/tests/test_render_openclash_config.py` so the deployment-owned fields test asserts:

```python
assert rendered["allow-lan"] is True
assert rendered["bind-address"] == "*"
```

- [ ] **Step 2: Run the renderer tests to verify they fail**

Run: `cd /Projects/Repos/OpenClash && python3 -m pytest tests/test_render_openclash_config.py -q`

Expected: FAIL because `render_openclash_config.py` still writes `allow-lan: false` and does not write `bind-address`.

- [ ] **Step 3: Add a bootstrap integration assertion for the generated shared-proxy config**

Extend `/Projects/Repos/OpenClash/tests/test_bootstrap_openclash.sh` so it also checks:

```bash
grep -q '^allow-lan: true$' "${STATE_DIR}/config.yaml"
grep -q '^bind-address: \*$' "${STATE_DIR}/config.yaml"
```

- [ ] **Step 4: Run the bootstrap test to verify it fails if needed**

Run: `cd /Projects/Repos/OpenClash && bash tests/test_bootstrap_openclash.sh`

Expected: FAIL until the renderer is updated.

- [ ] **Step 5: Commit the failing test updates only after the implementation passes**

Do not commit in red state.

### Task 2: Implement shared proxy behavior in OpenClash

**Files:**
- Modify: `/Projects/Repos/OpenClash/scripts/render_openclash_config.py`
- Modify: `/Projects/Repos/OpenClash/docker-compose.yml`
- Modify: `/Projects/Repos/OpenClash/.env.example`
- Modify: `/Projects/Repos/OpenClash/README.md`

- [ ] **Step 1: Update the renderer to produce shared proxy fields**

Modify `/Projects/Repos/OpenClash/scripts/render_openclash_config.py` so deployment-owned fields become:

```python
rendered["allow-lan"] = True
rendered["bind-address"] = "*"
```

Keep the existing deployment-owned fields intact:

- `mixed-port`
- `external-controller`
- `external-ui`
- `log-level`
- `geo-auto-update`
- `geox-url`

- [ ] **Step 2: Re-run renderer tests**

Run: `cd /Projects/Repos/OpenClash && python3 -m pytest tests/test_render_openclash_config.py -q`

Expected: PASS

- [ ] **Step 3: Keep the bootstrap path green**

Run: `cd /Projects/Repos/OpenClash && bash tests/test_bootstrap_openclash.sh`

Expected: PASS

- [ ] **Step 4: Publish the mixed proxy port to all interfaces**

Modify `/Projects/Repos/OpenClash/docker-compose.yml`:

Current:

```yaml
      - "127.0.0.1:${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}"
```

Target:

```yaml
      - "${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}"
```

Leave the controller port publishing unchanged.

- [ ] **Step 5: Update `.env.example` comments or defaults if needed**

Document that `OPENCLASH_MIXED_PORT` is now the shared proxy entrypoint for:

- host
- LAN
- tailnet
- Docker containers

- [ ] **Step 6: Update README operational guidance**

Modify `/Projects/Repos/OpenClash/README.md` so it explicitly states:

- the proxy is now shared and no longer loopback-only
- LAN devices can use `<lan-ip>:9981`
- tailnet devices can use `100.101.7.100:9981`
- Docker containers can use `host.docker.internal:9981`
- there is no proxy authentication on this entrypoint

- [ ] **Step 7: Verify rendered compose config**

Run: `cd /Projects/Repos/OpenClash && docker compose --env-file .env config`

Expected: rendered port mapping shows `${OPENCLASH_MIXED_PORT}` without `127.0.0.1`.

- [ ] **Step 8: Rebuild and recreate OpenClash**

Run:

```bash
cd /Projects/Repos/OpenClash
docker compose --env-file .env build
docker compose --env-file .env up -d --force-recreate --remove-orphans
```

Expected: container recreates successfully.

- [ ] **Step 9: Verify the container stays up**

Run:

```bash
docker compose --env-file .env ps
docker logs --tail 120 openclash
```

Expected:

- `openclash` is `Up`
- no restart loop
- initialization completes successfully

- [ ] **Step 10: Verify generated runtime config**

Run:

```bash
docker exec openclash sh -c 'grep -nE "^(allow-lan|bind-address|mixed-port|external-controller):" /root/.config/mihomo/config.yaml'
```

Expected output contains:

- `allow-lan: true`
- `bind-address: "*"` or YAML-equivalent
- `mixed-port: 9981`
- `external-controller: 0.0.0.0:9097`

- [ ] **Step 11: Commit the OpenClash shared-proxy implementation**

Run:

```bash
cd /Projects/Repos/OpenClash
git add .env.example README.md docker-compose.yml scripts/render_openclash_config.py tests/test_bootstrap_openclash.sh tests/test_render_openclash_config.py
git commit -m "feat: expose openclash as a shared proxy"
```

### Task 3: Split DevBox runtime and build proxy configuration

**Files:**
- Modify: `/Projects/DevBox/devbox/docker-compose.yml`
- Modify: `/Projects/DevBox/.env`
- Modify: `/Projects/DevBox/.example.env`

- [ ] **Step 1: Write the intended variable mapping down in compose comments**

In `/Projects/DevBox/devbox/docker-compose.yml`, add a short comment near proxy args/env clarifying:

- build args use `BUILD_PROXY`
- runtime env vars use `RUNTIME_PROXY`

- [ ] **Step 2: Change build args to use `BUILD_PROXY`**

Replace the current build arg references:

```yaml
http_proxy: ${PROXY}
https_proxy: ${PROXY}
all_proxy: ${PROXY}
HTTP_PROXY: ${PROXY}
HTTPS_PROXY: ${PROXY}
ALL_PROXY: ${PROXY}
```

with:

```yaml
http_proxy: ${BUILD_PROXY}
https_proxy: ${BUILD_PROXY}
all_proxy: ${BUILD_PROXY}
HTTP_PROXY: ${BUILD_PROXY}
HTTPS_PROXY: ${BUILD_PROXY}
ALL_PROXY: ${BUILD_PROXY}
```

- [ ] **Step 3: Change runtime env vars to use `RUNTIME_PROXY`**

Replace the runtime container env references:

```yaml
- all_proxy=${PROXY}
- http_proxy=${PROXY}
- https_proxy=${PROXY}
```

and add the uppercase variants sourced from `RUNTIME_PROXY`:

```yaml
- all_proxy=${RUNTIME_PROXY}
- http_proxy=${RUNTIME_PROXY}
- https_proxy=${RUNTIME_PROXY}
- ALL_PROXY=${RUNTIME_PROXY}
- HTTP_PROXY=${RUNTIME_PROXY}
- HTTPS_PROXY=${RUNTIME_PROXY}
```

- [ ] **Step 4: Update the real `.env`**

Modify `/Projects/DevBox/.env` so:

- `PROXY` is removed or deprecated
- `BUILD_PROXY` takes the current former value
- `RUNTIME_PROXY` becomes `http://host.docker.internal:9981`

Expected shape:

```dotenv
BUILD_PROXY=http://192.168.31.125:6789
RUNTIME_PROXY=http://host.docker.internal:9981
```

- [ ] **Step 5: Update `.example.env`**

Modify `/Projects/DevBox/.example.env` so the documented environment contract matches the split model.

- [ ] **Step 6: Verify rendered DevBox compose config**

Run:

```bash
cd /Projects/DevBox
docker compose config
```

Expected:

- build args resolve from `BUILD_PROXY`
- runtime env vars resolve from `RUNTIME_PROXY`

- [ ] **Step 7: Recreate DevBox**

Run:

```bash
cd /Projects/DevBox
docker compose up -d --force-recreate
```

Expected: `DevBox-devbox` restarts successfully.

- [ ] **Step 8: Verify runtime proxy env inside the container**

Run:

```bash
docker exec DevBox-devbox sh -lc 'env | grep -E "^(http_proxy|https_proxy|all_proxy|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY)=" | sort'
```

Expected output shows all six variables pointing at `http://host.docker.internal:9981`.

- [ ] **Step 9: Commit the DevBox runtime/build split**

Run:

```bash
cd /Projects/DevBox
git add .env .example.env devbox/docker-compose.yml
git commit -m "feat: split devbox build and runtime proxy settings"
```

### Task 4: Verify shared proxy access from host, DevBox, LAN, and tailnet

**Files:**
- No code changes expected unless verification reveals issues

- [ ] **Step 1: Verify host-local access still works**

Run:

```bash
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9981
```

Expected: connection succeeds at TCP level and does not immediately refuse.

- [ ] **Step 2: Verify tailnet-facing access now works**

Run:

```bash
curl --noproxy '*' -sS -o /dev/null -w '%{http_code}\n' http://100.101.7.100:9981
```

Expected: connection succeeds at TCP level and does not return `000` from connection refused.

- [ ] **Step 3: Verify DevBox can reach the shared proxy directly**

Run:

```bash
docker exec DevBox-devbox sh -lc 'env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY curl --noproxy "*" -sS -o /dev/null -w "%{http_code}\n" http://host.docker.internal:9981'
```

Expected: connection succeeds at TCP level and does not return `000` from connection refused.

- [ ] **Step 4: Verify dashboard behavior remains unchanged**

Run:

```bash
curl --noproxy '*' -sS -D - -o /tmp/openclash-tailnet-ui.html http://100.101.7.100:9097/ui/ | sed -n '1,12p'
ssh root@gate.teraai.cn 'curl -ksS --max-time 15 -D - -o /tmp/openclash-public-ui.out https://gate.teraai.cn/openclash/ui/ | sed -n "1,12p"'
```

Expected:

- tailnet UI returns `200`
- public UI still returns `401` until gateway auth is sent

- [ ] **Step 5: Perform one manual LAN-device check**

From a LAN client outside the host, verify `<lan-ip>:9981` is reachable and can be configured as the device proxy.

Expected: client can connect through the shared proxy.

- [ ] **Step 6: If all checks pass, stop**

Do not add extra hardening or refactors in this task.

