#!/usr/bin/env python3
from __future__ import annotations
import csv, html, json, re, shutil, sys
from pathlib import Path
from typing import Any

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path('mainrepo').resolve()
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path('public').resolve()
ASSETS = ROOT / 'app' / 'src' / 'main' / 'assets'
ARCHIVE_JSON = ASSETS / 'archive' / 'archive_items.json'
MEDIA_ROOT = ASSETS

URL_RE = re.compile(r'https?://\S+|www\.\S+', re.I)
CSS_RE = re.compile(r'(font-family|font-size|font-weight|text-decoration|\.nav|\.slogan|\{\s*font|</?style|<script|background\s*:|color\s*:)', re.I)
BAD_TITLE_RE = re.compile(r'(https?://|www\.|web\.archive\.org|balkesarsivi\.com|/user/cimage|user/cimage|cimage/|\.(gif|jpg|jpeg|png|webp)(\s|$|/|\?|-))', re.I)
IMG_EXT = re.compile(r'\.(png|jpe?g|webp|gif)$', re.I)

def clean_text(x: Any) -> str:
    s = '' if x is None else str(x)
    s = html.unescape(s)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'(?im)^\s*#{1,6}\s*Tablolar\s*$', '', s)
    s = re.sub(r'(?im)^\s*#{1,6}\s*Tablo\s+\d+\s*$', '', s)
    s = re.sub(r'(?i)Kayıp\s+Sayfalar\s*:?', '', s)
    # CSS/html noise satırlarını at
    lines=[]
    for line in s.split('\n'):
        t=line.strip()
        if not t: 
            lines.append('')
            continue
        if CSS_RE.search(t):
            continue
        # Tek başına URL/görsel satırını at.
        if URL_RE.fullmatch(t) or (BAD_TITLE_RE.search(t) and len(re.findall(r'[A-Za-zÇĞİÖŞÜçğıöşü]{3,}', t)) < 8):
            continue
        lines.append(t)
    s='\n'.join(lines)
    s = URL_RE.sub('', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

def word_count(s: str) -> int:
    return len(re.findall(r'[A-Za-zÇĞİÖŞÜçğıöşü]{3,}', s or ''))

def slugify(s: str, fallback: str) -> str:
    tr=str.maketrans('çğıöşüÇĞİÖŞÜ','cgiosuCGIOSU')
    s=(s or '').translate(tr).lower()
    s=re.sub(r'[^a-z0-9]+','-',s).strip('-')[:80]
    if not s or BAD_TITLE_RE.search(s): return fallback
    return s

def rel_asset(path: str) -> str:
    p=(path or '').strip().lstrip('/')
    p=re.sub(r'^app/src/main/assets/','',p)
    return p

def read_items() -> list[dict[str,Any]]:
    if not ARCHIVE_JSON.exists():
        raise SystemExit(f'archive_items.json bulunamadı: {ARCHIVE_JSON}')
    raw=json.loads(ARCHIVE_JSON.read_text(encoding='utf-8'))
    arr=raw.get('items') if isinstance(raw, dict) else raw
    if not isinstance(arr, list):
        raise SystemExit('archive_items.json içinde items listesi yok')
    out=[]
    seen=set()
    for idx, item in enumerate(arr,1):
        if not isinstance(item, dict): continue
        title=clean_text(item.get('title') or item.get('name') or f'Balkes Arşivi {idx}')
        content=clean_text(item.get('content') or item.get('text') or item.get('summary') or '')
        summary=clean_text(item.get('summary') or content[:260])
        if BAD_TITLE_RE.search(title) or word_count(title) < 1: continue
        if CSS_RE.search(title) or CSS_RE.search(summary): continue
        if re.search(r'ziyaretçi|ziyaretci|defter', title+' '+content[:200], re.I): continue
        if word_count(content) < 8 and not item.get('photos') and not item.get('tables'): continue
        iid=slugify(item.get('id') or title, f'arsiv-{idx}')
        if iid in seen: iid=f'{iid}-{idx}'
        seen.add(iid)
        photos=[]
        for p in item.get('photos') or []:
            if isinstance(p, dict):
                asset=rel_asset(p.get('asset') or '')
                cap=clean_text(p.get('caption') or '')
            else:
                asset=rel_asset(str(p)); cap=''
            if asset and IMG_EXT.search(asset):
                photos.append({'asset': asset, 'caption': cap[:220]})
        cover=rel_asset(item.get('imageAsset') or '')
        if cover and IMG_EXT.search(cover) and not any(p['asset']==cover for p in photos):
            photos.insert(0, {'asset': cover, 'caption': clean_text(item.get('imageCaption') or '')[:220]})
        tables=clean_tables(item.get('tables') or '')
        out.append({
            'id': iid,
            'season': clean_text(item.get('season') or ''),
            'title': title,
            'summary': summary[:320] + ('…' if len(summary) > 320 else ''),
            'content': content,
            'sourceUrl': item.get('sourceUrl') or '',
            'sourceType': clean_text(item.get('sourceType') or ''),
            'photos': photos,
            'tables': tables,
            'imageCount': len(photos),
            'tableCount': len(tables),
        })
    return out

def clean_tables(raw: str) -> list[dict[str,Any]]:
    raw = str(raw or '').strip()
    if not raw: return []
    sections=[]
    # Tablo N ayraçlarına böl, başlığı koru.
    parts=re.split(r'(?im)^\s*Tablo\s+(\d+)\s*$', raw)
    if len(parts) > 1:
        it=iter(parts)
        prefix=next(it,'')
        for no, body in zip(it,it):
            sec=parse_markdown_table(body, f'Tablo {no}')
            if sec: sections.append(sec)
    else:
        sec=parse_markdown_table(raw, 'Tablo')
        if sec: sections.append(sec)
    return sections

def parse_markdown_table(text: str, fallback_title: str) -> dict[str,Any]|None:
    lines=[l.strip() for l in str(text).splitlines() if l.strip()]
    title=fallback_title
    table_lines=[]
    for l in lines:
        if l.startswith('|') and l.endswith('|'):
            table_lines.append(l)
        elif not table_lines and not re.match(r'^[-| :]+$', l):
            t=clean_text(l)
            if t and not t.lower().startswith('tablo'):
                title=t[:120]
    rows=[]
    for l in table_lines:
        cells=[clean_text(c) for c in l.strip('|').split('|')]
        if not any(cells): continue
        # separator satırı
        if all(re.fullmatch(r'[-: ]*', c or '') for c in cells):
            continue
        rows.append(cells)
    if len(rows) < 2: return None
    maxlen=max(len(r) for r in rows)
    rows=[r+['']*(maxlen-len(r)) for r in rows]
    # Çok boş kolonları at
    keep=[]
    for ci in range(maxlen):
        non=sum(1 for r in rows if r[ci].strip())
        if non >= 2:
            keep.append(ci)
    rows=[[r[i] for i in keep] for r in rows] if keep else rows
    if len(rows) < 2: return None
    return {'title': title, 'headers': rows[0], 'rows': rows[1:120]}

def copy_media():
    media_src=ASSETS / 'archive_data' / 'media'
    media_dst=OUT / 'media' / 'archive_data' / 'media'
    if media_src.exists():
        shutil.copytree(media_src, media_dst, dirs_exist_ok=True)
    # temsili görseller vb diğer assets resimleri
    for sub in ['images','archive']:
        src=ASSETS/sub
        if src.exists():
            shutil.copytree(src, OUT/'media'/sub, dirs_exist_ok=True)

def write_files(items):
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    (OUT/'data').mkdir()
    (OUT/'data/items.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    copy_media()
    (OUT/'.nojekyll').write_text('', encoding='utf-8')
    (OUT/'index.html').write_text(INDEX, encoding='utf-8')
    (OUT/'style.css').write_text(STYLE, encoding='utf-8')
    (OUT/'app.js').write_text(APPJS, encoding='utf-8')

INDEX = '''<!doctype html>
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
    <div class="hero-inner">
      <h1>Balkes Arşivi</h1>
      <p>Kapatılan Balkes Arşivi projesinden kurtarılan verilerle yapılmış Balıkesirspor arşivi.</p>
    </div>
  </header>
  <main class="shell">
    <section class="toolbar">
      <input id="search" placeholder="Arşivde ara..." autocomplete="off">
      <button id="clearBtn" type="button">Temizle</button>
    </section>
    <div class="count" id="count">Yükleniyor...</div>
    <section id="detail" class="detail"></section>
    <section id="grid" class="grid"></section>
  </main>
  <footer>Balkes Arşivi</footer>
  <script src="app.js"></script>
</body>
</html>
'''

STYLE = r'''
:root{--bg:#0f0b0c;--panel:#1a1416;--panel2:#241a1e;--line:#3a252b;--text:#f5f1ef;--muted:#cfc4c0;--red:#c8102e;--red2:#8f0b1b;--paper:#fff7ef;--paperText:#211719}
*{box-sizing:border-box} html{scroll-behavior:smooth} body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh} body:before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(circle at 10% 0%,rgba(200,16,46,.26),transparent 30rem),linear-gradient(180deg,#170b0f,#0f0b0c 34rem)}
.hero{padding:44px 18px 24px}.hero-inner{max-width:1160px;margin:auto}.hero h1{font-size:clamp(42px,8vw,88px);line-height:.95;letter-spacing:-.055em;margin:0 0 18px}.hero p{font-size:clamp(18px,2.2vw,26px);line-height:1.55;max-width:820px;color:var(--muted);margin:0}.shell{max-width:1160px;margin:0 auto 70px;padding:0 16px}.toolbar{position:sticky;top:8px;z-index:10;background:rgba(26,20,22,.94);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:24px;padding:14px;display:grid;gap:10px;grid-template-columns:1fr auto;box-shadow:0 18px 50px rgba(0,0,0,.32)}input,button{font:inherit;border-radius:16px;padding:13px 15px}input{background:#100d0e;border:1px solid #4a3439;color:var(--text);outline:none}input::placeholder{color:#8f8582}button{border:1px solid #d81a39;background:linear-gradient(135deg,var(--red),var(--red2));color:white;font-weight:800;cursor:pointer}.count{margin:18px 4px;color:var(--muted);font-weight:800}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:18px;margin-top:18px}.card{background:linear-gradient(180deg,var(--panel2),var(--panel));border-radius:24px;overflow:hidden;box-shadow:0 18px 44px rgba(0,0,0,.28);border:1px solid var(--line);display:flex;flex-direction:column;min-height:380px;cursor:pointer}.card:hover{transform:translateY(-2px);transition:.18s ease}.thumb{height:170px;background:linear-gradient(135deg,#b5121b,#141012);display:grid;place-items:center;color:white;font-size:44px;font-weight:900;letter-spacing:-.05em}.thumb img{width:100%;height:100%;object-fit:cover}.content{padding:18px}.content h2{font-size:22px;line-height:1.2;margin:0 0 10px;color:#fff;word-break:break-word}.content p{font-size:16px;line-height:1.65;margin:0;color:var(--muted);word-break:break-word}.meta{margin-top:auto;padding:0 18px 18px;font-size:13px;color:#aa9d99}.empty{padding:26px;background:var(--panel);border-radius:24px;margin-top:18px;border:1px solid var(--line)}.detail{display:none;background:linear-gradient(180deg,#21191c,#171214);border:1px solid var(--line);border-radius:28px;margin-top:18px;padding:clamp(20px,4vw,50px);box-shadow:0 22px 60px rgba(0,0,0,.36)}.detail.active{display:block}.detail h1{font-size:clamp(34px,5vw,62px);line-height:1.02;margin:0 0 14px;color:#fff;letter-spacing:-.04em}.submeta{color:#b9aaa5;margin:0 0 26px;font-weight:700}.article{max-width:920px;font-size:clamp(19px,2vw,23px);line-height:1.82;color:#eee6e2;word-break:break-word}.article p{margin:0 0 22px}.hero-photo{max-width:100%;border-radius:24px;box-shadow:0 16px 40px rgba(0,0,0,.36);margin:8px 0 24px}.caption{font-size:14px;color:#b9aaa5;margin:-12px 0 22px}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin:28px 0}.gallery figure{margin:0;background:#130f10;border:1px solid var(--line);border-radius:18px;overflow:hidden}.gallery img{width:100%;height:160px;object-fit:cover;display:block}.gallery figcaption{font-size:12px;color:#b9aaa5;padding:8px;line-height:1.35}.tableWrap{margin:28px 0;background:#130f10;border:1px solid var(--line);border-radius:20px;overflow:hidden}.tableWrap h3{margin:0;padding:14px 16px;background:#2a1e22;color:#fff}.tableScroll{overflow:auto}table{width:100%;border-collapse:collapse;min-width:620px}th,td{padding:10px 12px;border-bottom:1px solid #3a252b;text-align:left}th{background:#1d1518;color:#fff;position:sticky;top:0}td{color:#eee6e2}.badge{display:inline-block;background:#2a1e22;border:1px solid #493238;color:#e9dad6;border-radius:999px;padding:8px 12px;margin:3px;font-size:13px}.topline{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:18px}footer{color:#a99d99;text-align:center;padding:34px}@media(max-width:700px){.toolbar{grid-template-columns:1fr;top:0;border-radius:0 0 22px 22px;margin-left:-16px;margin-right:-16px}.hero{padding-top:32px}.grid{grid-template-columns:1fr}.card{min-height:unset}.gallery{grid-template-columns:repeat(2,1fr)}.gallery img{height:130px}}
'''

APPJS = r'''
let ITEMS=[]; const mediaPrefix='media/';
const $=s=>document.querySelector(s); const grid=$('#grid'), detail=$('#detail'), search=$('#search');
function esc(s){return (s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function mediaPath(p){ if(!p) return ''; return mediaPrefix + p.replace(/^app\/src\/main\/assets\//,'').replace(/^assets\//,'').replace(/^\/+/, '');}
function placeholder(){return `<div class="thumb"><span>1966</span></div>`}
function thumb(item){const img=(item.photos||[])[0]?.asset; return img?`<div class="thumb"><img loading="lazy" src="${esc(mediaPath(img))}" onerror="this.parentElement.innerHTML='<span>1966</span>'"></div>`:placeholder();}
function card(item){return `<article class="card" onclick="openItem('${esc(item.id)}')">${thumb(item)}<div class="content"><h2>${esc(item.title)}</h2><p>${esc(item.summary)}</p></div><div class="meta">${esc(item.season||'Balkes Arşivi')} · ${item.imageCount||0} foto · ${item.tableCount||0} tablo</div></article>`}
function renderList(){const q=(search.value||'').toLocaleLowerCase('tr'); const arr=ITEMS.filter(x=>(x.title+' '+x.summary+' '+x.content+' '+(x.season||'')).toLocaleLowerCase('tr').includes(q)); detail.classList.remove('active'); grid.style.display='grid'; grid.innerHTML=arr.length?arr.map(card).join(''):`<div class="empty">Sonuç bulunamadı.</div>`; $('#count').textContent=`${arr.length} içerik`;}
function paras(text){return (text||'').split(/\n{2,}/).map(p=>p.trim()).filter(Boolean)}
function tableHtml(t){if(!t||!t.headers||!t.rows) return ''; return `<section class="tableWrap"><h3>${esc(t.title||'Tablo')}</h3><div class="tableScroll"><table><thead><tr>${t.headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${t.rows.map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`}
function openItem(id){const item=ITEMS.find(x=>x.id===id); if(!item)return; grid.style.display='none'; detail.classList.add('active'); const photos=item.photos||[]; const cover=photos[0]; const rest=photos.slice(1); let body=''; const ps=paras(item.content); ps.forEach((p,i)=>{body+=`<p>${esc(p).replace(/\n/g,'<br>')}</p>`}); let galleries=''; if(rest.length){galleries=`<h2>Fotoğraflar</h2><div class="gallery">${rest.map(p=>`<figure><img loading="lazy" src="${esc(mediaPath(p.asset))}"><figcaption>${esc(p.caption||'Arşiv görseli')}</figcaption></figure>`).join('')}</div>`} let tables=(item.tables||[]).map(tableHtml).join(''); detail.innerHTML=`<div class="topline"><button onclick="renderList()">← Arşive dön</button><span class="badge">${esc(item.season||'Balkes Arşivi')}</span><span class="badge">${item.imageCount||0} foto</span><span class="badge">${item.tableCount||0} tablo</span></div><h1>${esc(item.title)}</h1><div class="submeta">${esc(item.sourceType||'Balkes Arşivi')}</div>${cover?`<img class="hero-photo" loading="lazy" src="${esc(mediaPath(cover.asset))}"><div class="caption">${esc(cover.caption||'Arşiv görseli')}</div>`:`<div class="thumb" style="height:220px;border-radius:22px;margin-bottom:14px"><span>1966</span></div><div class="caption">Temsilidir</div>`}<article class="article">${body}</article>${tables}${galleries}`; location.hash=id; scrollTo({top:0,behavior:'smooth'});}
async function boot(){ITEMS=await fetch('data/items.json',{cache:'no-store'}).then(r=>r.json()); search.addEventListener('input', renderList); $('#clearBtn').addEventListener('click',()=>{search.value='';renderList()}); if(location.hash.length>1){renderList(); openItem(decodeURIComponent(location.hash.slice(1)));} else renderList();}
boot();
'''

def main():
    items=read_items()
    write_files(items)
    bad=[x for x in items if BAD_TITLE_RE.search(x['title']) or BAD_TITLE_RE.search(x['summary']) or CSS_RE.search(x['title']) or CSS_RE.search(x['summary'])]
    print(f'{len(items)} içerik üretildi: {OUT}')
    print(f'Bozuk kart kontrolü: {len(bad)}')
    if bad:
        for x in bad[:20]: print('BOZUK:', x['title'])
        raise SystemExit(1)

if __name__=='__main__': main()
