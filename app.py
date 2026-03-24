from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO
import subprocess
from typing import Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)

SECTORS = {
    "XLC": {"name": "Communication Services", "color": "#ff8a4c"},
    "XLY": {"name": "Consumer Discretionary", "color": "#ffb347"},
    "XLP": {"name": "Consumer Staples", "color": "#f6d365"},
    "XLE": {"name": "Energy", "color": "#ff6b6b"},
    "XLF": {"name": "Financials", "color": "#ffd166"},
    "XLV": {"name": "Health Care", "color": "#4ecdc4"},
    "XLI": {"name": "Industrials", "color": "#5dade2"},
    "XLB": {"name": "Materials", "color": "#48c78e"},
    "XLRE": {"name": "Real Estate", "color": "#b784f7"},
    "XLK": {"name": "Technology", "color": "#6c8cff"},
    "XLU": {"name": "Utilities", "color": "#7f8c8d"},
}


def parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    return datetime.strptime(value, "%Y-%m-%d").date()


def validate_dates(start_value: str | None, end_value: str | None) -> tuple[date, date]:
    today = date.today()
    default_start = today - timedelta(days=30)
    start_date = parse_date(start_value, default_start)
    end_date = parse_date(end_value, today)

    if end_date < start_date:
        raise ValueError("结束日期不能早于开始日期")
    if end_date > today:
        end_date = today
    if (end_date - start_date).days > 366 * 3:
        raise ValueError("时间区间过长，请选择 3 年以内")

    return start_date, end_date


def extract_symbol_frame(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        if symbol not in raw.columns.get_level_values(0):
            raise KeyError(symbol)
        frame = raw[symbol].copy()
    else:
        frame = raw.copy()

    return frame.dropna(subset=["Close", "High", "Low", "Volume"])


def money_flow_metrics(frame: pd.DataFrame) -> dict[str, float]:
    working = frame.copy()
    typical_price = (working["High"] + working["Low"] + working["Close"]) / 3.0
    spread = (working["High"] - working["Low"]).replace(0, np.nan)
    multiplier = (((working["Close"] - working["Low"]) - (working["High"] - working["Close"])) / spread).fillna(0)

    raw_flow = typical_price * working["Volume"] * multiplier
    dollar_volume = typical_price * working["Volume"]
    total_volume = float(working["Volume"].sum())

    net_flow = float(raw_flow.sum())
    total_dollar_volume = float(dollar_volume.sum())
    flow_intensity = float(net_flow / total_dollar_volume) if total_dollar_volume else 0.0
    avg_dollar_volume = float(dollar_volume.mean()) if len(dollar_volume) else 0.0
    cmf = float(raw_flow.sum() / total_volume) if total_volume else 0.0

    return {
        "net_flow": net_flow,
        "total_dollar_volume": total_dollar_volume,
        "flow_intensity": flow_intensity,
        "avg_dollar_volume": avg_dollar_volume,
        "cmf": cmf,
    }


def build_sector_record(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    if len(frame) < 2:
        raise ValueError(f"{symbol} 数据不足")

    start_close = float(frame["Close"].iloc[0])
    end_close = float(frame["Close"].iloc[-1])
    change_pct = ((end_close / start_close) - 1.0) * 100.0
    metrics = money_flow_metrics(frame)

    sparkline = [round(float(v), 2) for v in frame["Close"].tolist()]
    volume_mean = float(frame["Volume"].mean())
    volume_ratio = float(frame["Volume"].iloc[-1] / volume_mean) if volume_mean else 0.0

    return {
        "symbol": symbol,
        "name": SECTORS[symbol]["name"],
        "color": SECTORS[symbol]["color"],
        "start_close": round(start_close, 2),
        "end_close": round(end_close, 2),
        "change_pct": round(change_pct, 2),
        "net_flow": round(metrics["net_flow"], 2),
        "flow_intensity": round(metrics["flow_intensity"] * 100, 2),
        "avg_dollar_volume": round(metrics["avg_dollar_volume"], 2),
        "total_dollar_volume": round(metrics["total_dollar_volume"], 2),
        "cmf_proxy": round(metrics["cmf"], 4),
        "last_volume_ratio": round(volume_ratio, 2),
        "sparkline": sparkline,
    }


def fetch_csv_text(url: str) -> str:
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.text
    except Exception:
        result = subprocess.run(
            ["curl", "-k", "-L", url],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout


def download_from_stooq(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    csv_text = fetch_csv_text(url)
    frame = pd.read_csv(StringIO(csv_text))
    if frame.empty:
        raise ValueError(f"{symbol} 无可用数据")

    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame[(frame["Date"] >= pd.Timestamp(start_date)) & (frame["Date"] <= pd.Timestamp(end_date))]
    frame = frame.set_index("Date")
    frame = frame[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return frame


def download_sector_data(start_date: date, end_date: date) -> list[dict[str, Any]]:
    tickers = list(SECTORS.keys())
    raw = pd.DataFrame()

    try:
        raw = yf.download(
            tickers=tickers,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception:
        raw = pd.DataFrame()

    records: list[dict[str, Any]] = []
    for symbol in tickers:
        frame = pd.DataFrame()

        if not raw.empty:
            try:
                frame = extract_symbol_frame(raw, symbol)
                frame = frame[["Open", "High", "Low", "Close", "Volume"]].dropna()
            except Exception:
                frame = pd.DataFrame()

        if frame.empty:
            try:
                frame = download_from_stooq(symbol, start_date, end_date)
            except Exception:
                frame = pd.DataFrame()

        if frame.empty:
            continue
        records.append(build_sector_record(symbol, frame))

    if not records:
        raise ValueError("选定区间内没有可用板块数据")

    return records


def format_dashboard_payload(records: list[dict[str, Any]], start_date: date, end_date: date) -> dict[str, Any]:
    sorted_by_perf = sorted(records, key=lambda item: item["change_pct"], reverse=True)
    sorted_by_flow = sorted(records, key=lambda item: item["net_flow"], reverse=True)
    avg_change = sum(item["change_pct"] for item in records) / len(records)
    positive_count = sum(1 for item in records if item["change_pct"] >= 0)
    inflow_count = sum(1 for item in records if item["net_flow"] >= 0)

    return {
        "meta": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": (end_date - start_date).days + 1,
            "sector_count": len(records),
            "method": "使用美股板块 ETF 的 OHLCV 数据，以 Chaikin Money Flow 思路估算资金净流向，属于公开数据代理指标，不等同于官方申赎流量。",
        },
        "overview": {
            "avg_change_pct": round(avg_change, 2),
            "total_sectors": len(records),
            "positive_sector_count": positive_count,
            "inflow_sector_count": inflow_count,
            "top_gainer": sorted_by_perf[0],
            "top_loser": sorted_by_perf[-1],
            "strongest_inflow": sorted_by_flow[0],
            "strongest_outflow": sorted_by_flow[-1],
        },
        "sectors": sorted_by_perf,
    }


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/sectors")
def sector_dashboard() -> Any:
    try:
        start_date, end_date = validate_dates(request.args.get("start"), request.args.get("end"))
        records = download_sector_data(start_date, end_date)
        payload = format_dashboard_payload(records, start_date, end_date)
        return jsonify(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "数据拉取失败，请检查网络后重试"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5050)
