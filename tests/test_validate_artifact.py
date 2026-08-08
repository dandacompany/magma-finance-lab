from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_artifact", ROOT / "scripts" / "validate_artifact.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ValidateArtifactTest(unittest.TestCase):
    def test_verified_etf_snapshot(self) -> None:
        document = json.loads(
            (ROOT / "examples" / "etf-analysis-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        check = MODULE.validate(document)
        self.assertTrue(check["valid"], check)
        self.assertFalse(check["order_eligible"])

    def test_market_snapshot_rejects_unfinalized_row(self) -> None:
        document = json.loads(
            (ROOT / "examples" / "rehearsal-invalid-market-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        check = MODULE.validate(document)
        self.assertFalse(check["valid"])
        self.assertIn("row_0_must_be_final", check["errors"])

    def test_verified_final_market_snapshot(self) -> None:
        document = json.loads(
            (ROOT / "examples" / "rehearsal-final-market-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        check = MODULE.validate(document)
        self.assertTrue(check["valid"], check)
        self.assertFalse(check["order_eligible"])

    def test_market_snapshot_accepts_final_row(self) -> None:
        document = json.loads(
            (ROOT / "examples" / "rehearsal-final-market-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        check = MODULE.validate(document)
        self.assertTrue(check["valid"], check)
        self.assertEqual(["content_hash_missing"], check["warnings"])


if __name__ == "__main__":
    unittest.main()
