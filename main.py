"""주간 파이프라인: 지난 1주일 우수 논문 선별 → 요약 → 주간 이슈로 사이트 생성.

사용:
    python3 main.py            # 이번 주 이슈 발행 (선별·요약·사이트 갱신)
    python3 main.py --limit 3  # 이번 실행 신규 요약 개수 제한 (테스트용)
    python3 main.py --rebuild  # 새 선별 없이 기존 데이터로 사이트만 재생성
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

import curate
import fetch
import generate
import summarize

BASE = os.path.dirname(os.path.abspath(__file__))
PAPERS_FILE = os.path.join(BASE, "data", "papers.json")
ISSUES_FILE = os.path.join(BASE, "data", "issues.json")


def load_env() -> None:
    path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_json(path: str, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def week_label(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def has_full_summary(p: dict) -> bool:
    """새 스키마(예시·12살·배경지식)까지 갖춘 요약인지."""
    s = p.get("summary", {})
    return bool(s and "eli12" in s and "example" in s and "background" in s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="이번 실행 신규 요약 개수 제한")
    ap.add_argument("--rebuild", action="store_true", help="선별 없이 사이트만 재생성")
    args = ap.parse_args()

    load_env()
    cfg = load_json(os.path.join(BASE, "config.json"), {})
    store = load_json(PAPERS_FILE, {})
    issues = load_json(ISSUES_FILE, {})

    if args.rebuild:
        generate.build_site(store, issues, cfg)
        return 0

    backend = summarize.resolve_backend(cfg)
    print(f"요약 백엔드: {backend}")
    if backend == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        print("경고: ANTHROPIC_API_KEY가 없어 Claude 호출이 실패합니다.", file=sys.stderr)

    sel_cfg = cfg.get("selection", {})
    days = sel_cfg.get("days", 7)
    per_field = sel_cfg.get("per_field", 3)
    fallback_cats = cfg.get("arxiv", {}).get("categories", ["cs.AI", "cs.LG", "cs.CL", "cs.CV"])

    print(f"지난 {days}일 우수 논문 선별 (분야별 최대 {per_field}편)")
    selected = curate.select_weekly(days, per_field, fallback_cats)

    label = week_label(date.today())
    fields: dict[str, list[str]] = {}
    to_summarize = [p for p in selected if not (p["id"] in store and has_full_summary(store[p["id"]]))]
    if args.limit is not None:
        # 요약 개수를 제한하되, 이미 요약된 논문은 이슈에 그대로 포함
        keep_ids = {p["id"] for p in selected if p["id"] in store and has_full_summary(store[p["id"]])}
        to_summarize = to_summarize[: args.limit]
        allow = keep_ids | {p["id"] for p in to_summarize}
        selected = [p for p in selected if p["id"] in allow]

    print(f"신규 요약 {len(to_summarize)}편 (기존 재사용 {len(selected) - len(to_summarize)}편)")
    ok, fail = 0, 0
    to_sum_ids = {p["id"] for p in to_summarize}
    for i, p in enumerate(selected, 1):
        pid = p["id"]
        if pid in to_sum_ids:
            print(f"  [{i}/{len(selected)}] 요약: {p['title'][:55]}...")
            try:
                p["summary"] = summarize.summarize(p, cfg, backend)
                p["fetched_at"] = datetime.now(timezone.utc).isoformat()
                p["week"] = label
                store[pid] = p
                ok += 1
            except Exception as e:  # noqa: BLE001
                fail += 1
                print(f"    요약 실패: {e}", file=sys.stderr)
                continue
        else:
            # 기존 요약 재사용하되 이번 주 인기 신호/소속 주차 갱신
            store[pid]["upvotes"] = p.get("upvotes", store[pid].get("upvotes", 0))
            store[pid]["citations"] = p.get("citations", store[pid].get("citations"))
            store[pid].setdefault("week", label)
        fields.setdefault(store[pid]["subfield"], []).append(pid)

    issues[label] = {"date": datetime.now(timezone.utc).isoformat(), "fields": fields}
    save_json(PAPERS_FILE, store)
    save_json(ISSUES_FILE, issues)
    generate.build_site(store, issues, cfg)
    print(f"완료: {label} 이슈 발행 · 신규 {ok}편, 실패 {fail}편, 전체 축적 {len(store)}편")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
