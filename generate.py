"""주간 이슈·분야별 아카이브 구조의 정적 사이트(docs/)를 생성한다.

페이지 구성:
  index.html          - 최신 주간 이슈 (분야별 그룹)
  archive.html        - 지난 주차 목록 (히스토리)
  issue/<week>.html   - 특정 주차 이슈 (분야별 그룹)
  paper/<id>.html     - 논문 상세 (요약·예시·12살 버전·배경지식 등)
"""
from __future__ import annotations

import html
import os
from datetime import datetime, timezone

from curate import FIELD_ORDER

DOCS = os.path.join(os.path.dirname(__file__), "docs")

CAT_LABELS = {
    "cs.AI": "인공지능", "cs.LG": "머신러닝", "cs.CL": "자연어처리",
    "cs.CV": "컴퓨터비전", "cs.NE": "신경망/진화", "stat.ML": "통계적 ML",
    "cs.RO": "로보틱스", "cs.IR": "정보검색", "cs.SD": "음성", "eess.AS": "오디오",
}

CSS = """
:root{
  --bg:#f7f7f8; --card:#ffffff; --text:#1a1a1e; --muted:#6b6b78;
  --border:#e4e4ea; --accent:#5b4bff; --accent-soft:#eceafe; --chip:#f0f0f4;
  --kid:#0a7d5a; --kid-soft:#e2f6ee; --ex:#b35c00; --ex-soft:#fceede;
  --shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#0f0f12; --card:#1a1a20; --text:#ececf1; --muted:#9a9aa8;
  --border:#2a2a33; --accent:#8b7bff; --accent-soft:#26233f; --chip:#24242c;
  --kid:#4fd6a6; --kid-soft:#123329; --ex:#f0a850; --ex-soft:#33260f;
  --shadow:0 1px 3px rgba(0,0,0,.4);
}}
:root[data-theme=dark]{
  --bg:#0f0f12; --card:#1a1a20; --text:#ececf1; --muted:#9a9aa8;
  --border:#2a2a33; --accent:#8b7bff; --accent-soft:#26233f; --chip:#24242c;
  --kid:#4fd6a6; --kid-soft:#123329; --ex:#f0a850; --ex-soft:#33260f;
  --shadow:0 1px 3px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo",
  "Malgun Gothic",sans-serif;line-height:1.65;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:840px;margin:0 auto;padding:0 20px}
header{padding:40px 0 18px;border-bottom:1px solid var(--border);margin-bottom:22px}
.title{font-size:1.7rem;font-weight:750;letter-spacing:-.02em;margin:0}
.subtitle{color:var(--muted);margin:8px 0 0;font-size:.95rem}
.meta{color:var(--muted);font-size:.82rem;margin-top:14px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.meta a{color:var(--accent);font-weight:600}
#search{width:100%;padding:11px 14px;border:1px solid var(--border);border-radius:10px;
  background:var(--card);color:var(--text);font-size:.95rem;outline:none;margin-bottom:24px}
#search:focus{border-color:var(--accent)}
.field{margin:0 0 30px}
.field-h{font-size:1.02rem;font-weight:720;margin:0 0 12px;padding-bottom:7px;
  border-bottom:2px solid var(--accent-soft);display:flex;align-items:center;gap:8px}
.field-h .cnt{font-size:.75rem;color:var(--muted);font-weight:500}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:16px 18px;margin-bottom:12px;box-shadow:var(--shadow);transition:.15s;display:block}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card h3{font-size:1.04rem;font-weight:680;margin:0 0 7px;letter-spacing:-.01em}
.tldr{color:var(--text);font-size:.92rem;margin:0 0 11px}
.badges{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.badge{font-size:.72rem;padding:3px 9px;border-radius:6px;background:var(--accent-soft);
  color:var(--accent);font-weight:600}
.kw{font-size:.72rem;padding:3px 9px;border-radius:6px;background:var(--chip);color:var(--muted)}
.pop{font-size:.72rem;padding:3px 9px;border-radius:6px;background:var(--ex-soft);color:var(--ex);font-weight:600}
.date{color:var(--muted);font-size:.75rem;margin-left:auto}
footer{color:var(--muted);font-size:.8rem;text-align:center;padding:36px 0}
.empty{color:var(--muted);text-align:center;padding:50px 0}
/* archive */
.issue-row{display:flex;justify-content:space-between;align-items:center;
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:15px 18px;margin-bottom:11px;box-shadow:var(--shadow);transition:.15s}
.issue-row:hover{border-color:var(--accent)}
.issue-row .wk{font-weight:700;font-size:1rem}
.issue-row .sub{color:var(--muted);font-size:.8rem;margin-top:3px}
/* detail */
.back{display:inline-block;color:var(--accent);font-size:.88rem;margin-bottom:16px}
.authors{color:var(--muted);font-size:.88rem;margin:6px 0 0}
.section{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:18px 20px;margin-bottom:13px;box-shadow:var(--shadow)}
.section h4{margin:0 0 8px;font-size:.8rem;color:var(--accent);
  text-transform:uppercase;letter-spacing:.04em}
.section p{margin:0}
.section.kid{background:var(--kid-soft);border-color:transparent}
.section.kid h4{color:var(--kid)}
.section.ex{background:var(--ex-soft);border-color:transparent}
.section.ex h4{color:var(--ex)}
.bg-item{padding:10px 0;border-bottom:1px solid var(--border)}
.bg-item:last-child{border-bottom:none;padding-bottom:0}
.bg-item b{display:block;font-size:.92rem;margin-bottom:2px}
.bg-item span{color:var(--muted);font-size:.88rem}
.links{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.btn{padding:9px 16px;border-radius:9px;background:var(--accent);color:#fff;font-size:.88rem;font-weight:600}
.btn.ghost{background:var(--chip);color:var(--text)}
.abstract{color:var(--muted);font-size:.9rem}
"""

TOGGLE_JS = """
(function(){var k='apd-theme',r=document.documentElement,s=localStorage.getItem(k);
if(s)r.setAttribute('data-theme',s);
window.toggleTheme=function(){var c=r.getAttribute('data-theme');
var n=c==='dark'?'light':(c==='light'?'dark':(matchMedia('(prefers-color-scheme:dark)').matches?'light':'dark'));
r.setAttribute('data-theme',n);localStorage.setItem(k,n);};})();
"""

SEARCH_JS = """
function doSearch(){var q=document.getElementById('search').value.toLowerCase().trim();
document.querySelectorAll('.field').forEach(function(f){var any=0;
f.querySelectorAll('.card').forEach(function(c){var ok=!q||c.dataset.search.indexOf(q)>-1;
c.style.display=ok?'block':'none';if(ok)any++;});
f.style.display=any?'block':'none';});}
"""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _cat_label(cat: str) -> str:
    return CAT_LABELS.get(cat, cat)


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y.%m.%d")
    except Exception:  # noqa: BLE001
        return (iso or "")[:10]


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<script>{TOGGLE_JS}</script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{body}
</div>
</body>
</html>"""


def _pop_badge(p: dict) -> str:
    bits = []
    if p.get("upvotes"):
        bits.append(f'👍 {p["upvotes"]}')
    if p.get("citations"):
        bits.append(f'📊 인용 {p["citations"]}')
    return f'<span class="pop">{" · ".join(bits)}</span>' if bits else ""


def _card(p: dict, prefix: str) -> str:
    s = p["summary"]
    kws = "".join(f'<span class="kw">{_esc(k)}</span>' for k in s.get("keywords", [])[:3])
    blob = _esc(
        (p["title"] + " " + s.get("tldr", "") + " " + " ".join(s.get("keywords", []))
         + " " + p.get("subfield", "")).lower()
    )
    return f"""<a class="card" href="{prefix}paper/{_esc(p['id'])}.html" data-search="{blob}">
  <h3>{_esc(p['title'])}</h3>
  <p class="tldr">{_esc(s.get('tldr',''))}</p>
  <div class="badges"><span class="badge">{_esc(_cat_label(p.get('primary_category','')))}</span>
    {_pop_badge(p)}{kws}<span class="date">{_fmt_date(p.get('published',''))}</span></div>
</a>"""


def _fields_html(papers: list[dict], prefix: str) -> str:
    """분야별로 그룹지어 렌더링 (FIELD_ORDER 순서)."""
    groups: dict[str, list[dict]] = {}
    for p in papers:
        groups.setdefault(p.get("subfield", "기타 AI"), []).append(p)
    order = [f for f in FIELD_ORDER if f in groups] + [f for f in groups if f not in FIELD_ORDER]
    out = []
    for f in order:
        items = sorted(groups[f], key=lambda x: (x.get("upvotes", 0), x.get("published", "")), reverse=True)
        cards = "\n".join(_card(p, prefix) for p in items)
        out.append(f'<div class="field"><h2 class="field-h">{_esc(f)}'
                   f'<span class="cnt">{len(items)}편</span></h2>{cards}</div>')
    return "\n".join(out) or '<p class="empty">논문이 없습니다.</p>'


# ------------------------------------------------------------------ 상세
def _detail(p: dict, issue_label: str | None) -> str:
    s = p["summary"]
    authors = ", ".join(p.get("authors", [])[:8]) + (" 외" if len(p.get("authors", [])) > 8 else "")
    kws = "".join(f'<span class="kw">{_esc(k)}</span>' for k in s.get("keywords", []))
    cats = "".join(f'<span class="badge">{_esc(_cat_label(c))}</span>' for c in p.get("categories", [])[:5])

    bg = ""
    if s.get("background"):
        rows = "".join(
            f'<div class="bg-item"><b>{_esc(b["term"])}</b><span>{_esc(b.get("explain",""))}</span></div>'
            for b in s["background"]
        )
        bg = f'<div class="section"><h4>📚 배경지식 — 알아두면 좋은 개념</h4>{rows}</div>'

    example = (f'<div class="section ex"><h4>💡 예시 — 이렇게 쓰여요</h4>'
               f'<p>{_esc(s["example"])}</p></div>') if s.get("example") else ""
    eli12 = (f'<div class="section kid"><h4>🧒 12살 버전 — 아주 쉽게</h4>'
             f'<p>{_esc(s["eli12"])}</p></div>') if s.get("eli12") else ""

    back = f'<a class="back" href="../issue/{_esc(issue_label)}.html">← {_esc(issue_label)} 이슈로</a>' \
        if issue_label else '<a class="back" href="../index.html">← 목록으로</a>'

    body = f"""{back}
<h1 class="title" style="font-size:1.4rem">{_esc(p['title'])}</h1>
<p class="authors">{_esc(authors)}</p>
<div class="badges" style="margin:12px 0">{cats}{_pop_badge(p)}
  <span class="date">{_fmt_date(p.get('published',''))} · arXiv:{_esc(p['id'])}</span></div>
<div class="section" style="border-color:var(--accent)"><h4>한 줄 요약</h4><p>{_esc(s.get('tldr',''))}</p></div>
{eli12}
{example}
<div class="section"><h4>어떤 문제를 푸는가</h4><p>{_esc(s.get('problem',''))}</p></div>
<div class="section"><h4>핵심 방법</h4><p>{_esc(s.get('method',''))}</p></div>
<div class="section"><h4>결과와 의의</h4><p>{_esc(s.get('result',''))}</p></div>
{bg}
<div class="section"><h4>키워드</h4><div class="badges">{kws}</div></div>
<div class="section"><h4>원문 초록</h4><p class="abstract">{_esc(p.get('abstract',''))}</p>
  <div class="links">
    <a class="btn" href="{_esc(p['pdf_url'])}" target="_blank" rel="noopener">PDF 원문</a>
    <a class="btn ghost" href="{_esc(p['arxiv_url'])}" target="_blank" rel="noopener">arXiv 페이지</a>
  </div></div>
<footer>AI 논문 요약 다이제스트</footer>"""
    return _page(p["title"] + " · AI 논문 요약", body)


# ------------------------------------------------------------------ 목록/아카이브
def _issue_body(cfg: dict, label: str, date_iso: str, papers: list[dict],
                prefix: str, is_index: bool) -> str:
    now = _fmt_date(date_iso)
    if is_index:
        head = f"""<header>
  <h1 class="title">{_esc(cfg.get('site_title',''))}</h1>
  <p class="subtitle">{_esc(cfg.get('site_description',''))}</p>
  <p class="meta"><b>이번 주 이슈 · {_esc(label)}</b> ({now}) · 총 {len(papers)}편
    · <a href="archive.html">📚 지난 주차 보기</a>
    · <a href="#" onclick="toggleTheme();return false">🌗 테마</a></p>
</header>
<input id="search" type="search" placeholder="제목·키워드로 검색…" oninput="doSearch()">"""
    else:
        head = f"""<a class="back" href="{prefix}archive.html">← 아카이브로</a>
<header style="padding-top:8px">
  <h1 class="title">{_esc(label)} 주간 이슈</h1>
  <p class="subtitle">{now} 발행 · 총 {len(papers)}편 · <a href="{prefix}index.html" style="color:var(--accent)">최신 이슈 →</a></p>
</header>
<input id="search" type="search" placeholder="제목·키워드로 검색…" oninput="doSearch()">"""
    return head + _fields_html(papers, prefix) + \
        f'<footer>arXiv · Hugging Face 트렌딩 기반 자동 선별</footer><script>{SEARCH_JS}</script>'


def _archive_body(cfg: dict, issues: list[tuple[str, dict]]) -> str:
    rows = []
    for label, meta in issues:
        n = sum(len(v) for v in meta.get("fields", {}).values())
        fields = ", ".join(meta.get("fields", {}).keys())
        rows.append(f"""<a class="issue-row" href="issue/{_esc(label)}.html">
  <div><div class="wk">{_esc(label)}</div><div class="sub">{_esc(fields)}</div></div>
  <div class="badges"><span class="badge">{n}편</span>
    <span class="date">{_fmt_date(meta.get('date',''))}</span></div></a>""")
    body = f"""<a class="back" href="index.html">← 최신 이슈로</a>
<header style="padding-top:8px"><h1 class="title">📚 주차별 아카이브</h1>
  <p class="subtitle">지난 주간 이슈를 분야별로 다시 볼 수 있습니다.</p></header>
{"".join(rows) or '<p class="empty">아직 발행된 이슈가 없습니다.</p>'}
<footer>AI 논문 요약 다이제스트</footer>"""
    return body


# ------------------------------------------------------------------ 빌드
def build_site(store: dict, issues: dict, cfg: dict) -> None:
    os.makedirs(os.path.join(DOCS, "paper"), exist_ok=True)
    os.makedirs(os.path.join(DOCS, "issue"), exist_ok=True)

    # 최신순 정렬된 이슈 목록
    ordered = sorted(issues.items(), key=lambda kv: kv[1].get("date", ""), reverse=True)

    def papers_of(meta: dict) -> list[dict]:
        ids = [pid for lst in meta.get("fields", {}).values() for pid in lst]
        return [store[i] for i in ids if i in store]

    # index = 최신 이슈
    if ordered:
        label, meta = ordered[0]
        with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
            f.write(_page(cfg.get("site_title", "AI 논문 요약"),
                          _issue_body(cfg, label, meta.get("date", ""), papers_of(meta), "", True)))
    else:
        with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
            f.write(_page(cfg.get("site_title", "AI 논문 요약"),
                          '<header><h1 class="title">준비 중</h1></header>'
                          '<p class="empty">첫 주간 이슈를 생성하세요: <code>python3 main.py</code></p>'))

    # 아카이브
    with open(os.path.join(DOCS, "archive.html"), "w", encoding="utf-8") as f:
        f.write(_page("주차별 아카이브 · AI 논문 요약", _archive_body(cfg, ordered)))

    # 주차별 이슈 페이지
    for label, meta in ordered:
        with open(os.path.join(DOCS, "issue", f"{label}.html"), "w", encoding="utf-8") as f:
            f.write(_page(f"{label} 주간 이슈 · AI 논문 요약",
                          _issue_body(cfg, label, meta.get("date", ""), papers_of(meta), "../", False)))

    # 논문 상세 (issue_label = 그 논문이 속한 주차)
    for pid, p in store.items():
        with open(os.path.join(DOCS, "paper", f"{pid}.html"), "w", encoding="utf-8") as f:
            f.write(_detail(p, p.get("week")))

    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print(f"  사이트 생성: 이슈 {len(ordered)}개, 논문 {len(store)}편 → docs/")
