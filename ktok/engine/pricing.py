"""Pricing engine.

Formula:

    price = base
          × status_multiplier   (provider up/down affects its own assets)
          × demand_multiplier   (US / EU worktime bumps)
          × hype_multiplier     (HN frontpage mentions)
          × random_walk         (tiny per-tick jitter so ticker is alive)

All multipliers are bounded. status_multiplier < 1 during outages (tokens
cheaper when service is unusable) and > 1 as service rebounds to healthy.
Each asset has its own sensitivities so flagships move more than cheap models.

The random walk is deterministic-ish per asset: each asset carries its own
running walk state so we don't reset it every tick. This lives in a simple
mutable state dict on the engine instance.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ktok.engine.assets import ASSETS, Asset, Provider, Tier
from ktok.engine.signals import STATUS_MULTIPLIER, Signals


@dataclass
class Quote:
    asset: Asset
    price: float       # CHF per kToken
    change_pct: float  # change vs last tick
    direction: str     # ↗, ↘, →


class PricingEngine:
    """Stateful engine: holds the current price for each asset and steps it per tick."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._prices: dict[str, float] = {a.id: a.base_price_chf_per_kt for a in ASSETS}
        self._last_prices: dict[str, float] = dict(self._prices)
        # running multiplicative drift per asset – lets trends emerge
        self._drift: dict[str, float] = {a.id: 1.0 for a in ASSETS}

    @property
    def prices(self) -> dict[str, float]:
        return dict(self._prices)

    def tick(self, signals: Signals) -> list[Quote]:
        """Advance every asset by one tick using the current signal snapshot."""
        quotes: list[Quote] = []
        for asset in ASSETS:
            new_price = self._compute(asset, signals)
            prev = self._last_prices[asset.id]
            change = (new_price - prev) / prev if prev > 0 else 0.0
            direction = "↗" if change > 0.0005 else "↘" if change < -0.0005 else "→"
            self._last_prices[asset.id] = self._prices[asset.id]
            self._prices[asset.id] = new_price
            quotes.append(
                Quote(asset=asset, price=new_price, change_pct=change * 100, direction=direction)
            )
        return quotes

    # ---- components ----

    def _compute(self, asset: Asset, signals: Signals) -> float:
        status_mult = self._status_mult(asset, signals)
        demand_mult = self._demand_mult(asset, signals)
        hype_mult = self._hype_mult(asset, signals)
        walk = self._random_walk(asset)

        # tiny mean-reversion toward base so prices don't drift forever
        current = self._prices[asset.id]
        target = asset.base_price_chf_per_kt * status_mult * demand_mult * hype_mult
        reverted = current * 0.7 + target * 0.3
        price = reverted * walk
        # hard floor/ceiling so nothing goes negative or moonshots absurdly
        floor = asset.base_price_chf_per_kt * 0.3
        ceiling = asset.base_price_chf_per_kt * 3.0
        return max(floor, min(ceiling, price))

    def _status_mult(self, asset: Asset, signals: Signals) -> float:
        snap = signals.status.get(asset.provider)
        if snap is None or not snap.ok:
            return 1.0
        raw = STATUS_MULTIPLIER.get(snap.indicator, 1.0)
        # scale deviation from 1.0 by sensitivity
        return 1.0 + (raw - 1.0) * asset.status_sensitivity

    def _demand_mult(self, asset: Asset, signals: Signals) -> float:
        t = signals.time
        bump = 1.0
        # US providers (Anthropic + OpenAI + Google) all demand-bump during US worktime
        if asset.provider in (Provider.ANTHROPIC, Provider.OPENAI, Provider.GOOGLE):
            if t.us_pt_worktime or t.us_et_worktime:
                bump *= 1.0 + 0.15 * asset.demand_sensitivity
        # Anthropic gets a small EU worktime bump too (lots of EU devs)
        if asset.provider is Provider.ANTHROPIC and t.eu_worktime:
            bump *= 1.0 + 0.05 * asset.demand_sensitivity
        return bump

    def _hype_mult(self, asset: Asset, signals: Signals) -> float:
        h = signals.hype
        if not h.ok:
            return 1.0
        bump = 1.0
        provider_hype = {
            Provider.ANTHROPIC: h.claude_in_top10,
            Provider.OPENAI: h.gpt_in_top10,
            Provider.GOOGLE: h.gemini_in_top10,
        }
        if provider_hype.get(asset.provider):
            tier_scale = {Tier.FLAGSHIP: 1.0, Tier.MID: 0.6, Tier.CHEAP: 0.3}[asset.tier]
            bump *= 1.0 + 0.10 * asset.hype_sensitivity * tier_scale
        return bump

    def _random_walk(self, asset: Asset) -> float:
        # log-normal step, tiny sigma, so the ticker keeps breathing
        step = math.exp(self._rng.gauss(0.0, asset.volatility))
        # nudge drift gently toward 1.0 so walks don't run away
        self._drift[asset.id] = 0.995 * self._drift[asset.id] + 0.005
        return step
