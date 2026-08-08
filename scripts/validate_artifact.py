#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ETF_FIELDS = (
    "artifact_id", "artifact_type", "schema_version", "as_of", "available_at",
    "source", "symbol", "currency", "total_expense_ratio", "tracking_error",
    "aum", "avg_daily_turnover_20d", "premium_discount", "index_per",
    "index_pbr", "index_dividend_yield", "warnings",
)
MARKET_FIELDS = (
    "artifact_id", "artifact_type", "schema_version", "as_of", "available_at",
    "source", "symbol", "currency", "rows", "warnings",
)
NULLABLE_ETF_METRICS = (
    "total_expense_ratio", "tracking_error", "aum", "avg_daily_turnover_20d",
    "premium_discount", "index_per", "index_pbr", "index_dividend_yield",
)


def canonical_hash(document: dict[str, Any]) -> str:
    payload = dict(document)
    payload.pop("content_hash", None)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def make_result(
    errors: list[str], warnings: list[str], document: dict[str, Any]
) -> dict[str, Any]:
    return {
        "valid": not errors,
        "artifact_type": document.get("artifact_type"),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "canonical_content_hash": canonical_hash(document),
        "order_eligible": False,
    }


def validate(document: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    artifact_type = document.get("artifact_type")
    if artifact_type == "ETFAnalysisSnapshot":
        required = ETF_FIELDS
    elif artifact_type == "MarketSnapshot":
        required = MARKET_FIELDS
    else:
        errors.append("unsupported_artifact_type")
        return make_result(errors, warnings, document)

    missing = [field for field in required if field not in document]
    if missing:
        errors.append("missing_fields:" + ",".join(missing))
    if document.get("schema_version") != "1.0.0":
        errors.append("schema_version_must_be_1.0.0")
    if not re.fullmatch(r"[0-9]{6}", str(document.get("symbol", ""))):
        errors.append("symbol_must_be_six_digits_without_A_prefix")
    if document.get("currency") != "KRW":
        errors.append("currency_must_be_KRW")

    as_of = parse_datetime(document.get("as_of"))
    available_at = parse_datetime(document.get("available_at"))
    if as_of is None:
        errors.append("as_of_must_be_iso8601")
    if available_at is None:
        errors.append("available_at_must_be_iso8601")
    if as_of and available_at and available_at < as_of:
        errors.append("available_at_precedes_as_of")

    if artifact_type == "ETFAnalysisSnapshot":
        missing_metrics = [
            field for field in NULLABLE_ETF_METRICS if document.get(field) is None
        ]
        if missing_metrics and not document.get("warnings"):
            errors.append("null_metrics_require_warnings")
    else:
        rows = document.get("rows")
        if not isinstance(rows, list) or not rows:
            errors.append("rows_must_be_non_empty_array")
        else:
            dates: set[str] = set()
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    errors.append(f"row_{index}_must_be_object")
                    continue
                trade_date = str(row.get("trade_date"))
                if trade_date in dates:
                    errors.append(f"duplicate_trade_date:{trade_date}")
                dates.add(trade_date)
                if row.get("is_final") is not True:
                    errors.append(f"row_{index}_must_be_final")
                prices = [
                    row.get("open_price"), row.get("high_price"),
                    row.get("low_price"), row.get("close_price"),
                ]
                if not all(isinstance(value, int) and value >= 0 for value in prices):
                    errors.append(f"row_{index}_prices_must_be_nonnegative_integers")
                elif row["high_price"] < max(prices) or row["low_price"] > min(prices):
                    errors.append(f"row_{index}_ohlc_range_invalid")

    expected_hash = document.get("content_hash")
    if expected_hash and expected_hash != canonical_hash(document):
        errors.append("content_hash_mismatch")
    if not expected_hash:
        warnings.append("content_hash_missing")
    return make_result(errors, warnings, document)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    document = json.loads(args.artifact.read_text(encoding="utf-8"))
    check = validate(document)
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0 if check["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
