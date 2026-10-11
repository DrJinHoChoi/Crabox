import json
import re
import tempfile
import unittest
from pathlib import Path

from monitor.brand_monitor import classify, clean, write_reports
from seo.generate_site import build_jsonld, generate, load_config, render_html, render_sitemap

CONFIG = Path(__file__).resolve().parent.parent / "config"
SMARTEAR = load_config(CONFIG / "smartear.toml")
DATAPD = load_config(CONFIG / "datapd.toml")


def jsonld_types(page):
    return {json.loads(b)["@type"] for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page)}


class SiteTest(unittest.TestCase):
    def test_smartear_is_organization_linked_to_brand(self):
        org = build_jsonld(SMARTEAR)[0]
        self.assertEqual((org["@type"], org["name"]), ("Organization", "스마트이어 주식회사"))
        self.assertNotIn("데이터피디", org["alternateName"])  # 이름은 섞지 않고 관계로만 연결
        self.assertEqual(org["brand"][0]["name"], "데이터피디")
        self.assertIn("taxID", org)

    def test_datapd_is_brand_without_company_fields(self):
        brand = build_jsonld(DATAPD)[0]
        self.assertEqual((brand["@type"], brand["name"]), ("Brand", "데이터피디"))
        self.assertNotIn("스마트이어", " ".join(brand["alternateName"]))
        self.assertNotIn("taxID", brand)
        self.assertEqual(brand["subjectOf"][0]["name"], "스마트이어 주식회사")

    def test_titles_are_separate(self):
        self.assertIn("<title>스마트이어 주식회사(SmartEar Co., Ltd.) 공식 홈페이지</title>", render_html(SMARTEAR))
        page = render_html(DATAPD)
        self.assertIn("<title>데이터피디(DataPD) 공식 홈페이지</title>", page)
        self.assertEqual(jsonld_types(page), {"Brand", "WebSite", "FAQPage"})

    def test_sitemap(self):
        self.assertIn("<loc>https://www.datapd.example/</loc>", render_sitemap(DATAPD))

    def test_generate_writes_per_slug(self):
        with tempfile.TemporaryDirectory() as d:
            for cfg in ("smartear.toml", "datapd.toml"):
                generate(CONFIG / cfg, d)
            self.assertTrue((Path(d) / "smartear" / "index.html").exists())
            self.assertTrue((Path(d) / "datapd" / "sitemap.xml").exists())


class MonitorTest(unittest.TestCase):
    def test_classify_per_entity_keywords(self):
        m = DATAPD["monitor"]
        self.assertEqual(classify("데이터피디 환불 안해줌", m["negative_keywords"], m["positive_keywords"])[0], "부정")
        self.assertEqual(classify("데이터피디 강력 추천", m["negative_keywords"], m["positive_keywords"])[0], "긍정")
        m = SMARTEAR["monitor"]
        self.assertEqual(classify("스마트이어 임금 체불", m["negative_keywords"], m["positive_keywords"])[0], "부정")
        self.assertEqual(classify("스마트이어 소개", m["negative_keywords"], m["positive_keywords"]), ("중립", []))

    def test_clean(self):
        self.assertEqual(clean("<b>데이터피디</b> &amp; 스마트이어"), "데이터피디 & 스마트이어")

    def test_reports_written_per_slug(self):
        with tempfile.TemporaryDirectory() as d:
            _, md, counts = write_reports([], d, "datapd", "데이터피디")
            self.assertEqual(md.parent.name, "datapd")
            self.assertTrue(md.read_text(encoding="utf-8").startswith("# 데이터피디 모니터링 리포트"))
            self.assertEqual(counts["부정"], 0)


if __name__ == "__main__":
    unittest.main()
