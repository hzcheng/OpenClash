from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml


REQUIRED_SECTIONS = ("proxies", "proxy-groups", "rules")
GEOX_URLS = {
    "geoip": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geoip.dat",
    "geosite": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geosite.dat",
    "mmdb": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb",
}


def render_config(
    base_config: dict,
    *,
    mixed_port: int,
    controller_port: int,
    ui_dir: str,
    log_level: str,
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
    return rendered


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
    )

    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(rendered, handle, sort_keys=False)


if __name__ == "__main__":
    main()
