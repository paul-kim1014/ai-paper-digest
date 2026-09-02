#!/bin/bash
# 매주 자동 실행: 지난 1주일 우수 논문 선별·요약 → 사이트 갱신 → git push → Slack 알림.
# launchd(com.paulkim.ai-paper-digest)가 이 스크립트를 주 1회 실행한다.
# 절대 경로 사용 (launchd/cron은 PATH가 최소한이라 필수).

set -o pipefail
cd "$HOME/ai-paper-digest" || exit 1

PYTHON="/opt/homebrew/bin/python3"
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

# 선별·요약·사이트 생성·Slack 발송
"$PYTHON" main.py >> "$LOG" 2>&1
STATUS=$?

if [ $STATUS -eq 0 ]; then
  "$GIT" add -A >> "$LOG" 2>&1
  # 변경이 있을 때만 커밋/푸시
  if ! "$GIT" diff --cached --quiet; then
    "$GIT" commit -m "auto: 주간 이슈 $(date '+%Y-%m-%d')" >> "$LOG" 2>&1
    "$GIT" push origin main >> "$LOG" 2>&1 && echo "push 완료" >> "$LOG"
  else
    echo "변경 없음 — 커밋 생략" >> "$LOG"
  fi
else
  echo "main.py 실패 (exit $STATUS)" >> "$LOG"
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 종료 (exit $STATUS) =====" >> "$LOG"
