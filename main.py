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
from datetime import date, datetime, timedelta, timezone

import curate
import fetch
import generate
import notify
import summarize
import teams

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
    """원자적 저장: 임시 파일에 쓴 뒤 교체한다.

    open(path,"w")는 파일을 먼저 비우므로, 쓰기 도중 중단되면 누적 데이터가
    통째로 날아간다. 임시 파일 → fsync → os.replace(원자적 교체) 순서로 막는다.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def week_label(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_monday(label: str) -> date:
    """'2026-W37' → 그 주 월요일."""
    y, w = label.split("-W")
    return date.fromisocalendar(int(y), int(w), 1)


def has_full_summary(p: dict) -> bool:
    """현재 스키마(예시·12살·배경지식·쉬운 원리·개선효과·미비점)를 모두 갖춘 요약인지."""
    s = p.get("summary", {})
    need = ("eli12", "example", "background", "method_easy", "improvement", "limitations")
    return bool(s) and all(k in s for k in need)


def delivered(issue: dict) -> dict:
    # 전달 기록이 없는 과거 이슈는 Slack을 이미 보냈거나 시점이 지났으므로 완료로 간주.
    # Teams는 단계별로 teams.pending()이 따로 판단한다.
    return issue.setdefault("delivered", {"slack": True})


def create_issue(label: str, args, cfg: dict, store: dict, issues: dict) -> bool:
    """label 주차 이슈를 선별·요약해 만든다. 한 편이라도 실리면 True."""
    backend = summarize.resolve_backend(cfg)
    print(f"요약 백엔드: {backend}", flush=True)
    if backend == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
        print("경고: ANTHROPIC_API_KEY가 없어 Claude 호출이 실패합니다.", file=sys.stderr)

    sel = cfg.get("selection", {})
    days, per_field = sel.get("days", 7), sel.get("per_field", 3)
    fallback = cfg.get("arxiv", {}).get("categories", ["cs.AI", "cs.LG", "cs.CL", "cs.CV"])

    # 창: 그 주 월요일 직전 7일 (월요일에 못 돌고 화요일에 돌아도 같은 구간을 본다)
    monday = week_monday(label)
    start = monday - timedelta(days=days)
    print(f"[{label}] {start} ~ {monday - timedelta(days=1)} 논문 선별 (분야별 최대 {per_field}편)", flush=True)

    other = {pid for wk, m in issues.items() if wk != label
             for lst in m.get("fields", {}).values() for pid in lst}
    selected = curate.select_weekly(monday, days, per_field, fallback, exclude_ids=other)
    if not selected:
        print("선별 결과 없음 — 이슈를 만들지 않습니다.", file=sys.stderr)
        return False

    reusable = {p["id"] for p in selected if p["id"] in store and has_full_summary(store[p["id"]])}
    todo = [p for p in selected if p["id"] not in reusable]
    if args.limit is not None:
        todo = todo[: args.limit]
        keep = reusable | {p["id"] for p in todo}
        selected = [p for p in selected if p["id"] in keep]
    todo_ids = {p["id"] for p in todo}
    print(f"신규 요약 {len(todo)}편 (기존 재사용 {len(reusable & {p['id'] for p in selected})}편)", flush=True)

    fields: dict[str, list[str]] = {}
    ok = fail = 0
    for i, p in enumerate(selected, 1):
        pid = p["id"]
        if pid in todo_ids:
            print(f"  [{i}/{len(selected)}] 요약: {p['title'][:55]}...", flush=True)
            # 로컬 모델은 가끔 JSON을 끝까지 닫지 않고 멈춘다 → 한 번 더 시도
            err = None
            for attempt in range(2):
                try:
                    p["summary"] = summarize.summarize(p, cfg, backend)
                    err = None
                    break
                except Exception as e:  # noqa: BLE001
                    err = e
                    print(f"    요약 실패({attempt + 1}/2): {str(e)[:80]}", file=sys.stderr, flush=True)
            if err is not None:
                fail += 1
                continue
            p["fetched_at"] = datetime.now(timezone.utc).isoformat()
            p["week"] = label
            store[pid] = p
            ok += 1
            save_json(PAPERS_FILE, store)  # 한 편마다 원자적 저장
        else:
            store[pid]["upvotes"] = p.get("upvotes", store[pid].get("upvotes", 0))
            store[pid]["citations"] = p.get("citations", store[pid].get("citations"))
            store[pid]["week"] = label
        fields.setdefault(store[pid]["subfield"], []).append(pid)

    if not fields:
        print("요약에 모두 실패 — 이슈를 만들지 않습니다.", file=sys.stderr)
        return False

    is_backfill = monday < week_monday(week_label(date.today()))
    issues[label] = {
        # 소급 생성분은 아카이브 정렬이 맞도록 그 주 월요일을 발행일로 둔다
        "date": (datetime.combine(monday, datetime.min.time(), timezone.utc) if is_backfill
                 else datetime.now(timezone.utc)).isoformat(),
        "window": [start.isoformat(), (monday - timedelta(days=1)).isoformat()],
        "fields": fields,
        "delivered": {"slack": False},
    }
    save_json(PAPERS_FILE, store)
    save_json(ISSUES_FILE, issues)
    print(f"완료: {label} 이슈 발행 · 신규 {ok}편, 실패 {fail}편, 전체 축적 {len(store)}편", flush=True)
    return True


def issue_papers(label: str, store: dict, issues: dict) -> list[dict]:
    return [store[i] for lst in issues[label]["fields"].values() for i in lst if i in store]


def deliver(label: str, args, cfg: dict, store: dict, issues: dict) -> None:
    """아직 끝나지 않은 전달 단계(Slack, Teams)만 수행하고 결과를 기록한다."""
    d = delivered(issues[label])
    papers = issue_papers(label, store, issues)
    fields = issues[label]["fields"]

    if not d["slack"] and not args.no_notify:
        top = max(papers, key=lambda x: x.get("upvotes", 0)) if papers else None
        d["slack"] = notify.send_slack(cfg, notify.build_message(cfg, label, fields, top, papers))

    if not args.no_teams and teams.pending(issues[label], cfg):
        d["teams"] = teams.publish(label, issues[label], papers, cfg)

    save_json(ISSUES_FILE, issues)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="이번 실행 신규 요약 개수 제한")
    ap.add_argument("--rebuild", action="store_true", help="선별 없이 사이트만 재생성")
    ap.add_argument("--week", help="특정 주차 이슈 생성 (예: 2026-W37, 소급 생성용)")
    ap.add_argument("--force", action="store_true", help="이미 발행된 주차도 다시 선별")
    ap.add_argument("--no-notify", action="store_true", help="Slack 발송 건너뛰기")
    ap.add_argument("--no-teams", action="store_true", help="Teams 업로드 건너뛰기")
    args = ap.parse_args()

    load_env()
    cfg = load_json(os.path.join(BASE, "config.json"), {})
    store = load_json(PAPERS_FILE, {})
    issues = load_json(ISSUES_FILE, {})

    if args.rebuild:
        generate.build_site(store, issues, cfg)
        return 0

    label = args.week or week_label(date.today())
    created = False
    if label in issues and not args.force:
        print(f"[{label}] 이미 발행됨 — 선별·요약 생략", flush=True)
    elif create_issue(label, args, cfg, store, issues):
        created = True
    else:
        return 1  # 실패: 다음 날 스케줄이 다시 시도한다

    generate.build_site(store, issues, cfg)
    # 주간 Word 보고서도 사이트와 함께 만들어 둔다. 채널 카드의 [주간 보고서] 버튼이
    # 가리키는 파일이 게시 시점에 이미 GitHub Pages에 올라가 있게 하기 위해서다.
    for wk in sorted(issues):
        if (wk == label and created) or not os.path.exists(teams.report_path(wk)):
            teams.build_report(wk, issues[wk], issue_papers(wk, store, issues), cfg)

    # 이번 주차 + 전달이 덜 끝난 과거 주차(오래된 것부터 — 게시판에 시간순으로 쌓이도록)
    for wk in sorted(issues):
        if wk != label:
            delivered(issues[wk])["slack"] = True  # 과거 주차는 Slack 재발송하지 않음
        if wk == label or teams.pending(issues[wk], cfg) or not delivered(issues[wk])["slack"]:
            deliver(wk, args, cfg, store, issues)
    save_json(ISSUES_FILE, issues)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
