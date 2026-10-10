"use strict";
/* CRM — panel chatsiz to'liq ishlaydi (TALABLAR: CRM1–CRM5). panel.js dan oldin yuklanadi (faqat ta'riflar). */

/* ---------- CRM1: kalendar va eslatmalar ---------- */
const HAFTA_T = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"];
const VOQEA = {
  uchrashuv: {nom: "Uchrashuv", ikon: "ti-users-group"}, eslatma: {nom: "Eslatma", ikon: "ti-bell"},
  malumot: {nom: "Ma'lumot", ikon: "ti-bookmark"}, ish: {nom: "Ish muddati", ikon: "ti-tool"},
  vada: {nom: "Va'da", ikon: "ti-heart-handshake"}, maosh: {nom: "Maosh kuni", ikon: "ti-cash-banknote"},
};
const isoKun = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const kunMatn = s => { const d = new Date(s + "T00:00:00"); return `${d.getDate()}-${OYLAR[d.getMonth()]}, ${HAFTA_T[(d.getDay() + 6) % 7]}`; };

let KAL = null;  // {oy: Date (1-kun), tanlangan: "YYYY-MM-DD", voqealar: []}

async function kalendarSahifa(main) {
  const bugun = MEN.bugun;
  if (!KAL) KAL = {oy: new Date(bugun.slice(0, 8) + "01T00:00:00"), tanlangan: bugun};
  main.innerHTML = tepa("Kalendar", "Uchrashuvlar, eslatmalar, ish muddatlari va va'dalar — bitta joyda",
    `<button class="btn asosiy" data-xqosh><i class="ti ti-plus"></i>Qo'shish</button>`)
    + `<div class="kal-ust"><section class="karta kal" id="kal"></section><section class="karta kal-kun" id="kal-kun"></section></div>
      <section class="karta" id="kal-mal"></section>`;
  main.addEventListener("click", kalendarTugma);
  await kalendarChiz();
  await malumotlarChiz();
}

async function kalendarChiz() {
  const oy = KAL.oy, birinchi = new Date(oy), boshi = new Date(oy);
  boshi.setDate(1 - ((birinchi.getDay() + 6) % 7));  // dushanbadan boshlanadi
  const oxiri = new Date(boshi); oxiri.setDate(boshi.getDate() + 41);
  const r = await api(`/api/kalendar?dan=${isoKun(boshi)}&gacha=${isoKun(oxiri)}`);
  KAL.voqealar = r.voqealar;
  const kunlar = {};
  for (const v of r.voqealar) (kunlar[v.sana] = kunlar[v.sana] || []).push(v);
  let katak = "";
  for (let i = 0; i < 42; i++) {
    const d = new Date(boshi); d.setDate(boshi.getDate() + i);
    const k = isoKun(d), v = kunlar[k] || [];
    const korin = v.filter(x => x.holat !== "bekor");
    katak += `<button type="button" class="kal-k ${d.getMonth() !== oy.getMonth() ? "boshqa" : ""} ${k === r.bugun ? "bugun" : ""} ${k === KAL.tanlangan ? "tanl" : ""}" data-kun="${k}" aria-label="${H(kunMatn(k))}${korin.length ? `, ${korin.length} ta` : ""}">
      <b>${d.getDate()}</b><span class="kal-n">${korin.slice(0, 3).map(x => `<i class="kv ${x.tur} ${x.kechikkan ? "kech" : ""} ${["bajarildi", "qabul", "vaqtida", "kech"].includes(x.holat) ? "tugadi" : ""}">${H(x.soat ? x.soat + " " : "")}${H(x.matn)}</i>`).join("")}${korin.length > 3 ? `<small>+${korin.length - 3}</small>` : ""}</span></button>`;
  }
  $("#kal").innerHTML = `<div class="kb kal-b"><button class="btn ik kichik" data-oy="-1" aria-label="Oldingi oy"><i class="ti ti-chevron-left"></i></button>
      <h2>${H(OYLAR[oy.getMonth()][0].toUpperCase() + OYLAR[oy.getMonth()].slice(1))} ${oy.getFullYear()}</h2>
      <button class="btn ik kichik" data-oy="1" aria-label="Keyingi oy"><i class="ti ti-chevron-right"></i></button>
      <button class="btn kichik" data-oy="0">Bugun</button></div>
    <div class="kal-h">${HAFTA_K.map(x => `<span>${x}</span>`).join("")}</div>
    <div class="kal-p">${katak}</div>
    <div class="legend kal-l">${["uchrashuv", "eslatma", "ish", "vada", "maosh"].map(t => `<span><i class="kv ${t}"></i>${VOQEA[t].nom}</span>`).join("")}</div>`;
  kunChiz();
}

function kunChiz() {
  const k = KAL.tanlangan, v = KAL.voqealar.filter(x => x.sana === k);
  const qator = x => {
    const xot = ["uchrashuv", "eslatma", "malumot"].includes(x.tur);
    const tugagan = ["bajarildi", "qabul", "vaqtida", "kech", "bekor"].includes(x.holat);
    return `<div class="kq ${tugagan ? "tugadi" : ""}"><span class="kq-s">${H(x.soat || "")}</span>
      <span class="si ${x.tur} ${x.kechikkan ? "kech" : ""}"><i class="ti ${VOQEA[x.tur].ikon}"></i></span>
      <div class="kq-m"><b>${H(x.matn)}</b><small>${H(VOQEA[x.tur].nom)}${x.kim ? ` · ${H(x.kim)}` : ""}${x.kechikkan ? " · kechikkan" : ""}${x.holat === "bajarildi" ? " · bajarildi" : x.holat === "bekor" ? " · bekor" : ""}</small></div>
      <div class="sa">${xot ? `${x.holat === "ochiq" ? `<button class="btn kichik" data-xholat="${x.id}" data-h="bajarildi" aria-label="Bajarildi"><i class="ti ti-check"></i></button>` : ""}
        <button class="btn kichik" data-xtahrir="${x.id}">Tahrirlash</button>`
        : x.tur === "ish" ? `<button class="btn kichik" data-ish="${x.id}">Ochish</button>`
        : x.tur === "vada" ? `<a class="btn kichik" href="#/vadalar">Va'dalar</a>` : `<a class="btn kichik" href="#/maosh">Maosh</a>`}</div></div>`;
  };
  $("#kal-kun").innerHTML = `<div class="kb"><h2>${H(kunMatn(k))}</h2><button class="btn kichik" data-xqosh="${k}"><i class="ti ti-plus"></i>Qo'shish</button></div>
    ${v.length ? v.map(qator).join("") : `<div class="bosh"><i class="ti ti-calendar"></i>Bu kunga hech narsa yozilmagan</div>`}`;
}

async function malumotlarChiz(sorov = "") {
  const r = await api(`/api/xotira?tur=malumot&limit=100${sorov ? `&sorov=${encodeURIComponent(sorov)}` : ""}`);
  const el = $("#kal-mal");
  if (!el) return;
  const royxat = r.xotira.filter(x => x.holat !== "bekor");
  el.innerHTML = `<div class="kb"><h2>Xotiradagi ma'lumotlar</h2><span class="izoh">sanasiz yozilgan faktlar va kelishuvlar</span></div>
    <input type="search" id="mal-q" placeholder="Qidirish: hokimlik, Karimov, oylik…" value="${H(sorov)}" class="mal-q">
    ${royxat.length ? royxat.map(x => `<div class="kq"><span class="si malumot"><i class="ti ti-bookmark"></i></span>
      <div class="kq-m"><b>${H(x.matn)}</b><small>${H(x.yozgan || "")} · ${H(sanaMatn(x.vaqt))}${x.sana ? ` · ${H(x.qachon)}` : ""}</small></div>
      <div class="sa"><button class="btn kichik" data-xtahrir="${x.id}">Tahrirlash</button></div></div>`).join("")
      : `<div class="bosh"><i class="ti ti-bookmark"></i>${sorov ? "Topilmadi" : "Hali ma'lumot yozilmagan. Chatga yoki «Qo'shish» bilan yozing."}</div>`}`;
  let t;
  $("#mal-q").addEventListener("input", e => { clearTimeout(t); t = setTimeout(async () => { await malumotlarChiz(e.target.value.trim()); const q = $("#mal-q"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }, 300); });
}

async function kalendarTugma(e) {
  const kun = e.target.closest("[data-kun]");
  if (kun) { KAL.tanlangan = kun.dataset.kun; $$(".kal-k.tanl").forEach(x => x.classList.remove("tanl")); kun.classList.add("tanl"); return kunChiz(); }
  const oy = e.target.closest("[data-oy]");
  if (oy) {
    if (oy.dataset.oy === "0") { KAL.oy = new Date(MEN.bugun.slice(0, 8) + "01T00:00:00"); KAL.tanlangan = MEN.bugun; }
    else KAL.oy = new Date(KAL.oy.getFullYear(), KAL.oy.getMonth() + +oy.dataset.oy, 1);
    return kalendarChiz();
  }
  const q = e.target.closest("[data-xqosh]");
  if (q) return xotiraOyna(null, q.dataset.xqosh || KAL.tanlangan);
  const t = e.target.closest("[data-xtahrir]");
  if (t) return xotiraOyna(+t.dataset.xtahrir);
  const h = e.target.closest("[data-xholat]");
  if (h) {
    try { await api(`/api/xotira/${h.dataset.xholat}`, {body: {holat: h.dataset.h}}); xabar("Belgilandi"); await kalendarChiz(); } catch (x) { xabar(x.message, true); }
    return;
  }
  const i = e.target.closest("[data-ish]");
  if (i) return ishOyna(+i.dataset.ish);
}

async function xotiraOyna(id, sana = "") {
  const m = await malumotlar();
  let x = {tur: "uchrashuv", matn: "", sana, soat: "", kimga_id: null, holat: "ochiq"};
  if (id) {
    const r = await api(`/api/xotira?limit=500`);
    x = r.xotira.find(y => y.id === id) || x;
  }
  const o = oyna(id ? "Tahrirlash" : "Qo'shish", `<form id="xf" class="forma">
      <label class="maydon"><span>Turi</span><select name="tur">${[["uchrashuv", "Uchrashuv"], ["eslatma", "Eslatma (ish)"], ["malumot", "Ma'lumot"]].map(([k, n]) => `<option value="${k}" ${x.tur === k ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      <label class="maydon"><span>Kimga eslatilsin</span><select name="kimga_id"><option value="">O'zimga</option>${m.odamlar.filter(y => y.id !== MEN.odam.id).map(y => `<option value="${y.id}" ${x.kimga_id === y.id ? "selected" : ""}>${H(y.ism)} (va menga)</option>`).join("")}</select></label>
      <label class="maydon butun"><span>Nima</span><textarea name="matn" maxlength="500" required placeholder="Baxmal hokimligi — loyihalar bo'yicha">${H(x.matn)}</textarea></label>
      <label class="maydon"><span>Sana</span><input type="date" name="sana" value="${H(x.sana || "")}"><small>Bo'sh — sanasiz ma'lumot</small></label>
      <label class="maydon"><span>Soat</span><input type="time" name="soat" value="${H(x.soat || "")}"><small>Uchrashuv — 1 soat oldin, eslatma — o'z vaqtida</small></label>
      <div class="xato-m butun" id="xx"></div></form>`,
    `${id && x.holat !== "bekor" ? `<button class="btn xavf" id="xbekor">Bekor qilish</button>` : ""}<button class="btn" data-yop>Yopish</button><button class="btn asosiy" id="xsaqla"><i class="ti ti-check"></i>Saqlash</button>`);
  const f = $("#xf", o.el);
  $("#xsaqla", o.el).addEventListener("click", async () => {
    const d = Object.fromEntries(new FormData(f));
    if (!d.matn.trim()) { $("#xx", o.el).textContent = "Nima ekanini yozing"; return; }
    try {
      const r = await api(id ? `/api/xotira/${id}` : "/api/xotira", {body: {...d, kimga_id: d.kimga_id || null}});
      o.yop();
      xabar(r.matn);
      if (d.sana) { KAL.tanlangan = d.sana; KAL.oy = new Date(d.sana.slice(0, 8) + "01T00:00:00"); }
      if ($("#kal")) { await kalendarChiz(); await malumotlarChiz(); }
    } catch (er) { $("#xx", o.el).textContent = er.message; }
  });
  const b = $("#xbekor", o.el);
  if (b) b.addEventListener("click", async () => {
    try { await api(`/api/xotira/${id}`, {body: {holat: "bekor"}}); o.yop(); xabar("Bekor qilindi"); if ($("#kal")) { await kalendarChiz(); await malumotlarChiz(); } } catch (er) { $("#xx", o.el).textContent = er.message; }
  });
}

/* ---------- CRM2: tahrirlash (pul yozuvi, ish, va'da) ---------- */
const majorSon = (m, v) => v === "USD" ? m / 100 : m;
const sonKorinish = (m, v) => m == null || m === "" ? "" : v === "USD" ? String(m / 100) : guruh(m);

async function tuzatOyna(h) {
  const m = await malumotlar();
  const kassaTomon = [h.dan_k, h.ga_k].filter(k => (k || "").startsWith("kassa:"));
  const kassaOpt = (tanl) => m.kassalar.map(k => `<option value="${k.id}" ${`kassa:${k.id}` === tanl ? "selected" : ""}>${H(k.nom)} (${k.valyuta})</option>`).join("");
  const mijozlar = h.mijoz_id ? [...m.mijozlar, ...m.taminotchilar] : [];
  const o = oyna(`Tuzatish · #${h.id}`, `<p class="izoh-p">Eski yozuv bekor qilinadi (tarixda qoladi), o'rniga to'g'risi yoziladi.</p>
    <form id="tzf" class="forma">
      <label class="maydon"><span>Summa (${H(h.valyuta === "USD" ? "dollar" : "so'm")})</span><input type="text" name="summa" inputmode="decimal" value="${H(sonKorinish(h.summa.m, h.valyuta))}"></label>
      <label class="maydon"><span>Sana</span><input type="date" name="sana" value="${H(h.voqea_sana)}" max="${MEN.bugun}"></label>
      ${kassaTomon[0] ? `<label class="maydon"><span>${kassaTomon.length > 1 ? "Qaysi kassadan" : "Kassa"}</span><select name="kassa_id">${kassaOpt(kassaTomon[0])}</select></label>` : ""}
      ${kassaTomon[1] ? `<label class="maydon"><span>Qaysi kassaga</span><select name="kassa2_id">${kassaOpt(kassaTomon[1])}</select></label>` : ""}
      ${h.odam_id ? `<label class="maydon"><span>Xodim</span><select name="odam_id">${m.odamlar.map(x => `<option value="${x.id}" ${x.id === h.odam_id ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select></label>` : ""}
      ${h.mijoz_id && mijozlar.length ? `<label class="maydon"><span>Mijoz</span><select name="mijoz_id">${mijozlar.map(x => `<option value="${x.id}" ${x.id === h.mijoz_id ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select></label>` : ""}
      ${h.xarajat_turi_id ? `<label class="maydon"><span>Xarajat turi</span><select name="xarajat_turi_id">${m.xarajat.map(x => `<option value="${x.id}" ${x.id === h.xarajat_turi_id ? "selected" : ""}>${H(x.nom)}</option>`).join("")}</select></label>` : ""}
      ${h.muddat ? `<label class="maydon"><span>Qarz muddati</span><input type="date" name="muddat" value="${H(h.muddat)}"></label>` : ""}
      <label class="maydon butun"><span>Izoh</span><input type="text" name="izoh" maxlength="300" value="${H(h.izoh || "")}"></label>
      <label class="maydon butun"><span>Nima uchun tuzatilyapti?</span><input type="text" name="sabab" maxlength="200" required placeholder="Masalan: summa noto'g'ri yozilgan"></label>
      <div class="xato-m butun" id="tzx"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="tzok"><i class="ti ti-check"></i>Tuzatish</button>`);
  $("#tzok", o.el).addEventListener("click", async () => {
    const d = Object.fromEntries(new FormData($("#tzf", o.el)));
    if (!d.sabab.trim()) { $("#tzx", o.el).textContent = "Sababini yozing"; return; }
    d.summa = sonOqi(d.summa);
    if (!d.summa) { $("#tzx", o.el).textContent = "Summani raqam bilan yozing"; return; }
    try {
      const r = await api(`/api/harakat/${h.id}/tuzat`, {body: d});
      o.yop(); KESH = null;
      xabar(r.holat === "faol" ? "Tuzatildi" : "Tuzatildi — tasdiq kutmoqda");
      yonalish();
    } catch (x) { $("#tzx", o.el).textContent = x.message; }
  });
}

async function ishTahrirOyna(i) {
  const m = await malumotlar();
  const tanl = new Set(i.ijrochilar.map(x => x.odam_id));
  const o = oyna(`Ishni tahrirlash · #${i.id}`, `<form id="itf" class="forma">
      <label class="maydon butun"><span>Ish</span><input type="text" name="nom" maxlength="200" value="${H(i.nom)}" required></label>
      <div class="maydon butun"><span>Kim bajaradi</span><div class="tanlov" id="itj"></div></div>
      <label class="maydon"><span>Muddat</span><input type="date" name="muddat" value="${H(i.muddat || "")}"></label>
      <label class="maydon"><span>Soat</span><input type="time" name="soat" value="${H(i.soat || "")}"></label>
      <label class="maydon butun"><span>Manzil</span><input type="text" name="joy" maxlength="200" value="${H(i.joy || "")}"></label>
      <label class="maydon"><span>Narx</span><input type="text" name="narx" inputmode="decimal" value="${H(i.narx ? sonKorinish(i.narx.m, i.narx.v) : "")}" placeholder="—"></label>
      <label class="maydon butun" id="its" hidden><span>Muddat nega o'zgardi?</span><input type="text" name="sabab" maxlength="200" placeholder="Masalan: mijoz so'radi"></label>
      <div class="xato-m butun" id="itx"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="itok"><i class="ti ti-check"></i>Saqlash</button>`);
  const f = $("#itf", o.el);
  const chiz = () => { $("#itj", o.el).innerHTML = m.odamlar.map(x => `<button type="button" class="btn kichik ${tanl.has(x.id) ? "asosiy" : ""}" data-ij="${x.id}">${H(x.ism)}</button>`).join(""); };
  chiz();
  $("#itj", o.el).addEventListener("click", e => { const b = e.target.closest("[data-ij]"); if (!b) return; const id = +b.dataset.ij; tanl.has(id) ? tanl.delete(id) : tanl.add(id); chiz(); });
  f.muddat.addEventListener("change", () => { $("#its", o.el).hidden = f.muddat.value === (i.muddat || ""); });
  $("#itok", o.el).addEventListener("click", async () => {
    const d = Object.fromEntries(new FormData(f));
    if (!tanl.size) { $("#itx", o.el).textContent = "Kim bajarishini tanlang"; return; }
    try {
      await api(`/api/ish/${i.id}/tahrir`, {body: {...d, narx: d.narx ? sonOqi(d.narx) : null, ijrochilar: [...tanl]}});
      o.yop(); xabar("Saqlandi — o'zgarish ijrochilarga yuborildi"); yonalish();
    } catch (x) { $("#itx", o.el).textContent = x.message; }
  });
}

const vadaTahrirTugma = v => `<button class="btn kichik" data-vtahrir="${v.id}" data-summa="${v.summa ? v.summa.m : ""}" data-val="${v.summa ? v.summa.v : "UZS"}" data-muddat="${H(v.muddat)}" data-matn="${H(v.matn || "")}" data-tur="${H(v.tur)}">Tahrirlash</button>`;

function vadaTahrirOyna(v, otaOyna) {
  const o = oyna("Va'dani tahrirlash", `<form id="vtf" class="forma">
      ${v.tur === "tolov" ? `<label class="maydon"><span>Summa (${v.val === "USD" ? "dollar" : "so'm"})</span><input type="text" name="summa" inputmode="decimal" value="${H(sonKorinish(v.summa ? +v.summa : "", v.val))}"></label>` : ""}
      <label class="maydon"><span>Qachongacha</span><input type="date" name="muddat" value="${H(v.muddat)}"></label>
      <label class="maydon butun"><span>Izoh</span><input type="text" name="matn" maxlength="300" value="${H(v.matn)}"></label>
      <div class="xato-m butun" id="vtx"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="vtok"><i class="ti ti-check"></i>Saqlash</button>`);
  $("#vtok", o.el).addEventListener("click", async () => {
    const d = Object.fromEntries(new FormData($("#vtf", o.el)));
    if ("summa" in d) d.summa = sonOqi(d.summa) || "";
    try {
      await api(`/api/vada/${v.vtahrir}/tahrir`, {body: d});
      o.yop(); xabar("Saqlandi");
      if (otaOyna && otaOyna._qayta) otaOyna._qayta(); else yonalish();
    } catch (x) { $("#vtx", o.el).textContent = x.message; }
  });
}

/* ---------- CRM3: hisobotlar ---------- */
function davrlar() {
  const b = new Date(MEN.bugun + "T00:00:00"), y = b.getFullYear(), m = b.getMonth();
  const dush = new Date(b); dush.setDate(b.getDate() - ((b.getDay() + 6) % 7));
  return {
    oy: ["Shu oy", isoKun(new Date(y, m, 1)), MEN.bugun],
    otgan: ["O'tgan oy", isoKun(new Date(y, m - 1, 1)), isoKun(new Date(y, m, 0))],
    hafta: ["Shu hafta", isoKun(dush), MEN.bugun],
    yil: ["Bu yil", `${y}-01-01`, MEN.bugun],
  };
}

async function hisobotSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const D = davrlar();
  const tanl = D[params.get("d")] ? params.get("d") : (params.get("dan") ? "" : "oy");
  const dan = tanl ? D[tanl][1] : params.get("dan"), gacha = tanl ? D[tanl][2] : (params.get("gacha") || MEN.bugun);
  const r = await api(`/api/hisobot?dan=${dan}&gacha=${gacha}`);
  const f = r.foyda, p = x => H(x.t);
  const qisqaS = x => H(qisqa(x.m));
  const ust = (k, n) => `<a class="chip-b ${tanl === k ? "faol" : ""}" href="#/hisobot?d=${k}">${n}</a>`;
  const bosh_ = t => `<div class="bosh"><i class="ti ti-chart-bar"></i>${t}</div>`;
  main.innerHTML = tepa("Hisobotlar", `${H(sanaMatn(r.dan))} — ${H(sanaMatn(r.gacha))} · hammasini dastur hisoblaydi`,
    `<a class="btn" href="/api/eksport/hisobot?dan=${r.dan}&gacha=${r.gacha}"><i class="ti ti-file-spreadsheet"></i>Excel</a>`)
    + `<section class="karta filtr hs-davr"><div class="tanlov">${Object.entries(D).map(([k, v]) => ust(k, v[0])).join("")}</div>
      <form id="hsf" class="hs-oraliq"><label class="maydon"><span>Dan</span><input type="date" name="dan" value="${r.dan}" max="${MEN.bugun}"></label>
      <label class="maydon"><span>Gacha</span><input type="date" name="gacha" value="${r.gacha}"></label><button class="btn" type="submit">Ko'rsatish</button></form></section>
    <section class="kpi">
      <div class="k"><div class="kb0"><i class="ti ti-shopping-cart"></i>Sotuv</div><div class="kr raqam">${qisqaS(f.sotuv)}</div><div class="ki">${p(f.sotuv)}</div></div>
      <div class="k"><div class="kb0"><i class="ti ti-receipt"></i>Xarajat</div><div class="kr raqam q">${qisqaS(f.xarajat)}</div><div class="ki">${p(f.xarajat)}</div></div>
      <div class="k"><div class="kb0"><i class="ti ti-users"></i>Ish haqi</div><div class="kr raqam">${qisqaS(f.ishhaqi)}</div><div class="ki">${f.oy_yopilmagan ? "<i class='ti ti-info-circle'></i>oy yopilmagan — oylik hali kirmagan" : p(f.ishhaqi)}</div></div>
      <div class="k ${f.foyda.m < 0 ? "xavf" : ""}"><div class="kb0"><i class="ti ti-trending-${f.foyda.m < 0 ? "down" : "up"}"></i>Foyda</div><div class="kr raqam ${f.foyda.m < 0 ? "q" : "y"}">${qisqaS(f.foyda)}</div><div class="ki">sotuv − xarajat − ish haqi</div></div>
    </section>
    <div class="panjara">
      <section class="karta"><div class="kb"><h2>Xarajat turlari</h2><span class="izoh">${p(f.xarajat)}</span></div>
        ${r.xarajat_turlar.length ? r.xarajat_turlar.map(x => `<div class="hs-q"><div class="hs-n"><b>${H(x.nom)}</b><span class="raqam">${p(x.summa)}</span></div>
          <div class="chiz"><i style="width:${Math.max(x.ulush, 1)}%;background:var(--chiqim)"></i></div><small>${x.ulush}%</small></div>`).join("") : bosh_("Bu davrda xarajat yo'q")}</section>
      <section class="karta"><div class="kb"><h2>Qarzlar muddati</h2><span class="izoh">bugungi holat</span></div>
        ${r.qarz_yoshi.some(b => b.soni) ? r.qarz_yoshi.filter(b => b.soni).map(b => `<details class="hs-y ${["1_30", "31_60", "61_90", "90_plus"].includes(b.kalit) ? "otgan" : ""}"><summary><b>${H(b.nom)}</b><span>${b.soni} ta · <b class="raqam">${p(b.summa)}</b></span></summary>
          ${b.mijozlar.map(m => `<div class="hs-m" data-mk="${m.id}"><span>${H(m.ism)}${m.muddat ? ` · ${H(sanaMatn(m.muddat))}` : ""}</span><b class="raqam">${p(m.summa)}</b></div>`).join("")}</details>`).join("") : bosh_("Mijozlarda qarz yo'q")}</section>
      <section class="karta"><div class="kb"><h2>Sotuv — mijozlar</h2><span class="izoh">${r.sotuv_mijoz.length} ta mijoz</span></div>
        ${r.sotuv_mijoz.length ? `<div class="jadval-o"><table class="jadval"><thead><tr><th>Mijoz</th><th class="son">Soni</th><th class="son">Summa</th></tr></thead><tbody>
          ${r.sotuv_mijoz.slice(0, 15).map(x => `<tr class="${x.id ? "bosiladi" : ""}" ${x.id ? `data-mk="${x.id}"` : ""}><td>${H(x.ism)}</td><td class="son">${x.soni}</td><td class="son raqam">${p(x.summa)}</td></tr>`).join("")}</tbody></table></div>` : bosh_("Bu davrda sotuv yo'q")}</section>
      ${r.sotuv_mahsulot.length ? `<section class="karta"><div class="kb"><h2>Sotuv — mahsulotlar</h2><span class="izoh">buyurtmalardan</span></div>
        <div class="jadval-o"><table class="jadval"><thead><tr><th>Mahsulot / xizmat</th><th class="son">Miqdor</th><th class="son">Summa</th></tr></thead><tbody>
        ${r.sotuv_mahsulot.slice(0, 20).map(x => `<tr><td>${H(x.nom)}</td><td class="son">${+x.miqdor} ${H(x.birlik)}</td><td class="son raqam">${p(x.summa)}</td></tr>`).join("")}</tbody></table></div></section>` : ""}
      <section class="karta"><div class="kb"><h2>Kim qancha sotdi</h2></div>
        ${r.sotuv_sotuvchi.length ? `<div class="jadval-o"><table class="jadval"><thead><tr><th>Sotuvchi</th><th class="son">Soni</th><th class="son">Summa</th></tr></thead><tbody>
          ${r.sotuv_sotuvchi.map(x => `<tr><td>${H(x.ism)}</td><td class="son">${x.soni}</td><td class="son raqam">${p(x.summa)}</td></tr>`).join("")}</tbody></table></div>` : bosh_("Bu davrda sotuv yo'q")}</section>
      <section class="karta hs-keng"><div class="kb"><h2>Kassalar aylanmasi</h2><span class="izoh">tasdiqlangan pul</span></div>
        <div class="jadval-o"><table class="jadval"><thead><tr><th>Kassa</th><th class="son">Boshida</th><th class="son">Kirim</th><th class="son">Chiqim</th><th class="son">Oxirida</th></tr></thead><tbody>
        ${r.kassalar.map(k => `<tr><td>${H(k.nom)}</td><td class="son raqam">${p(k.boshida)}</td><td class="son raqam y">${p(k.kirim)}</td><td class="son raqam q">${p(k.chiqim)}</td><td class="son raqam"><b>${p(k.oxirida)}</b></td></tr>`).join("")}</tbody></table></div></section>
    </div>`;
  $("#hsf").addEventListener("submit", e => { e.preventDefault(); const d = Object.fromEntries(new FormData(e.target)); location.hash = `#/hisobot?dan=${d.dan}&gacha=${d.gacha}`; });
  main.addEventListener("click", e => { const t = e.target.closest("[data-mk]"); if (t) mijozOyna(+t.dataset.mk, () => yonalish()); });
}

/* ---------- CRM6: buyurtmalar (kanban) va katalog ---------- */
const BOSQICH = {yangi: ["Yangi", ""], taklif: ["Taklif berildi", "u"], sotildi: ["Sotildi", "kut"], bajarildi: ["Bajarildi", "y"], bekor: ["Bekor", ""]};
const qatorQisqa = b => b.qatorlar.slice(0, 2).map(q => `${q.nom} × ${+q.miqdor}`).join(", ") + (b.qatorlar.length > 2 ? ` +${b.qatorlar.length - 2}` : "");

async function buyurtmaSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const kor = params.get("k") === "royxat" ? "royxat" : "kanban", q = params.get("q") || "";
  const d = await api(`/api/buyurtmalar${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  const ust = Object.fromEntries(Object.keys(BOSQICH).map(k => [k, d.buyurtmalar.filter(b => b.bosqich === k)]));
  const jamiM = r => r.reduce((a, b) => a + (b.valyuta === "UZS" ? b.jami.m : 0), 0);
  const karta = b => `<button type="button" class="bk" data-b="${b.id}"><div class="bk-b"><b>${H(b.mijoz)}</b><span class="raqam">${H(b.jami.t)}</span></div>
    <small>${H(qatorQisqa(b) || "qator yo'q")}</small>
    <div class="bk-p"><span>#${b.id}</span>${b.muddat ? `<span><i class="ti ti-calendar"></i>${H(sanaMatn(b.muddat))}</span>` : ""}${b.masul ? `<span><i class="ti ti-user"></i>${H(b.masul.split(" ")[0])}</span>` : ""}<span class="${b.bosqichda_kun > 7 && ["yangi", "taklif"].includes(b.bosqich) ? "q" : ""}">${b.bosqichda_kun ? `${b.bosqichda_kun} kun` : "bugun"}</span></div></button>`;
  main.innerHTML = tepa("Buyurtmalar", "Yangi → taklif → sotildi → bajarildi · jami va qarzni dastur hisoblaydi",
    `<a class="btn" href="#/mahsulotlar"><i class="ti ti-package"></i>Mahsulotlar</a><button class="btn asosiy" data-byangi><i class="ti ti-plus"></i>Yangi buyurtma</button>`)
    + `<section class="karta filtr bk-f"><div class="tanlov"><a class="chip-b ${kor === "kanban" ? "faol" : ""}" href="#/buyurtmalar${q ? `?q=${encodeURIComponent(q)}` : ""}">Kanban</a><a class="chip-b ${kor === "royxat" ? "faol" : ""}" href="#/buyurtmalar?k=royxat${q ? `&q=${encodeURIComponent(q)}` : ""}">Ro'yxat</a></div>
      <form id="bqf" class="bk-q"><input type="search" name="q" value="${H(q)}" placeholder="Mijoz, mahsulot, manzil yoki #raqam"></form></section>`
    + (kor === "kanban"
      ? `<div class="kanban">${["yangi", "taklif", "sotildi", "bajarildi"].map(k => `<section class="kb-ust"><div class="kb-s"><span class="chip ${BOSQICH[k][1]}">${BOSQICH[k][0]}</span><b>${ust[k].length}</b><small class="raqam">${H(qisqa(jamiM(ust[k])))}</small></div>
          ${(k === "bajarildi" ? ust[k].slice(0, 15) : ust[k]).map(karta).join("") || `<div class="bk-bosh">bo'sh</div>`}</section>`).join("")}</div>
        ${ust.bekor.length ? `<details class="karta bk-bekor"><summary>Bekor qilinganlar · ${ust.bekor.length}</summary>${ust.bekor.map(karta).join("")}</details>` : ""}`
      : `<section class="karta">${d.buyurtmalar.length ? `<div class="jadval-o"><table class="jadval"><thead><tr><th>#</th><th>Mijoz</th><th>Nima</th><th class="son">Jami</th><th>Bosqich</th><th>Sana</th></tr></thead><tbody>
          ${d.buyurtmalar.map(b => `<tr class="bosiladi" data-b="${b.id}"><td>${b.id}</td><td><b>${H(b.mijoz)}</b></td><td>${H(qatorQisqa(b))}</td><td class="son raqam">${H(b.jami.t)}</td>
            <td><span class="chip ${BOSQICH[b.bosqich][1]}">${BOSQICH[b.bosqich][0]}</span></td><td>${H(sanaMatn(b.yaratilgan))}</td></tr>`).join("")}</tbody></table></div>`
        : `<div class="bosh"><i class="ti ti-clipboard-list"></i>Hali buyurtma yo'q</div>`}</section>`);
  $("#bqf").addEventListener("submit", e => { e.preventDefault(); const v = e.target.q.value.trim(); location.hash = `#/buyurtmalar?${kor === "royxat" ? "k=royxat&" : ""}q=${encodeURIComponent(v)}`; });
  main.addEventListener("click", e => {
    if (e.target.closest("[data-byangi]")) return buyurtmaOyna(null);
    const b = e.target.closest("[data-b]");
    if (b) buyurtmaOyna(+b.dataset.b);
  });
}

async function buyurtmaOyna(id) {
  const [m, kat] = await Promise.all([malumotlar(), api("/api/katalog")]);
  let b = id ? await api(`/api/buyurtma/${id}`) : {id: null, bosqich: "yangi", mijoz_id: null, valyuta: "UZS", chegirma: {m: 0}, qatorlar: [], manzil: "", muddat: "", masul_id: null, izoh: "", tarix: []};
  const ochiq = ["yangi", "taklif"].includes(b.bosqich);
  const v = b.valyuta, major = x => majorSon(x, v);
  let qatorlar = b.qatorlar.map(q => ({katalog_id: q.katalog_id, nom: q.nom, birlik: q.birlik, miqdor: q.miqdor, narx: major(q.narx.m)}));
  if (!qatorlar.length) qatorlar.push({katalog_id: null, nom: "", birlik: "dona", miqdor: 1, narx: 0});
  const katOpt = sel => `<option value="">— erkin yozish —</option>${kat.katalog.map(k => `<option value="${k.id}" ${k.id === sel ? "selected" : ""}>${H(k.nom)} · ${H(k.narx.t)}/${H(k.birlik)}</option>`).join("")}`;
  const qatorHtml = (q, i) => ochiq
    ? `<div class="bq" data-i="${i}"><select data-f="katalog_id" aria-label="Mahsulot">${katOpt(q.katalog_id)}</select>
        <input data-f="nom" value="${H(q.nom)}" placeholder="Nomi" ${q.katalog_id ? "hidden" : ""} aria-label="Nomi">
        <input data-f="miqdor" inputmode="decimal" value="${H(q.miqdor)}" aria-label="Miqdor"><span class="bq-b">${H(q.birlik || "")}</span>
        <input data-f="narx" inputmode="decimal" value="${H(sonKorinish(q.narx * (v === "USD" ? 100 : 1), v))}" aria-label="Narx">
        <b class="bq-s raqam">${H(guruh(Math.round((+q.miqdor || 0) * (q.narx || 0))))}</b>
        <button type="button" class="btn ik kichik" data-qolib="${i}" aria-label="Olib tashlash"><i class="ti ti-x"></i></button></div>`
    : `<div class="bq yop"><span>${H(q.nom)}</span><span>${+q.miqdor} ${H(q.birlik)} × ${H(sonKorinish(q.narx * (v === "USD" ? 100 : 1), v))}</span><b class="raqam">${H(guruh(Math.round(q.miqdor * q.narx)))}</b></div>`;
  const tarix = (b.tarix || []).map(t => `<div class="bt"><span>${H((t.vaqt || "").replace("T", " ").slice(0, 16))}</span><b>${H(t.matn)}</b><small>${H(t.kim || "tizim")}</small></div>`).join("");
  const o = oyna(id ? `Buyurtma #${id} · ${BOSQICH[b.bosqich][0]}` : "Yangi buyurtma", `<form id="bf" class="forma">
      <label class="maydon"><span>Mijoz</span><select name="mijoz_id" ${ochiq ? "" : "disabled"}><option value="">— tanlang —</option>${m.mijozlar.map(x => `<option value="${x.id}" ${x.id === b.mijoz_id ? "selected" : ""}>${H(x.ism)}</option>`).join("")}<option value="yangi">+ Yangi mijoz…</option></select></label>
      <label class="maydon"><span>Mas'ul</span><select name="masul_id"><option value="">—</option>${m.odamlar.map(x => `<option value="${x.id}" ${x.id === b.masul_id ? "selected" : ""}>${H(x.ism)}</option>`).join("")}</select></label>
      <div class="maydon butun"><span>Nimalar</span><div id="bqr" class="bq-r"></div>${ochiq ? `<button type="button" class="btn kichik" data-qqosh><i class="ti ti-plus"></i>Qator</button>` : ""}</div>
      ${ochiq ? `<label class="maydon"><span>Chegirma</span><input name="chegirma" inputmode="decimal" value="${H(sonKorinish(b.chegirma.m, v))}"></label>` : b.chegirma.m ? `<div class="maydon"><span>Chegirma</span><b>${H(b.chegirma.t)}</b></div>` : ""}
      <div class="maydon bjami"><span>Jami</span><b class="raqam" id="bjami">${id ? H(b.jami.t) : "0"}</b></div>
      <label class="maydon"><span>Manzil</span><input name="manzil" maxlength="300" value="${H(b.manzil || "")}"></label>
      <label class="maydon"><span>Bajarish sanasi</span><input type="date" name="muddat" value="${H(b.muddat || "")}"></label>
      <label class="maydon butun"><span>Izoh</span><input name="izoh" maxlength="300" value="${H(b.izoh || "")}"></label>
      ${b.sotuv ? `<div class="butun bt-s"><i class="ti ti-receipt"></i>${H(b.sotuv.tavsif)} · ${H((HOLAT[b.sotuv.holat] || [b.sotuv.holat])[0])}${b.qarz && b.qarz.m ? ` · mijoz qarzi ${H(b.qarz.t)}` : ""}</div>` : ""}
      ${b.ish_id ? `<div class="butun"><button type="button" class="btn kichik" data-ish="${b.ish_id}"><i class="ti ti-tool"></i>O'rnatish ishi #${b.ish_id}</button></div>` : ""}
      ${b.bekor_sabab ? `<div class="butun bt-s q">Bekor sababi: ${H(b.bekor_sabab)}</div>` : ""}
      ${tarix ? `<details class="butun"><summary>Tarix</summary>${tarix}</details>` : ""}
      <div class="xato-m butun" id="bx"></div></form>`,
    `${!["bajarildi", "bekor"].includes(b.bosqich) && id ? `<button class="btn xavf" data-bosq="bekor">Bekor qilish</button>` : ""}
     ${b.bosqich === "yangi" && id ? `<button class="btn" data-bosq="taklif">Taklif berildi</button>` : ""}
     ${b.bosqich === "sotildi" ? `<button class="btn" data-bosq="bajarildi"><i class="ti ti-circle-check"></i>Bajarildi</button>` : ""}
     ${!["bajarildi", "bekor"].includes(b.bosqich) ? `<button class="btn" id="bsaqla">Saqlash</button>` : `<button class="btn" data-yop>Yopish</button>`}
     ${ochiq ? `<button class="btn asosiy" id="bsot"><i class="ti ti-shopping-cart-check"></i>Sotildi…</button>` : ""}`);
  o.el.querySelector(".oyna").classList.add("keng");
  const f = $("#bf", o.el);
  // holat (qatorlar) har yozilganda yangilanadi; qayta chizish — faqat tuzilma o'zgarsa (qator qo'shish/olish, mahsulot tanlash)
  const jamiYoz = () => {
    if (!ochiq) return;
    const ch = sonOqi(f.chegirma.value);
    $("#bjami", o.el).textContent = guruh(Math.max(0, qatorlar.reduce((a, q) => a + Math.round((+q.miqdor || 0) * (q.narx || 0)), 0) - ch)) + (v === "USD" ? " $" : " so'm");
  };
  let chizilmoqda = false;
  const chiz = () => {
    if (chizilmoqda) return;  // innerHTML almashganda fokusdagi maydonning «blur»i qayta chaqirmasin
    chizilmoqda = true;
    try { $("#bqr", o.el).innerHTML = qatorlar.map(qatorHtml).join(""); } finally { chizilmoqda = false; }
    jamiYoz();
  };
  chiz();
  const oqi = () => $$(".bq[data-i]", o.el).forEach(r => {
    const q = qatorlar[+r.dataset.i];
    q.katalog_id = +$("[data-f=katalog_id]", r).value || null;
    q.nom = $("[data-f=nom]", r).value; q.miqdor = String($("[data-f=miqdor]", r).value).replace(",", ".");
    q.narx = sonOqi($("[data-f=narx]", r).value);
  });
  o.el.addEventListener("change", e => {
    if (e.target.name === "mijoz_id" && e.target.value === "yangi") {
      const ism = prompt("Yangi mijozning ismi:");
      if (!ism) { e.target.value = ""; return; }
      api("/api/mijoz", {body: {ism, tur: "mijoz"}}).then(r => { KESH = null; e.target.insertAdjacentHTML("afterbegin", `<option value="${r.id}">${H(ism)}</option>`); e.target.value = r.id; }).catch(x => { $("#bx", o.el).textContent = x.message; });
      return;
    }
    const r = e.target.closest(".bq[data-i]");
    if (!r || chizilmoqda) { if (e.target.name === "chegirma") jamiYoz(); return; }
    oqi();
    if (e.target.dataset.f === "katalog_id") {
      const q = qatorlar[+r.dataset.i], k = kat.katalog.find(x => x.id === q.katalog_id);
      if (k) { q.nom = k.nom; q.birlik = k.birlik; q.narx = majorSon(k.narx.m, k.valyuta); } else { q.nom = ""; q.birlik = "dona"; }
      chiz();
    }
  });
  o.el.addEventListener("input", e => {
    const r = e.target.closest(".bq[data-i]");
    if (!r) { if (e.target.name === "chegirma") jamiYoz(); return; }
    oqi();
    const q = qatorlar[+r.dataset.i];
    $(".bq-s", r).textContent = guruh(Math.round((+q.miqdor || 0) * (q.narx || 0)));
    jamiYoz();
  });
  const yuk = () => {
    oqi();
    const d = Object.fromEntries(new FormData(f));
    const t = {manzil: d.manzil, muddat: d.muddat, izoh: d.izoh, masul_id: d.masul_id || null};
    if (ochiq) Object.assign(t, {mijoz_id: d.mijoz_id, chegirma: sonOqi(d.chegirma),
      qatorlar: qatorlar.filter(q => q.katalog_id || q.nom.trim()).map(q => ({katalog_id: q.katalog_id, nom: q.nom, birlik: q.birlik, miqdor: +q.miqdor || 0, narx: q.narx}))});
    return t;
  };
  const saqla = async () => {
    const t = yuk();
    if (ochiq && (!t.mijoz_id || t.mijoz_id === "yangi")) throw new Error("Mijozni tanlang");
    return id ? api(`/api/buyurtma/${id}`, {body: t}) : api("/api/buyurtma", {body: t});
  };
  o.el.addEventListener("click", async e => {
    if (e.target.closest("[data-qqosh]")) { oqi(); qatorlar.push({katalog_id: null, nom: "", birlik: "dona", miqdor: 1, narx: 0}); return chiz(); }
    const qb = e.target.closest("[data-qolib]");
    if (qb) { oqi(); qatorlar.splice(+qb.dataset.qolib, 1); return chiz(); }
    const ishb = e.target.closest("[data-ish]");
    if (ishb) return ishOyna(+ishb.dataset.ish);
    try {
      if (e.target.closest("#bsaqla")) { const r = await saqla(); o.yop(); xabar(id ? "Saqlandi" : `Buyurtma #${r.id} yaratildi`); return yonalish(); }
      if (e.target.closest("#bsot")) { const r = await saqla(); o.yop(); return sotildiOyna(r); }
      const bq = e.target.closest("[data-bosq]");
      if (bq) {
        const body = {bosqich: bq.dataset.bosq};
        if (body.bosqich === "bekor") { body.sabab = prompt("Nima uchun bekor qilinadi?"); if (!body.sabab) return; }
        if (body.bosqich !== "bekor" && ochiq) await saqla();
        await api(`/api/buyurtma/${id}/bosqich`, {body});
        o.yop(); xabar(BOSQICH[body.bosqich][0]); yonalish();
      }
    } catch (x) { $("#bx", o.el).textContent = x.message; }
  });
}

async function sotildiOyna(b) {
  const m = await malumotlar();
  const v = b.valyuta, tanl = new Set();
  const kassalar = m.kassalar.filter(k => k.valyuta === v);
  const o = oyna(`Sotildi · buyurtma #${b.id}`, `<p class="izoh-p">${H(b.mijoz)} · jami <b>${H(b.jami.t)}</b>. Hisobga sotuv yoziladi; to'lanmagan qismi mijoz qarzi bo'ladi.</p>
    <form id="sf" class="forma">
      <label class="maydon"><span>Hozir to'ladi</span><input name="tolandi" inputmode="decimal" value="0"></label>
      <label class="maydon"><span>Qaysi kassaga</span><select name="kassa_id"><option value="">—</option>${kassalar.map(k => `<option value="${k.id}" ${k.id === MEN.odam.kassa_id ? "selected" : ""}>${H(k.nom)}</option>`).join("")}</select></label>
      <label class="maydon"><span>Qolganini qachon to'laydi</span><input type="date" name="qarz_muddati" min="${MEN.bugun}"><small>To'liq to'lansa — kerak emas</small></label>
      <label class="belgi butun"><input type="checkbox" name="ish" ${b.muddat || b.manzil ? "checked" : ""}> O'rnatish (bajarish) ishini hozir berish</label>
      <div class="butun forma" id="sish">
        <div class="maydon butun"><span>Kim bajaradi</span><div class="tanlov" id="sij"></div></div>
        <label class="maydon"><span>Sana</span><input type="date" name="ish_muddat" value="${H(b.muddat || "")}"></label>
        <label class="maydon"><span>Soat</span><input type="time" name="ish_soat"></label>
        <label class="maydon"><span>Ish haqi (ixtiyoriy)</span><input name="ish_narx" inputmode="decimal" placeholder="—"></label>
      </div>
      <div class="xato-m butun" id="sx"></div></form>`,
    `<button class="btn" data-yop>Keyinroq</button><button class="btn asosiy" id="sok"><i class="ti ti-check"></i>Sotildi</button>`);
  const f = $("#sf", o.el);
  const chiz = () => { $("#sij", o.el).innerHTML = m.odamlar.map(x => `<button type="button" class="btn kichik ${tanl.has(x.id) ? "asosiy" : ""}" data-ij="${x.id}">${H(x.ism)}</button>`).join(""); };
  const ishKor = () => { $("#sish", o.el).hidden = !f.ish.checked; };
  chiz(); ishKor();
  f.ish.addEventListener("change", ishKor);
  $("#sij", o.el).addEventListener("click", e => { const t = e.target.closest("[data-ij]"); if (!t) return; const i = +t.dataset.ij; tanl.has(i) ? tanl.delete(i) : tanl.add(i); chiz(); });
  $("#sok", o.el).addEventListener("click", async () => {
    const d = Object.fromEntries(new FormData(f));
    const body = {tolandi: sonOqi(d.tolandi), kassa_id: d.kassa_id || null, qarz_muddati: d.qarz_muddati || null};
    if (f.ish.checked) {
      if (!tanl.size) { $("#sx", o.el).textContent = "O'rnatishni kim bajaradi — tanlang"; return; }
      body.ish = {ijrochilar: [...tanl], muddat: d.ish_muddat || null, soat: d.ish_soat || null, narx: d.ish_narx ? sonOqi(d.ish_narx) : null};
    }
    try {
      const r = await api(`/api/buyurtma/${b.id}/sotildi`, {body});
      o.yop(); KESH = null;
      xabar(r.holat === "faol" ? `Sotildi${r.ish_id ? ` · ish #${r.ish_id} berildi` : ""}` : "Sotildi — boshliq tasdig'ini kutmoqda");
      yonalish();
    } catch (x) { $("#sx", o.el).textContent = x.message; }
  });
}

async function katalogSahifa(main) {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const d = await api("/api/katalog?hammasi=1");
  main.innerHTML = tepa("Mahsulotlar va xizmatlar", "Buyurtmada tanlanadi — narx o'zi qo'yiladi",
    `<a class="btn" href="#/buyurtmalar"><i class="ti ti-clipboard-list"></i>Buyurtmalar</a><button class="btn asosiy" data-kqosh><i class="ti ti-plus"></i>Qo'shish</button>`)
    + `<section class="karta">${d.katalog.length ? `<input type="search" id="kq" class="mal-q" placeholder="Qidirish" value="${H(params.get("q") || "")}">
      <div class="jadval-o"><table class="jadval"><thead><tr><th>Nomi</th><th>Turi</th><th>Birlik</th><th class="son">Narx</th><th class="son">Tannarx</th><th></th></tr></thead><tbody id="kt"></tbody></table></div>`
      : `<div class="bosh"><i class="ti ti-package"></i>Hali mahsulot yo'q. «Qo'shish» bilan kiriting — buyurtmada tanlanadi.</div>`}</section>`;
  const chiz = () => {
    const q = ($("#kq") ? $("#kq").value : "").toLowerCase();
    $("#kt").innerHTML = d.katalog.filter(k => !q || k.nom.toLowerCase().includes(q)).map(k => `<tr class="bosiladi ${k.faol ? "" : "bekor"}" data-k="${k.id}"><td><b>${H(k.nom)}</b>${k.izoh ? `<br><small>${H(k.izoh)}</small>` : ""}</td>
      <td><span class="chip ${k.tur === "xizmat" ? "u" : ""}">${k.tur === "xizmat" ? "xizmat" : "mahsulot"}</span></td><td>${H(k.birlik)}</td>
      <td class="son raqam">${H(k.narx.t)}</td><td class="son raqam">${k.tannarx ? H(k.tannarx.t) : "—"}</td><td>${k.faol ? "" : `<span class="chip">sotuvda emas</span>`}</td></tr>`).join("");
  };
  if ($("#kt")) { chiz(); $("#kq").addEventListener("input", chiz); }
  main.addEventListener("click", e => {
    if (e.target.closest("[data-kqosh]")) return katalogOyna(null);
    const r = e.target.closest("[data-k]");
    if (r) katalogOyna(d.katalog.find(k => k.id === +r.dataset.k));
  });
}

function katalogOyna(k) {
  k = k || {id: null, nom: "", tur: "mahsulot", birlik: "dona", narx: {m: 0}, valyuta: "UZS", tannarx: null, izoh: "", faol: true};
  const o = oyna(k.id ? "Tahrirlash" : "Mahsulot yoki xizmat qo'shish", `<form id="kf2" class="forma">
      <label class="maydon butun"><span>Nomi</span><input name="nom" maxlength="200" value="${H(k.nom)}" required placeholder="IP kamera 4MP"></label>
      <label class="maydon"><span>Turi</span><select name="tur"><option value="mahsulot" ${k.tur === "mahsulot" ? "selected" : ""}>Mahsulot</option><option value="xizmat" ${k.tur === "xizmat" ? "selected" : ""}>Xizmat</option></select></label>
      <label class="maydon"><span>Birlik</span><input name="birlik" maxlength="20" value="${H(k.birlik)}" list="birliklar"><datalist id="birliklar"><option>dona</option><option>metr</option><option>kv.m</option><option>soat</option><option>kg</option><option>komplekt</option></datalist></label>
      <label class="maydon"><span>Narx</span><input name="narx" inputmode="decimal" value="${H(sonKorinish(k.narx.m, k.valyuta))}"></label>
      <label class="maydon"><span>Valyuta</span><select name="valyuta"><option value="UZS" ${k.valyuta !== "USD" ? "selected" : ""}>so'm</option><option value="USD" ${k.valyuta === "USD" ? "selected" : ""}>dollar</option></select></label>
      <label class="maydon"><span>Tannarx (ixtiyoriy)</span><input name="tannarx" inputmode="decimal" value="${H(k.tannarx ? sonKorinish(k.tannarx.m, k.valyuta) : "")}"></label>
      <label class="belgi"><input type="checkbox" name="faol" ${k.faol ? "checked" : ""}> Sotuvda bor</label>
      <label class="maydon butun"><span>Izoh</span><input name="izoh" maxlength="300" value="${H(k.izoh || "")}"></label>
      <div class="xato-m butun" id="kx2"></div></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="kok"><i class="ti ti-check"></i>Saqlash</button>`);
  $("#kok", o.el).addEventListener("click", async () => {
    const f = $("#kf2", o.el), d = Object.fromEntries(new FormData(f));
    try {
      await api(k.id ? `/api/katalog/${k.id}` : "/api/katalog", {body: {...d, narx: sonOqi(d.narx), tannarx: d.tannarx ? sonOqi(d.tannarx) : null, faol: f.faol.checked}});
      o.yop(); xabar("Saqlandi"); yonalish();
    } catch (x) { $("#kx2", o.el).textContent = x.message; }
  });
}

// ---------- CRM4: umumiy qidiruv ----------

async function qidiruvSahifa(main) {
  const q = new URLSearchParams(location.hash.split("?")[1] || "").get("q") || "";
  const inp = $("#yq input");
  if (inp && document.activeElement !== inp) inp.value = q;
  const d = q ? await api(`/api/qidiruv?q=${encodeURIComponent(q)}`) : null;
  const blok = (kalit, nom, ikon, royxat, qator, hammasi = "") => royxat.length
    ? `<section class="karta qg"><div class="kb"><h2><i class="ti ${ikon}" aria-hidden="true"></i>${nom}</h2><span class="soni">${royxat.length}${royxat.length >= 8 ? "+" : ""}</span>${hammasi ? `<span class="qg-h">${hammasi}</span>` : ""}</div>
        <div class="qg-r">${royxat.map(qator).join("")}</div></section>` : "";
  const jami = d ? ["mijozlar", "buyurtmalar", "ishlar", "yozuvlar", "xotira", "xabarlar"].reduce((s, k) => s + d[k].length, 0) : 0;
  const q_ = encodeURIComponent(q);
  main.innerHTML = tepa("Qidiruv", q ? `«${H(q)}» bo'yicha · ${jami} ta natija` : "Mijoz, buyurtma, ish, pul yozuvi, xotira va xabarlar — bitta qatordan")
    + `<section class="karta"><form class="filtr" id="qsf" role="search"><label class="maydon" style="flex:1 1 320px"><span>Nima qidiramiz?</span><input type="search" name="q" value="${H(q)}" placeholder="Masalan: Karimov, 90 123 45 67, #12, eshik" autocomplete="off"></label>
      <button class="btn asosiy" type="submit"><i class="ti ti-search"></i>Qidirish</button></form></section>`
    + (!d ? "" : !jami ? `<section class="karta"><div class="bosh"><i class="ti ti-search-off"></i>Hech narsa topilmadi. So'zni qisqaroq yozib ko'ring.</div></section>`
      : blok("m", "Mijozlar", "ti-address-book", d.mijozlar, m => `<button type="button" class="qn" data-qm="${m.id}"><b>${H(m.ism)}</b>${m.arxiv ? ` <span class="chip">arxivda</span>` : ""}<small>${H([m.tur === "taminotchi" ? "Ta'minotchi" : "", m.telefon, m.manzil].filter(Boolean).join(" · ") || "—")}</small></button>`)
      + blok("b", "Buyurtmalar", "ti-clipboard-list", d.buyurtmalar, b => `<button type="button" class="qn" data-qb="${b.id}"><b>#${b.id} · ${H(b.mijoz || "Mijozsiz")}</b> <span class="chip ${BOSQICH[b.bosqich][1]}">${BOSQICH[b.bosqich][0]}</span><small><span class="raqam">${H(b.jami.t)}</span> · ${H(qatorQisqa(b) || "—")}</small></button>`)
      + blok("i", "Ishlar", "ti-checklist", d.ishlar, i => `<button type="button" class="qn" data-qi="${i.id}"><b>#${i.id} · ${H(i.nom)}</b><small>${H([i.joy, i.mijoz, i.ijrochilar.map(x => x.ism).join(", "), i.muddat ? sanaMatn(i.muddat) : ""].filter(Boolean).join(" · "))}</small></button>`)
      + blok("y", "Pul yozuvlari", "ti-receipt", d.yozuvlar, h => `<button type="button" class="qn" data-qh="${h.id}"><b>${H(h.tavsif)}</b><small>${H(sanaMatn(h.voqea_sana))} · ${H(h.yozgan)}</small>${h.holat !== "faol" && HOLAT[h.holat] ? ` <span class="chip ${HOLAT[h.holat][1]}">${HOLAT[h.holat][0]}</span>` : ""}</button>`,
        `<a class="btn kichik" href="#/kassa?q=${q_}">Hammasi</a>`)
      + blok("x", "Xotira", "ti-bulb", d.xotira, x => `<button type="button" class="qn" data-qx="${x.id}"><b>${H(x.matn)}</b><small>${H([VOQEA[x.tur] ? VOQEA[x.tur].nom : x.tur, x.qachon, x.kimga ? "→ " + x.kimga : ""].filter(Boolean).join(" · "))}</small></button>`)
      + blok("a", "Kim nima yozdi", "ti-messages", d.xabarlar, a => `<a class="qn" href="#/arxiv?q=${q_}"><b>${H(a.kim)}</b><small>${H(sanaMatn(a.vaqt))} · ${H(a.parcha)}</small></a>`,
        `<a class="btn kichik" href="#/arxiv?q=${q_}">Arxivda</a>`));
  $("#qsf").addEventListener("submit", e => { e.preventDefault(); const v = e.target.q.value.trim(); if (v) location.hash = `#/qidiruv?q=${encodeURIComponent(v)}`; });
  if (!q) $("#qsf input").focus();
  main.addEventListener("click", e => {
    const t = e.target.closest("[data-qm],[data-qb],[data-qi],[data-qh],[data-qx]");
    if (!t) return;
    const s = t.dataset;
    if (s.qm) mijozOyna(+s.qm, () => yonalish());
    else if (s.qb) buyurtmaOyna(+s.qb);
    else if (s.qi) ishOyna(+s.qi);
    else if (s.qh) harakatOyna(+s.qh);
    else if (s.qx) xotiraOyna(+s.qx);
  });
}

// ---------- CRM5: mijozlarni Excel'dan yuklash ----------

function importOyna(tur) {
  const nom = tur === "taminotchi" ? "ta'minotchi" : "mijoz";
  const o = oyna(`${tur === "taminotchi" ? "Ta'minotchilarni" : "Mijozlarni"} Excel'dan yuklash`, `<form id="imf" class="forma">
      <p class="butun im-izoh">Birinchi qatorda ustun nomlari bo'lsin: <b>Ism</b>, <b>Telefon</b>, <b>Manzil</b>, <b>Qarz</b>, <b>Izoh</b>. Faqat ism majburiy.
        Avval ko'rib chiqasiz — hech narsa o'zi yozilmaydi.</p>
      <label class="maydon butun"><span>Excel fayl (.xlsx)</span><input type="file" name="fayl" accept=".xlsx" required></label>
      <div class="butun" id="imk"></div><p class="xato butun" id="imx" role="alert"></p></form>`,
    `<button class="btn" data-yop>Bekor</button><button class="btn asosiy" id="imt" type="button" disabled><i class="ti ti-upload"></i>Yuklash</button>`);
  let natija = null;
  const IH = {yangi: ["Qo'shiladi", "y"], takror: ["O'tkaziladi", "kut"], xato: ["Xato", "q"]};
  $("[name=fayl]", o.el).addEventListener("change", async e => {
    const f = e.target.files[0];
    $("#imx", o.el).textContent = ""; $("#imt", o.el).disabled = true; natija = null;
    if (!f) return;
    $("#imk", o.el).innerHTML = `<div class="bosh"><i class="ti ti-loader-2"></i>O'qilmoqda…</div>`;
    const fd = new FormData();
    fd.append("fayl", f); fd.append("tur", tur);
    try {
      const r = await fetch("/api/mijoz/import/korib", {method: "POST", headers: {"X-Miya": "1"}, body: fd, credentials: "same-origin"});
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error((d && (d.xato || d.detail)) || `Xato (${r.status})`);
      natija = d;
      const qarzM = d.qatorlar.filter(x => x.holat === "yangi" && x.qarz > 0).length;
      $("#imk", o.el).innerHTML = !d.qatorlar.length ? `<div class="bosh"><i class="ti ti-file-off"></i>Faylda ${nom} topilmadi</div>`
        : `<div class="tanlov" style="margin-bottom:8px"><span class="chip y">${d.soni.yangi} ta qo'shiladi</span>${d.soni.takror ? `<span class="chip kut">${d.soni.takror} ta takror</span>` : ""}${d.soni.xato ? `<span class="chip q">${d.soni.xato} ta xato</span>` : ""}${qarzM ? `<span class="chip">${qarzM} tasida eski qarz</span>` : ""}</div>
          <div class="jadval-o" style="max-height:46vh"><table class="jadval"><thead><tr><th>Qator</th><th>Ism</th><th>Telefon</th><th class="son">Qarz</th><th>Holat</th></tr></thead><tbody>
          ${d.qatorlar.slice(0, 500).map(x => `<tr><td>${x.qator}</td><td><b>${H(x.ism)}</b>${x.manzil ? `<br><small>${H(x.manzil)}</small>` : ""}</td><td>${H(x.telefon || "—")}</td>
            <td class="son raqam">${x.qarz ? guruh(x.qarz) : "—"}</td><td><span class="chip ${IH[x.holat][1]}">${IH[x.holat][0]}</span>${x.sabab ? `<br><small>${H(x.sabab)}</small>` : ""}</td></tr>`).join("")}</tbody></table></div>
          ${d.qatorlar.length > 500 ? `<p class="ki">Birinchi 500 tasi ko'rsatildi (jami ${d.qatorlar.length}).</p>` : ""}`;
      $("#imt", o.el).disabled = !d.soni.yangi;
    } catch (x) { $("#imk", o.el).innerHTML = ""; $("#imx", o.el).textContent = x.message; }
  });
  $("#imt", o.el).addEventListener("click", async e => {
    if (!natija) return;
    e.target.disabled = true;
    try {
      const r = await api("/api/mijoz/import/yoz", {body: {tur, qatorlar: natija.qatorlar}});
      o.yop(); KESH = null;
      xabar(`${r.qoshildi} ta ${nom} qo'shildi${r.qarz_yozildi ? `, ${r.qarz_yozildi} tasining eski qarzi yozildi` : ""}`);
      yonalish();
    } catch (x) { $("#imx", o.el).textContent = x.message; e.target.disabled = false; }
  });
}
