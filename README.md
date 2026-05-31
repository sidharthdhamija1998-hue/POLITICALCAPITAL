# Political Capital — Theme & Stock Discovery Dashboard

Finds forward investment themes and ranks stocks from U.S. congressional
financial-disclosure filings (delayed 1–2 months by law). Research tool —
not investment advice.

## Run it
```bash
pip install -r requirements.txt
streamlit run app.py          # opens the dashboard in your browser
```
It starts in **SAMPLE** mode (offline, zero setup). Use the sidebar to widen
the disclosure window or raise the minimum signal score.

## Make it live (real data, on your machine)
1. Get a free API key at financialmodelingprep.com.
2. Paste it into `fetch_live()` (the `API_KEY` line).
3. Run once with `print(raw[0])` uncommented to confirm the provider's field
   names, then switch the sidebar to **LIVE — FMP**.

The free key gives you the Congress signal live. The Insider / Institutions /
Contracts / Lobbying columns are placeholders until those pipes are added —
each is the same pattern pointed at a different public source (SEC Form 4,
13F, USASpending, Senate LDA).

## Check the engine without the UI
```bash
python app.py --selftest      # prints ranked themes + stocks, no Streamlit
```

## Honest limits
- Never real-time: disclosure is delayed up to 45 days by law.
- Signal strength ≠ investment merit. Most members don't beat the S&P in a
  given year, and the post-STOCK-Act edge is academically contested.
- Disclosure data carries statutory use restrictions; get counsel before any
  commercial use.
