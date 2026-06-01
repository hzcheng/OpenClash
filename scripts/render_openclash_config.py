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


if __name__ == "__main__":
    main()
