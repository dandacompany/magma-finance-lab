from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("decide", ROOT / "broker" / "decide.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def state_file(directory: str, payload: dict) -> Path:
    path = Path(directory) / "2026-08-12.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class DailyGateTest(unittest.TestCase):
    """판정 0번 — 하루 한 번. rules.md 판정 순서 0번과 같은 값이어야 한다."""

    def test_one_draft_per_day(self) -> None:
        self.assertEqual(1, MODULE.DAILY_DRAFT_MAX)

    def test_no_state_file_leaves_the_gate_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            decisions = MODULE.load_daily_decisions(str(Path(directory) / "missing.json"))
        self.assertEqual([], decisions)
        self.assertLess(len(decisions), MODULE.DAILY_DRAFT_MAX)

    def test_one_recorded_decision_closes_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = state_file(directory, {"decisions": [{"decision": "BUY", "quantity": 1}]})
            decisions = MODULE.load_daily_decisions(str(path))
        self.assertGreaterEqual(len(decisions), MODULE.DAILY_DRAFT_MAX)

    def test_legacy_single_decision_file_also_closes_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = state_file(directory, {"decision": "BUY", "quantity": 1})
            decisions = MODULE.load_daily_decisions(str(path))
        self.assertEqual(1, len(decisions))
        self.assertGreaterEqual(len(decisions), MODULE.DAILY_DRAFT_MAX)


class JudgeTest(unittest.TestCase):
    """판정과 근거 문구 — 문구가 화면·카드에 그대로 실리므로 방향이 틀리면 안 된다."""

    def test_empty_position_starts_a_cycle(self) -> None:
        side, quantity, why = MODULE.judge(0, 0.0, 99_750)
        self.assertEqual(("BUY", 1), (side, quantity))
        self.assertEqual("보유 0주 — 사이클 시작", why)

    def test_target_reached_sells_everything(self) -> None:
        side, quantity, why = MODULE.judge(3, 100_000.0, 108_000)
        self.assertEqual(("SELL", 3), (side, quantity))
        self.assertIn("전량 매도", why)

    def test_cap_reached_stops_buying(self) -> None:
        side, quantity, why = MODULE.judge(10, 100_000.0, 100_500)
        self.assertEqual((None, 0), (side, quantity))
        self.assertIn("상한 도달", why)

    def test_at_or_below_the_trigger_buys_two(self) -> None:
        side, quantity, why = MODULE.judge(1, 100_000.0, 96_000)
        self.assertEqual(("BUY", 2), (side, quantity))
        self.assertEqual("평단의 97% 이하 — 최대 2주 매수", why)

    def test_two_share_signal_is_capped_by_the_holding_limit(self) -> None:
        """보유 9주에서 2주 신호가 나와도 상한을 넘지 않는다 (8.4 계약 4번)."""
        side, quantity, why = MODULE.judge(9, 100_000.0, 96_000)
        self.assertEqual(("BUY", 1), (side, quantity))
        self.assertEqual("평단의 97% 이하 — 상한 적용 1주 매수", why)

    def test_the_cap_is_never_exceeded_by_any_buy(self) -> None:
        for qty in range(0, MODULE.Q_MAX + 1):
            with self.subTest(qty=qty):
                side, quantity, _ = MODULE.judge(qty, 100_000.0, 96_000)
                if side == "BUY":
                    self.assertLessEqual(qty + quantity, MODULE.Q_MAX)

    def test_above_the_trigger_buys_one(self) -> None:
        side, quantity, why = MODULE.judge(1, 99_500.0, 102_875)
        self.assertEqual(("BUY", 1), (side, quantity))
        self.assertEqual("평단의 97% 초과 — 기본 1주 매수", why)

    def test_a_rising_price_is_never_described_as_a_fall(self) -> None:
        """실측 2026-08-12 — 기준가가 평단의 103.4%인데 '평단 대비 -3% 초과'로 찍혔다."""
        _, _, why = MODULE.judge(1, 99_500.0, 102_875)
        self.assertNotIn("-", why)
        self.assertNotIn("대비", why)


if __name__ == "__main__":
    unittest.main()
