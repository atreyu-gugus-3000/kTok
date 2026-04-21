"""Signal fetchers.

Every function returns a small snapshot object that `pricing.py` reads. All
network calls go through the TTL cache so the loop can tick every second
without DDoSing anyone.

Fail-soft: if a fetch errors, we return a neutral snapshot so the game keeps
running. The event log surfaces failures so you know when a signal is stale.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import httpx

from ktok.engine.assets import Provider
from ktok.engine.cache import TTLCache

log = logging.getLogger("ktok.signals")

# Atlassian Statuspage – all three providers use the same shape
STATUS_URLS: dict[Provider, str] = {
    Provider.ANTHROPIC: "https://status.claude.com/api/v2/summary.json",
    Provider.OPENAI: "https://status.openai.com/api/v2/summary.json",
    Provider.GOOGLE: "https://status.cloud.google.com/incidents.json",
}

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

# map statuspage indicators to a service-health multiplier.
# Down = tokens cheaper (service unusable). Recovery = rebound.
STATUS_MULTIPLIER: dict[str, float] = {
    "none": 1.00,      # all good
    "minor": 0.95,     # slight degradation
    "major": 0.80,     # significant outage
    "critical": 0.65,  # severe outage – fire-sale on this provider's tokens
}

PACIFIC = ZoneInfo("America/Los_Angeles")
EASTERN = ZoneInfo("America/New_York")
CET = ZoneInfo("Europe/Zurich")


@dataclass
class StatusSnapshot:
    indicator: str = "none"     # none|minor|major|critical
    description: str = "Operational"
    last_incident: str | None = None
    ok: bool = True             # False if the fetch itself failed


@dataclass
class HypeSnapshot:
    claude_in_top10: bool = False
    gpt_in_top10: bool = False
    gemini_in_top10: bool = False
    top_ai_headline: str | None = None
    ok: bool = True


@dataclass
class TimeSnapshot:
    utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    us_pt_worktime: bool = False   # 09-17 Pacific weekday
    us_et_worktime: bool = False
    eu_worktime: bool = False

    @classmethod
    def now(cls) -> "TimeSnapshot":
        utc = datetime.now(timezone.utc)
        pt = utc.astimezone(PACIFIC)
        et = utc.astimezone(EASTERN)
        eu = utc.astimezone(CET)
        return cls(
            utc=utc,
            us_pt_worktime=_is_worktime(pt),
            us_et_worktime=_is_worktime(et),
            eu_worktime=_is_worktime(eu),
        )


def _is_worktime(dt: datetime) -> bool:
    return dt.weekday() < 5 and 9 <= dt.hour < 17


@dataclass
class Signals:
    """Everything pricing.py needs to compute a tick."""

    status: dict[Provider, StatusSnapshot] = field(default_factory=dict)
    hype: HypeSnapshot = field(default_factory=HypeSnapshot)
    time: TimeSnapshot = field(default_factory=TimeSnapshot.now)
    events: list[str] = field(default_factory=list)  # human-readable, for the event log


class SignalFetcher:
    """Fetches all signals with per-source TTLs."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            timeout=5.0,
            headers={"User-Agent": "kTok/0.1 (+https://github.com/)"},
        )
        self._cache = TTLCache()
        self._previous_status: dict[Provider, str] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def snapshot(self) -> Signals:
        """Build a full signal snapshot. Cached per source."""
        signals = Signals(time=TimeSnapshot.now())

        for provider in Provider:
            signals.status[provider] = await self._cache.get_or_fetch(
                key=f"status:{provider.value}",
                ttl_seconds=60,
                fetch=lambda p=provider: self._fetch_status(p),
            )

        signals.hype = await self._cache.get_or_fetch(
            key="hype:hn",
            ttl_seconds=300,
            fetch=self._fetch_hype,
        )

        signals.events = self._diff_status_events(signals.status)
        return signals

    # ---------------- Status ----------------

    async def _fetch_status(self, provider: Provider) -> StatusSnapshot:
        url = STATUS_URLS[provider]
        try:
            r = await self._client.get(url)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("status fetch failed for %s: %s", provider.value, exc)
            return StatusSnapshot(ok=False)

        # Google uses a different shape (list of incidents, no rollup indicator).
        if provider is Provider.GOOGLE:
            return self._parse_google(data)
        return self._parse_statuspage(data)

    @staticmethod
    def _parse_statuspage(data: dict) -> StatusSnapshot:
        status = data.get("status", {})
        indicator = status.get("indicator", "none") or "none"
        description = status.get("description", "Operational")
        incidents = data.get("incidents") or []
        last = incidents[0]["name"] if incidents else None
        return StatusSnapshot(
            indicator=indicator, description=description, last_incident=last, ok=True
        )

    @staticmethod
    def _parse_google(data: list) -> StatusSnapshot:
        """Google Cloud: list of incidents. We only care about AI-ish ongoing ones."""
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(hours=2)
        worst = "none"
        severity_rank = {"none": 0, "minor": 1, "major": 2, "critical": 3}
        latest_name: str | None = None
        for inc in data if isinstance(data, list) else []:
            # only count ongoing or very recent, and only if it mentions AI/Vertex/Gemini
            end_str = inc.get("end")
            affected = (inc.get("affected_products") or [])
            affected_names = " ".join(p.get("title", "") for p in affected).lower()
            if not any(k in affected_names for k in ("vertex", "gemini", "ai")):
                continue
            # still active or ended within the last 2h
            is_active = end_str is None
            if not is_active:
                try:
                    end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                except Exception:
                    end_dt = now
                if end_dt < recent_cutoff:
                    continue
            sev = (inc.get("severity") or "none").lower()
            # Google uses "medium"/"high" etc.; map roughly
            sev = {"high": "major", "medium": "minor", "low": "minor"}.get(sev, sev)
            if severity_rank.get(sev, 0) > severity_rank.get(worst, 0):
                worst = sev
                latest_name = inc.get("external_desc") or inc.get("name")
        return StatusSnapshot(
            indicator=worst,
            description="Operational" if worst == "none" else f"Google AI: {worst}",
            last_incident=latest_name,
            ok=True,
        )

    def _diff_status_events(
        self, current: dict[Provider, StatusSnapshot]
    ) -> list[str]:
        """Emit human-readable events when a provider's status indicator changes."""
        events: list[str] = []
        for provider, snap in current.items():
            prev = self._previous_status.get(provider)
            if prev is not None and prev != snap.indicator:
                direction = "🔴" if STATUS_MULTIPLIER.get(snap.indicator, 1) < STATUS_MULTIPLIER.get(prev, 1) else "🟢"
                events.append(
                    f"{direction} {provider.value}: {prev} → {snap.indicator}"
                    + (f" ({snap.last_incident})" if snap.last_incident else "")
                )
            self._previous_status[provider] = snap.indicator
        return events

    # ---------------- Hype ----------------

    async def _fetch_hype(self) -> HypeSnapshot:
        try:
            r = await self._client.get(HN_TOP_URL)
            r.raise_for_status()
            ids = r.json()[:10]
        except Exception as exc:
            log.warning("HN top fetch failed: %s", exc)
            return HypeSnapshot(ok=False)

        titles: list[str] = []
        for item_id in ids:
            try:
                ir = await self._client.get(HN_ITEM_URL.format(id=item_id))
                if ir.status_code == 200:
                    t = (ir.json() or {}).get("title")
                    if t:
                        titles.append(t)
            except Exception:
                continue

        joined = " | ".join(titles).lower()
        snap = HypeSnapshot(
            claude_in_top10="claude" in joined or "anthropic" in joined,
            gpt_in_top10="gpt" in joined or "openai" in joined,
            gemini_in_top10="gemini" in joined or "google ai" in joined,
            ok=True,
        )
        # pick one hype headline to surface
        for t in titles:
            low = t.lower()
            if any(k in low for k in ("claude", "anthropic", "gpt", "openai", "gemini")):
                snap.top_ai_headline = t
                break
        return snap
