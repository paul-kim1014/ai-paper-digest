"""논문 인기도·인용수 신호 수집.

- Hugging Face Papers(daily_papers): 커뮤니티 추천수(upvotes) = 최근 논문의 인기/이슈 신호 (주 신호)
- Semantic Scholar: 인용수(citationCount) = 영향력 신호 (보조, 키 없으면 rate-limit 가능하므로 best-effort)
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

HF_API = "https://huggingface.co/api/daily_papers"
S2_API = "https://api.semanticscholar.org/graph/v1/paper"


def _get_json(url: str, timeout: int = 30, tries: int = 3):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-paper-digest/1.0"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def _collect(items: list, out: dict[str, dict], cutoff=None, until=None) -> None:
    """HF 응답을 {arxiv_id: 메타}로 누적. 같은 id는 추천수가 큰 쪽을 유지한다."""
    for it in items:
        paper = it.get("paper", {}) or {}
        aid = (paper.get("id") or "").strip()
        if not aid:
            continue
        pub = it.get("publishedAt") or paper.get("publishedAt") or ""
        try:
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if (cutoff and pub_dt < cutoff) or (until and pub_dt >= until):
                continue
        except Exception:  # noqa: BLE001
            pass
        up = int(paper.get("upvotes") or 0)
        if aid in out and up <= out[aid]["upvotes"]:
            continue
        out[aid] = {
            "upvotes": up,
            "published": pub[:10],
            # arXiv 조회가 막혀도 선별·요약을 계속할 수 있도록 HF 메타데이터를 그대로 보관
            "title": " ".join((paper.get("title") or it.get("title") or "").split()),
            "abstract": " ".join((paper.get("summary") or it.get("summary") or "").split()),
            "authors": [a.get("name", "") for a in paper.get("authors", []) if a.get("name")],
        }


def fetch_hf_window(end: date, days: int = 7) -> dict[str, dict]:
    """[end-days, end) 기간에 HF Daily Papers에 오른 논문을 날짜별로 모은다.

    날짜별 조회(?date=)라 과거 주차도 소급해 모을 수 있다. 전부 실패하면
    최근 목록 엔드포인트로 폴백한다.
    """
    out: dict[str, dict] = {}
    ok_days = 0
    for i in range(days, 0, -1):
        d = end - timedelta(days=i)
        try:
            _collect(_get_json(f"{HF_API}?date={d.isoformat()}&limit=100"), out)
            ok_days += 1
        except Exception as e:  # noqa: BLE001
            print(f"  HF {d} 조회 실패: {e}")
    if ok_days == 0:
        print("  HF 날짜별 조회 전부 실패 → 최근 목록으로 폴백")
        return fetch_hf_trending(days=days)
    return out


def fetch_hf_trending(days: int = 7, limit: int = 100) -> dict[str, dict]:
    """최근 `days`일간 HF에 소개된 트렌딩 논문 (날짜 지정 없는 최근 목록)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: dict[str, dict] = {}
    try:
        _collect(_get_json(f"{HF_API}?limit={limit}"), out, cutoff=cutoff)
    except Exception as e:  # noqa: BLE001
        print(f"  HF 트렌딩 수집 실패: {e}")
    return out


def fetch_citation(arxiv_id: str) -> int | None:
    """Semantic Scholar 인용수. 실패(429 등)하면 None. best-effort."""
    url = f"{S2_API}/arXiv:{arxiv_id}?fields=citationCount"
    for attempt in range(2):
        try:
            data = _get_json(url, timeout=20, tries=1)
            return int(data.get("citationCount") or 0)
        except Exception:  # noqa: BLE001
            if attempt == 0:
                time.sleep(1.5)
    return None
