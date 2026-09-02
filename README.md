# AI 논문 요약 다이제스트

arXiv에 게재된 인공지능 논문 중 **지난 1주일간 인기·이슈가 된 우수 논문**을 세부 분야별로 선별해, 한국어로 쉽게 풀어 정적 웹페이지로 보여주는 시스템입니다. 요약 엔진은 **상용 Claude API**와 **오픈소스 로컬 Ollama**를 모두 지원하고, 결과는 **GitHub Pages**로 배포됩니다. 매주 새 이슈가 발행되며 과거 주차는 아카이브로 남습니다.

**라이브:** https://paul-kim1014.github.io/ai-paper-digest/

## 동작 방식

```
Hugging Face 트렌딩(인기) + arXiv(메타데이터) + Semantic Scholar(인용수)
   → 분야별 우수 논문 선별 → 요약(Claude / Ollama) → 주간 이슈 사이트(docs/) → GitHub Pages
```

- **trending.py** — Hugging Face Papers 추천수(인기·이슈 신호), Semantic Scholar 인용수(영향력, 보조)
- **fetch.py** — arXiv에서 논문 메타데이터 수집 (표준 라이브러리)
- **curate.py** — 지난 1주일 논문을 AI 세부 분야별로 인기순 정렬해 2~3편씩 선별
- **summarize.py** — 한줄요약·문제·방법·결과 + **예시 · 12살 버전 · 배경지식**을 한국어로 생성
- **generate.py** — 주간 이슈·주차별 아카이브·논문 상세 정적 사이트 생성
- **main.py** — 선별 → 요약 → 사이트 파이프라인 (이미 요약한 논문은 재사용)

### 논문 상세에 담기는 항목
한 줄 요약 · **🧒 12살 버전**(아이도 이해할 쉬운 설명) · **💡 예시**(현실 사용 예/비유) · 어떤 문제를 푸는가 · 핵심 방법 · 결과와 의의 · **📚 배경지식**(주요 개념 코너) · 키워드 · 원문 초록/PDF 링크

## 선별 기준

갓 게재된 논문은 인용수가 거의 없으므로, **커뮤니티 인기(Hugging Face 추천수)를 주 신호**로 사용하고 Semantic Scholar 인용수를 보조로 씁니다. 지난 `days`일(기본 7일) 논문을 AI 세부 분야(NLP·CV·ML·강화학습/로보틱스·AI일반·음성 등)로 묶어 인기순 상위 `per_field`편(기본 3편)씩 고릅니다. `config.json`의 `selection`에서 조정합니다.

## 설치

```bash
cd ~/ai-paper-digest
# Ollama 백엔드만 쓰면 추가 설치 불필요 (표준 라이브러리로 동작)
# Claude API를 쓰려면:
pip install -r requirements.txt
cp .env.example .env   # .env에 ANTHROPIC_API_KEY 입력
```

## 요약 엔진 전환 (`config.json`의 `backend`)

| 값 | 동작 |
|----|------|
| `"auto"` | 키 있으면 Claude, 없으면 Ollama (기본값) |
| `"claude"` | 항상 Claude API |
| `"ollama"` | 항상 로컬 Ollama (qwen3:8b) |

## 실행

```bash
python3 main.py            # 이번 주 이슈 발행 (선별·요약·사이트 갱신)
python3 main.py --limit 3  # 신규 요약 개수 제한 (테스트용)
python3 main.py --rebuild  # 새 선별 없이 기존 데이터로 사이트만 재생성
```

데이터는 `data/papers.json`(논문·요약 축적), `data/issues.json`(주차별 이슈)에 저장되고 사이트는 `docs/`에 생성됩니다.

## Slack 주간 알림

주간 이슈가 발행되면 `main.py`가 자동으로 Slack에 링크를 보냅니다(설정된 경우에만, 미설정이면 조용히 건너뜀). 두 방식 중 하나를 고르세요.

### 방식 1) 봇 토큰 — 본인에게 DM (권장, 이메일로 대상 지정)
1. https://api.slack.com/apps → **Create New App** → From scratch → 워크스페이스 선택
2. **OAuth & Permissions** → *Bot Token Scopes* 에 `chat:write` 와 `users:read.email` 추가
3. 상단 **Install to Workspace** → 승인 → **Bot User OAuth Token**(`xoxb-...`) 복사
4. `.env` 에 `SLACK_BOT_TOKEN=xoxb-...` 입력
5. `config.json` 의 `notify.slack.recipient_email` 을 받을 사람 이메일로 설정(기본: 등록된 이메일)

> DM이 오려면 그 이메일이 해당 Slack 워크스페이스의 계정 이메일과 같아야 합니다.

### 방식 2) 웹훅 — 채널에 게시 (더 간단, DM 아님)
1. 위 앱에서 **Incoming Webhooks** 활성화 → **Add New Webhook to Workspace** → 채널 선택
2. 생성된 URL을 `.env` 에 `SLACK_WEBHOOK_URL=https://hooks.slack.com/...` 로 입력

설정 후 테스트: `python3 main.py --rebuild` 는 발송하지 않으므로, 실제 발송은 `python3 main.py` 실행 시 이뤄집니다. `--no-notify` 로 끌 수 있습니다.

## 배포 & 매주 자동 갱신

`docs/` 폴더 기반 GitHub Pages. 갱신은 아래 한 줄(Slack 발송 포함):

```bash
python3 main.py && git add -A && git commit -m "weekly update" && git push
```

**매주 월요일 오전 9시 자동 발행 + Slack 알림** — macOS `cron` 예시:

```bash
0 9 * * 1 cd ~/ai-paper-digest && /usr/bin/python3 main.py && \
  git add -A && git commit -m "auto: $(date +\%F)" && git push
```

`main.py` 안에서 Slack 발송까지 처리하므로 cron에 별도 알림 단계는 필요 없습니다.
