"""네이버 검색 API로 브랜드 언급을 수집하고 긍정/부정/중립으로 분류해 대응 리포트를 만든다.

목적: 부정 게시물을 '숨기는' 것이 아니라 빨리 발견해 정당한 방법(공식 답변, 사실관계 정정,
명백한 허위·명예훼손에 대한 법적 게시중단 요청)으로 대응하기 위함.

준비:
  1) https://developers.naver.com 에서 애플리케이션 등록 (검색 API)
  2) export NAVER_CLIENT_ID=... NAVER_CLIENT_SECRET=...

사용법:
  python -m monitor.brand_monitor                         # config/*.toml 각각 따로 리포트
  python -m monitor.brand_monitor --config config/datapd.toml
"""

import argparse
import csv
import html
import json
import os
import re
import tomllib
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

NAVER_ENDPOINTS = {
    "블로그": "https://openapi.naver.com/v1/search/blog.json",
    "뉴스": "https://openapi.naver.com/v1/search/news.json",
    "카페": "https://openapi.naver.com/v1/search/cafearticle.json",
    "웹문서": "https://openapi.naver.com/v1/search/webkr.json",
    "지식iN": "https://openapi.naver.com/v1/search/kin.json",
}

ACTIONS = {
    "부정": "내용 확인 → 사실이면 공식 답변·개선 / 명백한 허위·명예훼손이면 플랫폼 권리침해 신고(임시조치) 검토",
    "긍정": "작성자 동의 하에 공식 채널에서 인용·감사 인사",
    "중립": "기록만",
}

_TAG = re.compile(r"<[^>]+>")


def clean(text):
    return html.unescape(_TAG.sub("", text or "")).strip()


def classify(text, negative_keywords, positive_keywords):
    """텍스트를 (분류, 매칭 키워드 목록)으로 반환. 부정 키워드가 하나라도 있으면 우선 '부정'."""
    neg = [k for k in negative_keywords if k in text]
    if neg:
        return "부정", neg
    pos = [k for k in positive_keywords if k in text]
    if pos:
        return "긍정", pos
    return "중립", []


def naver_search(url, query, client_id, client_secret, display=100):
    qs = urllib.parse.urlencode({"query": query, "display": display, "sort": "date"})
    req = urllib.request.Request(f"{url}?{qs}", headers={
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r).get("items", [])


def collect(cfg, client_id, client_secret):
    mon = cfg["monitor"]
    seen, rows = set(), []
    for query in mon["queries"]:
        for source, url in NAVER_ENDPOINTS.items():
            try:
                items = naver_search(url, query, client_id, client_secret)
            except Exception as ex:  # 한 채널 실패가 전체를 막지 않도록
                print(f"[경고] {source}/{query}: {ex}")
                continue
            for it in items:
                link = it.get("originallink") or it.get("link")
                if not link or link in seen:
                    continue
                seen.add(link)
                title, desc = clean(it.get("title")), clean(it.get("description"))
                label, hits = classify(f"{title} {desc}", mon["negative_keywords"], mon["positive_keywords"])
                rows.append({
                    "분류": label, "채널": source, "검색어": query, "제목": title, "요약": desc[:200],
                    "링크": link, "날짜": it.get("postdate") or it.get("pubDate", ""),
                    "매칭키워드": ",".join(hits), "권장대응": ACTIONS[label],
                })
    order = {"부정": 0, "긍정": 1, "중립": 2}
    rows.sort(key=lambda r: order[r["분류"]])
    return rows


def write_reports(rows, out_dir, slug, name):
    out = Path(out_dir) / slug
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = out / f"brand_mentions_{stamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: 엑셀 한글 깨짐 방지
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["분류"])
        w.writeheader()
        w.writerows(rows)

    counts = {k: sum(r["분류"] == k for r in rows) for k in ("부정", "긍정", "중립")}
    lines = [f"# {name} 모니터링 리포트 ({stamp})", "",
             f"- 전체 {len(rows)}건 · 부정 {counts['부정']} · 긍정 {counts['긍정']} · 중립 {counts['중립']}", ""]
    neg = [r for r in rows if r["분류"] == "부정"]
    if neg:
        lines += ["## 대응 검토 필요 (부정 신호)", "", "| 채널 | 제목 | 키워드 | 링크 |", "|---|---|---|---|"]
        lines += [f'| {r["채널"]} | {r["제목"].replace("|", "/")} | {r["매칭키워드"]} | {r["링크"]} |' for r in neg]
        lines += ["", f"권장 대응: {ACTIONS['부정']}", "", "자세한 절차는 docs/SEO_PLAYBOOK.md 의 '부정 콘텐츠 대응' 참고."]
    md_path = out / f"brand_report_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, md_path, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", action="append", help="생략 시 config/*.toml 전부")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        raise SystemExit("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수를 설정하세요. (developers.naver.com)")
    for path in args.config or sorted(Path("config").glob("*.toml")):
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        name = cfg["company"]["name"]
        rows = collect(cfg, cid, secret)
        csv_path, md_path, counts = write_reports(rows, args.out, cfg["slug"], name)
        print(f"[{name}] 수집 {len(rows)}건 (부정 {counts['부정']}) → {csv_path}, {md_path}")


if __name__ == "__main__":
    main()
