"""수집 → 요약 → 사이트 생성 파이프라인.

사용:
    python3 main.py            # 최신 논문 수집·요약 후 사이트 갱신
    python3 main.py --limit 5  # 이번 실행에서 요약할 신규 논문 수 제한
    python3 main.py --rebuild  # 새 수집 없이 기존 데이터로 사이트만 재생성
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import fetch
import generate
import summarize

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data", "papers.json")


def load_env() -> None:
    """.env 파일이 있으면 환경변수로 로드한다. (외부 의존성 없이)"""
    path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config() -> dict:
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def load_store() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_store(store: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="이번 실행 신규 요약 개수 제한")
    ap.add_argument("--rebuild", action="store_true", help="수집 없이 사이트만 재생성")
    args = ap.parse_args()

    load_env()
    cfg = load_config()
    store = load_store()

    if args.rebuild:
        generate.build_site(list(store.values()), cfg)
        return 0

    backend = summarize.resolve_backend(cfg)
    print(f"요약 백엔드: {backend}")
    if backend == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        print("경고: ANTHROPIC_API_KEY가 없어 Claude 호출이 실패합니다.", file=sys.stderr)

    acfg = cfg["arxiv"]
    print(f"arXiv 수집: {', '.join(acfg['categories'])} (최대 {acfg['max_results']}편)")
    papers = fetch.fetch_recent(acfg["categories"], acfg["max_results"])

    new = [p for p in papers if p.id not in store]
    if args.limit is not None:
        new = new[: args.limit]
    print(f"신규 {len(new)}편 요약 시작 (기존 {len(store)}편)")

    ok, fail = 0, 0
    for i, p in enumerate(new, 1):
        print(f"  [{i}/{len(new)}] {p.title[:60]}...")
        pd = fetch.to_dict(p)
        try:
            pd["summary"] = summarize.summarize(pd, cfg, backend)
            pd["fetched_at"] = datetime.now(timezone.utc).isoformat()
            store[p.id] = pd
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"    요약 실패: {e}", file=sys.stderr)

    save_store(store)
    generate.build_site(list(store.values()), cfg)
    print(f"완료: 신규 {ok}편 성공, {fail}편 실패, 전체 {len(store)}편")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
