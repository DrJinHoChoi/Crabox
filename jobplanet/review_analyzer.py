"""잡플래닛 기업 리뷰를 기간별로 분석해 '과거 이미지 → 현재 모습' 대응 자료를 만든다.

잡플래닛은 자동 수집(크롤링)을 허용하지 않으므로, 기업회원 화면에서 리뷰를 직접 옮겨 적은 CSV를 입력으로 쓴다.

입력 CSV (UTF-8, 헤더 필수):
  날짜,직무,별점,장점,단점,기업답변여부
  2021-03-02,마케팅,2,"분위기 좋음","야근 많고 체계 없음",N

산출물 (reports/jobplanet/):
  - 연도별 평균 별점 / 리뷰 수
  - 과거 vs 최근 주제별 언급 비율 (개선된 주제, 여전히 남은 주제)
  - 기업 답변이 없는 리뷰 목록 + 주제별 답변 초안 (실제 개선 사항을 채워 넣어야 함)

사용법:
  python -m jobplanet.review_analyzer data/jobplanet_reviews.csv                              # 스마트이어
  python -m jobplanet.review_analyzer data/datapd_reviews.csv --config config/datapd.toml     # 데이터피디
"""

import argparse
import csv
import tomllib
from collections import defaultdict
from datetime import date
from pathlib import Path

# 리뷰 단점 문장에서 탐지할 주제 키워드 (config 의 [jobplanet.themes] 로 덮어쓸 수 있음)
DEFAULT_THEMES = {
    "연봉·보상": ["연봉", "급여", "월급", "보상", "인상", "성과급", "인센"],
    "야근·워라밸": ["야근", "워라밸", "칼퇴", "주말", "초과근무", "업무량"],
    "경영진·리더십": ["대표", "경영진", "임원", "오너", "독단", "비전"],
    "조직문화·소통": ["소통", "문화", "분위기", "갑질", "수평", "꼰대", "눈치"],
    "체계·프로세스": ["체계", "시스템", "프로세스", "주먹구구", "업무분장", "인수인계"],
    "성장·교육": ["성장", "교육", "배울", "커리어", "역량"],
    "고용안정·이직률": ["퇴사", "이직", "물갈이", "안정", "권고사직"],
    "복지": ["복지", "식대", "휴가", "연차", "장비", "재택"],
}

# 주제별 답변 초안 — {개선사항} 은 반드시 '실제로 바뀐 사실'로 채운다 (허위 기재 금지)
REPLY_TEMPLATES = {
    "연봉·보상": "소중한 의견 감사합니다. 말씀하신 보상 문제는 회사도 무겁게 받아들였고, {개선사항}을(를) 시행했습니다.",
    "야근·워라밸": "솔직한 의견 감사합니다. 업무량과 근무시간 문제를 개선하기 위해 {개선사항}을(를) 도입해 운영 중입니다.",
    "경영진·리더십": "의견 감사합니다. 경영진 소통 방식에 대한 지적을 반영해 {개선사항}을(를) 진행하고 있습니다.",
    "조직문화·소통": "남겨주신 의견 감사합니다. 조직문화 개선을 위해 {개선사항}을(를) 시행했고 계속 점검하고 있습니다.",
    "체계·프로세스": "의견 감사합니다. 업무 체계가 부족했던 점을 인정하며, {개선사항}을(를) 정비했습니다.",
    "성장·교육": "의견 감사합니다. 구성원 성장을 지원하기 위해 {개선사항}을(를) 운영하고 있습니다.",
    "고용안정·이직률": "의견 감사합니다. 안정적인 근무 환경을 위해 {개선사항}을(를) 마련했습니다.",
    "복지": "의견 감사합니다. 복지 관련 의견을 반영해 {개선사항}을(를) 새로 도입했습니다.",
}
DEFAULT_REPLY = "소중한 의견 감사합니다. 말씀하신 부분을 내부에서 공유했고, {개선사항}을(를) 통해 개선해 나가고 있습니다."


def load_reviews(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r["날짜"] = date.fromisoformat(r["날짜"].strip()[:10])
            r["별점"] = float(r["별점"])
            r["답변"] = r.get("기업답변여부", "").strip().upper() in ("Y", "YES", "O", "1", "TRUE")
            rows.append(r)
    return rows


def detect_themes(text, themes):
    return [name for name, kws in themes.items() if any(k in text for k in kws)]


def analyze(reviews, themes, recent_years, today=None):
    today = today or date.today()
    cutoff = date(today.year - recent_years, today.month, min(today.day, 28))

    by_year = defaultdict(list)
    period = {"과거": [], "최근": []}
    for r in reviews:
        by_year[r["날짜"].year].append(r["별점"])
        r["단점주제"] = detect_themes(r.get("단점", ""), themes)
        period["최근" if r["날짜"] >= cutoff else "과거"].append(r)

    yearly = {y: (round(sum(v) / len(v), 2), len(v)) for y, v in sorted(by_year.items())}

    def ratio(rs, theme):
        return sum(theme in r["단점주제"] for r in rs) / len(rs) if rs else 0.0

    theme_shift = []
    for t in themes:
        old, new = ratio(period["과거"], t), ratio(period["최근"], t)
        if old or new:
            theme_shift.append((t, old, new))
    theme_shift.sort(key=lambda x: x[1] - x[2], reverse=True)

    def avg(rs):
        return round(sum(r["별점"] for r in rs) / len(rs), 2) if rs else None

    return {
        "cutoff": cutoff,
        "yearly": yearly,
        "period_avg": {k: avg(v) for k, v in period.items()},
        "period_n": {k: len(v) for k, v in period.items()},
        "theme_shift": theme_shift,
        "unanswered": [r for r in reviews if not r["답변"] and r["별점"] <= 3],
    }


def draft_reply(review):
    themes = review.get("단점주제") or []
    return REPLY_TEMPLATES.get(themes[0], DEFAULT_REPLY) if themes else DEFAULT_REPLY


def render_report(res):
    pa, pn = res["period_avg"], res["period_n"]
    lines = [
        "# 잡플래닛 리뷰 분석 — 과거 vs 현재", "",
        f"- 기준일: {res['cutoff']} 이후 = **최근**",
        f"- 과거 평균 별점 {pa['과거']} ({pn['과거']}건) → 최근 {pa['최근']} ({pn['최근']}건)", "",
        "## 연도별 별점", "", "| 연도 | 평균 | 리뷰 수 |", "|---|---|---|",
        *[f"| {y} | {a} | {n} |" for y, (a, n) in res["yearly"].items()], "",
        "## 단점 주제 변화 (리뷰 중 언급 비율)", "", "| 주제 | 과거 | 최근 | 판단 |", "|---|---|---|---|",
    ]
    for t, old, new in res["theme_shift"]:
        if not old:
            verdict = "신규 이슈 → 원인 점검"
        elif new < old * 0.7:
            verdict = "개선 → 홍보 소재"
        else:
            verdict = "여전함 → 실제 개선 필요"
        lines.append(f"| {t} | {old:.0%} | {new:.0%} | {verdict} |")
    lines += [
        "", "> '개선' 주제는 채용 페이지·기업 소개에 **구체적 사실(제도명, 시행일, 수치)**로 알리고,",
        "> '여전함' 주제는 홍보보다 **실제 개선이 먼저**입니다. 이미지가 바뀌지 않는 원인입니다.", "",
        f"## 기업 답변이 없는 별점 3점 이하 리뷰 ({len(res['unanswered'])}건)", "",
        "답변 초안의 `{개선사항}`은 실제로 시행한 제도·변화로 채우세요. 사실이 아닌 내용은 쓰지 마세요.", "",
    ]
    for r in res["unanswered"]:
        lines += [
            f"### {r['날짜']} · {r.get('직무', '')} · ★{r['별점']:g}",
            f"- 단점: {r.get('단점', '').strip()}",
            f"- 주제: {', '.join(r['단점주제']) or '기타'}",
            f"- 답변 초안: {draft_reply(r)}", "",
        ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--config", default="config/smartear.toml")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    jp = cfg.get("jobplanet", {})
    res = analyze(load_reviews(args.csv), jp.get("themes", DEFAULT_THEMES), jp.get("recent_years", 2))
    out = Path(args.out) / cfg["slug"] / "jobplanet"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"jobplanet_report_{date.today():%Y%m%d}.md"
    path.write_text(render_report(res), encoding="utf-8")
    print(f"과거 ★{res['period_avg']['과거']} → 최근 ★{res['period_avg']['최근']}, 미답변 {len(res['unanswered'])}건 → {path}")


if __name__ == "__main__":
    main()
