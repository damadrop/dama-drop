/* Dama Drop frontend */
const $ = (s) => document.querySelector(s);

let PRODUCTS = [];
let BRANDS = [];
let activeBrand = "all";

const money = (n) =>
  n ? "$" + Number(n).toFixed(2).replace(/\.00$/, "") : "—";

function timeAgo(iso) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 90) return "just now";
  if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " hr ago";
  return Math.floor(s / 86400) + " days ago";
}

function isComplete(p) {
  const t = (p.type || "").toLowerCase();
  return t.includes("kendama") && !/only|accessor|apparel|gift|specialty/.test(t);
}

async function init() {
  try {
    const snap = await (await fetch("/api/snapshot")).json();
    PRODUCTS = snap.products || [];
    BRANDS = snap.brands || [];
    $("#updated").textContent = "stock updated " + timeAgo(snap.updated_at);
    const inStock = PRODUCTS.filter((p) => p.available).length;
    $("#counts").textContent = `${inStock} in stock · ${PRODUCTS.length} products`;
  } catch (e) {
    $("#updated").textContent = "couldn't load stock data";
  }
  renderBrandPills();
  renderGrid();
  renderKusa();
  loadEvents();
  wireForms();
}

function renderBrandPills() {
  const el = $("#brands");
  const live = BRANDS.filter((b) => b.live);
  el.innerHTML =
    `<button data-b="all" class="active">All brands</button>` +
    live.map((b) => `<button data-b="${b.id}">${b.name}</button>`).join("");
  el.querySelectorAll("button").forEach((btn) =>
    btn.addEventListener("click", () => {
      el.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      btn.classList.add("active");
      activeBrand = btn.dataset.b;
      renderGrid();
    })
  );
  const sel = $("#alert-brand");
  sel.innerHTML = live.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
}

function filtered() {
  const q = $("#search").value.trim().toLowerCase();
  const cat = $("#category").value;
  const inStockOnly = $("#instock").checked;
  return PRODUCTS.filter((p) => {
    if (activeBrand !== "all" && p.brand !== activeBrand) return false;
    if (inStockOnly && !p.available) return false;
    if (cat === "kendama" && !isComplete(p)) return false;
    if (cat === "parts" && isComplete(p)) return false;
    if (q && !(p.title.toLowerCase().includes(q))) return false;
    return true;
  }).sort((a, b) => (b.available - a.available) || a.title.localeCompare(b.title));
}

function card(p) {
  const brand = (BRANDS.find((b) => b.id === p.brand) || {}).name || p.brand;
  const badge = p.available
    ? `<span class="badge in">In stock</span>`
    : `<span class="badge out">Sold out</span>`;
  const buy = p.available
    ? `<a class="buy" href="${p.url}" target="_blank" rel="noopener">Buy direct</a>`
    : `<span class="buy disabled">Sold out</span>`;
  const img = p.image
    ? `<img src="${p.image}" alt="" loading="lazy">`
    : `<img alt="">`;
  return `<div class="card">${img}
    <div class="card-body">
      <div class="card-brand">${brand}</div>
      <h3 class="card-title">${escapeHtml(p.title)}</h3>
      <div class="card-foot"><span class="price">${money(p.price)}</span>${badge}</div>
      ${buy}
    </div></div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderGrid() {
  const list = filtered().slice(0, 300);
  $("#grid").innerHTML = list.map(card).join("");
  $("#empty").hidden = list.length > 0;
}

function renderKusa() {
  const b = BRANDS.find((x) => x.id === "kendama-usa");
  if (!b) return;
  $("#kusa").innerHTML = `<h3>${b.name}</h3>
    <p>${escapeHtml(b.note || "")}</p>
    <div class="kusa-links">${(b.links || [])
      .map((l) => `<a href="${l.url}" target="_blank" rel="noopener">${escapeHtml(l.label)} ↗</a>`)
      .join("")}</div>`;
}

async function loadEvents() {
  try {
    const evs = await (await fetch("/api/events")).json();
    $("#events").innerHTML = evs.length
      ? evs.map((e) => {
          const p = e.product || {};
          const label = e.type === "restock" ? "Restock" : "New drop";
          return `<div class="event"><span class="tag ${e.type}">${label}</span>
            <a href="${p.url}" target="_blank" rel="noopener">${escapeHtml(p.title || "")}</a>
            <time>${timeAgo(e.at)}</time></div>`;
        }).join("")
      : `<div class="event">No restocks or drops yet — check back soon.</div>`;
  } catch (e) { /* leave empty */ }
}

function wireForms() {
  $("#search").addEventListener("input", renderGrid);
  $("#category").addEventListener("change", renderGrid);
  $("#instock").addEventListener("change", renderGrid);

  // lookup
  $("#lookup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = $("#lookup-url").value.trim();
    const box = $("#lookup-result");
    box.innerHTML = `<p class="lede small">Looking it up…</p>`;
    try {
      const r = await fetch("/api/lookup?url=" + encodeURIComponent(url));
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Lookup failed");
      const badge = d.available
        ? `<span class="badge in">In stock</span>`
        : `<span class="badge out">Sold out</span>`;
      box.innerHTML = `<div class="lookup-card">
        ${d.image ? `<img src="${d.image}" alt="">` : ""}
        <div>
          <h3>${escapeHtml(d.title)}</h3>
          <div class="row"><span class="price">${money(d.price)}</span>${badge}
          ${d.brand ? `<span class="card-brand">${escapeHtml(d.brand)}</span>` : ""}</div>
          <div class="row"><a class="buy" style="margin:0" href="${d.url}" target="_blank" rel="noopener">Open on the real site ↗</a></div>
          <form class="mini-form" id="watch-form">
            <input type="email" id="watch-email" placeholder="Email for restock alert" required>
            <button type="submit">Alert me if it restocks</button>
          </form>
          <p class="form-msg" id="watch-msg" hidden></p>
        </div></div>`;
      $("#watch-form").addEventListener("submit", async (ev) => {
        ev.preventDefault();
        await subscribe($("#watch-email").value, "product", d.product_id || d.url, $("#watch-msg"));
      });
    } catch (err) {
      box.innerHTML = `<p class="form-msg err">${escapeHtml(err.message)}</p>`;
    }
  });

  // alerts
  const kindRadios = document.querySelectorAll('input[name="kind"]');
  const syncTarget = () => {
    const kind = document.querySelector('input[name="kind"]:checked').value;
    $("#alert-target").hidden = kind !== "product";
    $("#alert-brand").hidden = kind !== "brand";
  };
  kindRadios.forEach((r) => r.addEventListener("change", syncTarget));
  syncTarget();

  $("#alert-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const kind = document.querySelector('input[name="kind"]:checked').value;
    const target = kind === "product" ? $("#alert-target").value.trim()
                 : kind === "brand" ? $("#alert-brand").value : "";
    await subscribe($("#alert-email").value, kind, target, $("#alert-msg"));
  });
}

async function subscribe(email, kind, target, msgEl) {
  msgEl.hidden = true;
  try {
    const r = await fetch("/api/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, kind, target }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Couldn't save that alert");
    msgEl.className = "form-msg ok";
    msgEl.textContent = "You're in. We'll email you the moment it happens.";
  } catch (err) {
    msgEl.className = "form-msg err";
    msgEl.textContent = err.message;
  }
  msgEl.hidden = false;
}

init();
