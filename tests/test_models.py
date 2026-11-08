import copy
import math
import unittest

from rei_scientist.cli import _template
from rei_scientist.models import Proposal, StudySpec, StudyValidationError


class TestStudyContract(unittest.TestCase):
    def setUp(self):
        self.data = _template("sphere", "safe-study-01")

    def test_valid_study(self):
        spec = StudySpec.from_dict(self.data)
        self.assertEqual(spec.study_id, "safe-study-01")
        self.assertEqual(len(spec.test_seeds), 5)

    def test_roundtrip_json_dict(self):
        original = StudySpec.from_dict(self.data)
        self.assertEqual(StudySpec.from_dict(original.to_dict()), original)

    def test_overlap_rejected(self):
        self.data["test_seeds"][0] = 11
        with self.assertRaisesRegex(StudyValidationError, "overlap"):
            StudySpec.from_dict(self.data)

    def test_invalid_slug_rejected(self):
        self.data["study_id"] = "../evil"
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(self.data)

    def test_unknown_algorithm_rejected(self):
        self.data["methods"] = ["random_search", "unsafe_exec"]
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(self.data)

    def test_nan_bounds_rejected(self):
        self.data["bounds"] = [-5, float("nan")]
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(self.data)

    def test_unreasonable_budget_rejected(self):
        self.data["evaluation_budget"] = 999999999
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(self.data)

    def test_bool_is_not_int(self):
        self.data["dimension"] = True
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(self.data)

    def test_extra_field_rejected(self):
        self.data["code"] = "__import__('os').system('rm -rf /')"
        with self.assertRaises(StudyValidationError):
            StudySpec.from_dict(self.data)

    def test_proposal_schema_rejects_code(self):
        with self.assertRaises(StudyValidationError):
            Proposal.build("hill_climb", {"step_fraction": 0.1, "code": "print('x')"})

    def test_proposal_key_stable(self):
        a = Proposal.build("hill_climb", {"step_fraction": 0.12})
        b = Proposal.build("hill_climb", {"step_fraction": 0.12}, depth=1)
        self.assertEqual(a.key, b.key)
