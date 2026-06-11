"""Tests for the data-driven asset catalog (prices.json)."""

from __future__ import annotations

from ktok.engine.assets import (
    ASSETS,
    PRICES_PATH,
    Asset,
    Provider,
    Tier,
    asset_by_id,
    load_assets,
)


def test_prices_json_exists_and_loads():
    assert PRICES_PATH.exists(), "prices.json must ship next to assets.py"
    assets = load_assets()
    assert assets, "catalog must not be empty"
    assert all(isinstance(a, Asset) for a in assets)


def test_module_catalog_matches_loader():
    # ASSETS is just load_assets() run at import time.
    assert [a.id for a in ASSETS] == [a.id for a in load_assets()]


def test_ids_are_unique():
    ids = [a.id for a in ASSETS]
    assert len(ids) == len(set(ids))


def test_fable_is_in_catalog():
    fable = asset_by_id("fable")
    assert fable.provider is Provider.ANTHROPIC
    assert fable.tier is Tier.FLAGSHIP
    assert fable.base_price_chf_per_kt > 0


def test_known_assets_still_present():
    # the ids the rest of the code / tests rely on must stay
    for asset_id in ("opus", "sonnet", "haiku", "gpt5", "gem_pro"):
        assert asset_by_id(asset_id).id == asset_id


def test_optional_keys_fall_back_to_defaults():
    # haiku omits demand_sensitivity in prices.json -> dataclass default 0.6
    assert asset_by_id("haiku").demand_sensitivity == 0.6
