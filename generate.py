"""요약된 논문 데이터로 정적 사이트(docs/)를 생성한다."""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone

DOCS = os.path.join(os.path.dirname(__file__), "docs")

CAT_LABELS = {
    "cs.AI": "인공지능", "cs.LG": "머신러닝", "cs.CL": "자연어처리",
    "cs.CV": "컴퓨터비전", "cs.NE": "신경망/진화", "stat.ML": "통계적 ML",
    "cs.RO": "로보틱스", "cs.IR": "정보검색",
}

CSS = """
:root{
  --bg:#f7f7f8; --card:#ffffff; --text:#1a1a1e; --muted:#6b6b78;
  --border:#e4e4ea; --accent:#5b4bff; --accent-soft:#eceafe; --chip:#f0f0f4;
  --shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
}
:root:not([data-theme=light]){@media (prefers-color-scheme:dark){
  :root{}
}}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#0f0f12; --card:#1a1a20; --text:#ececf1; --muted:#9a9aa8;
  --border:#2a2a33; --accent:#8b7bff; --accent-soft:#26233f; --chip:#24242c;
  --shadow:0 1px 3px rgba(0,0,0,.4);
}}
:root[data-theme=dark]{
  --bg:#0f0f12; --card:#1a1a20; --text:#ececf1; --muted:#9a9aa8;
  --border:#2a2a33; --accent:#8b7bff; --accent-soft:#26233f; --chip:#24242c;
  --shadow:0 1px 3px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo",
  "Malgun Gothic",sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.wrap{max-width:820px;margin:0 auto;padding:0 20px}
header{padding:44px 0 20px;border-bottom:1px solid var(--border);margin-bottom:24px}
.title{font-size:1.7rem;font-weight:750;letter-spacing:-.02em;margin:0}
.subtitle{color:var(--muted);margin:8px 0 0;font-size:.95rem}
.meta{color:var(--muted);font-size:.8rem;margin-top:14px}
.controls{display:flex;flex-direction:column;gap:12px;margin-bottom:22px}
#search{width:100%;padding:11px 14px;border:1px solid var(--border);border-radius:10px;
  background:var(--card);color:var(--text);font-size:.95rem;outline:none}
#search:focus{border-color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{padding:6px 12px;border-radius:20px;background:var(--chip);border:1px solid transparent;
  font-size:.82rem;cursor:pointer;color:var(--muted);user-select:none;transition:.15s}
.chip.active{background:var(--accent-soft);color:var(--accent);border-color:var(--accent)}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:18px 20px;margin-bottom:14px;box-shadow:var(--shadow);transition:.15s;display:block}
.card:hover{border-color:var(--accent);transform:translateY(-1px)}
.card h2{font-size:1.08rem;font-weight:680;margin:0 0 8px;letter-spacing:-.01em}
.tldr{color:var(--text);font-size:.94rem;margin:0 0 12px}
.badges{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.badge{font-size:.72rem;padding:3px 9px;border-radius:6px;background:var(--accent-soft);
  color:var(--accent);font-weight:600}
.kw{font-size:.72rem;padding:3px 9px;border-radius:6px;background:var(--chip);color:var(--muted)}
.date{color:var(--muted);font-size:.75rem;margin-left:auto}
footer{color:var(--muted);font-size:.8rem;text-align:center;padding:36px 0}
.empty{color:var(--muted);text-align:center;padding:50px 0}
/* detail page */
.back{display:inline-block;color:var(--accent);font-size:.88rem;margin-bottom:18px}
.section{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:20px 22px;margin-bottom:14px;box-shadow:var(--shadow)}
.section h3{margin:0 0 8px;font-size:.82rem;color:var(--accent);
  text-transform:uppercase;letter-spacing:.04em}
.section p{margin:0}
.authors{color:var(--muted);font-size:.88rem;margin:6px 0 0}
.links{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
.btn{padding:9px 16px;border-radius:9px;background:var(--accent);color:#fff;
  font-size:.88rem;font-weight:600}
.btn.ghost{background:var(--chip);color:var(--text)}
.abstract{color:var(--muted);font-size:.9rem}
"""

TOGGLE_JS = """
(function(){
  var k='apd-theme',r=document.documentElement,s=localStorage.getItem(k);
  if(s)r.setAttribute('data-theme',s);
  window.toggleTheme=function(){
    var cur=r.getAttribute('data-theme');
    var next=cur==='dark'?'light':(cur==='light'?'dark':
      (matchMedia('(prefers-color-scheme:dark)').matches?'light':'dark'));
    r.setAttribute('data-theme',next);localStorage.setItem(k,next);
  };
})();
"""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _cat_label(cat: str) -> str:
    return CAT_LABELS.get(cat, cat)


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y.%m.%d")
    except Exception:  # noqa: BLE001
        return iso[:10]


def _page(title: str, body: str, rel: str = "") -> str:
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


def _card(p: dict) -> str:
    s = p["summary"]
    badges = f'<span class="badge">{_esc(_cat_label(p["primary_category"]))}</span>'
    kws = "".join(f'<span class="kw">{_esc(k)}</span>' for k in s.get("keywords", [])[:3])
    search_blob = _esc(
        (p["title"] + " " + s.get("tldr", "") + " " + " ".join(s.get("keywords", [])) + " "
         + " ".join(p.get("categories", []))).lower()
    )
    return f"""<a class="card" href="paper/{_esc(p['id'])}.html"
   data-cat="{_esc(p['primary_category'])}" data-search="{search_blob}">
  <h2>{_esc(p['title'])}</h2>
  <p class="tldr">{_esc(s.get('tldr',''))}</p>
  <div class="badges">{badges}{kws}
    <span class="date">{_fmt_date(p.get('published',''))}</span>
  </div>
</a>"""


def _detail(p: dict) -> str:
    s = p["summary"]
    authors = ", ".join(p.get("authors", [])[:8])
    if len(p.get("authors", [])) > 8:
        authors += " 외"
    kws = "".join(f'<span class="kw">{_esc(k)}</span>' for k in s.get("keywords", []))
    cats = "".join(
        f'<span class="badge">{_esc(_cat_label(c))}</span>' for c in p.get("categories", [])[:5]
    )
    body = f"""<a class="back" href="../index.html">← 목록으로</a>
<h1 class="title" style="font-size:1.45rem">{_esc(p['title'])}</h1>
<p class="authors">{_esc(authors)}</p>
<div class="badges" style="margin:12px 0">{cats}
  <span class="date">{_fmt_date(p.get('published',''))} · arXiv:{_esc(p['id'])}</span>
</div>
<div class="section" style="border-color:var(--accent)">
  <h3>한 줄 요약</h3><p>{_esc(s.get('tldr',''))}</p></div>
<div class="section"><h3>어떤 문제를 푸는가</h3><p>{_esc(s.get('problem',''))}</p></div>
<div class="section"><h3>핵심 방법</h3><p>{_esc(s.get('method',''))}</p></div>
<div class="section"><h3>결과와 의의</h3><p>{_esc(s.get('result',''))}</p></div>
<div class="section"><h3>키워드</h3><div class="badges">{kws}</div></div>
<div class="section"><h3>원문 초록</h3><p class="abstract">{_esc(p.get('abstract',''))}</p>
  <div class="links">
    <a class="btn" href="{_esc(p['pdf_url'])}" target="_blank" rel="noopener">PDF 원문</a>
    <a class="btn ghost" href="{_esc(p['arxiv_url'])}" target="_blank" rel="noopener">arXiv 페이지</a>
  </div>
</div>
<footer>AI 논문 요약 다이제스트</footer>"""
    return _page(p["title"] + " · AI 논문 요약", body)


def _index(papers: list[dict], cfg: dict) -> str:
    cats = []
    for p in papers:
        c = p["primary_category"]
        if c not in cats:
            cats.append(c)
    chips = '<span class="chip active" data-cat="all" onclick="filt(this)">전체</span>'
    chips += "".join(
        f'<span class="chip" data-cat="{_esc(c)}" onclick="filt(this)">{_esc(_cat_label(c))}</span>'
        for c in cats
    )
    cards = "\n".join(_card(p) for p in papers) or '<p class="empty">아직 요약된 논문이 없습니다.</p>'
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = f"""<header>
  <h1 class="title">{_esc(cfg.get('site_title','AI 논문 요약'))}</h1>
  <p class="subtitle">{_esc(cfg.get('site_description',''))}</p>
  <p class="meta">총 {len(papers)}편 · 마지막 갱신 {now}
    · <a href="#" onclick="toggleTheme();return false" style="color:var(--accent)">🌗 테마</a></p>
</header>
<div class="controls">
  <input id="search" type="search" placeholder="제목·키워드로 검색…" oninput="doSearch()">
  <div class="chips">{chips}</div>
</div>
<div id="list">{cards}</div>
<footer>arXiv 데이터 기반 · 자동 생성</footer>
<script>
var curCat='all';
function filt(el){{
  document.querySelectorAll('.chip').forEach(function(c){{c.classList.remove('active')}});
  el.classList.add('active');curCat=el.dataset.cat;doSearch();
}}
function doSearch(){{
  var q=document.getElementById('search').value.toLowerCase().trim();
  var n=0;
  document.querySelectorAll('.card').forEach(function(c){{
    var okCat=curCat==='all'||c.dataset.cat===curCat;
    var okQ=!q||c.dataset.search.indexOf(q)>-1;
    var show=okCat&&okQ;c.style.display=show?'block':'none';if(show)n++;
  }});
  var e=document.getElementById('empty');
  if(n===0){{if(!e){{e=document.createElement('p');e.id='empty';e.className='empty';
    e.textContent='검색 결과가 없습니다.';document.getElementById('list').appendChild(e);}}}}
  else if(e){{e.remove();}}
}}
</script>"""
    return _page(cfg.get("site_title", "AI 논문 요약"), body)


def build_site(papers: list[dict], cfg: dict) -> None:
    """최신순 정렬 후 index + 상세 페이지들을 생성한다."""
    papers = sorted(papers, key=lambda p: p.get("published", ""), reverse=True)
    os.makedirs(os.path.join(DOCS, "paper"), exist_ok=True)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(_index(papers, cfg))
    for p in papers:
        with open(os.path.join(DOCS, "paper", f"{p['id']}.html"), "w", encoding="utf-8") as f:
            f.write(_detail(p))
    # GitHub Pages가 Jekyll 처리를 건너뛰도록
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print(f"  사이트 생성: {len(papers)}편 → docs/")
