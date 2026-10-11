# 스마트이어 주식회사 · 데이터피디 검색 브랜딩 키트

"스마트이어 주식회사"(법인)와 "데이터피디"(별개 개인사업자)를 **각각 따로** 검색했을 때 공식 콘텐츠가 상위에 노출되도록 돕는 도구 모음 (Python 3.11+, 외부 패키지 없음).

| 구성 | 설명 |
|---|---|
| `config/smartear.toml` | 스마트이어 주식회사(법인) 정보·채널·모니터링 키워드 |
| `config/datapd.toml` | 데이터피디(개인사업자) 정보·채널·모니터링 키워드 |
| `seo/generate_site.py` | SEO 메타태그 + schema.org JSON-LD 포함 공식 랜딩 페이지, robots.txt, sitemap.xml을 `site/<slug>/`에 엔티티별 생성 |
| `monitor/brand_monitor.py` | 네이버 검색 API로 브랜드 언급 수집 → 부정/긍정/중립 분류 리포트를 `reports/<slug>/`에 엔티티별 생성 |
| `jobplanet/review_analyzer.py` | 잡플래닛 리뷰(CSV)를 과거 vs 최근으로 분석, 미답변 리뷰 답변 초안 생성 |
| `docs/JOBPLANET_PLAYBOOK.md` | 잡플래닛 5년 전 이미지 탈피 전략 |
| `docs/content/smartear/` | 스마트이어 현재 모습(제조 AX·AI 에이전트) 콘텐츠 초안: 잡플래닛 소개, 영업 채용공고, 블로그, 리뷰 답변 |
| `docs/SEO_PLAYBOOK.md` | 단계별 상위 노출 전략 + 부정 콘텐츠의 합법적 대응 절차 |

```bash
python -m seo.generate_site            # → site/smartear, site/datapd
export NAVER_CLIENT_ID=... NAVER_CLIENT_SECRET=...
python -m monitor.brand_monitor        # → reports/smartear, reports/datapd
python -m jobplanet.review_analyzer data/jobplanet_reviews.csv  # → reports/smartear/jobplanet
python -m jobplanet.review_analyzer data/datapd_reviews.csv --config config/datapd.toml  # 데이터피디 페이지가 있으면
python -m unittest discover tests
```
