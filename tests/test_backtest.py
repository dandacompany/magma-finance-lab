from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
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


def snapshot_file(directory: str, artifact_id: str | None) -> Path:
    document: dict = {"artifact_type": "MarketSnapshot", "rows": []}
    if artifact_id:
        document["artifact_id"] = artifact_id
    path = Path(directory) / "snapshot.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def report(data: Path, **overrides):
    options = dict(
        data=data, symbol="069500", p_target=8, d_trigger=3, q_max=10, cap="B",
        initial_cash=2_000_000, fee_bps=1.5, tax_bps=0, slippage_bps=2,
        train_start=None, train_end=None,
        hand_check_passed=False, used_test_period=False,
    )
    options.update(overrides)
    return MODULE.build_report(argparse.Namespace(**options), bars())


class ReportContractTest(unittest.TestCase):
    """감사 도구가 요구하는 계약 필드를 리포트가 갖추는지 확인한다."""

    def build(self, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            data = snapshot_file(directory, overrides.pop("artifact_id", "market-069500-x"))
            return report(data, **overrides)

    def test_required_contract_fields_are_present(self) -> None:
        document = self.build()
        for field in (
            "artifact_id", "data_snapshot_id", "strategy_spec_id", "train_period",
            "test_period", "signal_at", "execution_at", "initial_capital",
            "transaction_cost_bps", "benchmark", "warnings",
        ):
            self.assertIn(field, document)
        self.assertEqual("next_bar", document["execution_rule"])
        self.assertEqual(2_000_000, document["initial_capital"])
        self.assertEqual(3.5, document["transaction_cost_bps"])
        self.assertEqual("backtest-report-069500-2026-01-02-2026-01-07-p8", document["artifact_id"])

    def test_data_snapshot_id_prefers_the_document_artifact_id(self) -> None:
        self.assertEqual("market-069500-x", self.build()["data_snapshot_id"])

    def test_data_snapshot_id_falls_back_to_the_file_hash(self) -> None:
        snapshot_id = self.build(artifact_id=None)["data_snapshot_id"]
        self.assertTrue(snapshot_id.startswith("sha256:"))
        self.assertEqual(19, len(snapshot_id))

    def test_strategy_spec_id_points_at_the_rules_file(self) -> None:
        self.assertRegex(self.build()["strategy_spec_id"], r"^rules\.md@[0-9a-f]{12}$")

    def test_train_period_defaults_to_the_test_period(self) -> None:
        document = self.build()
        self.assertEqual(document["test_period"], document["train_period"])

    def test_train_period_records_the_calibration_window(self) -> None:
        document = self.build(train_start="2014-05-19", train_end="2020-12-30")
        self.assertEqual({"start": "2014-05-19", "end": "2020-12-30"}, document["train_period"])
        self.assertNotEqual(document["test_period"], document["train_period"])

    def test_hand_check_and_test_period_leak_default_to_false(self) -> None:
        document = self.build()
        self.assertFalse(document["hand_check_passed"])
        self.assertFalse(document["parameter_selection_used_test_period"])

    def test_flags_record_hand_check_and_test_period_leak(self) -> None:
        document = self.build(hand_check_passed=True, used_test_period=True)
        self.assertTrue(document["hand_check_passed"])
        self.assertTrue(document["parameter_selection_used_test_period"])


try:  # 감사 도구는 별도 패키지다. 없으면 계약 필드 검사만 돌린다.
    from vibe_finance_kit.contracts import audit_backtest_report
except ImportError:  # pragma: no cover - 스타터 저장소 단독 실행 경로
    audit_backtest_report = None


@unittest.skipIf(audit_backtest_report is None, "vibe_finance_kit is not installed")
class ReportAuditTest(unittest.TestCase):
    def audit(self, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            data = snapshot_file(directory, "market-069500-x")
            return audit_backtest_report(report(data, **overrides))

    def test_report_passes_the_audit_once_hand_checked(self) -> None:
        verdict = self.audit(hand_check_passed=True)
        self.assertEqual([], verdict["errors"])
        self.assertTrue(verdict["valid"])

    def test_missing_hand_check_only_warns(self) -> None:
        verdict = self.audit()
        self.assertEqual([], verdict["errors"])
        self.assertIn("one_cycle_hand_check_not_confirmed", verdict["warnings"])
        self.assertFalse(verdict["decision_eligible"])

    def test_test_period_leak_fails_the_audit(self) -> None:
        verdict = self.audit(hand_check_passed=True, used_test_period=True)
        self.assertIn("test_period_used_for_parameter_selection", verdict["errors"])
        self.assertFalse(verdict["valid"])


if __name__ == "__main__":
    unittest.main()
