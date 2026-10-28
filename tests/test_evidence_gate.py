import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/closed-loop-repair/scripts/evidence_gate.py"
spec = importlib.util.spec_from_file_location("gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.config = {"source_roots": ["src"], "protected_roots": ["data"],
                       "required_checks": ["behavior", "regression", "visual"],
                       "visual": True, "visual_check": "visual"}
        self.issue = {"root_cause": "implementation", "diagnosis": "Input correct; renderer drops border",
                      "diagnosis_evidence": ["evidence/diagnosis.txt"], "plan": "Propagate border attribute",
                      "approval": {"plan_sha256": gate.digest("Propagate border attribute"),
                                   "quote": "Synthetic test approval", "reference": "test fixture, not real approval"},
                      "changed_files": ["src/render.txt"],
                      "artifacts": {"baseline": "evidence/old.txt", "before": "evidence/before.png",
                                    "candidate": "evidence/new.txt", "after": "evidence/after.png"},
                      "checks": {k: f"evidence/{k}.json" for k in self.config["required_checks"]}}
        for name, text in {"src/render.txt": "broken", "src/stable.txt": "normal control",
                           "data/input.txt": "border=true",
                           "evidence/diagnosis.txt": "source inspection", "evidence/old.txt": "no border",
                           "evidence/before.png": "synthetic screenshot bytes"}.items():
            self.write(name, text)
        self.baseline = gate.capture(self.root, self.config, self.issue)
        self.write("src/render.txt", "fixed")
        self.write("evidence/new.txt", "border")
        self.write("evidence/after.png", "synthetic fixed screenshot bytes")
        self.candidate = gate.capture(self.root, self.config, self.issue)
        self.reports()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def reports(self, status="PASS"):
        for path in self.issue["checks"].values():
            self.write(path, json.dumps({"status": status, "summary": "Synthetic test observation",
                       "source_digest": self.candidate["source_digest"],
                       "artifacts_digest": self.candidate["artifacts_digest"]}))

    def ready(self):
        return gate.ready(self.root, self.config, self.issue, self.baseline, self.candidate)

    def test_valid_candidate_is_not_human_accepted(self):
        self.assertEqual(self.ready(), "ready_for_human")

    def test_data_branch_reports_without_source_repair(self):
        self.issue["root_cause"] = "data"
        self.assertEqual(gate.diagnosis(self.root, self.issue), "reported_data_issue")
        with self.assertRaises(gate.GateError): self.ready()

    def test_unknown_and_mixed_do_not_enter_repair(self):
        for cause, expected in [("mixed", "manual_review"), ("undetermined", "blocked")]:
            self.issue["root_cause"] = cause
            self.assertEqual(gate.diagnosis(self.root, self.issue), expected)
            with self.assertRaises(gate.GateError): self.ready()

    def test_plan_change_invalidates_confirmation(self):
        self.issue["plan"] += " and replace all tables"
        with self.assertRaises(gate.GateError): self.ready()

    def test_missing_confirmation_blocks(self):
        self.issue["approval"] = None
        with self.assertRaises(gate.GateError): self.ready()

    def test_source_and_artifact_drift_block(self):
        for name in ["src/render.txt", "evidence/after.png"]:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(b"changed after verification")
                with self.assertRaises(gate.GateError): self.ready()
                path.write_bytes(original)

    def test_input_change_cannot_be_hidden_by_new_snapshot(self):
        self.write("data/input.txt", "border=false")
        self.candidate = gate.capture(self.root, self.config, self.issue)
        self.reports()
        with self.assertRaises(gate.GateError): self.ready()

    def test_undeclared_changes_and_deletions_block(self):
        self.write("src/other.txt", "unexpected")
        self.candidate = gate.capture(self.root, self.config, self.issue)
        self.reports()
        with self.assertRaises(gate.GateError): self.ready()
        (self.root / "src/other.txt").unlink()
        (self.root / "src/render.txt").unlink()
        self.issue["changed_files"] = []
        self.candidate = gate.capture(self.root, self.config, self.issue)
        self.reports()
        with self.assertRaises(gate.GateError): self.ready()

    def test_original_evidence_cannot_be_replaced(self):
        self.write("evidence/before.png", "replaced baseline")
        self.candidate = gate.capture(self.root, self.config, self.issue)
        self.reports()
        with self.assertRaises(gate.GateError): self.ready()

    def test_nonpass_reports_block(self):
        for status in ["FAIL", "ERROR", "MANUAL_REVIEW", "BLOCKED"]:
            self.reports(status)
            with self.assertRaises(gate.GateError): self.ready()

    def test_old_report_does_not_validate_new_artifact(self):
        self.write("evidence/after.png", "new attempt")
        self.candidate = gate.capture(self.root, self.config, self.issue)
        with self.assertRaises(gate.GateError): self.ready()

    def test_nonvisual_work_does_not_require_screenshots(self):
        self.config["visual"] = False
        self.config["required_checks"] = ["behavior", "regression"]
        self.issue["artifacts"].pop("before")
        self.issue["artifacts"].pop("after")
        self.baseline["config_digest"] = gate.digest(self.config)
        self.candidate = gate.capture(self.root, self.config, self.issue)
        self.reports()
        self.assertEqual(self.ready(), "ready_for_human")

    def test_invalid_tracking_and_escape_block(self):
        for bad in ["../outside", str(self.root.parent / "outside")]:
            with self.assertRaises(gate.GateError): gate.safe_path(self.root, bad)
        self.config["protected_roots"] = ["src"]
        with self.assertRaises(gate.GateError): gate.capture(self.root, self.config, self.issue)
        self.config["protected_roots"] = ["missing"]
        with self.assertRaises(gate.GateError): gate.capture(self.root, self.config, self.issue)

    def test_empty_checks_block(self):
        self.config["required_checks"] = []
        with self.assertRaises(gate.GateError): gate.capture(self.root, self.config, self.issue)

    def test_visual_tasks_require_visual_check(self):
        self.config["required_checks"] = ["behavior", "regression"]
        with self.assertRaises(gate.GateError): gate.capture(self.root, self.config, self.issue)

    def test_cli_capture_refuses_snapshot_overwrite(self):
        self.write("project.json", json.dumps(self.config))
        self.write("issue.json", json.dumps(self.issue))
        command = [sys.executable, str(SCRIPT), "capture", "--root", str(self.root),
                   "--config", "project.json", "--issue", "issue.json", "--out", "evidence/snapshot.json"]
        first = subprocess.run(command, capture_output=True, text=True)
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)


if __name__ == "__main__":
    unittest.main()
