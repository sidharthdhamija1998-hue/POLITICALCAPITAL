#!/usr/bin/env python3
"""
Political Capital — Theme & Stock Discovery Dashboard
Loads real U.S. congressional disclosures (delayed 1-2 months by law), groups
quality-weighted buying into forward themes + market sectors, and ranks stocks.
Research tool — NOT investment advice.

RUN:  pip install streamlit pandas requests ; streamlit run app.py
LIVE: put a free FMP key in Settings -> Secrets as  FMP_API_KEY = "your_key"
"""
import argparse, sys
from datetime import date, datetime

_DEBUG_RAW = {}

MEMBER_QUALITY = {
    "Nancy Pelosi": {"q": 91, "party": "D", "state": "CA"},
    "Ron Wyden": {"q": 70, "party": "D", "state": "OR"},
    "Terri Sewell": {"q": 73, "party": "D", "state": "AL"},
    "Nick LaLota": {"q": 67, "party": "R", "state": "NY"},
    "Bryan Steil": {"q": 65, "party": "R", "state": "WI"},
    "Rick Scott": {"q": 63, "party": "R", "state": "FL"},
    "Ted Cruz": {"q": 60, "party": "R", "state": "TX"},
    "Thomas Suozzi": {"q": 55, "party": "D", "state": "NY"},
    "Tom McClintock": {"q": 56, "party": "R", "state": "CA"},
    "Donald Norcross": {"q": 51, "party": "D", "state": "NJ"},
    "Marjorie T. Greene": {"q": 47, "party": "R", "state": "GA"},
    "Alex Padilla": {"q": 44, "party": "D", "state": "CA"},
}
DEFAULT_Q = 50  # neutral weight for members without a researched score

# Curated forward themes (the thematic layer)
TICKER_INFO = {
    "NVDA": ("Nvidia", "AI Infrastructure & Power"), "GEV": ("GE Vernova", "AI Infrastructure & Power"),
    "VST": ("Vistra", "AI Infrastructure & Power"), "AVGO": ("Broadcom", "Semiconductors & Reshoring"),
    "MU": ("Micron", "Semiconductors & Reshoring"), "TSM": ("Taiwan Semiconductor", "Semiconductors & Reshoring"),
    "AMAT": ("Applied Materials", "Semiconductors & Reshoring"), "CEG": ("Constellation Energy", "Nuclear & Uranium"),
    "CCJ": ("Cameco", "Nuclear & Uranium"), "SMR": ("NuScale Power", "Nuclear & Uranium"),
    "LEU": ("Centrus Energy", "Nuclear & Uranium"), "LMT": ("Lockheed Martin", "Defense & Autonomous Systems"),
    "RTX": ("RTX Corp", "Defense & Autonomous Systems"), "PLTR": ("Palantir", "Defense & Autonomous Systems"),
    "GD": ("General Dynamics", "Defense & Autonomous Systems"), "COIN": ("Coinbase", "Crypto & Digital-Asset Policy"),
    "MSTR": ("Strategy", "Crypto & Digital-Asset Policy"),
}

# Broad market sectors for everything else (no API call needed)
SECTOR_MAP = {
    # Communication Services
    "T": "Communication Services", "VZ": "Communication Services", "GOOGL": "Communication Services",
    "GOOG": "Communication Services", "META": "Communication Services", "NFLX": "Communication Services",
    "DIS": "Communication Services", "CMCSA": "Communication Services", "TMUS": "Communication Services",
    # Consumer Discretionary
    "HD": "Consumer Discretionary", "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "MCD": "Consumer Discretionary", "SBUX": "Consumer Discretionary",
    "LOW": "Consumer Discretionary", "TJX": "Consumer Discretionary", "BKNG": "Consumer Discretionary",
    "TGT": "Consumer Discretionary", "ABNB": "Consumer Discretionary", "F": "Consumer Discretionary",
    # Consumer Staples
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples", "COST": "Consumer Staples",
    "WMT": "Consumer Staples", "PM": "Consumer Staples", "MO": "Consumer Staples", "CL": "Consumer Staples",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "OXY": "Energy", "MPC": "Energy",
    "PSX": "Energy", "VLO": "Energy", "EOG": "Energy", "KMI": "Energy", "WMB": "Energy",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials", "GS": "Financials", "MS": "Financials",
    "C": "Financials", "BLK": "Financials", "SCHW": "Financials", "AXP": "Financials", "BX": "Financials",
    "V": "Financials", "MA": "Financials", "SPGI": "Financials", "PYPL": "Financials", "COF": "Financials",
    # Health Care
    "UNH": "Health Care", "JNJ": "Health Care", "LLY": "Health Care", "PFE": "Health Care", "MRK": "Health Care",
    "ABBV": "Health Care", "TMO": "Health Care", "ABT": "Health Care", "DHR": "Health Care", "MDT": "Health Care",
    "BMY": "Health Care", "AMGN": "Health Care", "GILD": "Health Care", "CVS": "Health Care",
    "MEDP": "Health Care", "ISRG": "Health Care", "VRTX": "Health Care",
    # Industrials
    "HON": "Industrials", "UNP": "Industrials", "CAT": "Industrials", "GE": "Industrials", "BA": "Industrials",
    "DE": "Industrials", "UPS": "Industrials", "MMM": "Industrials", "EMR": "Industrials", "ETN": "Industrials",
    "PH": "Industrials", "NOC": "Industrials", "CSX": "Industrials",
    # Information Technology
    "AAPL": "Information Technology", "MSFT": "Information Technology", "ORCL": "Information Technology",
    "CRM": "Information Technology", "ADBE": "Information Technology", "AMD": "Information Technology",
    "ACN": "Information Technology", "CSCO": "Information Technology", "INTC": "Information Technology",
    "QCOM": "Information Technology", "TXN": "Information Technology", "IBM": "Information Technology",
    "NOW": "Information Technology", "DELL": "Information Technology", "SMCI": "Information Technology",
    # Materials / Real Estate / Utilities
    "LIN": "Materials", "APD": "Materials", "SHW": "Materials", "FCX": "Materials", "NEM": "Materials",
    "SPG": "Real Estate", "PLD": "Real Estate", "AMT": "Real Estate", "EQIX": "Real Estate", "O": "Real Estate",
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "D": "Utilities", "AEP": "Utilities",
}

TICKER_MAP = {
    "nvidia": "NVDA", "ge vernova": "GEV", "vistra": "VST", "broadcom": "AVGO", "micron": "MU",
    "taiwan semiconductor": "TSM", "applied materials": "AMAT", "constellation energy": "CEG",
    "cameco": "CCJ", "nuscale power": "SMR", "centrus energy": "LEU", "lockheed martin": "LMT",
    "rtx": "RTX", "palantir": "PLTR", "general dynamics": "GD", "coinbase": "COIN",
    "strategy": "MSTR", "microstrategy": "MSTR",
}


def classify(ticker, asset_desc=""):
    """Forward theme if curated, else market sector, else Other."""
    if ticker in TICKER_INFO:
        return TICKER_INFO[ticker]
    name = (asset_desc or "").strip() or ticker
    return (name, SECTOR_MAP.get(ticker, "Other"))


def sample_trades():
    rows = [
        ("Nancy Pelosi", "NVIDIA Corp", "purchase", "$1,000,001 - $5,000,000", "2025-02-20"),
        ("Thomas Suozzi", "NVIDIA", "purchase", "$500,001 - $1,000,000", "2025-04-10"),
        ("Marjorie T. Greene", "Nvidia", "purchase", "$15,001 - $50,000", "2025-03-30"),
        ("Bryan Steil", "GE Vernova", "purchase", "$50,001 - $100,000", "2025-06-12"),
        ("Ron Wyden", "Vistra", "purchase", "$100,001 - $250,000", "2025-05-05"),
        ("Tom McClintock", "Vistra", "purchase", "$15,001 - $50,000", "2025-06-18"),
        ("Nick LaLota", "Broadcom", "purchase", "$50,001 - $100,000", "2025-05-20"),
        ("Terri Sewell", "Broadcom", "purchase", "$50,001 - $100,000", "2025-06-03"),
        ("Rick Scott", "Micron", "purchase", "$15,001 - $50,000", "2025-05-25"),
        ("Ron Wyden", "Constellation Energy", "purchase", "$50,001 - $100,000", "2025-05-05"),
        ("Tom McClintock", "Cameco", "purchase", "$15,001 - $50,000", "2025-06-18"),
        ("Rick Scott", "NuScale Power", "purchase", "$15,001 - $50,000", "2025-06-05"),
        ("Nancy Pelosi", "Palantir", "purchase", "$250,001 - $500,000", "2025-06-25"),
        ("Donald Norcross", "Lockheed Martin", "purchase", "$15,001 - $50,000", "2025-05-12"),
        ("Nick LaLota", "RTX", "purchase", "$15,001 - $50,000", "2025-05-20"),
        ("Bryan Steil", "General Dynamics", "purchase", "$1,001 - $15,000", "2025-06-12"),
        ("Marjorie T. Greene", "Coinbase", "purchase", "$1,001 - $15,000", "2025-04-05"),
        ("Rick Scott", "Strategy", "purchase", "$15,001 - $50,000", "2025-05-27"),
    ]
    return [{"member": m, "asset": a, "ticker": None, "type": t, "amount": amt, "filing_date": fd}
            for m, a, t, amt, fd in rows]


def fetch_live(api_key, limit=25):
    """Latest House + Senate disclosures from FMP. Free tier locks page=0 and
    limit<=25, so we widen coverage by combining both chambers instead of paging."""
    import requests
    _DEBUG_RAW.clear()
    rows = []
    for endpoint in ("house-latest", "senate-latest"):
        url = (f"https://financialmodelingprep.com/stable/{endpoint}"
               f"?page=0&limit={limit}&apikey={api_key}")
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            if endpoint == "house-latest":
                raise RuntimeError(f"HTTP {resp.status_code} from FMP: {(resp.text or '')[:200]}")
            continue  # senate is a bonus; skip if unavailable
        try:
            data = resp.json()
        except Exception:
            if endpoint == "house-latest":
                raise RuntimeError(f"FMP returned non-JSON: {(resp.text or '')[:200]}")
            continue
        if isinstance(data, dict):
            if endpoint == "house-latest":
                raise RuntimeError(data.get("Error Message") or data.get("message") or str(data))
            continue
        for i, r in enumerate(data):
            if endpoint == "house-latest" and i == 0:
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


# ---------------- engine ----------------
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


def conviction_factor(a):
    return 1.0 if a >= 1_000_000 else 0.85 if a >= 250_000 else 0.65 if a >= 50_000 else 0.45


def recency_factor(fdate, asof):
    days = (asof - datetime.strptime(fdate, "%Y-%m-%d").date()).days
    return 1.0 if days <= 90 else 0.7 if days <= 180 else 0.4 if days <= 365 else 0.2


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
        trades.append({"member": r["member"], "ticker": ticker, "asset": r.get("asset", ""),
                       "amount_mid": amount_midpoint(r["amount"]), "filing_date": r["filing_date"]})
    return trades, unmapped


def score_stocks(trades, asof):
    agg = {}
    for t in trades:
        q = MEMBER_QUALITY.get(t["member"], {}).get("q", DEFAULT_Q)
        contrib = (q / 100) * conviction_factor(t["amount_mid"]) * recency_factor(t["filing_date"], asof)
        d = agg.setdefault(t["ticker"], {"raw": 0.0, "buyers": {}, "last": "", "amt": 0, "asset": ""})
        d["raw"] += contrib
        d["buyers"][t["member"]] = max(d["buyers"].get(t["member"], 0), round(contrib, 2))
        d["last"] = max(d["last"], t["filing_date"])
        d["amt"] += t["amount_mid"]
        if not d["asset"]:
            d["asset"] = t.get("asset", "")
    stocks = []
    for ticker, d in agg.items():
        name, theme = classify(ticker, d["asset"])
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
    # keep Other last regardless of score
    out.sort(key=lambda x: (x["theme"] == "Other", -x["theme_score"]))
    return out


def run_engine(source, lookback_days, asof, api_key=None):
    raw = sample_trades() if source == "sample" else fetch_live(api_key)
    trades, unmapped = normalize(raw, asof, lookback_days)
    stocks = score_stocks(trades, asof)
    return stocks, rank_themes(stocks), unmapped


# ---------------- UI ----------------
def render():
    import streamlit as st
    import pandas as pd
    import time

    st.set_page_config(page_title="Political Capital", page_icon="\U0001F3DB", layout="wide")
    st.markdown("## \U0001F3DB Political Capital")
    st.caption("Forward-theme & stock discovery from congressional disclosures. "
               "Research tool — not investment advice. Data is delayed 1\u20132 months by law.")

    with st.sidebar:
        st.header("Controls")
        mode = st.radio("Data source", ["SAMPLE (offline)", "LIVE \u2014 FMP (real data)"], index=0)
        source = "sample" if mode.startswith("SAMPLE") else "fmp"
        lookback = st.slider("Disclosure window (days)", 30, 365, 180, step=10)
        min_score = st.slider("Min stock signal score", 0, 100, 0, step=5)
        st.divider()
        st.caption("LIVE reads your free FMP key from Settings \u2192 Secrets (FMP_API_KEY).")

    api_key = None
    if source == "fmp":
        try:
            api_key = st.secrets["FMP_API_KEY"]
        except Exception:
            api_key = None
        if not api_key:
            st.warning("LIVE needs your FMP key in Settings \u2192 Secrets: `FMP_API_KEY = \"your_key\"`. "
                       "Showing SAMPLE meanwhile.")
            source = "fmp_nokey"

    asof = date.today() if source == "fmp" else date(2025, 6, 30)
    effective = "sample" if source in ("sample", "fmp_nokey") else "fmp"

    try:
        if effective == "fmp":
            c = st.session_state.get("_raw_cache")
            if c and c["key"] == api_key and time.time() - c["t"] < 1800:
                raw = c["raw"]
            else:
                raw = fetch_live(api_key)
                st.session_state["_raw_cache"] = {"raw": raw, "key": api_key, "t": time.time()}
        else:
            raw = sample_trades()
        trades, unmapped = normalize(raw, asof, lookback)
        stocks = score_stocks(trades, asof)
        themes = rank_themes(stocks)
    except Exception as e:
        st.error(f"Live fetch failed: {e}")
        st.info("If it mentions premium / legacy / 403, tell me and we'll switch sources.")
        if _DEBUG_RAW.get("first"):
            with st.expander("\U0001F527 Raw API response (first record)"):
                st.json(_DEBUG_RAW["first"])
        return

    is_live = (effective == "fmp")
    badge = "\U0001F7E2 LIVE — real disclosures" if is_live else "\U0001F7E1 SAMPLE DATA"
    st.info(f"{badge}  ·  as of {asof}  ·  window {lookback}d  ·  {len(stocks)} stocks across "
            f"{len(themes)} groups  ·  entry uses filing date (45-day legal lag)")

    if is_live and _DEBUG_RAW.get("first"):
        with st.expander("\U0001F527 Raw API response (first record)"):
            st.json(_DEBUG_RAW["first"])

    stocks = [s for s in stocks if s["score"] >= min_score]
    themes = [t for t in themes if any(s["score"] >= min_score for s in t["stocks"])]

    tab1, tab2, tab3 = st.tabs(["\U0001F52D Themes & Sectors", "\U0001F4C8 Stock Screener", "\U0001F465 Member Quality"])

    with tab1:
        st.markdown("##### Where disclosed, quality-weighted money is clustering")
        st.caption("Stocks fall into a curated forward theme when they fit, otherwise their market sector. "
                   "Groups are ranked by strength and breadth of recent buying.")
        for t in themes:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"#### {t['theme']}")
                    st.caption(f"{t['n_stocks']} stocks · {t['n_buyers']} distinct members buying")
                with c2:
                    st.metric("Group signal", t["theme_score"])
                rows = [{"Ticker": s["ticker"], "Company": s["name"], "Score": s["score"],
                         "Buyers": s["n_buyers"], "Last filed": s["last_filing"],
                         "Top buyer": s["buyers"][0] if s["buyers"] else ""} for s in t["stocks"][:10]]
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with tab2:
        st.markdown("##### Stock screener — your prioritized research list")
        st.caption("Ranked by congressional signal. Insider / 13F / contracts / lobbying are placeholders "
                   "until those pipes are added.")
        df = pd.DataFrame([{
            "Ticker": s["ticker"], "Company": s["name"], "Group": s["theme"], "Congress": s["score"],
            "Insider": "\u2014", "Instns": "\u2014", "Contracts": "\u2014", "Lobby": "\u2014",
            "Buyers": s["n_buyers"], "Disclosed $": f"${s['disclosed_usd']:,.0f}", "Last filed": s["last_filing"],
        } for s in stocks])
        st.dataframe(df, hide_index=True, width="stretch")
        if is_live and unmapped:
            st.caption(f"\u26A0\uFE0F {len(set(unmapped))} assets had no ticker and were skipped.")

    with tab3:
        st.markdown("##### Member quality — reliability, not last year's return")
        st.caption("Listed members have researched scores; everyone else gets a neutral default of "
                   f"{DEFAULT_Q} until per-member scoring is calibrated on real track records.")
        rows = [{"Member": m, "Party": v["party"], "State": v["state"], "Quality": v["q"]}
                for m, v in sorted(MEMBER_QUALITY.items(), key=lambda kv: kv[1]["q"], reverse=True)]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.divider()
    st.caption("Public U.S. disclosure data (STOCK Act / Ethics in Government Act). Signal strength "
               "\u2260 investment merit. Most members don't beat the S&P in a given year and the "
               "post-STOCK-Act edge is academically contested. Not investment, legal, or tax advice.")


def run_selftest():
    asof = date(2025, 6, 30)
    stocks, themes, _ = run_engine("sample", 180, asof)
    print(f"\nSELFTEST · SAMPLE · {asof}\nGROUPS")
    for t in themes:
        print(f"  {t['theme']:<32}{t['theme_score']:<5}{t['n_stocks']} stocks")
    print("TOP STOCKS")
    for s in stocks[:6]:
        print(f"  {s['ticker']:<6}{s['score']:<4}{s['theme']}")


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
        print("streamlit run app.py   |   python app.py --selftest")
