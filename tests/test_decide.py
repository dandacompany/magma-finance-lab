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


if __name__ == "__main__":
    unittest.main()
