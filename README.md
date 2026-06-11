# kTok

A terminal game where you trade the leftover tokens from your AI CLI sessions.

```
$ ktok
──── kTok 2026-04-21 23:09 · Tag 2026-04-21 ────
              market                         depot
  AnCC opus   0.4329 ↗ +6.57%    opus    40.00 kT    17.31 CHF
  AnCC sonnet 0.1305 ↗ +6.02%    cash       —         4.49 CHF
  AnCC haiku  0.0422 ↗ +1.00%    total                21.80 CHF
  oAI gpt5.4c 0.2198 ↗ +8.29%    P&L                 +21.80 CHF
  oAI gpt5.4m 0.0842 ↘ -1.16%
  oAI codex   0.1665 ↗ +5.77%
  gGL gem2.5p 0.1927 ↘ -3.00%
  gGL flash   0.0514 ↘ -3.07%

events
  🟢 anthropic: minor → none (Elevated errors on Messages API resolved)
```

## Concept

Fiction wrapper on real signals. Every model (Opus, Sonnet, Haiku, GPT-5.4, Gemini Flash, ...)
is a tradable asset. The price moves based on **real data**:

- **Status pages** (Anthropic, OpenAI, Google Cloud) – when a provider is **down**,
  tokens get cheaper (service unusable = less value). When it recovers, prices rebound.
  Outages are buying opportunities.
- **US worktime** – 09:00–17:00 PT = peak demand for US-based providers = prices up.
- **Hacker News frontpage** – hype signal. "Why we switched to Claude" in top 10 → Opus spike.
- **Random walk** – small brownian motion so the ticker never sits still.

Each day resets. You start with CHF 0 cash and 0 tokens. You earn inventory
via `grant` (claiming leftover tokens from a real AI session). At midnight
your portfolio is archived and you begin fresh – in parallel with your actual
Claude Code daily reset.

## Install

```bash
git clone https://github.com/<you>/kTok.git
cd kTok
pip install -e .
ktok
```

Requires Python 3.11+.

## Commands

```bash
ktok                          # = ktok status (market + depot + events)
ktok ticker                   # one-liner, exit (feed this to your statusline)
ktok watch --every 5          # live one-liner, Ctrl-C out
ktok grant opus 50            # claim leftover kT from a real AI session
ktok buy sonnet 10
ktok sell opus 5
ktok portfolio                # depot only, no market
ktok history 14               # last 14 archived days
ktok reset --cash 100         # archive current, fresh start
ktok assets                   # list tradable assets
```

Starting cash defaults to `0`. You earn inventory via `grant` (manual for now;
later auto-parsed from `ccusage` / `claude /cost`) or set it explicitly via
`KTOK_STARTING_CASH=100 ktok reset`. State lives at `~/.local/share/ktok/`.

## Architecture

```
ktok/
├── engine/
│   ├── assets.py      # Model catalog (Opus, Sonnet, GPT-5, Gemini, …)
│   ├── signals.py     # Real-signal fetchers (status pages, HN, time)
│   ├── pricing.py     # price = base × status_mult × demand_mult × hype_mult × walk
│   └── cache.py       # TTL cache so we don't hammer APIs
├── state/
│   ├── portfolio.py   # Daily-reset portfolio
│   └── history.py     # Archive past days for P&L history
├── dev/
│   └── run_engine.py  # Headless engine runner (debug)
├── cli.py             # Inline CLI – subcommands + one-liner ticker
└── __main__.py        # `python -m ktok` entry
```

## Why

Samuel wanted a small, playful private project next to the serious work-AI stuff.
Minimal scope, real data behind a fictional market. Softer than trading stocks,
funnier than solitaire. Lives inline in your terminal, not in a fullscreen app.

## License

MIT
