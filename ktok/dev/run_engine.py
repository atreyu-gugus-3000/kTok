"""Headless price-engine runner.

Runs the engine without the TUI and prints each tick as a line. Useful to
debug the pricing formula or verify signals are flowing before bothering with
the TUI. Run with:

    python -m ktok.dev.run_engine
"""

from __future__ import annotations

import asyncio
import signal
from datetime import datetime

from ktok.engine.pricing import PricingEngine
from ktok.engine.signals import SignalFetcher


async def main() -> None:
    fetcher = SignalFetcher()
    engine = PricingEngine()
    stop = asyncio.Event()

    def _on_sig(*_: object) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, _on_sig)

    print("kTok price engine – press Ctrl-C to stop")
    print("-" * 80)

    tick = 0
    try:
        while not stop.is_set():
            signals = await fetcher.snapshot()
            quotes = engine.tick(signals)
            tick += 1
            if tick % 5 == 1:  # every 5th tick print a header
                print()
                stamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{stamp}]  tick #{tick}")
                for provider, snap in signals.status.items():
                    flag = "✓" if snap.ok else "✗"
                    print(f"   status {provider.value:10s} {flag} {snap.indicator:10s} {snap.description}")
            line = "   "
            for q in quotes:
                arrow = q.direction
                line += f"{q.asset.id}:{q.price:.4f}{arrow}{q.change_pct:+.2f}%  "
            print(line)
            try:
                await asyncio.wait_for(stop.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
    finally:
        await fetcher.close()
        print("\nstopped.")


if __name__ == "__main__":
    asyncio.run(main())
