import unittest

from rei_scientist.cli import _template
from rei_scientist.models import Proposal, StudySpec
from rei_scientist.search import run_search


class TestTreeSearch(unittest.TestCase):
    def setUp(self):
        data = _template("sphere", "tree-search-test")
        data["evaluation_budget"] = 35
        data["candidate_budget"] = 5
        self.spec = StudySpec.from_dict(data)

    def test_search_is_bounded_and_test_seeds_unused_during_selection(self):
        outcome = run_search(self.spec)
        self.assertLessEqual(len(outcome.leaderboard) - 1, self.spec.candidate_budget)
        self.assertEqual(len(outcome.holdout_baseline), len(self.spec.test_seeds))
        self.assertEqual(len(outcome.holdout_selected), len(self.spec.test_seeds))
        for group in outcome.dev_runs.values():
            self.assertEqual({r.seed for r in group}, set(self.spec.dev_seeds))
        for group in (outcome.holdout_baseline, outcome.holdout_selected):
            self.assertEqual({r.seed for r in group}, set(self.spec.test_seeds))
        self.assertNotIn(outcome.selected.method, {"random_search"})

    def test_search_deterministic_without_elapsed_times(self):
        a = run_search(self.spec)
        b = run_search(self.spec)
        self.assertEqual(a.selected.key, b.selected.key)
        self.assertEqual(a.leaderboard, b.leaderboard)
        self.assertEqual(a.verdict, b.verdict)

    def test_reject_unregistered_external_proposal(self):
        with self.assertRaisesRegex(ValueError, "permitted"):
            run_search(self.spec, [Proposal.build("random_search", {})])

    def test_parent_links_are_consistent(self):
        outcome = run_search(self.spec)
        nodes = {r["key"] for r in outcome.leaderboard}
        for row in outcome.leaderboard:
            if row["parent"]:
                self.assertIn(row["parent"], nodes)
                self.assertGreater(row["depth"], 0)
