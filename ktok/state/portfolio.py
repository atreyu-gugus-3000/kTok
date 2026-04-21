"""Portfolio state.

Every day resets: CHF 1000 cash, 0 tokens. At midnight (local CET) the current
portfolio is archived, and a fresh one is created – in parallel with Samuel's
actual Claude Code daily reset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path

from ktok.engine.assets import ASSETS, asset_by_id

STARTING_CASH = 1000.0


@dataclass
class Holding:
    asset_id: str
    ktokens: float = 0.0        # signed, positive = long
    avg_cost_chf_per_kt: float = 0.0  # for P&L display


@dataclass
class Portfolio:
    day: date
    cash_chf: float = STARTING_CASH
    holdings: dict[str, Holding] = field(default_factory=dict)

    @classmethod
    def fresh(cls, day: date | None = None) -> "Portfolio":
        return cls(
            day=day or date.today(),
            cash_chf=STARTING_CASH,
            holdings={a.id: Holding(asset_id=a.id) for a in ASSETS},
        )

    def holding(self, asset_id: str) -> Holding:
        return self.holdings.setdefault(asset_id, Holding(asset_id=asset_id))

    # ---- trading ----

    def can_buy(self, asset_id: str, kt: float, price_chf_per_kt: float) -> bool:
        return kt > 0 and self.cash_chf >= kt * price_chf_per_kt - 1e-9

    def buy(self, asset_id: str, kt: float, price_chf_per_kt: float) -> None:
        if not self.can_buy(asset_id, kt, price_chf_per_kt):
            raise ValueError("insufficient cash")
        asset_by_id(asset_id)  # validate
        cost = kt * price_chf_per_kt
        h = self.holding(asset_id)
        new_total = h.ktokens + kt
        h.avg_cost_chf_per_kt = (
            (h.ktokens * h.avg_cost_chf_per_kt + kt * price_chf_per_kt) / new_total
            if new_total > 0
            else 0.0
        )
        h.ktokens = new_total
        self.cash_chf -= cost

    def can_sell(self, asset_id: str, kt: float) -> bool:
        return kt > 0 and self.holding(asset_id).ktokens + 1e-9 >= kt

    def sell(self, asset_id: str, kt: float, price_chf_per_kt: float) -> None:
        if not self.can_sell(asset_id, kt):
            raise ValueError("insufficient holdings")
        h = self.holding(asset_id)
        h.ktokens -= kt
        self.cash_chf += kt * price_chf_per_kt
        if h.ktokens < 1e-9:
            h.ktokens = 0.0
            h.avg_cost_chf_per_kt = 0.0

    # ---- valuation ----

    def total_value_chf(self, prices: dict[str, float]) -> float:
        v = self.cash_chf
        for h in self.holdings.values():
            v += h.ktokens * prices.get(h.asset_id, 0.0)
        return v

    def pnl_pct(self, prices: dict[str, float]) -> float:
        total = self.total_value_chf(prices)
        return (total - STARTING_CASH) / STARTING_CASH * 100.0

    # ---- persistence ----

    def to_json(self) -> str:
        return json.dumps(
            {
                "day": self.day.isoformat(),
                "cash_chf": self.cash_chf,
                "holdings": {k: asdict(v) for k, v in self.holdings.items()},
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, s: str) -> "Portfolio":
        data = json.loads(s)
        return cls(
            day=date.fromisoformat(data["day"]),
            cash_chf=data["cash_chf"],
            holdings={k: Holding(**v) for k, v in data["holdings"].items()},
        )


def default_state_dir() -> Path:
    return Path.home() / ".local" / "share" / "ktok"


def archive_portfolio(p: Portfolio, prices: dict[str, float], state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "day": p.day.isoformat(),
        "final_value_chf": p.total_value_chf(prices),
        "pnl_pct": p.pnl_pct(prices),
        "portfolio": json.loads(p.to_json()),
        "archived_at": datetime.now().isoformat(),
    }
    (state_dir / f"{p.day.isoformat()}.json").write_text(json.dumps(snapshot, indent=2))
