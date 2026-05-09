#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("mainrepo").resolve()
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("public").resolve()

ASSET_DIRS = [
    ROOT / "app" / "src" / "main" / "assets",
    ROOT / "app" / "src" / "main" / "res",
]

BAD_PATTERNS = re.compile(
    r"(https?://|www\.|web\.archive\.org|balkesarsivi\.com|/user/cimage|user/cimage|cimage/|"
    r"\.(gif|jpg|jpeg|png|webp)(\s|$|/|\?|-))",
    re.I,
)
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
IMG_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|gif)(\?.*)?$", re.I)

TITLE_KEYS = ["title", "baslik", "başlık", "name", "headline", "label", "pageTitle", "displayTitle"]
TEXT_KEYS = ["text", "body", "content", "fullText", "article", "description", "desc", "summary", "metin", "icerik", "içerik"]

def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def clean_text(s: Any) -> str:
    if s is None:
        return ""
    s = html.unescape(str(s))
    s = re.sub(r"\r\n?", "\n", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablolar\s*$", "", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablo\s+\d+\s*$", "", s)
    s = re.sub(r"(?i)Kayıp\s+Sayfalar\s*:?", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def word_count(s: str) -> int:
    s = URL_RE.sub(" ", s)
    s = re.sub(r"[\w./:-]+\.(png|jpg|jpeg|webp|gif)", " ", s, flags=re.I)
    return len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{3,}", s))

def is_bad_line(s: Any) -> bool:
    if not isinstance(s, str):
        return True
    t = clean_text(s)
    if not t:
        return True
    if URL_RE.fullmatch(t):
        return True
    if BAD_PATTERNS.search(t) and word_count(t) < 12:
        return True
    if len(URL_RE.findall(t)) >= 1 and word_count(t) < 18:
        return True
    return False

def is_bad_item(title: str, text: str) -> bool:
    title = clean_text(title)
    text = clean_text(text)
    blob = f"{title}\n{text[:500]}"
    if not title or not text:
        return True
    if is_bad_line(title):
        return True
    if word_count(text) < 10:
        return True
    if BAD_PATTERNS.search(blob) and word_count(blob) < 35:
        return True
    url_chars = sum(len(m.group(0)) for m in URL_RE.finditer(blob))
    if url_chars / max(1, len(blob)) > 0.25 and word_count(blob) < 70:
        return True
    if re.search(r"ziyaretçi|ziyaretci|defter", title + " " + text[:300], re.I):
        return True
    return False

def strip_noise(s: str) -> str:
    out = []
    for raw in re.split(r"\n+", s):
        line = clean_text(raw)
        if not line:
            continue
        if is_bad_line(line):
            continue
        line = URL_RE.sub("", line).strip()
        if line:
            out.append(line)
    return clean_text("\n\n".join(out))

def first_clean_str(d: dict, keys: list[str]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip() and not is_bad_line(v):
            return clean_text(v)
    return ""

def collect_text(obj: Any, limit: int = 120000) -> str:
    parts: list[str] = []
    total = 0

    def walk(x: Any, key: str = ""):
        nonlocal total
        if total > limit:
            return
        if isinstance(x, str):
            if is_bad_line(x):
                return
            t = strip_noise(x)
            if t and word_count(t) >= 5:
                parts.append(t)
                total += len(t)
        elif isinstance(x, dict):
            for k, v in x.items():
                if re.search(r"(image|photo|foto|src|path|cover|thumb|url|href|link)", str(k), re.I):
                    continue
                walk(v, str(k))
        elif isinstance(x, list):
            for v in x:
                walk(v, key)

    walk(obj)
    return clean_text("\n\n".join(parts))

def find_images(obj: Any) -> list[str]:
    imgs: list[str] = []

    def add(v: Any):
        if not isinstance(v, str):
            return
        vv = v.strip()
        if not IMG_EXT_RE.search(vv):
            return
        if vv.startswith("http://") or vv.startswith("https://") or "web.archive.org" in vv:
            return
        imgs.append(vv)

    def walk(x: Any):
        if isinstance(x, dict):
            for k, v in x.items():
                if re.search(r"(image|photo|foto|src|path|cover|thumb)", str(k), re.I):
                    add(v)
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        else:
            add(x)

    walk(obj)
    seen: list[str] = []
    for i in imgs:
        if i not in seen:
            seen.append(i)
    return seen[:8]

def slugify(s: str, fallback: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = s.translate(tr).lower()
    s = re.sub(r"https?://|www\.", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        s = fallback
    if BAD_PATTERNS.search(s):
        s = fallback
    return s[:80]

def load_jsons() -> list[tuple[Path, Any]]:
    out = []
    for base in ASSET_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*.json"):
            try:
                out.append((p, json.loads(read_text(p))))
            except Exception:
                pass
    return out

def title_from_text(text: str, idx: int) -> str:
    for part in re.split(r"\n+|\. ", text):
        line = clean_text(part)
        if 12 <= len(line) <= 110 and not is_bad_line(line):
            return line[:90]
    return f"Balkes Arşivi {idx}"

def normalize_item(raw: Any, source: str, idx: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    title = first_clean_str(raw, TITLE_KEYS)
    text = first_clean_str(raw, TEXT_KEYS)

    if text:
        text = strip_noise(text)
    if not text:
        text = collect_text(raw)

    if not title or is_bad_line(title):
        title = title_from_text(text, idx)

    title = clean_text(title)
    text = clean_text(text)

    if is_bad_item(title, text):
        return None

    images = find_images(raw)
    slug = slugify(title, f"arsiv-{idx}")

    return {
        "id": f"{slug}-{idx}",
        "title": title,
        "text": text,
        "summary": clean_text(text[:260]) + ("…" if len(text) > 260 else ""),
        "images": images,
        "source": source,
    }

def extract_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path, data in load_jsons():
        candidates: list[Any] = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            for key in ["items", "archive", "pages", "posts", "articles", "data", "records"]:
                if isinstance(data.get(key), list):
                    candidates.extend(data[key])
            if not candidates:
                candidates = [data]

        for raw in candidates:
            item = normalize_item(raw, str(path.relative_to(ROOT)), len(items) + 1)
            if not item:
                continue
            key = re.sub(r"\s+", " ", item["title"] + " " + item["text"][:80]).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

    return items

def copy_media():
    media = OUT / "media"
    media.mkdir(parents=True, exist_ok=True)
    for base in ASSET_DIRS:
        if not base.exists():
            continue
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"]:
            for p in base.rglob(ext):
                if p.is_file() and p.stat().st_size < 95 * 1024 * 1024:
                    rel = p.relative_to(base)
                    dest = media / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists() or dest.stat().st_size != p.stat().st_size:
                        shutil.copy2(p, dest)

def write_site(items: list[dict[str, Any]]):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "data" / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    css = r"""
:root{
  --bg:#0f0b0c;--panel:#1b1517;--panel2:#241b1e;--line:#3a252a;
  --text:#f5f1ef;--muted:#cfc4c0;--red:#c8102e;--red2:#8f0b1b;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
body:before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(circle at 15% 0%,rgba(200,16,46,.28),transparent 32rem),linear-gradient(180deg,#170b0f,#0f0b0c 34rem)}
.hero{padding:42px 18px 24px;max-width:1180px;margin:auto;color:var(--text)}
.hero h1{font-size:clamp(38px,7vw,76px);margin:0 0 18px;letter-spacing:-.055em;line-height:.95}
.hero p{max-width:780px;font-size:clamp(18px,2vw,25px);line-height:1.55;color:var(--muted);margin:0}
.shell{max-width:1180px;margin:0 auto 70px;padding:0 16px}
.toolbar{position:sticky;top:10px;z-index:5;background:rgba(27,21,23,.92);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:24px;padding:14px;display:grid;gap:10px;grid-template-columns:1fr auto;box-shadow:0 18px 50px rgba(0,0,0,.32)}
input,button{font:inherit;border-radius:16px;padding:13px 15px}
input{background:#100d0e;border:1px solid #4a3439;color:var(--text);outline:none}
input::placeholder{color:#8f8582}
button{border:1px solid #d81a39;background:linear-gradient(135deg,var(--red),var(--red2));color:white;font-weight:800;cursor:pointer}
.count{margin:18px 4px;color:var(--muted);font-weight:800}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:18px;margin-top:18px}
.card{background:linear-gradient(180deg,var(--panel2),var(--panel));border-radius:24px;overflow:hidden;box-shadow:0 18px 44px rgba(0,0,0,.28);border:1px solid var(--line);display:flex;flex-direction:column;min-height:360px;cursor:pointer}
.card:hover{transform:translateY(-2px);transition:.18s ease}
.thumb{height:160px;background:linear-gradient(135deg,#b5121b,#141012);display:grid;place-items:center;color:white;font-size:42px;font-weight:900;letter-spacing:-.05em}
.thumb img{width:100%;height:100%;object-fit:cover}
.content{padding:18px}
.content h2{font-size:22px;line-height:1.2;margin:0 0 10px;color:#fff;word-break:break-word}
.content p{font-size:16px;line-height:1.65;margin:0;color:var(--muted);word-break:break-word}
.meta{margin-top:auto;padding:0 18px 18px;font-size:13px;color:#aa9d99}
.empty{padding:26px;background:var(--panel);border-radius:24px;margin-top:18px;border:1px solid var(--line)}
.detail{display:none;background:linear-gradient(180deg,#21191c,#171214);border:1px solid var(--line);border-radius:28px;margin-top:18px;padding:clamp(20px,4vw,48px);box-shadow:0 22px 60px rgba(0,0,0,.36)}
.detail.active{display:block}
.detail h1{font-size:clamp(34px,5vw,60px);line-height:1.02;margin:0 0 24px;color:#fff;letter-spacing:-.04em}
.article{max-width:880px;font-size:clamp(19px,2vw,23px);line-height:1.82;color:#eee6e2;word-break:break-word}
.article p{margin:0 0 22px}
.article img{max-width:100%;border-radius:22px;box-shadow:0 12px 30px rgba(0,0,0,.30);margin:22px 0 7px}
.caption{font-size:14px;color:#b9aaa5;margin-bottom:22px}
.badge{display:inline-block;background:#2a1e22;border:1px solid #493238;color:#e9dad6;border-radius:999px;padding:8px 12px;margin:3px;font-size:13px}
.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
footer{color:#a99d99;text-align:center;padding:34px}
@media(max-width:700px){
  .toolbar{grid-template-columns:1fr;top:0;border-radius:0 0 22px 22px;margin-left:-16px;margin-right:-16px}
  .hero{padding-top:30px}
  .grid{grid-template-columns:1fr}
  .card{min-height:unset}
}
"""
    (OUT / "style.css").write_text(css, encoding="utf-8")

    js = r"""
let ITEMS=[];
const mediaPrefix="media/";
const $=s=>document.querySelector(s);
const grid=$("#grid"), detail=$("#detail"), search=$("#search");

function esc(s){return (s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]));}
function mediaPath(p){ if(!p) return ""; return mediaPrefix + p.replace(/^.*?assets\//,"").replace(/^app\/src\/main\/assets\//,"").replace(/^\/+/,""); }
function placeholder(){ return `<div class="thumb"><span>1966</span></div>`; }
function thumb(item){
  const img=(item.images||[])[0];
  return img ? `<div class="thumb"><img loading="lazy" src="${esc(mediaPath(img))}" onerror="this.parentElement.innerHTML='<span>1966</span>'"></div>` : placeholder();
}
function card(item){
  return `<article class="card" onclick="openItem('${esc(item.id)}')">
    ${thumb(item)}
    <div class="content"><h2>${esc(item.title)}</h2><p>${esc(item.summary)}</p></div>
    <div class="meta">Balkes Arşivi</div>
  </article>`;
}
function renderList(){
  const q=(search.value||"").toLocaleLowerCase("tr");
  const arr=ITEMS.filter(x=>(x.title+" "+x.summary+" "+x.text).toLocaleLowerCase("tr").includes(q));
  detail.classList.remove("active");
  grid.style.display="grid";
  grid.innerHTML=arr.length?arr.map(card).join(""):`<div class="empty">Sonuç bulunamadı.</div>`;
}
function paragraphs(text){
  return (text||"").split(/\n{2,}/).map(p=>p.trim()).filter(Boolean);
}
function articleHtml(item){
  const imgs=(item.images||[]).slice(0,6);
  const ps=paragraphs(item.text);
  let out="";
  ps.forEach((p,i)=>{
    out += `<p>${esc(p).replace(/\n/g,"<br>")}</p>`;
    if(imgs[i]){
      out += `<img loading="lazy" src="${esc(mediaPath(imgs[i]))}"><div class="caption">Arşiv görseli</div>`;
    }
  });
  if(!imgs.length){
    out = `<div class="thumb" style="height:220px;border-radius:22px;margin-bottom:14px"><span>1966</span></div><div class="caption">Temsilidir</div>` + out;
  }
  return out;
}
function openItem(id){
  const item=ITEMS.find(x=>x.id===id);
  if(!item) return;
  grid.style.display="none";
  detail.classList.add("active");
  detail.innerHTML=`<div class="topline"><button onclick="renderList()">← Arşive dön</button><span class="badge">Balkes Arşivi</span></div>
    <h1>${esc(item.title)}</h1>
    <div class="article">${articleHtml(item)}</div>`;
  location.hash=id;
  scrollTo({top:0,behavior:"smooth"});
}
async function boot(){
  ITEMS=await fetch("data/items.json",{cache:"no-store"}).then(r=>r.json());
  $("#count").textContent=ITEMS.length+" içerik";
  search.addEventListener("input", renderList);
  if(location.hash.length>1){
    const id=decodeURIComponent(location.hash.slice(1));
    renderList(); openItem(id);
  }else renderList();
}
boot();
"""
    (OUT / "app.js").write_text(js, encoding="utf-8")

    html_doc = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#0f0b0c">
  <title>Balkes Arşivi</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="hero">
    <h1>Balkes Arşivi</h1>
    <p>Kapatılan Balkes Arşivi projesinden kurtarılan verilerle yapılmış Balıkesirspor arşivi.</p>
  </header>
  <main class="shell">
    <section class="toolbar">
      <input id="search" placeholder="Arşivde ara...">
      <button onclick="location.reload()">Yenile</button>
    </section>
    <div class="count" id="count">Yükleniyor...</div>
    <section id="detail" class="detail"></section>
    <section id="grid" class="grid"></section>
  </main>
  <footer>Balkes Arşivi</footer>
  <script src="app.js"></script>
</body>
</html>
"""
    (OUT / "index.html").write_text(html_doc, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    items = extract_items()
    copy_media()
    write_site(items)

    bad = [x for x in items if BAD_PATTERNS.search(x["title"]) or BAD_PATTERNS.search(x["summary"])]
    print(f"{len(items)} temiz içerik ile site üretildi: {OUT}")
    print(f"Kalan bozuk URL/görsel kartı: {len(bad)}")
    if bad:
        for x in bad[:20]:
            print("BOZUK:", x["title"])

if __name__ == "__main__":
    main()
