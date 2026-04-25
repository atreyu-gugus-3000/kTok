"""Scrolling ticker widget.

Renders one line of rotating quotes, like the stock ticker at the bottom of a
financial news channel. Colors: green for up, red for down.
"""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ktok.engine.pricing import Quote


class Ticker(Static):
    DEFAULT_CSS = """
    Ticker {
        height: 1;
        background: $boost;
        color: $text;
    }
    """

    offset: reactive[int] = reactive(0)

    def __init__(self) -> None:
        super().__init__("")
        self._quotes: list[Quote] = []

    def update_quotes(self, quotes: list[Quote]) -> None:
        self._quotes = quotes
        self._refresh_text()

    def scroll_tick(self) -> None:
        self.offset += 1
        self._refresh_text()

    def _refresh_text(self) -> None:
        if not self._quotes:
            self.update("")
            return
        parts: list[Text] = []
        for q in self._quotes:
            color = "green" if q.change_pct > 0 else "red" if q.change_pct < 0 else "white"
            sign = "+" if q.change_pct > 0 else ""
            t = Text.assemble(
                (f"{q.asset.display} ", "bold"),
                (f"CHF {q.price:.4f}/kT ", "white"),
                (f"{q.direction}{sign}{q.change_pct:.2f}% ", color),
                ("│ ", "dim"),
            )
            parts.append(t)

        # concatenate and rotate by offset so it scrolls
        full = Text()
        for p in parts:
            full.append_text(p)
        width = self.size.width or 80
        s = full.plain
        if len(s) <= width:
            self.update(full)
            return
        o = self.offset % len(s)
        rotated_plain = s[o:] + "  •  " + s[:o]
        # simple rotation loses color spans – re-colorize by re-rendering from offset
        # For skeleton, plain rotating text is fine; Phase 2 can do richer rendering.
        self.update(Text(rotated_plain[:width]))
