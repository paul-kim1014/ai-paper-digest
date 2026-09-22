#!/bin/bash
# 매주 자동 실행: 지난 1주일 우수 논문 선별·요약 → 사이트 갱신 → git push → Slack 알림.
# launchd(com.paulkim.ai-paper-digest)가 이 스크립트를 주 1회 실행한다.
# 절대 경로 사용 (launchd/cron은 PATH가 최소한이라 필수).

set -o pipefail
cd "$HOME/ai-paper-digest" || exit 1

PYTHON="$HOME/ai-paper-digest/venv/bin/python"
GIT="/usr/bin/git"
OLLAMA="/usr/local/bin/ollama"
LOG="$HOME/ai-paper-digest/data/cron.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 주간 실행 시작 =====" >> "$LOG"

# Ollama가 떠 있지 않으면 백그라운드로 기동 (Claude API 백엔드면 불필요하지만 안전차원)
if ! curl -s -o /dev/null http://localhost:11434/api/tags; then
  echo "Ollama 미응답 → 기동 시도" >> "$LOG"
  "$OLLAMA" serve >> "$LOG" 2>&1 &
  sleep 8
fi

# .env 로드 (Slack/Claude 키)
[ -f .env ] && set -a && . ./.env && set +a

push_changes() {
  "$GIT" add -A >> "$LOG" 2>&1
  if ! "$GIT" diff --cached --quiet; then
    "$GIT" commit -m "auto: $1 $(date '+%Y-%m-%d')" >> "$LOG" 2>&1
    "$GIT" push origin main >> "$LOG" 2>&1 && echo "push 완료" >> "$LOG" && return 0
    return 1
  fi
  return 2  # 변경 없음
}

# 1단계: 이슈 발행·사이트·주간 보고서 생성 (전달은 아직 안 함)
"$PYTHON" -u main.py --no-notify --no-teams >> "$LOG" 2>&1
STATUS=$?

if [ $STATUS -eq 0 ]; then
  # 2단계: 먼저 푸시해서 Slack·Teams 링크(웹 이슈, Word 보고서)가 열리는 상태로 만든다
  push_changes "주간 이슈"
  [ $? -eq 0 ] && sleep 90  # GitHub Pages 반영 대기
  # 3단계: 남은 전달(Slack·Teams)만 수행 — 이슈는 이미 있으므로 선별·요약은 생략된다
  "$PYTHON" -u main.py >> "$LOG" 2>&1
  STATUS=$?
  push_changes "전달 기록"
else
  echo "main.py 실패 (exit $STATUS) — 내일 09:00에 다시 시도" >> "$LOG"
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 종료 (exit $STATUS) =====" >> "$LOG"
