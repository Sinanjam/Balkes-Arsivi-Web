#!/usr/bin/env python3
from __future__ import annotations
import json, re, shutil, sys
from pathlib import Path
from typing import Any

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("mainrepo").resolve()
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("public").resolve()
BASES = [ROOT / "app" / "src" / "main" / "assets", ROOT / "app" / "src" / "main" / "res"]

def text(p: Path) -> str:
    try: return p.read_text(encoding="utf-8", errors="ignore")
    except Exception: return ""

def clean(s: Any) -> str:
    s = "" if s is None else str(s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablolar\s*$", "", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablo\s+\d+\s*$", "", s)
    s = re.sub(r"(?i)Kayıp\s+Sayfalar\s*:?", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def first(d: dict, keys: list[str]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip(): return clean(v)
    return ""

def collect(obj: Any, limit=90000) -> str:
    parts=[]
    def walk(x):
        if sum(map(len, parts)) > limit: return
        if isinstance(x, str):
            t=clean(x)
            if len(t)>25: parts.append(t)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(obj)
    return clean("\n\n".join(parts))

def images(obj: Any) -> list[str]:
    out=[]
    def add(v):
        if isinstance(v,str) and re.search(r"\.(png|jpe?g|webp|gif)$", v.strip(), re.I): out.append(v.strip())
    def walk(x):
        if isinstance(x, dict):
            for k,v in x.items():
                if re.search(r"(image|photo|foto|src|path|cover|thumb|drawable)", str(k), re.I): add(v)
                walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
        else: add(x)
    walk(obj)
    seen=[]
    for i in out:
        if i not in seen: seen.append(i)
    return seen[:10]

def slug(s: str, fb: str) -> str:
    tr=str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s=s.translate(tr).lower()
    s=re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or fb

def json_files():
    for b in BASES:
        if b.exists():
            yield from b.rglob("*.json")

def norm(raw: Any, source: str, idx: int):
    if not isinstance(raw, dict): return None
    title=first(raw,["title","baslik","başlık","name","headline","label","pageTitle","displayTitle"])
    body=first(raw,["text","body","content","fullText","article","description","desc","summary","metin","icerik","içerik"])
    if not body: body=collect(raw)
    if not title: title=clean(body.split("\n",1)[0])[:100]
    title=clean(title); body=clean(body)
    if not title or len(title)<3: return None
    if re.search(r"ziyaretçi|ziyaretci|defter", title, re.I): return None
    if len(body)<30 and not images(raw): return None
    return {"id": f"{slug(title,'item')}-{idx}", "title": title, "text": body, "summary": clean(body[:260]) + ("…" if len(body)>260 else ""), "images": images(raw), "source": source}

def extract():
    items=[]; seen=set()
    for p in json_files():
        try: data=json.loads(text(p))
        except Exception: continue
        cand=[]
        if isinstance(data, list): cand=data
        elif isinstance(data, dict):
            for key in ["items","archive","pages","posts","articles","data","records","entries"]:
                if isinstance(data.get(key), list): cand += data[key]
            if not cand: cand=[data]
        for raw in cand:
            it=norm(raw, str(p.relative_to(ROOT)), len(items)+1)
            if not it: continue
            k=re.sub(r"\s+"," ",it["title"]).lower().strip()
            if k in seen: continue
            seen.add(k); items.append(it)
    if not items:
        for b in BASES:
            if not b.exists(): continue
            for p in list(b.rglob("*.txt"))+list(b.rglob("*.md"))+list(b.rglob("*.html")):
                body=clean(text(p))
                if len(body)<50: continue
                title=clean(body.split("\n",1)[0])[:100] or p.stem
                if re.search(r"ziyaretçi|ziyaretci|defter", title, re.I): continue
                items.append({"id":f"{slug(title,'file')}-{len(items)+1}","title":title,"text":body,"summary":body[:260]+("…" if len(body)>260 else ""),"images":[],"source":str(p.relative_to(ROOT))})
    return items

def copy_media():
    m=OUT/"media"; m.mkdir(parents=True, exist_ok=True)
    for b in BASES:
        if not b.exists(): continue
        for ext in ["*.png","*.jpg","*.jpeg","*.webp","*.gif"]:
            for p in b.rglob(ext):
                if p.is_file() and p.stat().st_size < 80*1024*1024:
                    rel=p.relative_to(b); d=m/rel; d.parent.mkdir(parents=True, exist_ok=True)
                    try: shutil.copy2(p,d)
                    except Exception: pass

def write(items):
    OUT.mkdir(parents=True, exist_ok=True); (OUT/"data").mkdir(exist_ok=True)
    (OUT/"data/items.json").write_text(json.dumps(items,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (OUT/".nojekyll").write_text("",encoding="utf-8")
    (OUT/"style.css").write_text(r'''
:root{--red:#b5121b;--paper:#fffaf3;--text:#241818}*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--text);background:linear-gradient(135deg,#7e090f,#c91722 42%,#fff 42%,#fff);min-height:100vh}.hero{max-width:1160px;margin:auto;padding:28px 18px 14px;color:#fff}.hero small{opacity:.9}.hero h1{margin:8px 0;font-size:clamp(34px,8vw,74px);letter-spacing:-.06em}.hero p{font-size:18px;max-width:760px}.shell{max-width:1160px;margin:auto;padding:0 16px 54px}.toolbar{position:sticky;top:0;z-index:5;background:rgba(255,250,243,.94);backdrop-filter:blur(12px);border:1px solid rgba(0,0,0,.08);border-radius:24px;padding:14px;display:grid;grid-template-columns:1fr auto;gap:10px;box-shadow:0 16px 44px rgba(0,0,0,.16)}input,button{font:inherit;border-radius:16px;border:1px solid rgba(0,0,0,.14);padding:12px 14px}button{background:var(--red);color:white;font-weight:800;cursor:pointer}.count{margin:14px 4px;color:#fff;font-weight:800}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}.card{background:var(--paper);border-radius:24px;overflow:hidden;box-shadow:0 14px 34px rgba(0,0,0,.16);border:1px solid rgba(0,0,0,.08);display:flex;flex-direction:column;min-height:330px;cursor:pointer}.thumb{height:150px;background:linear-gradient(135deg,#b5121b,#171111);display:grid;place-items:center;color:white;font-size:40px;font-weight:950;letter-spacing:-.05em}.thumb img{width:100%;height:100%;object-fit:cover}.content{padding:16px}.content h2{font-size:20px;margin:0 0 8px}.content p{line-height:1.55;margin:0;color:#4a3838}.meta{margin-top:auto;padding:0 16px 16px;font-size:13px;color:#765}.detail{display:none;background:var(--paper);border-radius:28px;margin-top:18px;padding:clamp(18px,4vw,44px);box-shadow:0 18px 50px rgba(0,0,0,.18)}.detail.active{display:block}.detail h1{font-size:clamp(30px,5vw,56px);line-height:.96;margin:0 0 18px;color:var(--red)}.article{font-size:clamp(18px,2vw,22px);line-height:1.82}.article p{margin:0 0 18px}.article img{max-width:100%;border-radius:22px;box-shadow:0 12px 30px rgba(0,0,0,.18);margin:18px 0 6px}.caption{font-size:14px;color:#765;margin-bottom:18px}.badge{display:inline-block;background:#fff;border:1px solid #eadbd1;border-radius:999px;padding:8px 12px;margin:3px;font-size:13px}.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:16px}.empty{padding:24px;background:var(--paper);border-radius:24px}footer{color:white;text-align:center;padding:30px}@media(max-width:620px){.toolbar{grid-template-columns:1fr}.grid{grid-template-columns:1fr}.card{min-height:unset}}
''',encoding="utf-8")
    (OUT/"app.js").write_text(r'''
let ITEMS=[];const mediaPrefix="media/";const $=s=>document.querySelector(s);const grid=$("#grid"),detail=$("#detail"),search=$("#search");function esc(s){return(s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]))}function mediaPath(p){return mediaPrefix+(p||"").replace(/^.*?assets\//,"").replace(/^app\/src\/main\/assets\//,"").replace(/^\/+/,"")}function ph(){return`<div class="thumb"><span>1966</span></div>`}function thumb(i){const im=(i.images||[])[0];return im?`<div class="thumb"><img loading="lazy" src="${esc(mediaPath(im))}" onerror="this.parentElement.innerHTML='<span>1966</span>'"></div>`:ph()}function card(i){return`<article class="card" onclick="openItem('${esc(i.id)}')">${thumb(i)}<div class="content"><h2>${esc(i.title)}</h2><p>${esc(i.summary)}</p></div><div class="meta">Balkes Arşivi</div></article>`}function renderList(){const q=(search.value||"").toLocaleLowerCase("tr");const arr=ITEMS.filter(x=>(x.title+" "+x.summary+" "+x.text).toLocaleLowerCase("tr").includes(q));detail.classList.remove("active");grid.style.display="grid";grid.innerHTML=arr.length?arr.map(card).join(""):`<div class="empty">Sonuç bulunamadı.</div>`}function pars(t){return(t||"").split(/\n{2,}/).map(p=>p.trim()).filter(Boolean)}function article(i){const imgs=(i.images||[]).slice(0,6);let out="";pars(i.text).forEach((p,n)=>{out+=`<p>${esc(p).replace(/\n/g,"<br>")}</p>`;if(imgs[n])out+=`<img loading="lazy" src="${esc(mediaPath(imgs[n]))}"><div class="caption">Arşiv görseli</div>`});if(!imgs.length)out=`<div class="thumb" style="height:220px;border-radius:22px;margin-bottom:8px"><span>1966</span></div><div class="caption">Temsilidir</div>`+out;return out}function openItem(id){const i=ITEMS.find(x=>x.id===id);if(!i)return;grid.style.display="none";detail.classList.add("active");detail.innerHTML=`<div class="topline"><button onclick="renderList()">← Arşive dön</button><span class="badge">Balkes Arşivi</span></div><h1>${esc(i.title)}</h1><div class="article">${article(i)}</div>`;location.hash=id;scrollTo({top:0,behavior:"smooth"})}async function boot(){ITEMS=await fetch("data/items.json",{cache:"no-store"}).then(r=>r.json());$("#count").textContent=ITEMS.length+" içerik";search.addEventListener("input",renderList);renderList();if(location.hash.length>1)openItem(decodeURIComponent(location.hash.slice(1)))}boot();
''',encoding="utf-8")
    (OUT/"index.html").write_text('''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#b5121b"><title>Balkes Arşivi</title><link rel="stylesheet" href="style.css"></head><body><header class="hero"><small>Sinanjam</small><h1>Balkes Arşivi</h1><p>Kapatılan Balkes Arşivi projesinden kurtarılan verilerle yapılmış Balıkesirspor arşivi.</p></header><main class="shell"><section class="toolbar"><input id="search" placeholder="Arşivde ara..."><button onclick="location.reload()">Yenile</button></section><div class="count" id="count">Yükleniyor...</div><section id="detail" class="detail"></section><section id="grid" class="grid"></section></main><footer>Github, kaynak kodu ve iletişim: https://github.com/Sinanjam/Balkes-Arsivi.git</footer><script src="app.js"></script></body></html>''',encoding="utf-8")

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    items=extract(); copy_media(); write(items)
    print(f"{len(items)} içerik ile site üretildi: {OUT}")
main()
