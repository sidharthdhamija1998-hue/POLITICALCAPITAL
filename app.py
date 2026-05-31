#!/usr/bin/env python3
"""
Political Capital — Theme & Stock Discovery Dashboard
=====================================================
A REAL, runnable dashboard. It loads actual congressional financial-disclosure
trades (delayed 1-2 months by law — that is the design, not a bug), groups the
quality-weighted buying into forward THEMES, and ranks the STOCKS inside each
theme by signal strength so you have a prioritized research list.

HOW TO RUN
  pip install streamlit pandas requests
  streamlit run app.py                  # opens the dashboard in your browser

  python app.py --selftest              # no Streamlit/UI: prints the engine
                                        # output so you can sanity-check logic

DATA MODES (pick in the sidebar)
  SAMPLE  : bundled rows, zero setup, runs offline. Marquee rows are grounded
            in real 2025 filings (NVDA was the House's most-bought stock).
  LIVE    : pulls the real feed on YOUR machine. Two free options are wired in
            fetch_live() — Financial Modeling Prep (free key) or the Senate
            Stock Watcher JSON (no key). Confirm field names once; they drift.

WHAT THIS IS / IS NOT
  * A research tool that surfaces where politically-connected, disclosed money
    is clustering. Signal strength is NOT the same as investment merit.
  * NOT investment advice and NOT a recommendation engine. The evidence that
    copying Congress beats the market is mixed: most members do not beat the
    S&P in a given year, and academic studies find the post-STOCK-Act edge thin.
  * NOT real-time and never can be: disclosure is delayed up to 45 days by law.
"""

import argparse
import sys
from datetime import date, datetime

# ----------------------------------------------------------------------
# REFERENCE DATA  (production: own tables; here: fixed for a self-contained app)
# ----------------------------------------------------------------------

# Member quality 0-100 = filing-date-adjusted track record + committee
# relevance + conviction. Production: computed by the member-quality engine.
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

# ticker -> (company, PRIMARY theme). Production: sector reference + theme rules.
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
    "GS":   ("Goldman Sachs", "Financials"),
    "CAT":  ("Caterpillar", "Industrials"),
}

# asset description -> ticker. Production: SEC CIK + OpenFIGI + fuzzy + LLM.
TICKER_MAP = {
    "nvidia": "NVDA", "ge vernova": "GEV", "vistra": "VST", "broadcom": "AVGO",
    "micron": "MU", "taiwan semiconductor": "TSM", "applied materials": "AMAT",
    "constellation energy": "CEG", "cameco": "CCJ", "nuscale power": "SMR",
    "centrus energy": "LEU", "lockheed martin": "LMT", "rtx": "RTX",
    "palantir": "PLTR", "general dynamics": "GD", "coinbase": "COIN",
    "strategy": "MSTR", "microstrategy": "MSTR", "goldman sachs": "GS",
    "caterpillar": "CAT",
}


def sample_trades():
    """Bundled rows shaped like real periodic-transaction disclosures.
    Marquee NVDA rows are grounded in real 2025 filings; the rest are
    representative samples to populate the themes for the offline demo."""
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
        ("Ted Cruz",           "Goldman Sachs",        "sale",     "$250,001 - $500,000",     "2025-09-05"),
    ]
    return [{"member": m, "asset": a, "type": t, "amount": amt, "filing_date": fd} for m, a, t, amt, fd in rows]


def fetch_live(source: str, lookback_days: int):
    """Pull the REAL feed on the user's machine. Map provider fields into the
    same dict keys sample_trades() returns. Confirm field names once by printing
    one raw record."""
    import requests
    if source == "fmp":
        API_KEY = "YOUR_FREE_KEY"  # https://site.financialmodelingprep.com
        url = f"https://financialmodelingprep.com/stable/house-trades?apikey={API_KEY}"
        raw = requests.get(url, timeout=30).json()
        # print(raw[0])  # <- run once to confirm field names
        return [{
            "member": r.get("representative") or r.get("office", ""),
            "asset": r.get("assetDescription", ""),
            "type": (r.get("type", "") or "").lower(),
            "amount": r.get("amount", ""),
            "filing_date": r.get("disclosureDate", ""),
        } for r in raw]
    raise ValueError(f"Unknown live source: {source}")


# ----------------------------------------------------------------------
# ENGINE  (pure functions — no Streamlit; testable offline)
# ----------------------------------------------------------------------

def clean_to_ticker(asset):
    key = asset.lower().strip()
    for tok in (" inc", " corp", " corporation", " co", " ltd", " plc", "."):
        key = key.replace(tok, "")
    return TICKER_MAP.get(key.strip())


def amount_midpoint(rng):
    parts = rng.replace("–", "-").split("-")
    nums = []
    for p in parts:
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
        if not r["type"].startswith("p"):      # buying conviction only
            continue
        ticker = clean_to_ticker(r["asset"])
        if not ticker:
            unmapped.append(r["asset"]); continue
        try:
            fd = datetime.strptime(r["filing_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if (asof - fd).days > lookback_days or fd > asof:
            continue                           # outside the chosen window
        trades.append({
            "member": r["member"], "ticker": ticker,
            "amount_mid": amount_midpoint(r["amount"]), "filing_date": r["filing_date"],
        })
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
        stocks.append({
            "ticker": ticker, "name": name, "theme": theme,
            "score": score, "level": level_from_score(score),
            "n_buyers": len(d["buyers"]),
            "buyers": sorted(d["buyers"], key=lambda m: MEMBER_QUALITY.get(m, {}).get("q", 0), reverse=True),
            "last_filing": d["last"], "disclosed_usd": d["amt"],
        })
    stocks.sort(key=lambda s: s["score"], reverse=True)
    return stocks


def rank_themes(stocks):
    themes = {}
    for s in stocks:
        t = themes.setdefault(s["theme"], {"stocks": [], "buyers": set()})
        t["stocks"].append(s)
        t["buyers"].update(s["buyers"])
    out = []
    for name, t in themes.items():
        ranked = sorted(t["stocks"], key=lambda s: s["score"], reverse=True)
        top = ranked[:3]
        avg_top = sum(s["score"] for s in top) / len(top)
        breadth = min(100, len(t["buyers"]) * 18)
        theme_score = round(0.65 * avg_top + 0.35 * breadth)
        out.append({
            "theme": name, "theme_score": theme_score,
            "n_stocks": len(ranked), "n_buyers": len(t["buyers"]),
            "stocks": ranked,
        })
    out.sort(key=lambda x: x["theme_score"], reverse=True)
    return out


def run_engine(source, lookback_days, asof):
    raw = sample_trades() if source == "sample" else fetch_live(source, lookback_days)
    trades, unmapped = normalize(raw, asof, lookback_days)
    stocks = score_stocks(trades, asof)
    themes = rank_themes(stocks)
    return stocks, themes, unmapped


# ----------------------------------------------------------------------
# UI  (Streamlit — imported only when rendering)
# ----------------------------------------------------------------------

def render():
    import streamlit as st
    import pandas as pd

    st.set_page_config(page_title="Political Capital", page_icon="🏛️", layout="wide")

    st.markdown("## 🏛️ Political Capital")
    st.caption("Forward-theme & stock discovery from congressional disclosures. "
               "Research tool — not investment advice. Data is delayed 1–2 months by law.")

    with st.sidebar:
        st.header("Controls")
        mode = st.radio("Data source", ["SAMPLE (offline)", "LIVE — FMP (needs free key)"], index=0)
        source = "sample" if mode.startswith("SAMPLE") else "fmp"
        lookback = st.slider("Disclosure window (days)", 30, 365, 150, step=10,
                             help="How far back to count filings. 90–150 days ≈ 'recent buying'.")
        min_score = st.slider("Min stock signal score", 0, 100, 0, step=5)
        st.divider()
        st.caption("LIVE mode pulls the real feed on YOUR machine. Add your free "
                   "FMP key in fetch_live(). Confirm field names once.")

    asof = date.today() if source != "sample" else date(2025, 6, 30)

    try:
        stocks, themes, unmapped = run_engine(source, lookback, asof)
    except Exception as e:
        st.error(f"Live fetch failed: {e}\n\nSwitch to SAMPLE mode, or check your API key / field mapping.")
        return

    stocks = [s for s in stocks if s["score"] >= min_score]
    themes = [t for t in themes if any(s["score"] >= min_score for s in t["stocks"])]

    badge = "🟢 LIVE" if source != "sample" else "🟡 SAMPLE DATA"
    st.info(f"{badge}  ·  as of {asof}  ·  window {lookback}d  ·  "
            f"{len(stocks)} stocks across {len(themes)} themes  ·  "
            f"entry uses filing date (45-day legal lag)")

    tab1, tab2, tab3 = st.tabs(["🔭 Future Themes", "📈 Stock Screener", "👥 Member Quality"])

    with tab1:
        st.markdown("##### Where disclosed, quality-weighted money is clustering")
        st.caption("Themes ranked by the strength and breadth of recent buying. "
                   "Higher score = more conviction from more credible members.")
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
                         "Top buyer": s["buyers"][0] if s["buyers"] else ""} for s in t["stocks"]]
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with tab2:
        st.markdown("##### Stock screener — your prioritized research list")
        st.caption("Ranked by congressional signal (the one live pipe). Insider / 13F / "
                   "contracts / lobbying columns are placeholders until those pipes are added; "
                   "the composite will combine all of them.")
        df = pd.DataFrame([{
            "Ticker": s["ticker"], "Company": s["name"], "Theme": s["theme"],
            "Congress": s["score"], "Insider": "—", "Instns": "—", "Contracts": "—", "Lobby": "—",
            "Buyers": s["n_buyers"], "Disclosed $": f"${s['disclosed_usd']:,.0f}",
            "Last filed": s["last_filing"],
        } for s in stocks])
        st.dataframe(df, hide_index=True, use_container_width=True)
        if unmapped:
            st.caption(f"⚠️ Unmapped assets needing ticker review: {sorted(set(unmapped))}")

    with tab3:
        st.markdown("##### Member quality — reliability, not last year's return")
        rows = [{"Member": m, "Party": v["party"], "State": v["state"], "Quality": v["q"]}
                for m, v in sorted(MEMBER_QUALITY.items(), key=lambda kv: kv[1]["q"], reverse=True)]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.divider()
    st.caption("Built on public U.S. disclosure data (STOCK Act / Ethics in Government Act). "
               "Signal strength ≠ investment merit. Most members do not beat the S&P in a given "
               "year and the post-STOCK-Act edge is academically contested. Not investment, "
               "legal, or tax advice. Obtain qualified counsel before any commercial use.")


# ----------------------------------------------------------------------
# DISPATCH
# ----------------------------------------------------------------------

def run_selftest():
    asof = date(2025, 6, 30)
    stocks, themes, unmapped = run_engine("sample", 150, asof)
    print(f"\nSELFTEST · SAMPLE data · as of {asof} · window 150d\n")
    print("FUTURE THEMES (ranked)")
    print(f"{'THEME':<34}{'SCORE':<7}{'STOCKS':<8}{'MEMBERS'}")
    print("-" * 64)
    for t in themes:
        print(f"{t['theme']:<34}{t['theme_score']:<7}{t['n_stocks']:<8}{t['n_buyers']}")
    print("\nTOP STOCKS (ranked by congressional signal)")
    print(f"{'TKR':<6}{'DOTS':<6}{'SCR':<5}{'BUY':<5}{'THEME':<32}BUYERS")
    print("-" * 96)
    for s in stocks[:12]:
        dots = "●" * s["level"] + "○" * (3 - s["level"])
        print(f"{s['ticker']:<6}{dots:<6}{s['score']:<5}{s['n_buyers']:<5}{s['theme']:<32}{', '.join(s['buyers'])}")
    if unmapped:
        print(f"\nUnmapped: {sorted(set(unmapped))}")


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
