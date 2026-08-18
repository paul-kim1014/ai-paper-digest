"""주간 우수 논문 선별.

지난 N일간 게재된 논문 중 인기(HF 추천수)·영향력(인용수) 신호로 순위를 매겨
AI 세부 분야별로 상위 2~3편을 고른다. HF 신호가 부족하면 arXiv 최신 논문으로 폴백한다.
"""
from __future__ import annotations

import fetch
import trending

# arXiv 카테고리 → 사람이 읽는 세부 분야 (선별 그룹 단위)
SUBFIELDS: dict[str, str] = {
    "cs.CL": "자연어처리 (NLP)",
    "cs.CV": "컴퓨터비전 (CV)",
    "eess.IV": "컴퓨터비전 (CV)",
    "cs.LG": "머신러닝 (ML)",
    "stat.ML": "머신러닝 (ML)",
    "cs.RO": "강화학습·로보틱스",
    "cs.AI": "AI 일반·에이전트",
    "cs.MA": "AI 일반·에이전트",
    "cs.NE": "신경망·최적화",
    "cs.SD": "음성·오디오",
    "eess.AS": "음성·오디오",
    "cs.IR": "정보검색·추천",
}
DEFAULT_SUBFIELD = "기타 AI"

# index/아카이브에서의 분야 노출 순서
FIELD_ORDER = [
    "자연어처리 (NLP)", "컴퓨터비전 (CV)", "머신러닝 (ML)",
    "강화학습·로보틱스", "AI 일반·에이전트", "음성·오디오",
    "정보검색·추천", "신경망·최적화", "기타 AI",
]


def subfield_of(primary: str, categories: list[str]) -> str:
    if primary in SUBFIELDS:
        return SUBFIELDS[primary]
    for c in categories:
        if c in SUBFIELDS:
            return SUBFIELDS[c]
    return DEFAULT_SUBFIELD


def select_weekly(days: int, per_field: int, fallback_categories: list[str]) -> list[dict]:
    """선별된 논문 목록을 반환한다. 각 항목은 Paper dict + {subfield, upvotes, citations}."""
    trend = trending.fetch_hf_trending(days=days)
    print(f"  HF 트렌딩 후보 {len(trend)}편")

    if trend:
        papers = fetch.fetch_by_ids(list(trend.keys()))
    else:
        # 폴백: HF가 비었으면 arXiv 최신에서 분야별로 모은다
        print("  폴백: arXiv 최신 논문으로 선별")
        papers = fetch.fetch_recent(fallback_categories, max_results=per_field * len(fallback_categories) * 2)

    # 분야별 그룹화
    groups: dict[str, list[dict]] = {}
    for p in papers:
        pd = fetch.to_dict(p)
        sf = subfield_of(p.primary_category, p.categories)
        pd["subfield"] = sf
        pd["upvotes"] = trend.get(p.id, {}).get("upvotes", 0)
        groups.setdefault(sf, []).append(pd)

    selected: list[dict] = []
    for sf, items in groups.items():
        # 인기(추천수) 우선, 동률이면 최신순
        items.sort(key=lambda x: (x["upvotes"], x.get("published", "")), reverse=True)
        selected.extend(items[:per_field])

    # 선별된 논문에 한해 인용수 조회 (보조 신호, best-effort)
    for pd in selected:
        pd["citations"] = trending.fetch_citation(pd["id"])

    print(f"  선별 완료: {len(selected)}편 / {len(groups)}개 분야")
    return selected
