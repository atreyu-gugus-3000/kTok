"""Asset catalog – the models you can trade on kTok.

Base prices are rough CHF/kToken estimates for output tokens as of early 2026.
They're a starting point, not financial advice. The engine multiplies them by
live signals to produce the market price.
"""

from dataclasses import dataclass
from enum import Enum


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


ASSETS: list[Asset] = [
    # Anthropic
    Asset(
        id="opus",
        display="AnCC opus",
        provider=Provider.ANTHROPIC,
        tier=Tier.FLAGSHIP,
        base_price_chf_per_kt=0.400,
        status_sensitivity=0.9,
        hype_sensitivity=0.7,
        volatility=0.025,
    ),
    Asset(
        id="sonnet",
        display="AnCC sonnet",
        provider=Provider.ANTHROPIC,
        tier=Tier.MID,
        base_price_chf_per_kt=0.120,
        status_sensitivity=0.8,
        hype_sensitivity=0.5,
        volatility=0.018,
    ),
    Asset(
        id="haiku",
        display="AnCC haiku",
        provider=Provider.ANTHROPIC,
        tier=Tier.CHEAP,
        base_price_chf_per_kt=0.040,
        status_sensitivity=0.6,
        hype_sensitivity=0.3,
        volatility=0.012,
    ),
    # OpenAI (fictional model names – it's a game)
    Asset(
        id="gpt5",
        display="oAI gpt5.4c",
        provider=Provider.OPENAI,
        tier=Tier.FLAGSHIP,
        base_price_chf_per_kt=0.200,
        status_sensitivity=0.85,
        hype_sensitivity=0.8,
        volatility=0.028,
    ),
    Asset(
        id="gpt5mini",
        display="oAI gpt5.4m",
        provider=Provider.OPENAI,
        tier=Tier.MID,
        base_price_chf_per_kt=0.080,
        status_sensitivity=0.75,
        hype_sensitivity=0.5,
        volatility=0.020,
    ),
    Asset(
        id="codex",
        display="oAI codex",
        provider=Provider.OPENAI,
        tier=Tier.MID,
        base_price_chf_per_kt=0.150,
        status_sensitivity=0.8,
        hype_sensitivity=0.6,
        volatility=0.022,
    ),
    # Google
    Asset(
        id="gem_pro",
        display="gGL gem2.5p",
        provider=Provider.GOOGLE,
        tier=Tier.FLAGSHIP,
        base_price_chf_per_kt=0.180,
        status_sensitivity=0.8,
        hype_sensitivity=0.6,
        volatility=0.024,
    ),
    Asset(
        id="gem_flash",
        display="gGL flash",
        provider=Provider.GOOGLE,
        tier=Tier.CHEAP,
        base_price_chf_per_kt=0.050,
        status_sensitivity=0.6,
        hype_sensitivity=0.4,
        volatility=0.015,
    ),
]


def asset_by_id(asset_id: str) -> Asset:
    for a in ASSETS:
        if a.id == asset_id:
            return a
    raise KeyError(f"no asset with id {asset_id!r}")
