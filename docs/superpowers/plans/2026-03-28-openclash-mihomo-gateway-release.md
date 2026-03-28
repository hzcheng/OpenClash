# OpenClash Mihomo Gateway Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy an `OpenClash` service that runs `mihomo` locally on the internal host, keeps the proxy port host-local only, and publishes the dashboard through `NestGate` at `https://gate.teraai.cn/openclash/`.

**Architecture:** The `OpenClash` image embeds `mihomo`, `metacubexd`, and a bootstrap flow that downloads the Clash subscription YAML at runtime and renders a deployment-owned `config.yaml` inside the container state volume. `NestGate` only reverse-proxies the controller/UI path; it must never expose the proxy mixed port.

**Tech Stack:** Docker Compose, Bash, Python 3, `pytest`, `PyYAML`, `mihomo`, `metacubexd`, `nginx`

---

### Task 1: Scaffold the repository and config-renderer test harness

**Files:**
- Create: `/Projects/Repos/OpenClash/.gitignore`
- Create: `/Projects/Repos/OpenClash/.env.example`
- Create: `/Projects/Repos/OpenClash/requirements-dev.txt`
- Create: `/Projects/Repos/OpenClash/pytest.ini`
- Create: `/Projects/Repos/OpenClash/tests/fixtures/subscription-base.yaml`
- Create: `/Projects/Repos/OpenClash/tests/test_render_openclash_config.py`
- Create: `/Projects/Repos/OpenClash/scripts/render_openclash_config.py`

- [ ] **Step 1: Create the base repository metadata files**

Create:

```gitignore
.env
.pytest_cache/
__pycache__/
*.pyc
```

Create:

```text
pytest==9.0.2
PyYAML==6.0.2
```

Create:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 2: Create `.env.example` with the deployment contract**

Create `/Projects/Repos/OpenClash/.env.example` with:

```dotenv
OPENCLASH_SUBSCRIPTION_URL=https://example.com/subscription.yaml
OPENCLASH_MIXED_PORT=9981
OPENCLASH_CONTROLLER_PORT=9097
OPENCLASH_LOG_LEVEL=warning
OPENCLASH_UI_PATH=/openclash/
OPENCLASH_UI_DIR=/var/lib/openclash/ui
OPENCLASH_STATE_DIR=/var/lib/openclash
OPENCLASH_AUTO_UPDATE_UI=false
```

- [ ] **Step 3: Create the base subscription fixture**

Create `/Projects/Repos/OpenClash/tests/fixtures/subscription-base.yaml` with a minimal valid Clash-style payload:

```yaml
mixed-port: 7890
allow-lan: true
mode: rule
proxies:
  - name: sample-node
    type: socks5
    server: 127.0.0.1
    port: 1080
proxy-groups:
  - name: Proxy
    type: select
    proxies:
      - sample-node
rules:
  - MATCH,Proxy
```

- [ ] **Step 4: Write the failing config-renderer tests**

Create `/Projects/Repos/OpenClash/tests/test_render_openclash_config.py` with tests that verify:

```python
def test_renderer_overrides_deployment_owned_fields(tmp_path):
    rendered = render_config(...)
    assert rendered["mixed-port"] == 9981
    assert rendered["allow-lan"] is False
    assert rendered["external-controller"] == "0.0.0.0:9097"
    assert rendered["external-ui"] == "/var/lib/openclash/ui"

def test_renderer_preserves_subscription_rules_and_groups(tmp_path):
    rendered = render_config(...)
    assert rendered["proxies"][0]["name"] == "sample-node"
    assert rendered["proxy-groups"][0]["name"] == "Proxy"
    assert rendered["rules"] == ["MATCH,Proxy"]

def test_renderer_rejects_missing_required_sections(tmp_path):
    with pytest.raises(ValueError, match="missing required Clash sections"):
        render_config(...)
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `cd /Projects/Repos/OpenClash && python3 -m pip install -r requirements-dev.txt && pytest tests/test_render_openclash_config.py -q`

Expected: FAIL because `/Projects/Repos/OpenClash/scripts/render_openclash_config.py` does not exist yet.

- [ ] **Step 6: Implement the minimal renderer**

Create `/Projects/Repos/OpenClash/scripts/render_openclash_config.py` with a pure function and CLI entrypoint that:

```python
def render_config(base_config: dict, *, mixed_port: int, controller_port: int, ui_dir: str, log_level: str) -> dict:
    required = ("proxies", "proxy-groups", "rules")
    missing = [key for key in required if key not in base_config]
    if missing:
        raise ValueError(f"missing required Clash sections: {', '.join(missing)}")

    config = dict(base_config)
    config["mixed-port"] = mixed_port
    config["allow-lan"] = False
    config["external-controller"] = f"0.0.0.0:{controller_port}"
    config["external-ui"] = ui_dir
    config["log-level"] = log_level
    return config
```

The CLI should:

- read `--input`, `--output`, and the deployment override flags
- load YAML from `--input`
- call `render_config`
- write the rendered YAML to `--output`

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd /Projects/Repos/OpenClash && pytest tests/test_render_openclash_config.py -q`

Expected: PASS

- [ ] **Step 8: Commit the scaffolding and renderer**

```bash
cd /Projects/Repos/OpenClash
git add .gitignore .env.example requirements-dev.txt pytest.ini tests/fixtures/subscription-base.yaml tests/test_render_openclash_config.py scripts/render_openclash_config.py
git commit -m "feat: add openclash config renderer"
```

### Task 2: Add bootstrap orchestration for runtime subscription rendering

**Files:**
- Create: `/Projects/Repos/OpenClash/scripts/bootstrap-openclash.sh`
- Create: `/Projects/Repos/OpenClash/tests/test_bootstrap_openclash.sh`
- Modify: `/Projects/Repos/OpenClash/scripts/render_openclash_config.py`

- [ ] **Step 1: Write the failing bootstrap integration test**

Create `/Projects/Repos/OpenClash/tests/test_bootstrap_openclash.sh` that:

- starts a temporary local HTTP server serving `tests/fixtures/subscription-base.yaml`
- provides a fake `mihomo` executable in `PATH`
- runs `scripts/bootstrap-openclash.sh`
- verifies:
  - `${OPENCLASH_STATE_DIR}/config.yaml` is created
  - the rendered YAML contains the overridden `mixed-port`
  - the bootstrap ultimately execs `mihomo -f <state>/config.yaml`

Core assertion shape:

```bash
grep -q '^mixed-port: 9981$' "${STATE_DIR}/config.yaml"
grep -q "mihomo -f ${STATE_DIR}/config.yaml" "${TMP_DIR}/mihomo-invocation.log"
```

- [ ] **Step 2: Run the bootstrap test to verify it fails**

Run: `cd /Projects/Repos/OpenClash && bash tests/test_bootstrap_openclash.sh`

Expected: FAIL because `/Projects/Repos/OpenClash/scripts/bootstrap-openclash.sh` does not exist yet.

- [ ] **Step 3: Implement the bootstrap script**

Create `/Projects/Repos/OpenClash/scripts/bootstrap-openclash.sh` that:

- validates required env vars
- normalizes `OPENCLASH_UI_PATH` so it ends with `/`
- creates `${OPENCLASH_STATE_DIR}` and `${OPENCLASH_UI_DIR}`
- downloads the subscription to a temp file
- runs:

```bash
python3 /usr/local/bin/render_openclash_config.py \
  --input "${TMP_SUBSCRIPTION}" \
  --output "${OPENCLASH_STATE_DIR}/config.yaml" \
  --mixed-port "${OPENCLASH_MIXED_PORT}" \
  --controller-port "${OPENCLASH_CONTROLLER_PORT}" \
  --ui-dir "${OPENCLASH_UI_DIR}" \
  --log-level "${OPENCLASH_LOG_LEVEL}"
```

- finally execs:

```bash
exec mihomo -f "${OPENCLASH_STATE_DIR}/config.yaml"
```

- [ ] **Step 4: Extend the renderer CLI only as needed for bootstrap**

Modify `/Projects/Repos/OpenClash/scripts/render_openclash_config.py` so its CLI supports:

- `--mixed-port`
- `--controller-port`
- `--ui-dir`
- `--log-level`

Keep the rendering logic shared with Task 1 tests.

- [ ] **Step 5: Run the bootstrap test to verify it passes**

Run: `cd /Projects/Repos/OpenClash && bash tests/test_bootstrap_openclash.sh`

Expected: PASS

- [ ] **Step 6: Re-run the renderer tests for regression safety**

Run: `cd /Projects/Repos/OpenClash && pytest tests/test_render_openclash_config.py -q`

Expected: PASS

- [ ] **Step 7: Commit the bootstrap flow**

```bash
cd /Projects/Repos/OpenClash
git add scripts/bootstrap-openclash.sh tests/test_bootstrap_openclash.sh scripts/render_openclash_config.py
git commit -m "feat: bootstrap openclash config at runtime"
```

### Task 3: Build the image and compose deployment around mihomo + metacubexd

**Files:**
- Create: `/Projects/Repos/OpenClash/Dockerfile`
- Create: `/Projects/Repos/OpenClash/docker-compose.yml`
- Create: `/Projects/Repos/OpenClash/README.md`
- Modify: `/Projects/Repos/OpenClash/.env.example`

- [ ] **Step 1: Write the failing compose smoke check**

Create a smoke assertion in `/Projects/Repos/OpenClash/README.md` and validate the compose file with:

Run: `cd /Projects/Repos/OpenClash && docker compose --env-file .env.example config`

Expected: FAIL because `Dockerfile` and `docker-compose.yml` do not exist yet.

- [ ] **Step 2: Implement the custom Dockerfile**

Create `/Projects/Repos/OpenClash/Dockerfile` using a `mihomo` runtime base and embed the UI plus scripts. The Dockerfile should:

- install `python3`, `pip`, `curl`, and CA certs
- install `PyYAML`
- download and unpack `metacubexd` UI assets into `/var/lib/openclash/ui`
- copy `scripts/bootstrap-openclash.sh` to `/usr/local/bin/bootstrap-openclash.sh`
- copy `scripts/render_openclash_config.py` to `/usr/local/bin/render_openclash_config.py`
- set the default command to the bootstrap script

- [ ] **Step 3: Implement the compose service**

Create `/Projects/Repos/OpenClash/docker-compose.yml` with one service:

```yaml
services:
  openclash:
    build:
      context: .
      dockerfile: Dockerfile
    image: openclash:custom
    container_name: openclash
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "127.0.0.1:${OPENCLASH_MIXED_PORT}:${OPENCLASH_MIXED_PORT}"
      - "${OPENCLASH_CONTROLLER_PORT}:${OPENCLASH_CONTROLLER_PORT}"
    volumes:
      - openclash-state:/var/lib/openclash
    command:
      - /usr/local/bin/bootstrap-openclash.sh

volumes:
  openclash-state:
```

- [ ] **Step 4: Add a README focused on deployment and verification**

Create `/Projects/Repos/OpenClash/README.md` documenting:

- required `.env` values
- local proxy usage at `127.0.0.1:${OPENCLASH_MIXED_PORT}`
- public dashboard path `https://gate.teraai.cn/openclash/`
- startup and verification commands

- [ ] **Step 5: Run the compose render check**

Run: `cd /Projects/Repos/OpenClash && cp .env.example .env && docker compose --env-file .env config`

Expected: PASS

- [ ] **Step 6: Build the image**

Run: `cd /Projects/Repos/OpenClash && docker compose --env-file .env build`

Expected: PASS and produce `openclash:custom`

- [ ] **Step 7: Commit the container packaging**

```bash
cd /Projects/Repos/OpenClash
git add Dockerfile docker-compose.yml README.md .env.example
git commit -m "feat: package openclash mihomo service"
```

### Task 4: Start OpenClash locally and verify local-only proxy behavior

**Files:**
- Modify: `/Projects/Repos/OpenClash/.env` (local runtime only, do not commit)
- Reference: `/Projects/Repos/OpenClash/docker-compose.yml`
- Reference: `/Projects/Repos/OpenClash/README.md`

- [ ] **Step 1: Populate the local `.env`**

Create `/Projects/Repos/OpenClash/.env` from `.env.example` and set:

```dotenv
OPENCLASH_SUBSCRIPTION_URL=https://fc1ddbea.ghelper.me/subs/clash/26102279fc1ddbeaeba31af7d530ed45
OPENCLASH_MIXED_PORT=9981
OPENCLASH_CONTROLLER_PORT=9097
OPENCLASH_LOG_LEVEL=warning
OPENCLASH_UI_PATH=/openclash/
OPENCLASH_UI_DIR=/var/lib/openclash/ui
OPENCLASH_STATE_DIR=/var/lib/openclash
OPENCLASH_AUTO_UPDATE_UI=false
```

- [ ] **Step 2: Start the service**

Run: `cd /Projects/Repos/OpenClash && docker compose --env-file .env up -d --remove-orphans`

Expected: container `openclash` starts

- [ ] **Step 3: Verify the generated runtime config exists**

Run: `docker exec openclash sh -c 'sed -n "1,60p" /var/lib/openclash/config.yaml'`

Expected: rendered config includes `mixed-port: 9981` and `external-controller: 0.0.0.0:9097`

- [ ] **Step 4: Verify the proxy mixed port is only host-local**

Run: `docker compose -f /Projects/Repos/OpenClash/docker-compose.yml --env-file /Projects/Repos/OpenClash/.env ps`

Expected: published port line shows `127.0.0.1:9981->9981/tcp`

- [ ] **Step 5: Verify the controller locally on the internal host**

Run: `curl -sS -D - -o /tmp/openclash-controller.html http://127.0.0.1:9097/ | sed -n '1,20p'`

Expected: HTTP success from the controller/UI endpoint

- [ ] **Step 6: Commit only tracked local-safe changes if any**

```bash
cd /Projects/Repos/OpenClash
git add README.md docker-compose.yml
git commit -m "chore: document local openclash startup"
```

Only commit tracked files that were intentionally changed. Do not add `.env`.

### Task 5: Publish the dashboard through NestGate

**Files:**
- Modify: `/Projects/Repos/NestGate/config/services.yml`
- Reference: `/Projects/Repos/NestGate/README.md`

- [ ] **Step 1: Add the OpenClash route**

Update `/Projects/Repos/NestGate/config/services.yml` with:

```yaml
  - name: openclash
    display_name: OpenClash
    description: 本地代理监控与配置面板
    icon: "🧭"
    badge: 代理面板
    show_in_home: true
    path: /openclash
    upstream: http://100.101.7.100:9097
    strip_prefix: false
    websocket: true
    auth: false
    notes: prefer subpath-native UI; if asset paths break, switch to strip_prefix true after verification
```

- [ ] **Step 2: Verify NestGate tests**

Run: `cd /Projects/Repos/NestGate && pytest tests/test_render_config.py tests/test_compose_smoke.py`

Expected: PASS

- [ ] **Step 3: Render the local gateway config**

Run: `cd /Projects/Repos/NestGate && ./scripts/deploy.sh --check-only`

Expected: either PASS or the known local certificate-staging limitation already documented in the repo; if it fails, inspect whether the generated `/openclash` route itself is correct before proceeding

- [ ] **Step 4: Commit the route change**

```bash
cd /Projects/Repos/NestGate
git add config/services.yml nginx/generated/services.conf nginx/generated/site-https.conf nginx/generated/index.html
git commit -m "feat: publish openclash dashboard"
```

### Task 6: Deploy the NestGate change to the cloud host and verify the public dashboard

**Files:**
- Modify: `/root/Docker/NestGate/config/services.yml`
- Reference: `/root/Docker/NestGate/scripts/deploy.sh`

- [ ] **Step 1: Sync the updated service catalog to the cloud host**

Run: `scp /Projects/Repos/NestGate/config/services.yml root@gate.teraai.cn:/root/Docker/NestGate/config/services.yml`

Expected: remote file updated

- [ ] **Step 2: Validate the real host config before reload**

Run: `ssh root@gate.teraai.cn 'cd /root/Docker/NestGate && ./scripts/deploy.sh --check-only'`

Expected: PASS

- [ ] **Step 3: Reload the gateway**

Run: `ssh root@gate.teraai.cn 'cd /root/Docker/NestGate && ./scripts/deploy.sh'`

Expected: PASS and `nginx` reload notice

- [ ] **Step 4: Verify the cloud host can reach the internal dashboard upstream**

Run: `ssh root@gate.teraai.cn 'docker exec nestgate-nginx-1 sh -lc "curl -sS --max-time 15 -D - -o /tmp/openclash-upstream.html http://100.101.7.100:9097/ | sed -n \"1,20p\""'`

Expected: HTTP success

- [ ] **Step 5: Verify the public dashboard**

Run: `ssh root@gate.teraai.cn 'curl -ksS --max-time 15 -D - -o /tmp/openclash-public.html https://gate.teraai.cn/openclash/ | sed -n "1,20p"'`

Expected: HTTP success

- [ ] **Step 6: Verify dashboard assets under the public path**

Extract one asset path from `/tmp/openclash-public.html` and verify:

Run: `ssh root@gate.teraai.cn 'curl -ksS --max-time 15 -o /dev/null -w "%{http_code}\n" https://gate.teraai.cn/openclash/<asset-path>'`

Expected: `200`

- [ ] **Step 7: If subpath assets fail, switch to prefix stripping**

If assets or API calls break under `/openclash/`:

- change `/Projects/Repos/NestGate/config/services.yml` to `strip_prefix: true`
- redeploy `NestGate`
- re-test the public page and assets

This fallback is allowed by the spec and should be used only if empirical verification shows subpath breakage.

- [ ] **Step 8: Review gateway logs for route errors**

Run: `ssh root@gate.teraai.cn 'docker logs --since 10m nestgate-nginx-1 2>&1 | grep -nE "/openclash/| 404 | 502 | 503 | 504 " | tail -n 120'`

Expected: successful `/openclash/` requests without new `502/504` errors

- [ ] **Step 9: Commit the final verified changes if needed**

```bash
cd /Projects/Repos/OpenClash
git status --short
cd /Projects/Repos/NestGate
git status --short
```

Only commit tracked implementation files that were intentionally changed and verified.
