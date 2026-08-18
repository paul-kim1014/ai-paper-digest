"""논문 인기도·인용수 신호 수집.

- Hugging Face Papers(daily_papers): 커뮤니티 추천수(upvotes) = 최근 논문의 인기/이슈 신호 (주 신호)
- Semantic Scholar: 인용수(citationCount) = 영향력 신호 (보조, 키 없으면 rate-limit 가능하므로 best-effort)
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

HF_API = "https://huggingface.co/api/daily_papers"
S2_API = "https://api.semanticscholar.org/graph/v1/paper"


def _get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-paper-digest/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_hf_trending(days: int = 7, limit: int = 100) -> dict[str, dict]:
    """최근 `days`일간 HF에 소개된 트렌딩 논문을 {arxiv_id: {upvotes, published}}로 반환."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        items = _get_json(f"{HF_API}?limit={limit}")
    except Exception as e:  # noqa: BLE001
        print(f"  HF 트렌딩 수집 실패(폴백 예정): {e}")
        return {}

    out: dict[str, dict] = {}
    for it in items:
        paper = it.get("paper", {}) or {}
        aid = (paper.get("id") or "").strip()
        if not aid:
            continue
        pub = it.get("publishedAt") or paper.get("publishedAt") or ""
        try:
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if pub_dt < cutoff:
                continue
        except Exception:  # noqa: BLE001
            pass
        up = int(paper.get("upvotes") or 0)
        # 같은 id가 여러 날 등장하면 최대 추천수 유지
        if aid not in out or up > out[aid]["upvotes"]:
            out[aid] = {"upvotes": up, "published": pub[:10]}
    return out


def fetch_citation(arxiv_id: str) -> int | None:
    """Semantic Scholar 인용수. 실패(429 등)하면 None. best-effort."""
    url = f"{S2_API}/arXiv:{arxiv_id}?fields=citationCount"
    for attempt in range(2):
        try:
            data = _get_json(url, timeout=20)
            return int(data.get("citationCount") or 0)
        except Exception:  # noqa: BLE001
            if attempt == 0:
                time.sleep(1.5)
    return None
