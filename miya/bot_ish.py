"""Botning ishlar va davomat qismi (I1–I8, M3, M4, O3).

Ish berish kartochkasi pul kartochkasi bilan bir xil yo'l: yetishmagan maydon tugma bilan so'raladi → «To'g'ri».
«Bajarildi» puldan ta'sir qiladi — ovozdan topilsa ham alohida tasdiqlanadi (I-a). Dalil kutilayotganda kelgan
rasm yoki joylashuv — dalil (I-c); aks holda joylashuv — davomat (M3-a).
"""
import json
import re
from datetime import date

from . import baza, davomat, hisob, ishlar, matn, odamlar, vaqt
from . import tgkit as b

DALIL_TUGMA = [("rasm", "Rasm"), ("joylashuv", "Joylashuv"), ("mijoz", "Mijoz tasdig'i"), ("yoq", "Dalilsiz")]


def suhbat_qoy(odam_id: int, holat: str, malumot: dict) -> None:
    baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?) ON CONFLICT(odam_id) DO UPDATE SET "
               "holat=excluded.holat, malumot=excluded.malumot, vaqt=excluded.vaqt",
               odam_id, holat, json.dumps(malumot), vaqt.iso())


def joylashuv_tugma(matn_: str = "Joylashuvni yuborish") -> dict:
    return {"keyboard": [[{"text": matn_, "request_location": True}], [{"text": "Bekor qilish"}]],
            "resize_keyboard": True, "one_time_keyboard": True}


def _vaqt(iso: str | None) -> str:
    return iso[11:16] if iso else "—"


# ---------- ish kartochkasi ----------

def ish_karta_yarat(o: dict, y: dict, xabar_id: int | None, chat_id: int) -> int:
    d = {"tur": "ish", "p": {}, "aytilgan": {k: y.get(k) for k in ("nom", "joy", "mijoz", "ish_turi", "soat")},
         "ijrochi_ismlar": [x for x in (y.get("ijrochilar") or []) if (x or "").strip()], "iqtibos": y.get("iqtibos") or ""}
    p = d["p"]
    p["nom"] = (y.get("nom") or "").strip()[:200]
    p["joy"] = (y.get("joy") or "").strip() or None
    p["ish_turi"] = (y.get("ish_turi") or "").strip().lower() or None
    muddat = (y.get("muddat") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", muddat):
        p["muddat"] = muddat
    soat = (y.get("soat") or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", soat):
        p["soat"] = soat.zfill(5)
    if float(y.get("narx") or 0) > 0:
        v = y.get("valyuta") if y.get("valyuta") in ("UZS", "USD") else "UZS"
        p["narx"], p["valyuta"] = matn.minor(y["narx"], v), v
    if y.get("dalil") in ("rasm", "joylashuv", "mijoz", "yoq"):
        p["dalil_turi"] = y["dalil"]
    p["ijrochilar"] = []
    return baza.bajar("INSERT INTO karta(odam_id,chat_id,xabar_id,malumot,yaratilgan) VALUES(?,?,?,?,?)",
                      o["id"], chat_id, xabar_id, json.dumps(d, ensure_ascii=False), vaqt.iso())


def ish_keyingi_savol(k: dict, o: dict) -> dict | None:
    d, p = k["d"], k["d"]["p"]
    kid = k["id"]
    if not p.get("nom"):
        return {"maydon": "nom", "matn": "Qanday ish? Qisqa yozing:", "yozib": True}
    # ijrochilar
    if not p["ijrochilar"] and not d.get("ijrochi_tanlash"):
        if not ishlar.tolov_huquqi(o):
            p["ijrochilar"] = [o["id"]]
        else:
            odamlar_ = [(x["id"], x["ism"]) for x in odamlar.faol_odamlar() if x["holat"] == "faol"]
            qolgan = []
            for ism in d["ijrochi_ismlar"]:
                if ism.lower() in ("men", "o'zim", "ozim"):
                    p["ijrochilar"].append(o["id"])
                    continue
                bitta = matn.yagona(matn.mosla(ism, odamlar_))
                if bitta:
                    if bitta[0] not in p["ijrochilar"]:
                        p["ijrochilar"].append(bitta[0])
                else:
                    qolgan.append(ism)
            d["ijrochi_ismlar"] = qolgan
    if d["ijrochi_ismlar"]:
        ism = d["ijrochi_ismlar"][0]
        mos = matn.mosla(ism, [(x["id"], x["ism"]) for x in odamlar.faol_odamlar()])
        royxat = mos[:6] if mos else [(x["id"], x["ism"], 0) for x in odamlar.faol_odamlar()][:12]
        return {"maydon": "ijrochi", "matn": f"«{b.e(ism)}» — qaysi xodim?",
                "tugmalar": [[n, f"ij:{kid}:{i}"] for i, n, _ in royxat] + [["Uni qo'shmaslik", f"ij:{kid}:0"]]}
    if not p["ijrochilar"]:
        taklif = ishlar.ijrochi_taklif(p.get("ish_turi"))[:8]
        d["ijrochi_tanlash"] = True
        return {"maydon": "ijrochi", "matn": "Kimga beriladi?" + (" (avval kim qilgani va hozirgi ishlari bilan)" if p.get("ish_turi") else ""),
                "tugmalar": [[f"{x['ism']}" + (f" · {x['qilgan']} marta qilgan" if x["qilgan"] else "") +
                              f" · {x['ochiq']} ta ishi bor", f"ij:{kid}:{x['odam_id']}"] for x in taklif]}
    # mijoz (ixtiyoriy)
    ism = (d["aytilgan"].get("mijoz") or "").strip()
    if ism and "mijoz_id" not in p and not p.get("mijozsiz"):
        mos = matn.mosla(ism, [(r["id"], r["ism"]) for r in baza.hammasi("SELECT id,ism FROM mijoz WHERE tur='mijoz' AND "
                                                                         "birlashdi IS NULL")])
        bitta = matn.yagona(mos)
        if bitta:
            p["mijoz_id"] = bitta[0]
        else:
            tug = [[n, f"km:{kid}:{i}"] for i, n, _ in mos[:5]] + [[f"Yangi mijoz: {ism[:40]}", f"km:{kid}:yangi"],
                                                                   ["Mijozsiz", f"km:{kid}:yoq"]]
            return {"maydon": "mijoz", "matn": f"«{b.e(ism)}» — qaysi mijoz?", "tugmalar": tug}
    if "dalil_turi" not in p:
        p["dalil_turi"] = baza.sozlama("dalil_standart", "rasm")
    return None


def ish_karta_matni(k: dict) -> str:
    p = k["d"]["p"]
    ismlar = [odamlar.odam(x)["ism"] for x in p["ijrochilar"] if odamlar.odam(x)]
    q = [f"<b>Yangi ish</b> · {b.e(', '.join(ismlar))}", b.e(p["nom"])]
    if p.get("joy"):
        q.append(f"Joy: {b.e(p['joy'])}")
    if p.get("mijoz_id"):
        m = baza.bir("SELECT ism FROM mijoz WHERE id=?", p["mijoz_id"])
        q.append(f"Mijoz: {b.e(m['ism'] if m else '')}")
    if p.get("muddat"):
        q.append(f"Muddat: {vaqt.sana_matn(p['muddat'])}" + (f", {p['soat']}" if p.get("soat") else ""))
    else:
        q.append("Muddat: aytilmagan")
    if p.get("narx"):
        q.append(f"Narxi: <b>{matn.pul(p['narx'], p['valyuta'])}</b> — {matn.pul_soz(p['narx'], p['valyuta'])}"
                 + (f" ({len(ismlar)} kishiga teng ulush)" if len(ismlar) > 1 else ""))
    q.append(f"Dalil: {ishlar.DALIL_NOMI[p['dalil_turi']]}")
    if k["d"].get("iqtibos"):
        q.append(f"<i>«{b.e(k['d']['iqtibos'][:200])}»</i>")
    return "\n".join(q)


class IshQismi:
    """Bot sinfiga qo'shiladigan usullar."""

    # ---------- kartochka ----------

    async def ish_karta_davom(self, kid: int, o: dict, msg_id: int | None = None):
        k = b._karta(kid)
        if not k or k["holat"] != "ochiq":
            return
        savol = ish_keyingi_savol(k, o)
        b._karta_saqla(kid, k["d"])
        chat = k["chat_id"]
        if savol:
            tug = [[t[0], t[1]] for t in savol.get("tugmalar", [])] + [["Bekor qilish", f"k:{kid}:bekor"]]
            if savol.get("yozib"):
                suhbat_qoy(o["id"], f"ishk_{savol['maydon']}", {"karta": kid})
            if msg_id:
                return await self.tahrir(chat, msg_id, "<b>Yangi ish</b>\n" + savol["matn"], tug)
            return await self.yoz(chat, "<b>Yangi ish</b>\n" + savol["matn"], tug)
        m = ish_karta_matni(k)
        if msg_id:
            await self.tahrir(chat, msg_id, m, b.KARTA_TUGMA(kid))
        else:
            r = await self.yoz(chat, m, b.KARTA_TUGMA(kid))
            baza.bajar("UPDATE karta SET msg_id=? WHERE id=?", r["message_id"], kid)

    async def ish_karta_tugma(self, k: dict, o: dict, tur: str, qiymat: str, chat_id: int, msg_id: int) -> str:
        kid, d = k["id"], k["d"]
        p = d["p"]
        if tur == "ij":
            if d["ijrochi_ismlar"]:
                d["ijrochi_ismlar"].pop(0)
            if qiymat != "0" and int(qiymat) not in p["ijrochilar"]:
                p["ijrochilar"].append(int(qiymat))
            d.pop("ijrochi_tanlash", None)
        elif tur == "km":
            if qiymat == "yangi":
                ism = d["aytilgan"].get("mijoz") or "Yangi mijoz"
                p["mijoz_id"] = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES(?,?)", ism[:1].upper() + ism[1:],
                                           vaqt.iso())
            elif qiymat == "yoq":
                p["mijozsiz"] = True
            else:
                p["mijoz_id"] = int(qiymat)
        elif tur == "dl":
            p["dalil_turi"] = qiymat
        elif tur == "kf":
            if qiymat == "ijrochi":
                p["ijrochilar"] = []
                d["ijrochi_ismlar"] = []
            elif qiymat == "dalil":
                b._karta_saqla(kid, d)
                await self.tahrir(chat_id, msg_id, ish_karta_matni(k) + "\n\n<b>Qanday dalil?</b>",
                                  [[[n, f"dl:{kid}:{t}"] for t, n in DALIL_TUGMA[:2]],
                                   [[n, f"dl:{kid}:{t}"] for t, n in DALIL_TUGMA[2:]]])
                return ""
            elif qiymat in ("muddat", "narx", "nom"):
                b._karta_saqla(kid, d)
                suhbat_qoy(o["id"], f"ishk_{qiymat}", {"karta": kid})
                await self.yoz(chat_id, {"muddat": "Muddatni yozing (masalan: 10.10, ertaga):",
                                         "narx": "Ish narxini yozing (0 — narxsiz):",
                                         "nom": "Ish nomini yozing:"}[qiymat])
                return ""
        elif tur == "k":
            if qiymat == "tuz":
                await self.tahrir(chat_id, msg_id, ish_karta_matni(k) + "\n\n<b>Nimasi noto'g'ri?</b>",
                                  [[["Ijrochi", f"kf:{kid}:ijrochi"], ["Muddat", f"kf:{kid}:muddat"]],
                                   [["Narx", f"kf:{kid}:narx"], ["Dalil", f"kf:{kid}:dalil"]],
                                   [["Ish nomi", f"kf:{kid}:nom"], ["Orqaga", f"kt:{kid}:orqa"]]])
                return ""
            if qiymat == "ok":
                iid, xabarlar = ishlar.ish_yarat(
                    p["nom"], [(x, 1) for x in p["ijrochilar"]], o["id"], joy=p.get("joy"), mijoz_id=p.get("mijoz_id"),
                    muddat=p.get("muddat"), soat=p.get("soat"), narx=p.get("narx"), valyuta=p.get("valyuta", "UZS"),
                    dalil_turi=p.get("dalil_turi"), ish_turi=p.get("ish_turi"), xabar_id=k["xabar_id"])
                baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", kid)
                await self.tahrir(chat_id, msg_id, ish_karta_matni(k) + f"\n\n✓ Ish berildi · #{iid}")
                return "Ish berildi"
        elif tur == "kt" and qiymat == "orqa":
            await self.tahrir(chat_id, msg_id, ish_karta_matni(k), b.KARTA_TUGMA(kid))
            return ""
        b._karta_saqla(kid, d)
        await self.ish_karta_davom(kid, o, msg_id=msg_id)
        return ""

    async def ish_suhbat(self, o: dict, chat_id: int, holat: str, d: dict, matn_: str) -> bool:
        """Yozib javob kutilgan ish holatlari. Ishlangan bo'lsa True."""
        if holat.startswith("ishk_"):
            k = b._karta(d["karta"])
            if not k or k["holat"] != "ochiq":
                return True
            maydon, p = holat[5:], k["d"]["p"]
            if maydon == "nom":
                p["nom"] = matn_.strip()[:200]
            elif maydon == "muddat":
                s = b._sana_oqi(matn_, kelajak=True)
                if not s:
                    suhbat_qoy(o["id"], holat, d)
                    await self.yoz(chat_id, "Sanani tushunmadim. Masalan: 10.10 yoki ertaga")
                    return True
                p["muddat"] = s
            elif maydon == "narx":
                son, v, _ = b.summa_oqi(matn_)
                if son is None:
                    suhbat_qoy(o["id"], holat, d)
                    await self.yoz(chat_id, "Narxni raqam bilan yozing, masalan: 300 000")
                    return True
                v = v or "UZS"
                if son <= 0:
                    p.pop("narx", None)
                else:
                    p["narx"], p["valyuta"] = matn.minor(son, v), v
            b._karta_saqla(k["id"], k["d"])
            await self.ish_karta_davom(k["id"], o)
            return True
        if holat == "qayta_sabab":
            try:
                ishlar.qayta(d["ish"], o["id"], matn_)
                await self.yoz(chat_id, "Ish qayta ishlashga qaytarildi, ijrochilarga xabar boradi.")
            except ishlar.IshXato as x:
                await self.yoz(chat_id, b.e(x))
            return True
        return False

    # ---------- bajarildi va dalil ----------

    async def bajarildi_sora(self, o: dict, chat_id: int, bj: dict, xabar_id: int | None):
        """AI topgan «bajarildi» — tasdiq bilan (I-a)."""
        iid = int(bj.get("ish_id") or 0)
        i = ishlar.ish(iid) if iid else None
        if i and i["holat"] in ishlar.OCHIQ and any(x["odam_id"] == o["id"] for x in i["ijrochilar"]):
            return await self.yoz(chat_id, f"Bajarildi deb belgilaymi?\n<b>{b.e(ishlar.qisqa(i))}</b>",
                                  [[["Ha, bajarildi", f"ib:{iid}:1"], ["Yo'q", f"ib:{iid}:0"]]])
        nom = (bj.get("nom") or "").strip()
        if not nom:
            return
        kid = baza.bajar("INSERT INTO karta(odam_id,chat_id,xabar_id,malumot,yaratilgan) VALUES(?,?,?,?,?)",
                         o["id"], chat_id, xabar_id, json.dumps({"tur": "ishyangi", "nom": nom[:200], "izoh": bj.get("izoh")},
                                                                ensure_ascii=False), vaqt.iso())
        await self.yoz(chat_id, f"Ro'yxatingizda yo'q ish: <b>{b.e(nom)}</b>\nYangi ish sifatida yozib, bajarildi deb "
                                "belgilaymi? (narxini boshliq qo'yadi)",
                       [[["Ha", f"k:{kid}:ok"], ["Yo'q", f"k:{kid}:bekor"]]])

    async def bajarildi_bajar(self, o: dict, chat_id: int, iid: int, izoh: str | None = None):
        try:
            r = ishlar.bajarildi_dedi(iid, o["id"], izoh)
        except ishlar.IshXato as x:
            return await self.yoz(chat_id, b.e(x))
        await self.dalil_sora(o, chat_id, iid, r)

    async def dalil_sora(self, o: dict, chat_id: int, iid: int, r: dict):
        i = ishlar.ish(iid)
        if r["holat"] == "bajarildi":
            return await self.yoz(chat_id, f"✓ Ish yopildi: {b.e(ishlar.qisqa(i))}" +
                                  ("\nNarxi boshliq qabul qilgach hisobingizga tushadi." if i["narx"] else ""),
                                  menyu_=b.menyu(o))
        tur = r["dalil"]
        if tur == "mijoz" and i["mijoz_tg"]:
            try:
                await self.yoz(i["mijoz_tg"], f"Assalomu alaykum! Ishxonamiz xodimi «{b.e(i['nom'])}» ishini bajarganini "
                                              "aytdi. Ish bajarildimi?",
                               [[["Ha, bajarildi", f"mb:{iid}:1"], ["Yo'q", f"mb:{iid}:0"]]])
                return await self.yoz(chat_id, "Mijozdan tasdiq so'raldi — u «Ha» desa ish yopiladi.")
            except Exception:
                tur = "rasm"
        if tur in ("rasm", "mijoz"):
            suhbat_qoy(o["id"], "dalil_rasm", {"ish": iid})
            return await self.yoz(chat_id, f"Ish rasmini yuboring — shunda ish yopiladi.\n{b.e(ishlar.qisqa(i))}")
        if tur == "joylashuv":
            suhbat_qoy(o["id"], "dalil_joylashuv", {"ish": iid})
            return await self.yoz(chat_id, "Ish joyidaligingizni tasdiqlash uchun joylashuvni yuboring.",
                                  menyu_=joylashuv_tugma())

    async def dalil_rasm(self, o: dict, x: dict, iid: int):
        chat_id = x["chat"]["id"]
        xid, _, q = await self.xabar_saqla(o, x)
        try:
            r = ishlar.dalil_qosh(iid, o["id"], "rasm", xabar_id=xid, fayl=q["fayl"], uzatilgan=bool(q["uzatilgan"]))
        except ishlar.IshXato as e_:
            return await self.yoz(chat_id, b.e(e_))
        baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        baza.bajar("UPDATE ilova SET tur='ish_dalil' WHERE xabar_id=?", xid)
        await self.dalil_sora(o, chat_id, iid, r)

    async def joylashuv(self, o: dict, x: dict):
        chat_id = x["chat"]["id"]
        loc = x["location"]
        uzatilgan = bool(x.get("forward_origin") or x.get("forward_from"))
        s = baza.bir("SELECT * FROM suhbat WHERE odam_id=?", o["id"])
        if s and s["holat"] == "dalil_joylashuv":
            iid = json.loads(s["malumot"])["ish"]
            try:
                r = ishlar.dalil_qosh(iid, o["id"], "joylashuv", lat=loc["latitude"], lon=loc["longitude"],
                                      uzatilgan=uzatilgan)
            except ishlar.IshXato as e_:
                return await self.yoz(chat_id, b.e(e_), menyu_=joylashuv_tugma())
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
            return await self.dalil_sora(o, chat_id, iid, r)
        if uzatilgan:
            return await self.yoz(chat_id, "Uzatilgan joylashuv qabul qilinmaydi — o'zingiz yuboring.", menyu_=b.menyu(o))
        await self.davomat_yoz(o, chat_id, loc["latitude"], loc["longitude"])

    async def davomat_yoz(self, o: dict, chat_id: int, lat=None, lon=None):
        try:
            r = davomat.belgila(o["id"], lat, lon)
        except davomat.DavomatXato as x:
            return await self.yoz(chat_id, b.e(x))
        if r["tur"] == "keldi":
            q = f"✓ Keldingiz: {_vaqt(r['vaqt'])}"
            if r["kechikish"]:
                q += f" · {r['kechikish']} daqiqa kechikish"
            if r["masofa"] is not None and r["masofa"] > 500:
                q += f" · ofisdan {r['masofa']} m uzoqda"
            if r["joylashuvsiz"]:
                q += " · joylashuvsiz"
            ochiq = ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)
            if ochiq:
                q += f"\nBugungi ishlaringiz: {len(ochiq)} ta — «Ishlarim»"
        elif r["tur"] == "ketdi":
            keldi = vaqt.hozir().fromisoformat(r["keldi"])
            ketdi = vaqt.hozir().fromisoformat(r["vaqt"])
            daq = int((ketdi - keldi).total_seconds() // 60)
            q = f"✓ Ketdingiz: {_vaqt(r['vaqt'])} · bugun {daq // 60} soat {daq % 60} daqiqa"
        else:
            q = f"Bugun allaqachon belgilangan: keldi {_vaqt(r['keldi'])}, ketdi {_vaqt(r['ketdi'])}"
        await self.yoz(chat_id, q, menyu_=b.menyu(o))

    # ---------- ro'yxatlar ----------

    async def ishlarim(self, o: dict, chat_id: int):
        ochiq = ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)
        if not ochiq:
            return await self.yoz(chat_id, "Ochiq ishingiz yo'q.", menyu_=b.menyu(o))
        q, tug = ["<b>Ishlarim</b>"], []
        for i in ochiq[:15]:
            kech = ishlar.kechikdi_kun(i)
            belgi = (f" · <b>{kech} kun kechikdi</b>" if kech else "") + \
                    (" · dalil kutilmoqda" if i["holat"] == "bajarildi_dalil" else "") + \
                    (" · qayta ishlash kerak" if i["holat"] == "qayta" else "")
            q.append(f"• {b.e(ishlar.qisqa(i))}{belgi}")
            qator = [[f"#{i['id']} bajarildi", f"id:{i['id']}"]]
            if any(x["odam_id"] == o["id"] and not x["korildi"] for x in i["ijrochilar"]):
                qator.append([f"#{i['id']} ko'rdim", f"ik:{i['id']}"])
            tug.append(qator)
        await self.yoz(chat_id, "\n".join(q), tug)

    async def ishlar_menyu(self, o: dict, chat_id: int):
        if not ishlar.tolov_huquqi(o):
            return await self.ishlarim(o, chat_id)
        q = ["<b>Ishlar — bugun</b>"]
        for x in davomat.bugun_holati():
            if x["ochiq_ish"] or x["kechikkan_ish"] or x["bugun_bajardi"]:
                q.append(f"{b.e(x['ism'])}: ochiq {x['ochiq_ish']}" + (f", kechikkan {x['kechikkan_ish']}" if x["kechikkan_ish"] else "")
                         + (f", bugun bajardi {x['bugun_bajardi']}" if x["bugun_bajardi"] else ""))
        kutish = ishlar.ishlar(qabul_kerak=True)
        if kutish:
            q.append("\n<b>Qabul kutmoqda:</b>")
        await self.yoz(chat_id, "\n".join(q) if len(q) > 1 else "Bugun ochiq ish yo'q. Ish berish uchun oddiy yozing: "
                                                                "«Akmal ertaga Chilonzorga borsin».", menyu_=b.menyu(o))
        for i in kutish[:10]:
            await self.yoz(chat_id, f"{b.e(ishlar.qisqa(i))}\nBajardi: {b.e(', '.join(x['ism'] for x in i['ijrochilar']))}"
                                    + (f"\nNarxi: {matn.pul(i['narx'], i['valyuta'])}" if i["narx"] else ""),
                           [[["Qabul qilish", f"iq:{i['id']}:1"], ["Qayta ishlash", f"iq:{i['id']}:0"]]])

    # ---------- tugmalar ----------

    async def ish_tugma(self, o: dict | None, tur: str, qism: list, chat_id: int, msg_id: int, tg_id: int) -> str:
        if tur == "mb":  # mijoz javobi (I6)
            m = baza.bir("SELECT * FROM mijoz WHERE tg_id=?", tg_id)
            i = ishlar.ish(int(qism[1]))
            if not m or not i or i["mijoz_id"] != m["id"]:
                return "Bu so'rov sizga tegishli emas"
            if qism[2] == "1":
                try:
                    ishlar.dalil_qosh(i["id"], None, "mijoz", mijoz_id=m["id"])
                except ishlar.IshXato as x:
                    return str(x)[:180]
                await self.tahrir(chat_id, msg_id, "Rahmat! Javobingiz yozildi.")
            else:
                boss = odamlar.boshliq()
                if boss:
                    hisob.xabarnoma(boss["id"], "malumot", f"Mijoz {m['ism']} ish bajarilmagan dedi: {ishlar.qisqa(i)}")
                await self.tahrir(chat_id, msg_id, "Rahmat, javobingiz ishxonaga yetkazildi.")
            return "Yozildi"
        if not o:
            return "Ruxsat yo'q"
        if tur == "ik":
            ishlar.korildi(int(qism[1]), o["id"])
            i = ishlar.ish(int(qism[1]))
            if i:
                await self.tahrir(chat_id, msg_id, f"{b.e(ishlar.ish_matni(i))}\n\n✓ Ko'rdingiz")
            return "Yozildi"
        if tur in ("ib", "id"):
            iid = int(qism[1])
            if tur == "ib" and qism[2] == "0":
                await self.tahrir(chat_id, msg_id, "Mayli, belgilanmadi.")
                return ""
            await self.tahrir(chat_id, msg_id, f"«Bajarildi» — #{iid}")
            await self.bajarildi_bajar(o, chat_id, iid)
            return ""
        if tur == "iq":
            iid = int(qism[1])
            if qism[2] == "1":
                try:
                    ishlar.qabul(iid, o["id"])
                except (ishlar.IshXato, hisob.HisobXato) as x:
                    return str(x)[:180]
                await self.tahrir(chat_id, msg_id, f"✓ Qabul qilindi: {b.e(ishlar.qisqa(ishlar.ish(iid)))}")
                return "Qabul qilindi"
            suhbat_qoy(o["id"], "qayta_sabab", {"ish": iid})
            await self.yoz(chat_id, "Nima uchun qayta ishlash kerak? Sababini yozing:")
            return ""
        if tur == "dv":
            try:
                davomat.sorov_hal(int(qism[1]), o["id"], qism[2] == "1")
            except davomat.DavomatXato as x:
                return str(x)[:180]
            await self.tahrir(chat_id, msg_id, "✓ Tasdiqlandi" if qism[2] == "1" else "✗ Rad etildi")
            return "Yozildi"
        return ""

    # ---------- AI natijasi: ishlar, bajarildi, davomat ----------

    async def ish_natija(self, o: dict, chat_id: int, natija: dict, xabar_id: int | None):
        for y in (natija.get("ishlar") or [])[:5]:
            if not (y.get("nom") or "").strip():
                continue
            if y.get("ijrochilar") and not ishlar.tolov_huquqi(o) and any(
                    (n or "").lower() not in ("men", "o'zim", "ozim") for n in y["ijrochilar"]):
                await self.yoz(chat_id, "Boshqa xodimga ishni boshliq yoki menejer beradi.")
                continue
            kid = ish_karta_yarat(o, y, xabar_id, chat_id)
            await self.ish_karta_davom(kid, o)
        for bj in (natija.get("bajarildi") or [])[:5]:
            await self.bajarildi_sora(o, chat_id, bj, xabar_id)
        for dv in (natija.get("davomat") or [])[:2]:
            if dv.get("tur") in ("keldi", "ketdi"):
                await self.davomat_yoz(o, chat_id)
            elif dv.get("tur") == "unutilgan":
                sana = (dv.get("sana") or "")[:10]
                try:
                    date.fromisoformat(sana)
                    davomat.sorov(o["id"], sana, dv.get("izoh") or None)
                    await self.yoz(chat_id, f"{vaqt.sana_matn(sana)} kuni uchun so'rov boshliqqa yuborildi.")
                except (ValueError, davomat.DavomatXato) as x:
                    await self.yoz(chat_id, f"Davomat so'rovi yuborilmadi: {b.e(x)}")
        if (natija.get("muammo") or "").strip():
            boss = odamlar.boshliq()
            if boss and boss["id"] != o["id"]:
                hisob.xabarnoma(boss["id"], "malumot", f"{o['ism']} muammo aytdi: {natija['muammo'][:500]}")
                await self.yoz(chat_id, "Muammo boshliqqa yetkazildi.")

    # ---------- jadval: ertalab, kechqurun, avto qabul ----------

    async def ish_jadval(self):
        hozir = vaqt.hozir()
        bugun = hozir.date()
        b_iso = bugun.isoformat()
        soat = hozir.strftime("%H:%M")
        ishlar.avto_qabul()
        if ishlar.dam_olishmi(bugun):
            return
        if soat >= str(baza.sozlama("ertalab_vaqti", "08:00")):
            if self._bir_marta(f"takror:{b_iso}"):
                ishlar.takroriy_yarat(bugun)
            for o in odamlar.faol_odamlar():
                if o["holat"] != "faol" or not o["tg_id"]:
                    continue
                ochiq = [i for i in ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)
                         if not i["muddat"] or i["muddat"] <= b_iso]
                if ochiq and self._bir_marta(f"ertalab:{o['id']}:{b_iso}"):
                    q = [f"Xayrli tong, {o['ism'].split()[0]}! Bugungi ishlaringiz:"]
                    for i in ochiq[:12]:
                        kech = ishlar.kechikdi_kun(i)
                        q.append(f"• {ishlar.qisqa(i)}" + (f" · {kech} kun kechikdi" if kech else ""))
                    hisob.xabarnoma(o["id"], "ertalab", "\n".join(q), None,
                                    [[f"#{i['id']} bajarildi", f"id:{i['id']}"] for i in ochiq[:6]])
        if soat >= str(baza.sozlama("kechki_vaqt", "18:00")):
            for o in odamlar.faol_odamlar():
                if o["holat"] != "faol" or not o["tg_id"]:
                    continue
                bugungi = [i for i in ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)
                           if not i["muddat"] or i["muddat"] <= b_iso]
                if bugungi and self._bir_marta(f"kechki:{o['id']}:{b_iso}"):
                    hisob.xabarnoma(o["id"], "kechki", "Bugun nima qildingiz? Ovozli xabar yuboring — bajarilgan ishlarni "
                                                       "o'zim topib, tasdiqlash uchun ko'rsataman.")
