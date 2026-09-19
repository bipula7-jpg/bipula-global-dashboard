"""
SIGNAL — market data fetcher

Pulls index, Treasury yield, energy, and FX quotes from Yahoo Finance
via yfinance (free, unofficial — no SLA, so every fetch is wrapped so a
single bad symbol can't take down the whole run) and writes the result
to data/market.json for the frontend to read.

Yahoo quotes ^FVX / ^TNX / ^TYX (5Y/10Y/30Y Treasury yields) as the
yield * 10 (e.g. 42.5 means 4.25%). This script divides price/change
for the "yields" category by 10 to store an actual percentage.

There is no free Yahoo ticker for the 2-year Treasury yield; if you
want it later, FRED (series DGS2) is a free alternative but needs a
separate fetch path.
"""

import json
import sys
from datetime import datetime, timezone

import yfinance as yf

SYMBOLS = {
    "indices": {
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "dow": "^DJI",
        "russell2000": "^RUT",
        "vix": "^VIX",
    },
    "yields": {
        "us5y": "^FVX",
        "us10y": "^TNX",
        "us30y": "^TYX",
    },
    "energy": {
        "wti_crude": "CL=F",
        "brent_crude": "BZ=F",
        "natural_gas": "NG=F",
    },
    "fx": {
        "dollar_index": "DX-Y.NYB",
        "eur_usd": "EURUSD=X",
    },
}

OUTPUT_PATH = "data/market.json"


def fetch_quote(symbol: str) -> dict:
    """Return {status, price, change, percent_change} for one symbol.
    Never raises — any failure is captured in the returned dict so the
    caller can keep going."""
    try:
        hist = yf.Ticker(symbol).history(period="5d", interval="1d")

        if hist.empty:
            return {"status": "error", "error": "no data returned"}

        if len(hist) < 2:
            last_close = float(hist["Close"].iloc[-1])
            return {
                "status": "partial",
                "price": round(last_close, 4),
                "change": None,
                "percent_change": None,
            }

        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change = last_close - prev_close
        percent_change = (change / prev_close) * 100 if prev_close else None

        return {
            "status": "ok",
            "price": round(last_close, 4),
            "change": round(change, 4),
            "percent_change": round(percent_change, 4) if percent_change is not None else None,
        }
    except Exception as exc:  # noqa: BLE001 — deliberately broad; one bad symbol must not stop the run
        return {"status": "error", "error": str(exc)}


def main() -> None:
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance (free, unofficial — no guaranteed uptime or accuracy SLA)",
    }

    any_success = False

    for category, symbols in SYMBOLS.items():
        output[category] = {}
        for key, symbol in symbols.items():
            quote = fetch_quote(symbol)

            # Yahoo's Treasury yield tickers are yield * 10.
            if category == "yields" and quote.get("status") in ("ok", "partial"):
                quote["price"] = round(quote["price"] / 10, 4)
                if quote.get("change") is not None:
                    quote["change"] = round(quote["change"] / 10, 4)

            output[category][key] = {**quote, "symbol": symbol}

            if quote.get("status") in ("ok", "partial"):
                any_success = True

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {OUTPUT_PATH} (any_success={any_success})")

    # Only hard-fail the workflow if literally everything failed — that
    # signals a systemic problem (e.g. Yahoo blocking the runner) worth
    # surfacing in Actions, rather than one flaky symbol.
    if not any_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
