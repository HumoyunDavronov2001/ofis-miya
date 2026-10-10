"use strict";
/* Miya paneli — bitta sahifa, hash yo'naltirish. Hamma raqamni server hisoblaydi; bu yerda faqat ko'rsatiladi. */

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const H = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
let MEN = null;

async function api(url, opts = {}) {
  const o = {credentials: "same-origin", headers: {}};
  if (opts.body !== undefined) {
    o.method = "POST";
    o.headers["Content-Type"] = "application/json";
    o.headers["X-Miya"] = "1";
    o.body = JSON.stringify(opts.body);
  }
  const r = await fetch(url, o);
  let d = null;
  try { d = await r.json(); } catch (e) { /* bo'sh javob */ }
  if (r.status === 401 && !url.startsWith("/api/kirish")) { kirishSahifa(); throw new Error("Qaytadan kiring"); }
  if (!r.ok) throw new Error((d && (d.xato || d.detail)) || `Xato (${r.status})`);
  return d;
}

function xabar(m, xato = false) {
  const t = document.createElement("div");
  if (xato) t.className = "xato";
  t.textContent = m;
  $("#toast").appendChild(t);
  setTimeout(() => t.remove(), xato ? 6000 : 3500);
}

function oyna(sarlavha, ichki, past = "") {
  const fon = document.createElement("div");
  fon.className = "oyna-fon";
  fon.innerHTML = `<div class="oyna" role="dialog" aria-modal="true" aria-label="${H(sarlavha)}">
    <h3>${H(sarlavha)}<button class="btn ik kichik" data-yop aria-label="Yopish"><i class="ti ti-x"></i></button></h3>
    <div class="oyna-ichi">${ichki}</div>${past ? `<div class="past">${past}</div>` : ""}</div>`;
  const yop = () => { fon.remove(); document.removeEventListener("keydown", esc); };
  const esc = e => { if (e.key === "Escape") yop(); };
  fon.addEventListener("click", e => { if (e.target === fon || e.target.closest("[data-yop]")) yop(); });
  document.addEventListener("keydown", esc);
  document.body.appendChild(fon);
  const birinchi = fon.querySelector("input,select,textarea");
  if (birinchi) birinchi.focus();
  return {el: fon, yop};
}

const pul = p => p ? p.t : "—";
function oyTanlov(tanlangan) {
  const [y, m] = MEN.oy.split("-").map(Number);
  let html = "";
  for (let i = 0; i < 24; i++) {
    const d = new Date(y, m - 1 - i, 1);
    const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const nom = OYLAR[d.getMonth()];
    html += `<option value="${k}" ${k === tanlangan ? "selected" : ""}>${nom[0].toUpperCase() + nom.slice(1)} ${d.getFullYear()}</option>`;
  }
  return `<select id="oy" style="width:auto">${html}</select>`;
}
const guruh = n => Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ");
const OYLAR = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"];
const sanaMatn = s => { if (!s) return "—"; const d = new Date(s.slice(0, 10) + "T00:00:00"); return `${d.getDate()}-${OYLAR[d.getMonth()]}`; };
const bosh = (ism) => (ism || "?").split(/\s+/).map(x => x[0]).join("").slice(0, 2).toUpperCase();
const AV = ["", "h2", "h3", "h4", "h5"];
const avRang = id => AV[(id || 0) % AV.length];

/* ---------- yozuv turlari (bot kartochkasi bilan bir xil) ---------- */
const TUR = {
  kirim: {nom: "Kirim", f: ["kassa", "mijoz?"]},
  chiqim: {nom: "Xarajat", f: ["kassa", "xarajat_turi"]},
  sotuv: {nom: "Sotuv", f: ["mijoz", "tolandi", "kassa", "sotuvchi", "muddat"]},
  avans: {nom: "Avans", f: ["kassa", "odam"]},
  maosh_tolov: {nom: "Maosh to'lovi", f: ["kassa", "odam"]},
  qolga_berish: {nom: "Xodimga xarajat uchun pul", f: ["kassa", "odam"]},
  qoldan_qaytarish: {nom: "Xodim pulni kassaga topshirdi", f: ["kassa", "odam"]},
  mijozdan_qolga: {nom: "Xodim mijozdan pul oldi", f: ["odam", "mijoz"]},
  otkazma: {nom: "Kassadan kassaga", f: ["kassa", "kassa2"]},
  egasi_oldi: {nom: "Egasi oldi", f: ["kassa"], rol: ["boshliq", "kassir"]},
  egasi_qoydi: {nom: "Egasi qo'ydi", f: ["kassa"], rol: ["boshliq", "kassir"]},
  xodim_qarz: {nom: "Xodimga qarz", f: ["kassa", "odam"]},
  qarz_qaytdi: {nom: "Xodim qarzini qaytardi", f: ["kassa", "odam"]},
  taminotchi_nasiya: {nom: "Ta'minotchidan nasiyaga olindi", f: ["taminotchi", "xarajat_turi", "muddat"]},
  taminotchiga_tolov: {nom: "Ta'minotchiga to'lov", f: ["kassa", "taminotchi"]},
  ishbay: {nom: "Ishbay ish haqi", f: ["odam"], rol: ["boshliq", "menejer"]},
  bonus: {nom: "Bonus", f: ["odam"], rol: ["boshliq"]},
  jarima: {nom: "Jarima", f: ["odam"], rol: ["boshliq"]},
  qarzdan_ushlash: {nom: "Xodim qarzi maoshdan ushlandi", f: ["odam"], rol: ["boshliq"]},
  boshlangich_kassa: {nom: "Kassadagi boshlang'ich pul", f: ["kassa"], rol: ["boshliq"]},
  boshlangich_maosh: {nom: "Xodimga avvaldan qarzimiz", f: ["odam"], rol: ["boshliq"]},
  boshlangich_mijoz: {nom: "Mijozning avvaldan qarzi", f: ["mijoz"], rol: ["boshliq"]},
  boshlangich_taminotchi: {nom: "Ta'minotchiga avvaldan qarzimiz", f: ["taminotchi"], rol: ["boshliq"]},
};
const HOLAT = {
  faol: ["Faol", "y"], nizo: ["Nizo", "q"], bekor: ["Bekor", ""], ruxsat_kutilmoqda: ["Ruxsat kutmoqda", "kut"], taklif: ["Taklif", ""],
};

/* ---------- boshlanish ---------- */
async function boshla() {
  try {
    const h = await api("/api/holat");
    if (!h.sozlangan) return sozlashSahifa(h.kod_kerak);
    MEN = await api("/api/men");
  } catch (e) { return; }
  if (!MEN.boshliq) return chatIlova();  // R1–R2: panel faqat boshliqqa; xodimlarga — faqat chat
  qobiq();
  window.addEventListener("hashchange", yonalish);
  yonalish();
}

function kirishSahifa() {
  MEN = null;
  $("#ildiz").innerHTML = `<div class="kirish"><div class="kirish-k">
    <div class="logo"><span class="orb k"><i></i></span><div><b>miya</b><small>Ofis xotirasi</small></div></div>
    <h1>Kirish</h1><p>Login va parolni boshliq beradi.</p>
    <form id="kf"><label class="maydon"><span>Login</span><input type="text" name="login" autocomplete="username" required></label>
    <label class="maydon"><span>Parol</span><input type="password" name="parol" autocomplete="current-password" required></label>
    <div class="xato-m" id="kx"></div><button class="btn asosiy" type="submit">Kirish</button></form></div></div>`;
  $("#kf").addEventListener("submit", async e => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      await api("/api/kirish", {body: {login: f.get("login"), parol: f.get("parol")}});
      location.hash = "#/bugun";
      boshla();
    } catch (x) { $("#kx").textContent = x.message; }
  });
}

function sozlashSahifa(kodKerak = false) {
  $("#ildiz").innerHTML = `<div class="kirish"><div class="kirish-k">
    <div class="logo"><span class="orb k"><i></i></span><div><b>miya</b><small>Ofis xotirasi</small></div></div>
    <h1>Birinchi sozlash</h1><p>Boshliq hisobini yarating. Keyin xodimlarni qo'shasiz.</p>
    <form id="sf"><label class="maydon"><span>Ismingiz</span><input type="text" name="ism" required placeholder="Rustam Aliyev"></label>
    <label class="maydon"><span>Login</span><input type="text" name="login" required minlength="3" autocomplete="username"></label>
    <label class="maydon"><span>Parol</span><input type="password" name="parol" required minlength="6" autocomplete="new-password"><small>Kamida 6 belgi</small></label>
    ${kodKerak ? `<label class="maydon"><span>Sozlash kodi</span><input type="text" name="kod" required autocomplete="off" style="text-transform:uppercase"><small>Dasturni o'rnatgan odam bergan bir martalik kod</small></label>` : ""}
    <div class="xato-m" id="sx"></div><button class="btn asosiy" type="submit">Yaratish</button></form></div></div>`;
  $("#sf").addEventListener("submit", async e => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      await api("/api/sozlash", {body: {ism: f.get("ism"), login: f.get("login"), parol: f.get("parol"), kod: (f.get("kod") || "").toUpperCase()}});
      location.hash = "#/sozlamalar";
      boshla();
    } catch (x) { $("#sx").textContent = x.message; }
  });
}

const SAHIFA = {
  bugun: {nom: "Bugun", ikon: "ti-sun", g: "Asosiy", k: () => true},
  chat: {nom: "Chat", ikon: "ti-message-circle", g: "Asosiy", k: m => m.boshliq},
  kalendar: {nom: "Kalendar", ikon: "ti-calendar-event", g: "Asosiy", k: m => m.boshliq},
  arxiv: {nom: "Xotira arxivi", ikon: "ti-archive", g: "Asosiy", k: () => true},
  buyurtmalar: {nom: "Buyurtmalar", ikon: "ti-clipboard-list", g: "Hisob", k: m => m.boshliq},
  mahsulotlar: {nom: "Mahsulotlar", ikon: "ti-package", g: "Hisob", k: m => m.boshliq},
  kassa: {nom: "Kassa va pul", ikon: "ti-wallet", g: "Hisob", k: m => m.boshliq || m.huquq.kassa},
  maosh: {nom: "Maosh", ikon: "ti-cash-banknote", g: "Hisob", k: () => true},
  mijozlar: {nom: "Mijozlar", ikon: "ti-address-book", g: "Hisob", k: m => m.boshliq || m.huquq.mijoz_qarz},
  vadalar: {nom: "Va'dalar", ikon: "ti-heart-handshake", g: "Hisob", k: m => m.boshliq || m.huquq.mijoz_qarz},
  hisobot: {nom: "Hisobotlar", ikon: "ti-chart-bar", g: "Hisob", k: m => m.boshliq},
  qidiruv: {nom: "Qidiruv", ikon: "ti-search", g: "", k: m => m.boshliq, yashirin: true},
  ishlar: {nom: "Ishlar", ikon: "ti-checklist", g: "Odamlar", k: m => m.boshliq || m.odam.rol === "menejer"},
  davomat: {nom: "Davomat", ikon: "ti-clock-check", g: "Odamlar", k: m => m.boshliq || m.odam.rol === "menejer"},
  xodimlar: {nom: "Xodimlar", ikon: "ti-users", g: "Odamlar", k: m => m.boshliq},
  usullar: {nom: "Ish usullari", ikon: "ti-book", g: "Odamlar", k: m => m.boshliq || m.odam.rol === "menejer"},
  qoidalar: {nom: "Boshliq qoidalari", ikon: "ti-scale", g: "Tizim", k: m => m.boshliq},
  sozlamalar: {nom: "Sozlamalar", ikon: "ti-settings", g: "Tizim", k: m => m.boshliq},
  jurnal: {nom: "Jurnal", ikon: "ti-history", g: "Tizim", k: m => m.boshliq},
};

function qobiq() {
  const o = MEN.odam;
  let nav = "", g = "";
  for (const [kalit, s] of Object.entries(SAHIFA)) {
    if (!s.k(MEN) || s.yashirin) continue;
    if (s.g !== g) { nav += `<div class="guruh">${s.g}</div>`; g = s.g; }
    nav += `<a href="#/${kalit}" data-s="${kalit}"><i class="ti ${s.ikon}" aria-hidden="true"></i>${s.nom}<span class="nishon yashirin" data-n="${kalit}"></span></a>`;
  }
  $("#ildiz").innerHTML = `<div class="ilova"><aside class="yon" id="yon">
      <div class="logo"><span class="orb k"><i></i></span><div><b>miya</b><small>Ofis xotirasi</small></div></div>
      <form class="yq" id="yq" role="search"><i class="ti ti-search" aria-hidden="true"></i><input type="search" name="q" placeholder="Qidirish…" aria-label="Umumiy qidiruv" autocomplete="off"><kbd>/</kbd></form>
      <nav>${nav}</nav>
      <div class="men"><span class="av ${avRang(o.id)}" style="width:36px;height:36px">${H(bosh(o.ism))}</span>
        <div><b>${H(o.ism)}</b><small>${H(o.rol_nomi)}</small></div>
        <button class="btn ik kichik" id="chiq" aria-label="Chiqish" title="Chiqish"><i class="ti ti-logout"></i></button></div>
    </aside><main id="sahifa"></main></div>`;
  $("#chiq").addEventListener("click", async () => { await api("/api/chiqish", {body: {}}); kirishSahifa(); });
  $("#yq").addEventListener("submit", e => { e.preventDefault(); const q = e.target.q.value.trim(); if (q) { location.hash = `#/qidiruv?q=${encodeURIComponent(q)}`; $("#yon").classList.remove("ochiq"); } });
  document.addEventListener("keydown", e => {  // «/» — qidiruvga (yozish maydonida emas)
    if (e.key === "/" && !e.target.closest("input,textarea,select,[contenteditable]")) { e.preventDefault(); $("#yq input")?.focus(); }
  });
  for (const [k, n] of Object.entries(MEN.nishon || {})) nishonQoy(k, n);
  $("#yon").addEventListener("click", e => { if (e.target.closest("a")) $("#yon").classList.remove("ochiq"); });
}

function nishonQoy(kalit, n) {
  const el = $(`[data-n="${kalit}"]`);
  if (!el) return;
  el.textContent = n || "";
  el.classList.toggle("yashirin", !n);
}

async function yonalish() {
  if (!MEN) return;
  let s = (location.hash.replace(/^#\//, "") || "bugun").split("?")[0];
  if (!SAHIFA[s] || !SAHIFA[s].k(MEN)) s = "bugun";
  $$("#yon a").forEach(a => a.classList.toggle("faol", a.dataset.s === s));
  // har o'tishda toza element: aks holda sahifalar qo'shgan tinglovchilar yig'ilib, tugma bir necha marta ishlardi
  const eski = $("#sahifa"), main = eski.cloneNode(false);
  eski.replaceWith(main);
  main.innerHTML = `<div class="bosh"><i class="ti ti-loader-2"></i>Yuklanmoqda…</div>`;
  try {
    await ({bugun: bugunSahifa, chat: chatSahifa, kalendar: kalendarSahifa, hisobot: hisobotSahifa, qidiruv: qidiruvSahifa, buyurtmalar: buyurtmaSahifa, mahsulotlar: katalogSahifa, kassa: kassaSahifa, maosh: maoshSahifa, mijozlar: mijozSahifa, vadalar: vadaSahifa, xodimlar: xodimSahifa, arxiv: arxivSahifa, usullar: usulSahifa,
      ishlar: ishSahifa, davomat: davomatSahifa,
      qoidalar: qoidaSahifa, sozlamalar: sozlamaSahifa, jurnal: jurnalSahifa})[s](main);
  } catch (e) {
    main.innerHTML = `<div class="karta"><div class="bosh"><i class="ti ti-alert-triangle"></i>${H(e.message)}</div></div>`;
  }
}

function tepa(sarlavha, izoh = "", tugmalar = "") {
  return `<header class="tepa"><div><h1><button class="btn ik menyu-b" onclick="document.getElementById('yon').classList.add('ochiq')" aria-label="Menyu"><i class="ti ti-menu-2"></i></button> ${sarlavha}</h1>${izoh ? `<p>${izoh}</p>` : ""}</div><div class="tugmalar">${tugmalar}</div></header>`;
}

/* ---------- Bugun ---------- */
function salom() {
  const s = new Date().getHours();
  return s < 5 ? "Xayrli tun" : s < 11 ? "Xayrli tong" : s < 17 ? "Xayrli kun" : "Xayrli kech";
}

const DIQQAT_IKON = {nizo: "ti-alert-triangle", ruxsat: "ti-shield-question", kassa_farq: "ti-cash-off",
  uzoq_tasdiq: "ti-hourglass", nasiya: "ti-clock-exclamation", qolda: "ti-wallet", maosh: "ti-cash-banknote",
  ish_kech: "ti-clock-exclamation", davomat: "ti-calendar-question", vada_bugun: "ti-heart-handshake",
  vada_buzildi: "ti-heart-broken", uxlagan: "ti-zzz", katta_xarajat: "ti-receipt", takror_chek: "ti-copy",
  band: "ti-briefcase", bosh: "ti-user-pause"};

async function bugunSahifa(main) {
  const d = await api("/api/bugun");
  const boss = MEN.boshliq;
  const kutSoni = d.kutmoqda.length;
  const ism1 = MEN.odam.ism.split(" ")[0];
  const takl = boss
    ? ["Kassada qancha pul bor?", "Kim bizga qarz?", "Bu hafta qancha xarajat qildik?", "Maosh kuniga pul yetadimi?"]
    : ["Mening hisobim qancha?", "Bu oy qancha avans oldim?"];
  let kpi = "";  // bo'sh (nol) kartalar ko'rsatilmaydi — faqat ma'lumoti borlari
  if (d.kassa_jami && (d.kassa_jami.m || (d.kassa_usd && d.kassa_usd.m) || d.oxirgi_sanoq)) {
    const s = d.oxirgi_sanoq;
    kpi += `<div class="k"><div class="kb0"><i class="ti ti-wallet"></i>Kassalarda</div>
      <div class="kr raqam">${H(d.kassa_jami.t.replace(/[\s\u00a0]so'm$/, ""))}<small>so'm</small></div>
      ${d.kassa_usd.m ? `<div class="ki">${H(d.kassa_usd.t)}</div>` : ""}
      <div class="ki ${s && s.farq === 0 ? "ok" : ""}">${s ? `<i class="ti ti-${s.farq === 0 ? "circle-check" : "alert-circle"}"></i>Oxirgi sanoq ${sanaMatn(s.sana)}${s.farq ? " · farq bor" : " · mos"}` : "Hali sanalmagan"}</div></div>`;
  }
  if (MEN.boshliq || MEN.huquq.mijoz_qarz) {
    const v = d.vadalar, pul_ = v.bugun.filter(x => x.tur === "tolov" && x.kim === "mijoz" && x.qolgan && x.qolgan.m > 0);
    const katta = pul_.reduce((a, x) => !a || x.qolgan.m > a.qolgan.m ? x : a, null);
    nishonQoy("vadalar", v.nishon);
    if (pul_.length) kpi += `<div class="k"><div class="kb0"><i class="ti ti-arrow-down-left"></i>Bugun kutilayotgan tushum</div>
      <div class="kr raqam">${H(v.bugun_tushum.t.replace(/[\s\u00a0]so'm$/, ""))}<small>so'm</small></div>
      <div class="ki"><i class="ti ti-heart-handshake"></i>${pul_.length} ta va'da · eng kattasi ${H(katta.mijoz.split(" ").slice(-1)[0])}</div></div>`;
  }
  if (d.mijoz_qarz && d.mijoz_qarz.soni) {
    kpi += `<div class="k"><div class="kb0"><i class="ti ti-users"></i>Mijozlar bizga qarz</div>
      <div class="kr raqam">${H(d.mijoz_qarz.jami.t.replace(/[\s\u00a0]so'm$/, ""))}<small>so'm</small></div>
      <div class="ki ${d.mijoz_qarz.otgan_soni ? "q" : ""}">${d.mijoz_qarz.otgan_soni ? `<i class="ti ti-clock-exclamation"></i>${H(d.mijoz_qarz.muddati_otgan.t)} muddati o'tgan` : `${d.mijoz_qarz.soni} ta mijoz`}</div></div>`;
  }
  if (d.maosh && d.maosh.kerak.m > 0) {
    const m = d.maosh, yetmaydi = m.yetmaydi.m > 0;
    const ulush = m.kerak.m ? Math.min(100, Math.round(m.aniq.m / m.kerak.m * 100)) : 100;
    kpi += `<div class="k ${yetmaydi ? "xavf" : ""}"><div class="kb0"><i class="ti ti-cash-banknote"></i>Maosh kuni · ${H(m.kun_matn)}</div>
      <div class="kr raqam">${yetmaydi ? `${H(m.yetmaydi.t.replace(/[\s\u00a0]so'm$/, ""))}<small>yetmaydi</small>` : `Yetadi<small>${m.qoldi_kun} kun bor</small>`}</div>
      <div class="chiz"><i style="width:${ulush}%;background:var(--kirim)"></i><i style="width:${100 - ulush}%;background:#F2B8B1"></i></div>
      <div class="ki">Kerak ${H(m.kerak.t)} · qo'lda ${H(m.aniq.t)}${m.vada && m.vada.m ? ` · va'dalar ${H(qisqa(m.vada.m))}` : ""}</div></div>`;
  }

  const diqqat = d.diqqat.map((x, i) => `<div class="sig" style="animation-delay:${i * 50}ms">
      <span class="si ${x.daraja === "xavf" ? "xavf" : "kut"}"><i class="ti ${DIQQAT_IKON[x.tur] || "ti-info-circle"}"></i></span>
      <div><b>${H(x.matn)}</b>${x.izoh ? `<div class="izohi">${H(x.izoh)}</div>` : ""}${diqqatManba(x)}</div>
      <div class="sa">${diqqatTugma(x)}</div></div>`).join("");
  const kut = d.kutmoqda.map(h => kutishQator(h)).join("");
  let chap = "";
  if (d.diqqat.length) chap += `<section class="karta"><div class="kb"><h2>Diqqat</h2><span class="soni">${d.diqqat.length}</span></div>${diqqat}</section>`;
  if (kutSoni) chap += `<section class="karta"><div class="kb"><h2>Tasdiq kutmoqda</h2><span class="soni kut">${kutSoni}</span><span class="izoh">Tasdiqlanmaguncha hisobga kirmaydi</span></div>${kut}</section>`;

  let ong = "";
  if (d.odamlar && (d.odamlar.length > 1 || d.odamlar.some(x => x.keldi))) {
    ong += `<section class="karta"><div class="kb"><h2>Bugun odamlar</h2><span class="izoh">${d.odamlar.filter(x => x.keldi).length} kishi keldi</span></div>
      ${d.odamlar.map(x => `<div class="odam"><span class="av ${avRang(x.odam_id)}">${H(bosh(x.ism))}</span>
        <div><b>${H(x.ism)}</b><small>${x.keldi ? `${H(x.keldi.slice(11, 16))} da keldi${x.kechikish ? ` · ${x.kechikish} daq kechikdi` : ""}${x.ketdi ? ` · ${H(x.ketdi.slice(11, 16))} da ketdi` : ""}${x.joylashuvsiz ? " · joylashuvsiz" : ""}` : "hali belgilanmagan"}</small></div>
        <div class="oi"><strong>${x.ochiq_ish} ta ish</strong>${x.kechikkan_ish ? `<span class="q">${x.kechikkan_ish} kechikkan</span>` : x.bugun_bajardi ? `${x.bugun_bajardi} tasi bajarildi` : ""}</div></div>`).join("")}</section>`;
  }
  if (d.qabul_kutmoqda && d.qabul_kutmoqda.length) {
    ong += `<section class="karta"><div class="kb"><h2>Qabul kutmoqda</h2><span class="soni kut">${d.qabul_kutmoqda.length}</span></div>
      ${d.qabul_kutmoqda.map(i => `<div class="sig"><span class="si ok"><i class="ti ti-circle-check"></i></span>
        <div><b>#${i.id} ${H(i.nom)}</b><div class="izohi">${H(i.ijrochilar.map(x => x.ism).join(", "))}${i.narx ? ` · ${H(i.narx.t)}` : i.manba === "xodim" ? " · narxi qo'yilmagan" : ""}</div></div>
        <div class="sa"><button class="btn kichik" data-ish="${i.id}">Ko'rish</button></div></div>`).join("")}</section>`;
  }
  if (d.xodimlar && d.xodimlar.length) {
    ong += `<section class="karta"><div class="kb"><h2>Xodimlar hisobi</h2><span class="izoh">to'lash kerak</span></div>
      ${d.xodimlar.length ? d.xodimlar.map(x => `<div class="odam"><span class="av ${avRang(x.id)}">${H(bosh(x.ism))}</span>
        <div><b>${H(x.ism)}</b>${x.qolida.m ? `<small>qo'lida ${H(x.qolida.t)}</small>` : ""}</div>
        <div class="oi"><strong class="raqam">${H(x.qolgani.t)}</strong></div></div>`).join("")
        : `<div class="bosh">Maosh sharti qo'yilgan xodim yo'q — «Maosh» bo'limida qo'ying</div>`}</section>`;
  }
  if (d.pul_oqimi && d.pul_oqimi.nuqtalar.some(n => n.aniq || n.vada)) ong += pulOqimi(d.pul_oqimi);
  if (d.xulosa) ong = xulosaKarta(d.xulosa, d.brifing_vaqti) + ong;
  if (d.hafta && (d.hafta.kirim.m || d.hafta.chiqim.m || d.hafta.sotuv.m)) {
    const kunlar = d.hafta.kunlar;
    const eng = Math.max(1, ...kunlar.map(k => Math.max(k.kirim, k.chiqim)));
    ong += `<section class="karta"><div class="kb"><h2>Shu hafta</h2><span class="izoh">kassa harakati</span></div>
      <div class="hafta"><div><small>Kirim</small><b class="raqam y">${H(qisqa(d.hafta.kirim.m))}</b></div>
      <div><small>Chiqim</small><b class="raqam q">${H(qisqa(d.hafta.chiqim.m))}</b></div>
      <div><small>Sotuv</small><b class="raqam">${H(qisqa(d.hafta.sotuv.m))}</b></div></div>
      <div class="diag">${kunlar.map((k, i) => `<div class="kun"><div class="jft"><i style="height:${Math.round(k.kirim / eng * 100)}%;animation-delay:${.2 + i * .06}s" title="Kirim ${guruh(k.kirim)}"></i><i style="height:${Math.round(k.chiqim / eng * 100)}%;animation-delay:${.25 + i * .06}s" title="Chiqim ${guruh(k.chiqim)}"></i></div><small>${k.sana === d.bugun ? "Bugun" : H(k.kun)}</small></div>`).join("")}</div>
      <div class="legend"><span><i style="background:var(--kirim)"></i>Kirim</span><span><i style="background:#E89A92"></i>Chiqim</span></div></section>`;
  }

  main.innerHTML = tepa(`${salom()}, ${H(ism1)}`,
    `${H(d.sana_matn)}<span class="n"></span>kecha ${d.kecha_yozuv || 0} ta xabar tushdi${kutSoni ? `<span class="n"></span><b>${kutSoni} tasi tasdiq kutmoqda</b>` : ""}`,
    `<button class="btn" data-a="yozuv"><i class="ti ti-plus"></i>Yozuv qo'shish</button>`)
    + miyaZona(takl)
    + boshlashKarta(d.boshlash)
    + (kpi ? `<section class="kpi">${kpi}</section>` : "")
    + (chap && ong ? `<div class="ustun2"><div class="ust">${chap}</div><div class="ust">${ong}</div></div>`
      : chap || ong ? `<div class="panjara">${chap}${ong}</div>` : "");
  miyaUlash(main);
  boshlashUlash(main);
  main.addEventListener("click", harakatTugmalari);
  main.addEventListener("click", vadaTugmalari);
  main.addEventListener("click", xulosaTugma);
  main.addEventListener("click", e => {
    const t = e.target.closest("[data-ish],[data-davomat]");
    if (!t) return;
    if (t.dataset.ish) return ishOyna(+t.dataset.ish);
    api(`/api/davomat/${t.dataset.davomat}/hal`, {body: {ha: t.dataset.ha === "1"}}).then(() => { xabar("Yozildi"); yonalish(); }).catch(x => xabar(x.message, true));
  });
  $("[data-a=yozuv]", main).addEventListener("click", () => yozuvOyna());
}

function qisqa(m) {
  const a = Math.abs(m);
  if (a >= 1e9) return (m / 1e9).toFixed(1).replace(".", ",").replace(",0", "") + " mlrd";
  if (a >= 1e6) return (m / 1e6).toFixed(1).replace(".", ",").replace(",0", "") + " mln";
  return guruh(m);
}

function diqqatManba(x) {
  if (x.tur !== "vada_bugun") return "";
  const m = x.manba;
  const ikon = {ovoz: "ti-microphone", rasm: "ti-photo", matn: "ti-message"}[m && m.tur] || "ti-pencil";
  const nom = m ? `${{ovoz: "Ovozli xabar", rasm: "Rasm", matn: "Yozma xabar", fayl: "Fayl"}[m.tur] || "Xabar"} · ${sanaMatn(m.sana)}${m.davomiylik ? ` · ${Math.floor(m.davomiylik / 60)}:${String(Math.round(m.davomiylik % 60)).padStart(2, "0")}` : ""}` : "Paneldan yozilgan";
  return `<div class="manbalar"><span class="chip"><i class="ti ${ikon}"></i>${H(nom)}</span>${x.ishonch && x.ishonch_kerak ? `<span class="chip ${x.ishonch_yaxshi ? "y" : "kut"}"><i class="ti ti-shield-check"></i>${H(bosHarf(x.ishonch))}</span>` : ""}</div>`;
}
const bosHarf = t => t ? t[0].toUpperCase() + t.slice(1) : "";

function diqqatTugma(x) {
  if (x.ish_id) return `<button class="btn kichik" data-ish="${x.ish_id}">Ochish</button>`;
  if (x.tur === "vada_bugun") {
    const eshit = x.manba && x.manba.tur === "ovoz" ? `<button class="btn ik kichik" data-eshit="${x.manba.xabar_id}" aria-label="Eshitish" title="Eshitish"><i class="ti ti-player-play"></i></button>` : "";
    if (x.vada_kim === "biz" || x.vada_tur === "boshqa") return eshit + `<button class="btn kichik" data-vyop="${x.vada_id}" data-ha="1">Bajarildi</button><button class="btn kichik" data-mijoz="${x.mijoz_id}">Ochish</button>`;
    const eslat = x.mijoz_botda ? `<button class="btn kichik" data-eslat="${x.vada_id}">Eslatish</button>` : "";
    return eshit + (eslat || `<button class="btn kichik" data-mijoz="${x.mijoz_id}">Ochish</button>`);
  }
  if (x.mijoz_id) return `<button class="btn kichik" data-mijoz="${x.mijoz_id}">Ochish</button>`;
  if (x.odam_id) return `<a class="btn kichik" href="#/ishlar">Ishlar</a>`;
  if (x.davomat_id && MEN.boshliq) return `<button class="btn kichik" data-davomat="${x.davomat_id}" data-ha="1">Tasdiqlash</button><button class="btn kichik xavf" data-davomat="${x.davomat_id}" data-ha="0">Rad</button>`;
  if (!x.harakat_id) return "";
  if (x.tur === "ruxsat" && MEN.boshliq) return `<button class="btn kichik" data-ruxsat="${x.harakat_id}" data-ha="1">Ruxsat</button><button class="btn kichik xavf" data-ruxsat="${x.harakat_id}" data-ha="0">Rad</button>`;
  if (x.tur === "nizo" && MEN.boshliq) return `<button class="btn kichik" data-nizo="${x.harakat_id}" data-ha="1">Berilgan</button><button class="btn kichik xavf" data-nizo="${x.harakat_id}" data-ha="0">Bekor</button>`;
  return `<button class="btn kichik" data-korish="${x.harakat_id}">Ko'rish</button>`;
}

function kutishQator(h) {
  const men = MEN.odam.id;
  let tug = "", izoh = "";
  if (h.holat === "ruxsat_kutilmoqda") {
    izoh = `Boshliq ruxsati kerak: ${h.qoida_buzilish || ""}`;
    if (MEN.boshliq) tug = `<button class="btn kichik" data-ruxsat="${h.id}" data-ha="1">Ruxsat</button><button class="btn kichik xavf" data-ruxsat="${h.id}" data-ha="0">Rad</button>`;
  } else {
    const kim = [];
    if (h.beruvchi_holat === "kutilmoqda") kim.push(`${h.beruvchi} «berdim»`);
    if (h.oluvchi_holat === "kutilmoqda") kim.push(`${h.oluvchi} «oldim»`);
    izoh = `${h.yozgan} yozdi · ${sanaMatn(h.voqea_sana)} · kutilmoqda: ${kim.join(", ")}`;
    if (h.oluvchi_holat === "kutilmoqda" && h.oluvchi_id === men) tug = `<button class="btn kichik" data-tomon="${h.id}" data-t="oluvchi" data-ha="1">Oldim</button><button class="btn kichik xavf" data-tomon="${h.id}" data-t="oluvchi" data-ha="0">Olmadim</button>`;
    else if (h.beruvchi_holat === "kutilmoqda" && h.beruvchi_id === men) tug = `<button class="btn kichik" data-tomon="${h.id}" data-t="beruvchi" data-ha="1">Berdim</button><button class="btn kichik xavf" data-tomon="${h.id}" data-t="beruvchi" data-ha="0">Bermadim</button>`;
    else tug = `<button class="btn kichik" data-korish="${h.id}">Ko'rish</button>`;
  }
  return `<div class="kutish"><div><b>${H(h.nom)} · ${H(h.dan)} → ${H(h.ga)}</b><small><i class="ti ti-hourglass"></i>${H(izoh)}</small></div>
    <div class="s raqam">${H(h.summa.t)}</div><div class="sa">${tug}</div></div>`;
}

async function harakatTugmalari(e) {
  const b = e.target.closest("[data-ruxsat],[data-nizo],[data-tomon],[data-korish]");
  if (!b) return;
  try {
    if (b.dataset.korish) return harakatOyna(+b.dataset.korish);
    b.disabled = true;
    if (b.dataset.ruxsat) await api(`/api/harakat/${b.dataset.ruxsat}/ruxsat`, {body: {ha: b.dataset.ha === "1"}});
    if (b.dataset.nizo) await api(`/api/harakat/${b.dataset.nizo}/nizo`, {body: {berilgan: b.dataset.ha === "1"}});
    if (b.dataset.tomon) await api(`/api/harakat/${b.dataset.tomon}/tomon`, {body: {tomon: b.dataset.t, ha: b.dataset.ha === "1"}});
    xabar("Yozildi");
    yonalish();
  } catch (x) { xabar(x.message, true); b.disabled = false; }
}

/* ---------- ishni boshlash (bo'sh tizim) — holat bazadan, hammasi bajarilgach karta yo'qoladi ---------- */
const BOSHLASH_TUGMA = {tg: "Ulash", xodim: "Qo'shish", kassa: "Yozish", mijoz: "Yozish", maosh: "Kiritish", ovoz: "Sozlash"};

function boshlashKarta(q) {
  if (!q) return "";
  try { if (localStorage.getItem("miya_boshlash_yop") === "1") return ""; } catch (e) { /* xotira yopiq */ }
  const bajarildi = q.filter(x => x.bajarildi).length;
  return `<section class="karta boshlash"><div class="kb"><h2>Ishni boshlash</h2><span class="soni">${bajarildi}/${q.length}</span>
      <span class="izoh">Hammasi bajarilgach bu karta o'zi yo'qoladi</span><button class="btn kichik" data-byop>Yashirish</button></div>
    <div class="chiz"><i style="width:${Math.round(bajarildi / q.length * 100)}%;background:var(--urgu)"></i></div>
    <ol class="qadam">${q.map(x => `<li class="${x.bajarildi ? "ok" : ""}"><i class="ti ti-${x.bajarildi ? "circle-check-filled" : "circle-dashed"}"></i>
      <div><b>${H(x.nom)}</b><small>${H(x.misol && !x.bajarildi ? `${x.izoh}: «${x.misol}»` : x.izoh)}</small></div>
      ${x.bajarildi ? `<span class="chip y">bajarildi</span>` : `<button class="btn kichik" data-qadam="${x.k}" data-misol="${H(x.misol || "")}">${BOSHLASH_TUGMA[x.k]}</button>`}</li>`).join("")}</ol></section>`;
}

function boshlashUlash(main) {
  const k = $(".boshlash", main);
  if (!k) return;
  k.addEventListener("click", e => {
    if (e.target.closest("[data-byop]")) {
      try { localStorage.setItem("miya_boshlash_yop", "1"); } catch (er) { /* xotira yopiq */ }
      k.remove();
      return;
    }
    const b = e.target.closest("[data-qadam]");
    if (!b) return;
    const q = b.dataset.qadam;
    if (q === "tg") return tgHavolaOyna(MEN.odam);
    if (q === "kassa" || q === "mijoz") {  // misol miya qatoriga yoziladi — raqamni almashtirib Enter bosiladi
      const t = $("#savol");
      if (!t || t.disabled) return xabar("Avval Sozlamalarda sun'iy intellekt kalitini kiriting", true);
      t.value = b.dataset.misol;
      t.dispatchEvent(new Event("input"));
      t.focus();
      t.setSelectionRange(t.value.length, t.value.length);
      t.closest(".miya").scrollIntoView({block: "start", behavior: "smooth"});
      return xabar("Raqam va ismlarni o'zingiznikiga almashtirib, Enter bosing");
    }
    location.hash = {xodim: "#/xodimlar", maosh: "#/maosh", ovoz: "#/sozlamalar"}[q];
  });
}

/* ---------- miya (savol ham, topshiriq ham) ---------- */
const ASBOB_NOMI = {mening_hisobim: "Mening hisobim", xodim_hisobi: "Maosh varaqasi", davr_jami: "Davr hisoboti",
  maosh_bashorati: "Maosh bashorati", tolash_kerak: "To'lash kerak", kassalar: "Kassalar", mijoz_qarzlari: "Mijozlar qarzi", yozuvlar: "Yozuvlar",
  mijoz_haqida: "Mijoz kartasi", vadalar: "Va'dalar", ishlar: "Ishlar", davomat: "Davomat", xabar_qidir: "Eski xabarlar", ish_usuli: "Ish usullari",
  xabarlar: "Kim nima yozdi", xotira: "Xotira"};

const MISOL_GAP = {boshliq: "Rustamga 10 ta kamera, Akmal ertaga borsin", menejer: "Rustamga 10 ta kamera, Akmal ertaga borsin",
  kassir: "Akmalga 500 ming avans berdim", xodim: "Benzinga 100 ming o'z pulimdan ishlatdim"};

function miyaZona(takl) {
  const yoq = !MEN.xizmat.ai;
  return `<section class="miya"><form class="mq" id="mq"><span class="orb" id="orb"><i></i></span>
      <label><small>${yoq ? "Sun'iy intellekt hali yoqilmagan — Sozlamalarda kalitni kiriting" : "Savol yoki topshiriq yozing"}</small>
      <textarea id="savol" rows="1" placeholder="${H(MISOL_GAP[MEN.odam.rol] || MISOL_GAP.boshliq)}" autocomplete="off" ${yoq ? "disabled" : ""} maxlength="1500"></textarea></label>
      <button class="mik" type="submit" aria-label="Yuborish" ${yoq ? "disabled" : ""}><i class="ti ti-arrow-up"></i></button></form>
      <div class="takl">${takl.map(t => `<button type="button" data-takl="${H(t)}" ${yoq ? "disabled" : ""}><i class="ti ti-sparkles"></i>${H(t)}</button>`).join("")}</div>
      <div id="javob"></div></section>`;
}

function miyaUlash(main) {
  const forma = $("#mq", main);
  if (!forma) return;
  const maydon = $("#savol", forma), tugma = $(".mik", forma);
  const osir = () => {  // yozilgan sari o'sadi (160 px dan keyin — aylantiriladi)
    maydon.style.height = "auto";
    maydon.style.height = Math.min(Math.max(maydon.scrollHeight, 28), 160) + "px";
    maydon.style.overflowY = maydon.scrollHeight > 160 ? "auto" : "hidden";
  };
  maydon.addEventListener("input", osir);
  maydon.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); forma.requestSubmit(); } });
  let band = false;
  const sora = async matn => {
    if (!matn.trim() || band) return;
    band = true; tugma.disabled = true;
    maydon.value = matn; osir();
    $("#orb").classList.add("oylaydi");
    $("#javob").innerHTML = `<div class="javob"><p>O'ylayapman…</p></div>`;
    try {
      const r = await api("/api/miya", {body: {matn}});
      if (r.tur === "takliflar") return await takliflarChiz(r.takliflar, $("#javob"), null, r.xotira || []);
      if (r.tur === "xotira") { $("#javob").innerHTML = `<div class="javob"><div class="mt-r" style="margin:0">${eslabHtml(r.xotira)}</div></div>`; maydon.value = ""; osir(); return; }
      if (r.tur === "tushunilmadi") {
        $("#javob").innerHTML = `<div class="javob"><p>${H(r.sabab)}</p><div class="manba"><span class="chip"><i class="ti ti-bulb"></i>Masalan: «Akmal ertaga Rustamga 10 ta kamera o'rnatsin» yoki «Dilshodga qancha qarzmiz?»</span></div></div>`;
        return;
      }
      const manba = r.manbalar.map(m => `<span class="chip u"><i class="ti ti-database"></i>${H(ASBOB_NOMI[m.asbob] || m.asbob)}</span>`).join("");
      $("#javob").innerHTML = `<div class="javob"><p>${H(r.javob)}</p>${manba || r.qolip ? `<div class="manba">${manba}${r.qolip ? `<span class="chip kut"><i class="ti ti-calculator"></i>Raqamlar to'g'ridan-to'g'ri daftardan</span>` : `<span class="chip y"><i class="ti ti-calculator"></i>Hisobni dastur qildi</span>`}</div>` : ""}</div>`;
    } catch (x) {
      $("#javob").innerHTML = `<div class="javob"><p>${H(x.message)}</p></div>`;
    } finally { band = false; tugma.disabled = false; $("#orb").classList.remove("oylaydi"); }
  };
  forma.addEventListener("submit", e => { e.preventDefault(); sora(maydon.value); });
  $$("[data-takl]", main).forEach(b => b.addEventListener("click", () => sora(b.dataset.takl)));
}

/* Miya gapdan ajratgan narsalar — tahrirlanadigan kartochkalar. Hech narsa o'zi yozilmaydi: «Tasdiqlash» bosilganda
   oddiy panel API'lari chaqiriladi (yozuv qo'shish, ish berish oynalari bilan bir xil qoidalar). */
const KARTA_TUR = {pul: ["ti-cash", "Pul"], ish: ["ti-tool", "Ish"], vada: ["ti-heart-handshake", "Va'da"], eslatma: ["ti-note", "Mijoz haqida eslatma"],
  bajarildi: ["ti-circle-check", "Ish tugadi"], buyurtma: ["ti-clipboard-list", "Buyurtma"]};
// buyurtma kartochkasi: qator summasi va jami — faqat ko'rsatish uchun (yozilganda server qayta hisoblaydi)
const bkPul = (n, v) => v === "USD" ? `${(Math.round(n * 100) / 100).toLocaleString("ru-RU")} $` : `${guruh(n)} so'm`;
const bkJami = c => c.qatorlar.reduce((a, q) => a + (+q.miqdor || 0) * (+q.narx || 0), 0);
const tOpt = (v, t, s) => `<option value="${H(v)}"${s ? " selected" : ""}>${H(t)}</option>`;
const tMaydon = (nom, ichki, cls = "keng") => `<label class="maydon ${cls}"><span>${nom}</span>${ichki}</label>`;
const tSumma = (s, v) => s ? (v === "USD" ? String(s) : guruh(s)) : "";
const tValyuta = v => tMaydon("Valyuta", `<select name="valyuta">${tOpt("UZS", "so'm", v !== "USD")}${tOpt("USD", "dollar", v === "USD")}</select>`, "");
const tQoshimcha = (nom, ichki, ochiq) => `<details class="mk-q butun"${ochiq ? " open" : ""}><summary>${nom}</summary><div class="forma">${ichki}</div></details>`;

function mijozOpt(r, royxat, tur, majburiy) {
  const so = tur === "taminotchi" ? "ta'minotchi" : "mijoz";
  const id = r && r.id, nomz = (r && r.nomzodlar) || [];
  const yarata = MEN.boshliq || MEN.huquq.mijoz_qarz;  // yangi mijozni faqat ruxsati borlar qo'shadi
  const yangiBosh = yarata && r && !id && r.yangi && !nomz.length;
  let h = tOpt("", majburiy ? "— tanlang —" : `— ${so}siz —`, !id && !yangiBosh);
  if (yarata && r && r.yangi && (!id || r.taxmin)) h += tOpt(`yangi:${r.yangi}`, `+ Yangi ${so}: ${r.yangi}`, yangiBosh);
  if (id && !royxat.some(x => x.id === id)) h += tOpt(id, r.ism, true);  // xodimga ro'yxat yuklanmaydi
  if (nomz.length) h += `<optgroup label="O'xshash ismlar">${nomz.map(x => tOpt(x.id, x.ism, false)).join("")}</optgroup>`;
  if (royxat.length) h += `<optgroup label="Hammasi">${royxat.map(x => tOpt(x.id, x.ism, x.id === id)).join("")}</optgroup>`;
  return `<select name="mijoz_id">${h}</select>${r && r.taxmin ? `<small class="ogoh">«${H(r.aytilgan)}» — ${H(r.ism)} deb oldim, to'g'rimi?</small>` : nomz.length && !id ? `<small class="ogoh">«${H(r.aytilgan)}» — bir nechta o'xshash, tanlang</small>` : ""}`;
}

function odamOpt(r, odamlar) {
  const id = r && r.id;
  return `<select name="odam_id">${tOpt("", "— tanlang —", !id)}${odamlar.map(x => tOpt(x.id, x.ism, id === x.id)).join("")}</select>${r && r.taxmin ? `<small class="ogoh">«${H(r.aytilgan)}» — ${H(r.ism)} deb oldim, to'g'rimi?</small>` : r && !id ? `<small class="ogoh">«${H(r.aytilgan)}» — ${(r.nomzodlar || []).length ? "bir nechta o'xshash" : "topilmadi"}, tanlang</small>` : ""}`;
}

function kartaHtml(c, m) {
  const [ik, nom] = KARTA_TUR[c.tur];
  const bosh = `<div class="mk-b"><i class="ti ${ik}"></i><b>${H(nom)}</b>${c.iqtibos ? `<q>${H(c.iqtibos)}</q>` : "<q></q>"}<button type="button" class="btn ik kichik" data-olib aria-label="Olib tashlash"><i class="ti ti-x"></i></button></div>`;
  let ich = "";
  if (c.tur === "pul") {
    const turlar = Object.entries(TUR).filter(([, t]) => !t.rol || t.rol.includes(MEN.odam.rol));
    let f = [...TUR[c.harakat_tur].f];
    if (c.harakat_tur === "chiqim" && c.qoldan) f = ["odam", "xarajat_turi"];
    const kassaOpt = v => m.kassalar.map(k => `<option value="${k.id}" data-v="${k.valyuta}" ${v === k.id ? "selected" : ""}>${H(k.nom)} (${k.valyuta})</option>`).join("");
    const xt = (c.xarajat_turi || "").trim(), xtBor = m.xarajat.find(x => x.nom.toLowerCase() === xt.toLowerCase());
    const maydon = {
      kassa: () => tMaydon("Kassa", `<select name="kassa_id">${kassaOpt(c.kassa_id)}</select>`),
      kassa2: () => tMaydon("Qaysi kassaga", `<select name="kassa2_id">${kassaOpt(null)}</select>`),
      odam: () => tMaydon("Xodim", odamOpt(c.odam, m.odamlar)),
      sotuvchi: () => tMaydon("Kim sotdi", `<select name="sotuvchi_id"><option value="">—</option>${m.odamlar.map(x => tOpt(x.id, x.ism, false)).join("")}</select>`),
      "mijoz?": () => tMaydon("Mijoz", mijozOpt(c.mijoz, m.mijozlar, "mijoz", false)),
      mijoz: () => tMaydon("Mijoz", mijozOpt(c.mijoz, m.mijozlar, "mijoz", true)),
      taminotchi: () => tMaydon("Ta'minotchi", mijozOpt(c.mijoz, m.taminotchilar, "taminotchi", true)),
      xarajat_turi: () => tMaydon("Xarajat turi", `<select name="xarajat_turi">${xt && !xtBor ? tOpt(`nom:${xt}`, `+ Yangi tur: ${xt}`, true) : ""}${m.xarajat.map(x => tOpt(x.id, x.nom, xtBor && xtBor.id === x.id)).join("")}</select>`),
      tolandi: () => tMaydon("Hozir to'landi", `<input type="text" name="tolandi" inputmode="decimal" value="${H(tSumma(c.tolandi, c.valyuta))}" placeholder="0">`, ""),
      muddat: () => tMaydon("Qarz muddati", `<input type="date" name="muddat" value="${H(c.muddat || "")}" min="${MEN.bugun}">`),
    };
    const sana = c.sana || MEN.bugun;
    ich = `${tMaydon("Nima bo'ldi?", `<select name="harakat_tur">${turlar.map(([k, t]) => tOpt(k, t.nom, k === c.harakat_tur)).join("")}</select>`)}
      ${tMaydon("Summa", `<input type="text" name="summa" inputmode="decimal" value="${H(tSumma(c.summa, c.valyuta))}" placeholder="500 000">`, "")}
      ${tValyuta(c.valyuta)}
      ${c.birlik_noaniq ? `<small class="ogoh butun">Ming yoki million — aniq aytilmagan, summani tekshiring</small>` : ""}
      ${c.harakat_tur === "chiqim" ? tMaydon("Qaysi puldan", `<select name="qoldan">${tOpt("", "Kassadan", !c.qoldan)}${tOpt("1", "Xodim qo'lidagi puldan", c.qoldan)}</select>`) : ""}
      ${f.map(x => maydon[x]()).join("")}
      ${tQoshimcha(sana === MEN.bugun ? "Sana: bugun · izoh" : `Sana: ${sanaMatn(sana)} · izoh`,
        `${tMaydon("Sana", `<input type="date" name="sana" value="${H(sana)}" max="${MEN.bugun}">`)}${tMaydon("Izoh", `<input type="text" name="izoh" maxlength="300" value="${H(c.izoh)}">`, "butun")}`, !!c.izoh)}
      ${c.ruxsat ? "" : `<small class="ogoh butun">Bu turdagi yozuvni faqat boshliq kiritadi</small>`}`;
  } else if (c.tur === "ish") {
    if (!c.tanlangan) c.tanlangan = new Set(c.ijrochilar.map(x => x.id));
    const taklif = c.taklif.length ? c.taklif : m.odamlar.map(x => ({odam_id: x.id, ism: x.ism, qilgan: 0, ochiq: 0}));
    ich = `${tMaydon("Ish", `<input type="text" name="nom" maxlength="200" value="${H(c.nom)}">`, "butun")}
      <div class="maydon butun"><span>Kim bajaradi</span><div class="tanlov">${taklif.map(x => `<button type="button" class="btn kichik ${c.tanlangan.has(x.odam_id) ? "asosiy" : ""}" data-ijr="${x.odam_id}">${H(x.ism)}${x.qilgan ? ` · ${x.qilgan} marta` : ""} · ${x.ochiq} ish</button>`).join("")}</div>${c.ijrochilar.some(x => x.taxmin) ? `<small class="ogoh">${H(c.ijrochilar.filter(x => x.taxmin).map(x => `«${x.aytilgan}» — ${x.ism}`).join(", "))} deb oldim, to'g'rimi?</small>` : ""}${c.nomalum.length ? `<small class="ogoh">Aniq emas: ${H(c.nomalum.map(x => x.aytilgan).join(", "))} — ro'yxatdan tanlang</small>` : !c.tanlangan.size ? `<small class="ogoh">Kim bajarishini tanlang</small>` : ""}</div>
      ${tMaydon("Mijoz", mijozOpt(c.mijoz, m.mijozlar, "mijoz", false))}
      ${tMaydon("Muddat", `<input type="date" name="muddat" value="${H(c.muddat || "")}">`)}
      ${c.ruxsat ? `${tMaydon("Narx", `<input type="text" name="narx" inputmode="decimal" value="${H(tSumma(c.narx, c.valyuta))}" placeholder="—">`, "")}${tValyuta(c.valyuta)}` : ""}
      ${tQoshimcha(c.joy || c.soat ? `Manzil: ${c.joy || "—"}${c.soat ? ` · soat ${c.soat}` : ""}` : "Manzil · soat", `${tMaydon("Manzil", `<input type="text" name="joy" maxlength="200" value="${H(c.joy)}">`)}${tMaydon("Soat", `<input type="time" name="soat" value="${H(c.soat)}">`, "")}`, false)}
      <input type="hidden" name="ish_turi" value="${H(c.ish_turi)}"><input type="hidden" name="dalil_turi" value="${H(c.dalil)}">`;
  } else if (c.tur === "vada") {
    ich = `${tMaydon("Mijoz", mijozOpt(c.mijoz, m.mijozlar, "mijoz", true))}
      ${tMaydon("Kim va'da berdi", `<select name="kim">${tOpt("mijoz", "Mijoz", c.kim !== "biz")}${tOpt("biz", "Biz", c.kim === "biz")}</select>`, "")}
      ${tMaydon("Nima", `<select name="vtur">${tOpt("tolov", "Pul to'lash", c.vtur === "tolov")}${tOpt("boshqa", "Boshqa ish", c.vtur !== "tolov")}</select>`, "")}
      ${c.vtur === "tolov" ? `${tMaydon("Summa", `<input type="text" name="summa" inputmode="decimal" value="${H(tSumma(c.summa, c.valyuta))}" placeholder="—">`, "")}${tValyuta(c.valyuta)}
      ${c.izoh ? `<small class="butun">${H(c.izoh)}</small>` : !c.summa ? `<small class="ogoh butun">Qancha to'laydi — summani yozing</small>` : ""}` : ""}
      ${tMaydon("Qachongacha", `<input type="date" name="muddat" value="${H(c.muddat || "")}">`)}
      ${tMaydon(c.vtur === "tolov" ? "Izoh" : "Nima qilinadi", `<input type="text" name="matn" maxlength="300" value="${H(c.matn)}">`, "butun")}`;
  } else if (c.tur === "buyurtma") {
    const v = c.valyuta, kat = m.katalog || [];
    const katOpt = (q, j) => {
      const nz = new Set((q.nomzodlar || []).map(x => x.id));
      return `<select name="q${j}_kid" aria-label="Katalogdan tanlash">${tOpt("", q.katalog_id ? "✎ Erkin qator" : `✎ ${q.nom || "Erkin qator"} — katalogda yo'q`, !q.katalog_id)}${nz.size ? `<optgroup label="O'xshash">${kat.filter(k => nz.has(k.id)).map(k => tOpt(k.id, `${k.nom} · ${k.narx.t}`, false)).join("")}</optgroup>` : ""}${kat.length ? `<optgroup label="Katalog">${kat.map(k => tOpt(k.id, `${k.nom} · ${k.narx.t}`, k.id === q.katalog_id)).join("")}</optgroup>` : ""}</select>`;
    };
    ich = `${tMaydon("Mijoz", mijozOpt(c.mijoz, m.mijozlar, "mijoz", true))}
      <div class="maydon butun"><span>Nima kerak</span><div class="bk-q">${c.qatorlar.map((q, j) => `<div class="bk-r">
        <div class="bk-n">${katOpt(q, j)}${q.katalog_id ? "" : `<input type="text" name="q${j}_nom" maxlength="200" value="${H(q.nom)}" placeholder="Nomi" aria-label="Qator nomi">`}${!q.katalog_id && (q.nomzodlar || []).length ? `<small class="ogoh">«${H(q.aytilgan)}» — bir nechta o'xshash, ro'yxatdan tanlang</small>` : ""}</div>
        <input type="text" name="q${j}_miqdor" inputmode="decimal" value="${+q.miqdor || ""}" placeholder="1" aria-label="Miqdor"><span class="bk-b">${H(q.birlik || "dona")} ×</span>
        <input type="text" name="q${j}_narx" inputmode="decimal" value="${H(tSumma(q.narx, v))}" placeholder="narx" aria-label="Bir donasi narxi">
        <b class="raqam bk-s" data-j="${j}">${bkPul((+q.miqdor || 0) * (+q.narx || 0), v)}</b>
        <button type="button" class="btn ik kichik" data-bqdel="${j}" aria-label="Qatorni olib tashlash"><i class="ti ti-trash"></i></button></div>`).join("")}</div>
        <div class="bk-p"><button type="button" class="btn kichik" data-bqqosh><i class="ti ti-plus"></i>Qator</button><span>Jami: <b class="raqam bk-j">${bkPul(bkJami(c), v)}</b></span></div>
        ${c.qatorlar.some(q => !q.narx) ? `<small class="ogoh">Narxi yo'q qator bor — narxni yozing yoki keyin buyurtmada to'ldiring</small>` : ""}</div>
      ${tQoshimcha(c.manzil || c.muddat ? `Manzil: ${c.manzil || "—"}${c.muddat ? ` · ${sanaMatn(c.muddat)} gacha` : ""}` : "Manzil · muddat · izoh",
        `${tMaydon("Manzil", `<input type="text" name="manzil" maxlength="300" value="${H(c.manzil)}">`)}${tMaydon("Qachonga kerak", `<input type="date" name="muddat" value="${H(c.muddat || "")}">`)}${tMaydon("Izoh", `<input type="text" name="izoh" maxlength="300" value="${H(c.izoh)}">`, "butun")}`, !!c.izoh)}`;
  } else if (c.tur === "bajarildi") {
    ich = `${tMaydon("Qaysi ish", `<select name="ish_id">${tOpt("", "— tanlang —", !c.ish_id)}${c.ochiq.map(i => tOpt(i.id, `#${i.id} ${i.nom}${i.ijrochilar ? ` — ${i.ijrochilar}` : ""}`, i.id === c.ish_id)).join("")}</select>${!c.ish_id ? `<small class="ogoh">«${H(c.aytilgan)}» — ochiq ishlardan tanlang</small>` : ""}`, "butun")}
      ${tMaydon("Izoh", `<input type="text" name="izoh" maxlength="300" value="${H(c.izoh)}">`, "butun")}
      ${c.ruxsat ? "" : `<small class="ogoh butun">Ishni Telegram botda rasm bilan yopasiz</small>`}`;
  } else {
    ich = `${tMaydon("Mijoz", mijozOpt(c.mijoz, m.mijozlar, "mijoz", true))}
      ${tMaydon("Eslatma", `<input type="text" name="matn" maxlength="300" value="${H(c.matn)}">`, "butun")}`;
  }
  return `${bosh}<div class="forma">${ich}</div><div class="xato-m"></div>`;
}

/* joy — qayerga chiziladi (bosh sahifa: #javob; chat: miya xabari ichi); tugadi(natijalar|null) — chat uchun:
   berilsa sahifa yangilanmaydi, natija chaqiruvchiga qaytadi. eslab — shu gapdan darhol saqlangan xotira matnlari. */
const eslabHtml = eslab => (eslab || []).map(x => `<div class="mk ok esl"><i class="ti ti-bookmark"></i><b>${H(x.matn)}</b></div>`).join("");

async function takliflarChiz(kartalar, joy = $("#javob"), tugadi = null, eslab = []) {
  const m = await malumotlar();
  if (kartalar.some(c => c.tur === "buyurtma") && !m.katalog) m.katalog = (await api("/api/katalog")).katalog;
  joy.innerHTML = `<div class="javob mt">${eslab.length ? `<div class="mt-r" style="margin:0 0 12px">${eslabHtml(eslab)}</div>` : ""}<p class="mt-bosh">${kartalar.length === 1 ? "Shuni tushundim" : `${kartalar.length} ta narsa tushundim`} — tekshirib, tasdiqlang</p>
    <div class="mt-r">${kartalar.map((_, i) => `<form class="mk" data-i="${i}" novalidate></form>`).join("")}</div>
    <div class="mt-past"><button type="button" class="btn" id="mtbekor">Bekor</button><button type="button" class="btn asosiy" id="mtok"><i class="ti ti-check"></i><span></span></button></div></div>`;
  const mt = $(".mt", joy);
  const forma = i => $(`.mk[data-i="${i}"]`, mt);
  const ok = $("#mtok", mt);
  const qolgan = () => kartalar.filter(c => !c.olib && !c.tayyor && c.ruxsat !== false);
  const yorliq = () => { const n = qolgan().length; ok.hidden = !n; $("span", ok).textContent = n > 1 ? `Hammasini tasdiqlash (${n})` : "Tasdiqlash"; };
  const chiz = i => { forma(i).innerHTML = kartaHtml(kartalar[i], m); forma(i).classList.toggle("yoq", kartalar[i].ruxsat === false); };
  const oqi = i => { const c = kartalar[i], d = Object.fromEntries(new FormData(forma(i))); for (const k of ["summa", "tolandi", "narx"]) if (k in d) c[k] = sonOqi(d[k]); for (const k of ["valyuta", "sana", "muddat", "izoh", "nom", "joy", "soat", "matn", "kim", "vtur", "manzil"]) if (k in d) c[k] = d[k]; if ("ish_id" in d) c.ish_id = +d.ish_id || null;
    if (c.tur === "buyurtma") c.qatorlar.forEach((q, j) => { if (`q${j}_miqdor` in d) q.miqdor = sonOqi(d[`q${j}_miqdor`]); if (`q${j}_narx` in d) q.narx = sonOqi(d[`q${j}_narx`]); if (`q${j}_nom` in d) q.nom = d[`q${j}_nom`]; });
    return d; };
  kartalar.forEach((_, i) => chiz(i));
  yorliq();
  mt.addEventListener("submit", e => e.preventDefault());  // Enter sahifani qayta yuklamasin
  mt.addEventListener("change", e => {
    const f = e.target.closest(".mk"); if (!f) return;
    const i = +f.dataset.i, c = kartalar[i];
    if (["harakat_tur", "qoldan", "vtur"].includes(e.target.name)) {
      oqi(i);
      if (e.target.name === "harakat_tur") { c.harakat_tur = e.target.value; c.ruxsat = true; } else if (e.target.name === "qoldan") c.qoldan = !!e.target.value;
      chiz(i);
    } else if (e.target.name === "kassa_id" && e.target.selectedOptions[0]) f.valyuta.value = e.target.selectedOptions[0].dataset.v;
    else if (/^q\d+_kid$/.test(e.target.name)) {  // buyurtma qatori katalogdan tanlandi — nom, birlik, narx katalogdan
      oqi(i);
      const q = c.qatorlar[parseInt(e.target.name.slice(1))], k = (m.katalog || []).find(x => x.id === +e.target.value);
      if (k) { q.katalog_id = k.id; q.nom = k.nom; q.birlik = k.birlik; if (k.valyuta === c.valyuta) q.narx = k.valyuta === "USD" ? k.narx.m / 100 : k.narx.m; } else q.katalog_id = null;
      chiz(i);
    }
  });
  mt.addEventListener("input", e => {  // buyurtma: qator summasi va jami yozish paytida (qayta chizmasdan — fokus qoladi)
    const f = e.target.closest(".mk"); if (!f || kartalar[+f.dataset.i].tur !== "buyurtma") return;
    const i = +f.dataset.i, c = kartalar[i];
    oqi(i);
    $$(".bk-s", f).forEach(b => { const q = c.qatorlar[+b.dataset.j]; b.textContent = bkPul((+q.miqdor || 0) * (+q.narx || 0), c.valyuta); });
    $(".bk-j", f).textContent = bkPul(bkJami(c), c.valyuta);
  });
  mt.addEventListener("click", e => {
    const f = e.target.closest(".mk");
    if (f && e.target.closest("[data-olib]")) {
      kartalar[+f.dataset.i].olib = true; f.remove(); yorliq();
      if (!qolgan().length) {
        if (tugadi) return tugadi(kartalar.filter(c => c.tayyor).map(c => c.tayyor));
        joy.innerHTML = kartalar.some(c => c.tayyor) ? "" : `<div class="javob"><p>Hech narsa yozilmadi</p></div>`;
      }
      return;
    }
    const bq = e.target.closest("[data-bqdel],[data-bqqosh]");
    if (f && bq) {
      const i = +f.dataset.i, c = kartalar[i];
      oqi(i);
      if (bq.dataset.bqdel !== undefined) c.qatorlar.splice(+bq.dataset.bqdel, 1);
      else c.qatorlar.push({katalog_id: null, nom: "", aytilgan: "", birlik: "dona", miqdor: 1, narx: 0, nomzodlar: []});
      chiz(i);
      return;
    }
    const b = e.target.closest("[data-ijr]");
    if (f && b) { const c = kartalar[+f.dataset.i], id = +b.dataset.ijr; oqi(+f.dataset.i); c.tanlangan.has(id) ? c.tanlangan.delete(id) : c.tanlangan.add(id); chiz(+f.dataset.i); }
  });
  $("#mtbekor", mt).addEventListener("click", () => {
    if (tugadi) return tugadi(kartalar.filter(c => c.tayyor).map(c => c.tayyor));
    joy.innerHTML = ""; $("#savol").value = "";
  });

  const yangi = {};  // bir xil yangi mijoz ikki kartochkada bo'lsa — bir marta yaratiladi
  const mijozId = async (v, tur) => {
    if (!v) return null;
    if (!v.startsWith("yangi:")) return +v;
    const ism = v.slice(6), k = `${tur}:${ism.toLowerCase()}`;
    if (!yangi[k]) yangi[k] = (await api("/api/mijoz", {body: {ism, tur}})).id;
    return yangi[k];
  };
  const tayyor = (i, matn) => {
    const c = kartalar[i]; c.tayyor = matn;
    forma(i).outerHTML = `<div class="mk ok"><i class="ti ti-circle-check"></i><b>${H(matn)}</b></div>`;
  };
  const yoz = async i => {
    const c = kartalar[i], f = forma(i), d = oqi(i), x = $(".xato-m", f);
    x.textContent = "";
    if (c.tur === "pul") {
      if (!c.ruxsat) throw new Error("Bu turdagi yozuvni faqat boshliq kiritadi");
      if (!c.summa) throw new Error("Summani raqam bilan yozing");
      const tur = d.harakat_tur, b = {tur, summa: c.summa, valyuta: d.valyuta, sana: d.sana, izoh: d.izoh || undefined};
      for (const k of ["kassa_id", "kassa2_id", "odam_id", "sotuvchi_id"]) if (d[k]) b[k] = +d[k];
      const mTur = ["taminotchi_nasiya", "taminotchiga_tolov", "boshlangich_taminotchi"].includes(tur) ? "taminotchi" : "mijoz";
      if ((TUR[tur].f.includes("odam") || d.qoldan) && !b.odam_id) throw new Error("Xodimni tanlang");
      if (TUR[tur].f.some(k => k.startsWith("mijoz") || k === "taminotchi")) {
        if (!d.mijoz_id && TUR[tur].f.some(k => k === "mijoz" || k === "taminotchi")) throw new Error(mTur === "taminotchi" ? "Ta'minotchini tanlang" : "Mijozni tanlang");
        const mid = await mijozId(d.mijoz_id, mTur); if (mid) b.mijoz_id = mid;
      }
      if (d.xarajat_turi) { if (d.xarajat_turi.startsWith("nom:")) b.xarajat_turi = d.xarajat_turi.slice(4); else b.xarajat_turi_id = +d.xarajat_turi; }
      if (d.qoldan) b.qoldan = true;
      if (c.tolandi) b.tolandi = c.tolandi;
      if (d.muddat) b.muddat = d.muddat;
      const yubor = async (qosh = {}) => {
        const r = await api("/api/harakat", {body: {...b, ...qosh}});
        if (r.holat === "takror") {
          const t = r.takrorlar[0];
          x.innerHTML = `<div class="kutish" style="margin:6px 0 0"><div><b>Shunga o'xshash yozuv bor</b><small>${H(t.tavsif)} · ${sanaMatn(t.voqea_sana)} · ${H(t.yozgan)}</small></div><div></div>
            <div class="sa"><button type="button" class="btn kichik" data-bir>Ha, o'sha</button><button type="button" class="btn kichik" data-bosh>Yo'q, boshqa</button></div></div>`;
          x.scrollIntoView({block: "center", behavior: "smooth"});
          return new Promise((ok_, yoq) => {
            $("[data-bir]", x).onclick = async () => { try { await api(`/api/harakat/${r.id}/birlashtir`, {body: {eski_id: t.id}}); ok_("Ikkalasi bitta qilindi"); } catch (er) { yoq(er); } };
            $("[data-bosh]", x).onclick = async () => { try { await api(`/api/harakat/${r.id}/bekor`, {body: {sabab: "qayta kiritildi"}}).catch(() => {}); ok_(await yubor({takror_emas: true})); } catch (er) { yoq(er); } };
          });
        }
        return `${r.harakat.tavsif || TUR[tur].nom}${r.holat === "ruxsat_kutilmoqda" ? " — boshliq ruxsatini kutmoqda" : [r.harakat.beruvchi_holat, r.harakat.oluvchi_holat].includes("kutilmoqda") ? " — yozildi, tasdiq kutmoqda" : " — yozildi"}`;
      };
      return tayyor(i, await yubor());
    }
    if (c.tur === "ish") {
      if (!(d.nom || "").trim()) throw new Error("Ish nomini yozing");
      if (!c.tanlangan.size) throw new Error("Kim bajarishini tanlang");
      const b = {nom: d.nom, ijrochilar: [...c.tanlangan].map(id => ({odam_id: id, ulush: 1})), joy: d.joy || null, muddat: d.muddat || null,
        soat: d.soat || null, narx: d.narx ? sonOqi(d.narx) : null, valyuta: d.valyuta || "UZS", ish_turi: d.ish_turi || null, dalil_turi: d.dalil_turi || null,
        mijoz_id: await mijozId(d.mijoz_id, "mijoz")};
      const r = await api("/api/ish", {body: b});
      return tayyor(i, `Ish #${r.id} «${d.nom}» berildi — ijrochiga Telegram'da boradi`);
    }
    if (c.tur === "bajarildi") {
      if (!c.ruxsat) throw new Error("Ishni Telegram botda rasm bilan yopasiz");
      if (!c.ish_id) throw new Error("Qaysi ish — tanlang");
      const r = await api(`/api/ish/${c.ish_id}/amal`, {body: {amal: "bajarildi", izoh: d.izoh || null}});
      return tayyor(i, `Ish #${r.id} «${r.nom}» bajarildi deb belgilandi`);
    }
    if (!d.mijoz_id) throw new Error("Mijozni tanlang");
    if (c.tur === "buyurtma") {
      const qatorlar = c.qatorlar.filter(q => (q.nom || "").trim());
      if (!qatorlar.length) throw new Error("Kamida bitta qator yozing");
      if (qatorlar.some(q => !(q.miqdor > 0))) throw new Error("Miqdorni yozing");
      const r = await api("/api/buyurtma", {body: {mijoz_id: await mijozId(d.mijoz_id, "mijoz"), valyuta: c.valyuta, manzil: d.manzil || null,
        muddat: d.muddat || null, izoh: d.izoh || null,
        qatorlar: qatorlar.map(q => ({katalog_id: q.katalog_id || null, nom: q.nom.trim(), birlik: q.birlik, miqdor: q.miqdor, narx: q.narx || 0}))}});
      return tayyor(i, `Buyurtma #${r.id} yaratildi — ${r.jami.t}${MEN.boshliq ? "" : " · boshliqqa xabar berildi"}`);
    }
    if (c.tur === "vada") {
      if (d.vtur === "tolov" && !c.summa) throw new Error("Qancha to'laydi — summani yozing");
      if (!d.muddat) throw new Error("Qachongacha — sanani tanlang");
      const mid = await mijozId(d.mijoz_id, "mijoz");
      await api("/api/vada", {body: {mijoz_id: mid, kim: d.kim, tur: d.vtur, summa: d.vtur === "tolov" ? c.summa : null, valyuta: d.valyuta, muddat: d.muddat, matn: d.matn || null}});
      return tayyor(i, `Va'da yozildi — ${sanaMatn(d.muddat)} kuni eslatiladi`);
    }
    if (!(d.matn || "").trim()) throw new Error("Eslatma matnini yozing");
    const mid = await mijozId(d.mijoz_id, "mijoz");
    await api(`/api/mijoz/${mid}/eslatma`, {body: {matn: d.matn}});
    return tayyor(i, "Eslatma mijoz kartasiga yozildi");
  };
  ok.addEventListener("click", async () => {
    ok.disabled = true;
    let xato = 0;
    for (let i = 0; i < kartalar.length; i++) {  // tartib muhim: avval pul, keyin va'da (to'lov va'dadan oldin tushadi)
      const c = kartalar[i];
      if (c.olib || c.tayyor || c.ruxsat === false) continue;  // huquqi yo'q kartochka — faqat ma'lumot
      try { await yoz(i); } catch (er) { xato++; const x = $(".xato-m", forma(i)); if (x) x.textContent = er.message; }
    }
    KESH = null;
    ok.disabled = false;
    yorliq();
    if (xato) { const birinchi = $(".mk .xato-m:not(:empty)", mt); if (birinchi) birinchi.scrollIntoView({block: "center", behavior: "smooth"}); return; }
    // hammasi yozildi: sahifa raqamlari yangilanadi, natija qatorda qoladi
    if (!kartalar.some(c => c.tayyor)) return;
    if (tugadi) return tugadi(kartalar.filter(c => c.tayyor).map(c => c.tayyor));
    const natija = `<div class="javob"><p class="mt-bosh">Yozildi</p><div class="mt-r">${kartalar.filter(c => c.tayyor).map(c => `<div class="mk ok"><i class="ti ti-circle-check"></i><b>${H(c.tayyor)}</b></div>`).join("")}</div></div>`;
    xabar("Hammasi yozildi");
    await yonalish();
    if ($("#javob")) $("#javob").innerHTML = natija;
  });
}

/* ---------- yozuv qo'shish ---------- */
let KESH = null;
async function malumotlar() {
  if (KESH && Date.now() - KESH.vaqt < 20000) return KESH;
  const [k, o, x] = await Promise.all([api("/api/kassalar"), api("/api/odamlar"), api("/api/xarajat_turlari")]);
  let m = {mijozlar: []}, t = {mijozlar: []};
  if (MEN.boshliq || MEN.huquq.mijoz_qarz) {
    [m, t] = await Promise.all([api("/api/mijozlar?tur=mijoz"), api("/api/mijozlar?tur=taminotchi")]);
  }
  KESH = {vaqt: Date.now(), kassalar: k.kassalar, odamlar: o.odamlar.filter(x => x.holat !== "ketgan"),
    xarajat: x.turlar, mijozlar: m.mijozlar, taminotchilar: t.mijozlar};
  return KESH;
}

async function yozuvOyna(boshTur = "chiqim") {
  const m = await malumotlar();
  const turlar = Object.entries(TUR).filter(([, t]) => !t.rol || t.rol.includes(MEN.odam.rol));
  const o = oyna("Yozuv qo'shish", `<form id="yf" class="forma">
      <label class="maydon butun"><span>Nima bo'ldi?</span><select name="tur">${turlar.map(([k, t]) => `<option value="${k}" ${k === boshTur ? "selected" : ""}>${H(t.nom)}</option>`).join("")}</select></label>
      <label class="maydon"><span>Summa</span><input type="text" name="summa" inputmode="decimal" placeholder="500 000" required></label>
      <label class="maydon"><span>Valyuta</span><select name="valyuta"><option value="UZS">so'm</option><option value="USD">dollar</option></select></label>
      <div id="yf-dinamik" class="forma butun"></div>
      <label class="maydon"><span>Sana</span><input type="date" name="sana" value="${MEN.bugun}" max="${MEN.bugun}"></label>
      <label class="maydon butun"><span>Izoh</span><input type="text" name="izoh" maxlength="300"></label>
      <div class="xato-m butun" id="yx"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="ysaqla"><i class="ti ti-check"></i>Yozish</button>`);
  const f = $("#yf", o.el);
  const kassaOpt = (v) => m.kassalar.map(k => `<option value="${k.id}" data-v="${k.valyuta}" ${v === k.id ? "selected" : ""}>${H(k.nom)} (${k.valyuta})</option>`).join("");
  const odamOpt = m.odamlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("");
  const maydonlar = {
    kassa: () => `<label class="maydon"><span>Kassa</span><select name="kassa_id" required>${kassaOpt(MEN.odam.kassa_id)}</select></label>`,
    kassa2: () => `<label class="maydon"><span>Qaysi kassaga</span><select name="kassa2_id" required>${kassaOpt(null)}</select></label>`,
    odam: () => `<label class="maydon"><span>Xodim</span><select name="odam_id" required>${odamOpt}</select></label>`,
    sotuvchi: () => `<label class="maydon"><span>Kim sotdi</span><select name="sotuvchi_id"><option value="">—</option>${odamOpt}</select></label>`,
    "mijoz?": () => `<label class="maydon"><span>Mijoz (ixtiyoriy)</span><select name="mijoz_id"><option value="">— mijozsiz —</option>${m.mijozlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select></label>`,
    mijoz: () => `<label class="maydon"><span>Mijoz</span><select name="mijoz_id" required>${m.mijozlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select>${m.mijozlar.length ? "" : `<small>Avval «Mijozlar» bo'limida mijoz qo'shing</small>`}</label>`,
    taminotchi: () => `<label class="maydon"><span>Ta'minotchi</span><select name="mijoz_id" required>${m.taminotchilar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select>${m.taminotchilar.length ? "" : `<small>Avval «Mijozlar → Ta'minotchilar»da qo'shing</small>`}</label>`,
    xarajat_turi: () => `<label class="maydon"><span>Xarajat turi</span><select name="xarajat_turi_id">${m.xarajat.map(x => `<option value="${x.id}">${H(x.nom)}</option>`).join("")}</select></label>`,
    tolandi: () => `<label class="maydon"><span>Hozir to'landi</span><input type="text" name="tolandi" inputmode="decimal" placeholder="0"><small>Qolgani nasiya bo'ladi</small></label>`,
    muddat: () => `<label class="maydon"><span>Qarz muddati</span><input type="date" name="muddat" min="${MEN.bugun}"></label>`,
  };
  const chiz = () => { $("#yf-dinamik", o.el).innerHTML = TUR[f.tur.value].f.map(x => maydonlar[x]()).join(""); valyutaMos(); };
  const valyutaMos = () => { const k = f.kassa_id; if (k && k.selectedOptions[0]) f.valyuta.value = k.selectedOptions[0].dataset.v; };
  f.tur.addEventListener("change", chiz);
  f.addEventListener("change", e => { if (e.target.name === "kassa_id") valyutaMos(); });
  chiz();
  const yubor = async (qosh = {}) => {
    const d = Object.fromEntries(new FormData(f));
    for (const k of Object.keys(d)) if (d[k] === "") delete d[k];
    d.summa = sonOqi(d.summa);
    if (!d.summa) { $("#yx", o.el).textContent = "Summani raqam bilan yozing"; return; }
    if (d.tolandi) d.tolandi = sonOqi(d.tolandi);
    try {
      const r = await api("/api/harakat", {body: {...d, ...qosh}});
      if (r.holat === "takror") {
        const t = r.takrorlar[0];
        $("#yx", o.el).innerHTML = `<div class="kutish" style="margin:0"><div><b>Shunga o'xshash yozuv bor</b><small>${H(t.tavsif)} · ${sanaMatn(t.voqea_sana)} · ${H(t.yozgan)}</small></div><div></div>
          <div class="sa"><button type="button" class="btn kichik" id="ybir">Ha, o'sha</button><button type="button" class="btn kichik" id="ybosh">Yo'q, boshqa</button></div></div>`;
        $("#ybir", o.el).onclick = async () => { await api(`/api/harakat/${r.id}/birlashtir`, {body: {eski_id: t.id}}); o.yop(); xabar("Ikkalasi bitta qilindi"); KESH = null; yonalish(); };
        $("#ybosh", o.el).onclick = async () => { await api(`/api/harakat/${r.id}/bekor`, {body: {sabab: "qayta kiritildi"}}).catch(() => {}); yubor({takror_emas: true}); };
        return;
      }
      o.yop();
      xabar(r.holat === "ruxsat_kutilmoqda" ? "Boshliq ruxsatini kutmoqda" : "Yozildi");
      KESH = null;
      yonalish();
    } catch (x) { $("#yx", o.el).textContent = x.message; }
  };
  $("#ysaqla", o.el).addEventListener("click", () => yubor());
  f.addEventListener("submit", e => { e.preventDefault(); yubor(); });
}

function sonOqi(s) {
  if (s === undefined || s === null) return 0;
  let t = String(s).toLowerCase().replace(/\s| /g, "");
  let k = 1;
  if (/mln|million/.test(t)) k = 1e6; else if (/ming|k$/.test(t)) k = 1e3;
  t = t.replace(/[^\d.,]/g, "");
  if (/[.,]\d{1,2}$/.test(t)) t = t.replace(",", "."); else t = t.replace(/[.,]/g, "");
  const n = parseFloat(t);
  return isFinite(n) ? n * k : 0;
}

/* ---------- yozuv tafsiloti ---------- */
async function harakatOyna(id) {
  let h;
  try { h = (await api(`/api/harakat/${id}`)).harakat; } catch (x) { return xabar("Yozuv topilmadi yoki ko'rish huquqi yo'q", true); }
  const tomon = (nom, holat) => holat === "kerak_emas" ? "tasdiq kerak emas" : holat === "tasdiq" ? `${nom} tasdiqladi` : holat === "rad" ? `${nom} rad etdi` : `${nom} kutilmoqda`;
  const q = (a, b) => `<div class="varaq-q"><span>${a}</span><b>${b}</b></div>`;
  const o = oyna(`${h.nom} · #${h.id}`, `
    ${q("Summa", H(h.summa.t) + (h.summa2 ? ` → ${H(h.summa2.t)}` : ""))}
    ${q("Qayerdan", H(h.dan))}${q("Qayerga", H(h.ga))}
    ${q("Voqea sanasi", sanaMatn(h.voqea_sana) + (h.kech ? ` · hisobga ${sanaMatn(h.hisob_sana)} (kech kiritilgan)` : ""))}
    ${q("Holat", `<span class="chip ${(HOLAT[h.holat] || ["", ""])[1]}">${(HOLAT[h.holat] || [h.holat])[0]}</span>`)}
    ${q("Beruvchi tomoni", H(tomon(h.beruvchi || "", h.beruvchi_holat)))}${q("Oluvchi tomoni", H(tomon(h.oluvchi || "", h.oluvchi_holat)))}
    ${q("Yozgan", H(h.yozgan) + " · " + H((h.yozilgan || "").replace("T", " ").slice(0, 16)))}
    ${h.izoh ? q("Izoh", H(h.izoh)) : ""}${h.muddat ? q("Qarz muddati", sanaMatn(h.muddat)) : ""}
    ${h.iqtibos ? `<p style="margin-top:10px;color:var(--matn2);font-style:italic">«${H(h.iqtibos)}»</p>` : ""}
    ${h.xabar_id ? `<p style="margin-top:10px"><a href="/api/fayl/${h.xabar_id}" target="_blank" rel="noopener"><i class="ti ti-paperclip"></i> Asl xabar fayli (ovoz yoki chek)</a></p>` : ""}
    ${h.bekor_sabab ? q("Bekor sababi", H(h.bekor_sabab)) : ""}
    <div id="hx" class="xato-m"></div>`,
    (MEN.boshliq && ["faol", "nizo", "ruxsat_kutilmoqda"].includes(h.holat) && !h.bog_id ? `<button class="btn" id="htuzat"><i class="ti ti-pencil"></i>Tuzatish</button>` : "")
    + (h.holat === "faol" || h.holat === "nizo" ? `<button class="btn xavf" id="hbekor"><i class="ti ti-trash"></i>Bekor qilish</button><button class="btn" data-yop>Yopish</button>` : `<button class="btn" data-yop>Yopish</button>`));
  const tz = $("#htuzat", o.el);
  if (tz) tz.addEventListener("click", () => { o.yop(); tuzatOyna(h); });
  const b = $("#hbekor", o.el);
  if (b) b.addEventListener("click", async () => {
    const sabab = prompt("Bekor qilish sababi:");
    if (!sabab) return;
    try {
      const r2 = await api(`/api/harakat/${id}/bekor`, {body: {sabab}});
      o.yop();
      xabar(r2.teskari_id ? "Davr yopilgan edi — bugungi sana bilan teskari yozuv qilindi" : "Bekor qilindi");
      yonalish();
    } catch (x) { $("#hx", o.el).textContent = x.message; }
  });
}

/* ---------- Kassa va pul ---------- */
async function kassaSahifa(main) {
  const [k, m] = await Promise.all([api("/api/kassalar"), malumotlar()]);
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  main.innerHTML = tepa("Kassa va pul", "Kassalar qoldig'i va barcha pul yozuvlari",
    `<button class="btn" data-a="yozuv"><i class="ti ti-plus"></i>Yozuv qo'shish</button>${MEN.boshliq ? `<button class="btn" data-a="kassa"><i class="ti ti-building-bank"></i>Kassa qo'shish</button>` : ""}`)
    + `<section class="kpi">${k.kassalar.map(x => `<div class="k"><div class="kb0"><i class="ti ti-${x.tur === "bank" ? "building-bank" : x.tur === "karta" ? "credit-card" : x.tur === "chontak" ? "user" : "wallet"}"></i>${H(x.nom)}</div>
        <div class="kr raqam">${H(x.qoldiq.t)}</div>
        <div class="ki">${x.masul ? `Mas'ul: ${H(x.masul)}` : "Mas'ul yo'q"}${x.oxirgi_sanoq ? ` · sanoq ${sanaMatn(x.oxirgi_sanoq.sana)}` : ""}</div>
        ${x.kutilayotgan_chiqim.m || x.kutilayotgan_kirim.m ? `<div class="ki" style="color:var(--kut)">Tasdiq kutmoqda: −${H(x.kutilayotgan_chiqim.t)} / +${H(x.kutilayotgan_kirim.t)}</div>` : ""}
        <div class="tugmalar" style="margin-top:10px"><button class="btn kichik" data-sanoq="${x.id}"><i class="ti ti-calculator"></i>Sanash</button>
        <button class="btn kichik" data-filtr="${x.id}">Yozuvlari</button>${MEN.boshliq ? `<button class="btn kichik" data-ktahrir="${x.id}">Tahrirlash</button>` : ""}</div></div>`).join("")}</section>
      <section class="karta"><div class="kb"><h2>Yozuvlar</h2></div>
      <form class="filtr" id="hf">
        <label class="maydon"><span>Kassa</span><select name="hisob"><option value="">Hammasi</option>${k.kassalar.map(x => `<option value="kassa:${x.id}" ${params.get("hisob") === "kassa:" + x.id ? "selected" : ""}>${H(x.nom)}</option>`).join("")}</select></label>
        <label class="maydon"><span>Tur</span><select name="tur"><option value="">Hammasi</option>${Object.entries(TUR).map(([kk, t]) => `<option value="${kk}">${H(t.nom)}</option>`).join("")}</select></label>
        <label class="maydon"><span>Xodim</span><select name="odam_id"><option value="">Hammasi</option>${m.odamlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select></label>
        <label class="maydon"><span>Mijoz</span><select name="mijoz_id"><option value="">Hammasi</option>${[...m.mijozlar, ...m.taminotchilar].map(x => `<option value="${x.id}" ${params.get("mijoz_id") === String(x.id) ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select></label>
        <label class="maydon"><span>Dan</span><input type="date" name="dan"></label><label class="maydon"><span>Gacha</span><input type="date" name="gacha"></label>
        <label class="maydon" style="flex:1 1 200px"><span>Qidirish</span><input type="search" name="q" placeholder="Izoh, mijoz, summa…" value="${H(params.get("q") || "")}"></label>
        <button class="btn" type="submit"><i class="ti ti-filter"></i>Ko'rsatish</button><button class="btn" type="button" id="hexcel"><i class="ti ti-file-spreadsheet"></i>Excel</button></form>
      <div class="jadval-o" id="hj"></div><div id="hyana"></div></section>`;
  $("#hexcel").addEventListener("click", () => {
    const f = Object.fromEntries(new FormData($("#hf")));
    location.href = `/api/eksport/kassa?${new URLSearchParams(Object.entries({dan: f.dan, gacha: f.gacha}).filter(([, v]) => v))}`;
  });
  let oxirgiId = null;
  const SAHIFA_SONI = 100;  // eskilari «Yana ko'rsatish» bilan (sahifalash)
  const qatorH = h => `<tr class="bosiladi ${h.holat === "bekor" ? "bekor" : ""} ${h.beruvchi_holat === "kutilmoqda" || h.oluvchi_holat === "kutilmoqda" ? "kutmoqda" : ""}" data-korish="${h.id}">
        <td>${sanaMatn(h.voqea_sana)}${h.kech ? ` <span class="chip kut">kech</span>` : ""}</td><td><b>${H(h.nom)}</b>${h.izoh ? `<br><small>${H(h.izoh)}</small>` : ""}</td>
        <td>${H(h.dan)} → ${H(h.ga)}</td><td class="son"><b>${H(h.summa.t)}</b></td>
        <td><span class="chip ${(HOLAT[h.holat] || ["", ""])[1]}">${(HOLAT[h.holat] || [h.holat])[0]}</span>${h.beruvchi_holat === "kutilmoqda" || h.oluvchi_holat === "kutilmoqda" ? ` <span class="chip kut">tasdiq kutmoqda</span>` : ""}</td>
        <td>${H(h.yozgan)}</td></tr>`;
  const yukla = async (yana = false) => {
    const q = new URLSearchParams(Object.entries(Object.fromEntries(new FormData($("#hf")))).filter(([, v]) => v));
    q.set("limit", String(SAHIFA_SONI));
    if (yana && oxirgiId) q.set("oldin_id", oxirgiId);
    const r = await api(`/api/harakatlar?${q}`);
    if (r.harakatlar.length) oxirgiId = r.harakatlar[r.harakatlar.length - 1].id;
    if (yana) $("#hj tbody").insertAdjacentHTML("beforeend", r.harakatlar.map(qatorH).join(""));
    else $("#hj").innerHTML = r.harakatlar.length ? `<table class="jadval"><thead><tr><th>Sana</th><th>Yozuv</th><th>Qayerdan → qayerga</th><th class="son">Summa</th><th>Holat</th><th>Yozgan</th></tr></thead><tbody>
      ${r.harakatlar.map(qatorH).join("")}</tbody></table>` : `<div class="bosh"><i class="ti ti-receipt-off"></i>Yozuv yo'q</div>`;
    $("#hyana").innerHTML = r.harakatlar.length === SAHIFA_SONI ? `<div class="yana"><button class="btn" type="button" data-yana><i class="ti ti-chevron-down"></i>Yana ko'rsatish</button></div>` : "";
  };
  $("#hf").addEventListener("submit", e => { e.preventDefault(); yukla(); });
  await yukla();
  main.addEventListener("click", async e => {
    if (e.target.closest("[data-yana]")) return yukla(true);
    const t = e.target.closest("[data-a],[data-sanoq],[data-filtr],[data-ktahrir],[data-korish]");
    if (!t) return;
    if (t.dataset.a === "yozuv") return yozuvOyna();
    if (t.dataset.a === "kassa") return kassaOyna(null, m);
    if (t.dataset.korish) return harakatOyna(+t.dataset.korish);
    if (t.dataset.filtr) { $("#hf").hisob.value = "kassa:" + t.dataset.filtr; return yukla(); }
    if (t.dataset.ktahrir) return kassaOyna(k.kassalar.find(x => x.id === +t.dataset.ktahrir), m);
    if (t.dataset.sanoq) return sanoqOyna(k.kassalar.find(x => x.id === +t.dataset.sanoq));
  });
}

function sanoqOyna(k) {
  const o = oyna(`Kassani sanash · ${k.nom}`, `<p style="color:var(--matn2);margin-bottom:12px">Kassadagi pulni sanab, natijani yozing. Dastur o'zi solishtiradi.</p>
    <form id="sf" class="forma"><label class="maydon butun"><span>Sanaldi (${k.valyuta === "USD" ? "dollar" : "so'm"})</span><input type="text" name="summa" inputmode="decimal" required></label>
    <label class="maydon butun"><span>Izoh (farq bo'lsa)</span><input type="text" name="izoh" maxlength="300"></label></form><div id="sn"></div>`,
    `<button class="btn" data-yop>Yopish</button><button class="btn asosiy" id="sok">Yozish</button>`);
  $("#sok", o.el).addEventListener("click", async () => {
    const f = $("#sf", o.el);
    try {
      const r = await api(`/api/kassa/${k.id}/sanoq`, {body: {summa: sonOqi(f.summa.value), izoh: f.izoh.value}});
      $("#sn", o.el).innerHTML = `<div style="margin-top:14px"><div class="varaq-q"><span>Dastur bo'yicha</span><b>${H(r.kutilgan.t)}</b></div>
        <div class="varaq-q"><span>Sanaldi</span><b>${H(r.sanalgan.t)}</b></div>
        <div class="varaq-q jami"><span>Farq</span><b class="${r.farq.m ? "q" : "y"}">${r.farq.m ? H(r.farq.t) : "Mos keldi"}</b></div>
        ${r.farq.m && r.agar.m !== r.kutilgan.m ? `<p class="ki" style="margin-top:8px">Tasdiq kutayotgan yozuvlar tasdiqlansa: ${H(r.agar.t)}</p>` : ""}</div>`;
      $("#sok", o.el).remove();
    } catch (x) { $("#sn", o.el).innerHTML = `<div class="xato-m">${H(x.message)}</div>`; }
  });
}

function kassaOyna(k, m) {
  const o = oyna(k ? "Kassani tahrirlash" : "Kassa qo'shish", `<form id="kf" class="forma">
    <label class="maydon butun"><span>Nomi</span><input type="text" name="nom" required value="${H(k ? k.nom : "")}" placeholder="Asosiy kassa"></label>
    ${k ? "" : `<label class="maydon"><span>Turi</span><select name="tur"><option value="naqd">Naqd</option><option value="karta">Karta</option><option value="bank">Bank hisobi</option><option value="chontak">Shaxsiy cho'ntak</option></select></label>
    <label class="maydon"><span>Valyuta</span><select name="valyuta"><option value="UZS">so'm</option><option value="USD">dollar</option></select></label>`}
    <label class="maydon butun"><span>Mas'ul (tasdiq beradi)</span><select name="masul_id"><option value="">—</option>${m.odamlar.map(x => `<option value="${x.id}" ${k && k.masul_id === x.id ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select></label>
    ${k ? `<label class="belgi butun"><input type="checkbox" name="faol" checked> Faol</label>` : ""}<div class="xato-m butun" id="kx"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="kok">Saqlash</button>`);
  $("#kok", o.el).addEventListener("click", async () => {
    const f = $("#kf", o.el);
    const d = {nom: f.nom.value, masul_id: f.masul_id.value ? +f.masul_id.value : null};
    try {
      if (k) await api(`/api/kassa/${k.id}`, {body: {...d, faol: f.faol.checked ? 1 : 0}});
      else await api("/api/kassa", {body: {...d, tur: f.tur.value, valyuta: f.valyuta.value}});
      o.yop(); KESH = null; yonalish();
    } catch (x) { $("#kx", o.el).textContent = x.message; }
  });
}

/* ---------- Maosh ---------- */
function varaqHtml(v) {
  const q = (a, b, kl = "") => `<div class="varaq-q ${kl}"><span>${a}</span><b>${b}</b></div>`;
  return q("O'tgan oydan", H(v.otgan.t))
    + v.qatorlar.map(x => q((x.summa.m > 0 ? "+ " : "− ") + H(x.nom) + (x.sana ? ` · ${sanaMatn(x.sana)}` : ""), H(x.summa.t.replace("−", "")))).join("")
    + (v.kutilmoqda.length ? v.kutilmoqda.map(x => q(`<span class="chip kut">tasdiq kutmoqda</span> ${H(x.nom)}`, H(x.summa.t))).join("") : "")
    + ((v.ish_kutilmoqda || []).map(x => q(`<span class="chip kut">ish</span> ${H(x.nom)}`, "+" + H(x.summa.t))).join(""))
    + q("Qolgani", H(v.qolgani.t), "jami");
}

async function maoshSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const oy = params.get("oy") || MEN.oy;
  const d = await api(`/api/maosh?oy=${oy}`);
  const oySelect = oyTanlov(oy);
  if (!MEN.boshliq) {
    let tol = "";
    if (d.tolash) tol = `<section class="karta"><div class="kb"><h2>To'lash kerak</h2><span class="izoh">faqat summa</span></div>${d.tolash.map(x => `<div class="odam"><span class="av ${avRang(x.odam_id)}">${H(bosh(x.ism))}</span><div><b>${H(x.ism)}</b></div><div class="oi"><strong>${H(x.qolgani.t)}</strong></div></div>`).join("")}</section>`;
    main.innerHTML = tepa("Maosh", d.oz.oy_matn, oySelect) + `<div class="ustun2"><section class="karta"><div class="kb"><h2>Mening hisobim</h2></div>${varaqHtml(d.oz)}</section>${tol}</div>`;
  } else {
    const yopiladi = oy < MEN.oy && !d.yopiq;
    main.innerHTML = tepa("Maosh", `${H(d.oy_matn)}${d.yopiq ? `<span class="n"></span><b style="color:var(--matn2)">oy yopilgan</b>` : ""}<span class="n"></span>maosh kunlari: ${d.maosh_kunlari.join(" va ")}`,
      `${oySelect}<a class="btn" href="/api/eksport/maosh?oy=${oy}"><i class="ti ti-file-spreadsheet"></i>Excel</a>${yopiladi ? `<button class="btn" id="yop"><i class="ti ti-lock"></i>Oyni yopish</button>` : ""}`)
      + `<section class="karta"><div class="kb"><h2>Xodimlar</h2><span class="izoh">qatorni bosing — tafsilot va maosh sharti</span></div>
      <div class="jadval-o"><table class="jadval"><thead><tr><th>Xodim</th><th>Maosh sharti</th><th class="son">O'tgan oydan</th><th class="son">Hisoblandi</th><th class="son">Oldi</th><th class="son">Kutmoqda</th><th class="son">Qolgani</th></tr></thead><tbody>
      ${d.royxat.map(v => `<tr class="bosiladi" data-odam="${v.odam.id}"><td><b>${H(v.odam.ism)}</b><br><small>${H(v.odam.rol_nomi)}</small></td>
        <td>${v.shartlar.length ? v.shartlar.map(s => `<span class="chip">${H(s.nom)} ${s.tur === "foiz" ? s.qiymat + "%" : guruh(s.qiymat) + (s.valyuta === "USD" ? " $" : "")}</span>`).join(" ") : `<span class="chip kut">shart yo'q</span>`}</td>
        <td class="son">${H(v.otgan.t)}</td><td class="son">${H(v.hisoblandi.t)}</td><td class="son">${H(v.olindi.t)}</td>
        <td class="son">${v.kutilmoqda_jami.m ? H(v.kutilmoqda_jami.t) : "—"}</td><td class="son"><b>${H(v.qolgani.t)}</b></td></tr>`).join("")}</tbody></table></div></section>`;
    const y = $("#yop");
    if (y) y.addEventListener("click", async () => {
      if (!confirm(`${d.oy_matn} yopilsinmi? Yopilgan oy raqamlari endi o'zgarmaydi, keyingi tuzatishlar keyingi oyga tushadi.`)) return;
      try { const r = await api("/api/maosh/yopish", {body: {oy}}); xabar(`Oy yopildi · ${r.yozuvlar} ta hisob yozuvi`); yonalish(); } catch (x) { xabar(x.message, true); }
    });
    main.addEventListener("click", e => { const t = e.target.closest("[data-odam]"); if (t) maoshOyna(d.royxat.find(v => v.odam.id === +t.dataset.odam), oy, d.yopiq); });
  }
  $("#oy").addEventListener("change", e => { location.hash = `#/maosh?oy=${e.target.value}`; });
}

function maoshOyna(v, oy, yopiq) {
  const shartlar = v.shartlar.map(s => `<div class="holat-q"><div><b>${H(s.nom)}: ${s.tur === "foiz" ? s.qiymat + "%" : guruh(s.qiymat) + (s.valyuta === "USD" ? " $" : " so'm")}</b><small>${sanaMatn(s.dan)} dan${s.gacha ? ` ${sanaMatn(s.gacha)} gacha` : ""}</small></div>
    ${!s.gacha && !yopiq ? `<button class="btn kichik" data-tugat="${s.id}">Tugatish</button>` : ""}</div>`).join("") || `<div class="bosh">Maosh sharti qo'yilmagan</div>`;
  const kunbay = v.shartlar.some(s => s.tur === "kunbay");
  const o = oyna(`${v.odam.ism} · ${v.oy_matn}`, `${varaqHtml(v)}
    <h3 style="margin-top:22px">Maosh sharti</h3>${shartlar}
    ${kunbay && !yopiq ? `<form id="kunf" class="filtr"><label class="maydon"><span>Ishlagan kunlarini qo'lda o'zgartirish (odatda davomatdan olinadi)</span><input type="number" name="kunlar" min="0" max="31" step="0.5" value="${v.kunlar ?? ""}"></label><button class="btn" type="submit">Saqlash</button></form>` : ""}
    ${yopiq ? "" : `<form id="shf" class="forma" style="margin-top:12px">
      <label class="maydon"><span>Yangi shart</span><select name="tur"><option value="oylik">Oylik</option><option value="kunbay">Kunbay (1 kun)</option><option value="foiz">Sotuvdan foiz</option></select></label>
      <label class="maydon"><span>Qiymat</span><input type="text" name="qiymat" inputmode="decimal" required placeholder="4 000 000"></label>
      <label class="maydon"><span>Valyuta</span><select name="valyuta"><option value="UZS">so'm</option><option value="USD">dollar</option></select></label>
      <label class="maydon"><span>Qaysi sanadan</span><input type="date" name="dan" value="${oy}-01"></label>
      <div class="butun"><button class="btn asosiy" type="submit"><i class="ti ti-plus"></i>Shartni qo'yish</button> <small style="color:var(--matn3)">Shu turdagi eski shart o'zi yopiladi, tarix saqlanadi</small></div></form>`}
    <div class="xato-m" id="mx"></div>`);
  const qayta = () => { o.yop(); yonalish(); };
  const sh = $("#shf", o.el);
  if (sh) sh.addEventListener("submit", async e => {
    e.preventDefault();
    try {
      const q = sh.tur.value === "foiz" ? parseFloat(sh.qiymat.value.replace(",", ".")) : sonOqi(sh.qiymat.value);
      await api("/api/maosh/shart", {body: {odam_id: v.odam.id, tur: sh.tur.value, qiymat: q, valyuta: sh.valyuta.value, dan: sh.dan.value}});
      xabar("Shart qo'yildi"); qayta();
    } catch (x) { $("#mx", o.el).textContent = x.message; }
  });
  const kf = $("#kunf", o.el);
  if (kf) kf.addEventListener("submit", async e => {
    e.preventDefault();
    try { await api("/api/maosh/kunlar", {body: {odam_id: v.odam.id, oy, kunlar: +kf.kunlar.value}}); xabar("Saqlandi"); qayta(); } catch (x) { $("#mx", o.el).textContent = x.message; }
  });
  o.el.addEventListener("click", async e => {
    const t = e.target.closest("[data-tugat]");
    if (!t) return;
    const gacha = prompt("Qaysi sanagacha amal qildi? (YYYY-MM-DD)", MEN.bugun);
    if (!gacha) return;
    try { await api(`/api/maosh/shart/${t.dataset.tugat}/tugat`, {body: {gacha}}); qayta(); } catch (x) { $("#mx", o.el).textContent = x.message; }
  });
}

/* ---------- Mijozlar ---------- */
const VADA_RANG = {vaqtida: "y", kech: "kut", qisman: "kut", buzildi: "q", ochiq: "u", bekor: ""};
const ishonchRang = i => !i || !i.jami ? "" : i.vaqtida * 5 >= i.jami * 4 ? "y" : i.vaqtida * 2 >= i.jami ? "kut" : "q";

async function mijozSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const tur = params.get("tur") === "taminotchi" ? "taminotchi" : "mijoz";
  const arxiv = params.get("arxiv") === "1";
  const d = await api(`/api/mijozlar?tur=${tur}${arxiv ? "&arxiv=1" : ""}`);
  const nom = tur === "mijoz" ? "mijoz" : "ta'minotchi";
  const tab = (k, n) => `<a href="#/mijozlar${k === "mijoz" ? "" : "?tur=taminotchi"}" ${tur === k ? 'style="font-weight:800"' : ""}>${n}</a>`;
  const son = f => d.mijozlar.filter(f).length;
  const filtrlar = tur === "mijoz" ? [["hammasi", `Hammasi · ${d.mijozlar.length}`, () => true], ["qarz", `Qarzi bor · ${son(m => m.qarz.length)}`, m => m.qarz.length],
    ["uxlagan", `Uzoq kelmagan · ${son(m => m.uxlagan)}`, m => m.uxlagan], ["vada", `Ochiq va'dasi bor · ${son(m => m.ochiq_vada)}`, m => m.ochiq_vada]] : [];
  main.innerHTML = tepa("Mijozlar", `${tab("mijoz", "Mijozlar")}<span class="n"></span>${tab("taminotchi", "Ta'minotchilar")}`,
    `<a class="btn" href="#/mijozlar?${tur === "taminotchi" ? "tur=taminotchi&" : ""}${arxiv ? "" : "arxiv=1"}"><i class="ti ti-archive"></i>${arxiv ? "Arxivdan chiqish" : "Arxiv"}</a><a class="btn" href="/api/eksport/qarzlar"><i class="ti ti-file-spreadsheet"></i>Qarzlar Excel'da</a>${MEN.boshliq && !arxiv ? `<button class="btn" id="mimp"><i class="ti ti-file-import"></i>Excel'dan yuklash</button>` : ""}${d.tahrir ? `<button class="btn" id="madd"><i class="ti ti-plus"></i>${tur === "mijoz" ? "Mijoz" : "Ta'minotchi"} qo'shish</button>` : ""}`)
    + `<section class="karta">${d.mijozlar.length ? `<div class="filtr"><label class="maydon" style="flex:1 1 220px"><span>Qidirish</span><input type="text" id="mqid" placeholder="Ism, telefon yoki manzil" autocomplete="off"></label>
      ${filtrlar.length ? `<div class="tanlov" role="group" aria-label="Saralash">${filtrlar.map(([k, n], i) => `<button type="button" class="chip-b ${i ? "" : "faol"}" data-f="${k}" aria-pressed="${i ? "false" : "true"}">${n}</button>`).join("")}</div>` : ""}</div>
      <div id="mro"></div>` : `<div class="bosh"><i class="ti ti-address-book"></i>Hali ${nom} yo'q. Botga «Karimov 3 mln to'ladi» desangiz ham o'zi qo'shiladi.</div>`}</section>`;
  let filtr = "hammasi";
  const chiz = () => {
    const q = ($("#mqid") ? $("#mqid").value : "").trim().toLowerCase();
    const f = (filtrlar.find(x => x[0] === filtr) || [0, 0, () => true])[2];
    const royxat = d.mijozlar.filter(m => f(m) && (!q || [m.ism, m.telefon, m.telefon2, m.manzil, m.izoh].some(x => (x || "").toLowerCase().includes(q))));
    if (filtr === "uxlagan") royxat.sort((a, b) => b.uxlash.ortacha_summa - a.uxlash.ortacha_summa);
    if (filtr === "qarz") royxat.sort((a, b) => b.qarz_som - a.qarz_som);
    const qator = m => tur === "mijoz"
      ? `<tr class="bosiladi" data-mk="${m.id}"><td><b>${H(m.ism)}</b>${m.manzil || m.izoh ? `<br><small>${H([m.manzil, m.izoh].filter(Boolean).join(" · "))}</small>` : ""}${m.masul ? `<br><small><i class="ti ti-user"></i> ${H(m.masul)}</small>` : ""}</td>
        <td>${H(m.telefon || "—")}</td>
        <td class="son">${m.qarz.length ? m.qarz.map(q => `<b>${H(q.t)}</b>`).join("<br>") : "—"}${m.muddat ? `<br><span class="chip ${m.muddat < MEN.bugun ? "q" : ""}">${sanaMatn(m.muddat)} gacha</span>` : ""}</td>
        <td>${m.oxirgi_xarid ? sanaMatn(m.oxirgi_xarid) : "—"}${m.uxlagan ? `<br><span class="chip kut"><i class="ti ti-zzz"></i>${m.uxlash.otdi_kun} kun kelmadi</span>` : ""}</td>
        <td>${m.ishonch && m.ishonch.jami ? `<span class="chip ${ishonchRang(m.ishonch)}">${m.ishonch.vaqtida}/${m.ishonch.jami} vaqtida</span>` : "—"}${m.ochiq_vada ? `<br><small>${m.ochiq_vada} ta kutilmoqda</small>` : ""}</td>
        <td class="amal">${m.tg_id ? `<span class="chip y">botda</span>` : d.tahrir ? `<button class="btn kichik" data-mbot="${m.id}">Botga ulash</button>` : ""}</td></tr>`
      : `<tr class="bosiladi" data-mk="${m.id}"><td><b>${H(m.ism)}</b>${m.izoh ? `<br><small>${H(m.izoh)}</small>` : ""}</td><td>${H(m.telefon || "—")}</td>
        <td class="son">${m.qarz.length ? m.qarz.map(q => `<b>${H(q.t)}</b>`).join("<br>") : "—"}</td>
        <td>${m.muddat ? `<span class="chip ${m.muddat < MEN.bugun ? "q" : m.muddat <= kunQosh(MEN.bugun, 2) ? "kut" : ""}">${sanaMatn(m.muddat)}</span>` : "—"}</td></tr>`;
    $("#mro").innerHTML = royxat.length ? `<div class="jadval-o"><table class="jadval"><thead><tr>${tur === "mijoz"
      ? `<th>Mijoz</th><th>Telefon</th><th class="son">Bizga qarzi</th><th>Oxirgi xarid</th><th>Va'dalari</th><th></th>`
      : `<th>Ta'minotchi</th><th>Telefon</th><th class="son">Bizning qarzimiz</th><th>To'lash muddati</th>`}</tr></thead><tbody>${royxat.map(qator).join("")}</tbody></table></div>`
      : `<div class="bosh"><i class="ti ti-search"></i>Mos ${nom} topilmadi</div>`;
  };
  if ($("#mro")) chiz();
  if ($("#mqid")) $("#mqid").addEventListener("input", chiz);
  main.addEventListener("click", async e => {
    const fb = e.target.closest("[data-f]");
    if (fb) {
      filtr = fb.dataset.f;
      $$("[data-f]", main).forEach(b => { b.classList.toggle("faol", b === fb); b.setAttribute("aria-pressed", b === fb ? "true" : "false"); });
      return chiz();
    }
    const mb = e.target.closest("[data-mbot]");
    if (mb) return mijozBotOyna(+mb.dataset.mbot);
    const r = e.target.closest("[data-mk]");
    if (r) mijozOyna(+r.dataset.mk, () => yonalish());
  });
  if ($("#mimp")) $("#mimp").addEventListener("click", () => importOyna(tur));
  const madd = $("#madd");
  if (madd) madd.addEventListener("click", () => {
    const o = oyna(`${tur === "mijoz" ? "Mijoz" : "Ta'minotchi"} qo'shish`, `<form id="mf" class="forma"><label class="maydon butun"><span>Ism yoki nom</span><input type="text" name="ism" required></label>
      <label class="maydon"><span>Telefon</span><input type="text" name="telefon"></label><label class="maydon"><span>Izoh</span><input type="text" name="izoh"></label><div class="xato-m butun" id="mx"></div></form>`,
      `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="mok">Saqlash</button>`);
    $("#mok", o.el).addEventListener("click", async () => {
      const f = $("#mf", o.el);
      try { await api("/api/mijoz", {body: {ism: f.ism.value, telefon: f.telefon.value, izoh: f.izoh.value, tur}}); o.yop(); KESH = null; yonalish(); } catch (x) { $("#mx", o.el).textContent = x.message; }
    });
  });
}

const kunQosh = (s, n) => { const d = new Date(s + "T00:00:00"); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

async function mijozBotOyna(id) {
  try {
    const r = await api(`/api/mijoz/${id}/taklif`, {body: {}});
    oyna("Mijozni botga ulash", r.havola ? `<p style="color:var(--matn2);margin-bottom:10px">Shu havolani mijozga yuboring. U bosgach, bajarilgan ishlar bo'yicha «bajarildimi?» so'rovi va siz bosgan to'lov eslatmalari unga boradi.</p><div class="nusxa">${H(r.havola)}</div>` : `<p>Bot hali ulanmagan — Sozlamalarda bot tokenini kiriting.</p>`);
  } catch (x) { xabar(x.message, true); }
}

/* ---------- mijoz kartasi (C1, C2, C6) ---------- */
function vadaQator(v, mijozBilan = false) {
  const nima = v.tur === "tolov" ? (v.summa ? v.summa.t : "") : (v.matn || "");
  const tolov = v.tur === "tolov" && v.kim === "mijoz" && v.qoplandi && v.qoplandi.m ? ` · to'landi ${v.qoplandi.t}` : "";
  const ochiq = v.holat === "ochiq" && !["vaqtida", "kech"].includes(v.holat_h);
  const boshqa = v.tur === "boshqa" || v.kim === "biz";
  let tug = "";
  if (ochiq && boshqa && ["ochiq", "buzildi"].includes(v.holat_h)) tug += `<button class="btn kichik" data-vyop="${v.id}" data-ha="1">Bajarildi</button><button class="btn kichik" data-vyop="${v.id}" data-ha="0">Bajarilmadi</button>`;
  if (ochiq && MEN.boshliq) tug += vadaTahrirTugma(v);
  if (ochiq && (MEN.boshliq || MEN.odam.rol === "menejer")) tug += `<button class="btn kichik xavf" data-vbekor="${v.id}">Bekor</button>`;
  return `<div class="vq"><div><b>${mijozBilan ? `${H(v.mijoz)} — ` : ""}${v.kim === "biz" ? `<span class="chip">biz va'da berganmiz</span> ` : ""}${H(nima)}</b>
    <small>${v.muddat_matn} gacha${H(tolov)}${v.qolgan && v.qolgan.m && v.qoplandi && v.qoplandi.m ? ` · qolgani ${H(v.qolgan.t)}` : ""}${v.masul ? ` · eslatma: ${H(v.masul.split(" ")[0])}` : ""}${v.izoh ? ` · ${H(v.izoh)}` : ""}</small>
    ${v.iqtibos ? `<small class="iqt">«${H(v.iqtibos)}»</small>` : ""}</div>
    <span class="chip ${VADA_RANG[v.holat_h] || ""}">${H(v.holat_nomi)}</span>${tug ? `<div class="sa">${tug}</div>` : ""}</div>`;
}

function vadaForma(mijozlar, almashadi = []) {
  return `<form class="forma vf" novalidate>
    ${mijozlar ? `<label class="maydon butun"><span>Mijoz</span><select name="mijoz_id" required>${mijozlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select>${mijozlar.length ? "" : `<small>Avval «Mijozlar» bo'limida mijoz qo'shing</small>`}</label>` : ""}
    <label class="maydon"><span>Kim va'da berdi</span><select name="kim"><option value="mijoz">Mijoz bizga</option><option value="biz">Biz mijozga</option></select></label>
    <label class="maydon"><span>Nima haqida</span><select name="tur"><option value="tolov">To'lov</option><option value="boshqa">Boshqa (hujjat, mol…)</option></select></label>
    <label class="maydon vf-s"><span>Summa</span><input type="text" name="summa" inputmode="decimal" placeholder="2 000 000"></label>
    <label class="maydon vf-s"><span>Valyuta</span><select name="valyuta"><option value="UZS">so'm</option><option value="USD">dollar</option></select></label>
    <label class="maydon butun vf-m yashirin"><span>Nima va'da qilindi</span><input type="text" name="matn" maxlength="300" placeholder="Hujjatni olib keladi"></label>
    <label class="maydon"><span>Qachongacha</span><input type="date" name="muddat" min="${MEN.bugun}" value="${kunQosh(MEN.bugun, 1)}" required></label>
    ${almashadi.length ? `<div class="kutish butun vf-ogoh" style="margin:0"><div><b>Oldingi va'da bajarilmagan</b><small>${almashadi.map(v => `${H(v.summa ? v.summa.t : "")}, ${v.muddat_matn}`).join("; ")} — yangi to'lov va'dasi yozilsa, u «buzildi» bo'lib yopiladi</small></div></div>` : ""}
    <div class="xato-m butun"></div>
    <div class="butun"><button class="btn asosiy" type="submit"><i class="ti ti-check"></i>Va'dani yozish</button></div></form>`;
}

function vadaFormaUlash(f, tayyor) {
  const yangila = () => {
    const tolov = f.tur.value === "tolov";
    $$(".vf-s", f).forEach(x => x.classList.toggle("yashirin", !tolov));
    $(".vf-m", f).classList.toggle("yashirin", tolov);
    const og = $(".vf-ogoh", f);
    if (og) og.classList.toggle("yashirin", !(tolov && f.kim.value === "mijoz"));
  };
  f.tur.addEventListener("change", yangila);
  f.kim.addEventListener("change", yangila);
  yangila();
  f.addEventListener("submit", async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(f));
    const x = $(".xato-m", f);
    if (d.tur === "tolov") { d.summa = sonOqi(d.summa); if (!d.summa) { x.textContent = "Summani raqam bilan yozing"; return; } delete d.matn; }
    else { delete d.summa; if (!(d.matn || "").trim()) { x.textContent = "Nima va'da qilinganini yozing"; return; } }
    if (!d.muddat) { x.textContent = "Muddatni tanlang"; return; }
    try { await api("/api/vada", {body: d}); xabar("Va'da yozildi"); tayyor(); } catch (er) { x.textContent = er.message; }
  });
}

async function vadaTugmalari(e) {
  const t = e.target.closest("[data-vtahrir]");
  if (t) return vadaTahrirOyna(t.dataset, t.closest(".oyna-fon"));
  const b = e.target.closest("[data-vyop],[data-vbekor],[data-eslat],[data-eshit],[data-mijoz]");
  if (!b) return;
  if (b.dataset.mijoz) return mijozOyna(+b.dataset.mijoz, () => yonalish());
  if (b.dataset.eshit) { new Audio(`/api/fayl/${b.dataset.eshit}`).play().catch(() => xabar("Ovozni ochib bo'lmadi", true)); return; }
  try {
    b.disabled = true;
    if (b.dataset.eslat) { await api(`/api/vada/${b.dataset.eslat}/eslat`, {body: {}}); xabar("Mijozga eslatma yuborildi"); b.disabled = false; return; }
    if (b.dataset.vyop) await api(`/api/vada/${b.dataset.vyop}/yop`, {body: {bajarildi: b.dataset.ha === "1"}});
    if (b.dataset.vbekor) {
      const sabab = prompt("Nima uchun bekor qilinadi?");
      if (!sabab) { b.disabled = false; return; }
      await api(`/api/vada/${b.dataset.vbekor}/bekor`, {body: {sabab}});
    }
    xabar("Yozildi");
    const oy = b.closest(".oyna-fon");
    if (oy && oy._qayta) oy._qayta(); else yonalish();
  } catch (x) { xabar(x.message, true); b.disabled = false; }
}

const TARIX_IKON = {pul: "ti-cash", vada: "ti-heart-handshake", eslatma: "ti-notes", ish: "ti-checklist"};

async function mijozOyna(id, yopilganda) {
  let d;
  try { d = await api(`/api/mijoz/${id}`); } catch (x) { return xabar(x.message, true); }
  const m = d.mijoz, mijozmi = m.tur === "mijoz";
  const qarz = mijozmi ? d.qarz : d.qarzimiz;
  const xabarHavola = xb => !xb ? "" : xb.fayl ? ` · <a href="/api/fayl/${xb.id}" target="_blank" rel="noopener"><i class="ti ti-${xb.tur === "ovoz" ? "player-play" : "paperclip"}"></i> ${xb.tur === "ovoz" ? "asl ovoz" : "asl fayl"}</a>` : "";
  const ichki = `<div class="mk-bosh"><span class="av ${avRang(m.id)}">${H(bosh(m.ism))}</span><div><b>${H(m.ism)}</b>
      <small>${H([m.telefon, m.telefon2, m.manzil].filter(Boolean).join(" · ") || "telefon va manzil yozilmagan")}</small></div>${m.tg_id ? `<span class="chip y">botda</span>` : ""}</div>
    ${mijozmi ? `<div class="qongiroq"><small><i class="ti ti-phone-call"></i>Qo'ng'iroqdan oldin</small>${d.qisqa.map(q => `<p>${H(q)}</p>`).join("")}</div>` : ""}
    <div class="mk-son"><div><small>${mijozmi ? "Bizga qarzi" : "Bizning qarzimiz"}</small><b class="raqam">${qarz.length ? qarz.map(q => H(q.t)).join("<br>") : "yo'q"}</b></div>
      ${mijozmi ? `<div><small>Va'dalari</small><b>${d.ishonch.jami ? `${d.ishonch.vaqtida} / ${d.ishonch.jami} vaqtida` : "tarix yo'q"}</b></div>
      <div><small>Xarid odati</small><b>${d.uxlash ? `${String(d.uxlash.ortacha_kun).replace(".", ",")} kunda bir` : "kam ma'lumot"}</b>${d.uxlash && d.uxlash.uxlagan ? `<span class="chip kut">${d.uxlash.otdi_kun} kun kelmadi</span>` : ""}</div>` : ""}
      <div><small>Mas'ul</small><b>${H(d.masul || "—")}</b></div></div>
    ${mijozmi ? `<h4>Va'dalar <button class="btn kichik" id="mvy" type="button"><i class="ti ti-plus"></i>Va'da yozish</button></h4><div id="mvf"></div>
    ${d.vadalar.length ? d.vadalar.map(v => vadaQator(v)).join("") : `<div class="bosh">Va'da yozilmagan</div>`}` : ""}
    <h4>Eslatmalar</h4>
    ${d.eslatmalar.map(e_ => `<div class="vq"><div><b>${H(e_.matn)}</b><small>${H(e_.yozgan || "")} · ${sanaMatn(e_.vaqt)}${e_.manba === "aytilgan" ? " · xabardan o'zi olindi" : ""}</small></div>${e_.bekor_mumkin ? `<div class="sa"><button class="btn kichik" data-ebekor="${e_.id}">Bekor qilish</button></div>` : ""}</div>`).join("") || `<div class="bosh">Eslatma yo'q. «Karimov faqat naqd to'laydi» desangiz, bot o'zi yozib qo'yadi.</div>`}
    <form id="mef" class="filtr"><label class="maydon" style="flex:1 1 240px"><span>Yangi eslatma</span><input type="text" name="matn" maxlength="300" placeholder="Masalan: faqat naqd to'laydi"></label><button class="btn" type="submit">Qo'shish</button></form>
    <h4>Tarix</h4>
    ${d.tarix.length ? `<div class="tarix">${d.tarix.slice(0, 80).map(t => `<div class="tq"><span class="tn ${t.tur}"><i class="ti ${TARIX_IKON[t.tur] || "ti-point"}"></i></span>
      <div><b>${H(t.matn)}</b><small>${sanaMatn(t.vaqt)}${t.tur === "pul" ? (t.holat !== "faol" ? ` · ${H((HOLAT[t.holat] || [t.holat])[0].toLowerCase())}` : "") : t.tur === "eslatma" ? "" : ` · ${H(t.holat)}`}${xabarHavola(t.xabar)}</small>
      ${t.xabar && !t.xabar.fayl && t.xabar.matn ? `<small class="iqt">«${H(t.xabar.matn)}»</small>` : t.xabar && t.xabar.tur === "ovoz" && t.xabar.matn ? `<small class="iqt">«${H(t.xabar.matn)}»</small>` : ""}</div></div>`).join("")}</div>` : `<div class="bosh">Hali hech narsa yozilmagan</div>`}
    ${d.tahrir ? `<h4>Ma'lumotlar</h4><form id="mtf" class="forma">
      <label class="maydon"><span>Ism</span><input type="text" name="ism" value="${H(m.ism)}" required></label>
      <label class="maydon"><span>Telefon</span><input type="text" name="telefon" value="${H(m.telefon || "")}"></label>
      <label class="maydon"><span>Qo'shimcha telefon</span><input type="text" name="telefon2" value="${H(m.telefon2 || "")}"></label>
      <label class="maydon"><span>Manzil</span><input type="text" name="manzil" value="${H(m.manzil || "")}"></label>
      ${d.masul_tanlash ? `<label class="maydon"><span>Mas'ul xodim</span><select name="masul_id"><option value="">— yo'q —</option>${d.odamlar.map(x => `<option value="${x.id}" ${x.id === m.masul_id ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select><small>Va'da eslatmalari shunga boradi</small></label>` : ""}
      <label class="maydon butun"><span>Izoh</span><input type="text" name="izoh" value="${H(m.izoh || "")}"></label>
      <div class="butun" style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" type="submit">Saqlash</button>${MEN.boshliq || MEN.odam.rol === "menejer" ? `<button class="btn" type="button" id="mbir"><i class="ti ti-arrows-join"></i>Boshqa karta bilan birlashtirish</button>` : ""}${MEN.boshliq ? `<button class="btn" type="button" id="marx"><i class="ti ti-archive"></i>${m.arxiv ? "Arxivdan qaytarish" : "Arxivga olish"}</button>` : ""}</div></form>` : ""}
    <div class="xato-m" id="mkx"></div>`;
  const o = oyna(mijozmi ? "Mijoz kartasi" : "Ta'minotchi kartasi", ichki);
  o.el.querySelector(".oyna").classList.add("keng");
  $("[data-yop]", o.el).focus();  // birinchi maydonga emas — karta boshidan ko'rinsin
  $(".oyna", o.el).scrollTop = 0;
  let ozgardi = false;
  const qayta = () => { o.yop(); mijozOyna(id, yopilganda); };
  o.el._qayta = () => { ozgardi = true; qayta(); };
  o.el.addEventListener("click", vadaTugmalari);
  const kuzat = new MutationObserver(() => { if (!document.body.contains(o.el)) { kuzat.disconnect(); if (ozgardi && yopilganda) yopilganda(); } });
  kuzat.observe(document.body, {childList: true});
  const mvy = $("#mvy", o.el);
  if (mvy) mvy.addEventListener("click", () => {
    if ($("#mvf", o.el).innerHTML) { $("#mvf", o.el).innerHTML = ""; return; }
    $("#mvf", o.el).innerHTML = vadaForma(null, d.almashadi);
    const f = $(".vf", $("#mvf", o.el));
    vadaFormaUlash(f, () => { ozgardi = true; qayta(); });
    f.insertAdjacentHTML("afterbegin", `<input type="hidden" name="mijoz_id" value="${id}">`);
    f.summa.focus();
  });
  o.el.addEventListener("click", async e => {
    const b = e.target.closest("[data-ebekor]");
    if (!b) return;
    try { await api(`/api/eslatma/${b.dataset.ebekor}/bekor`, {body: {}}); ozgardi = true; qayta(); } catch (x) { xabar(x.message, true); }
  });
  $("#mef", o.el).addEventListener("submit", async e => {
    e.preventDefault();
    const matn_ = e.target.matn.value.trim();
    if (!matn_) return;
    try { await api(`/api/mijoz/${id}/eslatma`, {body: {matn: matn_}}); ozgardi = true; qayta(); } catch (x) { $("#mkx", o.el).textContent = x.message; }
  });
  const marx = $("#marx", o.el);
  if (marx) marx.addEventListener("click", async () => {
    if (!m.arxiv && !confirm(`«${m.ism}» arxivga olinsinmi? Ro'yxatdan yo'qoladi, tarixi saqlanadi, istalgan vaqt qaytarasiz.`)) return;
    try { await api(`/api/mijoz/${id}`, {body: {arxiv: !m.arxiv}}); o.yop(); KESH = null; xabar(m.arxiv ? "Arxivdan qaytarildi" : "Arxivga olindi"); yonalish(); } catch (x) { $("#mkx", o.el).textContent = x.message; }
  });
  const mbir = $("#mbir", o.el);
  if (mbir) mbir.addEventListener("click", async () => {
    const ml = await malumotlar();
    const royxat = (mijozmi ? ml.mijozlar : ml.taminotchilar).filter(x => x.id !== id);
    const b = oyna("Ikki kartani birlashtirish", `<p style="color:var(--matn2);margin-bottom:12px">«${H(m.ism)}» kartasidagi hamma yozuvlar, va'dalar va eslatmalar tanlangan kartaga o'tadi, «${H(m.ism)}» ro'yxatdan yo'qoladi.</p>
      <label class="maydon"><span>Qaysi kartaga</span><select id="kimga">${royxat.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select></label><div class="xato-m" id="bx"></div>`,
      `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="bok" ${royxat.length ? "" : "disabled"}>Birlashtirish</button>`);
    $("#bok", b.el).addEventListener("click", async () => {
      try { await api(`/api/mijoz/${id}/birlashtir`, {body: {kimga: +$("#kimga", b.el).value}}); b.yop(); o.yop(); KESH = null; xabar("Birlashtirildi"); yonalish(); } catch (x) { $("#bx", b.el).textContent = x.message; }
    });
  });
  const mtf = $("#mtf", o.el);
  if (mtf) mtf.addEventListener("submit", async e => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(mtf));
    try { await api(`/api/mijoz/${id}`, {body}); xabar("Saqlandi"); KESH = null; ozgardi = true; qayta(); } catch (x) { $("#mkx", o.el).textContent = x.message; }
  });
}

/* ---------- Va'dalar (C3, C4) ---------- */
async function vadaSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const f = ["ochiq", "bugun", "buzilgan", "hammasi"].includes(params.get("f")) ? params.get("f") : "ochiq";
  const d = await api(`/api/vadalar?f=${f}`);
  nishonQoy("vadalar", d.nishon);
  const tab = (k, n, s) => `<a href="#/vadalar?f=${k}" ${f === k ? 'style="font-weight:800"' : ""}>${n}${s !== undefined ? ` · ${s}` : ""}</a>`;
  const bosh_ = {ochiq: "Kutilayotgan va'da yo'q.", bugun: "Bugunga va'da yo'q.", buzilgan: "Bajarilmagan va'da yo'q.", hammasi: "Hali va'da yozilmagan."}[f];
  main.innerHTML = tepa("Va'dalar", [tab("ochiq", "Kutilmoqda", d.soni.ochiq), tab("bugun", "Bugun", d.soni.bugun), tab("buzilgan", "Bajarilmagan", d.soni.buzilgan), tab("hammasi", "Hammasi")].join('<span class="n"></span>'),
    `<button class="btn asosiy" id="vyoz"><i class="ti ti-plus"></i>Va'da yozish</button>`)
    + (d.tushum ? `<section class="kpi"><div class="k"><div class="kb0"><i class="ti ti-arrow-down-left"></i>Bugun kutilayotgan tushum</div><div class="kr raqam">${H(d.tushum.bugun.t.replace(/[\s ]so'm$/, ""))}<small>so'm</small></div><div class="ki">Bugun muddati kelgan to'lov va'dalari</div></div>
      <div class="k"><div class="kb0"><i class="ti ti-calendar-dollar"></i>30 kunda kutilayotgan</div><div class="kr raqam">${H(d.tushum.oy.t.replace(/[\s ]so'm$/, ""))}<small>so'm</small></div><div class="ki">Faqat muddati o'tmagan va'dalar — aniq pul emas</div></div>
      <div class="k ${d.soni.buzilgan ? "xavf" : ""}"><div class="kb0"><i class="ti ti-heart-broken"></i>Bajarilmagan</div><div class="kr raqam">${d.soni.buzilgan}<small>ta va'da</small></div><div class="ki">Muddati o'tib, to'liq bajarilmagan</div></div></section>` : "")
    + `<section class="karta">${d.vadalar.length ? `<div class="jadval-o"><table class="jadval"><thead><tr><th>Muddat</th><th>Mijoz</th><th>Va'da</th><th class="son">To'landi</th><th>Kimga eslatiladi</th><th>Holat</th><th></th></tr></thead><tbody>
      ${d.vadalar.map(v => `<tr class="bosiladi ${v.holat === "bekor" ? "bekor" : ""}" data-mk="${v.mijoz_id}"><td>${v.bugun ? `<b>Bugun</b>` : v.muddat_matn}</td><td><b>${H(v.mijoz)}</b></td>
        <td>${v.kim === "biz" ? `<span class="chip">biz va'da berganmiz</span><br>` : ""}${H(v.tur === "tolov" ? (v.summa ? v.summa.t : "") : v.matn)}${v.iqtibos ? `<br><small class="iqt">«${H(v.iqtibos)}»</small>` : ""}</td>
        <td class="son">${v.qoplandi && v.qoplandi.m ? H(v.qoplandi.t) : "—"}${v.qolgan && v.qolgan.m && v.qoplandi && v.qoplandi.m ? `<br><small>qolgani ${H(v.qolgan.t)}</small>` : ""}</td>
        <td>${H(v.masul || "—")}</td><td><span class="chip ${VADA_RANG[v.holat_h] || ""}">${H(v.holat_nomi)}</span></td>
        <td class="amal">${v.holat === "ochiq" && (v.tur === "boshqa" || v.kim === "biz") && ["ochiq", "buzildi"].includes(v.holat_h) ? `<button class="btn kichik" data-vyop="${v.id}" data-ha="1">Bajarildi</button> ` : ""}${v.holat === "ochiq" && !["vaqtida", "kech"].includes(v.holat_h) && MEN.boshliq ? vadaTahrirTugma(v) + " " : ""}${v.holat === "ochiq" && !["vaqtida", "kech"].includes(v.holat_h) && (MEN.boshliq || MEN.odam.rol === "menejer") ? `<button class="btn kichik xavf" data-vbekor="${v.id}">Bekor</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
      : `<div class="bosh"><i class="ti ti-heart-handshake"></i>${bosh_} Botga «Karimov juma kuni 2 mln to'layman dedi» desangiz, kartochka chiqadi.</div>`}</section>`;
  main.addEventListener("click", e => {
    if (e.target.closest("button,a")) return vadaTugmalari(e);
    const r = e.target.closest("[data-mk]");
    if (r) mijozOyna(+r.dataset.mk, () => yonalish());
  });
  $("#vyoz").addEventListener("click", async () => {
    const m = await malumotlar();
    const o = oyna("Va'da yozish", vadaForma(m.mijozlar));
    vadaFormaUlash($(".vf", o.el), () => { o.yop(); yonalish(); });
  });
}

/* ---------- pul oqimi (P8) ---------- */
function pulOqimi(p) {
  const n = p.nuqtalar, en = n.length - 1;
  const qiymat = n.flatMap(x => [x.aniq, x.vada]).concat([0]);
  const past = Math.min(...qiymat), tepa_ = Math.max(...qiymat), oraliq = Math.max(1, tepa_ - past);
  const y = v => (96 - (v - past) / oraliq * 90).toFixed(2), x = i => (i / en * 300).toFixed(2);
  const chiziq = k => n.map((t, i) => `${x(i)},${y(t[k])}`).join(" ");
  const mk = n.findIndex(t => t.sana === p.maosh_kun);
  const aniqOxir = n[en].aniq, vadaOxir = n[en].vada;
  return `<section class="karta"><div class="kb"><h2>Pul oqimi · 30 kun</h2><span class="izoh">qo'ldagi pul va va'dalar</span></div>
    <svg class="oqim" viewBox="0 0 300 100" preserveAspectRatio="none" role="img" aria-label="30 kunlik pul oqimi: aniq pul ${guruh(aniqOxir)} so'm, va'dalar bajarilsa ${guruh(vadaOxir)} so'm">
      ${past < 0 ? `<line x1="0" x2="300" y1="${y(0)}" y2="${y(0)}" class="nol"/>` : ""}
      ${mk >= 0 ? `<line x1="${x(mk)}" x2="${x(mk)}" y1="4" y2="96" class="mk"/>` : ""}
      <polyline points="${chiziq("vada")}" class="vada"/><polyline points="${chiziq("aniq")}" class="aniq"/></svg>
    <div class="oqim-o"><small>Bugun</small>${mk >= 0 ? `<small>Maosh · ${sanaMatn(p.maosh_kun)}</small>` : ""}<small>${sanaMatn(n[en].sana)}</small></div>
    <div class="hafta"><div><small>Aniq pul, 30 kundan keyin</small><b class="raqam ${aniqOxir < 0 ? "q" : ""}">${H(qisqa(aniqOxir))}</b></div>
      <div><small>Va'dalar bajarilsa</small><b class="raqam y">${H(qisqa(vadaOxir))}</b></div>
      <div><small>Eng kam nuqta</small><b class="raqam ${p.eng_kam.m < 0 ? "q" : ""}">${H(qisqa(p.eng_kam.m))}</b></div></div>
    <div class="legend"><span><i style="background:var(--matn)"></i>Aniq pul</span><span><i style="background:var(--kirim)"></i>Va'dalar bajarilsa</span>${mk >= 0 ? `<span><i style="background:var(--kut-ch)"></i>Maosh kuni</span>` : ""}</div></section>`;
}

/* ---------- ertalabki va haftalik xulosa (S6, S8) ---------- */
function xulosaKarta(x, soat) {
  return `<section class="karta" id="xk"><div class="kb"><h2>Ertalabki xulosa</h2>${x ? `<span class="chip ${x.qolip ? "" : "u"}">${x.qolip ? "tayyor qolip" : "raqamlari tekshirilgan"}</span>` : ""}
    <div class="ong"><button class="btn kichik" data-xulosa="hafta"><i class="ti ti-calendar-week"></i>Haftalik</button><button class="btn kichik" data-xulosa="kun">${x ? "Yangilash" : "Hozir yasash"}</button></div></div>
    ${x ? `<p class="xulosa-m">${H(x.matn)}</p>` : `<div class="bosh"><i class="ti ti-sun"></i>Har ish kuni ${H(soat || "08:30")} da botga keladi</div>`}</section>`;
}

async function xulosaTugma(e) {
  const b = e.target.closest("[data-xulosa]");
  if (!b) return;
  b.disabled = true;
  try {
    if (b.dataset.xulosa === "kun") {
      const r = await api("/api/xulosa/yasash", {body: {tur: "kun"}});
      $("#xk").outerHTML = xulosaKarta(r.xulosa);
      return;
    }
    let r = await api("/api/xulosa?tur=hafta");
    const dushanba = kunQosh(MEN.bugun, -((new Date(MEN.bugun + "T00:00:00").getDay() + 6) % 7));
    if (!r.xulosa || r.xulosa.sana < dushanba) r = await api("/api/xulosa/yasash", {body: {tur: "hafta"}});
    oyna("Haftalik xulosa", `<p class="xulosa-m">${H(r.xulosa.matn)}</p><p class="ki" style="margin-top:10px">${r.xulosa.qolip ? "Tayyor qolip" : "Sun'iy intellekt yozdi, raqamlari dastur hisobi bilan tekshirildi"} · har dushanba botga keladi</p>`);
  } catch (x) { xabar(x.message, true); } finally { b.disabled = false; }
}

/* ---------- Xotira arxivi (X1, X6) ---------- */
const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const ARXIV_IKON = {ovoz: "ti-microphone", matn: "ti-message", rasm: "ti-photo", fayl: "ti-paperclip"};

function arxivQator(x) {
  const fayl = `/api/fayl/${x.id}`;
  return `<div class="aq"><span class="tn ${x.tur === "ovoz" ? "vada" : ""}"><i class="ti ${ARXIV_IKON[x.tur] || "ti-point"}"></i></span><div>
    <b>${H(x.kim)}</b><small>${sanaMatn(x.vaqt)} ${H(x.vaqt.slice(11, 16))} · ${H(x.tur_nomi)}${x.uzatilgan ? ` · uzatilgan: ${H(x.uzatilgan)}` : ""}${x.ball ? ` · ${x.ball}/${x.jami} so'z mos` : ""}</small>
    ${x.parcha ? `<p>«${H(x.parcha)}»</p>` : ""}
    ${x.tur === "ovoz" && x.fayl ? `<audio controls preload="none" src="${fayl}${x.soniya != null ? `#t=${x.soniya.toFixed(1)}` : ""}"></audio>${x.soniya != null ? `<small>Topilgan joy: ${mmss(x.soniya)} dan</small>` : ""}` : ""}
    ${x.tur === "rasm" && x.fayl ? `<a href="${fayl}" target="_blank" rel="noopener"><img src="${fayl}" alt="Xabardagi rasm" loading="lazy"></a>` : ""}
    ${x.tur === "fayl" && x.fayl ? `<a class="btn kichik" href="${fayl}" target="_blank" rel="noopener"><i class="ti ti-paperclip"></i>Faylni ochish</a>` : ""}</div></div>`;
}

async function arxivSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const q = params.get("q") || "", tur = params.get("tur") || "";
  const d = await api(`/api/arxiv?${new URLSearchParams({q, tur})}`);
  const turlar = [["", "Hammasi"], ["ovoz", "Ovoz"], ["matn", "Yozma"], ["rasm", "Rasm"], ["fayl", "Fayl"]];
  main.innerHTML = tepa("Xotira arxivi", MEN.boshliq ? "Har ovoz, matn va rasm asl holida saqlanadi — so'z bilan qidiring" : "Siz yuborgan xabarlar asl holida")
    + `<section class="karta"><form class="filtr" id="af"><label class="maydon" style="flex:1 1 260px"><span>Qidirish</span><input type="text" name="q" value="${H(q)}" placeholder="Masalan: Karimov narx" autocomplete="off"></label>
      <label class="maydon"><span>Turi</span><select name="tur">${turlar.map(([k, n]) => `<option value="${k}" ${k === tur ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      <button class="btn asosiy" type="submit"><i class="ti ti-search"></i>Qidirish</button></form>
      <p class="ki" style="margin-bottom:4px">${d.qidiruv ? `${d.xabarlar.length} ta mos xabar` : "Oxirgi xabarlar"}</p>
      <div class="arxiv">${d.xabarlar.map(arxivQator).join("") || `<div class="bosh"><i class="ti ti-archive"></i>${d.qidiruv ? "Bunday so'zli xabar topilmadi" : "Hali xabar yo'q"}</div>`}</div></section>`;
  $("#af").addEventListener("submit", e => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    location.hash = `#/arxiv?${new URLSearchParams(Object.entries(f).filter(([, v]) => v))}`;
  });
}

/* ---------- Ish usullari (O5) ---------- */
async function usulSahifa(main) {
  const d = await api("/api/usullar");
  main.innerHTML = tepa("Ish usullari", "Xodim «buni qanday qilamiz?» deb so'rasa, miya faqat shu yerdagi matndan javob beradi",
    d.tahrir ? `<button class="btn asosiy" id="uyangi"><i class="ti ti-plus"></i>Usul yozish</button>` : "")
    + `<section class="karta">${d.usullar.length ? d.usullar.map(u => `<div class="vq"><div><b>${H(u.sarlavha)}</b><small class="usul-m">${H(u.matn)}</small>
        <small>${H(u.yozgan || "")} · ${sanaMatn(u.yangilangan || u.vaqt)}</small></div>
        ${d.tahrir ? `<div class="sa"><button class="btn kichik" data-utahrir="${u.id}">Tahrirlash</button><button class="btn kichik xavf" data-uochir="${u.id}">O'chirish</button></div>` : ""}</div>`).join("")
      : `<div class="bosh"><i class="ti ti-book"></i>Hali usul yozilmagan. Botga «Usul: Kafel yotqizish» deb, keyingi qatorga tartibini yozsangiz ham saqlanadi.</div>`}</section>`;
  const forma = u => {
    const o = oyna(u ? "Usulni tahrirlash" : "Yangi ish usuli", `<form id="uf" class="forma"><label class="maydon butun"><span>Nomi</span><input type="text" name="sarlavha" maxlength="120" value="${H(u ? u.sarlavha : "")}" placeholder="Kafel yotqizish" required></label>
      <label class="maydon butun"><span>Qanday qilinadi</span><textarea name="matn" rows="8" maxlength="4000" required placeholder="Tartibi, o'lchamlar, nimaga e'tibor berish kerak">${H(u ? u.matn : "")}</textarea></label><div class="xato-m butun" id="ux"></div></form>`,
      `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="uok">Saqlash</button>`);
    $("#uok", o.el).addEventListener("click", async () => {
      const f = Object.fromEntries(new FormData($("#uf", o.el)));
      try { await api(u ? `/api/usul/${u.id}` : "/api/usul", {body: f}); o.yop(); xabar("Saqlandi"); yonalish(); } catch (x) { $("#ux", o.el).textContent = x.message; }
    });
  };
  const yangi = $("#uyangi");
  if (yangi) yangi.addEventListener("click", () => forma(null));
  main.addEventListener("click", async e => {
    const t = e.target.closest("[data-utahrir]");
    if (t) return forma(d.usullar.find(u => u.id === +t.dataset.utahrir));
    const och = e.target.closest("[data-uochir]");
    if (och && confirm("Usul o'chirilsinmi? (jurnalda qoladi)")) {
      try { await api(`/api/usul/${och.dataset.uochir}`, {body: {ochir: true}}); yonalish(); } catch (x) { xabar(x.message, true); }
    }
  });
}

/* ---------- Xodim ketishi: topshirish varaqasi (O4) ---------- */
async function topshirishOyna(x) {
  let v;
  try { v = await api(`/api/odam/${x.id}/topshirish`); } catch (er) { return xabar(er.message, true); }
  const m = await malumotlar();
  const kimlar = m.odamlar.filter(o => o.holat === "faol" && o.id !== x.id);
  const bolak = (nom, royxat, fn, izoh = "") => `<h4>${nom} <span class="chip ${royxat.length ? "kut" : "y"}">${royxat.length ? royxat.length + " ta" : "yo'q"}</span></h4>${royxat.map(fn).join("")}${royxat.length && izoh ? `<p class="ki">${izoh}</p>` : ""}`;
  const qator = (b, s = "") => `<div class="vq"><div><b>${H(b)}</b>${s ? `<small>${H(s)}</small>` : ""}</div></div>`;
  const ichki = `<p class="ki">${v.tayyor ? "Hammasi topshirilgan — kirishni yopish mumkin." : "Quyidagilar topshirilgach kirish yopiladi. Ketmoqda paytida xodim faqat «Mening hisobim»ni ko'radi."}</p>
    ${bolak("Ochiq ishlari", v.ishlar, i => qator(i.qisqa))}
    ${bolak("Mas'ul mijozlari", v.mijozlar, c => qator(c.ism))}
    ${bolak("Ochiq va'dalari", v.vadalar, w => qator(`${w.mijoz} — ${w.matn}`, `${sanaMatn(w.muddat)} gacha`))}
    ${bolak("Mas'ul kassalari", v.kassalar, k => qator(k.nom, `qoldiq ${guruh(k.valyuta === "USD" ? k.qoldiq / 100 : k.qoldiq)} ${k.valyuta === "USD" ? "$" : "so'm"}`))}
    ${kimlar.length && (v.ishlar.length || v.mijozlar.length || v.vadalar.length || v.kassalar.length) ? `<form id="tf" class="forma" style="margin-top:12px"><label class="maydon"><span>Kimga o'tkaziladi</span><select name="kimga">${kimlar.map(o => `<option value="${o.id}">${H(o.ism)}</option>`).join("")}</select></label>
      <div class="maydon"><span>Nimalar</span><div class="tanlov">${[["ishlar", "Ishlar"], ["mijozlar", "Mijozlar"], ["vadalar", "Va'dalar"], ["kassalar", "Kassalar"]].map(([k, n]) => `<label class="belgi"><input type="checkbox" name="nimalar" value="${k}" checked> ${n}</label>`).join("")}</div></div>
      <div class="butun"><button class="btn asosiy" type="submit"><i class="ti ti-transfer"></i>O'tkazish</button></div></form>` : ""}
    ${bolak("Qo'lidagi ishxona puli", v.qolida, p => qator(p.matn), "Kassaga topshirgani «Yozuv qo'shish → Xodim pulni kassaga topshirdi» bilan yoziladi")}
    ${bolak("Ishxonaga qarzi", v.qarzi, p => qator(p.matn), "Maoshdan ushlash yoki naqd qaytarish bilan yopiladi")}
    ${bolak("Maosh qoldig'i", v.maosh_qolgani.summa ? [v.maosh_qolgani] : [], p => qator(p.matn), "Oxirgi maosh «Maosh to'lovi» bilan beriladi — xodim botda «oldim» deydi")}
    ${bolak("Tasdiq kutayotgan yozuvlari", v.kutmoqda, h => qator(h.tavsif))}
    <div class="xato-m" id="tx"></div>`;
  const o = oyna(`${x.ism} — topshirish varaqasi`, ichki, `<button class="btn" data-yop>Yopish</button><button class="btn ${v.tayyor ? "asosiy" : "xavf"}" id="tyop"><i class="ti ti-user-off"></i>${v.tayyor ? "Kirishni yopish" : "Baribir yopish"}</button>`);
  o.el.querySelector(".oyna").classList.add("keng");
  const tf = $("#tf", o.el);
  if (tf) tf.addEventListener("submit", async e => {
    e.preventDefault();
    const nimalar = $$("[name=nimalar]:checked", tf).map(c => c.value);
    try {
      const r = await api(`/api/odam/${x.id}/topshir`, {body: {kimga: +tf.kimga.value, nimalar}});
      xabar(`O'tkazildi: ${r.ishlar} ish, ${r.mijozlar} mijoz, ${r.vadalar} va'da, ${r.kassalar} kassa`);
      o.yop(); KESH = null; topshirishOyna(x);
    } catch (er) { $("#tx", o.el).textContent = er.message; }
  });
  $("#tyop", o.el).addEventListener("click", async () => {
    let sabab = null;
    if (!v.tayyor) {
      sabab = prompt("Topshirish tugamagan. Baribir yopish sababi (jurnalga yoziladi):");
      if (!sabab) return;
    } else if (!confirm(`${x.ism} uchun kirish yopilsinmi?`)) return;
    try { await api(`/api/odam/${x.id}/holat`, {body: {holat: "ketgan", sabab}}); o.yop(); KESH = null; xabar("Kirish yopildi"); yonalish(); } catch (er) { $("#tx", o.el).textContent = er.message; }
  });
}

async function tgHavolaOyna(x) {
  const ozi = x.id === MEN.odam.id;
  try {
    const r = await api(`/api/odam/${x.id}/taklif`, {body: {}});
    const o = oyna(ozi ? "Telegram'ga ulanish" : `${x.ism} — Telegram'ga ulash`, r.havola
      ? `<p style="margin-bottom:10px;color:var(--matn2)">${ozi ? "Telefoningizda shu havolani oching va «Start» bosing — bot sizni taniydi." : `Shu havolani ${H(x.ism)}ga yuboring. U bosib «Start» desa, bot uni taniydi.`} Havola bir martalik, ${r.muddat_kun} kun amal qiladi.</p><div class="nusxa"><span id="hv">${H(r.havola)}</span></div>`
      : `<p style="color:var(--matn2)">Bot hali ulanmagan. «Sozlamalar»da bot tokenini kiriting, keyin havola tayyor bo'ladi. Kod: <b>${H(r.kod)}</b></p>`,
      r.havola ? `${ozi ? `<a class="btn" href="${H(r.havola)}" target="_blank" rel="noopener"><i class="ti ti-brand-telegram"></i>Telegram'da ochish</a>` : ""}<button class="btn" id="nus"><i class="ti ti-copy"></i>Nusxa olish</button>` : "");
    const n = $("#nus", o.el);
    if (n) n.addEventListener("click", () => { navigator.clipboard.writeText(r.havola).then(() => xabar("Nusxa olindi")); });
  } catch (er) { xabar(er.message, true); }
}

/* ---------- Xodimlar ---------- */
async function xodimSahifa(main) {
  const [d, k] = await Promise.all([api("/api/odamlar"), api("/api/kassalar")]);
  main.innerHTML = tepa("Xodimlar", "Telegram'ga ulash, rol va panel paroli", `<button class="btn" id="oadd"><i class="ti ti-user-plus"></i>Xodim qo'shish</button>`)
    + `<section class="karta"><div class="jadval-o"><table class="jadval"><thead><tr><th>Xodim</th><th>Rol</th><th>Telegram</th><th>Panel</th><th>Holat</th><th></th></tr></thead><tbody>
    ${d.odamlar.map(x => `<tr><td><b>${H(x.ism)}</b><br><small>${H(x.lavozim || "")}${x.telefon ? " · " + H(x.telefon) : ""}</small></td>
      <td>${H(x.rol_nomi)}${x.maosh_tolaydi ? `<br><small>maosh to'laydi</small>` : ""}</td>
      <td>${x.telegram ? `<span class="chip y"><i class="ti ti-check"></i>ulangan</span>` : `<button class="btn kichik" data-taklif="${x.id}"><i class="ti ti-brand-telegram"></i>Havola</button>`}</td>
      <td>${x.parol_bor ? `<button class="btn kichik" data-parolkor="${x.id}">${H(x.login)} · parol</button>` : `<button class="btn kichik" data-parol="${x.id}">Parol qo'yish</button>`}</td>
      <td><span class="chip ${x.holat === "faol" ? "y" : x.holat === "ketmoqda" ? "kut" : ""}">${{faol: "faol", ketmoqda: "ketmoqda", ketgan: "ketgan"}[x.holat]}</span></td>
      <td><button class="btn kichik" data-karta="${x.id}">Karta</button> <button class="btn kichik" data-tahrir="${x.id}">Tahrirlash</button>${x.holat === "ketmoqda" ? ` <button class="btn kichik" data-topsh="${x.id}"><i class="ti ti-transfer"></i>Topshirish</button>` : ""}</td></tr>`).join("")}</tbody></table></div></section>`;
  $("#oadd").addEventListener("click", () => odamOyna(null, k.kassalar));
  main.addEventListener("click", async e => {
    const kt = e.target.closest("[data-karta]");
    if (kt) return xodimKartaOyna(+kt.dataset.karta);
    const tp = e.target.closest("[data-topsh]");
    if (tp) return topshirishOyna(d.odamlar.find(o => o.id === +tp.dataset.topsh));
    const t = e.target.closest("[data-taklif],[data-parol],[data-parolkor],[data-tahrir]");
    if (!t) return;
    const x = d.odamlar.find(o => o.id === +(t.dataset.taklif || t.dataset.parol || t.dataset.parolkor || t.dataset.tahrir));
    if (t.dataset.taklif) tgHavolaOyna(x);
    if (t.dataset.parol) return parolOyna(x);
    if (t.dataset.parolkor) {
      try {
        const r = await api(`/api/odam/${x.id}/parol`);
        const o = oyna(`${x.ism} — panel kirishi`, `<div class="varaq-q"><span>Login</span><b>${H(x.login)}</b></div><div class="varaq-q"><span>Parol</span><b>${H(r.parol || "saqlanmagan — yangisini qo'ying")}</b></div>`,
          `<button class="btn" id="pyangi">Parolni o'zgartirish</button>`);
        $("#pyangi", o.el).addEventListener("click", () => { o.yop(); parolOyna(x); });
      } catch (er) { xabar(er.message, true); }
    }
    if (t.dataset.tahrir) odamOyna(x, k.kassalar);
  });
}

function odamOyna(x, kassalar) {
  const rol = x ? x.rol : "xodim";
  const o = oyna(x ? `${x.ism} — tahrirlash` : "Xodim qo'shish", `<form id="of" class="forma">
    <label class="maydon butun"><span>Ism familiya</span><input type="text" name="ism" required value="${H(x ? x.ism : "")}"></label>
    <label class="maydon"><span>Rol</span><select name="rol">${[["xodim", "Xodim — faqat o'z hisobi"], ["kassir", "Kassir — kassa va to'lovlar"], ["menejer", "Menejer — mijozlar va sotuv"], ["boshliq", "Boshliq — hammasi"]].map(([k, n]) => `<option value="${k}" ${k === rol ? "selected" : ""}>${n}</option>`).join("")}</select></label>
    <label class="maydon"><span>Lavozim</span><input type="text" name="lavozim" value="${H(x ? x.lavozim || "" : "")}" placeholder="Usta"></label>
    <label class="maydon"><span>Telefon</span><input type="text" name="telefon" value="${H(x ? x.telefon || "" : "")}"></label>
    ${x ? "" : `<label class="maydon"><span>Login</span><input type="text" name="login" autocomplete="off" placeholder="akmal"><small>Panelga kirish uchun</small></label>
      <label class="maydon"><span>Parol</span><input type="text" name="parol" autocomplete="off" minlength="6"><small>Bitta doimiy parol — keyin «parol» tugmasi bilan ko'rasiz</small></label>`}
    ${x ? `<label class="maydon"><span>Odatdagi kassasi</span><select name="kassa_id"><option value="">—</option>${kassalar.map(k => `<option value="${k.id}" ${x.kassa_id === k.id ? "selected" : ""}>${H(k.nom)}</option>`).join("")}</select></label>` : ""}
    <label class="belgi butun"><input type="checkbox" name="maosh_tolaydi" ${x && x.maosh_tolaydi ? "checked" : ""}> Maosh to'lay oladi (faqat «to'lash kerak» summasini ko'radi)</label>
    ${x && x.id !== MEN.odam.id ? `<label class="maydon"><span>Holat</span><select name="holat">${[["faol", "Faol"], ["ketmoqda", "Ketmoqda — faqat o'z hisobini ko'radi"], ["ketgan", "Ketgan — kirish yopiq"]].map(([k, n]) => `<option value="${k}" ${k === x.holat ? "selected" : ""}>${n}</option>`).join("")}</select></label>` : ""}
    <div class="xato-m butun" id="ox"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="ook">Saqlash</button>`);
  if (!x) {  // login ismdan taklif qilinadi: «Akmal Toshpo'latov» → akmal (o'zgartirsa bo'ladi)
    const f = $("#of", o.el);
    let qolda = false;
    f.login.addEventListener("input", () => { qolda = true; });
    f.ism.addEventListener("input", () => {
      if (qolda) return;
      f.login.value = (f.ism.value.trim().split(/\s+/)[0] || "").toLowerCase().replace(/[ʻʼ’'`‘]/g, "")
        .replace(/[^a-z0-9._-]/g, "");
    });
  }
  $("#ook", o.el).addEventListener("click", async () => {
    const f = $("#of", o.el);
    const d = {ism: f.ism.value, rol: f.rol.value, lavozim: f.lavozim.value, telefon: f.telefon.value, maosh_tolaydi: f.maosh_tolaydi.checked ? 1 : 0};
    try {
      if (x) {
        if (f.kassa_id) d.kassa_id = f.kassa_id.value ? +f.kassa_id.value : null;
        await api(`/api/odam/${x.id}`, {body: d});
        if (f.holat && f.holat.value === "ketgan" && x.holat !== "ketgan") { o.yop(); KESH = null; return topshirishOyna(x); }
        if (f.holat && f.holat.value !== x.holat) await api(`/api/odam/${x.id}/holat`, {body: {holat: f.holat.value}});
        if (f.holat && f.holat.value === "ketmoqda" && x.holat === "faol") { o.yop(); KESH = null; yonalish(); return topshirishOyna({...x, holat: "ketmoqda"}); }
      } else {
        if (f.login.value.trim()) {
          if (f.parol.value.length < 6) { $("#ox", o.el).textContent = "Parol kamida 6 belgi bo'lsin"; return; }
          d.login = f.login.value.trim(); d.parol = f.parol.value;
        }
        await api("/api/odam", {body: d});
      }
      o.yop(); KESH = null; yonalish();
    } catch (er) { $("#ox", o.el).textContent = er.message; }
  });
}

function parolOyna(x) {
  const o = oyna(`${x.ism} — panel paroli`, `<form id="pf" class="forma"><label class="maydon"><span>Login</span><input type="text" name="login" value="${H(x.login || "")}" required minlength="3"></label>
    <label class="maydon"><span>Parol</span><input type="text" name="parol" required minlength="6"><small>Bitta doimiy parol — keyin «parol» tugmasi bilan ko'rasiz</small></label><div class="xato-m butun" id="px"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="pok">Saqlash</button>`);
  $("#pok", o.el).addEventListener("click", async () => {
    const f = $("#pf", o.el);
    try { await api(`/api/odam/${x.id}/parol`, {body: {login: f.login.value, parol: f.parol.value}}); o.yop(); xabar("Parol saqlandi"); yonalish(); } catch (er) { $("#px", o.el).textContent = er.message; }
  });
}

/* ---------- Qoidalar ---------- */
async function qoidaSahifa(main) {
  const d = await api("/api/qoidalar");
  main.innerHTML = tepa("Boshliq qoidalari", "Qoidaga mos yozuv o'zi o'tadi, mos kelmasa — sizdan ruxsat so'raladi")
    + `<div class="ustun2"><section class="karta"><div class="kb"><h2>Amaldagi qoidalar</h2></div>
      ${d.qoidalar.length ? d.qoidalar.map(q => `<div class="holat-q"><div><b>${H(q.tavsif)}</b>${q.matn ? `<small>«${H(q.matn)}»</small>` : ""}</div><button class="btn kichik xavf" data-ochir="${q.id}">O'chirish</button></div>`).join("")
        : `<div class="bosh"><i class="ti ti-scale"></i>Hali qoida yo'q</div>`}</section>
      <section class="karta"><div class="kb"><h2>Yangi qoida</h2></div>
        <form id="qm" class="forma"><label class="maydon butun"><span>Oddiy so'z bilan yozing</span><textarea name="matn" placeholder="Avans oyiga bir marta, maoshning 30 foizidan oshmasin" ${MEN.xizmat.ai ? "" : "disabled"}></textarea>
        ${MEN.xizmat.ai ? "" : `<small>Sun'iy intellekt yoqilmagan — pastdagi tayyor shakldan foydalaning</small>`}</label>
        <div class="butun"><button class="btn" type="submit" ${MEN.xizmat.ai ? "" : "disabled"}><i class="ti ti-sparkles"></i>Tushunib ko'rish</button></div></form>
        <div id="qt"></div>
        <form id="qf" class="forma" style="margin-top:16px;border-top:1px solid var(--chiziq);padding-top:14px">
          <label class="maydon butun"><span>Yoki tayyor shakl</span><select name="tur">${Object.entries(d.turlar).map(([k, n]) => `<option value="${k}">${H(n)}</option>`).join("")}</select></label>
          <label class="maydon"><span>Qiymat</span><input type="text" name="qiymat" required placeholder="30 yoki 1 000 000"><small>Foiz, soni yoki summa</small></label>
          <div class="butun"><button class="btn asosiy" type="submit">Qo'yish</button></div><div class="xato-m butun" id="qx"></div></form></section></div>`;
  main.addEventListener("click", async e => {
    const t = e.target.closest("[data-ochir]");
    if (t && confirm("Qoida o'chirilsinmi?")) { await api(`/api/qoida/${t.dataset.ochir}/ochir`, {body: {}}); yonalish(); }
  });
  $("#qm").addEventListener("submit", async e => {
    e.preventDefault();
    const matn = e.target.matn.value.trim();
    if (!matn) return;
    $("#qt").innerHTML = `<p class="ki" style="margin-top:10px">O'ylayapman…</p>`;
    try {
      const r = await api("/api/qoida/matndan", {body: {matn}});
      if (r.tushmadi) { $("#qt").innerHTML = `<div class="kutish"><div><b>Dastur bu qoidani tekshira olmaydi</b><small>${H(r.sabab)}</small></div></div>`; return; }
      $("#qt").innerHTML = `<div class="kutish"><div><b>Dastur shunday tushundi:</b><small style="color:var(--matn)">${H(r.matn)}</small></div><div></div><div class="sa"><button class="btn asosiy kichik" id="qsaqla">To'g'ri, saqlash</button></div></div>`;
      $("#qsaqla").addEventListener("click", async () => { await api("/api/qoida", {body: {tur: r.tur, param: r.param, matn}}); xabar("Qoida qo'yildi"); yonalish(); });
    } catch (x) { $("#qt").innerHTML = `<div class="xato-m">${H(x.message)}</div>`; }
  });
  $("#qf").addEventListener("submit", async e => {
    e.preventDefault();
    const f = e.target, tur = f.tur.value, q = f.qiymat.value;
    const param = tur === "avans_foiz" ? {foiz: parseFloat(q.replace(",", "."))} : tur === "avans_soni" ? {soni: parseInt(q)} : {summa: sonOqi(q), valyuta: "UZS"};
    try { await api("/api/qoida", {body: {tur, param}}); xabar("Qoida qo'yildi"); yonalish(); } catch (x) { $("#qx").textContent = x.message; }
  });
}

/* ---------- Sozlamalar ---------- */
async function sozlamaSahifa(main) {
  const d = await api("/api/sozlamalar");
  const kalit = (tur, nom, izoh, bor) => `<div class="holat-q"><div><b>${nom} ${bor ? `<span class="chip y">kiritilgan</span>` : `<span class="chip kut">kiritilmagan</span>`}</b><small>${izoh}</small></div>
    <button class="btn kichik" data-kalit="${tur}">${bor ? "Almashtirish" : "Kiritish"}</button></div>`;
  main.innerHTML = tepa("Sozlamalar", "Ulanishlar, ish tartibi va xarajat")
    + `<div class="ustun2"><div class="ust"><section class="karta"><div class="kb"><h2>Ulanishlar</h2></div>
        ${kalit("bot", "Telegram bot", d.bot_ishlayapti ? (d.bot_xato ? `⚠ ${H(d.bot_xato)}` : `Ishlayapti: @${H(d.bot_nomi)}`) : "@BotFather'dan olingan token. Bot ishlamasa xodimlar ulana olmaydi", d.kalitlar.bot)}
        ${kalit("anthropic", "Sun'iy intellekt (Claude)", "Anthropic kaliti — console.anthropic.com", d.kalitlar.anthropic)}
        ${kalit("google", "Ovozni yozuvga aylantirish (Google)", "Google Cloud API kaliti, Speech-to-Text yoqilgan bo'lsin", d.kalitlar.google)}
        <div class="holat-q"><div><b>Sun'iy intellekt versiyasi</b><small>Haiku 4.5 — eng arzon (standart); Sonnet 5 — 2 baravar, Opus 5 — 5 baravar qimmat</small></div>
          <select id="model" style="width:auto">${[["claude-haiku-4-5", "Haiku 4.5"], ["claude-sonnet-5", "Sonnet 5"], ["claude-opus-5", "Opus 5"]].map(([k, n]) => `<option value="${k}" ${d.ai_model === k ? "selected" : ""}>${n}</option>`).join("")}</select></div>
      </section>
      <section class="karta"><div class="kb"><h2>Ish tartibi</h2></div><form id="if" class="forma">
        <label class="maydon"><span>Maosh kunlari</span><input type="text" name="maosh_kunlari" value="${d.maosh_kunlari.join(", ")}"><small>Masalan: 10, 25</small></label>
        <label class="maydon"><span>Kassa sanog'i eslatmasi</span><input type="time" name="kassa_sanoq_vaqti" value="${H(d.kassa_sanoq_vaqti)}"></label>
        <label class="maydon butun"><span>Domen (Telegram ichidagi oyna uchun)</span><input type="text" name="domen" value="${H(d.domen)}" placeholder="https://miya.misol.uz"><small>Bo'sh bo'lsa hisob chatning o'zida ko'rsatiladi</small></label>
        <label class="belgi butun"><input type="checkbox" name="guruh_ovoz" ${d.guruh_ovoz ? "checked" : ""}> Ish guruhidagi ovozli xabarlarni ham yozish (xarajat oshadi)</label>
        <label class="maydon"><span>Ertalabki ro'yxat</span><input type="time" name="ertalab_vaqti" value="${H(d.ertalab_vaqti)}"></label>
        <label class="maydon"><span>Boshliqqa ertalabki xulosa</span><input type="time" name="brifing_vaqti" value="${H(d.brifing_vaqti)}"></label>
        <label class="maydon"><span>Kechki savol</span><input type="time" name="kechki_vaqt" value="${H(d.kechki_vaqt)}"></label>
        <label class="maydon"><span>Ish boshlanishi (kechikish uchun)</span><input type="time" name="ish_boshlanishi" value="${H(d.ish_boshlanishi)}"></label>
        <label class="maydon"><span>Ish dalili (standart)</span><select name="dalil_standart">${DALIL.map(([k, n]) => `<option value="${k}" ${d.dalil_standart === k ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <div class="maydon butun"><span>Dam olish kunlari</span><div class="tugmalar">${HAFTA_K.map((k, i) => `<label class="belgi"><input type="checkbox" name="dam" value="${i}" ${d.dam_olish_kunlari.includes(i) ? "checked" : ""}> ${k}</label>`).join("")}</div></div>
        <label class="maydon"><span>Ofis kengligi (lat)</span><input type="text" name="ofis_lat" value="${d.ofis_joylashuvi ? d.ofis_joylashuvi.lat : ""}" placeholder="41.3111"></label>
        <label class="maydon"><span>Ofis uzunligi (lon)</span><input type="text" name="ofis_lon" value="${d.ofis_joylashuvi ? d.ofis_joylashuvi.lon : ""}" placeholder="69.2797"><small>«Keldim» ofisdan uzoqda bo'lsa belgilanadi</small></label>
        <div class="butun"><button class="btn asosiy" type="submit">Saqlash</button></div><div class="xato-m butun" id="ix"></div></form></section></div>
      <div class="ust"><section class="karta"><div class="kb"><h2>Shu oy xarajati</h2></div>
        <div class="varaq-q"><span>Sun'iy intellekt · ${d.sarf.ai_soni} ta murojaat</span><b>$${d.sarf.ai_dollar}</b></div>
        <div class="varaq-q"><span>Ovoz · ${d.sarf.ovoz_daqiqa} daqiqa</span><b>$${d.sarf.ovoz_dollar}</b></div></section>
      <section class="karta"><div class="kb"><h2>Zaxira nusxa</h2><span class="ong"><button class="btn kichik" id="zxol"><i class="ti ti-database-export"></i>Hozir olish</button></span></div>
        ${d.zaxira ? `<div class="varaq-q"><span>Oxirgi nusxa</span><b>${H(String(d.zaxira.vaqt || "").replace("T", " ").slice(0, 16))}</b></div>
          <div class="varaq-q"><span>Tekshiruv</span><b class="${d.zaxira.butun && d.zaxira.mos ? "y" : "q"}">${d.zaxira.butun && d.zaxira.mos ? `butun · ${d.zaxira.harakat} yozuv` : "muammo bor"}</b></div>` : `<div class="bosh">Hali nusxa olinmagan — har kecha 03:30 da o'zi oladi</div>`}
        <form id="zf" class="filtr"><label class="maydon" style="flex:1"><span>Ikkinchi joy (boshqa disk)</span><input type="text" name="yol2" value="${H(d.zaxira_yol2)}" placeholder="/mnt/disk2/miya"></label><button class="btn" type="submit">Saqlash</button></form></section>
      <section class="karta"><div class="kb"><h2>Xarajat turlari</h2></div>
        ${d.xarajat_turlari.filter(x => x.faol).map(x => `<div class="holat-q"><div><b>${H(x.nom)}</b></div><button class="btn kichik" data-xochir="${x.id}">Olib tashlash</button></div>`).join("")}
        <form id="xf" class="filtr"><label class="maydon"><span>Yangi tur</span><input type="text" name="nom" required></label><button class="btn" type="submit">Qo'shish</button></form></section></div></div>`;
  main.addEventListener("click", async e => {
    const t = e.target.closest("[data-kalit],[data-xochir]");
    if (!t) return;
    if (t.dataset.xochir) { await api("/api/sozlamalar", {body: {xarajat_turi_ochir: +t.dataset.xochir}}); return yonalish(); }
    const nomlar = {bot: "Telegram bot tokeni", anthropic: "Anthropic kaliti", google: "Google kaliti"};
    const o = oyna(nomlar[t.dataset.kalit], `<p style="color:var(--matn2);margin-bottom:12px">Kalit shifrlangan holda saqlanadi va qayta ko'rsatilmaydi. Uni hech kimga, chatga ham yozmang.</p>
      <label class="maydon"><span>Kalit</span><input type="password" id="kq" autocomplete="off"></label><small class="ki" style="margin-top:6px">Saqlashdan oldin kalit ishlashi tekshiriladi — bu pul sarflamaydi.</small><div class="xato-m" id="kx"></div>`,
      `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="kok">Saqlash</button>`);
    $("#kok", o.el).addEventListener("click", async () => {
      try {
        const r = await api("/api/kalit", {body: {tur: t.dataset.kalit, qiymat: $("#kq", o.el).value}});
        if (r.xato) { $("#kx", o.el).textContent = r.xato; return; }
        o.yop(); xabar("Kalit tekshirildi va saqlandi"); MEN = await api("/api/men"); yonalish();
      } catch (x) { $("#kx", o.el).textContent = x.message; }
    });
  });
  $("#model").addEventListener("change", async e => { await api("/api/sozlamalar", {body: {ai_model: e.target.value}}); xabar("Saqlandi"); });
  $("#if").addEventListener("submit", async e => {
    e.preventDefault();
    const f = e.target;
    try {
      await api("/api/sozlamalar", {body: {maosh_kunlari: f.maosh_kunlari.value.split(/[,\s]+/).filter(Boolean).map(Number),
        kassa_sanoq_vaqti: f.kassa_sanoq_vaqti.value, domen: f.domen.value, guruh_ovoz: f.guruh_ovoz.checked,
        ertalab_vaqti: f.ertalab_vaqti.value, kechki_vaqt: f.kechki_vaqt.value, brifing_vaqti: f.brifing_vaqti.value, ish_boshlanishi: f.ish_boshlanishi.value,
        dalil_standart: f.dalil_standart.value, dam_olish_kunlari: $$("input[name=dam]:checked", f).map(x => +x.value),
        ofis_joylashuvi: f.ofis_lat.value && f.ofis_lon.value ? {lat: f.ofis_lat.value, lon: f.ofis_lon.value} : null}});
      xabar("Saqlandi");
    } catch (x) { $("#ix").textContent = x.message; }
  });
  $("#xf").addEventListener("submit", async e => { e.preventDefault(); await api("/api/sozlamalar", {body: {xarajat_turi_yangi: e.target.nom.value}}); KESH = null; yonalish(); });
  $("#zxol").addEventListener("click", async e => {
    e.target.disabled = true;
    try { const r = await api("/api/zaxira", {body: {}}); xabar(r.butun && r.mos ? "Nusxa olindi va tekshirildi" : "Nusxada muammo bor", !(r.butun && r.mos)); yonalish(); }
    catch (x) { xabar(x.message, true); e.target.disabled = false; }
  });
  $("#zf").addEventListener("submit", async e => { e.preventDefault(); try { await api("/api/sozlamalar", {body: {zaxira_yol2: e.target.yol2.value}}); xabar("Saqlandi"); } catch (x) { xabar(x.message, true); } });
}

/* ---------- Jurnal ---------- */
const AMAL = {odam_yarat: "Xodim qo'shildi", odam_tahrir: "Xodim tahrirlandi", odam_holat: "Xodim holati o'zgardi",
  taklif_yarat: "Telegram havolasi yaratildi", telegram_ulandi: "Telegram'ga ulandi", parol_qoyildi: "Parol qo'yildi",
  parol_korildi: "Parol ko'rildi", panelga_kirdi: "Panelga kirdi", kassa_yarat: "Kassa qo'shildi", kassa_tahrir: "Kassa tahrirlandi",
  harakat_faol: "Yozuv kiritildi", harakat_bekor: "Yozuv bekor qilindi", teskari_yozuv: "Teskari yozuv qilindi",
  tomon_tasdiq: "Tasdiqladi", tomon_rad: "Rad etdi", nizo_hal: "Nizo hal qilindi", ruxsat_soraldi: "Ruxsat so'raldi",
  ruxsat_berildi: "Ruxsat berildi", ruxsat_rad: "Ruxsat rad etildi", takror_birlashtirildi: "Takror birlashtirildi",
  kassa_sanoq: "Kassa sanaldi", maosh_shart: "Maosh sharti qo'yildi", maosh_shart_tugadi: "Maosh sharti tugadi",
  ish_kunlari: "Ish kunlari yozildi", oy_yopildi: "Oy yopildi", qoida_qoyildi: "Qoida qo'yildi", qoida_ochirildi: "Qoida o'chirildi",
  sozlama: "Sozlama o'zgardi", mijoz_yarat: "Mijoz qo'shildi", mijoz_birlashtirildi: "Mijozlar birlashtirildi",
  zaxira_olindi: "Zaxira nusxa olindi"};
async function jurnalSahifa(main) {
  const d = await api("/api/jurnal?limit=300");
  main.innerHTML = tepa("Jurnal", "Kim, qachon, nimani o'zgartirdi — hech narsa o'chirilmaydi")
    + `<section class="karta"><div class="jadval-o"><table class="jadval"><thead><tr><th>Vaqt</th><th>Kim</th><th>Amal</th><th>Nima</th><th>Tafsilot</th></tr></thead><tbody>
    ${d.jurnal.map(j => `<tr><td>${H(j.vaqt.replace("T", " ").slice(0, 16))}</td><td>${H(j.kim)}</td><td>${H(AMAL[j.amal] || j.amal.replace(/_/g, " "))}</td><td>${H(j.obyekt || "")}</td><td><small>${H((j.keyin || "").slice(0, 120))}</small></td></tr>`).join("")}</tbody></table></div></section>`;
}


/* ---------- Ishlar (I1–I8) ---------- */
const ISH_HOLAT = {yangi: ["Bajarilmoqda", "u"], bajarildi_dalil: ["Dalil kutilmoqda", "kut"], bajarildi: ["Bajarildi", "y"],
  qabul: ["Qabul qilindi", ""], qayta: ["Qayta ishlash", "q"], bekor: ["Bekor", ""]};
const DALIL = [["rasm", "Rasm"], ["joylashuv", "Joylashuv"], ["mijoz", "Mijoz tasdig'i"], ["yoq", "Dalilsiz"]];
const HAFTA_K = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"];

async function ishSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const filtr = params.get("f") || "ochiq";
  const fq = new URLSearchParams({f: filtr});
  for (const k of ["odam_id", "dan", "gacha"]) if (params.get(k)) fq.set(k, params.get(k));
  const [d, t, m] = await Promise.all([api(`/api/ishlar?${fq}`), api("/api/takroriy"), malumotlar()]);
  const soz = (params.get("q") || "").toLowerCase();
  if (soz) d.ishlar = d.ishlar.filter(i => [i.nom, i.joy, i.mijoz, ...i.ijrochilar.map(x => x.ism)].some(x => (x || "").toLowerCase().includes(soz)));
  const tab = (k, n) => `<a href="#/ishlar?f=${k}" ${filtr === k ? 'style="font-weight:800"' : ""}>${n}</a>`;
  main.innerHTML = tepa("Ishlar", [tab("ochiq", "Ochiq"), tab("qabul", "Qabul kutmoqda"), tab("bajarilgan", "Bajarilgan"), tab("hammasi", "Hammasi")].join('<span class="n"></span>'),
    `<button class="btn asosiy" id="iber"><i class="ti ti-plus"></i>Ish berish</button><button class="btn" id="itak"><i class="ti ti-repeat"></i>Takroriy ishlar · ${t.takroriy.length}</button>`)
    + `<section class="karta"><form class="filtr" id="if_"><input type="hidden" name="f" value="${H(filtr)}">
        <label class="maydon"><span>Xodim</span><select name="odam_id"><option value="">Hammasi</option>${m.odamlar.map(x => `<option value="${x.id}" ${params.get("odam_id") === String(x.id) ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select></label>
        <label class="maydon"><span>Dan</span><input type="date" name="dan" value="${H(params.get("dan") || "")}"></label><label class="maydon"><span>Gacha</span><input type="date" name="gacha" value="${H(params.get("gacha") || "")}"></label>
        <label class="maydon" style="flex:1 1 200px"><span>Qidirish</span><input type="search" name="q" value="${H(params.get("q") || "")}" placeholder="Ish, manzil, mijoz"></label>
        <button class="btn" type="submit"><i class="ti ti-filter"></i>Ko'rsatish</button></form>
      ${d.ishlar.length ? `<div class="jadval-o"><table class="jadval"><thead><tr><th>#</th><th>Ish</th><th>Kim</th><th>Muddat</th><th class="son">Narx</th><th>Dalil</th><th>Holat</th></tr></thead><tbody>
      ${d.ishlar.map(i => `<tr class="bosiladi" data-ish="${i.id}"><td>${i.id}</td><td><b>${H(i.nom)}</b>${i.joy ? `<br><small>${H(i.joy)}</small>` : ""}${i.manba === "xodim" ? ` <span class="chip">xodim aytgan</span>` : ""}</td>
        <td>${H(i.ijrochilar.map(x => x.ism.split(" ")[0]).join(", "))}${i.ijrochilar.some(x => !x.korildi) && i.holat === "yangi" ? ` <span class="chip kut">ko'rmagan</span>` : ""}</td>
        <td>${i.muddat ? sanaMatn(i.muddat) + (i.soat ? " " + H(i.soat) : "") : "—"}${i.kechikdi ? ` <span class="chip q">${i.kechikdi} kun kechikdi</span>` : ""}</td>
        <td class="son">${i.narx ? H(i.narx.t) : "—"}</td><td>${H(i.dalil_nomi)}</td>
        <td><span class="chip ${ISH_HOLAT[i.holat][1]}">${ISH_HOLAT[i.holat][0]}</span></td></tr>`).join("")}</tbody></table></div>`
      : `<div class="bosh"><i class="ti ti-checklist"></i>Bu ro'yxatda ish yo'q. Botga «Akmal ertaga Chilonzorga borsin» desangiz ham ish beriladi.</div>`}</section>`;
  main.addEventListener("click", e => { const r = e.target.closest("[data-ish]"); if (r) ishOyna(+r.dataset.ish); });
  $("#if_").addEventListener("submit", e => { e.preventDefault(); location.hash = `#/ishlar?${new URLSearchParams(Object.entries(Object.fromEntries(new FormData(e.target))).filter(([, v]) => v))}`; });
  $("#iber").addEventListener("click", () => ishBerishOyna(d.turlar));
  $("#itak").addEventListener("click", () => takroriyOyna(t.takroriy));
}

async function ishBerishOyna(turlar = []) {
  const m = await malumotlar();
  const o = oyna("Ish berish", `<form id="ibf" class="forma">
    <label class="maydon butun"><span>Qanday ish</span><input type="text" name="nom" required maxlength="200" placeholder="Kafel yotqizish"></label>
    <label class="maydon"><span>Ish turi</span><input type="text" name="ish_turi" list="turl" placeholder="kafel"><datalist id="turl">${turlar.map(x => `<option value="${H(x)}">`).join("")}</datalist><small>Kim qilganini eslab qolish uchun</small></label>
    <label class="maydon"><span>Joy</span><input type="text" name="joy" placeholder="Chilonzor, 5-mavze"></label>
    <div class="maydon butun"><span>Kim bajaradi</span><div id="ijr" class="tugmalar"></div><small id="ijrt">Ish turini yozsangiz — kim avval qilganini ko'rsatadi</small></div>
    <label class="maydon"><span>Mijoz</span><select name="mijoz_id"><option value="">—</option>${m.mijozlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select></label>
    <label class="maydon"><span>Muddat</span><input type="date" name="muddat"></label>
    <label class="maydon"><span>Soat</span><input type="time" name="soat"></label>
    <label class="maydon"><span>Narxi (ishbay)</span><input type="text" name="narx" inputmode="decimal" placeholder="0"><small>Bir necha kishi bo'lsa teng bo'linadi</small></label>
    <label class="maydon"><span>Valyuta</span><select name="valyuta"><option value="UZS">so'm</option><option value="USD">dollar</option></select></label>
    <label class="maydon"><span>Bajarilganiga dalil</span><select name="dalil_turi">${DALIL.map(([k, n]) => `<option value="${k}">${n}</option>`).join("")}</select></label>
    <div class="xato-m butun" id="ibx"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="ibok">Ish berish</button>`);
  const f = $("#ibf", o.el);
  const tanlangan = new Set();
  const chiz = async () => {
    const r = await api(`/api/ish_taklif?tur=${encodeURIComponent(f.ish_turi.value.trim())}`);
    $("#ijr", o.el).innerHTML = r.taklif.map(x => `<button type="button" class="btn kichik ${tanlangan.has(x.odam_id) ? "asosiy" : ""}" data-ijr="${x.odam_id}">${H(x.ism)}${x.qilgan ? ` · ${x.qilgan} marta` : ""} · ${x.ochiq} ish</button>`).join("");
  };
  $("#ijr", o.el).addEventListener("click", e => { const b = e.target.closest("[data-ijr]"); if (!b) return; const id = +b.dataset.ijr; tanlangan.has(id) ? tanlangan.delete(id) : tanlangan.add(id); chiz(); });
  f.ish_turi.addEventListener("change", chiz);
  chiz();
  $("#ibok", o.el).addEventListener("click", async () => {
    const d = Object.fromEntries(new FormData(f));
    if (!tanlangan.size) { $("#ibx", o.el).textContent = "Kim bajarishini tanlang"; return; }
    try {
      await api("/api/ish", {body: {...d, narx: d.narx ? sonOqi(d.narx) : null, mijoz_id: d.mijoz_id ? +d.mijoz_id : null,
        ijrochilar: [...tanlangan].map(id => ({odam_id: id, ulush: 1}))}});
      o.yop(); xabar("Ish berildi — ijrochilarga Telegram'da boradi"); yonalish();
    } catch (x) { $("#ibx", o.el).textContent = x.message; }
  });
}

async function ishOyna(id) {
  let i;
  try { i = await api(`/api/ish/${id}`); } catch (x) { return xabar(x.message, true); }
  const q = (a, b) => `<div class="varaq-q"><span>${a}</span><b>${b}</b></div>`;
  const boss = MEN.boshliq || MEN.odam.rol === "menejer";
  const dalil = i.dalillar.length ? i.dalillar.map(d => `<div class="holat-q"><div><b>${{rasm: "Rasm", joylashuv: "Joylashuv", mijoz: "Mijoz tasdig'i"}[d.tur] || d.tur}</b><small>${H(d.vaqt.replace("T", " ").slice(0, 16))}${d.masofa != null ? ` · ish joyidan ${Math.round(d.masofa)} m` : ""}${d.izoh ? " · " + H(d.izoh) : ""}</small></div>
    ${d.rasm ? `<a class="btn kichik" href="/api/ish_dalil/${d.id}" target="_blank" rel="noopener"><i class="ti ti-photo"></i>Ochish</a>` : ""}</div>`).join("") : `<div class="bosh">Dalil hali yo'q</div>`;
  let tug = "";
  if (boss && i.holat === "bajarildi") tug += `${!i.narx ? `<input type="text" id="qnarx" placeholder="Narx (ixtiyoriy)" style="width:160px">` : ""}<button class="btn asosiy" data-amal="qabul">Qabul qilish</button><button class="btn" data-amal="qayta">Qayta ishlash</button>`;
  if (boss && ["yangi", "qayta", "bajarildi_dalil"].includes(i.holat)) tug += `<button class="btn" data-ishtahrir><i class="ti ti-pencil"></i>Tahrirlash</button><button class="btn" data-amal="bajarildi">Bajarildi deb yopish</button>`;
  if (boss && !["qabul", "bekor"].includes(i.holat)) tug += `<button class="btn xavf" data-amal="bekor">Bekor qilish</button>`;
  const o = oyna(`#${i.id} ${i.nom}`, `
    ${q("Holat", `<span class="chip ${ISH_HOLAT[i.holat][1]}">${ISH_HOLAT[i.holat][0]}</span>`)}
    ${q("Kim", H(i.ijrochilar.map(x => x.ism + (x.korildi ? "" : " (ko'rmagan)")).join(", ")))}
    ${i.joy ? q("Joy", H(i.joy)) : ""}${i.mijoz ? q("Mijoz", H(i.mijoz)) : ""}
    ${q("Muddat", i.muddat ? sanaMatn(i.muddat) + (i.soat ? " " + H(i.soat) : "") + (i.kechikdi ? ` · ${i.kechikdi} kun kechikdi` : "") : "—")}
    ${q("Narxi", i.narx ? H(i.narx.t) : "—")}${q("Dalil", H(i.dalil_nomi))}
    ${q("Kim berdi", H(i.yaratgan || "") + " · " + H(i.yaratilgan.replace("T", " ").slice(0, 16)))}
    ${i.sabab ? q("Sabab", H(i.sabab)) : ""}${i.izoh ? `<p style="margin-top:8px;color:var(--matn2);white-space:pre-line">${H(i.izoh)}</p>` : ""}
    <h3 style="margin-top:18px">Dalillar</h3>${dalil}<div class="xato-m" id="ix"></div>`, tug + `<button class="btn" data-yop>Yopish</button>`);
  o.el.addEventListener("click", async e => {
    if (e.target.closest("[data-ishtahrir]")) { o.yop(); return ishTahrirOyna(i); }
    const b = e.target.closest("[data-amal]");
    if (!b) return;
    const amal = b.dataset.amal, body = {amal};
    if (amal === "qabul" && $("#qnarx", o.el)?.value) body.narx = sonOqi($("#qnarx", o.el).value);
    if (["qayta", "bekor", "muddat"].includes(amal)) { body.sabab = prompt("Sababini yozing:"); if (!body.sabab) return; }
    if (amal === "muddat") { body.muddat = prompt("Yangi muddat (YYYY-MM-DD):", MEN.bugun); if (!body.muddat) return; }
    try { await api(`/api/ish/${id}/amal`, {body}); o.yop(); xabar("Yozildi"); yonalish(); } catch (x) { $("#ix", o.el).textContent = x.message; }
  });
}

async function takroriyOyna(royxat) {
  const m = await malumotlar();
  const davrNom = x => x.davr === "har_kun" ? "Har ish kuni" : x.davr === "har_hafta" ? `Har ${HAFTA_K[x.kun]}` : `Har oy ${x.kun}-kuni`;
  const o = oyna("Takroriy ishlar", `${royxat.length ? royxat.map(x => `<div class="holat-q"><div><b>${H(x.nom)}</b><small>${davrNom(x)} · ${H(x.ijrochilar.map(y => y.ism).join(", "))}</small></div><button class="btn kichik xavf" data-tochir="${x.id}">O'chirish</button></div>`).join("") : `<div class="bosh">Takroriy ish yo'q</div>`}
    <form id="tf" class="forma" style="margin-top:14px;border-top:1px solid var(--chiziq);padding-top:14px">
      <label class="maydon butun"><span>Ish</span><input type="text" name="nom" required placeholder="Ombor tozalash"></label>
      <label class="maydon"><span>Qachon</span><select name="davr"><option value="har_kun">Har ish kuni</option><option value="har_hafta">Har hafta</option><option value="har_oy">Har oy</option></select></label>
      <label class="maydon"><span>Kuni</span><select name="kun"></select></label>
      <label class="maydon butun"><span>Kim</span><select name="ijrochi">${m.odamlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select></label>
      <div class="butun"><button class="btn asosiy" type="submit">Qo'shish</button></div><div class="xato-m butun" id="tx"></div></form>`);
  const f = $("#tf", o.el);
  const kunlar = () => { f.kun.innerHTML = f.davr.value === "har_hafta" ? HAFTA_K.map((k, i) => `<option value="${i}">${k}</option>`).join("") : f.davr.value === "har_oy" ? [...Array(28)].map((_, i) => `<option value="${i + 1}">${i + 1}</option>`).join("") : `<option value="">—</option>`; };
  f.davr.addEventListener("change", kunlar); kunlar();
  f.addEventListener("submit", async e => {
    e.preventDefault();
    try { await api("/api/takroriy", {body: {nom: f.nom.value, davr: f.davr.value, kun: f.kun.value, ijrochilar: [+f.ijrochi.value]}}); o.yop(); xabar("Qo'shildi"); yonalish(); } catch (x) { $("#tx", o.el).textContent = x.message; }
  });
  o.el.addEventListener("click", async e => { const b = e.target.closest("[data-tochir]"); if (b && confirm("O'chirilsinmi?")) { await api(`/api/takroriy/${b.dataset.tochir}/ochir`, {body: {}}); o.yop(); yonalish(); } });
}

/* ---------- Davomat (M3) ---------- */
async function davomatSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const oy = params.get("oy") || MEN.oy;
  const [d, m] = await Promise.all([api(`/api/davomat?oy=${oy}`), malumotlar()]);
  const vq = s => s ? H(s.slice(11, 16)) : "—";
  main.innerHTML = tepa("Davomat", "Xodim botdagi «Keldim / Ketdim» tugmasini bosadi — joylashuvi bilan yoziladi",
    `${oyTanlov(oy)}${MEN.boshliq ? `<button class="btn" id="dq"><i class="ti ti-pencil"></i>Qo'lda yozish</button>` : ""}`)
    + `<div class="ustun2"><section class="karta"><div class="kb"><h2>Bugun</h2></div>
      ${d.bugun.map(x => `<div class="odam"><span class="av ${avRang(x.odam_id)}">${H(bosh(x.ism))}</span><div><b>${H(x.ism)}</b><small>${x.keldi ? `keldi ${vq(x.keldi)}${x.ketdi ? ` · ketdi ${vq(x.ketdi)}` : ""}` : "belgilanmagan"}${x.joylashuvsiz ? " · joylashuvsiz" : ""}${x.masofa != null && x.masofa > 500 ? ` · ofisdan ${x.masofa} m` : ""}</small></div>
        <div class="oi">${x.kechikish ? `<span class="q">${x.kechikish} daq kechikdi</span>` : x.keldi ? `<span class="y">vaqtida</span>` : ""}</div></div>`).join("")}</section>
      <section class="karta"><div class="kb"><h2>Oy bo'yicha</h2><span class="izoh">${d.qatorlar.length} yozuv</span></div>
      ${d.qatorlar.length ? `<div class="jadval-o"><table class="jadval"><thead><tr><th>Sana</th><th>Xodim</th><th>Keldi</th><th>Ketdi</th><th>Holat</th></tr></thead><tbody>
        ${d.qatorlar.map(r => `<tr><td>${sanaMatn(r.sana)}</td><td>${H(r.ism)}</td><td>${vq(r.keldi)}${r.kechikish ? ` <span class="chip q">${r.kechikish} daq</span>` : ""}</td><td>${vq(r.ketdi)}</td>
          <td>${r.holat === "sorov" ? `<span class="chip kut">so'rov</span>${MEN.boshliq ? ` <button class="btn kichik" data-dh="${r.id}" data-ha="1">Tasdiqlash</button><button class="btn kichik xavf" data-dh="${r.id}" data-ha="0">Rad</button>` : ""}` : r.holat === "rad" ? `<span class="chip">rad</span>` : `<span class="chip y">ok</span>`}</td></tr>`).join("")}</tbody></table></div>` : `<div class="bosh">Bu oyda yozuv yo'q</div>`}</section></div>`;
  $("#oy").addEventListener("change", e => { location.hash = `#/davomat?oy=${e.target.value}`; });
  main.addEventListener("click", async e => {
    const b = e.target.closest("[data-dh]");
    if (b) { try { await api(`/api/davomat/${b.dataset.dh}/hal`, {body: {ha: b.dataset.ha === "1"}}); yonalish(); } catch (x) { xabar(x.message, true); } }
  });
  const dq = $("#dq");
  if (dq) dq.addEventListener("click", () => {
    const o = oyna("Davomatni qo'lda yozish", `<form id="df" class="forma"><label class="maydon butun"><span>Xodim</span><select name="odam_id">${m.odamlar.map(x => `<option value="${x.id}">${H(x.ism)}</option>`).join("")}</select></label>
      <label class="maydon"><span>Sana</span><input type="date" name="sana" value="${MEN.bugun}" max="${MEN.bugun}" required></label><label class="maydon"><span>Keldi</span><input type="time" name="keldi"></label><label class="maydon"><span>Ketdi</span><input type="time" name="ketdi"></label>
      <div class="xato-m butun" id="dx"></div></form>`, `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="dok">Saqlash</button>`);
    $("#dok", o.el).addEventListener("click", async () => {
      const f = $("#df", o.el);
      try { await api("/api/davomat/qolda", {body: Object.fromEntries(new FormData(f))}); o.yop(); xabar("Yozildi — jurnalga tushdi"); yonalish(); } catch (x) { $("#dx", o.el).textContent = x.message; }
    });
  });
}

/* ---------- Xodim kartasi (O1, O2) ---------- */
async function xodimKartaOyna(id) {
  const d = await api(`/api/odam/${id}/karta`);
  const x = d.odam;
  const o = oyna(`${x.ism} — karta`, `<form id="xkf" class="forma">
      <label class="maydon"><span>Ishga kirgan sana</span><input type="date" name="kirgan_sana" value="${H(x.kirgan_sana || "")}"></label>
      <label class="maydon"><span>Yaqinining telefoni</span><input type="text" name="yaqin_telefon" value="${H(x.yaqin_telefon || "")}"></label>
      <label class="maydon butun"><span>Izoh</span><input type="text" name="izoh" value="${H(x.izoh || "")}"></label>
      <div class="butun"><button class="btn" type="submit">Saqlash</button></div></form>
    <h3 style="margin-top:18px">Shu oy</h3>
    <div class="varaq-q"><span>Kelgan kunlari</span><b>${d.davomat_oy}</b></div><div class="varaq-q"><span>Kechikkan kunlari</span><b>${d.kechikishlar}</b></div>
    <div class="varaq-q"><span>Ochiq ishlari</span><b>${d.ochiq_ishlar.length}</b></div>
    <h3 style="margin-top:18px">Nimalarni qilgan (bajarilgan ishlaridan)</h3>
    ${d.konikma.length ? `<table class="jadval"><thead><tr><th>Ish turi</th><th class="son">Soni</th><th class="son">Vaqtida</th><th class="son">Qayta ishlangan</th></tr></thead><tbody>${d.konikma.map(k => `<tr><td>${H(k.tur)}</td><td class="son">${k.soni}</td><td class="son">${k.vaqtida}</td><td class="son">${k.qayta}</td></tr>`).join("")}</tbody></table>` : `<div class="bosh">Hali bajarilgan ish yo'q</div>`}
    <h3 style="margin-top:18px">Hujjatlar</h3>
    ${d.hujjatlar.map(h => `<div class="holat-q"><div><b>${H(h.nom)}</b><small>${H(h.vaqt.slice(0, 10))}</small></div><a class="btn kichik" href="/api/hujjat/${h.id}" target="_blank" rel="noopener">Ochish</a></div>`).join("") || `<div class="bosh">Hujjat yuklanmagan</div>`}
    <form id="hf" class="filtr"><label class="maydon"><span>Nomi</span><input type="text" name="nom" placeholder="Pasport nusxasi"></label><div class="maydon"><span>Fayl (rasm yoki PDF)</span><label class="btn"><i class="ti ti-paperclip"></i><span id="fnom">Faylni tanlash</span><input type="file" name="fayl" accept="image/*,.pdf" hidden></label></div><button class="btn" type="submit">Yuklash</button></form>
    <div class="xato-m" id="xkx"></div>`);
  $("#xkf", o.el).addEventListener("submit", async e => { e.preventDefault(); try { await api(`/api/odam/${id}/qoshimcha`, {body: Object.fromEntries(new FormData(e.target))}); xabar("Saqlandi"); } catch (x) { $("#xkx", o.el).textContent = x.message; } });
  $("#hf", o.el).fayl.addEventListener("change", e => { $("#fnom", o.el).textContent = e.target.files[0] ? e.target.files[0].name : "Faylni tanlash"; });
  $("#hf", o.el).addEventListener("submit", async e => {
    if (!e.target.fayl.files.length) { e.preventDefault(); $("#xkx", o.el).textContent = "Avval faylni tanlang"; return; }
    e.preventDefault();
    const r = await fetch(`/api/odam/${id}/hujjat`, {method: "POST", headers: {"X-Miya": "1"}, body: new FormData(e.target), credentials: "same-origin"});
    if (r.ok) { o.yop(); xabar("Yuklandi"); xodimKartaOyna(id); } else { const j = await r.json().catch(() => ({})); $("#xkx", o.el).textContent = j.xato || j.detail || "Yuklanmadi"; }
  });
}

boshla();
