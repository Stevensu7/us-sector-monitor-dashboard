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


def fetch_csv(symbol: str) -> list[dict[str, str]]:
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    result = subprocess.run(
        ["curl", "-k", "-L", url],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
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
    payload: dict[str, list[dict[str, float | str]]] = {}
    for symbol in SYMBOLS:
        payload[symbol] = normalize(fetch_csv(symbol))

    document = {
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "symbols": SYMBOLS,
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
