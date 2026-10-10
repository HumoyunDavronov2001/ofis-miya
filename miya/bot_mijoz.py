"""Botning mijozlar qismi (C1–C6, P6): va'da kartochkasi, mijoz eslatmalari, va'da eslatmalari, uxlab qolgan mijozlar.

Va'da pul emas — lekin eslatma va bashoratga ta'sir qiladi, shuning uchun kartochka bilan tasdiqlanadi (C-d).
Mijoz haqidagi eslatma esa o'zi saqlanadi, ostida [Bekor qilish] tugmasi bo'ladi (C-e).
"""
import json
import re
from datetime import timedelta

from . import baza, hisob, matn, mijozlar, odamlar, vadalar, vaqt
from . import tgkit as b
from .bot_ish import suhbat_qoy

HAFTA_KUNI = {"dushanba": 0, "seshanba": 1, "chorshanba": 2, "payshanba": 3, "juma": 4, "shanba": 5, "yakshanba": 6}


def _mijozlar(kim: str) -> list[tuple[int, str]]:
    shart = "tur='mijoz' AND " if kim == "mijoz" else ""
    return [(r["id"], r["ism"]) for r in baza.hammasi(f"SELECT id,ism FROM mijoz WHERE {shart}birlashdi IS NULL")]


def _ism(mid: int | None) -> str:
    m = baza.bir("SELECT ism FROM mijoz WHERE id=?", mid) if mid else None
    return m["ism"] if m else ""


def muddat_oqi(s: str) -> str | None:
    """«ertaga», «10.10», «juma», «juma kuni» → kelajakdagi sana (bugun ham bo'ladi)."""
    s = (s or "").strip().lower().replace(" kuni", "").strip(" .")
    if s in HAFTA_KUNI:
        bugun = vaqt.bugun()
        farq = (HAFTA_KUNI[s] - bugun.weekday()) % 7
        return (bugun + timedelta(days=farq or 7)).isoformat()
    d = b.sana_oqi(s, kelajak=True)
    return d if d and d >= vaqt.bugun().isoformat() else None


def _muddat_tugmalari(kid: int) -> list:
    bugun = vaqt.bugun()
    juma = bugun + timedelta(days=((4 - bugun.weekday()) % 7) or 7)
    variant = [("Bugun", bugun), ("Ertaga", bugun + timedelta(days=1)), ("Indinga", bugun + timedelta(days=2)),
               (f"Juma ({juma.day}-{vaqt.OYLAR[juma.month - 1][:3]})", juma), ("Bir haftada", bugun + timedelta(days=7))]
    return [[n, f"kv:{kid}:{d.isoformat()}"] for n, d in variant]


# ---------- va'da kartochkasi ----------

def vada_karta_yarat(o: dict, y: dict, xabar_id: int | None, chat_id: int) -> int:
    a = {"mijoz": (y.get("mijoz") or "").strip()[:80], "matn": (y.get("matn") or "").strip()[:300]}
    summa = float(y.get("summa") or 0)
    if summa > 0:
        a["summa"] = summa
        a["valyuta"] = y.get("valyuta") if y.get("valyuta") in ("UZS", "USD") else None
        a["birlik_noaniq"] = bool(y.get("birlik_noaniq"))
    vtur = y.get("tur") if y.get("tur") in ("tolov", "boshqa") else ("tolov" if summa > 0 else "boshqa")
    d = {"tur": "vada", "kim": y.get("kim") if y.get("kim") in ("mijoz", "biz") else "mijoz", "vtur": vtur, "p": {},
         "aytilgan": a, "iqtibos": (y.get("iqtibos") or "")[:500]}
    muddat = (y.get("muddat") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", muddat) and muddat >= vaqt.bugun().isoformat():
        d["p"]["muddat"] = muddat
    if vtur == "boshqa" and a["matn"]:
        d["p"]["matn"] = a["matn"]
    return baza.bajar("INSERT INTO karta(odam_id,chat_id,xabar_id,malumot,yaratilgan) VALUES(?,?,?,?,?)",
                      o["id"], chat_id, xabar_id, json.dumps(d, ensure_ascii=False), vaqt.iso())


def vada_keyingi_savol(k: dict, o: dict) -> dict | None:
    d, p, a, kid = k["d"], k["d"]["p"], k["d"]["aytilgan"], k["id"]
    # 1. mijoz
    if "mijoz_id" not in p:
        ism = a.get("mijoz", "")
        mos = matn.mosla(ism, _mijozlar(d["kim"])) if ism else []
        bitta = matn.yagona(mos)
        if bitta:
            p["mijoz_id"] = bitta[0]
        else:
            tug = [[n, f"km:{kid}:{i}"] for i, n, _ in mos[:5]]
            if ism:
                tug.append([f"Yangi mijoz: {ism[:40]}", f"km:{kid}:yangi"])
            return {"maydon": "mijoz", "matn": f"«{b.e(ism)}» — qaysi mijoz?" if ism else "Qaysi mijoz? Ismini yozing:",
                    "tugmalar": tug, "yozib": True}
    # 2. summa yoki nima va'da qilingani
    if d["vtur"] == "tolov" and "summa" not in p:
        if "summa" in a and not a.get("birlik_noaniq"):
            v = a.get("valyuta") or "UZS"
            p["summa"], p["valyuta"] = matn.minor(a["summa"], v), v
        elif "summa" in a:
            son = a["summa"]
            return {"maydon": "birlik", "matn": f"«{matn.guruh(int(son))}» — qaysi biri?", "tugmalar": [
                [f"{matn.guruh(int(son))} so'm", f"kb:{kid}:1"], [f"{matn.guruh(int(son * 1000))} so'm", f"kb:{kid}:1000"],
                [f"{matn.guruh(int(son * 1_000_000))} so'm", f"kb:{kid}:1000000"], [f"{matn.guruh(int(son))} $", f"kb:{kid}:usd"]]}
        else:
            tug = []
            if d["kim"] == "mijoz":
                for v, s in hisob.qoldiq(f"mijoz:{p['mijoz_id']}").items():
                    if s > 0:
                        tug.append([f"Butun qarzi — {matn.pul(s, v)}", f"vs:{kid}:{v}"])
            return {"maydon": "summa", "matn": "Qancha to'laydi? Summani yozing (masalan: 2 mln):", "tugmalar": tug,
                    "yozib": True}
    if d["vtur"] == "boshqa" and not p.get("matn"):
        return {"maydon": "matn", "matn": "Nima va'da qilindi? Qisqa yozing (masalan: hujjatni olib keladi):", "yozib": True}
    # 3. muddat (C-d: aytilmagan bo'lsa so'raladi)
    if "muddat" not in p:
        return {"maydon": "muddat", "matn": "Qachongacha? Tugmani bosing yoki sanani yozing (masalan: 15.10):",
                "tugmalar": _muddat_tugmalari(kid), "yozib": True}
    return None


def vada_karta_matni(k: dict, o: dict) -> str:
    d, p = k["d"], k["d"]["p"]
    m = mijozlar.mijoz(p["mijoz_id"])
    sarlavha, fel = ("Va'da", "To'laydi") if d["kim"] == "mijoz" else ("Bizning va'da", "To'laymiz")
    q = [f"<b>{sarlavha}</b> · {b.e(m['ism'])}"]
    if d["vtur"] == "tolov":
        q.append(f"{fel}: <b>{matn.pul(p['summa'], p['valyuta'])}</b> — {matn.pul_soz(p['summa'], p['valyuta'])}")
    else:
        q.append(f"Nima: {b.e(p['matn'])}")
    q.append(f"Muddat: {vaqt.sana_matn(p['muddat'])}")
    masul = odamlar.odam(m.get("masul_id") or o["id"])
    if masul:
        q.append(f"Eslatma kimga: {b.e(masul['ism'])}")
    if d["kim"] == "mijoz" and mijozlar.korishi_mumkin(o, m):
        qarz = {v: s for v, s in hisob.qoldiq(f"mijoz:{m['id']}").items() if s > 0}
        q.append(("Qarzi hozir: " + ", ".join(matn.pul(s, v) for v, s in qarz.items()) if qarz else "Hozir qarzi yo'q")
                 + f" · {vadalar.ishonch(m['id'])['matn']}")
    if d["kim"] == "mijoz" and d["vtur"] == "tolov":
        for v in vadalar.almashadiganlar(m["id"]):
            q.append(f"⚠ Oldingi va'da ({matn.pul(v['summa'], v['valyuta'])}, {vaqt.sana_matn(v['muddat'], False)}) "
                     "bajarilmagan — yopiladi, keyingi to'lovlar yangi va'daga yoziladi.")
    if d.get("iqtibos"):
        q.append(f"<i>«{b.e(d['iqtibos'][:200])}»</i>")
    return "\n".join(q)


def vada_qisqa(v: dict) -> str:
    if v["tur"] == "tolov":
        qolgan = v.get("qolgan")
        s = matn.pul(v["summa"], v["valyuta"])
        if qolgan is not None and qolgan != v["summa"]:
            s += f" (qolgani {matn.pul(qolgan, v['valyuta'])})"
    else:
        s = v["matn"] or ""
    kim = "" if v["kim"] == "mijoz" else "biz va'da berganmiz: "
    return f"{v['mijoz']} — {kim}{s}"


def _faol_yoki_boshliq(odam_id: int | None, boss: dict | None) -> int | None:
    """Mas'ul ketmoqda yoki ketgan bo'lsa — eslatma boshliqqa (D-e)."""
    o = odamlar.odam(odam_id) if odam_id else None
    if o and o["holat"] == "faol":
        return o["id"]
    return (boss or {}).get("id")


def mijozga_matn(v: dict, m: dict) -> str:
    joriy = next((x for x in vadalar.royxat(v["mijoz_id"]) if x["id"] == v["id"]), v)
    summa = joriy.get("qolgan") if joriy.get("qolgan") is not None else v["summa"]
    nima = f"{matn.pul(summa, v['valyuta'])} to'lov muddati" if v["tur"] == "tolov" else f"{v['matn']} muddati"
    return (f"Assalomu alaykum, {b.e(m['ism'])}! Eslatma: {vaqt.sana_matn(v['muddat'], False)} — {b.e(nima)}. "
            "Savolingiz bo'lsa, shu yerga yozing.")


class MijozQismi:
    """Bot sinfiga qo'shiladigan usullar."""

    async def vada_karta_davom(self, kid: int, o: dict, msg_id: int | None = None):
        k = b._karta(kid)
        if not k or k["holat"] != "ochiq":
            return
        savol = vada_keyingi_savol(k, o)
        b._karta_saqla(kid, k["d"])
        chat = k["chat_id"]
        if savol:
            tug = [[t[0], t[1]] for t in savol.get("tugmalar", [])] + [["Bekor qilish", f"k:{kid}:bekor"]]
            if savol.get("yozib"):
                suhbat_qoy(o["id"], f"vada_{savol['maydon']}", {"karta": kid})
            matn_ = "<b>Va'da</b>\n" + savol["matn"]
            if msg_id:
                return await self.tahrir(chat, msg_id, matn_, tug)
            return await self.yoz(chat, matn_, tug)
        m = vada_karta_matni(k, o)
        if msg_id:
            await self.tahrir(chat, msg_id, m, b.KARTA_TUGMA(kid))
        else:
            r = await self.yoz(chat, m, b.KARTA_TUGMA(kid))
            baza.bajar("UPDATE karta SET msg_id=? WHERE id=?", r["message_id"], kid)

    async def vada_karta_tugma(self, k: dict, o: dict, tur: str, qiymat: str, chat_id: int, msg_id: int) -> str:
        kid, d = k["id"], k["d"]
        p, a = d["p"], d["aytilgan"]
        if d["tur"] == "eslatma":
            return await self._eslatma_karta(k, o, tur, qiymat, chat_id, msg_id)
        if tur == "km":
            if qiymat == "yangi":
                ism = a.get("mijoz") or "Yangi mijoz"
                p["mijoz_id"] = baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES(?,?,?)",
                                           ism[:1].upper() + ism[1:], "mijoz", vaqt.iso())
                baza.jurnal(o["id"], "mijoz_yarat", f"mijoz:{p['mijoz_id']}", None, ism)
            else:
                p["mijoz_id"] = int(qiymat)
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        elif tur == "kb":
            son = a["summa"]
            if qiymat == "usd":
                a["valyuta"] = "USD"
            else:
                a["summa"], a["valyuta"] = son * int(qiymat), a.get("valyuta") or "UZS"
            a["birlik_noaniq"] = False
        elif tur == "vs":
            p["summa"], p["valyuta"] = hisob.qoldiq(f"mijoz:{p['mijoz_id']}").get(qiymat, 0), qiymat
            if p["summa"] <= 0:
                p.pop("summa")
                return "Qarzi yo'q"
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        elif tur == "kv":
            p["muddat"] = qiymat
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        elif tur == "kf":
            if qiymat == "mijoz":
                p.pop("mijoz_id", None)
                a.pop("mijoz", None)
            elif qiymat == "summa":
                p.pop("summa", None)
                p.pop("valyuta", None)
                a.pop("summa", None)
            elif qiymat == "matn":
                p.pop("matn", None)
            elif qiymat == "muddat":
                p.pop("muddat", None)
        elif tur == "kt" and qiymat == "orqa":
            await self.tahrir(chat_id, msg_id, vada_karta_matni(k, o), b.KARTA_TUGMA(kid))
            return ""
        elif tur == "k":
            if qiymat == "bekor":
                baza.bajar("UPDATE karta SET holat='bekor' WHERE id=?", kid)
                baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
                await self.tahrir(chat_id, msg_id, "Va'da yozilmadi.")
                return "Bekor qilindi"
            if qiymat == "tuz":
                ikkinchi = ["Summa", f"kf:{kid}:summa"] if d["vtur"] == "tolov" else ["Nima", f"kf:{kid}:matn"]
                await self.tahrir(chat_id, msg_id, vada_karta_matni(k, o) + "\n\n<b>Nimasi noto'g'ri?</b>",
                                  [[["Mijoz", f"kf:{kid}:mijoz"], ikkinchi],
                                   [["Muddat", f"kf:{kid}:muddat"], ["Orqaga", f"kt:{kid}:orqa"]]])
                return ""
            if qiymat == "ok":
                try:
                    vid = vadalar.yoz(p["mijoz_id"], p["muddat"], o["id"], kim=d["kim"], tur=d["vtur"],
                                      summa=p.get("summa"), valyuta=p.get("valyuta", "UZS"), matn_=p.get("matn"),
                                      xabar_id=k["xabar_id"], iqtibos=d.get("iqtibos") or None)
                except vadalar.VadaXato as x:
                    return str(x)[:180]
                baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", kid)
                v = vadalar.vada(vid)
                masul = odamlar.odam(v["masul_id"])
                kimga = f"{b.e(masul['ism'].split()[0])}ga" if masul else "mas'ulga"
                await self.tahrir(chat_id, msg_id, vada_karta_matni(k, o).split("\n⚠")[0]
                                  + f"\n\n✓ Va'da yozildi. {vaqt.sana_matn(v['muddat'], False)} kuni ertalab {kimga} "
                                    "eslataman.")
                return "Yozildi"
        b._karta_saqla(kid, d)
        await self.vada_karta_davom(kid, o, msg_id=msg_id)
        return ""

    async def mijoz_suhbat(self, o: dict, chat_id: int, holat: str, d: dict, matn_: str) -> bool:
        """Yozib javob kutilgan va'da holatlari. Ishlangan bo'lsa True."""
        if not holat.startswith("vada_"):
            return False
        k = b._karta(d["karta"])
        if not k or k["holat"] != "ochiq":
            return True
        maydon, p, a = holat[5:], k["d"]["p"], k["d"]["aytilgan"]
        if maydon == "mijoz":
            a["mijoz"] = matn_.strip()[:80]
        elif maydon == "summa":
            son, v, noaniq = b.summa_oqi(matn_)
            if not son or son <= 0:
                suhbat_qoy(o["id"], holat, d)
                await self.yoz(chat_id, "Summani raqam bilan yozing, masalan: 2 mln yoki 500 000")
                return True
            a["summa"], a["valyuta"], a["birlik_noaniq"] = son, v, noaniq
        elif maydon == "matn":
            p["matn"] = matn_.strip()[:300]
        elif maydon == "muddat":
            s = muddat_oqi(matn_)
            if not s:
                suhbat_qoy(o["id"], holat, d)
                await self.yoz(chat_id, "Sanani tushunmadim (o'tgan kun bo'lmasin). Masalan: 15.10, ertaga yoki juma")
                return True
            p["muddat"] = s
        b._karta_saqla(k["id"], k["d"])
        await self.vada_karta_davom(k["id"], o)
        return True

    # ---------- mijoz eslatmasi (C-e) ----------

    async def _eslatma_saqla(self, o: dict, chat_id: int, mid: int, matn_: str, xabar_id: int | None,
                             msg_id: int | None = None):
        eid = mijozlar.eslatma_qosh(mid, matn_, o["id"], xabar_id)
        q = f"📝 {b.e(_ism(mid))} haqida eslatma saqlandi: «{b.e(matn_)}»"
        tug = [["Bekor qilish", f"me:{eid}"]]
        if msg_id:
            return await self.tahrir(chat_id, msg_id, q, tug)
        return await self.yoz(chat_id, q, tug)

    async def _eslatma_karta(self, k: dict, o: dict, tur: str, qiymat: str, chat_id: int, msg_id: int) -> str:
        d = k["d"]
        if tur == "k" and qiymat == "bekor":
            baza.bajar("UPDATE karta SET holat='bekor' WHERE id=?", k["id"])
            await self.tahrir(chat_id, msg_id, "Eslatma saqlanmadi.")
            return ""
        if tur != "km":
            return ""
        if qiymat == "yangi":
            ism = d["ism"] or "Yangi mijoz"
            mid = baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES(?,?,?)", ism[:1].upper() + ism[1:], "mijoz",
                             vaqt.iso())
            baza.jurnal(o["id"], "mijoz_yarat", f"mijoz:{mid}", None, ism)
        else:
            mid = int(qiymat)
        baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", k["id"])
        await self._eslatma_saqla(o, chat_id, mid, d["matn"], k["xabar_id"], msg_id)
        return "Saqlandi"

    async def mijoz_natija(self, o: dict, chat_id: int, natija: dict, xabar_id: int | None):
        for y in (natija.get("vadalar") or [])[:5]:
            if not (y.get("mijoz") or "").strip() and not float(y.get("summa") or 0) and not (y.get("matn") or "").strip():
                continue
            kid = vada_karta_yarat(o, y, xabar_id, chat_id)
            await self.vada_karta_davom(kid, o)
        for es in (natija.get("mijoz_eslatmalar") or [])[:5]:
            ism, matn_ = (es.get("mijoz") or "").strip(), (es.get("matn") or "").strip()[:300]
            if not matn_:
                continue
            mos = matn.mosla(ism, _mijozlar("hammasi")) if ism else []
            bitta = matn.yagona(mos)
            if bitta:
                await self._eslatma_saqla(o, chat_id, bitta[0], matn_, xabar_id)
                continue
            kid = baza.bajar("INSERT INTO karta(odam_id,chat_id,xabar_id,malumot,yaratilgan) VALUES(?,?,?,?,?)",
                             o["id"], chat_id, xabar_id,
                             json.dumps({"tur": "eslatma", "ism": ism[:80], "matn": matn_}, ensure_ascii=False), vaqt.iso())
            tug = [[n, f"km:{kid}:{i}"] for i, n, _ in mos[:5]]
            if ism:
                tug.append([f"Yangi mijoz: {ism[:40]}", f"km:{kid}:yangi"])
            tug.append(["Saqlamaslik", f"k:{kid}:bekor"])
            await self.yoz(chat_id, f"📝 Eslatma: «{b.e(matn_)}»\n" + (f"«{b.e(ism)}» — qaysi mijoz?" if ism else
                                                                        "Qaysi mijoz haqida?"), tug)

    # ---------- tugmalar: eslatmani bekor qilish, va'dani yopish, mijozga eslatish ----------

    async def mijoz_tugma(self, o: dict, tur: str, qism: list, chat_id: int, msg_id: int) -> str:
        if tur == "me":
            e_ = baza.bir("SELECT * FROM mijoz_eslatma WHERE id=?", int(qism[1]))
            if not e_ or e_["bekor"]:
                return "Allaqachon bekor qilingan"
            if e_["yozgan_id"] != o["id"] and o["rol"] not in ("boshliq", "menejer"):
                return "Buni faqat yozgan odam bekor qiladi"
            mijozlar.eslatma_bekor(e_["id"], o["id"])
            await self.tahrir(chat_id, msg_id, f"Eslatma bekor qilindi: «{b.e(e_['matn'])}»")
            return "Bekor qilindi"
        v = vadalar.vada(int(qism[1]))
        if not v:
            return "Va'da topilmadi"
        huquq = o["id"] in (v["masul_id"], v["yozgan_id"]) or o["rol"] in ("boshliq", "menejer")
        if not huquq:
            return "Bu va'da sizga tegishli emas"
        m = mijozlar.mijoz(v["mijoz_id"])
        if tur == "vb":
            try:
                vadalar.boshqa_yop(v["id"], o["id"], qism[2] == "1")
            except vadalar.VadaXato as x:
                return str(x)[:180]
            await self.tahrir(chat_id, msg_id, f"{b.e(m['ism'])} — {b.e(v['matn'] or '')}\n"
                                               + ("✓ Bajarildi" if qism[2] == "1" else "✗ Bajarilmadi"))
            return "Yozildi"
        if tur == "ve":  # mijozga eslatma faqat tugma bosilganda va mijoz botga ulangan bo'lsa (C-h)
            if not m or not m["tg_id"]:
                return "Mijoz botga ulanmagan"
            if not self._bir_marta(f"vada_mijozga:{v['id']}:{vaqt.bugun().isoformat()}"):
                return "Bugun allaqachon eslatilgan"
            await self.yoz(m["tg_id"], mijozga_matn(v, m))
            await self.yoz(chat_id, f"Mijozga eslatma yuborildi: {b.e(m['ism'])}")
            return "Yuborildi"
        return ""

    async def vadalar_royxati(self, o: dict, chat_id: int):
        bugun = vaqt.bugun().isoformat()
        f = {"masul_id": o["id"]} if o["rol"] == "xodim" else {}
        royxat = vadalar.royxat(faqat_ochiq=True, **f)
        buzilgan = [v for v in vadalar.royxat(dan=(vaqt.bugun() - timedelta(days=30)).isoformat(), gacha=bugun, **f)
                    if v["holat"] == "ochiq" and v["holat_h"] in ("buzildi", "qisman")]
        if not royxat and not buzilgan:
            return await self.yoz(chat_id, "Ochiq va'da yo'q.", menyu_=b.menyu(o))
        q = []
        bugungi = [v for v in royxat if v["muddat"] == bugun]
        if bugungi:
            q.append("<b>Bugun muddati:</b>")
            q += [f"• {b.e(vada_qisqa(v))}" for v in bugungi]
        if buzilgan:
            q.append("<b>Bajarilmagan:</b>")
            q += [f"• {b.e(vada_qisqa(v))} · {vaqt.sana_matn(v['muddat'], False)}" for v in buzilgan[:10]]
        keyin = sorted([v for v in royxat if v["muddat"] > bugun], key=lambda v: v["muddat"])
        if keyin:
            q.append("<b>Keyingi kunlar:</b>")
            q += [f"• {vaqt.sana_matn(v['muddat'], False)}: {b.e(vada_qisqa(v))}" for v in keyin[:10]]
        await self.yoz(chat_id, "\n".join(q), menyu_=b.menyu(o))

    # ---------- jadval: va'da eslatmalari, uxlab qolganlar, ta'minotchi muddati ----------

    async def mijoz_jadval(self):
        hozir = vaqt.hozir()
        bugun = hozir.date()
        b_iso = bugun.isoformat()
        if hozir.strftime("%H:%M") < str(baza.sozlama("ertalab_vaqti", "08:00")):
            return
        boss = odamlar.boshliq()
        # 1. Muddati bugun — mas'ulga (C-h)
        for v in vadalar.royxat(dan=b_iso, gacha=b_iso):
            if v["holat_h"] != "ochiq" or not self._bir_marta(f"vada:{v['id']}:kun"):
                continue
            kimga = _faol_yoki_boshliq(v["masul_id"], boss)
            if not kimga or (kimga == v["yozgan_id"] and v["yozilgan"][:10] == b_iso):
                continue  # bugun o'zi yozgan — eslatish shart emas
            m = mijozlar.mijoz(v["mijoz_id"])
            tug = []
            if v["tur"] == "boshqa" or v["kim"] == "biz":
                tug = [["Bajarildi", f"vb:{v['id']}:1"], ["Bajarilmadi", f"vb:{v['id']}:0"]]
            elif m and m["tg_id"]:
                tug = [["Mijozga eslatish", f"ve:{v['id']}"]]
            sarlavha = "Bugun va'da muddati" if v["kim"] == "mijoz" else "Bugun biz bergan va'da muddati"
            hisob.xabarnoma(kimga, "vada", f"{sarlavha}: {vada_qisqa(v)}" + (f"\n«{v['iqtibos'][:200]}»" if v["iqtibos"] else ""),
                            None, tug)
        # 2. Muddati o'tib bajarilmagan — mas'ul va boshliqqa bir marta (C-h)
        for v in vadalar.royxat(dan=(bugun - timedelta(days=7)).isoformat(), gacha=(bugun - timedelta(days=1)).isoformat()):
            if v["holat"] != "ochiq" or v["holat_h"] not in ("buzildi", "qisman"):
                continue
            if not self._bir_marta(f"vada:{v['id']}:buzildi"):
                continue
            q = f"Va'da bajarilmadi ({vaqt.sana_matn(v['muddat'], False)}): {vada_qisqa(v)}"
            if v["tur"] == "tolov" and v["kim"] == "mijoz" and v["qoplandi"]:
                q += f"\nTo'langani: {matn.pul(v['qoplandi'], v['valyuta'])}"
            tug = [["Bajarildi", f"vb:{v['id']}:1"], ["Bajarilmadi", f"vb:{v['id']}:0"]] if (
                v["tur"] == "boshqa" or v["kim"] == "biz") else []
            for kimga in {_faol_yoki_boshliq(v["masul_id"], boss), (boss or {}).get("id")} - {None}:
                hisob.xabarnoma(kimga, "vada", q, None, tug)
        # 3. Uxlab qolgan mijozlar — haftasiga bir marta (C5)
        hafta = f"{bugun.isocalendar()[0]}-{bugun.isocalendar()[1]}"
        if self._bir_marta(f"uxlagan:{hafta}"):
            uxlagan = mijozlar.uxlab_qolganlar()
            guruhlar: dict[int, list] = {}
            for m in uxlagan:
                for kimga in {_faol_yoki_boshliq(m.get("masul_id"), boss), (boss or {}).get("id")} - {None}:
                    guruhlar.setdefault(kimga, []).append(m)
            for kimga, royxat in guruhlar.items():
                q = ["Uzoq vaqtdan beri kelmagan mijozlar:"]
                for m in royxat[:10]:
                    q.append(f"• {m['ism']} — odatda {m['ortacha_kun']:g} kunda bir keladi, {m['otdi_kun']} kundan beri "
                             f"yo'q (o'rtacha xaridi {matn.pul(m['ortacha_summa'])})")
                hisob.xabarnoma(kimga, "uxlagan", "\n".join(q), None)
        # 4. Ta'minotchiga to'lov muddati yaqin — boshliqqa (P6)
        if boss:
            gacha = (bugun + timedelta(days=2)).isoformat()
            for r in baza.hammasi("SELECT id, dan, summa, valyuta, muddat FROM harakat WHERE tur='taminotchi_nasiya' "
                                  "AND holat='faol' AND muddat BETWEEN ? AND ?", b_iso, gacha):
                qarz = {v: -s for v, s in hisob.qoldiq(r["dan"]).items() if s < 0}
                if not qarz or not self._bir_marta(f"p6:{r['id']}"):
                    continue
                hisob.xabarnoma(boss["id"], "taminotchi",
                                f"Ta'minotchiga to'lov muddati {vaqt.sana_matn(r['muddat'], False)}: "
                                f"{hisob.hisob_nomi(r['dan'])} — qarzimiz "
                                + ", ".join(matn.pul(s, v) for v, s in qarz.items()), r["id"])
