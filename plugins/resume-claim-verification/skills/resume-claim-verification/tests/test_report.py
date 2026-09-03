from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from validate_report import ReportValidationError, load_and_validate, validate_and_normalize_report  # noqa: E402


class ReportTests(unittest.TestCase):
    def test_all_fixtures_validate(self) -> None:
        fixtures = sorted(FIXTURES.glob("*.json"))
        self.assertEqual(len(fixtures), 5)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                report = load_and_validate(fixture)
                self.assertGreater(len(report["claims"]), 0)
                self.assertIn("counts", report)
                self.assertEqual(sum(report["percentages"].values()), 100)

    def test_standard_limitations_are_always_added(self) -> None:
        report = load_and_validate(FIXTURES / "consistent.json")
        joined = " ".join(report["limitations"])
        self.assertIn("Missing public evidence is not evidence of deception.", joined)
        self.assertIn("does not establish fraud", joined)

    def test_prohibited_decision_field_is_rejected(self) -> None:
        raw = json.loads((FIXTURES / "consistent.json").read_text(encoding="utf-8"))
        raw["candidate_score"] = 82
        with self.assertRaises(ReportValidationError):
            validate_and_normalize_report(raw)

    def test_fake_probability_is_rejected(self) -> None:
        raw = json.loads((FIXTURES / "consistent.json").read_text(encoding="utf-8"))
        raw["fake_probability"] = 80
        with self.assertRaises(ReportValidationError):
            validate_and_normalize_report(raw)

    def test_prohibited_hiring_conclusion_is_rejected(self) -> None:
        raw = json.loads((FIXTURES / "consistent.json").read_text(encoding="utf-8"))
        raw["summary"] = "Do not hire the candidate."
        with self.assertRaises(ReportValidationError):
            validate_and_normalize_report(raw)

    def test_supported_claim_requires_evidence(self) -> None:
        raw = json.loads((FIXTURES / "consistent.json").read_text(encoding="utf-8"))
        raw["claims"][0]["evidence"] = []
        with self.assertRaises(ReportValidationError):
            validate_and_normalize_report(raw)

    def test_flagged_claim_requires_alternative_and_question(self) -> None:
        raw = json.loads((FIXTURES / "mixed-evidence.json").read_text(encoding="utf-8"))
        raw["claims"][1]["alternative_explanations"] = []
        with self.assertRaises(ReportValidationError):
            validate_and_normalize_report(raw)

    def test_pdf_generation_and_required_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.pdf"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "generate_report.py"),
                    str(FIXTURES / "mixed-evidence.json"),
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(output.exists())
            reader = PdfReader(output)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            for heading in (
                "Executive summary",
                "What the review found",
                "Claim assessment",
                "Detailed findings",
                "Sources",
                "Limitations and required human review",
            ):
                self.assertIn(heading, text)
            self.assertIn("This report does not establish fraud", text)
            self.assertIn("Unverified does not mean false", text)
            self.assertIn("not a probability that the resume is deceptive", text)


if __name__ == "__main__":
    unittest.main()
