from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("backtest", ROOT / "backtest" / "backtest.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def bars() -> list:
    return [
        MODULE.Bar("2026-01-02", 100, 100),
        MODULE.Bar("2026-01-05", 110, 110),
        MODULE.Bar("2026-01-06", 120, 120),
        MODULE.Bar("2026-01-07", 130, 130),
    ]


def run(**overrides):
    options = dict(
        p_target=100, d_trigger=3, q_max=10, cap_mode="B",
        initial_cash=2_000_000, fee_bps=0, tax_bps=0, slippage_bps=0,
    )
    options.update(overrides)
    return MODULE.run_strategy(bars(), **options)


class BacktestTest(unittest.TestCase):
    def test_signal_uses_close_and_executes_at_next_open(self) -> None:
        result = run()
        first = result["trades"][0]
        self.assertEqual("2026-01-02", first["signal_date"])
        self.assertEqual("2026-01-05", first["execution_date"])
        self.assertEqual(110, first["execution_open"])

    def test_quantity_never_exceeds_cap(self) -> None:
        result = run(q_max=2)
        self.assertLessEqual(result["open_position"]["quantity"], 2)

    def test_costs_reduce_final_equity(self) -> None:
        free = run()
        costly = run(fee_bps=10, slippage_bps=10)
        self.assertLess(costly["final_equity"], free["final_equity"])

    def test_cap_mode_b_does_not_lower_profit_target(self) -> None:
        result = run(q_max=1, p_target=50, cap_mode="B")
        self.assertEqual(["BUY"], [trade["side"] for trade in result["trades"]])


if __name__ == "__main__":
    unittest.main()
