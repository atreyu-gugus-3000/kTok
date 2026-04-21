"""kTok Textual app.

Phase 2 skeleton: live ticker + inventory + event log. No trading yet – the
[b]/[s] keybinds are wired but stubbed so you can see where they plug in.
"""

from __future__ import annotations

import logging
from datetime import date

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from ktok.engine.pricing import PricingEngine
from ktok.engine.signals import SignalFetcher
from ktok.state.portfolio import Portfolio, archive_portfolio, default_state_dir
from ktok.tui.panels import EventLogPanel, InventoryPanel
from ktok.tui.ticker import Ticker

log = logging.getLogger("ktok.tui")


class StatusLine(Static):
    DEFAULT_CSS = "StatusLine { height: 1; background: $panel; padding: 0 1; }"


class KTokApp(App):
    CSS = """
    Screen { layout: vertical; }
    #ticker-row { height: 1; }
    #status-row { height: 1; }
    #main       { height: auto; }
    """

    BINDINGS = [
        ("q", "quit", "quit"),
        ("d", "choose_asset", "asset"),
        ("b", "buy", "buy"),
        ("s", "sell", "sell"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.engine = PricingEngine()
        self.fetcher = SignalFetcher()
        self.portfolio = Portfolio.fresh()
        self.ticker = Ticker()
        self.status_line = StatusLine("loading signals…")
        self.inventory = InventoryPanel()
        self.events = EventLogPanel(max_events=5)

    def compose(self) -> ComposeResult:
        yield self.ticker
        yield self.status_line
        with Vertical(id="main"):
            yield self.inventory
            yield self.events
        yield Footer()

    async def on_mount(self) -> None:
        # immediate first render
        await self._tick_signals()
        self._tick_prices()
        self._refresh_ui()
        # schedule tasks
        self.set_interval(1.0, self._on_price_tick)
        self.set_interval(30.0, self._on_signal_tick)
        self.set_interval(0.2, self.ticker.scroll_tick)
        self.set_interval(60.0, self._on_midnight_check)
        self.events.push("🎰 kTok booted. Markets open.")

    # ---- periodic tasks ----

    async def _on_signal_tick(self) -> None:
        await self._tick_signals()

    async def _tick_signals(self) -> None:
        try:
            self._signals = await self.fetcher.snapshot()
            for ev in self._signals.events:
                self.events.push(ev)
        except Exception as exc:
            log.exception("signal tick failed")
            self.events.push(f"⚠ signal fetch failed: {exc}")

    def _on_price_tick(self) -> None:
        self._tick_prices()
        self._refresh_ui()

    def _tick_prices(self) -> None:
        signals = getattr(self, "_signals", None)
        if signals is None:
            return
        quotes = self.engine.tick(signals)
        self.ticker.update_quotes(quotes)

    def _on_midnight_check(self) -> None:
        today = date.today()
        if today != self.portfolio.day:
            archive_portfolio(self.portfolio, self.engine.prices, default_state_dir())
            self.events.push(f"🌅 new day. archived {self.portfolio.day}. fresh CHF 1000.")
            self.portfolio = Portfolio.fresh(today)

    def _refresh_ui(self) -> None:
        self.inventory.render_portfolio(self.portfolio, self.engine.prices)
        total = self.portfolio.total_value_chf(self.engine.prices)
        pnl = self.portfolio.pnl_pct(self.engine.prices)
        pnl_sign = "+" if pnl >= 0 else ""
        self.status_line.update(
            f"[d] asset  [b] buy  [s] sell  [q] quit   "
            f"cash CHF {self.portfolio.cash_chf:.2f}   "
            f"total CHF {total:.2f}   P&L {pnl_sign}{pnl:.2f}%"
        )

    # ---- stubbed actions (Phase 3) ----

    async def action_choose_asset(self) -> None:
        self.events.push("choose asset: not implemented yet (Phase 3)")

    async def action_buy(self) -> None:
        self.events.push("buy: not implemented yet (Phase 3)")

    async def action_sell(self) -> None:
        self.events.push("sell: not implemented yet (Phase 3)")

    async def on_unmount(self) -> None:
        await self.fetcher.close()


def run() -> None:
    logging.basicConfig(level=logging.WARNING)
    KTokApp().run()
