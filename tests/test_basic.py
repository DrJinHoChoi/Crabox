import json
import re
import unittest
from pathlib import Path

from monitor.brand_monitor import classify, clean
from seo.generate_site import build_jsonld, load_config, render_html, render_sitemap

CFG = load_config(Path(__file__).resolve().parent.parent / "config" / "brand.toml")


class SiteTest(unittest.TestCase):
    def test_jsonld_has_names(self):
        org = build_jsonld(CFG)[0]
        self.assertEqual(org["name"], "스마트이어 주식회사")
        self.assertIn("데이터피디", org["alternateName"])
        self.assertEqual(len(org["alternateName"]), len(set(org["alternateName"])))

    def test_html_contains_valid_jsonld(self):
        page = render_html(CFG)
        self.assertIn("<title>데이터피디(DataPD) | 스마트이어 주식회사 공식 홈페이지</title>", page)
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page)
        self.assertEqual({json.loads(b)["@type"] for b in blocks}, {"Organization", "WebSite", "FAQPage"})

    def test_sitemap(self):
        self.assertIn("<loc>https://www.example.com/</loc>", render_sitemap(CFG))


class MonitorTest(unittest.TestCase):
    neg, pos = CFG["monitor"]["negative_keywords"], CFG["monitor"]["positive_keywords"]

    def test_classify(self):
        self.assertEqual(classify("데이터피디 환불 안해줌", self.neg, self.pos)[0], "부정")
        self.assertEqual(classify("데이터피디 강력 추천", self.neg, self.pos)[0], "긍정")
        self.assertEqual(classify("데이터피디 소개", self.neg, self.pos), ("중립", []))

    def test_clean(self):
        self.assertEqual(clean("<b>데이터피디</b> &amp; 스마트이어"), "데이터피디 & 스마트이어")


if __name__ == "__main__":
    unittest.main()
