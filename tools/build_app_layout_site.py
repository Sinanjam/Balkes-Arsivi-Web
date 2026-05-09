#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("mainrepo").resolve()
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path("public").resolve()

ARCHIVE_JSON = ROOT / "app" / "src" / "main" / "assets" / "archive" / "archive_items.json"
ASSETS_ROOT = ROOT / "app" / "src" / "main" / "assets"
RAW_BASE = "https://raw.githubusercontent.com/Sinanjam/Balkes-Arsivi/main/app/src/main/assets/"
MAX_INLINE_TABLES = 8

BAD_CARD_RE = re.compile(
    r"(font-family:|\.slogan|\.nav1|https?://|www\.|web\.archive\.org|balkesarsivi\.com|/user/cimage|user/cimage|cimage/)",
    re.I,
)

def clean_reader_text(s: str) -> str:
    s = str(s or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablolar\s*$", "", s)
    s = re.sub(r"(?im)^\s*#{1,6}\s*Tablo\s+\d+\s*$", "", s)
    s = re.sub(r"(?i)Kayıp\s+Sayfalar\s*:?", "", s)
    s = s.replace("S ampiyon", "Şampiyon")
    s = s.replace("Ş ampiyon", "Şampiyon")
    s = s.replace("Oynadıgımız", "Oynadığımız")
    s = s.replace("Ilk Yarı", "İlk Yarı")
    s = s.replace("Ikinci Yarı", "İkinci Yarı")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def make_snippet(s: str, n: int = 230) -> str:
    s = clean_reader_text(s)
    s = re.sub(r"\s+", " ", s)
    return s[:n].rstrip() + ("…" if len(s) > n else "")

def slugify(text: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    s = (text or "").translate(tr).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90] or "arsiv"

def article_paragraphs(item: dict) -> list[str]:
    content = clean_reader_text(item.get("content", ""))
    title = clean_reader_text(item.get("title", ""))
    paras: list[str] = []

    # Uygulamadaki gibi content metnini okuyucu paragraflarına böl.
    for raw in re.split(r"\n\s*\n", content):
        p = clean_reader_text(raw)
        if not p:
            continue
        if p == title:
            continue
        if re.match(r"^\s*Tablo\s+\d+\s*$", p, re.I):
            continue
        if p.lower() in ("tablolar", "fotoğraflar", "fotograflar"):
            continue
        # Düz tablo satırları metin akışını bozmasın; tablolar aşağıdaki tablo parser'dan gelir.
        if "|" in p and len(p) < 500:
            continue
        paras.append(p)

    if not paras:
        fallback = clean_reader_text(item.get("summary", ""))
        if fallback:
            paras.append(fallback)
    if not paras:
        paras.append("Bu sayfa için okunabilir metin kısa olduğu için içerik arşiv kaydı olarak korunmuştur.")
    return paras

def split_tables(markdown: str) -> list[dict]:
    markdown = clean_reader_text(markdown)
    if not markdown:
        return []
    chunks = []
    current_title = "Tablo"
    current_lines = []
    for line in markdown.splitlines():
        if re.match(r"^\s*Tablo\s+\d+", line, re.I):
            if current_lines:
                chunks.append({"title": current_title, "markdown": "\n".join(current_lines).strip()})
            current_title = line.strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        chunks.append({"title": current_title, "markdown": "\n".join(current_lines).strip()})

    out = []
    for c in chunks:
        if "|" not in c["markdown"]:
            continue
        rows = parse_markdown_table(c["markdown"])
        if not rows:
            continue
        title = extract_table_title(rows) or c["title"]
        out.append({"title": clean_reader_text(title), "rows": rows})
    return out

def parse_markdown_table(md: str) -> list[list[str]]:
    rows = []
    for line in md.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        line = re.sub(r"^\|", "", line)
        line = re.sub(r"\|$", "", line)
        cells = [clean_reader_text(c) for c in line.split("|")]
        if not cells:
            continue
        if all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells):
            continue
        if all(not c for c in cells):
            continue
        rows.append(cells)
    return normalize_rows(rows)

def normalize_rows(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return []
    max_len = max(len(r) for r in rows)
    out = []
    for r in rows:
        rr = list(r) + [""] * (max_len - len(r))
        # Android tarafındaki basit temizlikle uyumlu.
        rr = [clean_reader_text(x) for x in rr]
        if any(rr):
            out.append(rr)
    return out

def extract_table_title(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    first = [c for c in rows[0] if c]
    if len(first) == 1 and len(rows) > 1:
        return first[0]
    if len(first) > 1:
        joined = " ".join(first)
        if "Puan" in joined or "Sezon" in joined or "Yarı" in joined or "Yari" in joined:
            return joined
    return ""

def looks_like_match_table(rows: list[list[str]]) -> bool:
    blob = " ".join(" ".join(r) for r in rows[:8]).lower()
    return ("tarih" in blob and ("ilk yarı" in blob or "ikinci yarı" in blob or "rakip" in blob)) or bool(re.search(r"\d{2}\.\d{2}\.\d{4}", blob))

def looks_like_standing_table(rows: list[list[str]]) -> bool:
    blob = " ".join(" ".join(r) for r in rows[:8]).lower()
    return ("takımlar" in blob or "takimlar" in blob) and (" o " in " " + blob + " " or "puan" in blob or " p " in " " + blob + " ")

def normalize_items(raw_items: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for i, x in enumerate(raw_items, 1):
        title = clean_reader_text(x.get("title", ""))
        summary = clean_reader_text(x.get("summary", ""))
        content = clean_reader_text(x.get("content", ""))

        if not title or BAD_CARD_RE.search(title) or BAD_CARD_RE.search(summary[:250]):
            continue
        if re.search(r"ziyaretçi|ziyaretci|defter", title + " " + summary[:300], re.I):
            continue

        photos = []
        used = set()
        for p in x.get("photos") or []:
            if not isinstance(p, dict):
                continue
            asset = str(p.get("asset") or "").strip()
            if not asset or asset in used:
                continue
            used.add(asset)
            photos.append({
                "asset": asset,
                "caption": clean_reader_text(p.get("caption", "")) or "Arşiv görseli",
            })

        image_asset = str(x.get("imageAsset") or "").strip()
        if image_asset and image_asset not in used:
            photos.insert(0, {
                "asset": image_asset,
                "caption": clean_reader_text(x.get("imageCaption", "")) or "Arşiv görseli",
            })

        tables = split_tables(x.get("tables", ""))
        item_id = slugify(title)
        if item_id in seen:
            item_id = f"{item_id}-{i}"
        seen.add(item_id)

        out.append({
            "id": item_id,
            "season": clean_reader_text(x.get("season", "")),
            "title": title,
            "summary": make_snippet(summary or content, 240),
            "paragraphs": article_paragraphs(x),
            "photos": photos,
            "tables": tables,
            "imageCount": len(photos),
            "tableCount": len(tables),
            "sourceType": clean_reader_text(x.get("sourceType", "")),
        })
    return out

def write_site(items: list[dict]):
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "data" / "items.json").write_text(json.dumps({
        "rawBase": RAW_BASE,
        "maxInlineTables": MAX_INLINE_TABLES,
        "items": items,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    css = """
:root{--bg:#0d0a0b;--panel:#171214;--panel2:#21181b;--page:#191315;--line:#3d262c;--text:#f7f1ef;--muted:#cdbfba;--red:#c8102e;--red2:#8f0b1b;--gold:#f1d3a2}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;min-height:100vh}
body:before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(circle at 15% -10%,rgba(200,16,46,.30),transparent 30rem),linear-gradient(180deg,#17070b,#0d0a0b 38rem)}
.hero{max-width:1180px;margin:auto;padding:42px 18px 24px}.hero h1{font-size:clamp(42px,7vw,82px);letter-spacing:-.06em;line-height:.92;margin:0 0 18px}.hero p{font-size:clamp(18px,2vw,24px);line-height:1.55;color:var(--muted);max-width:820px;margin:0}
.shell{max-width:1180px;margin:0 auto 70px;padding:0 16px}.toolbar{position:sticky;top:8px;z-index:10;background:rgba(23,18,20,.94);border:1px solid var(--line);border-radius:24px;padding:14px;display:grid;grid-template-columns:1fr auto;gap:10px;box-shadow:0 18px 60px rgba(0,0,0,.36);backdrop-filter:blur(14px)}
input,button{font:inherit;border-radius:16px;padding:13px 15px}input{background:#0e0b0c;color:var(--text);border:1px solid #4b3036;outline:none}input::placeholder{color:#8d817e}button{border:1px solid #e0223f;background:linear-gradient(135deg,var(--red),var(--red2));color:white;font-weight:800;cursor:pointer}
.count{margin:18px 4px;color:var(--muted);font-weight:800}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:18px;margin-top:18px}.card{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:24px;overflow:hidden;box-shadow:0 18px 44px rgba(0,0,0,.30);display:flex;flex-direction:column;cursor:pointer;min-height:330px;content-visibility:auto;contain-intrinsic-size:330px}.card:hover{transform:translateY(-2px);transition:.18s ease}
.thumb{height:150px;background:linear-gradient(135deg,#b5121b,#141012);display:grid;place-items:center;color:white;font-size:42px;font-weight:900;letter-spacing:-.05em}.thumb img{width:100%;height:100%;object-fit:cover}.content{padding:18px}.content h2{font-size:22px;line-height:1.2;margin:0 0 10px;color:white}.content p{font-size:16px;line-height:1.65;margin:0;color:var(--muted)}.meta{margin-top:auto;padding:0 18px 18px;color:#a99b97;font-size:13px}
.detail{display:none;margin-top:18px}.detail.active{display:block}.article-page{background:linear-gradient(180deg,#21191c,#171214);border:1px solid var(--line);border-radius:28px;padding:clamp(20px,4vw,48px);box-shadow:0 22px 64px rgba(0,0,0,.38)}.detail h1{font-size:clamp(34px,5vw,62px);line-height:1.02;letter-spacing:-.045em;margin:0 0 18px}.kicker{text-align:center;color:var(--red);font-size:14px;font-weight:900;letter-spacing:.08em;margin:0 0 14px}.badges{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}.badge{background:#2a1e22;border:1px solid #493238;color:#eadbd6;border-radius:999px;padding:8px 12px;font-size:13px}
.article{max-width:920px;font-size:clamp(19px,2vw,23px);line-height:1.82;color:#eee6e2}.para{background:#120e10;border:1px solid rgba(255,255,255,.05);border-radius:18px;padding:16px 17px;margin:0 0 18px}.para.lead{font-size:1.08em;color:white}
.photo-block{margin:20px 0 22px}.photo-block img{width:100%;max-height:560px;object-fit:contain;background:#0b0809;border:1px solid var(--line);border-radius:22px;display:block;box-shadow:0 14px 40px rgba(0,0,0,.35)}.caption{font-size:14px;color:#b9aaa5;margin:8px 2px 0}.placeholder{height:240px;border-radius:22px;background:linear-gradient(135deg,#b5121b,#141012);display:grid;place-items:center;font-size:52px;font-weight:900}
.notice{border:1px dashed #684047;background:#130e10;border-radius:18px;color:#d8cbc7;padding:13px 15px;margin:16px 0}
.table-card{background:#120e10;border:1px solid var(--line);border-radius:22px;padding:14px;margin:20px 0;overflow:auto}.table-card h3{margin:0 0 12px;color:#fff}.table-card table{border-collapse:collapse;min-width:720px;width:100%;font-size:15px}.table-card th,.table-card td{border:1px solid #493238;padding:9px 10px;text-align:left}.table-card th{background:#2b1a1f;color:#fff}.table-card tr:nth-child(even) td{background:#1a1315}
.match-grid,.standing-grid{display:grid;gap:10px}.match-card,.standing-card{border:1px solid #493238;background:#171113;border-radius:16px;padding:12px}.match-card .score{font-size:24px;font-weight:900;color:#fff}.standing-card b{font-size:18px;color:#fff}.small{font-size:13px;color:#b9aaa5}.empty{padding:24px;border:1px solid var(--line);background:var(--panel);border-radius:24px}.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:20px}footer{color:#a99b97;text-align:center;padding:34px}
@media(max-width:720px){.toolbar{grid-template-columns:1fr;top:0;border-radius:0 0 22px 22px;margin-left:-16px;margin-right:-16px}.grid{grid-template-columns:1fr}.card{min-height:unset}.table-card table{font-size:14px;min-width:640px}.article-page{border-radius:20px;padding:18px}.para{padding:14px}}
"""
    (OUT / "style.css").write_text(css, encoding="utf-8")

    js = r"""
let DATA=null,ITEMS=[],RAW="",MAXT=8;
const $=s=>document.querySelector(s); const grid=$("#grid"), detail=$("#detail"), search=$("#search");
const esc=s=>(s||"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[m]));
function encAsset(p){return RAW + String(p||"").split("/").map(encodeURIComponent).join("/")}
function ph(){return `<div class="thumb"><span>1966</span></div>`}
function cardThumb(it){let p=(it.photos&&it.photos[0]&&it.photos[0].asset)||"";return p?`<div class="thumb"><img loading="lazy" decoding="async" src="${esc(encAsset(p))}" onerror="this.parentElement.innerHTML='<span>1966</span>'"></div>`:ph()}
function card(it){return `<article class="card" onclick="openItem('${esc(it.id)}')">${cardThumb(it)}<div class="content"><h2>${esc(it.title)}</h2><p>${esc(it.summary)}</p></div><div class="meta">${esc(it.season||"Balkes Arşivi")} · ${it.imageCount||0} foto · ${it.tableCount||0} tablo</div></article>`}
function renderList(){let q=(search.value||"").toLocaleLowerCase("tr");let arr=ITEMS.filter(x=>(x.title+" "+x.summary+" "+(x.paragraphs||[]).join(" ")).toLocaleLowerCase("tr").includes(q));detail.classList.remove("active");grid.style.display="grid";grid.innerHTML=arr.length?arr.map(card).join(""):`<div class="empty">Sonuç bulunamadı.</div>`}
function photoBlock(it,index,total){let p=it.photos[index];if(!p)return"";return `<figure class="photo-block"><img loading="lazy" decoding="async" src="${esc(encAsset(p.asset))}" alt="${esc(p.caption||it.title)}"><figcaption class="caption">Fotoğraf ${index+1}/${total}${p.caption?` · ${esc(p.caption)}`:""}</figcaption></figure>`}
function generatedBlock(it){return `<div class="photo-block"><div class="placeholder">1966</div><div class="caption">Temsilidir</div></div>`}
function tableHtml(rows){if(!rows||!rows.length)return"";let head=rows[0],body=rows.slice(1);return `<table><thead><tr>${head.map(c=>`<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${body.map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function looksMatch(rows){let blob=(rows||[]).slice(0,8).flat().join(" ").toLocaleLowerCase("tr");return blob.includes("tarih")||/\d{2}\.\d{2}\.\d{4}/.test(blob)}
function looksStanding(rows){let blob=(rows||[]).slice(0,8).flat().join(" ").toLocaleLowerCase("tr");return blob.includes("takımlar")||blob.includes("takimlar")||blob.includes("puan durumu")}
function matchCards(rows){let out=`<div class="match-grid">`;for(let i=1;i<Math.min(rows.length,80);i++){let r=rows[i];let joined=r.filter(Boolean).join(" ");if(!joined)continue;out+=`<div class="match-card"><div class="small">${esc(r[0]||"")}</div><div class="score">${esc(r.slice(1).filter(Boolean).join(" · "))}</div></div>`}return out+`</div>`}
function standingCards(rows){let out=`<div class="standing-grid">`;for(let i=1;i<Math.min(rows.length,80);i++){let r=rows[i];if(!r.some(Boolean))continue;out+=`<div class="standing-card"><b>${esc((r[0]?r[0]+". ":"")+(r[1]||r[0]||""))}</b><div class="small">${esc(r.slice(2).filter(Boolean).join(" · "))}</div></div>`}return out+`</div>`}
function tableBlock(t){let rows=t.rows||[];let body=looksMatch(rows)?matchCards(rows):(looksStanding(rows)?standingCards(rows):tableHtml(rows));return `<section class="table-card"><h3>${esc(t.title||"Tablo")}</h3>${body}</section>`}
function appArticleFlow(it){
  let ps=it.paragraphs||[], tables=it.tables||[], maxTables=Math.min(tables.length,MAXT);
  let photoCount=(it.photos||[]).length;
  let photoLimit=Math.min(photoCount,Math.max(1,Math.min(8,Math.max(1,Math.floor(ps.length/2)+1))));
  let photoIndex=0, tableIndex=0, generatedShown=false, out="";
  if(!ps.length)ps=["Bu sayfa için okunabilir metin kısa olduğu için içerik arşiv kaydı olarak korunmuştur."];
  for(let i=0;i<ps.length;i++){
    out+=`<p class="para ${i===0?"lead":""}">${esc(ps[i]).replace(/\n/g,"<br>")}</p>`;
    if(i===0){
      if(photoCount>0 && photoIndex<photoLimit){out+=photoBlock(it,photoIndex,photoCount);photoIndex++}
      else if(photoCount===0){out+=generatedBlock(it);generatedShown=true}
    }
    if(i===1 && tableIndex<maxTables){out+=tableBlock(tables[tableIndex]);tableIndex++}
    if(i>1 && photoIndex<photoLimit && ((i+1)%3===0)){out+=photoBlock(it,photoIndex,photoCount);photoIndex++}
    if(i>2 && tableIndex<maxTables && ((i+1)%4===0)){out+=tableBlock(tables[tableIndex]);tableIndex++}
  }
  if(photoCount===0 && !generatedShown) out+=generatedBlock(it);
  else if(photoCount>0){
    while(photoIndex<photoLimit){out+=photoBlock(it,photoIndex,photoCount);photoIndex++}
    if(photoCount>photoLimit) out+=`<div class="notice">${photoCount-photoLimit} fotoğraf daha var. İlk ${photoLimit} fotoğraf uygulamadaki akışa uygun şekilde metin arasına yerleştirildi.</div>`;
  }
  while(tableIndex<maxTables){out+=tableBlock(tables[tableIndex]);tableIndex++}
  if(tables.length>maxTables) out+=`<div class="notice">${tables.length-maxTables} tablo daha var. Ağır sayfalarda uygulamadaki gibi ilk tablolar akışta gösterilir.</div>`;
  return out;
}
function openItem(id){let it=ITEMS.find(x=>x.id===id);if(!it)return;grid.style.display="none";detail.classList.add("active");detail.innerHTML=`<div class="topline"><button onclick="renderList()">← Arşive dön</button><span class="badge">${esc(it.season||"Balkes Arşivi")}</span><span class="badge">${it.imageCount||0} foto</span><span class="badge">${it.tableCount||0} tablo</span></div><article class="article-page"><div class="kicker">${esc(it.season?("Balkes Arşivi • "+it.season):"Balkes Arşivi")}</div><h1>${esc(it.title)}</h1><div class="article">${appArticleFlow(it)}</div></article>`;location.hash=id;scrollTo({top:0,behavior:"smooth"})}
async function boot(){DATA=await fetch("data/items.json",{cache:"no-store"}).then(r=>r.json());RAW=DATA.rawBase;MAXT=DATA.maxInlineTables||8;ITEMS=DATA.items||[];$("#count").textContent=ITEMS.length+" içerik";search.addEventListener("input",renderList);renderList();if(location.hash.length>1){openItem(decodeURIComponent(location.hash.slice(1)))}}
boot();
"""
    (OUT / "app.js").write_text(js, encoding="utf-8")

    html = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0d0a0b"><title>Balkes Arşivi</title><link rel="stylesheet" href="style.css"></head><body><header class="hero"><h1>Balkes Arşivi</h1><p>Kapatılan Balkes Arşivi projesinden kurtarılan verilerle yapılmış Balıkesirspor arşivi.</p></header><main class="shell"><section class="toolbar"><input id="search" placeholder="Arşivde ara..."><button onclick="location.reload()">Yenile</button></section><div class="count" id="count">Yükleniyor...</div><section id="detail" class="detail"></section><section id="grid" class="grid"></section></main><footer>Balkes Arşivi</footer><script src="app.js"></script></body></html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")

def main():
    if not ARCHIVE_JSON.exists():
        print(f"HATA: archive_items.json bulunamadı: {ARCHIVE_JSON}")
        sys.exit(1)
    data = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    items = normalize_items(data.get("items", []))
    if not items:
        print("HATA: hiç içerik üretilemedi")
        sys.exit(1)
    photo_count = sum(len(x.get("photos", [])) for x in items)
    table_count = sum(len(x.get("tables", [])) for x in items)
    if photo_count == 0:
        print("HATA: fotoğraf bulunamadı; web sitesi uygulama verisini okuyamıyor")
        sys.exit(1)
    write_site(items)
    print(f"FAST site üretildi: {len(items)} içerik, {photo_count} foto referansı, {table_count} tablo")
    print("Not: Görseller web repo içine kopyalanmadı; ana repodan lazy/raw yüklenir.")

if __name__ == "__main__":
    main()
