import copy
import json
from pathlib import Path
import tempfile
import unittest

from rei_scientist.artifacts import save_study
from rei_scientist.cli import _template, main
from rei_scientist.models import StudySpec
from rei_scientist.replay import replay_artifacts
from rei_scientist.search import run_search


class TestArtifacts(unittest.TestCase):
    def setUp(self):
        data = _template("sphere", "replay-test-001")
        data["evaluation_budget"] = 30
        data["candidate_budget"] = 3
        self.spec = StudySpec.from_dict(data)

    def test_artifact_creation_replay_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "first"
            outcome = run_search(self.spec)
            manifest = save_study(folder, self.spec, outcome, False)
            self.assertTrue((folder / "report.md").is_file())
            self.assertTrue((folder / "dashboard.html").is_file())
            self.assertNotIn("<script", (folder / "dashboard.html").read_text())
            self.assertIn("source_sha256", manifest)
            self.assertEqual(replay_artifacts(folder), [])
            payload = json.loads((folder / "results.json").read_text())
            payload["holdout_selected"][0]["best_value"] = 999
            (folder / "results.json").write_text(json.dumps(payload))
            failures = replay_artifacts(folder)
            self.assertTrue(any("SHA-256" in x for x in failures))
            self.assertTrue(any("objective differs" in x for x in failures))

    def test_report_and_dashboard_tampering_detected(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "run"
            save_study(folder, self.spec, run_search(self.spec), False)
            dashboard = folder / "dashboard.html"
            dashboard.write_text(dashboard.read_text() + "<!-- forged -->")
            report = folder / "report.md"
            report.write_text(report.read_text() + "\nForged claim")
            errors = replay_artifacts(folder)
            self.assertTrue(any("dashboard SHA-256 mismatch" in error for error in errors))
            self.assertTrue(any("report SHA-256 mismatch" in error for error in errors))

    def test_html_escapes_untrusted_study_description(self):
        with tempfile.TemporaryDirectory() as td:
            data = self.spec.to_dict()
            data["question"] = "Will <script>alert(1)</script> improve?"
            spec = StudySpec.from_dict(data)
            folder = Path(td) / "run"
            save_study(folder, spec, run_search(spec), False)
            html = (folder / "dashboard.html").read_text()
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn("<script>", html)
            markdown = (folder / "report.md").read_text()
            self.assertNotIn("<script>", markdown)
            self.assertIn("&lt;script&gt;", markdown)
            self.assertEqual(replay_artifacts(folder), [])

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "first"
            folder.mkdir()
            with self.assertRaises(FileExistsError):
                save_study(folder, self.spec, run_search(self.spec), False)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            study = Path(td) / "study.json"
            out = Path(td) / "report"
            study.write_text(json.dumps(self.spec.to_dict()))
            self.assertEqual(main(["run", str(study), "--out", str(out)]), 0)
            self.assertEqual(main(["verify", str(out)]), 0)
            self.assertEqual(main(["run", str(study), "--out", str(out)]), 2)
            text = (out / "report.md").read_text()
            self.assertIn("Research status:", text)
            self.assertIn("NOT VERIFIED", text)

    def test_cli_init_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            new_study = Path(td) / "new-study.json"
            self.assertEqual(main(["init", "--study-id", "rotor-pilot", "--benchmark", "ackley",
                                   "--out", str(new_study)]), 0)
            validated = StudySpec.from_dict(json.loads(new_study.read_text()))
            self.assertEqual(validated.benchmark, "ackley")
            self.assertEqual(main(["init", "--study-id", "rotor-pilot", "--out", str(new_study)]), 2)

    def test_cli_does_not_network_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            study = Path(td) / "study.json"
            out = Path(td) / "report"
            study.write_text(json.dumps(self.spec.to_dict()))
            from unittest.mock import patch
            with patch("rei_scientist.cli.propose_candidates", side_effect=AssertionError("unexpected LLM call")), \
                 patch("rei_scientist.cli.search_crossref", side_effect=AssertionError("unexpected Crossref call")):
                self.assertEqual(main(["run", str(study), "--out", str(out)]), 0)
