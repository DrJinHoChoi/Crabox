"""config/brand.toml 을 읽어 검색엔진 최적화된 공식 랜딩 페이지를 생성한다.

생성물 (site/):
  index.html   - title/description/OG 메타, schema.org JSON-LD(Organization, WebSite, FAQPage)
  robots.txt   - 크롤링 허용 + sitemap 위치
  sitemap.xml  - 네이버 서치어드바이저 / 구글 서치콘솔 제출용

사용법:
  python -m seo.generate_site [--config config/brand.toml] [--out site]
"""

import argparse
import html
import json
import tomllib
from datetime import date
from pathlib import Path


def load_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def build_jsonld(cfg):
    c, s = cfg["company"], cfg["site"]
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": c["legal_name"],
        "alternateName": [c["brand"], c["brand_en"], c["legal_name_en"], *c.get("alternate_names", [])],
        "url": s["url"],
        "logo": s["logo"],
        "description": c["description"],
        "foundingDate": c["founded"],
        "founder": {"@type": "Person", "name": c["ceo"]},
        "taxID": c["business_number"],
        "email": c["email"],
        "telephone": c["phone"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": c["address_street"],
            "addressLocality": c["address_locality"],
            "postalCode": c["postal_code"],
            "addressCountry": "KR",
        },
        "brand": {"@type": "Brand", "name": c["brand"], "alternateName": c["brand_en"]},
        "sameAs": s.get("same_as", []),
        "makesOffer": [
            {"@type": "Offer", "itemOffered": {"@type": "Service", "name": sv["name"], "description": sv["description"]}}
            for sv in cfg.get("services", [])
        ],
    }
    # 중복 제거 (순서 유지)
    org["alternateName"] = list(dict.fromkeys(n for n in org["alternateName"] if n and n != c["legal_name"]))
    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": f'{c["brand"]} | {c["legal_name"]}',
        "alternateName": c["brand_en"],
        "url": s["url"],
        "inLanguage": "ko-KR",
    }
    blocks = [org, website]
    if cfg.get("faq"):
        blocks.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in cfg["faq"]
            ],
        })
    return blocks


def render_html(cfg):
    c, s = cfg["company"], cfg["site"]
    e = html.escape
    title = f'{c["brand"]}({c["brand_en"]}) | {c["legal_name"]} 공식 홈페이지'
    desc = c["description"]
    keywords = ", ".join(dict.fromkeys([c["legal_name"], c["brand"], c["brand_en"], *c.get("alternate_names", [])]))

    verify = ""
    if s.get("naver_site_verification"):
        verify += f'  <meta name="naver-site-verification" content="{e(s["naver_site_verification"])}">\n'
    if s.get("google_site_verification"):
        verify += f'  <meta name="google-site-verification" content="{e(s["google_site_verification"])}">\n'

    jsonld = "\n".join(
        f'  <script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>'
        for b in build_jsonld(cfg)
    )
    services = "\n".join(
        f'      <li><h3>{e(sv["name"])}</h3><p>{e(sv["description"])}</p></li>' for sv in cfg.get("services", [])
    )
    faqs = "\n".join(
        f'      <details><summary>{e(f["q"])}</summary><p>{e(f["a"])}</p></details>' for f in cfg.get("faq", [])
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}">
  <meta name="keywords" content="{e(keywords)}">
  <link rel="canonical" href="{e(s["url"])}/">
{verify}  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{e(c["brand"])}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:url" content="{e(s["url"])}/">
  <meta property="og:image" content="{e(s["og_image"])}">
  <meta property="og:locale" content="ko_KR">
  <meta name="twitter:card" content="summary_large_image">
{jsonld}
  <style>
    body {{ font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; margin: 0; color: #111; background: #fff; line-height: 1.6; }}
    header, section, footer {{ max-width: 960px; margin: 0 auto; padding: 32px 16px; }}
    h1 {{ font-size: 2rem; margin: 0 0 8px; }}
    ul {{ list-style: none; padding: 0; display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
    li {{ border: 1px solid #e5e5e5; border-radius: 12px; padding: 16px; }}
    footer {{ font-size: .85rem; color: #555; border-top: 1px solid #eee; }}
  </style>
</head>
<body>
  <header>
    <h1>{e(c["brand"])} <small>({e(c["brand_en"])})</small></h1>
    <p><strong>{e(c["legal_name"])}</strong> — {e(c["tagline"])}</p>
    <p>{e(desc)}</p>
  </header>
  <section>
    <h2>서비스</h2>
    <ul>
{services}
    </ul>
  </section>
  <section>
    <h2>자주 묻는 질문</h2>
{faqs}
  </section>
  <footer>
    <p>{e(c["legal_name"])} ({e(c["legal_name_en"])}) · 대표 {e(c["ceo"])} · 사업자등록번호 {e(c["business_number"])}</p>
    <p>{e(c["address_locality"])} {e(c["address_street"])} · {e(c["phone"])} · {e(c["email"])}</p>
  </footer>
</body>
</html>
"""


def render_robots(cfg):
    return f'User-agent: *\nAllow: /\n\nSitemap: {cfg["site"]["url"]}/sitemap.xml\n'


def render_sitemap(cfg, pages=("/",)):
    today = date.today().isoformat()
    urls = "\n".join(
        f'  <url><loc>{html.escape(cfg["site"]["url"] + p)}</loc><lastmod>{today}</lastmod></url>' for p in pages
    )
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/brand.toml")
    ap.add_argument("--out", default="site")
    args = ap.parse_args()

    cfg = load_config(args.config)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_html(cfg), encoding="utf-8")
    (out / "robots.txt").write_text(render_robots(cfg), encoding="utf-8")
    (out / "sitemap.xml").write_text(render_sitemap(cfg), encoding="utf-8")
    print(f"생성 완료: {out}/index.html, robots.txt, sitemap.xml")


if __name__ == "__main__":
    main()
