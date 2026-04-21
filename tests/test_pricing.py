"""Tests for the pricing engine."""

from __future__ import annotations

from ktok.engine.assets import ASSETS, Provider, asset_by_id
from ktok.engine.pricing import PricingEngine
from ktok.engine.signals import HypeSnapshot, Signals, StatusSnapshot, TimeSnapshot


def _neutral_signals() -> Signals:
    return Signals(
        status={p: StatusSnapshot() for p in Provider},
        hype=HypeSnapshot(),
        time=TimeSnapshot(us_pt_worktime=False, us_et_worktime=False, eu_worktime=False),
    )


def test_prices_start_near_base():
    engine = PricingEngine(seed=42)
    for a in ASSETS:
        assert engine.prices[a.id] == a.base_price_chf_per_kt


def test_status_outage_drops_price():
    engine = PricingEngine(seed=42)
    down_signals = _neutral_signals()
    down_signals.status[Provider.ANTHROPIC] = StatusSnapshot(
        indicator="critical", description="Down"
    )

    # run many ticks to let the mean-reversion settle
    for _ in range(50):
        engine.tick(down_signals)

    opus = asset_by_id("opus")
    price = engine.prices["opus"]
    # critical drops raw mult to ~0.65; with flagship sensitivity 0.9 => ~0.685
    # allow a wide band because of random walk
    assert price < opus.base_price_chf_per_kt * 0.95
    assert price > opus.base_price_chf_per_kt * 0.3  # never below floor


def test_status_recovery_rebounds():
    engine = PricingEngine(seed=7)
    # first, drop
    down = _neutral_signals()
    down.status[Provider.ANTHROPIC] = StatusSnapshot(indicator="critical")
    for _ in range(50):
        engine.tick(down)
    low = engine.prices["opus"]

    # then recover
    up = _neutral_signals()
    for _ in range(50):
        engine.tick(up)
    recovered = engine.prices["opus"]
    assert recovered > low


def test_price_has_floor_and_ceiling():
    engine = PricingEngine(seed=1)
    signals = _neutral_signals()
    # hammer with critical everywhere for a long time
    for p in Provider:
        signals.status[p] = StatusSnapshot(indicator="critical")
    for _ in range(500):
        engine.tick(signals)
    for a in ASSETS:
        price = engine.prices[a.id]
        assert a.base_price_chf_per_kt * 0.3 <= price <= a.base_price_chf_per_kt * 3.0


def test_us_worktime_lifts_demand():
    engine_a = PricingEngine(seed=100)
    engine_b = PricingEngine(seed=100)
    off_hours = _neutral_signals()
    on_hours = _neutral_signals()
    on_hours.time = TimeSnapshot(us_pt_worktime=True, us_et_worktime=True)

    for _ in range(100):
        engine_a.tick(off_hours)
        engine_b.tick(on_hours)

    # on-hours engine should trend higher for flagship US assets
    assert engine_b.prices["gpt5"] > engine_a.prices["gpt5"]


def test_different_providers_react_independently():
    engine = PricingEngine(seed=11)
    signals = _neutral_signals()
    signals.status[Provider.OPENAI] = StatusSnapshot(indicator="critical")
    for _ in range(60):
        engine.tick(signals)

    opus = asset_by_id("opus")
    gpt5 = asset_by_id("gpt5")
    # OpenAI assets should be noticeably lower, Anthropic should not be heavily affected
    assert engine.prices["gpt5"] < gpt5.base_price_chf_per_kt * 0.95
    assert engine.prices["opus"] > opus.base_price_chf_per_kt * 0.85
