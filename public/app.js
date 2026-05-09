
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
