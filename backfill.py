"""기존 요약에 새로 추가된 필드(improvement, limitations)를 채워 넣는다.

사용:
    python3 backfill.py            # 누락된 논문 전체 재요약
    python3 backfill.py --top 3    # 최신 이슈 인기 상위 N편만
"""
from __future__ import annotations

import argparse
import sys

import main as m
import summarize

NEW_FIELDS = ("improvement", "limitations")


def needs_backfill(p: dict) -> bool:
    s = p.get("summary", {})
    return not all(s.get(f) for f in NEW_FIELDS)


def run() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=None, help="최신 이슈 인기 상위 N편만")
    args = ap.parse_args()

    m.load_env()
    cfg = m.load_json(m.BASE + "/config.json", {})
    store = m.load_json(m.PAPERS_FILE, {})
    issues = m.load_json(m.ISSUES_FILE, {})
    backend = summarize.resolve_backend(cfg)

    if args.top:
        label = max(issues, key=lambda k: issues[k]["date"])
        ids = [i for lst in issues[label]["fields"].values() for i in lst]
        cand = sorted((store[i] for i in ids if i in store),
                      key=lambda x: x.get("upvotes", 0), reverse=True)[: args.top]
    else:
        cand = list(store.values())

    targets = [p for p in cand if needs_backfill(p)]
    print(f"백엔드 {backend} · 백필 대상 {len(targets)}편")

    ok = 0
    for i, p in enumerate(targets, 1):
        print(f"  [{i}/{len(targets)}] {p['title'][:55]}...", flush=True)
        try:
            new = summarize.summarize(p, cfg, backend)
            # 기존 요약 유지 + 새 필드만 채움(빈 값이면 새 값으로 대체)
            merged = dict(p["summary"])
            for k, v in new.items():
                if k in NEW_FIELDS or not merged.get(k):
                    merged[k] = v
            store[p["id"]]["summary"] = merged
            ok += 1
            m.save_json(m.PAPERS_FILE, store)
        except Exception as e:  # noqa: BLE001
            print(f"    실패: {e}", file=sys.stderr)

    print(f"완료: {ok}/{len(targets)}편 백필")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
