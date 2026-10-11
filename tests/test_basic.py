import json
import re
import tempfile
import unittest
from pathlib import Path

from monitor.brand_monitor import classify, clean, is_legacy, write_reports
from seo.generate_site import build_jsonld, generate, load_config, render_html, render_sitemap

CONFIG = Path(__file__).resolve().parent.parent / "config"
SMARTEAR = load_config(CONFIG / "smartear.toml")
DATAPD = load_config(CONFIG / "datapd.toml")
DRCHOI = load_config(CONFIG / "drchoistudio.toml")


def jsonld_types(page):
    return {json.loads(b)["@type"] for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page)}


class SiteTest(unittest.TestCase):
    def test_smartear_is_organization(self):
        org = build_jsonld(SMARTEAR)[0]
        self.assertEqual((org["@type"], org["name"]), ("Organization", "스마트이어 주식회사"))
        self.assertIn("taxID", org)

    def test_datapd_is_separate_sole_proprietorship(self):
        biz = build_jsonld(DATAPD)[0]
        self.assertEqual((biz["@type"], biz["legalName"]), ("Organization", "데이터피디"))
        self.assertIn("taxID", biz)  # 자체 사업자등록번호
        self.assertIn("개인사업자", render_html(DATAPD))

    def test_identities_are_independent(self):
        # 어느 쪽 페이지에도 상대 엔티티의 이름·도메인이 나오지 않아야 함
        pairs = [(SMARTEAR, DATAPD), (DATAPD, SMARTEAR)]
        for cfg, other in pairs:
            page = render_html(cfg)
            for token in [other["company"]["name"], other["company"]["name_en"], other["site"]["url"]]:
                self.assertNotIn(token, page)
            for key in ("brand", "parentOrganization", "subOrganization", "subjectOf"):
                self.assertNotIn(key, build_jsonld(cfg)[0])

    def test_titles_are_separate(self):
        self.assertIn("<title>스마트이어 주식회사(SmartEar Co., Ltd.) 공식 홈페이지</title>", render_html(SMARTEAR))
        page = render_html(DATAPD)
        self.assertIn("<title>데이터피디(DataPD) 공식 홈페이지</title>", page)
        self.assertEqual(jsonld_types(page), {"Organization", "WebSite", "FAQPage"})

    def test_sitemap(self):
        self.assertIn("<loc>https://www.datapd.example/</loc>", render_sitemap(DATAPD))

    def test_generate_writes_per_slug(self):
        with tempfile.TemporaryDirectory() as d:
            for cfg in ("smartear.toml", "datapd.toml"):
                generate(CONFIG / cfg, d)
            self.assertTrue((Path(d) / "smartear" / "index.html").exists())
            self.assertTrue((Path(d) / "datapd" / "sitemap.xml").exists())


class DrChoiStudioTest(unittest.TestCase):
    def test_official_url_is_canonical(self):
        page = render_html(DRCHOI)
        self.assertIn('<link rel="canonical" href="https://drchoistudio.datapd.ai/">', page)
        self.assertNotIn("<h2>서비스</h2>", page)  # 서비스 미입력 시 빈 섹션 없음
        self.assertEqual(build_jsonld(DRCHOI)[0]["@type"], "Brand")

    def test_legacy_redirect_only_when_listed(self):
        with tempfile.TemporaryDirectory() as d:
            generate(CONFIG / "drchoistudio.toml", d)
            self.assertEqual(bool(DRCHOI["site"]["legacy_urls"]), (Path(d) / "drchoistudio" / "legacy_redirect.html").exists())
            cfg_path = Path(d) / "c.toml"
            cfg_path.write_text(
                (CONFIG / "drchoistudio.toml").read_text(encoding="utf-8")
                .replace("legacy_urls = []", 'legacy_urls = ["https://old.example.com"]'), encoding="utf-8")
            generate(cfg_path, d)
            page = (Path(d) / "drchoistudio" / "legacy_redirect.html").read_text(encoding="utf-8")
            self.assertIn('url=https://drchoistudio.datapd.ai/', page)
            self.assertIn('content="noindex, follow"', page)

    def test_is_legacy(self):
        legacy = ["https://old-drchoi.example.com", "blog.example.com/drchoi"]
        self.assertTrue(is_legacy("https://www.old-drchoi.example.com/price", legacy))
        self.assertTrue(is_legacy("https://m.old-drchoi.example.com/", legacy))
        self.assertTrue(is_legacy("https://blog.example.com/drchoi/123", legacy))
        self.assertFalse(is_legacy("https://blog.example.com/someoneelse", legacy))
        self.assertFalse(is_legacy("https://blog.example.com/drchoi2", legacy))
        self.assertFalse(is_legacy("https://drchoistudio.datapd.ai/", legacy))

    def test_report_lists_legacy_hits(self):
        row = {"분류": "중립", "채널": "웹문서", "검색어": "최박사 사진관", "제목": "최박사 사진관", "요약": "",
               "링크": "https://old-drchoi.example.com/", "날짜": "", "매칭키워드": "", "구버전": "Y", "권장대응": ""}
        with tempfile.TemporaryDirectory() as d:
            _, md, _ = write_reports([row], d, "drchoistudio", "최박사 사진관")
            self.assertIn("## 예전(중복) 사이트 노출", md.read_text(encoding="utf-8"))


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
