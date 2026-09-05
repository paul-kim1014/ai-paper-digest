"""주간 이슈 발행 시 Slack으로 링크를 자동 발송한다.

두 가지 방식 지원 (둘 중 하나만 설정하면 됨):
  1) 봇 토큰(SLACK_BOT_TOKEN) + 이메일  → 본인에게 DM (recipient_email로 사용자 조회)
  2) 웹훅(SLACK_WEBHOOK_URL)             → 지정 채널에 게시

설정 위치:
  - .env:        SLACK_BOT_TOKEN=xoxb-...   또는   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
  - config.json: notify.slack.recipient_email (봇 토큰 방식에서 DM 대상)
"""
from __future__ import annotations

import json
import os
import unicodedata
import urllib.parse
import urllib.request

SLACK_API = "https://slack.com/api"


def _post_json(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except Exception:  # noqa: BLE001 (웹훈은 "ok" 평문 반환)
        return {"ok": body.strip() == "ok", "raw": body}


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------- 표 렌더링
def _dw(s: str) -> int:
    """표시 폭. 한글·CJK는 2칸으로 센다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _fit(s: str, width: int) -> str:
    """표시 폭 기준으로 자르고(넘치면 …) 오른쪽을 공백으로 채운다."""
    s = " ".join((s or "").split())
    out, cur = "", 0
    for ch in s:
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if cur + w > width - 1:
            out += "…"
            cur += 1
            break
        out += ch
        cur += w
    return out + " " * max(0, width - cur)


def _pad(s: str, width: int) -> str:
    """이미 폭 안에 들어가는 문자열을 오른쪽 공백으로 채운다(자르지 않음)."""
    return s + " " * max(0, width - _dw(s))


def _wrap(s: str, width: int) -> list[str]:
    """표시 폭 기준으로 줄바꿈. 내용을 자르지 않고 여러 줄로 펼친다."""
    s = " ".join((s or "").split())
    if not s:
        return [""]
    lines, cur, cw = [], "", 0
    for ch in s:
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if cw + w > width:
            lines.append(cur)
            cur, cw = ch, w
        else:
            cur += ch
            cw += w
    if cur:
        lines.append(cur)
    return lines


def build_top3_table(papers: list[dict]) -> str:
    """인기 1~3위를 구분/주제/핵심 원리 및 기술/개선효과/미비점 및 우려사항 표로.

    셀 내용은 자르지 않고 열 폭에 맞춰 줄바꿈하여 전체 내용을 보여준다.
    """
    top = sorted(papers, key=lambda x: x.get("upvotes", 0), reverse=True)[:3]
    if not top:
        return ""
    cols = [("구분", 5), ("주제", 20), ("핵심 원리 및 기술", 28),
            ("개선효과", 22), ("미비점 및 우려사항", 24)]
    sep = "+".join("-" * w for _, w in cols)
    out = ["|".join(_fit(h, w) for h, w in cols), sep]

    for i, p in enumerate(top, 1):
        s = p.get("summary", {})
        improve = s.get("improvement") or s.get("result", "")
        limits = s.get("limitations") or "요약에 명시된 한계 없음"
        cells = [f"{i}위 👍{p.get('upvotes', 0)}",
                 s.get("tldr") or p.get("title", ""),
                 s.get("method", ""), improve, limits]
        wrapped = [_wrap(c, w) for c, (_, w) in zip(cells, cols)]
        height = max(len(w) for w in wrapped)
        for r in range(height):
            line = [_pad(w[r] if r < len(w) else "", cw)
                    for w, (_, cw) in zip(wrapped, cols)]
            out.append("|".join(line))
        out.append(sep)
    return "```\n" + "\n".join(out) + "\n```"


def build_message(cfg: dict, label: str, fields: dict, top_paper: dict | None,
                  all_papers: list[dict] | None = None) -> str:
    site = cfg.get("site_url", "").rstrip("/")
    issue_link = f"{site}/issue/{label}.html" if site else ""
    total = sum(len(v) for v in fields.values())
    lines = [
        f"📚 *{cfg.get('site_title','AI 논문 요약 다이제스트')}* — 이번 주 이슈(*{label}*)가 나왔어요!",
        f"{len(fields)}개 분야 · 총 {total}편",
    ]
    if all_papers:
        table = build_top3_table(all_papers)
        if table:
            lines.append("")
            lines.append("*🏆 이번 주 인기 1~3위 요약*")
            lines.append(table)
    elif top_paper:
        up = top_paper.get("upvotes", 0)
        lines.append(f"🔥 이번 주 인기 1위: {top_paper['title']} (👍 {up})")
    if issue_link:
        lines.append(f"👉 <{issue_link}|이번 주 이슈 열기>")
    if site:
        lines.append(f"🏠 최신: {site}/")
    return "\n".join(lines)


def send_slack(cfg: dict, text: str) -> bool:
    """설정된 방식으로 Slack 발송. 성공 True, 미설정/실패 False."""
    token = os.getenv("SLACK_BOT_TOKEN")
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    email = cfg.get("notify", {}).get("slack", {}).get("recipient_email", "")

    # 1) 봇 토큰 방식: 이메일로 사용자 조회 후 DM
    if token:
        try:
            if not email:
                print("  Slack: recipient_email이 없어 봇 토큰 방식 DM 불가", flush=True)
            else:
                info = _get_json(f"{SLACK_API}/users.lookupByEmail?email={urllib.parse.quote(email)}", token)
                if not info.get("ok"):
                    print(f"  Slack 사용자 조회 실패: {info.get('error')}", flush=True)
                else:
                    uid = info["user"]["id"]
                    res = _post_json(f"{SLACK_API}/chat.postMessage",
                                     {"channel": uid, "text": text, "unfurl_links": True}, token)
                    if res.get("ok"):
                        print(f"  Slack DM 발송 완료 → {email}", flush=True)
                        return True
                    print(f"  Slack 발송 실패: {res.get('error')}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  Slack 봇 토큰 발송 오류: {e}", flush=True)

    # 2) 웹훅 방식
    if webhook:
        try:
            res = _post_json(webhook, {"text": text})
            if res.get("ok"):
                print("  Slack 웹훅 발송 완료", flush=True)
                return True
            print(f"  Slack 웹훅 응답: {res.get('raw', res)}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  Slack 웹훅 발송 오류: {e}", flush=True)

    if not token and not webhook:
        print("  Slack 미설정(SLACK_BOT_TOKEN 또는 SLACK_WEBHOOK_URL 없음) — 발송 건너뜀", flush=True)
    return False
