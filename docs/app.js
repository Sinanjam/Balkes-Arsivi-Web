
const DATA = window.BALKES_DATA || { items: [], rawBase: "", maxInlineTables: 8 };
let ITEMS = DATA.items || [];
let RAW = DATA.rawBase || "";
let MAXT = DATA.maxInlineTables || 8;

const $ = (s) => document.querySelector(s);
const grid = $("#grid");
const detail = $("#detail");
let search = $("#search");

const esc = (s) => (s || "").replace(/[&<>"']/g, (m) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
  "'": "&#39;"
}[m]));

function normalizeTR(s) {
  return String(s || "")
    .toLocaleLowerCase("tr")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[ıİ]/g, "i")
    .replace(/[ğĞ]/g, "g")
    .replace(/[üÜ]/g, "u")
    .replace(/[şŞ]/g, "s")
    .replace(/[öÖ]/g, "o")
    .replace(/[çÇ]/g, "c")
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function itemHaystack(it) {
  return normalizeTR([
    it.title,
    it.summary,
    it.season,
    ...(it.paragraphs || []),
    ...(it.photos || []).map((p) => p.caption || ""),
    ...(it.tables || []).map((t) => t.title || "")
  ].join(" "));
}

ITEMS = ITEMS.map((it) => ({ ...it, _search: itemHaystack(it) }));

function encAsset(p) {
  return RAW + String(p || "").split("/").map(encodeURIComponent).join("/");
}

function placeholderThumb() {
  return `<div class="thumb"><span>1966</span></div>`;
}

function cardThumb(it) {
  const p = it.photos && it.photos[0] && it.photos[0].asset;
  return p
    ? `<div class="thumb"><img loading="lazy" decoding="async" src="${esc(encAsset(p))}" onerror="this.parentElement.innerHTML='<span>1966</span>'"></div>`
    : placeholderThumb();
}

function card(it) {
  return `<article class="card" onclick="openItem('${esc(it.id)}')">
    ${cardThumb(it)}
    <div class="content">
      <h2>${esc(it.title)}</h2>
      <p>${esc(it.summary)}</p>
    </div>
    <div class="meta">${esc(it.season || "Balkes Arşivi")} · ${it.imageCount || 0} foto · ${it.tableCount || 0} tablo</div>
  </article>`;
}

function parseQuery(q) {
  return normalizeTR(q).split(" ").filter(Boolean);
}

function scoreItem(it, terms) {
  if (!terms.length) return 1;
  const title = normalizeTR(it.title);
  const season = normalizeTR(it.season);
  let score = 0;
  for (const t of terms) {
    if (title.includes(t)) score += 8;
    if (season.includes(t)) score += 4;
    if (it._search.includes(t)) score += 1;
    else return -1;
  }
  return score;
}

function renderList() {
  const terms = parseQuery(search ? search.value : "");
  let arr = ITEMS
    .map((it) => ({ it, score: scoreItem(it, terms) }))
    .filter((x) => x.score >= 0)
    .sort((a, b) => b.score - a.score || a.it.title.localeCompare(b.it.title, "tr"))
    .map((x) => x.it);

  detail.classList.remove("active");
  grid.style.display = "grid";

  const count = $("#count");
  if (count) {
    count.innerHTML = terms.length
      ? `${arr.length} sonuç <button class="clear-btn" onclick="clearSearch()">Aramayı temizle</button>`
      : `${ITEMS.length} içerik`;
  }

  if (!arr.length) {
    grid.innerHTML = `<div class="empty">Aramanla eşleşen içerik bulunamadı. Daha kısa veya farklı bir kelime dene.</div>`;
    return;
  }

  const visible = terms.length ? arr.slice(0, 250) : arr.slice(0, 120);
  grid.innerHTML = visible.map(card).join("");
  if (arr.length > visible.length) {
    grid.innerHTML += `<div class="empty">${arr.length - visible.length} içerik daha var. Daha dar arama yaparak hızlıca ulaşabilirsin.</div>`;
  }
}

function clearSearch() {
  search.value = "";
  renderList();
  search.focus();
}

function photoBlock(it, index, total) {
  const p = it.photos[index];
  if (!p) return "";
  return `<figure class="photo-block">
    <img loading="lazy" decoding="async" src="${esc(encAsset(p.asset))}" alt="${esc(p.caption || it.title)}">
    <figcaption class="caption">${p.caption ? esc(p.caption) : "Arşiv görseli"}</figcaption>
  </figure>`;
}

function generatedBlock() {
  return `<div class="photo-block"><div class="placeholder">1966</div><div class="caption">Temsilidir</div></div>`;
}

function tableHtml(rows) {
  if (!rows || !rows.length) return "";
  const head = rows[0];
  const body = rows.slice(1);
  return `<table>
    <thead><tr>${head.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${body.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody>
  </table>`;
}

function looksMatch(rows) {
  const blob = (rows || []).slice(0, 8).flat().join(" ").toLocaleLowerCase("tr");
  return blob.includes("tarih") || /\d{2}\.\d{2}\.\d{4}/.test(blob);
}

function looksStanding(rows) {
  const blob = (rows || []).slice(0, 8).flat().join(" ").toLocaleLowerCase("tr");
  return blob.includes("takımlar") || blob.includes("takimlar") || blob.includes("puan durumu");
}

function matchCards(rows) {
  let out = `<div class="match-grid">`;
  for (let i = 1; i < Math.min(rows.length, 80); i++) {
    const r = rows[i];
    const joined = r.filter(Boolean).join(" ");
    if (!joined) continue;
    out += `<div class="match-card"><div class="small">${esc(r[0] || "")}</div><div class="score">${esc(r.slice(1).filter(Boolean).join(" · "))}</div></div>`;
  }
  return out + `</div>`;
}

function standingCards(rows) {
  let out = `<div class="standing-grid">`;
  for (let i = 1; i < Math.min(rows.length, 80); i++) {
    const r = rows[i];
    if (!r.some(Boolean)) continue;
    out += `<div class="standing-card"><b>${esc((r[0] ? r[0] + ". " : "") + (r[1] || r[0] || ""))}</b><div class="small">${esc(r.slice(2).filter(Boolean).join(" · "))}</div></div>`;
  }
  return out + `</div>`;
}

function tableBlock(t) {
  const rows = t.rows || [];
  const body = looksMatch(rows) ? matchCards(rows) : (looksStanding(rows) ? standingCards(rows) : tableHtml(rows));
  return `<section class="table-card"><h3>${esc(t.title || "Tablo")}</h3>${body}</section>`;
}

function appArticleFlow(it) {
  let ps = it.paragraphs || [];
  const tables = it.tables || [];
  const maxTables = Math.min(tables.length, MAXT);
  const photoCount = (it.photos || []).length;
  const photoLimit = Math.min(photoCount, Math.max(1, Math.min(8, Math.floor(ps.length / 2) + 1)));
  let photoIndex = 0;
  let tableIndex = 0;
  let generatedShown = false;
  let out = "";

  if (!ps.length) ps = ["Bu içerik arşiv kaydı olarak korunmuştur."];

  for (let i = 0; i < ps.length; i++) {
    out += `<p class="para ${i === 0 ? "lead" : ""}">${esc(ps[i]).replace(/\n/g, "<br>")}</p>`;

    if (i === 0) {
      if (photoCount > 0 && photoIndex < photoLimit) {
        out += photoBlock(it, photoIndex, photoCount);
        photoIndex++;
      } else if (photoCount === 0) {
        out += generatedBlock();
        generatedShown = true;
      }
    }

    if (i === 1 && tableIndex < maxTables) {
      out += tableBlock(tables[tableIndex]);
      tableIndex++;
    }

    if (i > 1 && photoIndex < photoLimit && ((i + 1) % 3 === 0)) {
      out += photoBlock(it, photoIndex, photoCount);
      photoIndex++;
    }

    if (i > 2 && tableIndex < maxTables && ((i + 1) % 4 === 0)) {
      out += tableBlock(tables[tableIndex]);
      tableIndex++;
    }
  }

  if (photoCount === 0 && !generatedShown) out += generatedBlock();
  while (photoIndex < photoLimit) {
    out += photoBlock(it, photoIndex, photoCount);
    photoIndex++;
  }
  while (tableIndex < maxTables) {
    out += tableBlock(tables[tableIndex]);
    tableIndex++;
  }
  return out;
}

function openItem(id) {
  const it = ITEMS.find((x) => x.id === id);
  if (!it) return;
  grid.style.display = "none";
  detail.classList.add("active");
  detail.innerHTML = `<div class="topline">
      <button onclick="renderList()">← Arşive dön</button>
      <span class="badge">${esc(it.season || "Balkes Arşivi")}</span>
      <span class="badge">${it.imageCount || 0} foto</span>
      <span class="badge">${it.tableCount || 0} tablo</span>
    </div>
    <article class="article-page">
      <div class="kicker">${esc(it.season ? ("Balkes Arşivi • " + it.season) : "Balkes Arşivi")}</div>
      <h1>${esc(it.title)}</h1>
      <div class="article">${appArticleFlow(it)}</div>
    </article>`;
  location.hash = id;
  scrollTo({ top: 0, behavior: "smooth" });
}

function boot() {
  const toolbar = document.querySelector(".toolbar");
  if (toolbar && !toolbar.querySelector(".search-wrap")) {
    toolbar.innerHTML = `<div class="search-wrap"><input id="search" placeholder="Arşivde ara..." autocomplete="off"><button class="clear-btn" onclick="clearSearch()">Temizle</button></div>`;
  }
  search = document.querySelector("#search");
  window.search = search;
  search.addEventListener("input", renderList);
  renderList();
  if (location.hash.length > 1) {
    openItem(decodeURIComponent(location.hash.slice(1)));
  }
}

boot();
