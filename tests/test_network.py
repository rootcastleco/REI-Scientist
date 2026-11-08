import unittest
from unittest.mock import patch

from rei_scientist.cli import _template
from rei_scientist.literature import search_crossref
from rei_scientist.llm import propose_candidates
from rei_scientist.models import StudySpec, StudyValidationError
from rei_scientist.network import NetworkSecurityError, secure_https


class TestRemoteBoundaries(unittest.TestCase):
    def test_ssrf_prevented(self):
        hosts = frozenset({"api.openai.com"})
        for url in ["http://api.openai.com/v1/chat/completions", "https://127.0.0.1/",
                    "https://api.openai.com.evil.test/v1/chat/completions",
                    "https://api.openai.com:4443/v1/chat/completions",
                    "https://user:secret@api.openai.com/v1/chat/completions"]:
            with self.subTest(url=url), self.assertRaises(NetworkSecurityError):
                secure_https(url, hosts)

    def test_valid_approved_host(self):
        secure_https("https://api.openai.com/v1/chat/completions", frozenset({"api.openai.com"}))

    def test_llm_proposal_with_code_is_rejected(self):
        spec = StudySpec.from_dict(_template("sphere", "llm-test-01"))
        response = {"proposals": [{"method": "hill_climb", "params": {"step_fraction": 0.1, "code": "print('unsafe')"}}]}
        with patch("rei_scientist.llm.complete_json", return_value=response):
            with self.assertRaises(StudyValidationError):
                propose_candidates(spec)

    def test_llm_approved_json_only(self):
        spec = StudySpec.from_dict(_template("sphere", "llm-test-02"))
        response = {"proposals": [{"method": "hill_climb", "params": {"step_fraction": 0.1}}]}
        with patch("rei_scientist.llm.complete_json", return_value=response):
            proposals = propose_candidates(spec)
            self.assertEqual(proposals[0].method, "hill_climb")

    def test_crossref_metadata_no_fulltext_claim(self):
        response = {"message": {"items": [{"DOI": "10.1000/example", "title": ["Dummy result"],
                                                  "published": {"date-parts": [[2025, 1, 1]]}}]}}
        with patch("rei_scientist.literature.get_json", return_value=response):
            record = search_crossref("random numerical optimization")
        self.assertEqual(record[0]["doi"], "10.1000/example")
        self.assertIn("full text not read", record[0]["provenance"])
