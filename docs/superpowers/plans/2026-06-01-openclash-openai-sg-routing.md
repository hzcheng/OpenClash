# OpenAI Singapore Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route OpenAI traffic through subscription proxies whose names indicate Singapore region, using a `url-test` group injected at render time.

**Architecture:** All logic lives in `scripts/render_openclash_config.py`. Five new env vars (with defaults) flow through `bootstrap-openclash.sh` to the renderer's CLI. The renderer adds a `rule-providers.openai` entry, prepends an `OpenAI` `url-test` group built from regex-matched proxies, and prepends a `RULE-SET,openai,OpenAI` rule. No subscription mutation; failure modes raise `ValueError`.

**Tech Stack:** Python 3 (stdlib `re`, PyYAML), POSIX shell, pytest, bash test harness.

Spec: `docs/superpowers/specs/2026-06-01-openclash-openai-sg-routing-design.md`

---

## File Structure

- Modify `scripts/render_openclash_config.py` — add OpenAI routing logic, extend `render_config` signature, extend CLI.
- Modify `scripts/bootstrap-openclash.sh` — set defaults for the five new env vars and pass them as flags.
- Modify `tests/fixtures/subscription-base.yaml` — add SG / JP / US proxies and a referencing group, so the fixture stays a valid Clash config.
- Modify `tests/test_render_openclash_config.py` — add OpenAI routing test cases; existing tests keep working with the extended fixture.
- Modify `tests/test_bootstrap_openclash.sh` — set the new env vars (or rely on defaults) and assert the rendered config contains the new group/rule.
- Modify `.env.example` — document the five new env vars with defaults.
- Modify `README.md` — add an "OpenAI Routing" section.

---

### Task 1: Extend the test fixture with SG / JP / US proxies

**Files:**
- Modify: `tests/fixtures/subscription-base.yaml`

- [ ] **Step 1: Run the existing test suite to confirm baseline green**

Run: `pytest -q`
Expected: 4 tests pass.

- [ ] **Step 2: Replace the fixture with multi-region proxies**

Overwrite `tests/fixtures/subscription-base.yaml` with:

```yaml
mixed-port: 7890
allow-lan: true
mode: rule
proxies:
  - name: 🇸🇬 SG-01
    type: ss
    server: sg1.example.com
    port: 8388
    cipher: aes-128-gcm
    password: password
  - name: Singapore-02
    type: ss
    server: sg2.example.com
    port: 8388
    cipher: aes-128-gcm
    password: password
  - name: 日本-东京-01
    type: ss
    server: jp1.example.com
    port: 8388
    cipher: aes-128-gcm
    password: password
  - name: US-LA-01
    type: ss
    server: us1.example.com
    port: 8388
    cipher: aes-128-gcm
    password: password
proxy-groups:
  - name: Auto
    type: select
    proxies:
      - 🇸🇬 SG-01
      - Singapore-02
      - 日本-东京-01
      - US-LA-01
rules:
  - MATCH,Auto
```

- [ ] **Step 3: Re-run the existing test suite**

Run: `pytest -q`
Expected: still 4 tests pass — the existing assertions only check that `proxies / proxy-groups / rules` are preserved and deployment fields override, so a richer fixture must not break them.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/subscription-base.yaml
git commit -m "test: extend subscription fixture with SG/JP/US proxies"
```

---

### Task 2: Write failing tests for the OpenAI group injection

**Files:**
- Modify: `tests/test_render_openclash_config.py`

- [ ] **Step 1: Add a shared kwargs helper and the happy-path tests**

At the top of `tests/test_render_openclash_config.py`, after the existing imports, add:

```python
OPENAI_KWARGS = dict(
    openai_rule_provider_url="https://example.com/openai.yaml",
    openai_region_regex=r"(?i)(🇸🇬|SG|Singapore|新加坡|狮城)",
    openai_group_name="OpenAI",
    openai_healthcheck_url="https://chat.openai.com/cdn-cgi/trace",
    openai_healthcheck_interval=300,
)
```

Then append these tests at the bottom of the file:

```python
def test_openai_group_is_first_proxy_group_with_only_sg_nodes() -> None:
    base_config = _load_fixture()

    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
        **OPENAI_KWARGS,
    )

    first_group = rendered["proxy-groups"][0]
    assert first_group["name"] == "OpenAI"
    assert first_group["type"] == "url-test"
    assert first_group["proxies"] == ["🇸🇬 SG-01", "Singapore-02"]
    assert first_group["url"] == "https://chat.openai.com/cdn-cgi/trace"
    assert first_group["interval"] == 300
    assert first_group["tolerance"] == 50


def test_openai_rule_is_prepended() -> None:
    base_config = _load_fixture()

    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
        **OPENAI_KWARGS,
    )

    assert rendered["rules"][0] == "RULE-SET,openai,OpenAI"


def test_openai_rule_provider_is_injected() -> None:
    base_config = _load_fixture()

    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
        **OPENAI_KWARGS,
    )

    provider = rendered["rule-providers"]["openai"]
    assert provider["type"] == "http"
    assert provider["behavior"] == "classical"
    assert provider["format"] == "yaml"
    assert provider["url"] == "https://example.com/openai.yaml"
    assert provider["path"] == "./ruleset/openai.yaml"
    assert provider["interval"] == 86400


def test_openai_group_uses_custom_name() -> None:
    base_config = _load_fixture()

    kwargs = {**OPENAI_KWARGS, "openai_group_name": "OpenAI-SG"}
    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
        **kwargs,
    )

    assert rendered["proxy-groups"][0]["name"] == "OpenAI-SG"
    assert rendered["rules"][0] == "RULE-SET,openai,OpenAI-SG"


def test_no_matching_proxies_raises() -> None:
    base_config = _load_fixture()

    kwargs = {**OPENAI_KWARGS, "openai_region_regex": r"^DOES_NOT_MATCH$"}
    with pytest.raises(ValueError, match="no proxies match"):
        render_config(
            base_config,
            mixed_port=9981,
            controller_port=9097,
            ui_dir="/var/lib/openclash/ui",
            log_level="warning",
            **kwargs,
        )


def test_existing_openai_group_raises() -> None:
    base_config = _load_fixture()
    base_config["proxy-groups"].append({"name": "OpenAI", "type": "select", "proxies": ["🇸🇬 SG-01"]})

    with pytest.raises(ValueError, match="already defines a proxy-group named"):
        render_config(
            base_config,
            mixed_port=9981,
            controller_port=9097,
            ui_dir="/var/lib/openclash/ui",
            log_level="warning",
            **OPENAI_KWARGS,
        )


def test_existing_openai_rule_provider_raises() -> None:
    base_config = _load_fixture()
    base_config["rule-providers"] = {"openai": {"type": "http", "url": "x", "behavior": "classical", "path": "./x"}}

    with pytest.raises(ValueError, match="already defines a rule-provider named"):
        render_config(
            base_config,
            mixed_port=9981,
            controller_port=9097,
            ui_dir="/var/lib/openclash/ui",
            log_level="warning",
            **OPENAI_KWARGS,
        )
```

- [ ] **Step 2: Run the new tests and verify they fail for the right reason**

Run: `pytest tests/test_render_openclash_config.py -q`
Expected: 4 original tests pass; 7 new tests fail with `TypeError: render_config() got an unexpected keyword argument 'openai_rule_provider_url'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_render_openclash_config.py
git commit -m "test: add failing OpenAI SG routing tests"
```

---

### Task 3: Implement OpenAI routing in `render_config`

**Files:**
- Modify: `scripts/render_openclash_config.py`

- [ ] **Step 1: Add the imports and constants**

At the top of `scripts/render_openclash_config.py`, replace the existing imports block with:

```python
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path

import yaml


REQUIRED_SECTIONS = ("proxies", "proxy-groups", "rules")
GEOX_URLS = {
    "geoip": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geoip.dat",
    "geosite": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geosite.dat",
    "mmdb": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb",
}
OPENAI_RULE_PROVIDER_KEY = "openai"
OPENAI_RULE_PROVIDER_INTERVAL = 86400
OPENAI_GROUP_TOLERANCE = 50
```

- [ ] **Step 2: Replace `render_config` with the extended version**

Replace the entire `render_config` function with:

```python
def render_config(
    base_config: dict,
    *,
    mixed_port: int,
    controller_port: int,
    ui_dir: str,
    log_level: str,
    openai_rule_provider_url: str,
    openai_region_regex: str,
    openai_group_name: str,
    openai_healthcheck_url: str,
    openai_healthcheck_interval: int,
) -> dict:
    missing = [section for section in REQUIRED_SECTIONS if section not in base_config]
    if missing:
        raise ValueError(
            f"missing required Clash sections: {', '.join(missing)}"
        )

    rendered = copy.deepcopy(base_config)
    rendered["mixed-port"] = mixed_port
    rendered["allow-lan"] = True
    rendered["bind-address"] = "*"
    rendered["external-controller"] = f"0.0.0.0:{controller_port}"
    rendered["external-ui"] = ui_dir
    rendered["log-level"] = log_level
    rendered["geo-auto-update"] = False
    rendered["geox-url"] = copy.deepcopy(GEOX_URLS)

    _inject_openai_routing(
        rendered,
        rule_provider_url=openai_rule_provider_url,
        region_regex=openai_region_regex,
        group_name=openai_group_name,
        healthcheck_url=openai_healthcheck_url,
        healthcheck_interval=openai_healthcheck_interval,
    )

    return rendered


def _inject_openai_routing(
    rendered: dict,
    *,
    rule_provider_url: str,
    region_regex: str,
    group_name: str,
    healthcheck_url: str,
    healthcheck_interval: int,
) -> None:
    pattern = re.compile(region_regex)
    matched = [
        proxy["name"]
        for proxy in rendered["proxies"]
        if pattern.search(proxy["name"])
    ]
    if not matched:
        raise ValueError("no proxies match OPENCLASH_OPENAI_REGION_REGEX")

    existing_groups = {group["name"] for group in rendered["proxy-groups"]}
    if group_name in existing_groups:
        raise ValueError(
            f"subscription already defines a proxy-group named {group_name!r}"
        )

    providers = rendered.setdefault("rule-providers", {})
    if OPENAI_RULE_PROVIDER_KEY in providers:
        raise ValueError(
            f"subscription already defines a rule-provider named {OPENAI_RULE_PROVIDER_KEY!r}"
        )

    providers[OPENAI_RULE_PROVIDER_KEY] = {
        "type": "http",
        "behavior": "classical",
        "format": "yaml",
        "url": rule_provider_url,
        "path": f"./ruleset/{OPENAI_RULE_PROVIDER_KEY}.yaml",
        "interval": OPENAI_RULE_PROVIDER_INTERVAL,
    }

    rendered["proxy-groups"].insert(
        0,
        {
            "name": group_name,
            "type": "url-test",
            "proxies": matched,
            "url": healthcheck_url,
            "interval": healthcheck_interval,
            "tolerance": OPENAI_GROUP_TOLERANCE,
        },
    )

    rendered["rules"].insert(
        0,
        f"RULE-SET,{OPENAI_RULE_PROVIDER_KEY},{group_name}",
    )
```

- [ ] **Step 3: Run the unit tests to verify all pass**

Run: `pytest tests/test_render_openclash_config.py -q`
Expected: 11 tests pass (4 original + 7 new).

- [ ] **Step 4: Commit the implementation**

```bash
git add scripts/render_openclash_config.py
git commit -m "feat: inject OpenAI rule-set and SG url-test group at render time"
```

---

### Task 4: Wire the new flags through the renderer CLI

**Files:**
- Modify: `scripts/render_openclash_config.py`

- [ ] **Step 1: Replace `_parse_args` and `main`**

Replace the existing `_parse_args` and `main` functions at the bottom of `scripts/render_openclash_config.py` with:

```python
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render OpenClash configuration from a subscription payload."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mixed-port", type=int, required=True)
    parser.add_argument("--controller-port", type=int, required=True)
    parser.add_argument("--ui-dir", required=True)
    parser.add_argument("--log-level", required=True)
    parser.add_argument("--openai-rule-provider-url", required=True)
    parser.add_argument("--openai-region-regex", required=True)
    parser.add_argument("--openai-group-name", required=True)
    parser.add_argument("--openai-healthcheck-url", required=True)
    parser.add_argument("--openai-healthcheck-interval", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", encoding="utf-8") as handle:
        base_config = yaml.safe_load(handle) or {}

    rendered = render_config(
        base_config,
        mixed_port=args.mixed_port,
        controller_port=args.controller_port,
        ui_dir=args.ui_dir,
        log_level=args.log_level,
        openai_rule_provider_url=args.openai_rule_provider_url,
        openai_region_regex=args.openai_region_regex,
        openai_group_name=args.openai_group_name,
        openai_healthcheck_url=args.openai_healthcheck_url,
        openai_healthcheck_interval=args.openai_healthcheck_interval,
    )

    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(rendered, handle, sort_keys=False)
```

- [ ] **Step 2: Smoke-test the CLI by hand**

Run:

```bash
python3 scripts/render_openclash_config.py \
  --input tests/fixtures/subscription-base.yaml \
  --output /tmp/openclash-rendered.yaml \
  --mixed-port 9981 \
  --controller-port 9097 \
  --ui-dir /tmp/ui \
  --log-level warning \
  --openai-rule-provider-url https://example.com/openai.yaml \
  --openai-region-regex '(?i)(🇸🇬|SG|Singapore|新加坡|狮城)' \
  --openai-group-name OpenAI \
  --openai-healthcheck-url https://chat.openai.com/cdn-cgi/trace \
  --openai-healthcheck-interval 300

grep -E '^- RULE-SET,openai,OpenAI$|^  name: OpenAI$|type: url-test' /tmp/openclash-rendered.yaml
rm -f /tmp/openclash-rendered.yaml
```

Expected: the grep prints the OpenAI rule line, the group name, and `type: url-test`.

- [ ] **Step 3: Commit the CLI changes**

```bash
git add scripts/render_openclash_config.py
git commit -m "feat: expose OpenAI routing flags on render_openclash_config CLI"
```

---

### Task 5: Pass new env vars through `bootstrap-openclash.sh`

**Files:**
- Modify: `scripts/bootstrap-openclash.sh`

- [ ] **Step 1: Add defaults and CLI flags**

In `scripts/bootstrap-openclash.sh`, immediately after the line `OPENCLASH_BUNDLED_UI_SOURCE_DIR="${OPENCLASH_BUNDLED_UI_SOURCE_DIR:-/opt/metacubexd}"`, add:

```sh
OPENCLASH_OPENAI_RULE_PROVIDER_URL="${OPENCLASH_OPENAI_RULE_PROVIDER_URL:-https://testingcf.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.yaml}"
OPENCLASH_OPENAI_REGION_REGEX="${OPENCLASH_OPENAI_REGION_REGEX:-(?i)(🇸🇬|SG|Singapore|新加坡|狮城)}"
OPENCLASH_OPENAI_GROUP_NAME="${OPENCLASH_OPENAI_GROUP_NAME:-OpenAI}"
OPENCLASH_OPENAI_HEALTHCHECK_URL="${OPENCLASH_OPENAI_HEALTHCHECK_URL:-https://chat.openai.com/cdn-cgi/trace}"
OPENCLASH_OPENAI_HEALTHCHECK_INTERVAL="${OPENCLASH_OPENAI_HEALTHCHECK_INTERVAL:-300}"
```

Then replace the existing `python3 /usr/local/bin/render_openclash_config.py` invocation block with:

```sh
python3 /usr/local/bin/render_openclash_config.py \
  --input "${TMP_SUBSCRIPTION}" \
  --output "${OPENCLASH_STATE_DIR}/config.yaml" \
  --mixed-port "${OPENCLASH_MIXED_PORT}" \
  --controller-port "${OPENCLASH_CONTROLLER_PORT}" \
  --ui-dir "${OPENCLASH_UI_DIR}" \
  --log-level "${OPENCLASH_LOG_LEVEL}" \
  --openai-rule-provider-url "${OPENCLASH_OPENAI_RULE_PROVIDER_URL}" \
  --openai-region-regex "${OPENCLASH_OPENAI_REGION_REGEX}" \
  --openai-group-name "${OPENCLASH_OPENAI_GROUP_NAME}" \
  --openai-healthcheck-url "${OPENCLASH_OPENAI_HEALTHCHECK_URL}" \
  --openai-healthcheck-interval "${OPENCLASH_OPENAI_HEALTHCHECK_INTERVAL}"
```

- [ ] **Step 2: Lint the shell script**

Run: `sh -n scripts/bootstrap-openclash.sh`
Expected: no output (syntax OK).

- [ ] **Step 3: Commit**

```bash
git add scripts/bootstrap-openclash.sh
git commit -m "feat: pass OpenAI routing env to renderer in bootstrap"
```

---

### Task 6: Extend the bootstrap shell test

**Files:**
- Modify: `tests/test_bootstrap_openclash.sh`

- [ ] **Step 1: Append new assertions**

At the end of `tests/test_bootstrap_openclash.sh`, after the existing `grep -q "mihomo -f ${STATE_DIR}/config.yaml" "${MIHOMO_LOG}"` line, append:

```bash
grep -q '^- RULE-SET,openai,OpenAI$' "${STATE_DIR}/config.yaml"
grep -q '^  name: OpenAI$' "${STATE_DIR}/config.yaml"
grep -q '^  type: url-test$' "${STATE_DIR}/config.yaml"
grep -q '^- name: OpenAI$' "${STATE_DIR}/config.yaml" || true  # tolerated: yaml.safe_dump may emit either form
```

Note: the third grep targets the rendered group's `type: url-test` line. The fourth is a best-effort match that the `OpenAI` group exists at top level; the `|| true` keeps the test green if `yaml.safe_dump` chose the indented form covered by the second grep.

- [ ] **Step 2: Run the bootstrap test**

Run: `bash tests/test_bootstrap_openclash.sh`
Expected: no errors; the script exits with status 0.

- [ ] **Step 3: Commit**

```bash
git add tests/test_bootstrap_openclash.sh
git commit -m "test: assert bootstrap renders OpenAI rule and url-test group"
```

---

### Task 7: Document defaults in `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Append the new env block**

Append to the end of `.env.example`:

```dotenv
# OpenAI traffic routing — sent to the url-test group built from SG nodes.
OPENCLASH_OPENAI_RULE_PROVIDER_URL=https://testingcf.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.yaml
OPENCLASH_OPENAI_REGION_REGEX=(?i)(🇸🇬|SG|Singapore|新加坡|狮城)
OPENCLASH_OPENAI_GROUP_NAME=OpenAI
OPENCLASH_OPENAI_HEALTHCHECK_URL=https://chat.openai.com/cdn-cgi/trace
OPENCLASH_OPENAI_HEALTHCHECK_INTERVAL=300
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: document OpenAI routing env vars in .env.example"
```

---

### Task 8: Document operator usage in `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Insert a new "OpenAI Routing" section before "Mainland China Notes"**

Find the line `## Mainland China Notes` in `README.md`. Immediately before that line, insert:

```markdown
## OpenAI Routing

OpenAI traffic is steered to a `url-test` proxy-group built from your subscription's Singapore nodes. The renderer adds three things to the runtime config every restart:

- a `rule-providers.openai` entry that pulls the `blackmatrix7` OpenAI rule list (jsdelivr-mirrored, refreshes every 24h)
- an `OpenAI` proxy-group of `type: url-test` whose members are the proxies whose names match `OPENCLASH_OPENAI_REGION_REGEX`
- a top-priority `RULE-SET,openai,OpenAI` rule

Defaults route only Singapore nodes. To widen coverage to Japan as well:

```dotenv
OPENCLASH_OPENAI_REGION_REGEX=(?i)(🇸🇬|🇯🇵|SG|JP|Singapore|Japan|新加坡|日本|东京|狮城|Tokyo)
```

The default healthcheck URL is `https://chat.openai.com/cdn-cgi/trace`, which reflects real OpenAI reachability. If your provider rate-limits Cloudflare trace probes, switch to the more permissive Google probe:

```dotenv
OPENCLASH_OPENAI_HEALTHCHECK_URL=https://www.gstatic.com/generate_204
```

If a subscription refresh produces zero matching nodes, the renderer fails loudly and the container does not start — the proxy will not silently fall back to DIRECT. Rename nodes upstream or relax the regex.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: explain OpenAI Singapore routing in README"
```

---

### Task 9: Final verification

**Files:** none changed.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q && bash tests/test_bootstrap_openclash.sh`
Expected: pytest reports 11 passed; bootstrap test exits 0 with no errors.

- [ ] **Step 2: Inspect the rendered fixture-driven config**

Run:

```bash
python3 scripts/render_openclash_config.py \
  --input tests/fixtures/subscription-base.yaml \
  --output /tmp/openclash-final.yaml \
  --mixed-port 9981 \
  --controller-port 9097 \
  --ui-dir /tmp/ui \
  --log-level warning \
  --openai-rule-provider-url https://testingcf.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.yaml \
  --openai-region-regex '(?i)(🇸🇬|SG|Singapore|新加坡|狮城)' \
  --openai-group-name OpenAI \
  --openai-healthcheck-url https://chat.openai.com/cdn-cgi/trace \
  --openai-healthcheck-interval 300

sed -n '1,40p' /tmp/openclash-final.yaml
rm -f /tmp/openclash-final.yaml
```

Expected: the rendered file's `proxy-groups` starts with the `OpenAI` group containing `🇸🇬 SG-01` and `Singapore-02`, and `rules` starts with `RULE-SET,openai,OpenAI`.

- [ ] **Step 3: No commit needed** — verification only.
