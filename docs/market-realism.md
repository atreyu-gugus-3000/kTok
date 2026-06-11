# kTok — realere Marktzahlen

Notiz, Stand 2026-06-11. Wie die Preise näher an die echte Welt kommen.

## Wo die Zahlen heute herkommen

- **Basispreise**: hartkodiert in `ktok/engine/assets.py` (`base_price_chf_per_kt`),
  grobe CHF/kToken-Schätzungen für *Output*-Tokens.
- **Signale (schon live!)**: `ktok/engine/signals.py` zieht echte Daten —
  Atlassian-Statuspages (Anthropic/OpenAI/Google), HN-Frontpage als Hype-Proxy,
  US-PT/ET- und EU-Worktime als Demand-Proxy.
- **Engine**: `pricing.py` = `base × status × demand × hype × random_walk`
  mit Mean-Reversion zur Basis. Die Mechanik ist solide — der *schwächste* Realismus
  steckt in den Basispreisen und im fiktiven Katalog.

## Hebel für mehr Realismus (nach Aufwand sortiert)

### 1. Basispreise an echte Preislisten ankern — **kleinster Aufwand, größter Effekt**
Die offiziellen API-Preise (USD pro 1M Tokens) sind öffentlich. In CHF/kToken umrechnen
(`USD/1M × fx ÷ 1000`) und als `base_price_chf_per_kt` eintragen. Optional ein
**Blended-Preis** statt nur Output: `0.2 × input + 0.8 × output` bildet typische
Coding-Sessions besser ab.
- Quelle: `docs.anthropic.com/.../pricing`, `openai.com/api/pricing`, `ai.google.dev/pricing`.
- Heute fix; sauberer wäre eine kleine `prices.json`, die man ohne Code-Edit pflegt.

### 2. Live-FX statt fixem CHF — klein
USD→CHF einmal pro Tag über einen Gratis-Endpoint (z.B. `exchangerate.host`,
`frankfurter.app`) durch den bestehenden `TTLCache` ziehen. Macht die CHF-Zahlen
tagesaktuell ohne große Änderung.

### 3. Echte Preis-*Änderungen* als Signal — mittel
Preissenkungen/-erhöhungen sind die realsten „Kursbewegungen" im LLM-Markt. Ein
Scraper/Changelog-Watcher (oder manuell gepflegte `prices.json` mit `effective_date`)
lässt den Basispreis bei einer echten Preisrunde sprunghaft umspringen statt nur zu
zittern. Das ist die ehrlichste Form von „Markt".

### 4. Mehr/echtere Signale — mittel
- **GitHub-Trending / npm-Downloads** der SDKs als Demand-Proxy pro Provider.
- **OpenRouter-Rankings** (`openrouter.ai/rankings`) — echte relative Nutzung pro Modell,
  fast ein direkter „Volumen"-Indikator. Stärkster Realismus-Gewinn unter den Signalen.
- **HN-Hype granularer**: nicht nur Top-10-Flag, sondern Score/Kommentarzahl gewichten.
- **Status-Historie**: nicht nur aktueller Indicator, sondern Incident-Häufigkeit der
  letzten 24 h → „Reliability"-Premium.

### 5. Provider-Korrelation & Marktindex — mittel
Echte Modelle korrelieren (eine GPT-Preissenkung drückt den ganzen Markt). Ein
gemeinsamer Marktfaktor + provider-spezifisches Beta macht Bewegungen plausibler als
heute, wo jedes Asset isoliert läuft.

## Fehlend: Fable

**Fable 5** (Anthropic, `claude-fable-5`) fehlt im Katalog. Ergänzen in
`ktok/engine/assets.py`, z.B.:

```python
Asset(
    id="fable",
    display="AnCC fable",
    provider=Provider.ANTHROPIC,
    tier=Tier.FLAGSHIP,          # bzw. eigener Tier, je nach Positionierung
    base_price_chf_per_kt=0.350, # PLATZHALTER — aus echter Preisliste füllen
    status_sensitivity=0.9,
    hype_sensitivity=0.75,
    volatility=0.026,
),
```
> `base_price_chf_per_kt` ist ein Platzhalter — vor dem Merge mit dem echten
> Fable-5-Output-Preis ersetzen. Display-Kürzel `AnCC fable` hält die Konvention.

## Weitere Vorschläge (über „realer" hinaus)

- **`prices.json` + Schema**: Katalog & Preise aus dem Code lösen → ohne Python-Edit pflegbar,
  testbar, diff-bar bei Preisrunden.
- **Stale-Badge im Ticker**: wenn ein Signal-Fetch fehlschlägt (Code kann das schon
  „fail-soft"), im UI markieren, statt still neutral zu tun.
- **Persistente Preis-Historie** → echte Sparkline/Charts statt nur ↗/↘ pro Tick.
- **„Real mode" vs „arcade mode"**: per Flag zwischen echten Signalen und einer rein
  synthetischen, schnelleren Vol für mehr Spielspaß umschalten.
- **Backtest-Seed**: Engine mit fixem Seed + aufgezeichneten Signalen → reproduzierbare
  Markttage für Tests und Vergleich von Strategien.
