"""
Phase 2 backend script — run on a schedule via GitHub Actions.

Yahoo Finance has been rate-limiting/blocking requests from cloud IP ranges
(including GitHub Actions runners) since late 2024. This version routes
through a browser-TLS-fingerprint-impersonating client (curl_cffi) to work
around that, retries on failure, and logs which tickers failed and why in
the output JSON's "diagnostics" field instead of failing silently.
"""

import os
import time
import json
from datetime import datetime, timezone

import yfinance as yf
from curl_cffi import requests as curl_requests

INDICES = {
    "S&P 500": "^GSPC",
    "Nasdaq Composite": "^IXIC",
    "Dow Jones": "^DJI",
    "Russell 2000": "^RUT",
    "VIX": "^VIX",
}

SECTORS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
}

COMMODITIES = {
    "WTI Crude": "CL=F",
    "Brent Crude": "BZ=F",
    "Nat Gas": "NG=F",
    "Gold": "GC=F",
}

SESSION = curl_requests.Session(impersonate="chrome")

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 8


def fetch_quote(ticker, retries=MAX_RETRIES):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            t = yf.Ticker(ticker, session=SESSION)
            hist = t.history(period="5d", interval="1d")
            if hist.empty or len(hist) < 2:
                last_error = "empty or insufficient history returned"
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            last = hist.iloc[-1]
            prev_close = hist.iloc[-2]["Close"]
            change = last["Close"] - prev_close
            pct = (change / prev_close) * 100 if prev_close else None
            return {
                "price": round(float(last["Close"]), 2),
                "change": round(float(change), 2),
                "pct_change": round(float(pct), 2) if pct is not None else None,
                "day_high": round(float(last["High"]), 2),
                "day_low": round(float(last["Low"]), 2),
                "prev_close": round(float(prev_close), 2),
            }
        except Exception as e:
            last_error = str(e)
            time.sleep(RETRY_DELAY_SECONDS)
    return {"status": "DATA UNAVAILABLE", "error": last_error}


def build_section(mapping):
    out = {}
    for name, ticker in mapping.items():
        out[name] = fetch_quote(ticker)
        time.sleep(1.5)
    return out


def main():
    indices = build_section(INDICES)
    sectors = build_section(SECTORS)
    commodities = build_section(COMMODITIES)

    failures = [
        name for section in (indices, sectors, commodities)
        for name, v in section.items() if v.get("status") == "DATA UNAVAILABLE"
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "indices": indices,
        "sectors": sectors,
        "commodities": commodities,
        "diagnostics": {
            "failed_tickers": failures,
            "failure_count": len(failures),
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/market.json", "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Done. {len(failures)} ticker(s) failed: {failures}" if failures
          else "Done. All tickers fetched successfully.")


if __name__ == "__main__":
    main()
