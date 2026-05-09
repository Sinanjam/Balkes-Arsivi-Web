#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from html import escape

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("mainrepo").resolve()
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("public").resolve()

ARCHIVE_JSON = ROOT / "app" / "src" / "main" / "assets" / "archive" / "archive_items.json"
ASSETS_ROOT = ROOT / "app" / "src" / "main" / "assets"

BAD_CARD_RE = re.compile(r"(font-family:|\.slogan|\.nav1|https?://|www\.|web\.archive\.org|balkesarsivi\.com|/user/cimage|user/cimage|cimage/)", re.I)

def slugify(text: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = (text or "").translate(tr).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or "arsiv"

def clean_text(s: str) -> str:
    s = str(s or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablolar\s*$", "", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablo\s+\d+\s*$", "", s)
    s = re.sub(r"(?i)Kayıp\s+Sayfalar\s*:?", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def strip_table_blocks_from_content(content: str) -> str:
    lines = clean_text(content).splitlines()
    out = []
    in_table = False
    for line in lines:
        l = line.strip()
        if re.match(r"^(Tablo\s+\d+|.*Puan Durumu|.*Oynadığımız Maçlar|.*Oynadigimiz Maclar)", l, re.I):
            in_table = True
            continue
        if in_table:
            # tablo satırları bitince, foto açıklaması / normal metin tekrar başlıyor olabilir
            if not l:
                continue
            if "|" in l or re.fullmatch(r"[-:| ]+", l) or re.fullmatch(r"\d+", l) or re.match(r"^\d{2}\.\d{2}\.\d{4}", l):
                continue
            if len(l) < 45 and re.match(r"^(Sıra|Takımlar|Tarih|Ilk|İlk|Ikinci|İkinci|O|G|B|M|A|Y|P)$", l, re.I):
                continue
            in_table = False
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def split_tables(tables: str) -> list[dict]:
    tables = clean_text(tables)
    if not tables:
        return []
    chunks = []
    current_title = "Tablo"
    current_lines = []
    for line in tables.splitlines():
        if re.match(r"^\s*Tablo\s+\d+", line, re.I):
            if current_lines:
                chunks.append({"title": current_title, "markdown": "\n".join(current_lines).strip()})
            current_title = line.strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        chunks.append({"title": current_title, "markdown": "\n".join(current_lines).strip()})
    return [c for c in chunks if "|" in c["markdown"]]

def normalize_items(raw_items: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for i, x in enumerate(raw_items, 1):
        title = clean_text(x.get("title", ""))
        summary = clean_text(x.get("summary", ""))
        content = clean_text(x.get("content", ""))
        if not title or BAD_CARD_RE.search(title) or BAD_CARD_RE.search(summary[:250]):
            continue
        if re.search(r"ziyaretçi|ziyaretci|defter", title + " " + summary[:300], re.I):
            continue

        photos = []
        image_asset = x.get("imageAsset") or ""
        if image_asset:
            photos.append({
                "asset": image_asset,
                "caption": clean_text(x.get("imageCaption", "")) or "Arşiv görseli"
            })
        for p in x.get("photos") or []:
            if isinstance(p, dict) and p.get("asset"):
                asset = str(p.get("asset"))
                if asset not in [q["asset"] for q in photos]:
                    photos.append({
                        "asset": asset,
                        "caption": clean_text(p.get("caption", "")) or "Arşiv görseli"
                    })

        clean_content = strip_table_blocks_from_content(content)
        item = {
            "id": slugify(title),
            "season": x.get("season", ""),
            "title": title,
            "summary": summary or clean_content[:260],
            "content": clean_content,
            "sourceUrl": x.get("sourceUrl", ""),
            "imageAsset": image_asset,
            "photos": photos,
            "tables": split_tables(x.get("tables", "")),
            "tableCount": x.get("tableCount", 0),
            "imageCount": len(photos),
        }
        if item["id"] in seen:
            item["id"] = f"{item['id']}-{i}"
        seen.add(item["id"])
        out.append(item)
    return out

def copy_assets():
    dest = OUT / "assets"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if ASSETS_ROOT.exists():
        shutil.copytree(ASSETS_ROOT, dest, dirs_exist_ok=True)

def write_files(items: list[dict]):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "data" / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    css = """
:root{--bg:#0d0a0b;--panel:#171214;--panel2:#21181b;--line:#3d262c;--text:#f7f1ef;--muted:#cdbfba;--red:#c8102e;--red2:#8f0b1b;--gold:#f1d3a2}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;min-height:100vh}
body:before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(circle at 15% -10%,rgba(200,16,46,.30),transparent 30rem),linear-gradient(180deg,#17070b,#0d0a0b 38rem)}
.hero{max-width:1180px;margin:auto;padding:42px 18px 24px}.hero h1{font-size:clamp(42px,7vw,82px);letter-spacing:-.06em;line-height:.92;margin:0 0 18px}.hero p{font-size:clamp(18px,2vw,24px);line-height:1.55;color:var(--muted);max-width:820px;margin:0}
.shell{max-width:1180px;margin:0 auto 70px;padding:0 16px}.toolbar{position:sticky;top:8px;z-index:10;background:rgba(23,18,20,.94);border:1px solid var(--line);border-radius:24px;padding:14px;display:grid;grid-template-columns:1fr auto;gap:10px;box-shadow:0 18px 60px rgba(0,0,0,.36);backdrop-filter:blur(14px)}
input,button{font:inherit;border-radius:16px;padding:13px 15px}input{background:#0e0b0c;color:var(--text);border:1px solid #4b3036;outline:none}input::placeholder{color:#8d817e}button{border:1px solid #e0223f;background:linear-gradient(135deg,var(--red),var(--red2));color:white;font-weight:800;cursor:pointer}
.count{margin:18px 4px;color:var(--muted);font-weight:800}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:18px;margin-top:18px}.card{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:24px;overflow:hidden;box-shadow:0 18px 44px rgba(0,0,0,.30);display:flex;flex-direction:column;cursor:pointer;min-height:370px}.card:hover{transform:translateY(-2px);transition:.18s ease}
.thumb{height:168px;background:linear-gradient(135deg,#b5121b,#141012);display:grid;place-items:center;color:white;font-size:42px;font-weight:900;letter-spacing:-.05em}.thumb img{width:100%;height:100%;object-fit:cover}.content{padding:18px}.content h2{font-size:22px;line-height:1.2;margin:0 0 10px;color:white}.content p{font-size:16px;line-height:1.65;margin:0;color:var(--muted)}.meta{margin-top:auto;padding:0 18px 18px;color:#a99b97;font-size:13px}
.detail{display:none;background:linear-gradient(180deg,#21191c,#171214);border:1px solid var(--line);border-radius:28px;margin-top:18px;padding:clamp(20px,4vw,48px);box-shadow:0 22px 64px rgba(0,0,0,.38)}.detail.active{display:block}.detail h1{font-size:clamp(34px,5vw,62px);line-height:1.02;letter-spacing:-.045em;margin:0 0 18px}.badges{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}.badge{background:#2a1e22;border:1px solid #493238;color:#eadbd6;border-radius:999px;padding:8px 12px;font-size:13px}
.article{max-width:920px;font-size:clamp(19px,2vw,23px);line-height:1.85;color:#eee6e2}.article p{margin:0 0 22px}.lead-img{width:100%;max-height:540px;object-fit:cover;border-radius:24px;box-shadow:0 14px 40px rgba(0,0,0,.35);margin:4px 0 10px}.caption{font-size:14px;color:#b9aaa5;margin:0 0 24px}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px;margin:26px 0}.gallery figure{margin:0;background:#120e10;border:1px solid var(--line);border-radius:18px;overflow:hidden}.gallery img{width:100%;height:170px;object-fit:cover;display:block}.gallery figcaption{font-size:12px;color:#c8b9b5;padding:9px;line-height:1.4}
.table-section{margin:34px 0}.table-card{background:#120e10;border:1px solid var(--line);border-radius:22px;padding:14px;margin:16px 0;overflow:auto}.table-card h3{margin:0 0 12px;color:#fff}.table-card table{border-collapse:collapse;min-width:720px;width:100%;font-size:15px}.table-card th,.table-card td{border:1px solid #493238;padding:9px 10px;text-align:left}.table-card th{background:#2b1a1f;color:#fff}.table-card tr:nth-child(even) td{background:#1a1315}.empty{padding:24px;border:1px solid var(--line);background:var(--panel);border-radius:24px}.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:20px}footer{color:#a99b97;text-align:center;padding:34px}
@media(max-width:720px){.toolbar{grid-template-columns:1fr;top:0;border-radius:0 0 22px 22px;margin-left:-16px;margin-right:-16px}.grid{grid-template-columns:1fr}.card{min-height:unset}.gallery{grid-template-columns:repeat(2,1fr)}}
"""
    (OUT / "style.css").write_text(css, encoding="utf-8")

    js = r"""
let ITEMS=[]; const $=s=>document.querySelector(s); const grid=$("#grid"), detail=$("#detail"), search=$("#search");
const esc=s=>(s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]));
const asset=p=>p?("assets/"+String(p).replace(/^\/+/,"")):"";
function ph(){return `<div class="thumb"><span>1966</span></div>`}
function thumb(it){let p=it.imageAsset||(it.photos&&it.photos[0]&&it.photos[0].asset);return p?`<div class="thumb"><img loading="lazy" src="${esc(asset(p))}" onerror="this.parentElement.innerHTML='<span>1966</span>'"></div>`:ph()}
function card(it){return `<article class="card" onclick="openItem('${esc(it.id)}')">${thumb(it)}<div class="content"><h2>${esc(it.title)}</h2><p>${esc(it.summary)}</p></div><div class="meta">${esc(it.season||"Balkes Arşivi")} · ${it.imageCount||0} foto · ${it.tables?.length||0} tablo</div></article>`}
function renderList(){let q=(search.value||"").toLocaleLowerCase("tr");let arr=ITEMS.filter(x=>(x.title+" "+x.summary+" "+x.content).toLocaleLowerCase("tr").includes(q));detail.classList.remove("active");grid.style.display="grid";grid.innerHTML=arr.length?arr.map(card).join(""):`<div class="empty">Sonuç bulunamadı.</div>`}
function mdTable(md){let lines=(md||"").split(/\n/).filter(l=>l.includes("|")); if(!lines.length)return""; let rows=lines.map(l=>l.trim().replace(/^\||\|$/g,"").split("|").map(c=>c.trim())); rows=rows.filter(r=>!r.every(c=>/^:?-{3,}:?$/.test(c)||c==="")); if(!rows.length)return""; let head=rows[0], body=rows.slice(1); return `<table><thead><tr>${head.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${body.map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function article(it){let parts=(it.content||"").split(/\n{2,}/).map(x=>x.trim()).filter(Boolean);return parts.map(p=>`<p>${esc(p).replace(/\n/g,"<br>")}</p>`).join("")}
function gallery(it){let ps=(it.photos||[]).slice(0,80); if(!ps.length)return`<div class="thumb" style="height:220px;border-radius:22px;margin-bottom:10px"><span>1966</span></div><div class="caption">Temsilidir</div>`; let lead=ps[0]; let rest=ps.slice(1); return `<img class="lead-img" src="${esc(asset(lead.asset))}"><div class="caption">${esc(lead.caption||"Arşiv görseli")}</div>${rest.length?`<section class="gallery">${rest.map(p=>`<figure><img loading="lazy" src="${esc(asset(p.asset))}"><figcaption>${esc(p.caption||"Arşiv görseli")}</figcaption></figure>`).join("")}</section>`:""}`}
function tables(it){let ts=it.tables||[]; if(!ts.length)return""; return `<section class="table-section"><h2>Tablolar</h2>${ts.map(t=>`<div class="table-card"><h3>${esc(t.title||"Tablo")}</h3>${mdTable(t.markdown)}</div>`).join("")}</section>`}
function openItem(id){let it=ITEMS.find(x=>x.id===id);if(!it)return;grid.style.display="none";detail.classList.add("active");detail.innerHTML=`<div class="topline"><button onclick="renderList()">← Arşive dön</button><span class="badge">${esc(it.season||"Balkes Arşivi")}</span><span class="badge">${it.imageCount||0} foto</span><span class="badge">${it.tables?.length||0} tablo</span></div><h1>${esc(it.title)}</h1><div class="article">${article(it)}</div>${gallery(it)}${tables(it)}`;location.hash=id;scrollTo({top:0,behavior:"smooth"})}
async function boot(){ITEMS=await fetch("data/items.json",{cache:"no-store"}).then(r=>r.json());$("#count").textContent=ITEMS.length+" içerik";search.addEventListener("input",renderList);renderList();if(location.hash.length>1){openItem(decodeURIComponent(location.hash.slice(1)))}}
boot();
"""
    (OUT / "app.js").write_text(js, encoding="utf-8")

    html = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0d0a0b"><title>Balkes Arşivi</title><link rel="stylesheet" href="style.css"></head><body><header class="hero"><h1>Balkes Arşivi</h1><p>Kapatılan Balkes Arşivi projesinden kurtarılan verilerle yapılmış Balıkesirspor arşivi.</p></header><main class="shell"><section class="toolbar"><input id="search" placeholder="Arşivde ara..."><button onclick="location.reload()">Yenile</button></section><div class="count" id="count">Yükleniyor...</div><section id="detail" class="detail"></section><section id="grid" class="grid"></section></main><footer>Balkes Arşivi</footer><script src="app.js"></script></body></html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")

def main():
    if not ARCHIVE_JSON.exists():
        print(f"HATA: archive_items.json bulunamadı: {ARCHIVE_JSON}")
        sys.exit(1)
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    items = normalize_items(data.get("items", []))
    copy_assets()
    write_files(items)

    if not items:
        print("HATA: hiç içerik üretilemedi")
        sys.exit(1)
    photo_count = sum(len(x.get("photos", [])) for x in items)
    table_count = sum(len(x.get("tables", [])) for x in items)
    bad = [x for x in items if BAD_CARD_RE.search(x["title"]) or BAD_CARD_RE.search(x["summary"])]
    print(f"Site üretildi: {len(items)} içerik, {photo_count} foto, {table_count} tablo")
    if photo_count == 0:
        print("HATA: fotoğraf bulunamadı; asset yolu/JSON yapısı yanlış")
        sys.exit(1)
    if bad:
        print("HATA: bozuk kart kaldı:")
        for x in bad[:20]:
            print("-", x["title"])
        sys.exit(1)

if __name__ == "__main__":
    main()
