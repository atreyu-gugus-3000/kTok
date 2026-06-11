"""Asset catalog – the models you can trade on kTok.

The catalog lives in ``prices.json`` next to this module, not in code: base
prices, tiers and per-asset sensitivities are data you can edit without touching
Python. Base prices are rough CHF/kToken estimates for output tokens as of early
2026 – a starting point, not financial advice. The engine multiplies them by
live signals to produce the market price. See ``docs/market-realism.md``.
"""

import json
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path


class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class Tier(str, Enum):
    """Rough tier – flagship, mid, cheap. Controls how jumpy the price is."""
    FLAGSHIP = "flagship"
    MID = "mid"
    CHEAP = "cheap"


@dataclass(frozen=True)
class Asset:
    """A tradable model."""

    id: str                      # short ticker id, e.g. "opus"
    display: str                 # rendered name in ticker, e.g. "AnCC opus"
    provider: Provider
    tier: Tier
    base_price_chf_per_kt: float
    # How much this asset responds to each signal category (0..1).
    # Flagship models react more to status + hype; cheap models are sticky.
    status_sensitivity: float = 0.8
    demand_sensitivity: float = 0.6
    hype_sensitivity: float = 0.5
    volatility: float = 0.02     # sigma for the random walk per tick


PRICES_PATH = Path(__file__).with_name("prices.json")

# Optional keys an entry may carry; anything omitted falls back to the Asset
# dataclass default. Required keys (id/display/provider/tier/base price) have no
# default and must be present.
_OPTIONAL_KEYS = frozenset(
    f.name for f in fields(Asset)
) - {"id", "display", "provider", "tier", "base_price_chf_per_kt"}


def _asset_from_entry(entry: dict) -> Asset:
    """Build an Asset from one prices.json record, applying dataclass defaults."""
    return Asset(
        id=entry["id"],
        display=entry["display"],
        provider=Provider(entry["provider"]),
        tier=Tier(entry["tier"]),
        base_price_chf_per_kt=float(entry["base_price_chf_per_kt"]),
        **{k: entry[k] for k in _OPTIONAL_KEYS if k in entry},
    )


def load_assets(path: Path = PRICES_PATH) -> list[Asset]:
    """Load the tradable catalog from prices.json."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    assets = [_asset_from_entry(e) for e in raw["assets"]]
    ids = [a.id for a in assets]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate asset id in {path.name}: {ids}")
    return assets


ASSETS: list[Asset] = load_assets()


def asset_by_id(asset_id: str) -> Asset:
    for a in ASSETS:
        if a.id == asset_id:
            return a
    raise KeyError(f"no asset with id {asset_id!r}")
