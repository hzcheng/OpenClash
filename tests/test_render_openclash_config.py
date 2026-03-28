from pathlib import Path

import pytest
import yaml

from scripts.render_openclash_config import render_config


def _load_fixture() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "subscription-base.yaml"
    with fixture_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_deployment_owned_fields_are_overridden() -> None:
    base_config = _load_fixture()

    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
    )

    assert rendered["mixed-port"] == 9981
    assert rendered["allow-lan"] is False
    assert rendered["external-controller"] == "0.0.0.0:9097"
    assert rendered["external-ui"] == "/var/lib/openclash/ui"
    assert rendered["log-level"] == "warning"


def test_subscription_sections_are_preserved() -> None:
    base_config = _load_fixture()

    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
    )

    assert rendered["proxies"] == base_config["proxies"]
    assert rendered["proxy-groups"] == base_config["proxy-groups"]
    assert rendered["rules"] == base_config["rules"]


@pytest.mark.parametrize("missing_key", ["proxies", "proxy-groups", "rules"])
def test_missing_required_sections_raise_value_error(missing_key: str) -> None:
    base_config = _load_fixture()
    base_config.pop(missing_key, None)

    with pytest.raises(ValueError, match="missing required Clash sections"):
        render_config(
            base_config,
            mixed_port=9981,
            controller_port=9097,
            ui_dir="/var/lib/openclash/ui",
            log_level="warning",
        )
