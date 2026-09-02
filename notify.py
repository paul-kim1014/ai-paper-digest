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


def build_message(cfg: dict, label: str, fields: dict, top_paper: dict | None) -> str:
    site = cfg.get("site_url", "").rstrip("/")
    issue_link = f"{site}/issue/{label}.html" if site else ""
    total = sum(len(v) for v in fields.values())
    lines = [
        f"📚 *{cfg.get('site_title','AI 논문 요약 다이제스트')}* — 이번 주 이슈(*{label}*)가 나왔어요!",
        f"{len(fields)}개 분야 · 총 {total}편",
    ]
    if top_paper:
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
