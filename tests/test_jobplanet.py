import unittest
from datetime import date
from pathlib import Path

from jobplanet.review_analyzer import DEFAULT_THEMES, analyze, draft_reply, load_reviews, render_report

ROOT = Path(__file__).resolve().parent.parent


class JobplanetTest(unittest.TestCase):
    def setUp(self):
        self.reviews = load_reviews(ROOT / "data" / "jobplanet_reviews.sample.csv")
        self.res = analyze(self.reviews, DEFAULT_THEMES, 2, today=date(2026, 10, 11))

    def test_period_split(self):
        self.assertEqual(self.res["period_n"], {"과거": 3, "최근": 3})
        self.assertLess(self.res["period_avg"]["과거"], self.res["period_avg"]["최근"])

    def test_theme_shift(self):
        shift = {t: (o, n) for t, o, n in self.res["theme_shift"]}
        old, new = shift["야근·워라밸"]
        self.assertGreater(old, new)
        self.assertIn("연봉·보상", shift)

    def test_unanswered_low_rated_only(self):
        self.assertTrue(all(not r["답변"] and r["별점"] <= 3 for r in self.res["unanswered"]))
        self.assertEqual(len(self.res["unanswered"]), 3)

    def test_reply_draft_requires_fact(self):
        for r in self.res["unanswered"]:
            self.assertIn("{개선사항}", draft_reply(r))

    def test_report_render(self):
        report = render_report(self.res)
        self.assertIn("개선 → 홍보 소재", report)
        self.assertIn("여전함 → 실제 개선 필요", report)


if __name__ == "__main__":
    unittest.main()
