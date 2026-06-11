"""kTok — inline CLI. No fullscreen, just print-and-exit commands.

Portfolio persistent als JSON, Subcommands fuer Aktionen, One-Liner fuer
Claude-Code-Statusline.

    ktok                    # = ktok status
    ktok status             # market + depot + events
    ktok ticker             # one-liner (fuer statusline scripts)
    ktok watch [--every N]  # live one-liner, Ctrl-C raus
    ktok buy opus 10        # trade at current market price
    ktok sell sonnet 5
    ktok grant opus 50      # claim leftover kT from a real AI session
    ktok portfolio          # depot only, no market
    ktok history [n]        # last n archived days
    ktok reset [--cash CHF] # archive current, start fresh
    ktok assets             # list tradable assets

Starting cash ist 0. Du bekommst Kapital durch `grant` (faktisch: "hier sind die
Rest-Tokens meiner letzten echten Session") oder ueber `reset --cash`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, datetime

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from ktok.engine.assets import ASSETS, asset_by_id
from ktok.engine.pricing import PricingEngine, Quote
from ktok.engine.signals import SignalFetcher, Signals
from ktok.state.portfolio import Portfolio, archive_portfolio, default_state_dir

console = Console()
STARTING_CASH = float(os.environ.get("KTOK_STARTING_CASH", "0.0"))
STATE_FILE = default_state_dir() / "current.json"


# ---------- persistence ----------

def load() -> Portfolio:
    if not STATE_FILE.exists():
        return _fresh(STARTING_CASH)
    p = Portfolio.from_json(STATE_FILE.read_text())
    if p.day != date.today():
        # neuer Tag -> archivieren (best-effort ohne Live-Preise) und frisch
        archive_portfolio(p, {}, default_state_dir())
        return _fresh(STARTING_CASH)
    return p


def save(p: Portfolio) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(p.to_json())


def _fresh(cash: float) -> Portfolio:
    p = Portfolio.fresh()
    p.cash_chf = cash
    return p


# ---------- market ----------

def market(engine: PricingEngine | None = None) -> tuple[dict[str, Quote], Signals]:
    """Holt Signals + laesst Engine 3 ticks warmlaufen. Synchron nach aussen."""
    eng = engine or PricingEngine()
    sig = asyncio.run(_snapshot())
    for _ in range(3):
        eng.tick(sig)
    quotes = {q.asset.id: q for q in eng.tick(sig)}
    return quotes, sig


async def _snapshot() -> Signals:
    f = SignalFetcher()
    try:
        return await f.snapshot()
    finally:
        await f.close()


def prices(qs: dict[str, Quote]) -> dict[str, float]:
    return {aid: q.price for aid, q in qs.items()}


# ---------- formatting ----------

def color(pct: float) -> str:
    return "green" if pct > 0 else "red" if pct < 0 else "dim"


def signed(v: float, prec: int = 2) -> str:
    return f"{'+' if v >= 0 else ''}{v:.{prec}f}"


def pct_cell(q: Quote) -> Text:
    return Text(f"{q.direction}{signed(q.change_pct):>7}%", style=color(q.change_pct))


def _market_table(qs: dict[str, Quote]) -> Table:
    t = Table(title="market", title_style="bold cyan", padding=(0, 1))
    t.add_column("asset")
    t.add_column("CHF/kT", justify="right")
    t.add_column("change", justify="right")
    for a in ASSETS:
        q = qs[a.id]
        t.add_row(a.display, f"{q.price:.4f}", pct_cell(q))
    return t


def _depot_table(p: Portfolio, qs: dict[str, Quote]) -> Table:
    px = prices(qs) if qs else {}
    t = Table(title="depot", title_style="bold magenta", padding=(0, 1))
    t.add_column("asset")
    t.add_column("kT", justify="right")
    t.add_column("CHF value", justify="right")
    held = [h for h in p.holdings.values() if h.ktokens > 1e-9]
    if not held:
        t.add_row("[dim]empty[/dim]", "", "")
    for h in held:
        val = h.ktokens * px.get(h.asset_id, 0.0)
        t.add_row(h.asset_id, f"{h.ktokens:,.2f}", f"{val:,.2f}")
    total = p.total_value_chf(px)
    pnl = total - STARTING_CASH
    pnl_style = f"bold {color(pnl)}"
    t.add_section()
    t.add_row("cash", "—", f"{p.cash_chf:,.2f}", style="dim")
    t.add_row("total", "", Text(f"{total:,.2f}", style="bold"))
    t.add_row("P&L", "", Text(f"{signed(pnl)} CHF", style=pnl_style))
    return t


def render_status(qs: dict[str, Quote], p: Portfolio) -> Table:
    outer = Table.grid(padding=(0, 3))
    outer.add_column()
    outer.add_column()
    outer.add_row(_market_table(qs), _depot_table(p, qs))
    return outer


def render_ticker(qs: dict[str, Quote], p: Portfolio) -> Text:
    """Ein-Zeilen-Ticker fuer Statusline / Watch-Mode."""
    px = prices(qs)
    total = p.total_value_chf(px)
    pnl = total - STARTING_CASH
    line = Text()
    for i, a in enumerate(ASSETS):
        q = qs[a.id]
        c = color(q.change_pct)
        if i:
            line.append(" ", "dim")
        line.append(f"{a.id} ", "bold")
        line.append(f"{q.price:.3f}", c)
        line.append(q.direction, c)
    line.append("  │  ", "dim")
    line.append(f"CHF {total:,.2f} ", "bold")
    line.append(signed(pnl), color(pnl))
    return line


# ---------- commands ----------

def cmd_status(args: argparse.Namespace) -> int:
    p = load()
    qs, sig = market()
    console.rule(f"[bold]kTok[/] [dim]{datetime.now():%Y-%m-%d %H:%M} · Tag {p.day}[/]")
    console.print(render_status(qs, p))
    if sig.events:
        console.print()
        console.print("[bold yellow]events[/]")
        for e in sig.events[-5:]:
            console.print(f"  {e}")
    elif sig.hype.ok and sig.hype.top_ai_headline:
        console.print(f"\n[dim]HN says:[/] {sig.hype.top_ai_headline}")
    return 0


def cmd_ticker(args: argparse.Namespace) -> int:
    p = load()
    qs, _ = market()
    console.print(render_ticker(qs, p), soft_wrap=True, highlight=False, markup=False)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    eng = PricingEngine()
    p = load()

    def frame() -> Text:
        qs, _ = market(eng)
        return render_ticker(qs, p)

    with Live(frame(), console=console, refresh_per_second=4, transient=False) as live:
        try:
            while True:
                time.sleep(args.every)
                live.update(frame())
        except KeyboardInterrupt:
            pass
    return 0


def cmd_buy(args: argparse.Namespace) -> int:
    return _trade(args, buying=True)


def cmd_sell(args: argparse.Namespace) -> int:
    return _trade(args, buying=False)


def _trade(args: argparse.Namespace, buying: bool) -> int:
    asset_by_id(args.asset)  # validate or raise
    p = load()
    qs, _ = market()
    price = qs[args.asset].price
    op = p.buy if buying else p.sell
    try:
        op(args.asset, args.kt, price)
    except ValueError as e:
        console.print(f"[red]refused:[/] {e}")
        return 1
    save(p)
    verb = "bought" if buying else "sold"
    total = args.kt * price
    console.print(
        f"[{'green' if buying else 'yellow'}]{verb}[/] {args.kt:,.2f} kT "
        f"{args.asset} @ CHF {price:.4f} = CHF {total:,.2f}   "
        f"[dim]cash now[/] CHF {p.cash_chf:,.2f}"
    )
    return 0


def cmd_grant(args: argparse.Namespace) -> int:
    """'Hier sind die Rest-Tokens aus meiner echten AI-Session.'

    Faktisch ein Geschenk ans Depot: Tokens rein, avg_cost=0, kein Cash-Abzug.
    Spaeter automatisierbar (ccusage parsen etc.), fuer jetzt manuell.
    """
    asset_by_id(args.asset)
    p = load()
    h = p.holding(args.asset)
    total_before = h.ktokens
    h.ktokens += args.kt
    # avg cost zieht runter weil Gratis-Tokens reinkommen
    h.avg_cost_chf_per_kt = (
        h.avg_cost_chf_per_kt * total_before / h.ktokens if h.ktokens > 0 else 0.0
    )
    save(p)
    console.print(
        f"[green]granted[/] {args.kt:,.2f} kT {args.asset}   "
        f"[dim]holding now[/] {h.ktokens:,.2f} kT"
    )
    return 0


def cmd_portfolio(args: argparse.Namespace) -> int:
    p = load()
    qs, _ = market()
    console.print(_depot_table(p, qs))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    d = default_state_dir()
    files = sorted(f for f in d.glob("*.json") if f.name != "current.json")
    files = files[-args.n:]
    if not files:
        console.print("[dim]no archive yet[/]")
        return 0
    t = Table(title=f"last {len(files)} days", title_style="bold")
    t.add_column("day")
    t.add_column("final CHF", justify="right")
    t.add_column("P&L", justify="right")
    for f in files:
        data = json.loads(f.read_text())
        pnl = data.get("pnl_pct", 0.0)
        t.add_row(
            data.get("day", f.stem),
            f"{data.get('final_value_chf', 0):.2f}",
            Text(f"{signed(pnl)}%", style=color(pnl)),
        )
    console.print(t)
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    p = load()
    qs, _ = market()
    archive_portfolio(p, prices(qs), default_state_dir())
    save(_fresh(args.cash))
    console.print(f"[green]fresh start.[/] cash CHF {args.cash:.2f}. los geht's.")
    return 0


def cmd_assets(args: argparse.Namespace) -> int:
    t = Table(title="tradable", title_style="bold")
    for c in ("id", "display", "provider", "tier", "base CHF/kT"):
        t.add_column(c)
    for a in ASSETS:
        t.add_row(a.id, a.display, a.provider.value, a.tier.value,
                  f"{a.base_price_chf_per_kt:.4f}")
    console.print(t)
    return 0


# ---------- argparse ----------

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ktok", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd")

    for name, fn in (
        ("status", cmd_status), ("ticker", cmd_ticker),
        ("portfolio", cmd_portfolio), ("assets", cmd_assets),
    ):
        sub.add_parser(name).set_defaults(func=fn)

    w = sub.add_parser("watch")
    w.add_argument("--every", type=float, default=5.0, metavar="SEC")
    w.set_defaults(func=cmd_watch)

    for name, fn in (("buy", cmd_buy), ("sell", cmd_sell), ("grant", cmd_grant)):
        s = sub.add_parser(name)
        s.add_argument("asset")
        s.add_argument("kt", type=float)
        s.set_defaults(func=fn)

    h = sub.add_parser("history")
    h.add_argument("n", nargs="?", type=int, default=7)
    h.set_defaults(func=cmd_history)

    r = sub.add_parser("reset")
    r.add_argument("--cash", type=float, default=STARTING_CASH)
    r.set_defaults(func=cmd_reset)

    return p


def run() -> None:
    args = _parser().parse_args()
    if not getattr(args, "func", None):
        args.func = cmd_status
    sys.exit(args.func(args))


if __name__ == "__main__":
    run()
