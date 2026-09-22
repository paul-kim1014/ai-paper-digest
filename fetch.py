"""arXiv에서 최신 AI 논문 메타데이터를 가져온다. (표준 라이브러리만 사용)"""
from __future__ import annotations

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


@dataclass
class Paper:
    id: str
    title: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abstract: str
    pdf_url: str
    arxiv_url: str


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _parse_entries(raw: str) -> list[Paper]:
    root = ET.fromstring(raw)
    papers: list[Paper] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = entry.findtext(f"{ATOM}id", "").strip()
        short_id = raw_id.rsplit("/", 1)[-1]
        clean_id = short_id.split("v")[0]
        if not clean_id:
            continue
        authors = [
            _clean(a.findtext(f"{ATOM}name", ""))
            for a in entry.findall(f"{ATOM}author")
        ]
        cats = [c.get("term", "") for c in entry.findall(f"{ATOM}category") if c.get("term")]
        primary_el = entry.find(f"{ARXIV_NS}primary_category")
        primary = primary_el.get("term") if primary_el is not None else (cats[0] if cats else "")
        pdf_url = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", "")
        if not pdf_url:
            pdf_url = f"https://arxiv.org/pdf/{clean_id}"
        papers.append(
            Paper(
                id=clean_id,
                title=_clean(entry.findtext(f"{ATOM}title", "")),
                authors=authors,
                categories=cats,
                primary_category=primary,
                published=entry.findtext(f"{ATOM}published", "").strip(),
                updated=entry.findtext(f"{ATOM}updated", "").strip(),
                abstract=_clean(entry.findtext(f"{ATOM}summary", "")),
                pdf_url=pdf_url,
                arxiv_url=f"https://arxiv.org/abs/{clean_id}",
            )
        )
    return papers


def _get(url: str, tries: int = 4) -> str:
    """arXiv GET. 429면 Retry-After를 존중하고 10→30→60초로 물러난다."""
    req = urllib.request.Request(url, headers={"User-Agent": "ai-paper-digest/1.0"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            wait = (10, 30, 60)[min(attempt, 2)]
            retry_after = getattr(e, "headers", None) and e.headers.get("Retry-After")
            if retry_after and str(retry_after).isdigit():
                wait = max(wait, int(retry_after))
            print(f"  arXiv 요청 재시도 ({attempt + 1}/{tries}, {wait}s 대기): {e}", flush=True)
            time.sleep(wait)
    return ""


def fetch_by_ids(ids: list[str]) -> list[Paper]:
    """arXiv id 목록으로 메타데이터를 배치 조회한다 (20개씩, 3초 간격).

    한 배치가 끝내 실패하면 예외를 던지지 않고 그때까지의 결과만 돌려준다.
    호출 측이 나머지를 다른 방법(키워드 분류)으로 메우게 하기 위해서다.
    """
    results: list[Paper] = []
    for i in range(0, len(ids), 20):
        chunk = ids[i : i + 20]
        url = f"{ARXIV_API}?id_list={','.join(chunk)}&max_results={len(chunk)}"
        try:
            results.extend(_parse_entries(_get(url)))
        except Exception as e:  # noqa: BLE001
            print(f"  arXiv 메타데이터 조회 중단({len(results)}/{len(ids)}편 확보): {e}", flush=True)
            break
        if i + 20 < len(ids):
            time.sleep(3)  # arXiv 권장 간격
    return results


def fetch_recent(categories: list[str], max_results: int = 15) -> list[Paper]:
    """지정한 카테고리의 최신 논문을 제출일 내림차순으로 가져온다."""
    cat_query = "+OR+".join(f"cat:{c}" for c in categories)
    params = {
        "search_query": cat_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(max_results),
    }
    # search_query의 +OR+ 는 인코딩하지 않아야 arXiv가 올바로 해석한다.
    url = f"{ARXIV_API}?search_query={cat_query}&" + urllib.parse.urlencode(
        {k: v for k, v in params.items() if k != "search_query"}
    )
    return _parse_entries(_get(url))


def to_dict(p: Paper) -> dict:
    return asdict(p)


if __name__ == "__main__":
    for p in fetch_recent(["cs.AI", "cs.LG"], 5):
        print(f"[{p.primary_category}] {p.title}\n  {p.arxiv_url}\n")
