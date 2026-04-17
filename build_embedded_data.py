from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf


OVERVIEW_SYMBOLS = ["XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLK", "XLU"]
DETAIL_SYMBOLS = ["SMH", "IGV", "XBI", "IHI", "KRE", "KIE", "XRT", "ITB", "IYT", "ICLN"]
SYMBOLS = OVERVIEW_SYMBOLS + DETAIL_SYMBOLS
OUT_FILE = Path(__file__).with_name("sector_data.js")


def load_existing_data() -> dict[str, list[dict[str, float | str]]]:
    if not OUT_FILE.exists():
        return {}

    text = OUT_FILE.read_text(encoding="utf-8")
    payload = json.loads(text.split("=", 1)[1].rsplit(";", 1)[0])
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


def fetch_history(symbol: str, existing_rows: list[dict]) -> list[dict[str, float | str]]:
    """
    Fetch latest history for symbol via yfinance.
    If yfinance fails, fall back to existing cached rows.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2y", auto_adjust=True)
    except Exception:
        return existing_rows

    if hist.empty:
        return existing_rows

    rows: list[dict[str, float | str]] = []
    for date, row in hist.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        # Skip if this date is already in existing data and is the last entry
        if existing_rows and date_str == existing_rows[-1].get("date"):
            continue
        try:
            rows.append({
                "date": date_str,
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": round(float(row["Volume"]), 4),
            })
        except (KeyError, TypeError, ValueError):
            continue

    return rows


def main() -> None:
    existing = load_existing_data()
    payload: dict[str, list[dict[str, float | str]]] = {}
    reused_symbols: list[str] = []
    fetched_count = 0

    for symbol in SYMBOLS:
        existing_rows = existing.get(symbol, [])
        fresh_rows = fetch_history(symbol, existing_rows)

        if fresh_rows:
            payload[symbol] = fresh_rows
            if not fresh_rows or (existing_rows and fresh_rows[-1]["date"] == existing_rows[-1]["date"]):
                reused_symbols.append(symbol)
            else:
                fetched_count += 1
        else:
            payload[symbol] = existing_rows
            reused_symbols.append(symbol)

    if not any(payload.values()):
        raise RuntimeError("No sector data available (yfinance failed and no cached data)")

    document = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "symbols": SYMBOLS,
            "reused_symbols": reused_symbols,
        },
        "data": payload,
    }

    OUT_FILE.write_text(
        "window.SECTOR_DATA = " + json.dumps(document, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_FILE}  (fresh={fetched_count}, reused={len(reused_symbols)})")


if __name__ == "__main__":
    main()
