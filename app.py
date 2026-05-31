#!/usr/bin/env python3
"""
Political Capital — Theme & Stock Discovery Dashboard
=====================================================
Loads U.S. congressional financial-disclosure trades (delayed 1-2 months by
law), groups quality-weighted buying into forward THEMES, and ranks STOCKS so
you get a prioritized research list. Research tool — NOT investment advice.

RUN
  pip install streamlit pandas requests
  streamlit run app.py
  python app.py --selftest      # engine check, no UI

LIVE DATA (the safe way)
  Get a free key at financialmodelingprep.com. Put it in the app's
  Settings -> Secrets as:   FMP_API_KEY = "your_key_here"
  Then pick LIVE in the sidebar. The key never goes in this file or GitHub.
"""

import argparse
import sys
from datetime import date, datetime

# stores the first raw API record so the UI can show it for troubleshooting
_DEBUG_RAW = {}

# ----------------------------------------------------------------------
# REFERENCE DATA
# ----------------------------------------------------------------------
MEMBER_QUALITY = {
    "Nancy Pelosi":       {"q": 91, "party": "D", "state": "CA"},
    "Ron Wyden":          {"q": 70, "party": "D", "state": "OR"},
    "Terri Sewell":       {"q": 73, "party": "D", "state": "AL"},
    "Nick LaLota":        {"q": 67, "party": "R", "state": "NY"},
    "Bryan Steil":        {"q": 65, "party": "R", "state": "WI"},
    "Rick Scott":         {"q": 63, "party": "R", "state": "FL"},
    "Ted Cruz":           {"q": 60, "party": "R", "state": "TX"},
    "Thomas Suozzi":      {"q": 55, "party": "D", "state": "NY"},
    "Tom McClintock":     {"q": 56, "party": "R", "state": "CA"},
    "Donald Norcross":    {"q": 51, "party": "D", "state": "NJ"},
    "Marjorie T. Greene": {"q": 47, "party": "R", "state": "GA"},
    "Alex Padilla":       {"q": 44, "party": "D", "state": "CA"},
}

TICKER_INFO = {
    "NVDA": ("Nvidia", "AI Infrastructure & Power"),
    "GEV":  ("GE Vernova", "AI Infrastructure & Power"),
    "VST":  ("Vistra", "AI Infrastructure & Power"),
    "AVGO": ("Broadcom", "Semiconductors & Reshoring"),
    "MU":   ("Micron", "Semiconductors & Reshoring"),
    "TSM":  ("Taiwan Semiconductor", "Semiconductors & Reshoring"),
    "AMAT": ("Applied Materials", "Semiconductors & Reshoring"),
    "CEG":  ("Constellation Energy", "Nuclear & Uranium"),
    "CCJ":  ("Cameco", "Nuclear & Uranium"),
    "SMR":  ("NuScale Power", "Nuclear & Uranium"),
    "LEU":  ("Centrus Energy", "Nuclear & Uranium"),
    "LMT":  ("Lockheed Martin", "Defense & Autonomous Systems"),
    "RTX":  ("RTX Corp", "Defense & Autonomous Systems"),
    "PLTR": ("Palantir", "Defense & Autonomous Systems"),
    "GD":   ("General Dynamics", "Defense & Autonomous Systems"),
    "COIN": ("Coinbase", "Crypto & Digital-Asset Policy"),
    "MSTR": ("Strategy", "Crypto & Digital-Asset Policy"),
}

TICKER_MAP = {
    "nvidia": "NVDA", "ge vernova": "GEV", "vistra": "VST", "broadcom": "AVGO",
    "micron": "MU", "taiwan semiconductor": "TSM", "applied materials": "AMAT",
    "constellation energy": "CEG", "cameco": "CCJ", "nuscale power": "SMR",
    "centrus energy": "LEU", "lockheed martin": "LMT", "rtx": "RTX",
    "palantir": "PLTR", "general dynamics": "GD", "coinbase": "COIN",
    "strategy": "MSTR", "microstrategy": "MSTR",
}


def sample_trades():
    rows = [
        ("Nancy Pelosi",       "NVIDIA Corp",          "purchase", "$1,000,001 - $5,000,000", "2025-02-20"),
        ("Thomas Suozzi",      "NVIDIA",               "purchase", "$500,001 - $1,000,000",   "2025-04-10"),
        ("Marjorie T. Greene", "Nvidia",               "purchase", "$15,001 - $50,000",       "2025-03-30"),
        ("Bryan Steil",        "GE Vernova",           "purchase", "$50,001 - $100,000",      "2025-06-12"),
        ("Ron Wyden",          "Vistra",               "purchase", "$100,001 - $250,000",     "2025-05-05"),
        ("Tom McClintock",     "Vistra",               "purchase", "$15,001 - $50,000",       "2025-06-18"),
        ("Nick LaLota",        "Broadcom",             "purchase", "$50,001 - $100,000",      "2025-05-20"),
        ("Terri Sewell",       "Broadcom",             "purchase", "$50,001 - $100,000",      "2025-06-03"),
        ("Rick Scott",         "Micron",               "purchase", "$15,001 - $50,000",       "2025-05-25"),
        ("Ron Wyden",          "Constellation Energy", "purchase", "$50,001 - $100,000",      "2025-05-05"),
        ("Tom McClintock",     "Cameco",               "purchase", "$15,001 - $50,000",       "2025-06-18"),
        ("Rick Scott",         "NuScale Power",        "purchase", "$15,001 - $50,000",       "2025-06-05"),
        ("Nancy Pelosi",       "Palantir",             "purchase", "$250,001 - $500,000",     "2025-06-25"),
        ("Donald Norcross",    "Lockheed Martin",      "purchase", "$15,001 - $50,000",       "2025-05-12"),
        ("Nick LaLota",        "RTX",                  "purchase", "$15,001 - $50,000",       "2025-05-20"),
        ("Bryan Steil",        "General Dynamics",     "purchase", "$1,001 - $15,000",        "2025-06-12"),
        ("Marjorie T. Greene", "Coinbase",             "purchase", "$1,001 - $15,000",        "2025-04-05"),
        ("Rick Scott",         "Strategy",             "purchase", "$15,001 - $50,000",       "2025-05-27"),
    ]
    return [{"member": m, "asset": a, "ticker": None, "type": t, "amount": amt, "filing_date": fd}
            for m, a, t, amt, fd in rows]


def fetch_live(api_key, max_pages=3):
    """Real House disclosures from FMP's stable/house-latest endpoint.
    Maps fields defensively and stashes the first raw record for debugging."""
    import requests
    _DEBUG_RAW.clear()
    rows = []
    for page in range(max_pages):
        url = (f"https://financialmodelingprep.com/stable/house-latest"
               f"?page={page}&limit=100&apikey={api_key}")
        resp = requests.get(url, timeout=30)
        data = resp.json()
        if isinstance(data, dict):  # FMP returns a dict only on error
            raise RuntimeError(data.get("Error Message") or data.get("message") or str(data))
        if not data:
            break
        for i, r in enumerate(data):
            if page == 0 and i == 0:
                _DEBUG_RAW["first"] = r
            first = (r.get("firstName") or "").strip()
            last = (r.get("lastName") or "").strip()
            name = (f"{first} {last}".strip() or r.get("representative") or r.get("office") or "")
            rows.append({
                "member": name,
                "asset": r.get("assetDescription", "") or "",
                "ticker": ((r.get("symbol") or "").strip().upper() or None),
                "type": (r.get("type", "") or "").lower(),
                "amount": r.get("amount", "") or "",
                "filing_date": (r.get("disclosureDate") or r.get("dateRecieved") or "")[:10],
            })
    return rows


# ----------------------------------------------------------------------
# ENGINE (pure)
# ----------------------------------------------------------------------
def clean_to_ticker(asset):
    key = asset.lower().strip()
    for tok in (" inc", " corp", " corporation", " co", " ltd", " plc", "."):
        key = key.replace(tok, "")
    return TICKER_MAP.get(key.strip())


def amount_midpoint(rng):
    nums = []
    for p in rng.replace("\u2013", "-").split("-"):
        d = p.replace("$", "").replace(",", "").strip()
        if d.isdigit():
            nums.append(int(d))
    return sum(nums) // len(nums) if nums else 0


def conviction_factor(amt):
    if amt >= 1_000_000: return 1.0
    if amt >= 250_000:   return 0.85
    if amt >= 50_000:    return 0.65
    return 0.45


def recency_factor(filing_date, asof):
    fd = datetime.strptime(filing_date, "%Y-%m-%d").date()
    days = (asof - fd).days
    if days <= 90:  return 1.0
    if days <= 180: return 0.7
    if days <= 365: return 0.4
    return 0.2


def level_from_score(s):
    return 3 if s >= 70 else 2 if s >= 40 else 1 if s > 0 else 0


def normalize(raw_rows, asof, lookback_days):
    trades, unmapped = [], []
    for r in raw_rows:
        if not (r.get("type") or "").startswith("p"):
            continue
        ticker = r.get("ticker") or clean_to_ticker(r.get("asset", ""))
        if not ticker:
            unmapped.append(r.get("asset", "")); continue
        try:
            fd = datetime.strptime(r["filing_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if (asof - fd).days > lookback_days or fd > asof:
            continue
        trades.append({"member": r["member"], "ticker": ticker,
                       "amount_mid": amount_midpoint(r["amount"]), "filing_date": r["filing_date"]})
    return trades, unmapped


def score_stocks(trades, asof):
    agg = {}
    for t in trades:
        q = MEMBER_QUALITY.get(t["member"], {}).get("q", 30)
        contrib = (q / 100) * conviction_factor(t["amount_mid"]) * recency_factor(t["filing_date"], asof)
        d = agg.setdefault(t["ticker"], {"raw": 0.0, "buyers": {}, "last": "", "amt": 0})
        d["raw"] += contrib
        d["buyers"][t["member"]] = max(d["buyers"].get(t["member"], 0), round(contrib, 2))
        d["last"] = max(d["last"], t["filing_date"])
        d["amt"] += t["amount_mid"]
    stocks = []
    for ticker, d in agg.items():
        name, theme = TICKER_INFO.get(ticker, (ticker, "Other"))
        score = min(100, round(d["raw"] * 45))
        stocks.append({"ticker": ticker, "name": name, "theme": theme, "score": score,
                       "level": level_from_score(score), "n_buyers": len(d["buyers"]),
                       "buyers": sorted(d["buyers"], key=lambda m: MEMBER_QUALITY.get(m, {}).get("q", 0), reverse=True),
                       "last_filing": d["last"], "disclosed_usd": d["amt"]})
    stocks.sort(key=lambda s: s["score"], reverse=True)
    return stocks


def rank_themes(stocks):
    themes = {}
    for s in stocks:
        t = themes.setdefault(s["theme"], {"stocks": [], "buyers": set()})
        t["stocks"].append(s); t["buyers"].update(s["buyers"])
    out = []
    for name, t in themes.items():
        ranked = sorted(t["stocks"], key=lambda s: s["score"], reverse=True)
        top = ranked[:3]
        avg_top = sum(s["score"] for s in top) / len(top)
        breadth = min(100, len(t["buyers"]) * 18)
        out.append({"theme": name, "theme_score": round(0.65 * avg_top + 0.35 * breadth),
                    "n_stocks": len(ranked), "n_buyers": len(t["buyers"]), "stocks": ranked})
    out.sort(key=lambda x: x["theme_score"], reverse=True)
    return out


def run_engine(source, lookback_days, asof, api_key=None):
    raw = sample_trades() if source == "sample" else fetch_live(api_key)
    trades, unmapped = normalize(raw, asof, lookback_days)
    stocks = score_stocks(trades, asof)
    themes = rank_themes(stocks)
    return stocks, themes, unmapped


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------
def render():
    import streamlit as st
    import pandas as pd

    st.set_page_config(page_title="Political Capital", page_icon="\U0001F3DB", layout="wide")
    st.markdown("## \U0001F3DB Political Capital")
    st.caption("Forward-theme & stock discovery from congressional disclosures. "
               "Research tool — not investment advice. Data is delayed 1\u20132 months by law.")

    with st.sidebar:
        st.header("Controls")
        mode = st.radio("Data source", ["SAMPLE (offline)", "LIVE \u2014 FMP (real data)"], index=0)
        source = "sample" if mode.startswith("SAMPLE") else "fmp"
        lookback = st.slider("Disclosure window (days)", 30, 365, 150, step=10)
        min_score = st.slider("Min stock signal score", 0, 100, 0, step=5)
        st.divider()
        st.caption("LIVE reads your free FMP key from Settings \u2192 Secrets "
                   "(FMP_API_KEY). The key never touches your code.")

    api_key = None
    if source == "fmp":
        try:
            api_key = st.secrets["FMP_API_KEY"]
        except Exception:
            api_key = None
        if not api_key:
            st.warning("LIVE needs your free FMP key. Open this app's **Settings \u2192 Secrets** and add:\n\n"
                       "`FMP_API_KEY = \"your_key_here\"`\n\nthen reboot. Showing SAMPLE data meanwhile.")
            source = "fmp_nokey"

    asof = date.today() if source == "fmp" else date(2025, 6, 30)
    effective = "sample" if source in ("sample", "fmp_nokey") else "fmp"

    try:
        stocks, themes, unmapped = run_engine(effective, lookback, asof, api_key)
    except Exception as e:
        st.error(f"Live fetch failed: {e}")
        st.info("If the message mentions premium / legacy / 403, the congressional endpoint isn't on "
                "your free plan — tell me and we'll switch to a no-key source. Otherwise, open the raw "
                "record below and send me a screenshot so I can map the fields.")
        if _DEBUG_RAW.get("first"):
            with st.expander("\U0001F527 Raw API response (first record)"):
                st.json(_DEBUG_RAW["first"])
        return

    is_live = (effective == "fmp")
    badge = "\U0001F7E2 LIVE — real disclosures" if is_live else "\U0001F7E1 SAMPLE DATA"
    st.info(f"{badge}  ·  as of {asof}  ·  window {lookback}d  ·  {len(stocks)} stocks across "
            f"{len(themes)} themes  ·  entry uses filing date (45-day legal lag)")

    if is_live and _DEBUG_RAW.get("first"):
        with st.expander("\U0001F527 Raw API response (first record) — for troubleshooting"):
            st.json(_DEBUG_RAW["first"])

    stocks = [s for s in stocks if s["score"] >= min_score]
    themes = [t for t in themes if any(s["score"] >= min_score for s in t["stocks"])]

    tab1, tab2, tab3 = st.tabs(["\U0001F52D Future Themes", "\U0001F4C8 Stock Screener", "\U0001F465 Member Quality"])

    with tab1:
        st.markdown("##### Where disclosed, quality-weighted money is clustering")
        st.caption("Themes ranked by strength and breadth of recent buying.")
        if is_live:
            st.caption("Live note: only pre-classified tickers fall into named themes; everything else "
                       "shows as 'Other' until the theme map is expanded.")
        for t in themes:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"#### {t['theme']}")
                    st.caption(f"{t['n_stocks']} stocks · {t['n_buyers']} distinct members buying")
                with c2:
                    st.metric("Theme signal", t["theme_score"])
                rows = [{"Ticker": s["ticker"], "Company": s["name"], "Score": s["score"],
                         "Buyers": s["n_buyers"], "Last filed": s["last_filing"],
                         "Top buyer": s["buyers"][0] if s["buyers"] else ""} for s in t["stocks"][:10]]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with tab2:
        st.markdown("##### Stock screener — your prioritized research list")
        st.caption("Ranked by congressional signal (the one live pipe). Insider / 13F / contracts / "
                   "lobbying columns are placeholders until those pipes are added.")
        df = pd.DataFrame([{
            "Ticker": s["ticker"], "Company": s["name"], "Theme": s["theme"],
            "Congress": s["score"], "Insider": "\u2014", "Instns": "\u2014", "Contracts": "\u2014", "Lobby": "\u2014",
            "Buyers": s["n_buyers"], "Disclosed $": f"${s['disclosed_usd']:,.0f}", "Last filed": s["last_filing"],
        } for s in stocks])
        st.dataframe(df, hide_index=True, use_container_width=True)
        if is_live and unmapped:
            st.caption(f"\u26A0\uFE0F {len(set(unmapped))} asset names had no ticker and were skipped "
                       f"(e.g. {sorted(set(unmapped))[:5]}).")

    with tab3:
        st.markdown("##### Member quality — reliability, not last year's return")
        if is_live:
            st.caption("Live note: only the members in the quality table get a real score; others get a "
                       "neutral default weight until the table is expanded.")
        rows = [{"Member": m, "Party": v["party"], "State": v["state"], "Quality": v["q"]}
                for m, v in sorted(MEMBER_QUALITY.items(), key=lambda kv: kv[1]["q"], reverse=True)]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.divider()
    st.caption("Public U.S. disclosure data (STOCK Act / Ethics in Government Act). Signal strength "
               "\u2260 investment merit. Most members don't beat the S&P in a given year and the "
               "post-STOCK-Act edge is academically contested. Not investment, legal, or tax advice.")


def run_selftest():
    asof = date(2025, 6, 30)
    stocks, themes, unmapped = run_engine("sample", 150, asof)
    print(f"\nSELFTEST · SAMPLE · as of {asof} · window 150d\n")
    print("FUTURE THEMES")
    for t in themes:
        print(f"  {t['theme']:<32}{t['theme_score']:<5}{t['n_stocks']} stocks · {t['n_buyers']} members")
    print("\nTOP STOCKS")
    for s in stocks[:8]:
        dots = "\u25CF" * s["level"] + "\u25CB" * (3 - s["level"])
        print(f"  {s['ticker']:<6}{dots:<5}{s['score']:<4}{s['theme']:<30}{', '.join(s['buyers'])}")


def _in_streamlit():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_selftest()
    elif _in_streamlit():
        render()
    else:
        print("Run the dashboard:  streamlit run app.py")
        print("Test the engine:    python app.py --selftest")
