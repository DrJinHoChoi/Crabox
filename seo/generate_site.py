"""config/*.toml 을 읽어 엔티티(회사/브랜드)별로 검색엔진 최적화된 공식 랜딩 페이지를 따로 생성한다.

각 엔티티는 검색엔진에 완전히 독립된 정체성으로 알린다 (상호 링크·관계 속성 없음).

생성물 (site/<slug>/):
  index.html   - title/description/OG 메타, schema.org JSON-LD(Organization|Brand, WebSite, FAQPage)
  robots.txt   - 크롤링 허용 + sitemap 위치
  sitemap.xml  - 네이버 서치어드바이저 / 구글 서치콘솔 제출용

사용법:
  python -m seo.generate_site                       # config/*.toml 전부 (스마트이어, 데이터피디 각각)
  python -m seo.generate_site --config config/datapd.toml
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


def _names(c):
    return list(dict.fromkeys(n for n in [c.get("name_en"), *c.get("alternate_names", [])] if n and n != c["name"]))


def build_jsonld(cfg):
    c, s = cfg["company"], cfg["site"]
    is_brand = c.get("type") == "Brand"
    entity = {
        "@context": "https://schema.org",
        "@type": "Brand" if is_brand else "Organization",
        "name": c["name"],
        "alternateName": _names(c),
        "url": s["url"],
        "logo": s["logo"],
        "description": c["description"],
        "sameAs": s.get("same_as", []),
    }
    if c.get("keywords"):
        entity["knowsAbout"] = c["keywords"]
    optional = {"foundingDate": "founded", "taxID": "business_number", "email": "email", "telephone": "phone"}
    if c.get("legal_form"):
        entity["legalName"] = c["name"]
    if not is_brand:  # Brand 타입에는 사업자 고유 속성을 넣지 않음
        entity.update({k: c[v] for k, v in optional.items() if c.get(v)})
        if c.get("ceo"):
            entity["founder"] = {"@type": "Person", "name": c["ceo"]}
        if c.get("address_street"):
            entity["address"] = {
                "@type": "PostalAddress",
                "streetAddress": c["address_street"],
                "addressLocality": c.get("address_locality", ""),
                "postalCode": c.get("postal_code", ""),
                "addressCountry": "KR",
            }
        if cfg.get("services"):
            entity["makesOffer"] = [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": sv["name"], "description": sv["description"]}}
                for sv in cfg["services"]
            ]

    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": c["name"],
        "alternateName": _names(c),
        "url": s["url"],
        "inLanguage": "ko-KR",
    }
    blocks = [entity, website]
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
    title = f'{c["name"]}({c["name_en"]}) 공식 홈페이지' if c.get("name_en") else f'{c["name"]} 공식 홈페이지'
    desc = c["description"]
    keywords = ", ".join([c["name"], *_names(c), *c.get("keywords", [])])

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
    footer = [e(c["name"]) + (f' ({e(c["name_en"])})' if c.get("name_en") else "")]
    if c.get("legal_form"):
        footer.append(e(c["legal_form"]))
    if c.get("ceo"):
        footer.append(f'대표 {e(c["ceo"])}')
    if c.get("business_number"):
        footer.append(f'사업자등록번호 {e(c["business_number"])}')
    contact = [x for x in (
        f'{c.get("address_locality", "")} {c.get("address_street", "")}'.strip(), c.get("phone"), c.get("email")
    ) if x]
    sub = f' <small>({e(c["name_en"])})</small>' if c.get("name_en") else ""
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
  <meta property="og:site_name" content="{e(c["name"])}">
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
    <h1>{e(c["name"])}{sub}</h1>
    <p><strong>{e(c["tagline"])}</strong></p>
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
    <p>{" · ".join(footer)}</p>
    <p>{" · ".join(e(x) for x in contact)}</p>
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


def generate(config_path, out_root):
    cfg = load_config(config_path)
    out = Path(out_root) / cfg["slug"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_html(cfg), encoding="utf-8")
    (out / "robots.txt").write_text(render_robots(cfg), encoding="utf-8")
    (out / "sitemap.xml").write_text(render_sitemap(cfg), encoding="utf-8")
    return cfg["company"]["name"], out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", action="append", help="생략 시 config/*.toml 전부")
    ap.add_argument("--out", default="site")
    args = ap.parse_args()

    for path in args.config or sorted(Path("config").glob("*.toml")):
        name, out = generate(path, args.out)
        print(f"[{name}] 생성 완료: {out}/index.html, robots.txt, sitemap.xml")


if __name__ == "__main__":
    main()
