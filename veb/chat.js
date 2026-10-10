"use strict";
/* Chat — xodimlar uchun yagona ekran (R2), boshliq uchun panel ichidagi sahifa (R9). Bitta miya: /api/chat.
   Odam yozgani, miya javobi va miya o'zi yuborgani (eslatma, «tasdiqlaysizmi?», xulosa) bitta oqimda. */

const CHAT_TAKLIF = {
  boshliq: ["Bugun nima bor?", "Kassada qancha pul bor?", "Bu hafta pul nimalarga ketdi?", "Kim bizga qarz?"],
  boshqa: ["Bugun nima ishlarim bor?", "Kassada qancha pul bor?", "Mening hisobim qancha?", "Ertaga nima bor?"],
};

function chatIlova() {  // R2: xodim — faqat chat, boshqa ekran yo'q
  $("#ildiz").innerHTML = `<div class="chat-ilova"><header class="chat-bosh">
      <div class="logo"><span class="orb k"><i></i></span><div><b>miya</b><small>${H(MEN.odam.ism)}</small></div></div>
      <button class="btn ik kichik" id="chiq" aria-label="Chiqish" title="Chiqish"><i class="ti ti-logout"></i></button></header>
    <div class="chat-joy" id="chat-joy"></div></div>`;
  $("#chiq").addEventListener("click", async () => { await api("/api/chiqish", {body: {}}); kirishSahifa(); });
  chatOch($("#chat-joy"));
}

async function chatSahifa(main) {  // boshliq: panel ichida
  main.innerHTML = tepa("Chat", "Yozing yoki so'rang — miya eslab qoladi, hisoblaydi va o'zi eslatadi")
    + `<div class="chat-joy panelda" id="chat-joy"></div>`;
  await chatOch($("#chat-joy", main));
}

const chatSoat = v => (v || "").slice(11, 16);
function chatKun(v) {
  const s = (v || "").slice(0, 10), bugun = MEN.bugun;
  const kecha = new Date(new Date(bugun + "T00:00:00") - 864e5);
  const k = `${kecha.getFullYear()}-${String(kecha.getMonth() + 1).padStart(2, "0")}-${String(kecha.getDate()).padStart(2, "0")}`;
  return s === bugun ? "Bugun" : s === k ? "Kecha" : sanaMatn(s);
}

async function chatOch(joy) {
  const yoq = !MEN.xizmat.ai;
  const misol = MISOL_GAP[MEN.odam.rol] || MISOL_GAP.boshliq;
  joy.innerHTML = `<div class="chat-r" id="chat-r" aria-live="polite"><div class="bosh"><i class="ti ti-loader-2"></i>Yuklanmoqda…</div></div>
    <form class="chat-yoz" id="chat-f"><textarea id="chat-m" rows="1" maxlength="1500" placeholder="${H(yoq ? "Sun'iy intellekt hali yoqilmagan" : misol)}" ${yoq ? "disabled" : ""}></textarea>
      <button class="mik" type="submit" aria-label="Yuborish" ${yoq ? "disabled" : ""}><i class="ti ti-arrow-up"></i></button></form>`;
  const r_ = $("#chat-r", joy), f = $("#chat-f", joy), m = $("#chat-m", joy), tugma = $(".mik", f);
  const korilgan = new Set();
  let oxirgi = null, oxirgiKun = null, band = false;
  const pastga = () => { r_.scrollTop = r_.scrollHeight; };
  const osir = () => { m.style.height = "auto"; m.style.height = Math.min(Math.max(m.scrollHeight, 24), 150) + "px"; };

  const qosh = async (x, joyEl = null) => {  // bitta xabar: odam / miya javobi / miya o'zi yuborgani
    if (korilgan.has(x.k)) return;
    korilgan.add(x.k);
    const kun = chatKun(x.vaqt);
    if (kun !== oxirgiKun) { r_.insertAdjacentHTML("beforeend", `<div class="cx-kun">${H(kun)}</div>`); oxirgiKun = kun; }
    const el = joyEl || document.createElement("div");
    el.className = `cx ${x.kim === "odam" ? "cx-odam" : "cx-miya"}`;  // .miya/.odam — bosh sahifa klasslari bilan to'qnashmasin
    el.dataset.k = x.k;
    if (x.kim === "odam") {
      el.innerHTML = `<div class="pufak">${H(x.matn)}</div><time>${chatSoat(x.vaqt)}</time>`;
    } else {
      el.innerHTML = `<div class="cx-ich"><div class="pufak"></div><time>${chatSoat(x.vaqt)}</time></div>`;
      await miyaChiz($(".pufak", el), x);
    }
    if (!joyEl) r_.appendChild(el);
  };

  async function miyaChiz(p, x) {
    const d = x.malumot;
    if (!d) {  // miya o'zi yuborgan (xabarnoma): eslatma, tasdiq so'rovi, xulosa
      p.innerHTML = `<p>${H(x.matn)}</p>${x.holat ? `<div class="cx-natija">${H(x.holat)}</div>` : ""}${(x.tugmalar || []).length ? `<div class="cx-tug">${x.tugmalar.map(t => `<button type="button" class="btn kichik ${/^(✅|Ha|Tasdiq|Bajarildi)/.test(t[0]) ? "asosiy" : ""}" data-tug="${H(t[1])}">${H(t[0])}</button>`).join("")}</div>` : ""}`;
      return;
    }
    if (d.tur === "javob") {
      const manba = (d.manbalar || []).map(mn => `<span class="chip u"><i class="ti ti-database"></i>${H(ASBOB_NOMI[mn.asbob] || mn.asbob)}</span>`).join("");
      p.innerHTML = `<p>${H(d.javob)}</p>${manba ? `<div class="manba">${manba}</div>` : ""}`;
    } else if (d.tur === "tushunilmadi") {
      p.innerHTML = `<p>${H(d.sabab)}</p>`;
    } else if (d.tur === "xotira" || d.yakun) {
      p.innerHTML = `<div class="mt-r" style="margin:0">${eslabHtml(d.xotira)}${(d.yakun || []).map(t => `<div class="mk ok"><i class="ti ti-circle-check"></i><b>${H(t)}</b></div>`).join("")}</div>`;
    } else if (d.tur === "takliflar") {
      p.classList.add("keng");
      await takliflarChiz(d.takliflar, p, async natija => {  // tasdiqlandi yoki bekor — chatda natija qoladi
        d.yakun = natija && natija.length ? natija : ["Bekor qilindi"];
        try { await api(`/api/chat/${x.k.slice(1)}/yakun`, {body: {natija: d.yakun}}); } catch (er) { /* keyingi ochilishda qayta so'raladi */ }
        p.classList.remove("keng");
        miyaChiz(p, x);
        KESH = null;
      }, d.xotira || []);
    }
  }

  r_.addEventListener("click", async e => {
    const b = e.target.closest("[data-tug]");
    if (b) {
      const qator = b.closest(".cx-tug");
      $$("button", qator).forEach(x => { x.disabled = true; });
      try {
        const r = await api("/api/chat/tugma", {body: {data: b.dataset.tug}});
        qator.outerHTML = `<div class="cx-natija">${H(r.matn)}</div>`;
      } catch (er) { qator.outerHTML = `<div class="cx-natija">${H(er.message)}</div>`; }
      return;
    }
    const t = e.target.closest("[data-chtakl]");
    if (t) yubor(t.dataset.chtakl);
  });

  async function yubor(matn) {
    matn = (matn || "").trim();
    if (!matn || band) return;
    band = true; tugma.disabled = true;
    m.value = ""; osir();
    $(".cx-bosh", r_)?.remove();
    const vaqtincha = document.createElement("div");
    vaqtincha.className = "cx cx-odam";
    vaqtincha.innerHTML = `<div class="pufak">${H(matn)}</div><time>…</time>`;
    r_.appendChild(vaqtincha);
    const kut = document.createElement("div");
    kut.className = "cx cx-miya";
    kut.innerHTML = `<div class="cx-ich"><div class="pufak"><p class="kutish-m" aria-label="O'ylayapman"><i></i><i></i><i></i></p></div></div>`;
    r_.appendChild(kut);
    pastga();
    try {
      const r = await api("/api/chat", {body: {matn}});
      vaqtincha.remove();
      await qosh(r.odam, null);
      r_.appendChild(kut);  // tartib: odam xabari, keyin miya javobi
      await qosh(r.miya, kut);
    } catch (er) {
      kut.innerHTML = `<div class="cx-ich"><div class="pufak"><p>${H(er.message)}</p></div></div>`;
      m.value = matn; osir();
    } finally { band = false; tugma.disabled = false; pastga(); }
  }

  m.addEventListener("input", osir);
  m.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); f.requestSubmit(); } });
  f.addEventListener("submit", e => { e.preventDefault(); yubor(m.value); });

  try {
    const r = await api("/api/chat");
    r_.innerHTML = "";
    for (const x of r.xabarlar) await qosh(x);
    oxirgi = r.hozir;
    if (!r.xabarlar.length) {
      const takl = CHAT_TAKLIF[MEN.boshliq ? "boshliq" : "boshqa"];
      r_.innerHTML = `<div class="cx-bosh"><span class="orb k"><i></i></span><b>Salom, ${H(MEN.odam.ism.split(" ")[0])}!</b>
        <p>Menga oddiy gapirgandek yozing: pul, ish, uchrashuv, kelishuv — hammasini eslab qolaman, hisoblayman va vaqtida eslataman.</p>
        <div class="takl">${takl.map(t => `<button type="button" data-chtakl="${H(t)}"><i class="ti ti-sparkles"></i>${H(t)}</button>`).join("")}</div></div>`;
    }
    pastga();
  } catch (er) { r_.innerHTML = `<div class="bosh">${H(er.message)}</div>`; }
  if (!yoq) m.focus();

  // miya o'zi yuboradigan xabarlar (eslatma, tasdiq so'rovi) — har 15 soniyada
  const taymer = setInterval(async () => {
    if (!document.body.contains(joy)) return clearInterval(taymer);
    if (band || document.hidden || !oxirgi) return;
    try {
      const r = await api(`/api/chat?keyin=${encodeURIComponent(oxirgi)}`);
      oxirgi = r.hozir;
      const yangi = r.xabarlar.filter(x => !korilgan.has(x.k));
      if (!yangi.length) return;
      $(".cx-bosh", r_)?.remove();
      const pastda = r_.scrollHeight - r_.scrollTop - r_.clientHeight < 80;
      for (const x of yangi) await qosh(x);
      if (pastda) pastga();
    } catch (er) { /* tarmoq uzilgan — keyingi safar */ }
  }, 15000);
}
