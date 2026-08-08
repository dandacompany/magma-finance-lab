from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "backfill_prices", ROOT / "scripts" / "backfill_prices.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def raw(date: str, close: str = "100") -> dict[str, str]:
    return {
        "dt": date,
        "open_pric": "+100",
        "high_pric": "+110",
        "low_pric": "+90",
        "cur_prc": close,
        "trde_qty": "1000",
    }


class BackfillPricesTest(unittest.TestCase):
    def test_normalize_excludes_cutoff_and_removes_price_signs(self) -> None:
        rows = MODULE.normalize_rows(
            [raw("20260808"), raw("20260807", "-101")], "20260808"
        )
        self.assertEqual(1, len(rows))
        self.assertEqual("2026-08-07", rows[0]["trade_date"])
        self.assertEqual(101, rows[0]["close_price"])
        self.assertTrue(rows[0]["adjusted"])
        self.assertTrue(rows[0]["is_final"])

    def test_duplicate_date_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate trade date"):
            MODULE.normalize_rows([raw("20260807"), raw("20260807")], "20260808")

    def test_common_history_gate(self) -> None:
        now = datetime(2026, 8, 8, 12, tzinfo=ZoneInfo("Asia/Seoul"))
        a = MODULE.make_snapshot("069500", "KODEX 200", MODULE.normalize_rows(
            [raw("20260805"), raw("20260806")], "20260808"), now)
        b = MODULE.make_snapshot("102110", "TIGER 200", MODULE.normalize_rows(
            [raw("20260806"), raw("20260807")], "20260808"), now)
        manifest = MODULE.coverage_manifest([a, b], 1)
        self.assertEqual(1, manifest["common_bars"])
        self.assertEqual("2026-08-06", manifest["common_start"])
        with self.assertRaisesRegex(ValueError, "insufficient common history"):
            MODULE.coverage_manifest([a, b], 2)

    def test_sql_is_idempotent_upsert(self) -> None:
        now = datetime(2026, 8, 8, 12, tzinfo=ZoneInfo("Asia/Seoul"))
        snapshot = MODULE.make_snapshot(
            "069500", "KODEX 200", MODULE.normalize_rows([raw("20260807")], "20260808"), now
        )
        with tempfile.TemporaryDirectory() as temp:
            paths = MODULE.write_sql_chunks(Path(temp), [snapshot], 500)
            sql = paths[0].read_text(encoding="utf-8")
        self.assertIn("on conflict(symbol,trade_date) do update", sql)
        self.assertIn("'2026-08-07'", sql)


if __name__ == "__main__":
    unittest.main()
