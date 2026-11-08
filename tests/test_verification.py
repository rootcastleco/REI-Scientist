from dataclasses import replace
import unittest

from rei_scientist.algorithms import run_seed
from rei_scientist.cli import _template
from rei_scientist.models import Proposal, StudySpec
from rei_scientist.verification import compare_holdout, verify_seed


class TestIndependentVerifier(unittest.TestCase):
    def setUp(self):
        self.spec = StudySpec.from_dict(_template("sphere", "verification-test"))
        self.baseline = Proposal.build("random_search", {})
        self.candidate = Proposal.build("hill_climb", {"step_fraction": 0.12})

    def test_detect_wrong_objective(self):
        r = run_seed(self.spec, self.baseline, 101)
        forged = replace(r, best_value=r.best_value + 10)
        self.assertTrue(any("mismatch" in msg for msg in verify_seed(self.spec, forged)))

    def test_detect_out_of_bounds(self):
        r = run_seed(self.spec, self.baseline, 101)
        forged = replace(r, best_position=(1000.0, 1000.0))
        self.assertIn("infeasible best position", verify_seed(self.spec, forged))

    def test_detect_budget_mismatch(self):
        r = run_seed(self.spec, self.baseline, 101)
        self.assertTrue(any("budget" in msg for msg in verify_seed(self.spec, replace(r, evaluations=2))))

    def test_holdout_identity_guard(self):
        base = [run_seed(self.spec, self.baseline, s) for s in self.spec.test_seeds]
        candidate = [run_seed(self.spec, self.candidate, s) for s in reversed(self.spec.test_seeds)]
        verdict = compare_holdout(self.spec, base, candidate)
        self.assertEqual(verdict["status"], "NOT VERIFIED")

    def test_insufficient_seeds_not_verified(self):
        data = _template("sphere", "small-holdout")
        data["test_seeds"] = [101, 103, 107]
        spec = StudySpec.from_dict(data)
        base = [run_seed(spec, self.baseline, s) for s in spec.test_seeds]
        candidate = [run_seed(spec, self.candidate, s) for s in spec.test_seeds]
        self.assertEqual(compare_holdout(spec, base, candidate)["status"], "NOT VERIFIED")
