# AI 논문 요약 다이제스트

arXiv에 게재된 최신 인공지능 논문을 자동으로 수집·한국어 요약하여 정적 웹페이지로 보여주는 시스템입니다. 요약 엔진은 **상용 Claude API**와 **오픈소스 로컬 Ollama**를 모두 지원하며, 결과는 **GitHub Pages**로 배포됩니다.

## 동작 방식

```
arXiv API (수집) → 요약 엔진(Claude / Ollama) → 정적 사이트(docs/) → GitHub Pages
```

- **fetch.py** — arXiv API에서 최신 논문 메타데이터 수집 (표준 라이브러리만 사용)
- **summarize.py** — 초록을 한국어 구조화 요약(한줄요약·문제·방법·결과·키워드)으로 변환
- **generate.py** — 검색·카테고리 필터·다크모드를 갖춘 정적 HTML 생성
- **main.py** — 수집→요약→생성 파이프라인 (이미 요약한 논문은 건너뜀)

## 설치

```bash
cd ~/ai-paper-digest
# Ollama 백엔드만 쓰면 추가 설치 불필요 (표준 라이브러리로 동작)
# Claude API를 쓰려면:
pip install -r requirements.txt
cp .env.example .env   # 그리고 .env에 ANTHROPIC_API_KEY 입력
```

## 요약 엔진 전환

`config.json`의 `backend` 값으로 제어합니다.

| 값 | 동작 |
|----|------|
| `"auto"` | `ANTHROPIC_API_KEY`가 있으면 Claude, 없으면 Ollama (기본값) |
| `"claude"` | 항상 Claude API (`claude` 설정의 model 사용) |
| `"ollama"` | 항상 로컬 Ollama (`ollama` 설정의 model 사용) |

수집 카테고리·논문 수도 `config.json`의 `arxiv` 항목에서 조정합니다.

## 실행

```bash
python3 main.py            # 최신 논문 수집·요약 후 사이트 갱신
python3 main.py --limit 5  # 이번 실행에서 신규 5편만 요약
python3 main.py --rebuild  # 새 수집 없이 기존 데이터로 사이트만 재생성
```

수집·요약 결과는 `data/papers.json`에 누적되고, 사이트는 `docs/`에 생성됩니다.

## 배포 (GitHub Pages)

`docs/` 폴더를 소스로 하는 GitHub Pages로 배포됩니다. 최초 1회 설정 후에는
`python3 main.py && git add -A && git commit -m "update" && git push` 만으로 갱신됩니다.
자동화는 아래 "매일 자동 갱신" 참고.

## 매일 자동 갱신 (선택)

macOS `cron` 예시 — 매일 오전 9시에 갱신·배포:

```bash
0 9 * * * cd ~/ai-paper-digest && /usr/bin/python3 main.py && \
  git add -A && git commit -m "auto: $(date +\%F)" && git push
```
