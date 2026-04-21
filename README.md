# kTok

A terminal game where you trade the leftover tokens from your AI CLI sessions.

```
◀ AnCC opus CHF 0.400/kT ↗1.80% │ oAI gpt5.4c CHF 0.200/kT ↘0.32% │ gGL flash CHF 0.050/kT ↗0.15% ▶
───────────────────────────────────────────────────────────────────────────────────────────────────
[d] asset │ [b] buy │ [s] sell │ [q] quit                          cash: CHF 1000.00  P&L: +2.3%
───────────────────────────────────────────────────────────────────────────────────────────────────
 Opus        +300 kT     CHF  12.01
 Sonnet      +800 kT     CHF   9.60
 Haiku       +40  GT     CHF   0.04
 Codex       500  kT     CHF   2.05
 Gemini fl.  20   kT     CHF   0.40
───────────────────────────────────────────────────────────────────────────────────────────────────
 14:32 🟢 Anthropic resolved: "Elevated errors on Messages API" → Opus +8%
 14:15 🟡 US market open → OpenAI demand +5%
```

## Concept

Fiction wrapper on real signals. Every model (Opus, Sonnet, Haiku, GPT-5.4, Gemini Flash, ...)
is a tradable asset. The price moves based on **real data**:

- **Status pages** (Anthropic, OpenAI, Google Cloud) – when a provider is **down**,
  tokens get cheaper (service unusable = less value). When it recovers, prices rebound.
  Outages are buying opportunities.
- **US worktime** – 09:00–17:00 PT = peak demand for US-based providers = prices up.
- **Hacker News frontpage** – hype signal. "Why we switched to Claude" in top 10 → Opus spike.
- **GitHub activity** – commits on AI repos as proxy for developer usage.
- **Random walk** – small brownian motion so the ticker never sits still.

Each day resets. You start with CHF 1000 cash, 0 tokens. At midnight your portfolio
is archived and you begin fresh – in parallel with your actual Claude Code daily reset.

## Status

**Phase 1 (in progress):** Price engine + signal fetchers.
**Phase 2 (next):** Textual TUI skeleton with live ticker.
**Phase 3 (later):** Trade loop, portfolio persistence, daily reset.

## Install

```bash
git clone https://github.com/<you>/kTok.git
cd kTok
pip install -e .
ktok
```

Requires Python 3.11+.

## Architecture

```
ktok/
├── engine/
│   ├── assets.py      # Model catalog (Opus, Sonnet, GPT-5, Gemini, …)
│   ├── signals.py     # Real-signal fetchers (status pages, HN, GitHub, time)
│   ├── pricing.py     # price = base × status_mult × demand_mult × hype_mult × walk
│   └── cache.py       # TTL cache so we don't hammer APIs
├── tui/
│   ├── app.py         # Textual app entry
│   ├── ticker.py      # Scrolling ticker widget
│   └── panels.py      # Inventory, trade form, event log
├── state/
│   ├── portfolio.py   # Daily-reset portfolio
│   └── history.py     # Archive past days for P&L history
└── main.py
```

## Why

Samuel wanted a small, playful private project next to the serious work-AI stuff.
4–6 lines in the terminal, minimal scope, real data behind a fictional market.
Softer than trading stocks, funnier than solitaire.

## License

MIT
