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


# arXiv 분류를 못 얻었을 때 쓰는 키워드 규칙 (위에서부터 먼저 맞는 분야)
KEYWORD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("음성·오디오", ("speech", "audio", "asr", "text-to-speech", "tts", "voice", "music", "sound")),
    ("강화학습·로보틱스", ("robot", "embodied", "manipulation", "locomotion", "reinforcement learning",
                     "autonomous driving", "vla ", "vision-language-action", "humanoid")),
    ("정보검색·추천", ("retrieval", "recommend", "search engine", "rag ", "reranking")),
    ("컴퓨터비전 (CV)", ("image", "video", "visual", "vision", "3d", "segmentation", "detection",
                      "pixel", "diffusion", "camera", "scene")),
    ("AI 일반·에이전트", ("agent", "agentic", "tool use", "multi-agent", "planning", "workflow")),
    ("자연어처리 (NLP)", ("language model", "llm", "text", "token", "reasoning", "translation",
                       "question answering", "chat", "instruction")),
]


def subfield_by_keywords(title: str, abstract: str) -> str:
    text = f" {title} {abstract} ".lower()
    for field, words in KEYWORD_RULES:
        if any(w in text for w in words):
            return field
    return "머신러닝 (ML)"


def _from_hf(aid: str, meta: dict) -> dict:
    """arXiv 메타데이터 없이 HF 정보만으로 논문 dict를 만든다."""
    return {
        "id": aid,
        "title": meta.get("title", ""),
        "authors": meta.get("authors", []),
        "categories": [],
        "primary_category": "",
        "published": meta.get("published", ""),
        "updated": meta.get("published", ""),
        "abstract": meta.get("abstract", ""),
        "pdf_url": f"https://arxiv.org/pdf/{aid}",
        "arxiv_url": f"https://arxiv.org/abs/{aid}",
    }


def select_weekly(window_end, days: int, per_field: int, fallback_categories: list[str],
                  exclude_ids: set[str] | None = None, max_candidates: int = 80) -> list[dict]:
    """[window_end-days, window_end) 기간 논문을 분야별로 인기순 선별한다.

    각 항목은 논문 dict + {subfield, upvotes, citations}. arXiv 조회가 막혀도
    HF 메타데이터와 키워드 분류로 선별을 끝까지 진행한다.
    """
    exclude_ids = exclude_ids or set()
    trend = trending.fetch_hf_window(window_end, days)
    trend = {k: v for k, v in trend.items() if k not in exclude_ids and v.get("abstract")}
    print(f"  HF 후보 {len(trend)}편 (다른 주차 게재분 제외)", flush=True)

    if not trend:
        print("  폴백: arXiv 최신 논문으로 선별", flush=True)
        try:
            papers = [fetch.to_dict(p) for p in fetch.fetch_recent(
                fallback_categories, max_results=per_field * len(fallback_categories) * 2)]
        except Exception as e:  # noqa: BLE001
            print(f"  arXiv 폴백도 실패: {e}", flush=True)
            return []
        for pd in papers:
            pd["upvotes"] = 0
            pd["subfield"] = subfield_of(pd["primary_category"], pd["categories"])
    else:
        # 추천수 상위 후보만 분류한다 (분야별 2~3편만 뽑으므로 충분, arXiv 호출도 줄임)
        ranked = sorted(trend, key=lambda k: trend[k]["upvotes"], reverse=True)[:max_candidates]
        arx = {p.id: p for p in fetch.fetch_by_ids(ranked)}
        by_kw = 0
        papers = []
        for aid in ranked:
            meta = trend[aid]
            if aid in arx:
                pd = fetch.to_dict(arx[aid])
                pd["subfield"] = subfield_of(pd["primary_category"], pd["categories"])
            else:
                pd = _from_hf(aid, meta)
                pd["subfield"] = subfield_by_keywords(pd["title"], pd["abstract"])
                by_kw += 1
            pd["upvotes"] = meta["upvotes"]
            papers.append(pd)
        if by_kw:
            print(f"  arXiv 분류 불가 {by_kw}편 → 제목·초록 키워드로 분류", flush=True)

    groups: dict[str, list[dict]] = {}
    for pd in papers:
        groups.setdefault(pd["subfield"], []).append(pd)

    selected: list[dict] = []
    for items in groups.values():
        items.sort(key=lambda x: (x["upvotes"], x.get("published", "")), reverse=True)
        selected.extend(items[:per_field])

    for pd in selected:
        pd["citations"] = trending.fetch_citation(pd["id"])

    print(f"  선별 완료: {len(selected)}편 / {len(groups)}개 분야", flush=True)
    return selected
