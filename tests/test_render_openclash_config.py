from pathlib import Path

import pytest
import yaml

from scripts.render_openclash_config import render_config

OPENAI_KWARGS = dict(
    openai_rule_provider_url="https://example.com/openai.yaml",
    openai_region_regex=r"(?i)(🇸🇬|SG|Singapore|新加坡|狮城)",
    openai_group_name="OpenAI",
    openai_healthcheck_url="https://chat.openai.com/cdn-cgi/trace",
    openai_healthcheck_interval=300,
)


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
        **OPENAI_KWARGS,
    )

    assert rendered["mixed-port"] == 9981
    assert rendered["allow-lan"] is True
    assert rendered["bind-address"] == "*"
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
        **OPENAI_KWARGS,
    )

    assert rendered["proxies"] == base_config["proxies"]
    # proxy-groups gains the injected OpenAI group at index 0; original groups follow
    original_group_names = {g["name"] for g in base_config["proxy-groups"]}
    rendered_group_names = {g["name"] for g in rendered["proxy-groups"]}
    assert original_group_names.issubset(rendered_group_names)
    # rules gains the OpenAI RULE-SET at index 0; original rules follow
    assert rendered["rules"][1:] == base_config["rules"]


def test_renderer_pins_geodata_downloads_to_jsdelivr_urls() -> None:
    base_config = _load_fixture()

    rendered = render_config(
        base_config,
        mixed_port=9981,
        controller_port=9097,
        ui_dir="/var/lib/openclash/ui",
        log_level="warning",
        **OPENAI_KWARGS,
    )

    assert rendered["geo-auto-update"] is False
    assert rendered["geox-url"] == {
        "geoip": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geoip.dat",
        "geosite": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/geosite.dat",
        "mmdb": "https://testingcf.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@release/country.mmdb",
    }


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
            **OPENAI_KWARGS,
        )


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
