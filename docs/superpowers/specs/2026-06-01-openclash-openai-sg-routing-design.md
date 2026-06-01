# OpenAI Traffic Routed Through Singapore Nodes — Design

Date: 2026-06-01
Status: Approved (pending user spec review)

## 1. Goal

Route OpenAI-related traffic through proxies that come from the Singapore region only. The selection happens at deployment-render time, so subscription refreshes never silently drop the routing.

Non-goals:

- Routing for other AI vendors (Claude, Gemini, etc.). Out of scope; the same shape can be added later if needed.
- TUN-mode integration, transparent proxy, or any change to host-level networking.
- Mutating the upstream subscription file in place.

## 2. Why renderer-side, not subscription-side

The deployment owns the runtime contract — ports, allow-lan, geox-url, log-level, and now traffic policy for OpenAI. Putting it in `render_openclash_config.py` means:

- A subscription refresh that comes with new node names but no `OpenAI` group still gets the routing applied.
- Operators do not need to coordinate with the subscription provider.
- The behavior is testable in pytest without standing up `mihomo`.

## 3. Configuration interface

Five new env vars, all with defaults, exposed through `.env.example`, `bootstrap-openclash.sh`, and the renderer CLI:

```dotenv
OPENCLASH_OPENAI_RULE_PROVIDER_URL=https://testingcf.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.yaml
OPENCLASH_OPENAI_REGION_REGEX=(?i)(🇸🇬|SG|Singapore|新加坡|狮城)
OPENCLASH_OPENAI_GROUP_NAME=OpenAI
OPENCLASH_OPENAI_HEALTHCHECK_URL=https://chat.openai.com/cdn-cgi/trace
OPENCLASH_OPENAI_HEALTHCHECK_INTERVAL=300
```

Notes:

- The default regex matches Singapore only. Operators who want JP as a fallback edit env, not code.
- The healthcheck URL defaults to OpenAI's own trace endpoint so url-test reflects real OpenAI reachability. Operators who hit CF rate-limiting can switch to `https://www.gstatic.com/generate_204`.
- Interval is in seconds; mihomo convention.

## 4. Renderer behavior

`render_config(...)` gains five parameters: `openai_rule_provider_url`, `openai_region_regex`, `openai_group_name`, `openai_healthcheck_url`, `openai_healthcheck_interval`.

Steps, in order:

1. Compile the regex. An invalid regex must surface as an error (the `re.error` is acceptable; the renderer does not need to wrap it).
2. Iterate `rendered["proxies"]` and collect every entry whose `name` matches. Empty result → `raise ValueError("no proxies match OPENCLASH_OPENAI_REGION_REGEX")`.
3. If a proxy-group with `name == openai_group_name` already exists in `rendered["proxy-groups"]`, `raise ValueError` — never silently overwrite.
4. Inject `rule-providers.openai`:
   ```yaml
   type: http
   behavior: classical
   format: yaml
   url: <openai_rule_provider_url>
   path: ./ruleset/openai.yaml
   interval: 86400
   ```
   The provider key is the literal string `openai`, independent of `openai_group_name`, because the rule reference uses this key.
5. Prepend the OpenAI group at index 0 of `proxy-groups`:
   ```yaml
   - name: <openai_group_name>
     type: url-test
     proxies: [<matched node names, in subscription order>]
     url: <openai_healthcheck_url>
     interval: <openai_healthcheck_interval>
     tolerance: 50
   ```
6. Prepend `RULE-SET,openai,<openai_group_name>` at index 0 of `rules`.

The CLI parser (`_parse_args`) and `main()` are extended to thread the same five values through. `bootstrap-openclash.sh` reads the env vars and passes them as flags. None of the values are `require_env` — they all have defaults baked into the bootstrap script.

## 5. Error and edge cases

| Scenario | Behavior |
|---|---|
| No SG nodes in subscription | `ValueError` from renderer; bootstrap exits non-zero; container restarts with visible error in logs |
| Rule-provider URL unreachable at mihomo runtime | mihomo logs the error; matches existing geox-url behavior; renderer does not pre-fetch |
| Invalid regex in env | `re.error` propagates; bootstrap exits non-zero |
| Subscription already defines a group named `OpenAI` | `ValueError`; operator must rename or set `OPENCLASH_OPENAI_GROUP_NAME` |
| Subscription already defines a `rule-providers.openai` | `ValueError`; same reason |

## 6. Testing

### `tests/fixtures/subscription-base.yaml`

Extend to at least 3 proxies covering the regex shapes:

- `🇸🇬 SG-01` (emoji + code)
- `日本-东京-01` (Japanese, must NOT match the SG regex)
- `US-LA-01` (clearly out)

Plus a corresponding `proxy-groups` entry that references them, so the file stays a valid Clash config.

### `tests/test_render_openclash_config.py`

New cases:

- `OpenAI` group exists at `proxy-groups[0]`, `type == "url-test"`, `proxies` contains only the SG node names.
- `rules[0] == "RULE-SET,openai,OpenAI"`.
- `rule-providers.openai.url` equals the injected URL; `interval == 86400`; `behavior == "classical"`.
- Healthcheck `url` and `interval` on the group match what was passed in.
- Empty match set → `ValueError` with the documented message fragment.
- Pre-existing `OpenAI` group → `ValueError`.
- Pre-existing `rule-providers.openai` → `ValueError`.
- Existing tests for deployment-owned fields and section preservation continue to pass with the extended fixture.

### `tests/test_bootstrap_openclash.sh`

- Add `grep -q '^- RULE-SET,openai,OpenAI$' "${STATE_DIR}/config.yaml"`.
- Add a check that the rendered file contains an `OpenAI` proxy-group with `type: url-test`.
- Fixture already contains an SG-named node so bootstrap doesn't fail.

## 7. Documentation

Add a "OpenAI Routing" section to `README.md`:

- Default behavior (Singapore only, url-test auto-picks lowest latency).
- How to widen to JP by editing `OPENCLASH_OPENAI_REGION_REGEX`.
- How to switch healthcheck URL when hitting CF limits.
- Note that rule-provider refreshes every 24h; restart container to force-refresh.
- Note that this is deployment-level config and survives subscription refreshes.

## 8. Out of scope

- Per-vendor groups for Claude/Gemini. Same shape can be cloned later.
- Selecting nodes by latency at render time (mihomo's url-test handles this at runtime).
- Caching or mirroring the rule-provider file inside the image.
- UI/dashboard changes — metacubexd will pick up the new group automatically.
