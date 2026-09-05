"""논문 초록을 한국어로 요약한다. Claude API와 로컬 Ollama를 모두 지원한다."""
from __future__ import annotations

import json
import os
import re
import urllib.request

PROMPT_TEMPLATE = """당신은 인공지능 논문을 한국어로 쉽게 풀어 설명하는 전문 요약가입니다.
아래 arXiv 논문 정보를 읽고, 배경지식이 적은 개발자도 이해할 수 있도록 요약하세요.

제목: {title}
분야: {categories}
초록(영문):
{abstract}

다음 JSON 형식으로만 답하세요. 다른 설명은 절대 붙이지 마세요.
{{
  "tldr": "핵심을 한 문장으로 (40자 내외)",
  "problem": "이 논문이 풀려는 문제 (2~3문장)",
  "method": "제안한 방법의 핵심 아이디어 (2~3문장)",
  "result": "주요 결과와 의의 (2~3문장)",
  "method_easy": "핵심 원리와 기술을 12살 아이에게 설명하듯 아주 쉬운 말로 풀어쓰고, 이해를 돕는 구체적인 예시나 비유를 반드시 포함할 것 (3~4문장). 전문용어를 쓸 수밖에 없으면 곧바로 쉬운 말로 풀어줄 것",
  "improvement": "반드시 이 순서로 서술할 것 (3~4문장): (1) 기존에는 어떤 한계·불편이 있었는지 (2) 이 연구로 그게 어떻게 좋아졌는지(수치가 있으면 포함) (3) 그래서 현실에서 어떤 의미가 있는지. 이해를 돕는 구체적 예시를 반드시 들 것. 수치만 나열하지 말 것",
  "limitations": "이 연구의 미비점·부족한 점·우려되는 점을 먼저 쓰고, 이어서 '이렇게 하면 보완할 수 있을 것으로 보인다' 식으로 구체적인 보완 방안을 반드시 함께 제시할 것 (3~4문장)",
  "example": "이 기술이 현실에서 어떻게 쓰이는지 구체적 사용 예시, 또는 이해를 돕는 쉬운 비유 (3~4문장)",
  "eli12": "12살 아이에게 이야기하듯 아주 쉬운 말과 친근한 비유로 풀어 설명 (3~4문장, 전문용어 금지)",
  "background": [
    {{"term": "이 논문을 이해하는 데 필요한 개념/배경지식 이름", "explain": "그 개념을 쉬운 말로 1~2문장 설명"}}
  ],
  "keywords": ["키워드", "3~5개"]
}}
background 항목은 3~5개를 넣으세요.

작성 규칙:
- 모든 문장은 "~습니다/~합니다" 존댓말로 통일하세요. 반말("~거야", "~한다")을 섞지 마세요.
- method_easy, improvement, example에 드는 예시는 서로 겹치지 않게 각각 다른 예시를 드세요.
  같은 문장을 두 항목에 반복해 쓰지 마세요.
- limitations의 보완 방안은 "~하면 보완할 수 있을 것으로 보입니다" 형태로 자연스럽게 이어 쓰세요."""


def _extract_json(text: str) -> dict:
    """모델 출력에서 첫 JSON 객체를 추출한다. (Ollama가 앞뒤로 말 붙일 때 대비)"""
    # <think> 블록 제거 (qwen3 등 reasoning 모델 대비)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rsplit("```", 1)[0]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON 없음: {text[:200]}")
    return json.loads(text[start : end + 1])


def _normalize(data: dict) -> dict:
    kw = data.get("keywords", [])
    if isinstance(kw, str):
        kw = [k.strip() for k in re.split(r"[,;]", kw) if k.strip()]

    bg_raw = data.get("background", [])
    background = []
    if isinstance(bg_raw, dict):
        bg_raw = [{"term": k, "explain": v} for k, v in bg_raw.items()]
    if isinstance(bg_raw, list):
        for b in bg_raw:
            if isinstance(b, dict):
                term = str(b.get("term", "")).strip()
                explain = str(b.get("explain", b.get("description", ""))).strip()
                if term:
                    background.append({"term": term, "explain": explain})
            elif isinstance(b, str) and b.strip():
                background.append({"term": b.strip(), "explain": ""})

    return {
        "tldr": str(data.get("tldr", "")).strip(),
        "problem": str(data.get("problem", "")).strip(),
        "method": str(data.get("method", "")).strip(),
        "result": str(data.get("result", "")).strip(),
        "method_easy": str(data.get("method_easy", "")).strip(),
        "improvement": str(data.get("improvement", "")).strip(),
        "limitations": str(data.get("limitations", "")).strip(),
        "example": str(data.get("example", "")).strip(),
        "eli12": str(data.get("eli12", "")).strip(),
        "background": background[:5],
        "keywords": [str(k).strip() for k in kw][:5],
    }


# ---------------------------------------------------------------- Claude
def summarize_claude(prompt: str, cfg: dict) -> dict:
    from anthropic import Anthropic  # 지연 import: 미설치여도 Ollama는 동작

    client = Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용
    msg = client.messages.create(
        model=cfg.get("model", "claude-sonnet-5"),
        max_tokens=cfg.get("max_tokens", 1200),
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return _normalize(_extract_json(text))


# ---------------------------------------------------------------- Ollama
def summarize_ollama(prompt: str, cfg: dict) -> dict:
    host = cfg.get("host", "http://localhost:11434").rstrip("/")
    payload = {
        "model": cfg.get("model", "qwen3:8b"),
        "prompt": prompt,
        "stream": False,
        # qwen3 등 추론 모델의 <think> 블록은 어차피 버리므로 끈다 (속도 2~3배)
        "think": cfg.get("think", False),
        "options": {
            "temperature": 0.3,
            "num_predict": cfg.get("num_predict", 1200),  # 폭주 방지
        },
    }
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return _normalize(_extract_json(body.get("response", "")))


# ---------------------------------------------------------------- 라우팅
def resolve_backend(cfg: dict) -> str:
    """'auto'이면 키 존재 여부로 결정한다."""
    backend = cfg.get("backend", "auto")
    if backend == "auto":
        return "claude" if os.getenv("ANTHROPIC_API_KEY") else "ollama"
    return backend


def summarize(paper: dict, cfg: dict, backend: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        title=paper["title"],
        categories=", ".join(paper.get("categories", [])),
        abstract=paper["abstract"],
    )
    if backend == "claude":
        return summarize_claude(prompt, cfg.get("claude", {}))
    return summarize_ollama(prompt, cfg.get("ollama", {}))
