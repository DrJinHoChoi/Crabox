# 스마트이어 주식회사 · 데이터피디 검색 브랜딩 키트

"스마트이어 주식회사", "데이터피디" 검색 시 공식 콘텐츠가 상위에 노출되도록 돕는 도구 모음 (Python 3.11+, 외부 패키지 없음).

| 구성 | 설명 |
|---|---|
| `config/brand.toml` | 회사 정보·공식 채널·모니터링 키워드 (TODO 항목을 실제 값으로 수정) |
| `seo/generate_site.py` | SEO 메타태그 + schema.org JSON-LD 포함 공식 랜딩 페이지, robots.txt, sitemap.xml 생성 |
| `monitor/brand_monitor.py` | 네이버 검색 API로 브랜드 언급 수집 → 부정/긍정/중립 분류 리포트(CSV, Markdown) |
| `docs/SEO_PLAYBOOK.md` | 단계별 상위 노출 전략 + 부정 콘텐츠의 합법적 대응 절차 |

```bash
python -m seo.generate_site            # → site/
export NAVER_CLIENT_ID=... NAVER_CLIENT_SECRET=...
python -m monitor.brand_monitor        # → reports/
python -m unittest discover tests
```
