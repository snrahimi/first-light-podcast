"""Offline editorial-value telemetry tests; no network or audio."""
import unittest

from src.official_context36 import review_official_context


def lead(excerpts):
    return {
        "headline": "NASA launches ocean monitoring satellite",
        "claims": [{
            "exact_excerpt": "NASA launches ocean monitoring satellite on Tuesday."
        }],
        "official_issuer_excerpts": [
            {"issuer": "NASA News Releases",
             "url": "https://www.nasa.gov/news-release/ocean",
             "exact_excerpt": text} for text in excerpts
        ],
    }


class OfficialContextValueTests(unittest.TestCase):
    def test_distinct_details_are_only_candidates_not_verified_facts(self):
        result = review_official_context([lead([
            "The mission carries radar instruments measuring coastal erosion "
            "and ocean salinity across the Pacific basin every week."
        ])])
        self.assertEqual(result["official_excerpts_compared"], 1)
        self.assertEqual(result["distinct_detail_candidates"], 1)
        self.assertFalse(result["independent_factual_verification"])
        self.assertFalse(result["proven_editorial_usefulness"])
        self.assertFalse(result["automatic_broadcast_approval"])
        self.assertTrue(result["human_review_needed"])
        self.assertTrue(result["leads"][0]["comparison"][0][
            "editorial_human_review_required"
        ])

    def test_repeating_rss_context_is_not_a_distinct_detail(self):
        result = review_official_context([lead([
            "NASA launches ocean monitoring satellite on Tuesday."
        ])])
        self.assertEqual(result["distinct_detail_candidates"], 0)

    def test_untrusted_or_oversize_material_not_included(self):
        sample = lead([
            "Unexpectedly long " * 50,
            "Short.",
        ])
        sample["official_issuer_excerpts"].append({
            "issuer": "NASA", "url": "http://bad.example/a",
            "exact_excerpt": "This line should not be included in the audit.",
        })
        result = review_official_context([sample])
        self.assertEqual(result["official_excerpts_compared"], 1)
        self.assertEqual(result["distinct_detail_candidates"], 0)

    def test_bounded_to_two_leads_and_twelve_excerpts(self):
        leads = [lead(["The mission carries radar instruments measuring "
                       "coastal erosion along oceans and river deltas."] * 20)
                 for _ in range(4)]
        result = review_official_context(leads)
        self.assertEqual(len(result["leads"]), 2)
        self.assertEqual(result["official_excerpts_compared"], 12)


if __name__ == "__main__":
    unittest.main()
