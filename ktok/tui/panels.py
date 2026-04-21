"""Panels: inventory table, event log."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from ktok.engine.assets import ASSETS
from ktok.state.portfolio import Portfolio


class InventoryPanel(Static):
    DEFAULT_CSS = """
    InventoryPanel { height: auto; padding: 0 1; }
    """

    def render_portfolio(self, portfolio: Portfolio, prices: dict[str, float]) -> None:
        t = Table.grid(padding=(0, 2))
        t.add_column(justify="left")
        t.add_column(justify="right")
        t.add_column(justify="right")
        t.add_column(justify="right")
        for asset in ASSETS:
            h = portfolio.holding(asset.id)
            price = prices.get(asset.id, 0.0)
            value = h.ktokens * price
            if h.ktokens == 0:
                qty_txt = Text("·", style="dim")
                val_txt = Text("—", style="dim")
                pnl_txt = Text("", style="dim")
            else:
                qty_txt = Text(f"{h.ktokens:+.1f} kT")
                val_txt = Text(f"CHF {value:7.2f}")
                if h.avg_cost_chf_per_kt > 0:
                    pnl = (price - h.avg_cost_chf_per_kt) / h.avg_cost_chf_per_kt * 100
                    style = "green" if pnl > 0 else "red" if pnl < 0 else "white"
                    pnl_txt = Text(f"{pnl:+.1f}%", style=style)
                else:
                    pnl_txt = Text("")
            t.add_row(Text(f"{asset.display:<14}"), qty_txt, val_txt, pnl_txt)
        self.update(t)


class EventLogPanel(Static):
    DEFAULT_CSS = """
    EventLogPanel { height: auto; padding: 0 1; color: $text-muted; }
    """

    def __init__(self, max_events: int = 5) -> None:
        super().__init__("")
        self._events: deque[str] = deque(maxlen=max_events)

    def push(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        self._events.append(f"{ts}  {message}")
        self.update("\n".join(self._events))
