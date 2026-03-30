from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


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


def fetch_csv(symbol: str) -> list[dict[str, str]]:
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    try:
        result = subprocess.run(
            ["curl", "-k", "-L", url],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except subprocess.SubprocessError:
        return []
    reader = csv.DictReader(StringIO(result.stdout))
    return list(reader)


def normalize(rows: list[dict[str, str]]) -> list[dict[str, float | str]]:
    cleaned: list[dict[str, float | str]] = []
    for row in rows:
        try:
            cleaned.append(
                {
                    "date": row["Date"],
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": round(float(row["Volume"]), 4),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return cleaned


def main() -> None:
    existing = load_existing_data()
    payload: dict[str, list[dict[str, float | str]]] = {}
    reused_symbols: list[str] = []

    for symbol in SYMBOLS:
        fresh_rows = normalize(fetch_csv(symbol))
        if fresh_rows:
            payload[symbol] = fresh_rows
            continue

        cached_rows = existing.get(symbol, [])
        if cached_rows:
            payload[symbol] = cached_rows
            reused_symbols.append(symbol)
            continue

        payload[symbol] = []

    if not any(payload.values()):
        raise RuntimeError("No sector data fetched and no cached data available")

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
    print(f"wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
