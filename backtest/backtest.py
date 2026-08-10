#!/usr/bin/env python3
"""분할매수 규칙 백테스트.

t일 확정 종가로 판단하고 t+1일 시가에 체결한다. 전략과 일괄매수는
같은 초기자금·기간·비용 모형을 사용한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "backtest" / "rules.md"


@dataclass(frozen=True)
class Bar:
    trade_date: str
    open_price: int
    close_price: int


def iso_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    date.fromisoformat(value)
    return value


def load_bars(path: Path, start: str | None, end: str | None) -> list[Bar]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("rows") if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise ValueError("data must be a MarketSnapshot object or a row array")
    bars: list[Bar] = []
    seen: set[str] = set()
    for row in rows:
        if "trade_date" in row:
            trade_date = iso_date(str(row["trade_date"]))
            open_price = int(row["open_price"])
            close_price = int(row["close_price"])
            if row.get("adjusted") is not True or row.get("is_final") is not True:
                raise ValueError(f"unadjusted or unfinalized row: {trade_date}")
        else:
            trade_date = iso_date(str(row["dt"]))
            open_price = abs(int(row["open_pric"]))
            close_price = abs(int(row["cur_prc"]))
        if trade_date in seen:
            raise ValueError(f"duplicate trade date: {trade_date}")
        seen.add(trade_date)
        if (start is None or trade_date >= start) and (end is None or trade_date <= end):
            bars.append(Bar(trade_date, open_price, close_price))
    bars.sort(key=lambda item: item.trade_date)
    if len(bars) < 2:
        raise ValueError("backtest requires at least two finalized bars")
    return bars


def short_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:12]


def data_snapshot_id(path: Path) -> str:
    """입력 스냅샷의 신원. 문서가 artifact_id를 밝히면 그 값, 아니면 파일 해시."""
    raw = path.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        document = None
    if isinstance(document, dict) and document.get("artifact_id"):
        return str(document["artifact_id"])
    return "sha256:" + short_digest(raw)


def strategy_spec_id() -> str | None:
    if not RULES_PATH.exists():
        return None
    return f"rules.md@{short_digest(RULES_PATH.read_bytes())}"


def code_version() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return worst * 100


def cagr(initial: float, final: float, first: str, last: str) -> float:
    days = max((date.fromisoformat(last) - date.fromisoformat(first)).days, 1)
    return ((final / initial) ** (365.25 / days) - 1) * 100


def buy_cost(price: int, quantity: int, fee_bps: float, slippage_bps: float) -> tuple[float, float]:
    fill = price * (1 + slippage_bps / 10_000)
    gross = fill * quantity
    return gross + gross * fee_bps / 10_000, gross


def sell_proceeds(
    price: int, quantity: int, fee_bps: float, tax_bps: float, slippage_bps: float
) -> tuple[float, float]:
    fill = price * (1 - slippage_bps / 10_000)
    gross = fill * quantity
    deductions = gross * (fee_bps + tax_bps) / 10_000
    return gross - deductions, gross


def run_strategy(
    bars: list[Bar],
    *,
    p_target: float,
    d_trigger: float,
    q_max: int,
    cap_mode: str,
    initial_cash: float,
    fee_bps: float,
    tax_bps: float,
    slippage_bps: float,
) -> dict[str, Any]:
    cash = initial_cash
    quantity = 0
    position_cost = 0.0
    turnover = 0.0
    trades: list[dict[str, Any]] = []
    equity_curve = [initial_cash]
    max_invested = 0.0

    for signal_bar, execution_bar in zip(bars, bars[1:]):
        average = position_cost / quantity if quantity else 0.0
        action, desired = "HOLD", 0
        if quantity == 0:
            action, desired = "BUY", 1
        elif signal_bar.close_price >= average * (1 + p_target / 100):
            action, desired = "SELL", quantity
        elif quantity >= q_max:
            if cap_mode == "A":
                action, desired = "SELL", quantity
        else:
            action = "BUY"
            desired = 2 if signal_bar.close_price <= average * (1 - d_trigger / 100) else 1
            desired = min(desired, q_max - quantity)

        if action == "BUY" and desired:
            unit_cost, _ = buy_cost(execution_bar.open_price, 1, fee_bps, slippage_bps)
            affordable = max(0, math.floor(cash / unit_cost))
            executed = min(desired, affordable, q_max - quantity)
            if executed:
                total_cost, gross = buy_cost(
                    execution_bar.open_price, executed, fee_bps, slippage_bps
                )
                cash -= total_cost
                quantity += executed
                position_cost += total_cost
                turnover += gross
                max_invested = max(max_invested, position_cost)
                trades.append({
                    "signal_date": signal_bar.trade_date,
                    "execution_date": execution_bar.trade_date,
                    "side": "BUY", "quantity": executed,
                    "execution_open": execution_bar.open_price,
                })
        elif action == "SELL" and desired:
            proceeds, gross = sell_proceeds(
                execution_bar.open_price, desired, fee_bps, tax_bps, slippage_bps
            )
            cash += proceeds
            quantity -= desired
            position_cost = 0.0 if quantity == 0 else position_cost * quantity / (quantity + desired)
            turnover += gross
            trades.append({
                "signal_date": signal_bar.trade_date,
                "execution_date": execution_bar.trade_date,
                "side": "SELL", "quantity": desired,
                "execution_open": execution_bar.open_price,
                "forced_by_cap": cap_mode == "A" and average > 0
                and signal_bar.close_price < average * (1 + p_target / 100),
            })
        equity_curve.append(cash + quantity * execution_bar.close_price)

    final_equity = equity_curve[-1]
    return {
        "initial_cash": round(initial_cash, 2),
        "final_equity": round(final_equity, 2),
        "return_pct": round((final_equity / initial_cash - 1) * 100, 6),
        "cagr_pct": round(cagr(initial_cash, final_equity, bars[0].trade_date, bars[-1].trade_date), 6),
        "mdd_pct": round(drawdown(equity_curve), 6),
        "turnover_amount": round(turnover, 2),
        "turnover_ratio": round(turnover / initial_cash, 6),
        "max_invested_capital": round(max_invested, 2),
        "trade_count": len(trades),
        "open_position": {
            "quantity": quantity,
            "average_cost": round(position_cost / quantity, 2) if quantity else 0.0,
            "unrealized_pnl": round(quantity * bars[-1].close_price - position_cost, 2),
        },
        "trades": trades,
    }


def run_benchmark(
    bars: list[Bar], *, initial_cash: float, fee_bps: float, tax_bps: float, slippage_bps: float
) -> dict[str, Any]:
    entry = bars[1]
    unit_cost, _ = buy_cost(entry.open_price, 1, fee_bps, slippage_bps)
    quantity = math.floor(initial_cash / unit_cost)
    total_cost, gross = buy_cost(entry.open_price, quantity, fee_bps, slippage_bps)
    cash = initial_cash - total_cost
    equity_curve = [initial_cash, cash + quantity * entry.close_price]
    for bar in bars[2:]:
        equity_curve.append(cash + quantity * bar.close_price)
    final_equity = equity_curve[-1]
    return {
        "initial_cash": round(initial_cash, 2),
        "final_equity": round(final_equity, 2),
        "return_pct": round((final_equity / initial_cash - 1) * 100, 6),
        "cagr_pct": round(cagr(initial_cash, final_equity, bars[0].trade_date, bars[-1].trade_date), 6),
        "mdd_pct": round(drawdown(equity_curve), 6),
        "turnover_amount": round(gross, 2),
        "turnover_ratio": round(gross / initial_cash, 6),
        "max_invested_capital": round(total_cost, 2),
        "trade_count": 1 if quantity else 0,
        "open_position": {
            "quantity": quantity,
            "average_cost": round(total_cost / quantity, 2) if quantity else 0.0,
            "unrealized_pnl": round(quantity * bars[-1].close_price - total_cost, 2),
        },
    }


def build_report(args: argparse.Namespace, bars: list[Bar]) -> dict[str, Any]:
    costs = {
        "fee_bps": args.fee_bps,
        "sell_tax_bps": args.tax_bps,
        "slippage_bps": args.slippage_bps,
        "dividends_included": False,
    }
    strategy = run_strategy(
        bars, p_target=args.p_target, d_trigger=args.d_trigger, q_max=args.q_max,
        cap_mode=args.cap, initial_cash=args.initial_cash,
        fee_bps=args.fee_bps, tax_bps=args.tax_bps, slippage_bps=args.slippage_bps,
    )
    benchmark = run_benchmark(
        bars, initial_cash=args.initial_cash, fee_bps=args.fee_bps,
        tax_bps=args.tax_bps, slippage_bps=args.slippage_bps,
    )
    first, last = bars[0].trade_date, bars[-1].trade_date
    test_period = {"start": first, "end": last, "bars": len(bars)}
    if args.train_start or args.train_end:
        train_period = {
            "start": args.train_start or first,
            "end": args.train_end or last,
        }
    else:
        train_period = dict(test_period)
    return {
        "artifact_id": f"backtest-report-{args.symbol}-{first}-{last}-p{args.p_target:g}",
        "artifact_type": "BacktestReport",
        "schema_version": "1.0.0",
        "status": "draft",
        "symbol": args.symbol,
        "data_snapshot_id": data_snapshot_id(args.data),
        "strategy_spec_id": strategy_spec_id(),
        "code_version": code_version(),
        "train_period": train_period,
        "test_period": test_period,
        "signal_at": "t_close_final",
        "execution_at": "t_plus_1_open",
        "execution_rule": "next_bar",
        "strategy": {"p_target": args.p_target, "d_trigger": args.d_trigger, "q_max": args.q_max, "cap_mode": args.cap},
        "initial_capital": args.initial_cash,
        "transaction_cost_bps": args.fee_bps + args.slippage_bps + args.tax_bps,
        "parameter_selection_used_test_period": args.used_test_period,
        "hand_check_passed": args.hand_check_passed,
        "costs": costs,
        "result": strategy,
        "benchmark": {"name": "buy_and_hold", **benchmark},
        "excess_return_pct_point": round(strategy["return_pct"] - benchmark["return_pct"], 6),
        "warnings": ["dividends_not_included", "past_performance_not_future_performance"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("artifacts/market/market-snapshot-069500.json"))
    parser.add_argument("--symbol", default="069500")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--train-start", help="파라미터를 고른 보정 구간 시작일")
    parser.add_argument("--train-end", help="파라미터를 고른 보정 구간 종료일")
    parser.add_argument(
        "--hand-check-passed", action="store_true",
        help="한 사이클을 사람이 손으로 검산해 스크립트와 일치함을 확인했다",
    )
    parser.add_argument(
        "--used-test-period", action="store_true",
        help="평가 구간을 보고 파라미터를 골랐음을 기록한다 (감사에서 거절된다)",
    )
    parser.add_argument("-P", "--p-target", type=float, default=8)
    parser.add_argument("-D", "--d-trigger", type=float, default=3)
    parser.add_argument("-Q", "--q-max", type=int, default=10)
    parser.add_argument("--cap", choices=["A", "B"], default="B")
    parser.add_argument("--initial-cash", type=float, default=2_000_000)
    parser.add_argument("--fee-bps", type=float, default=1.5)
    parser.add_argument("--tax-bps", type=float, default=0)
    parser.add_argument("--slippage-bps", type=float, default=2)
    args = parser.parse_args()
    try:
        bars = load_bars(args.data, args.start, args.end)
        report = build_report(args, bars)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
