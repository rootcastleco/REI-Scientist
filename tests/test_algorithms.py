import math
import unittest

from rei_scientist.algorithms import run_seed
from rei_scientist.cli import _template
from rei_scientist.models import Proposal, StudySpec
from rei_scientist.objectives import evaluate
from rei_scientist.verification import reference_objective, verify_seed


class TestAlgorithms(unittest.TestCase):
    def setUp(self):
        data = _template("sphere", "algorithm-test")
        data["evaluation_budget"] = 41
        self.spec = StudySpec.from_dict(data)

    def test_reproducible_registered_solvers(self):
        proposals = [
            Proposal.build("random_search", {}),
            Proposal.build("hill_climb", {"step_fraction": 0.1}),
            Proposal.build("simulated_annealing", {"step_fraction": 0.1, "temperature": 1.5, "cooling": 0.97}),
        ]
        for p in proposals:
            with self.subTest(method=p.method):
                first = run_seed(self.spec, p, 17)
                second = run_seed(self.spec, p, 17)
                self.assertEqual(first.evaluations, 41)
                self.assertEqual(first.best_position, second.best_position)
                self.assertEqual(first.best_value, second.best_value)
                self.assertEqual(first.trace_sha256, second.trace_sha256)
                self.assertEqual(verify_seed(self.spec, first), [])

    def test_analytic_optima(self):
        for objective, point, expected in (
            ("sphere", (0.0, 0.0), 0.0),
            ("rastrigin", (0.0, 0.0), 0.0),
            ("rosenbrock", (1.0, 1.0), 0.0),
            ("ackley", (0.0, 0.0), 0.0),
        ):
            with self.subTest(objective=objective):
                self.assertAlmostEqual(evaluate(objective, point), expected, delta=1e-9)
                self.assertAlmostEqual(reference_objective(objective, point), expected, delta=1e-9)

    def test_cross_formula_many_inputs(self):
        points = [(0.1, 2.2), (-4.0, 3.1), (0.0, 0.0), (1.1, -2.3), (3.2, 4.5)]
        for objective in ("sphere", "rastrigin", "rosenbrock", "ackley"):
            for point in points:
                self.assertAlmostEqual(evaluate(objective, point), reference_objective(objective, point), delta=1e-9)

    def test_dimension_and_finite_guard(self):
        with self.assertRaises(ValueError):
            evaluate("sphere", (float("nan"), 1.0))
        with self.assertRaises(ValueError):
            evaluate("sphere", (0.0,))
