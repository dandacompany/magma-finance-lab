#!/usr/bin/env python3
"""키움 확정 일봉을 수집·검증하고 Supabase 적재 SQL을 만든다.

기본 실행은 KODEX 200과 TIGER 200의 수정주가 일봉을 각각 5페이지
(최대 3,000봉) 수집한다. 당일 봉은 제외하고, 두 종목의 공통 거래일이
2,500개 미만이면 실패한다. 주문 API는 호출하지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")
DEFAULT_SYMBOLS = {"069500": "KODEX 200", "102110": "TIGER 200"}


def canonical_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("content_hash", None)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def positive_int(value: Any, field: str) -> int:
    try:
        return abs(int(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not an integer: {value!r}") from exc


def normalize_rows(raw_rows: list[dict[str, Any]], cutoff: str) -> list[dict[str, Any]]:
    """키움 원문을 MarketSnapshot 행으로 바꾸고 당일·중복·비정상 OHLC를 막는다."""
    normalized: dict[str, dict[str, Any]] = {}
    for raw in raw_rows:
        compact_date = str(raw.get("dt", ""))
        if len(compact_date) != 8 or not compact_date.isdigit():
            raise ValueError(f"invalid trade date: {compact_date!r}")
        if compact_date >= cutoff:
            continue
        trade_date = f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:]}"
        if trade_date in normalized:
            raise ValueError(f"duplicate trade date: {trade_date}")
        row = {
            "trade_date": trade_date,
            "open_price": positive_int(raw.get("open_pric"), "open_pric"),
            "high_price": positive_int(raw.get("high_pric"), "high_pric"),
            "low_price": positive_int(raw.get("low_pric"), "low_pric"),
            "close_price": positive_int(raw.get("cur_prc"), "cur_prc"),
            "volume": positive_int(raw.get("trde_qty"), "trde_qty"),
            "adjusted": True,
            "is_final": True,
        }
        prices = [row[k] for k in ("open_price", "high_price", "low_price", "close_price")]
        if row["high_price"] < max(prices) or row["low_price"] > min(prices):
            raise ValueError(f"invalid OHLC range: {trade_date}")
        normalized[trade_date] = row
    return [normalized[key] for key in sorted(normalized)]


def run_kiwoom_page(code: str, base_date: str, profile: str) -> dict[str, Any]:
    command = [
        "kiwoomcli", "domestic", "candles", "daily",
        "--code", code,
        "--date", base_date,
        "--adjusted", "true",
        "--pages", "1",
        "--profile", profile,
        "--format", "json",
    ]
    delays = (0, 2, 4, 8)
    last_error = ""
    for delay in delays:
        if delay:
            time.sleep(delay)
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode == 0:
            payload = json.loads(completed.stdout)
            if payload.get("return_code") != 0:
                raise RuntimeError(f"Kiwoom returned code {payload.get('return_code')}")
            return payload
        last_error = completed.stderr.strip()
        if "429" not in last_error and "1700" not in last_error:
            break
    raise RuntimeError(f"Kiwoom read failed for {code}: {last_error}")


def run_kiwoom(code: str, base_date: str, profile: str, pages: int) -> dict[str, Any]:
    """기준일을 뒤로 옮기며 600봉씩 수집한다.

    kwcli 1.0.0의 한 프로세스 연속조회는 페이지 사이 간격이 0.2초라
    모의 서버의 초당 1건 제한과 충돌할 수 있다. 공개 CLI만 사용하되
    한 페이지씩 호출하고 1.1초 간격을 둔다.
    """
    if pages < 1:
        raise ValueError("pages must be a positive integer")
    all_rows: list[dict[str, Any]] = []
    request_date = base_date
    latest_payload: dict[str, Any] = {}
    for page in range(pages):
        if page:
            time.sleep(1.1)
        latest_payload = run_kiwoom_page(code, request_date, profile)
        rows = latest_payload.get("stk_dt_pole_chart_qry")
        if not isinstance(rows, list):
            raise RuntimeError(f"unexpected Kiwoom response for {code}")
        if not rows:
            break
        all_rows.extend(rows)
        oldest = min(str(row.get("dt", "")) for row in rows)
        try:
            previous = datetime.strptime(oldest, "%Y%m%d").date() - timedelta(days=1)
        except ValueError as exc:
            raise RuntimeError(f"invalid Kiwoom date for {code}: {oldest!r}") from exc
        request_date = previous.strftime("%Y%m%d")
        if len(rows) < 600:
            break
    latest_payload["stk_cd"] = code
    latest_payload["stk_dt_pole_chart_qry"] = all_rows
    return latest_payload


def make_snapshot(
    code: str, name: str, rows: list[dict[str, Any]], available_at: datetime
) -> dict[str, Any]:
    if not rows:
        raise ValueError(f"no finalized rows for {code}")
    document: dict[str, Any] = {
        "artifact_id": f"market-{code}-{available_at.strftime('%Y%m%dT%H%M%S%z')}",
        "artifact_type": "MarketSnapshot",
        "schema_version": "1.0.0",
        "as_of": rows[-1]["trade_date"] + "T15:30:00+09:00",
        "available_at": available_at.isoformat(timespec="seconds"),
        "source": "kiwoom:ka10081:adjusted",
        "symbol": code,
        "name": name,
        "currency": "KRW",
        "rows": rows,
        "warnings": ["dividends_not_included"],
    }
    document["content_hash"] = canonical_hash(document)
    return document


def coverage_manifest(snapshots: list[dict[str, Any]], minimum: int) -> dict[str, Any]:
    calendars = [{row["trade_date"] for row in item["rows"]} for item in snapshots]
    common = set.intersection(*calendars)
    coverage = {
        item["symbol"]: {
            "name": item["name"],
            "rows": len(item["rows"]),
            "start": item["rows"][0]["trade_date"],
            "end": item["rows"][-1]["trade_date"],
            "adjusted": all(row["adjusted"] for row in item["rows"]),
            "content_hash": item["content_hash"],
        }
        for item in snapshots
    }
    result = {
        "artifact_type": "PriceHistoryCoverage",
        "schema_version": "1.0.0",
        "minimum_common_bars": minimum,
        "common_bars": len(common),
        "common_start": min(common) if common else None,
        "common_end": max(common) if common else None,
        "symbols": coverage,
        "gate_passed": bool(common) and len(common) >= minimum,
    }
    if not result["gate_passed"]:
        raise ValueError(
            f"insufficient common history: {len(common)} < required {minimum}"
        )
    return result


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_sql_chunks(
    output_dir: Path, snapshots: list[dict[str, Any]], chunk_size: int
) -> list[Path]:
    paths: list[Path] = []
    sequence = 1
    for item in snapshots:
        code, name = item["symbol"], item["name"]
        symbol_sql = (
            "insert into finance.symbols(symbol,name,market,note) values "
            f"({sql_literal(code)},{sql_literal(name)},'KRX','historical backfill') "
            "on conflict(symbol) do update set name=excluded.name, market=excluded.market;\n"
        )
        for offset in range(0, len(item["rows"]), chunk_size):
            values = []
            for row in item["rows"][offset : offset + chunk_size]:
                values.append(
                    "(" + ",".join(
                        [
                            sql_literal(code), sql_literal(row["trade_date"]),
                            str(row["open_price"]), str(row["high_price"]),
                            str(row["low_price"]), str(row["close_price"]),
                            str(row["volume"]), "'kiwoom'", "true",
                        ]
                    ) + ")"
                )
            price_sql = (
                "insert into finance.daily_prices "
                "(symbol,trade_date,open_price,high_price,low_price,close_price,volume,source,adjusted) values\n"
                + ",\n".join(values)
                + "\non conflict(symbol,trade_date) do update set "
                "open_price=excluded.open_price,high_price=excluded.high_price,"
                "low_price=excluded.low_price,close_price=excluded.close_price,"
                "volume=excluded.volume,source=excluded.source,adjusted=excluded.adjusted;\n"
            )
            path = output_dir / f"supabase-upsert-{sequence:02d}-{code}.sql"
            path.write_text(symbol_sql + price_sql, encoding="utf-8")
            paths.append(path)
            sequence += 1
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="모의계좌")
    parser.add_argument("--base-date", help="YYYYMMDD, 기본값은 한국시간 오늘")
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--minimum-common-bars", type=int, default=2500)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/market"))
    args = parser.parse_args()

    now = datetime.now(KST)
    base_date = args.base_date or now.strftime("%Y%m%d")
    if len(base_date) != 8 or not base_date.isdigit():
        parser.error("--base-date must be YYYYMMDD")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    snapshots = []
    for index, (code, name) in enumerate(DEFAULT_SYMBOLS.items()):
        if index:
            time.sleep(1.1)
        payload = run_kiwoom(code, base_date, args.profile, args.pages)
        raw_rows = payload.get("stk_dt_pole_chart_qry")
        if not isinstance(raw_rows, list):
            raise RuntimeError(f"unexpected Kiwoom response for {code}")
        rows = normalize_rows(raw_rows, base_date)
        snapshot = make_snapshot(code, name, rows, now)
        snapshot_path = args.output_dir / f"market-snapshot-{code}.json"
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        snapshots.append(snapshot)

    manifest = coverage_manifest(snapshots, args.minimum_common_bars)
    manifest["generated_at"] = now.isoformat(timespec="seconds")
    sql_files = write_sql_chunks(args.output_dir, snapshots, args.chunk_size)
    manifest["supabase_sql_files"] = [path.name for path in sql_files]
    manifest_path = args.output_dir / "price-history-coverage.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
