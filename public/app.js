
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
