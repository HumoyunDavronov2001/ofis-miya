"""Telegram bot — asosiy kiritish yo'li (K1–K11, T2, T5).

Oqim: xabar → asl holida saqlanadi (X1) → ovoz bo'lsa matnga → sun'iy intellekt taklif chiqaradi →
kartochka (yetishmagan maydonlar tugma bilan so'raladi) → «To'g'ri» → hisob.tasdiqla → ikkinchi tomonga so'rov.
Sun'iy intellektsiz ham ishlaydi: pastki menyudagi tugmalar bilan xuddi shu kartochka to'ldiriladi (K11).
"""
import asyncio
import html
import json
import logging
import os
import re
from datetime import timedelta

import httpx

from . import (ai, arxiv, baza, davomat, hisob, ishlar, maosh, matn, mijozlar, odamlar, ovoz, usullar, vadalar, vaqt,
               xotira, xulosa)
from .bot_buyurtma import BuyurtmaQismi
from .bot_ish import IshQismi, suhbat_qoy
from .bot_mijoz import MijozQismi, muddat_oqi
from .tgkit import KARTA_TUGMA, _karta, _karta_saqla, _sana_oqi, e, inline, menyu, menyu_sozlari, summa_oqi

log = logging.getLogger("miya.bot")

TUGMA_TUR = {"Kirim": "kirim", "Xarajat": "chiqim", "Avans": "avans", "Avans oldim": "avans", "Sotuv": "sotuv"}
YORDAM = ("Menga oddiy gapirib yoki yozib yuboring, masalan:\n"
          "• «Akmalga 500 ming avans berdim»\n• «Benzinga 320 ming ketdi» (chek rasmini ham yuborsangiz bo'ladi)\n"
          "• «Karimov 3 mln to'ladi»\n• «Dilshodga qancha qarzmiz?»\n\n"
          "Har yozuvni kartochka qilib ko'rsataman — «To'g'ri» bosmaguningizcha hisobga kirmaydi.\n"
          "Pul boshqa odamga o'tsa, u ham «oldim» deb tasdiqlaydi.")
KASSA_KERAK = {"kirim", "otkazma", "avans", "maosh_tolov", "qolga_berish", "qoldan_qaytarish", "egasi_oldi",
               "egasi_qoydi", "xodim_qarz", "qarz_qaytdi", "taminotchiga_tolov", "boshlangich_kassa"}
TAMINOTCHI_TUR = {"taminotchi_nasiya", "taminotchiga_tolov", "boshlangich_taminotchi"}
# Claude chaqirilmaydigan gaplar (token tejash): xushmuomalalik va aniq savollar
GAPLASHUV = {matn.norm(x) for x in ("rahmat", "raxmat", "rahmat katta", "ok", "okey", "xo'p", "xop", "mayli", "yaxshi",
                                    "tushunarli", "tushundim", "bo'ldi", "ha", "yo'q", "salom", "assalomu alaykum",
                                    "assalomu aleykum", "zo'r", "ajoyib", "+", "👍")}
SAVOL_SOZ = {matn.norm(x) for x in ("qancha", "qanchа", "nechta", "necha", "kim", "kimga", "kimdan", "kimning", "qachon",
                                   "qayerda", "qaysi", "nima", "nimaga", "nega", "qanday", "bormi", "qani", "qancha?")}


def savolmi(m: str) -> bool:
    """Aniq savol — «tushunish» bosqichisiz to'g'ridan-to'g'ri javobga (bitta Claude chaqiruvi tejaladi)."""
    t = matn.norm(m).split()
    if not t:
        return False
    sonli = any(ch.isdigit() for ch in m)
    return m.strip().endswith("?") or t[0] in SAVOL_SOZ or (not sonli and bool({"kancha", "nechta", "necha"} & set(t)))


def karta_yarat(o: dict, tur: str, yozuv: dict | None, xabar_id: int | None, chat_id: int) -> int:
    """AI yozuvi yoki qo'lda tanlangan tur → kartochka (maydonlar keyin to'ldiriladi)."""
    y = yozuv or {}
    d = {"tur": tur, "p": {}, "aytilgan": {}, "iqtibos": y.get("iqtibos") or "", "manba": "aytilgan" if yozuv else "tugma"}
    summa = float(y.get("summa") or 0)
    valyuta = y.get("valyuta") if y.get("valyuta") in ("UZS", "USD") else None
    if summa > 0:
        d["aytilgan"]["summa"] = summa
        d["aytilgan"]["valyuta"] = valyuta
        d["aytilgan"]["birlik_noaniq"] = bool(y.get("birlik_noaniq"))
    for maydon in ("odam", "mijoz", "kassa", "kassa2", "xarajat_turi", "muddat", "izoh"):
        if (y.get(maydon) or "").strip():
            d["aytilgan"][maydon] = y[maydon].strip()
    if float(y.get("tolandi") or 0) > 0:
        d["aytilgan"]["tolandi"] = float(y["tolandi"])
    if y.get("qoldan"):
        d["p"]["qoldan"] = True
    sana = (y.get("sana") or "").strip()[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", sana):
        d["p"]["sana"] = sana
    if y.get("izoh"):
        d["p"]["izoh"] = y["izoh"][:300]
    if y.get("iqtibos"):
        d["p"]["iqtibos"] = y["iqtibos"][:500]
    return baza.bajar("INSERT INTO karta(odam_id,chat_id,xabar_id,malumot,yaratilgan) VALUES(?,?,?,?,?)",
                      o["id"], chat_id, xabar_id, json.dumps(d, ensure_ascii=False), vaqt.iso())


def _odam_variantlari(o: dict) -> list[tuple[int, str]]:
    return [(x["id"], x["ism"]) for x in odamlar.faol_odamlar()]


def _mijoz_variantlari(tur: str) -> list[tuple[int, str]]:
    t = "taminotchi" if tur in TAMINOTCHI_TUR else "mijoz"
    return [(r["id"], r["ism"]) for r in baza.hammasi("SELECT id,ism FROM mijoz WHERE tur=? AND birlashdi IS NULL", t)]


def _keyingi_savol(k: dict, o: dict) -> dict | None:
    """Birinchi yetishmagan maydon: {"maydon", "matn", "tugmalar", "yozib"} yoki None (hammasi tayyor)."""
    d, p, a, tur = k["d"], k["d"]["p"], k["d"]["aytilgan"], k["d"]["tur"]
    kid = k["id"]
    # 1. summa
    if "summa" not in p:
        if "summa" in a and not a.get("birlik_noaniq"):
            v = a.get("valyuta") or None
            if v:
                p["valyuta"] = v
            p["summa_xom"] = a["summa"]
        elif "summa" in a and a.get("birlik_noaniq"):
            son = a["summa"]
            return {"maydon": "birlik", "matn": f"«{matn.guruh(int(son))}» — qaysi biri?", "tugmalar": [
                [f"{matn.guruh(int(son))} so'm", f"kb:{kid}:1"],
                [f"{matn.guruh(int(son * 1000))} so'm", f"kb:{kid}:1000"],
                [f"{matn.guruh(int(son * 1_000_000))} so'm", f"kb:{kid}:1000000"],
                [f"{matn.guruh(int(son))} $", f"kb:{kid}:usd"]]}
        else:
            return {"maydon": "summa", "matn": "Summani yozing (masalan: 500 000, 1,5 mln yoki 200 $):", "yozib": True}
    # 2. xodim
    if tur in hisob.ODAM_KERAK or (tur == "chiqim" and p.get("qoldan")):
        if "odam_id" not in p:
            ism = a.get("odam", "")
            if not ism and o["rol"] in ("xodim", "menejer") and tur in ("avans", "maosh_tolov", "qolga_berish",
                                                                      "qoldan_qaytarish", "mijozdan_qolga", "chiqim"):
                p["odam_id"] = o["id"]  # «oldim», «o'zimdagi puldan» — yozgan odamning o'zi
            elif ism.lower() in ("men", "o'zim", "ozim", "мен"):
                p["odam_id"] = o["id"]
            else:
                mos = matn.mosla(ism, _odam_variantlari(o)) if ism else []
                bitta = matn.yagona(mos)
                if bitta:
                    p["odam_id"] = bitta[0]
                else:
                    royxat = mos[:6] if mos else [(i, n, 0) for i, n in _odam_variantlari(o)[:12]]
                    return {"maydon": "odam", "matn": (f"«{e(ism)}» — qaysi xodim?" if ism else "Qaysi xodim?"),
                            "tugmalar": [[n, f"ko:{kid}:{i}"] for i, n, _ in royxat]}
    # 3. mijoz / ta'minotchi
    mijoz_kerak = tur in hisob.MIJOZ_KERAK
    kirim_mijoz = tur == "kirim" and (a.get("mijoz") or d.get("manba") == "tugma")
    if (mijoz_kerak or kirim_mijoz) and "mijoz_id" not in p and not p.get("mijozsiz"):
        ism = a.get("mijoz", "")
        mos = matn.mosla(ism, _mijoz_variantlari(tur)) if ism else []
        bitta = matn.yagona(mos)
        if bitta:
            p["mijoz_id"] = bitta[0]
        else:
            nom = "ta'minotchi" if tur in TAMINOTCHI_TUR else "mijoz"
            tug = [[n, f"km:{kid}:{i}"] for i, n, _ in mos[:5]]
            if ism:
                tug.append([f"Yangi {nom}: {ism[:40]}", f"km:{kid}:yangi"])
            if tur == "kirim":
                tug.append(["Mijozsiz kirim", f"km:{kid}:yoq"])
            return {"maydon": "mijoz", "matn": (f"«{e(ism)}» — qaysi {nom}?" if ism else f"Qaysi {nom}? Ismini yozing:"),
                    "tugmalar": tug, "yozib": True}
    # 4. kassa
    tolandi_bor = tur == "sotuv" and a.get("tolandi")
    kassa_kerak = tur in KASSA_KERAK or (tur == "chiqim" and not p.get("qoldan")) or tolandi_bor
    if kassa_kerak and "kassa_id" not in p:
        kassalar = hisob.kassalar()
        nom = a.get("kassa", "")
        if nom:
            mos = matn.yagona(matn.mosla(nom, [(x["id"], x["nom"]) for x in kassalar], 0.6))
            if mos:
                p["kassa_id"] = mos[0]
        if "kassa_id" not in p:
            ozi = [x for x in kassalar if x["masul_id"] == o["id"]]
            v = p.get("valyuta")
            ozi_v = [x for x in ozi if not v or x["valyuta"] == v]
            if o.get("kassa_id") and any(x["id"] == o["kassa_id"] and (not v or x["valyuta"] == v) for x in kassalar):
                p["kassa_id"] = o["kassa_id"]
            elif len(ozi_v) == 1:
                p["kassa_id"] = ozi_v[0]["id"]
            elif len(kassalar) == 1:
                p["kassa_id"] = kassalar[0]["id"]
            else:
                return {"maydon": "kassa", "matn": "Qaysi kassa?",
                        "tugmalar": [[f"{x['nom']} ({x['valyuta']})", f"kk:{kid}:{x['id']}"] for x in kassalar]}
    if tur == "otkazma" and "kassa2_id" not in p:
        kassalar = [x for x in hisob.kassalar() if x["id"] != p.get("kassa_id")]
        nom = a.get("kassa2", "")
        mos = matn.yagona(matn.mosla(nom, [(x["id"], x["nom"]) for x in kassalar], 0.6)) if nom else None
        if mos:
            p["kassa2_id"] = mos[0]
        else:
            return {"maydon": "kassa2", "matn": "Qaysi kassaga?",
                    "tugmalar": [[f"{x['nom']} ({x['valyuta']})", f"k2:{kid}:{x['id']}"] for x in kassalar]}
    # summa yakuni: valyuta kassadan
    if "summa" not in p:
        v = p.get("valyuta")
        if not v:
            kas = hisob.kassa(p.get("kassa_id")) if p.get("kassa_id") else None
            v = kas["valyuta"] if kas else "UZS"
        p["valyuta"] = v
        p["summa"] = matn.minor(p.pop("summa_xom"), v)
        if a.get("tolandi"):
            p["tolandi"] = matn.minor(a["tolandi"], v)
    if tur == "chiqim" and "xarajat_turi" not in p:
        p["xarajat_turi"] = a.get("xarajat_turi") or "Boshqa"
    if tur in ("sotuv", "taminotchi_nasiya") and a.get("muddat") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", a["muddat"][:10]):
        p["muddat"] = a["muddat"][:10]
    return None


def _mos_kutayotgan(o: dict, y: dict) -> tuple[dict, str] | None:
    """Odam aytgan pul boshqa odam yozgan va undan tasdiq kutayotgan yozuvga mosmi (o'sha summa, 3 kun ichida)."""
    if not y.get("summa") or y.get("birlik_noaniq"):
        return None
    guruh = {"avans": ("avans", "maosh_tolov"), "maosh_tolov": ("avans", "maosh_tolov")}.get(y["tur"], (y["tur"],))
    dan = vaqt.iso(vaqt.hozir() - timedelta(days=3))
    for h in baza.hammasi(
            "SELECT * FROM harakat WHERE holat='faol' AND faollashgan>=? AND tur IN (%s) AND "
            "((oluvchi_id=? AND oluvchi_holat='kutilmoqda') OR (beruvchi_id=? AND beruvchi_holat='kutilmoqda')) "
            "ORDER BY id DESC" % ",".join("?" * len(guruh)), dan, *guruh, o["id"], o["id"]):
        if matn.minor(y["summa"], h["valyuta"]) != h["summa"]:
            continue
        if y.get("valyuta") in ("UZS", "USD") and y["valyuta"] != h["valyuta"]:
            continue
        tomon = "o" if h["oluvchi_id"] == o["id"] and h["oluvchi_holat"] == "kutilmoqda" else "b"
        return h, tomon
    return None


def karta_matni(k: dict, o: dict) -> str:
    d, p, tur = k["d"], k["d"]["p"], k["d"]["tur"]
    nom = hisob.SHABLON[tur][0]
    qism = [f"<b>{e(nom)}</b>"]
    if p.get("odam_id"):
        qism[0] += f" · {e(odamlar.odam(p['odam_id'])['ism'])}"
    if p.get("mijoz_id"):
        m = baza.bir("SELECT ism FROM mijoz WHERE id=?", p["mijoz_id"])
        qism[0] += f" · {e(m['ism'] if m else '')}"
    v = p.get("valyuta", "UZS")
    qism.append(f"<b>{matn.pul(p['summa'], v)}</b> — {matn.pul_soz(p['summa'], v)}")
    if tur == "sotuv":
        tol = p.get("tolandi") or 0
        nasiya = p["summa"] - tol
        qism.append(f"Hozir to'landi: {matn.pul(tol, v)} · nasiya: {matn.pul(nasiya, v)}"
                    + (f" · muddat {vaqt.sana_matn(p['muddat'], False)}" if p.get("muddat") else ""))
        if nasiya > 0 and p.get("mijoz_id"):  # nasiya berishda mijozning va'da tarixi (C4)
            m = baza.bir("SELECT * FROM mijoz WHERE id=?", p["mijoz_id"])
            qarz = {vl: sm for vl, sm in hisob.qoldiq(f"mijoz:{p['mijoz_id']}").items() if sm > 0}
            if m and mijozlar.korishi_mumkin(o, m):
                qism.append(("Avvalgi qarzi: " + ", ".join(matn.pul(sm, vl) for vl, sm in qarz.items()) if qarz
                             else "Avvalgi qarzi yo'q") + f" · {vadalar.ishonch(p['mijoz_id'])['matn']}")
            if p.get("muddat"):
                qism.append(f"Nasiyani {vaqt.sana_matn(p['muddat'], False)} gacha to'lash va'dasi ham yoziladi.")
    if tur == "taminotchi_nasiya" and p.get("muddat"):
        qism.append(f"To'lash muddati: {vaqt.sana_matn(p['muddat'], False)} (2 kun oldin eslataman)")
    if tur == "chiqim":
        qism.append(f"Xarajat turi: {e(p.get('xarajat_turi'))}" + (" · o'z qo'lidagi puldan" if p.get("qoldan") else ""))
    if p.get("kassa_id"):
        qism.append(f"Kassa: {e(hisob.kassa(p['kassa_id'])['nom'])}")
    if p.get("kassa2_id"):
        qism.append(f"Qaysi kassaga: {e(hisob.kassa(p['kassa2_id'])['nom'])}")
    qism.append(f"Sana: {vaqt.sana_matn(p.get('sana') or vaqt.bugun())}")
    if p.get("izoh"):
        qism.append(f"Izoh: {e(p['izoh'])}")
    if d.get("iqtibos"):
        qism.append(f"<i>«{e(d['iqtibos'][:200])}»</i>")
    try:
        dan, ga = hisob.hisoblarni_tuz(tur, p)
        if hisob.SHABLON[tur][3]:
            kim = []
            for kal, soz in ((dan, "berdim"), (ga, "oldim")):
                m_id = hisob.masul(kal)
                if m_id and m_id != o["id"]:
                    kim.append(f"{odamlar.odam(m_id)['ism'].split()[0]} «{soz}»")
            if kim:
                qism.append("Tasdiqlashi kerak: " + ", ".join(kim) + ".")
    except hisob.HisobXato:
        pass
    return "\n".join(qism)


class Bot(IshQismi, MijozQismi, BuyurtmaQismi):
    def __init__(self, token: str, url: str | None = None):
        self.token = token
        self.url = (url or os.environ.get("MIYA_TG_URL") or "https://api.telegram.org").rstrip("/")
        self.mijoz = httpx.AsyncClient(timeout=40)
        self.offset = 0
        self.ishlayapti = False
        self.qulflar: dict[int, asyncio.Lock] = {}
        self.vazifalar: list[asyncio.Task] = []
        self.username = None
        self._urinish: dict[int, int] = {}
        self.oxirgi_xato: str | None = None  # Sozlamalarda ko'rinadi (409 — token boshqa joyda ham ishlayapti)

    # ---------- Telegram API ----------

    async def api(self, metod: str, **p):
        p = {k: v for k, v in p.items() if v is not None}
        fayl = p.pop("_fayl", None)  # (maydon, yo'l) — ovoz yoki hujjat yuborish
        for k in ("reply_markup",):
            if k in p and not isinstance(p[k], str):
                p[k] = json.dumps(p[k], ensure_ascii=False)
        if fayl:
            with open(fayl[1], "rb") as fh:
                r = await self.mijoz.post(f"{self.url}/bot{self.token}/{metod}", data=p,
                                          files={fayl[0]: (os.path.basename(fayl[1]), fh.read())})
        else:
            r = await self.mijoz.post(f"{self.url}/bot{self.token}/{metod}", data=p)
        d = r.json()
        if not d.get("ok"):
            raise TgXato(d.get("error_code", r.status_code), d.get("description", ""))
        return d["result"]

    async def yoz(self, chat_id: int, matn_: str, tugmalar=None, menyu_=None, javob_id=None):
        rm = inline(tugmalar) if tugmalar else menyu_
        return await self.api("sendMessage", chat_id=chat_id, text=matn_[:4000], parse_mode="HTML",
                              reply_markup=rm, reply_to_message_id=javob_id, disable_web_page_preview=True)

    async def tahrir(self, chat_id: int, msg_id: int, matn_: str, tugmalar=None):
        try:
            await self.api("editMessageText", chat_id=chat_id, message_id=msg_id, text=matn_[:4000], parse_mode="HTML",
                           reply_markup=inline(tugmalar) if tugmalar else {"inline_keyboard": []})
        except TgXato as x:
            if "not modified" not in x.tavsif:
                raise

    async def fayl_yukla(self, file_id: str, nom: str) -> str:
        f = await self.api("getFile", file_id=file_id)
        sana = vaqt.bugun()
        papka = os.path.join(os.path.dirname(os.path.abspath(baza.yol())), "fayllar", f"{sana:%Y}", f"{sana:%m}")
        os.makedirs(papka, exist_ok=True)
        yol = os.path.join(papka, nom)
        r = await self.mijoz.get(f"{self.url}/file/bot{self.token}/{f['file_path']}")
        r.raise_for_status()
        with open(yol, "wb") as fh:
            fh.write(r.content)
        return yol

    # ---------- asosiy halqa ----------

    async def boshla(self):
        men = await self.api("getMe")
        self.username = men.get("username")
        baza.sozlama_qoy("bot_nomi", self.username)
        await self.api("deleteWebhook")  # avval webhook qo'yilgan token bilan getUpdates 409 beradi
        await self.api("setMyCommands", commands=json.dumps([
            {"command": "hisobim", "description": "Mening hisobim"},
            {"command": "kutayotgan", "description": "Tasdiq kutayotganlar"},
            {"command": "kassa", "description": "Kassa va sanoq"},
            {"command": "yordam", "description": "Qanday ishlatiladi"}]))
        self.ishlayapti = True
        self.vazifalar = [asyncio.create_task(self._tinglash()), asyncio.create_task(self._xabarnoma_halqa()),
                          asyncio.create_task(self._jadval_halqa())]

    async def toxta(self):
        self.ishlayapti = False
        for t in self.vazifalar:
            t.cancel()
        await self.mijoz.aclose()

    async def _tinglash(self):
        while self.ishlayapti:
            try:
                yangilar = await self.api("getUpdates", offset=self.offset, timeout=25,
                                          allowed_updates=json.dumps(["message", "callback_query"]))
            except TgXato as x:
                self.oxirgi_xato = ("Bu token boshqa dasturda ham ishlayapti — bitta bot faqat bitta joyda ishlaydi"
                                    if x.kod == 409 else "Token bekor qilingan yoki noto'g'ri" if x.kod in (401, 404)
                                    else f"Telegram xatosi: {x.tavsif[:120]}")
                log.warning("getUpdates: %s", x)
                await asyncio.sleep(10 if x.kod in (401, 404, 409) else 3)
                continue
            except Exception as x:
                self.oxirgi_xato = "Telegram'ga ulanib bo'lmadi — internet"
                log.warning("getUpdates: %s", x)
                await asyncio.sleep(3)
                continue
            self.oxirgi_xato = None
            for u in yangilar:
                self.offset = u["update_id"] + 1
                asyncio.create_task(self._ishla_qulf(u))

    async def _ishla_qulf(self, u: dict):
        chat = (u.get("message") or (u.get("callback_query") or {}).get("message") or {}).get("chat", {}).get("id", 0)
        qulf = self.qulflar.setdefault(chat, asyncio.Lock())
        async with qulf:
            try:
                await self.ishla(u)
            except Exception:
                log.exception("yangilanishni ishlashda xato")
                try:
                    if chat:
                        await self.yoz(chat, "Xatolik yuz berdi. Qaytadan urinib ko'ring.")
                except Exception:
                    pass

    async def ishla(self, u: dict):
        if "callback_query" in u:
            return await self.tugma(u["callback_query"])
        x = u.get("message")
        if not x or "from" not in x:
            return
        chat = x["chat"]
        if chat["type"] in ("group", "supergroup"):
            return await self.guruh(x)
        if chat["type"] != "private":
            return
        tg_id = x["from"]["id"]
        matn_ = (x.get("text") or "").strip()
        o = odamlar.odam_tg(tg_id)
        if not o and matn_.startswith("/start m"):  # mijoz havolasi — xodim kodi tasodifan «m» bilan boshlansa ham adashmasin
            kod_ = matn_.split(maxsplit=1)[1]
            if not baza.bir("SELECT 1 FROM taklif WHERE kod=?", kod_):
                return await self.mijoz_ulash(x, kod_[1:])
        if not o and baza.bir("SELECT 1 FROM mijoz WHERE tg_id=?", tg_id):
            return await self.mijoz_xabari(x)
        if matn_.startswith("/start"):
            kod = matn_.split(maxsplit=1)[1] if " " in matn_ else ""
            if kod and not o:
                o = odamlar.taklif_ishlat(kod, tg_id, x["from"].get("username"))
                if o:
                    return await self.yoz(chat["id"], f"Xush kelibsiz, {e(o['ism'])}!\n\n{YORDAM}", menyu_=menyu(o))
            if not o:
                return await self.yoz(chat["id"], "Bu ishxonaning yopiq boti. Kirish uchun rahbaringiz yuborgan "
                                                  "havolani bosing.")
            return await self.yoz(chat["id"], f"Salom, {e(o['ism'])}!\n\n{YORDAM}", menyu_=menyu(o))
        if not o:
            return await self.yoz(chat["id"], "Bu ishxonaning yopiq boti. Kirish uchun rahbaringiz yuborgan havolani "
                                              "bosing.")
        if o["holat"] == "ketmoqda" and matn_ not in ("Hisobim", "/hisobim"):
            return await self.hisobim(o, chat["id"])
        if x.get("location"):
            return await self.joylashuv(o, x)
        # suhbat holati (yozib javob kutilmoqda)
        s = baza.bir("SELECT * FROM suhbat WHERE odam_id=?", o["id"])
        if matn_ == "Bekor qilish":
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
            return await self.yoz(chat["id"], "Bekor qilindi.", menyu_=menyu(o))
        if s and s["holat"] == "dalil_rasm" and x.get("photo"):
            return await self.dalil_rasm(o, x, json.loads(s["malumot"])["ish"])
        if s and s["holat"] and matn_ and not matn_.startswith("/") and matn_ not in menyu_sozlari(o):
            sd = json.loads(s["malumot"] or "{}")
            if await self.ish_suhbat(o, chat["id"], s["holat"], sd, matn_) or \
                    await self.mijoz_suhbat(o, chat["id"], s["holat"], sd, matn_):
                if baza.qiymat("SELECT vaqt FROM suhbat WHERE odam_id=?", o["id"]) == s["vaqt"]:
                    baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
                return
            return await self.suhbat_javob(o, chat["id"], s, matn_)
        if s and s["holat"] not in ("dalil_rasm", "dalil_joylashuv"):
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        # menyu va buyruqlar
        if matn_ in ("Hisobim", "/hisobim"):
            return await self.hisobim(o, chat["id"])
        if matn_ in ("Kutayotganlar", "/kutayotgan"):
            return await self.kutayotganlar(o, chat["id"])
        if matn_ in ("Kassa", "/kassa"):
            return await self.kassa_menyu(o, chat["id"])
        if matn_ == "Maosh":
            return await self.maosh_menyu(o, chat["id"])
        if matn_ in ("Yordam", "/yordam", "/help"):
            return await self.yoz(chat["id"], YORDAM, menyu_=menyu(o))
        if matn_ in ("Ishlarim", "/ishlarim"):
            return await self.ishlarim(o, chat["id"])
        if matn_ in ("Ishlar", "/ishlar"):
            return await self.ishlar_menyu(o, chat["id"])
        if matn_ in ("Va'dalar", "/vadalar"):
            return await self.vadalar_royxati(o, chat["id"])
        kichik = matn_.lower()
        if kichik.startswith(("usul:", "ish usuli:")) and o["rol"] in ("boshliq", "menejer"):
            return await self.usul_saqla(o, x, matn_.split(":", 1)[1])
        if kichik.startswith(("qidir:", "/qidir")):
            return await self.qidir(o, chat["id"], matn_.split(":", 1)[1] if ":" in matn_ else matn_[6:])
        if matn_.lower().strip(" .!") in ("keldim", "ketdim", "ishga keldim", "ishdan ketdim"):
            return await self.davomat_yoz(o, chat["id"])
        if matn_ in TUGMA_TUR:
            kid = karta_yarat(o, TUGMA_TUR[matn_], None, None, chat["id"])
            return await self.karta_davom(kid, o)
        # xabar: matn, ovoz, rasm, hujjat
        await self.xabar_ishla(o, x)

    # ---------- xabarni ishlash ----------

    async def xabar_saqla(self, o: dict, x: dict) -> tuple[int, str, dict]:
        tur, fayl, davom, uzatilgan = "matn", None, None, None
        if x.get("forward_origin") or x.get("forward_from") or x.get("forward_sender_name"):
            fo = x.get("forward_origin") or {}
            uzatilgan = (fo.get("sender_user", {}).get("first_name") or fo.get("sender_user_name")
                         or x.get("forward_sender_name") or (x.get("forward_from") or {}).get("first_name") or "noma'lum")
        qism = {}
        if x.get("voice") or x.get("audio"):
            tur = "ovoz"
            qism = x.get("voice") or x.get("audio")
            davom = qism.get("duration")
        elif x.get("photo"):
            tur = "rasm"
            qism = x["photo"][-1]
        elif x.get("document"):
            tur = "fayl"
            qism = x["document"]
        xid = baza.bajar("INSERT INTO xabar(odam_id,chat_id,msg_id,tur,matn,davomiylik,uzatilgan,vaqt) VALUES(?,?,?,?,?,?,?,?)",
                         o["id"], x["chat"]["id"], x["message_id"], tur, x.get("text") or x.get("caption"), davom,
                         uzatilgan, vaqt.iso())
        if qism.get("file_id"):
            ext = {"ovoz": ".ogg", "rasm": ".jpg"}.get(tur) or os.path.splitext(qism.get("file_name") or "")[1] or ".bin"
            try:
                fayl = await self.fayl_yukla(qism["file_id"], f"{xid}{ext}")
                baza.bajar("UPDATE xabar SET fayl=? WHERE id=?", fayl, xid)
                if tur == "rasm":
                    baza.bajar("INSERT INTO ilova(xabar_id,fayl,tur,xesh,vaqt) VALUES(?,?,?,?,?)", xid, fayl, "rasm",
                               qism.get("file_unique_id"), vaqt.iso())
            except Exception:
                log.exception("fayl yuklanmadi")
        return xid, tur, {"fayl": fayl, "uzatilgan": uzatilgan}

    async def xabar_ishla(self, o: dict, x: dict, xid: int | None = None):
        chat_id = x["chat"]["id"]
        if xid is None:
            xid, tur, q = await self.xabar_saqla(o, x)
        xb = baza.bir("SELECT * FROM xabar WHERE id=?", xid)
        tur = xb["tur"]
        matn_ = xb["matn"] or ""
        if tur == "fayl" and not matn_:
            return await self.yoz(chat_id, "Fayl saqlandi.")
        try:
            await self.api("sendChatAction", chat_id=chat_id, action="typing")
        except Exception:
            pass
        if tur == "ovoz":
            if not ovoz.yoqilganmi():
                return await self.yoz(chat_id, "Ovoz saqlandi, lekin ovozni matnga aylantirish hali sozlanmagan. "
                                               "Pastdagi tugmalar bilan kiriting.", menyu_=menyu(o))
            try:
                stt, sozlar, _ = await ovoz.matnga(xb["fayl"], xb["davomiylik"])
            except ovoz.OvozXato as ox:
                self._navbatga(xid, str(ox))
                return await self.yoz(chat_id, f"Ovoz saqlandi. {e(ox)} — keyinroq qayta urinaman.")
            baza.bajar("UPDATE xabar SET stt_matn=?, stt_sozlar=? WHERE id=?", stt, json.dumps(sozlar, ensure_ascii=False), xid)
            if not stt:
                return await self.yoz(chat_id, "Ovozda gap eshitilmadi. Qaytadan ayting yoki yozing.")
            matn_ = stt
            await self.yoz(chat_id, f"<i>Eshitildi:</i> {e(stt)}")
        if not ai.yoqilganmi():
            return await self.yoz(chat_id, "Sun'iy intellekt hali yoqilmagan — pastdagi tugmalar bilan kiriting.",
                                  menyu_=menyu(o))
        if tur != "rasm" and matn.norm(matn_) in GAPLASHUV:
            baza.bajar("UPDATE xabar SET holat='ishlandi' WHERE id=?", xid)
            return await self.yoz(chat_id, "Xo'p 👍", menyu_=menyu(o))
        if tur != "rasm" and savolmi(matn_):
            baza.bajar("UPDATE xabar SET holat='ishlandi' WHERE id=?", xid)
            return await self.savol(o, chat_id, matn_)
        rasm = None
        if tur == "rasm" and xb["fayl"]:
            with open(xb["fayl"], "rb") as fh:
                rasm = fh.read()
        try:
            ochiq = [i for i in ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)]
            natija = await ai.tushun(matn_, o, rasm=rasm, uzatilgan=xb["uzatilgan"], ochiq_ishlar=ochiq)
        except ai.AiXato as ax:
            self._navbatga(xid, str(ax))
            return await self.yoz(chat_id, f"Xabar saqlandi. {e(ax)} — navbatga qo'ydim, ishlagach yozaman. "
                                           "Shoshilinch bo'lsa — tugmalar bilan kiriting.", menyu_=menyu(o))
        baza.bajar("UPDATE xabar SET holat='ishlandi' WHERE id=?", xid)
        eslab = xotira.saqla_natija(natija.get("xotira"), o, xid)  # R5: uchrashuv, eslatma, ma'lumot — darhol
        if eslab:
            await self.yoz(chat_id, "\n".join(e(x["matn"]) for x in eslab))
        ish_qismi = any(natija.get(k) for k in ("ishlar", "bajarildi", "davomat")) or (natija.get("muammo") or "").strip()
        mijoz_qismi = any(natija.get(k) for k in ("vadalar", "mijoz_eslatmalar", "buyurtmalar"))
        if natija["savol"] and not natija["yozuvlar"] and not ish_qismi and not mijoz_qismi and not eslab:
            return await self.savol(o, chat_id, natija["savol"])
        yozuvlar = [y for y in natija["yozuvlar"] if y.get("tur") in hisob.SHABLON]
        if ish_qismi:
            await self.ish_natija(o, chat_id, natija, xid)
        if mijoz_qismi:
            await self.mijoz_natija(o, chat_id, natija, xid)
            await self.buyurtma_natija(o, chat_id, natija, xid)
        if not yozuvlar and (ish_qismi or mijoz_qismi or eslab):
            return
        if not yozuvlar:
            sabab = natija.get("tushunilmadi") or "pul harakati topilmadi"
            if tur == "rasm":
                baza.bajar("UPDATE ilova SET tur='hujjat' WHERE xabar_id=?", xid)
                return await self.yoz(chat_id, "Rasm saqlandi.")
            return await self.yoz(chat_id, f"Tushunmadim: {e(sabab)}.\nBoshqacha ayting yoki tugmalar bilan kiriting.",
                                  menyu_=menyu(o))
        for y in yozuvlar[:5]:
            if not hisob.yozishi_mumkin(o, y["tur"]):
                await self.yoz(chat_id, f"«{e(hisob.SHABLON[y['tur']][0])}» yozuvini faqat boshliq kirita oladi.")
                continue
            kid = karta_yarat(o, y["tur"], y, xid, chat_id)
            mos = _mos_kutayotgan(o, y)
            if mos:  # bu pulni boshqa odam allaqachon yozgan — yangi yozuv emas, tasdiq (K5, K10)
                h, tomon = mos
                yozgan = odamlar.odam(h["yozgan_id"])
                soz = "Ha, oldim" if tomon == "o" else "Ha, berdim"
                await self.yoz(chat_id, f"Bu pulni {e(yozgan['ism'] if yozgan else '')} allaqachon yozgan:\n"
                                        f"{e(hisob.qisqa_tavsif(h))} · {vaqt.sana_matn(h['voqea_sana'], False)}\n"
                                        "Shumi?",
                               [[[soz, f"t:{h['id']}:{tomon}:1"], ["Yo'q, bu boshqa", f"kd:{kid}"]]])
                continue
            await self.karta_davom(kid, o)

    def _navbatga(self, xid: int, sabab: str):
        baza.bajar("INSERT INTO navbat(xabar_id,sabab,vaqt) VALUES(?,?,?)", xid, sabab, vaqt.iso())
        baza.bajar("UPDATE xabar SET holat='navbatda' WHERE id=?", xid)

    async def karta_davom(self, kid: int, o: dict, msg_id: int | None = None):
        k = _karta(kid)
        if not k or k["holat"] != "ochiq":
            return
        savol = _keyingi_savol(k, o)
        _karta_saqla(kid, k["d"])
        chat = k["chat_id"]
        if savol:
            tug = [[t[0], t[1]] for t in savol.get("tugmalar", [])] + [["Bekor qilish", f"k:{kid}:bekor"]]
            if savol.get("yozib"):
                baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?) ON CONFLICT(odam_id) DO "
                           "UPDATE SET holat=excluded.holat, malumot=excluded.malumot, vaqt=excluded.vaqt",
                           o["id"], f"karta_{savol['maydon']}", json.dumps({"karta": kid}), vaqt.iso())
            sarlavha = f"<b>{e(hisob.SHABLON[k['d']['tur']][0])}</b>\n"
            if msg_id:
                return await self.tahrir(chat, msg_id, sarlavha + savol["matn"], tug)
            r = await self.yoz(chat, sarlavha + savol["matn"], tug)
            return r
        try:
            m = karta_matni(k, o)
        except Exception as x:
            log.exception("karta matni")
            return await self.yoz(chat, f"Kartochkani tuzib bo'lmadi: {e(x)}")
        if msg_id:
            await self.tahrir(chat, msg_id, m, KARTA_TUGMA(kid))
            baza.bajar("UPDATE karta SET msg_id=? WHERE id=?", msg_id, kid)
        else:
            r = await self.yoz(chat, m, KARTA_TUGMA(kid))
            baza.bajar("UPDATE karta SET msg_id=? WHERE id=?", r["message_id"], kid)

    async def suhbat_javob(self, o: dict, chat_id: int, s: dict, matn_: str):
        d = json.loads(s["malumot"] or "{}")
        holat = s["holat"]
        baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        if holat.startswith("karta_"):
            kid = d["karta"]
            k = _karta(kid)
            if not k or k["holat"] != "ochiq":
                return
            maydon = holat[6:]
            a, p = k["d"]["aytilgan"], k["d"]["p"]
            if maydon == "summa":
                son, v, noaniq = summa_oqi(matn_)
                if not son or son <= 0:
                    baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?)", o["id"], holat,
                               s["malumot"], vaqt.iso())
                    return await self.yoz(chat_id, "Summani raqam bilan yozing, masalan: 500 000")
                a["summa"], a["valyuta"], a["birlik_noaniq"] = son, v, noaniq
                p.pop("summa", None)
                p.pop("summa_xom", None)
            elif maydon in ("mijoz",):
                a["mijoz"] = matn_[:80]
            elif maydon == "sana":
                sana = _sana_oqi(matn_)
                if not sana:
                    return await self.yoz(chat_id, "Sanani tushunmadim. Masalan: 7.10 yoki kecha")
                p["sana"] = sana
            elif maydon == "izoh":
                p["izoh"] = matn_[:300]
            elif maydon == "muddat":
                sana = muddat_oqi(matn_)
                if not sana:
                    return await self.yoz(chat_id, "Sanani tushunmadim (o'tgan kun bo'lmasin). Masalan: 15.10 yoki juma")
                p["muddat"] = a["muddat"] = sana
            _karta_saqla(kid, k["d"])
            return await self.karta_davom(kid, o)
        if holat == "sanoq":
            son, v, _ = summa_oqi(matn_)
            if son is None:
                baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?)", o["id"], holat,
                           s["malumot"], vaqt.iso())
                return await self.yoz(chat_id, "Kassadagi pulni raqam bilan yozing, masalan: 4 350 000")
            kas = hisob.kassa(d["kassa"])
            try:
                r = hisob.kassa_sanoq(d["kassa"], matn.minor(son, kas["valyuta"]), o["id"])
            except hisob.HisobXato as hx:
                return await self.yoz(chat_id, e(hx))
            if r["farq"] and r["sanalgan"] != r["agar_tasdiqlansa"]:
                baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?) ON CONFLICT(odam_id) DO "
                           "UPDATE SET holat=excluded.holat, malumot=excluded.malumot, vaqt=excluded.vaqt",
                           o["id"], "sanoq_izoh", json.dumps({"kassa": kas["id"]}), vaqt.iso())
            return await self.yoz(chat_id, _sanoq_matni(r), menyu_=menyu(o))
        if holat == "sanoq_izoh":
            baza.bajar("UPDATE kassa_sanoq SET izoh=? WHERE kassa_id=? AND sana=?", matn_[:300], d["kassa"],
                       vaqt.bugun().isoformat())
            b = odamlar.boshliq()
            if b and b["id"] != o["id"]:
                hisob.xabarnoma(b["id"], "malumot", f"Kassa farqi izohi ({o['ism']}): {matn_[:300]}")
            return await self.yoz(chat_id, "Izoh yozildi.", menyu_=menyu(o))

    # ---------- tugmalar ----------

    async def tugma(self, cq: dict):
        data = cq.get("data") or ""
        tg_id = cq["from"]["id"]
        o = odamlar.odam_tg(tg_id)
        msg = cq.get("message") or {}
        chat_id, msg_id = msg.get("chat", {}).get("id"), msg.get("message_id")
        javob = ""
        try:
            qism = data.split(":")
            tur = qism[0]
            if tur == "mb":  # mijozning javobi — u xodim emas
                javob = await self.ish_tugma(None, tur, qism, chat_id, msg_id, tg_id)
                return
            if not o:
                javob = "Ruxsat yo'q"
                return
            if tur in ("ik", "ib", "id", "iq", "dv"):
                javob = await self.ish_tugma(o, tur, qism, chat_id, msg_id, tg_id)
                return
            if tur in ("me", "vb", "ve"):
                javob = await self.mijoz_tugma(o, tur, qism, chat_id, msg_id)
                return
            if tur in ("xb", "xk"):  # xotira eslatmasi: bajarildi / bekor
                x = xotira.bir(int(qism[1]))
                if x and (o["id"] in (x["yozgan_id"], x["kimga_id"]) or odamlar.boshliqmi(o)):
                    xotira.holat_qoy(x["id"], "bajarildi" if tur == "xb" else "bekor", o["id"])
                    await self.tahrir(chat_id, msg_id, f"{'✅ Bajarildi' if tur == 'xb' else 'Bekor qilindi'}: {e(x['matn'])}")
                    javob = "Belgilandi"
                return
            if tur == "ub":
                u = baza.bir("SELECT * FROM usul WHERE id=?", int(qism[1]))
                if u and u["faol"] and (u["yozgan_id"] == o["id"] or odamlar.boshliqmi(o)):
                    usullar.ochir(u["id"], o["id"])
                    await self.tahrir(chat_id, msg_id, f"Ish usuli bekor qilindi: {e(u['sarlavha'])}")
                    javob = "Bekor qilindi"
                return
            if tur == "kd":
                k = _karta(int(qism[1]))
                if k and k["odam_id"] == o["id"] and k["holat"] == "ochiq":
                    await self.tahrir(chat_id, msg_id, "Yangi yozuv sifatida davom etamiz.")
                    await self.karta_davom(k["id"], o)
                return
            if tur in ("k", "kb", "ko", "km", "kk", "k2", "kt", "kf", "ij", "dl", "kv", "vs", "kby"):
                k = _karta(int(qism[1]))
                if not k or k["odam_id"] != o["id"]:
                    javob = "Bu kartochka sizniki emas"
                    return
                if k["holat"] != "ochiq":
                    javob = "Bu kartochka yopilgan"
                    return
                qiymat = qism[2] if len(qism) > 2 else ""
                if k["d"]["tur"] == "ish":
                    javob = await self.ish_karta_tugma(k, o, tur, qiymat, chat_id, msg_id)
                elif k["d"]["tur"] == "ishyangi":
                    javob = await self._ishyangi(k, o, qiymat, chat_id, msg_id)
                elif k["d"]["tur"] in ("vada", "eslatma"):
                    javob = await self.vada_karta_tugma(k, o, tur, qiymat, chat_id, msg_id)
                elif k["d"]["tur"] == "buyurtma":
                    javob = await self.buyurtma_karta_tugma(k, o, tur, qiymat, chat_id, msg_id)
                else:
                    javob = await self._karta_tugma(k, o, tur, qiymat, chat_id, msg_id)
            elif tur == "t":
                hid, tomon, ha = int(qism[1]), {"o": "oluvchi", "b": "beruvchi"}[qism[2]], qism[3] == "1"
                xabarlar = hisob.tomon_tasdiq(hid, o["id"], tomon, ha)
                h = hisob.harakat(hid)
                await self.tahrir(chat_id, msg_id, f"{e(hisob.qisqa_tavsif(h))}\n"
                                                   + ("✓ Tasdiqladingiz" if ha else "✗ Rad etdingiz — boshliqqa yuborildi"))
                javob = "Yozildi"
            elif tur == "n":
                hisob.nizo_hal(int(qism[1]), o["id"], qism[2] == "1")
                h = hisob.harakat(int(qism[1]))
                await self.tahrir(chat_id, msg_id, f"{e(hisob.qisqa_tavsif(h))}\n"
                                                   + ("✓ Berilgan deb hisoblandi" if qism[2] == "1" else "✗ Bekor qilindi"))
                javob = "Hal qilindi"
            elif tur == "r":
                r = hisob.ruxsat(int(qism[1]), o["id"], qism[2] == "1")
                h = hisob.harakat(int(qism[1]))
                await self.tahrir(chat_id, msg_id, f"{e(hisob.qisqa_tavsif(h))}\n"
                                                   + ("✓ Ruxsat berildi" if qism[2] == "1" else "✗ Rad etildi"))
                javob = "Yozildi"
            elif tur == "s":
                kas = hisob.kassa(int(qism[1]))
                baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?) ON CONFLICT(odam_id) DO "
                           "UPDATE SET holat=excluded.holat, malumot=excluded.malumot, vaqt=excluded.vaqt",
                           o["id"], "sanoq", json.dumps({"kassa": kas["id"]}), vaqt.iso())
                await self.yoz(chat_id, f"<b>{e(kas['nom'])}</b>: kassada hozir qancha pul bor? Sanab, raqam bilan yozing.")
            elif tur == "si":
                baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?) ON CONFLICT(odam_id) DO "
                           "UPDATE SET holat=excluded.holat, malumot=excluded.malumot, vaqt=excluded.vaqt",
                           o["id"], "sanoq_izoh", json.dumps({"kassa": int(qism[1])}), vaqt.iso())
                await self.yoz(chat_id, "Farq sababini yozing:")
        except hisob.HisobXato as hx:
            javob = str(hx)[:180]
            if chat_id:
                await self.yoz(chat_id, e(hx))
        finally:
            try:
                await self.api("answerCallbackQuery", callback_query_id=cq["id"], text=javob[:190] or None)
            except Exception:
                pass

    async def _karta_tugma(self, k: dict, o: dict, tur: str, qiymat: str, chat_id: int, msg_id: int) -> str:
        kid, d = k["id"], k["d"]
        a, p = d["aytilgan"], d["p"]
        if tur == "kb":
            son = a["summa"]
            if qiymat == "usd":
                a["valyuta"] = "USD"
            else:
                a["summa"] = son * int(qiymat)
                a["valyuta"] = a.get("valyuta") or "UZS"
            a["birlik_noaniq"] = False
        elif tur == "ko":
            p["odam_id"] = int(qiymat)
        elif tur == "km":
            if qiymat == "yangi":
                t = "taminotchi" if d["tur"] in TAMINOTCHI_TUR else "mijoz"
                ism = a.get("mijoz") or "Yangi mijoz"
                p["mijoz_id"] = baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES(?,?,?)", ism[:1].upper() + ism[1:],
                                           t, vaqt.iso())
                baza.jurnal(o["id"], "mijoz_yarat", f"mijoz:{p['mijoz_id']}", None, ism)
            elif qiymat == "yoq":
                p["mijozsiz"] = True
            else:
                p["mijoz_id"] = int(qiymat)
            baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
        elif tur == "kk":
            p["kassa_id"] = int(qiymat)
            kas = hisob.kassa(p["kassa_id"])
            if "summa" in p and p.get("valyuta") != kas["valyuta"]:
                return "Kassa valyutasi summaga mos emas"
        elif tur == "k2":
            p["kassa2_id"] = int(qiymat)
        elif tur == "kf":  # tuzatish: qaysi maydon
            if qiymat in ("summa",):
                for x in ("summa", "summa_xom", "valyuta", "tolandi"):
                    p.pop(x, None)
                a.pop("summa", None)
                a.pop("tolandi", None)
            elif qiymat == "odam":
                p.pop("odam_id", None)
                a.pop("odam", None)
            elif qiymat == "mijoz":
                p.pop("mijoz_id", None)
                p.pop("mijozsiz", None)
                a.pop("mijoz", None)
            elif qiymat == "kassa":
                p.pop("kassa_id", None)
                a.pop("kassa", None)
            elif qiymat in ("sana", "izoh", "muddat"):
                _karta_saqla(kid, d)
                baza.bajar("INSERT INTO suhbat(odam_id,holat,malumot,vaqt) VALUES(?,?,?,?) ON CONFLICT(odam_id) DO "
                           "UPDATE SET holat=excluded.holat, malumot=excluded.malumot, vaqt=excluded.vaqt",
                           o["id"], f"karta_{qiymat}", json.dumps({"karta": kid}), vaqt.iso())
                await self.yoz(chat_id, {"sana": "Sanani yozing (masalan: 7.10, kecha):", "izoh": "Izohni yozing:",
                                         "muddat": "Qarz qachon to'lanadi? (masalan: 15.10, juma)"}[qiymat])
                return ""
        elif tur == "k":
            if qiymat == "bekor":
                baza.bajar("UPDATE karta SET holat='bekor' WHERE id=?", kid)
                baza.bajar("DELETE FROM suhbat WHERE odam_id=?", o["id"])
                await self.tahrir(chat_id, msg_id, "Bekor qilindi.")
                return "Bekor qilindi"
            if qiymat == "tuz":
                tug = [[["Summa", f"kf:{kid}:summa"], ["Sana", f"kf:{kid}:sana"]]]
                ikkinchi = []
                if p.get("odam_id"):
                    ikkinchi.append(["Xodim", f"kf:{kid}:odam"])
                if p.get("mijoz_id") or p.get("mijozsiz"):
                    ikkinchi.append(["Mijoz", f"kf:{kid}:mijoz"])
                if p.get("kassa_id"):
                    ikkinchi.append(["Kassa", f"kf:{kid}:kassa"])
                if ikkinchi:
                    tug.append(ikkinchi)
                if d["tur"] in ("sotuv", "taminotchi_nasiya"):
                    tug.append([["Qarz muddati", f"kf:{kid}:muddat"]])
                tug.append([["Izoh", f"kf:{kid}:izoh"], ["Orqaga", f"kt:{kid}:orqa"]])
                await self.tahrir(chat_id, msg_id, karta_matni(k, o) + "\n\n<b>Nimasi noto'g'ri?</b>", tug)
                return ""
            if qiymat == "ok":
                return await self._karta_tasdiq(k, o, chat_id, msg_id)
        elif tur == "kt":
            if qiymat == "orqa":
                await self.tahrir(chat_id, msg_id, karta_matni(k, o), KARTA_TUGMA(kid))
                return ""
            hid = k["harakat_id"]
            boglangan = baza.hammasi("SELECT id FROM harakat WHERE bog_id=? AND id!=? AND holat='taklif'", hid, hid)
            if qiymat == "0":  # takror emas — baribir yozilsin
                r = hisob.faollashtir(hid, o["id"])
                for b in boglangan:
                    if r["holat"] == "faol":
                        r["xabarlar"] += hisob.faollashtir(b["id"], o["id"])["xabarlar"]
                return await self._natija_korsat(k, o, r, chat_id, msg_id)
            for b in boglangan:
                baza.bajar("UPDATE harakat SET holat='bekor', bekor_sabab='takror sotuvning to''lovi' WHERE id=?", b["id"])
            xabarlar = hisob.birlashtir(hid, int(qiymat), o["id"])
            baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", kid)
            await self.tahrir(chat_id, msg_id, "Bu yozuv avval kiritilgan ekan — ikkalasi bitta qilindi"
                                               + (", sizning tasdig'ingiz ham qo'shildi." if xabarlar is not None else "."))
            return "Birlashtirildi"
        _karta_saqla(kid, d)
        await self.karta_davom(kid, o, msg_id=msg_id)
        return ""

    async def _karta_tasdiq(self, k: dict, o: dict, chat_id: int, msg_id: int) -> str:
        d, p = k["d"], dict(k["d"]["p"])
        p.pop("mijozsiz", None)
        with baza.tranz():
            if d["tur"] == "sotuv":
                sid, kid2 = hisob.sotuv_tuz(p, o["id"], k["xabar_id"])
                hid = sid
            else:
                hid = hisob.taklif(d["tur"], p, o["id"], k["xabar_id"], manba=d.get("manba", "aytilgan"))
                kid2 = None
            if k["xabar_id"]:
                baza.bajar("UPDATE ilova SET harakat_id=? WHERE xabar_id=? AND harakat_id IS NULL", hid, k["xabar_id"])
            baza.bajar("UPDATE karta SET harakat_id=? WHERE id=?", hid, k["id"])
        k["harakat_id"] = hid
        r = hisob.tasdiqla(hid, o["id"])
        if kid2 and r["holat"] == "faol":
            r2 = hisob.tasdiqla(kid2, o["id"])
            if r2["holat"] == "takror":
                hisob.faollashtir(kid2, o["id"])
            r["xabarlar"] += r2.get("xabarlar", [])
        return await self._natija_korsat(k, o, r, chat_id, msg_id)

    async def _natija_korsat(self, k: dict, o: dict, r: dict, chat_id: int, msg_id: int) -> str:
        hid = k["harakat_id"]
        if r["holat"] == "takror":
            t = r["takrorlar"][0]
            yozgan = odamlar.odam(t["yozgan_id"])
            await self.tahrir(chat_id, msg_id,
                              karta_matni(k, o) + f"\n\n<b>Shunga o'xshash yozuv bor:</b> {e(hisob.qisqa_tavsif(t))}"
                              f" · {vaqt.sana_matn(t['voqea_sana'], False)} · yozgan: {e(yozgan['ism'] if yozgan else '')}\n"
                              "Bu o'sha yozuvmi?",
                              [[["Ha, o'sha", f"kt:{k['id']}:{t['id']}"], ["Yo'q, boshqa", f"kt:{k['id']}:0"]]])
            return "Takror bo'lishi mumkin"
        baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", k["id"])
        h = hisob.harakat(hid)
        if r["holat"] == "ruxsat_kutilmoqda":
            await self.tahrir(chat_id, msg_id, karta_matni(k, o) + f"\n\n⏳ Boshliq ruxsatini kutmoqda: "
                                                                  f"{e(h['qoida_buzilish'])}")
            return "Ruxsat so'raldi"
        izoh = "✓ Yozildi"
        kutish = []
        for tomon in ("beruvchi", "oluvchi"):
            if h[f"{tomon}_holat"] == "kutilmoqda":
                kim = odamlar.odam(h[f"{tomon}_id"])
                if kim:
                    kutish.append(kim["ism"].split()[0])
        if kutish:
            izoh += f" · {', '.join(kutish)} tasdig'i kutilmoqda"
        if h["kech"]:
            izoh += " · kech kiritilgani uchun bugungi kunga yozildi"
        await self.tahrir(chat_id, msg_id, karta_matni(k, o) + f"\n\n{izoh}")
        return "Yozildi"

    async def _ishyangi(self, k: dict, o: dict, qiymat: str, chat_id: int, msg_id: int) -> str:
        """Ro'yxatda yo'q ish — xodim o'zi aytgan, narxsiz (I-f)."""
        baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", k["id"])
        if qiymat != "ok":
            await self.tahrir(chat_id, msg_id, "Mayli, yozilmadi.")
            return ""
        iid, _ = ishlar.ish_yarat(k["d"]["nom"], [(o["id"], 1)], o["id"], xabar_id=k["xabar_id"])
        await self.tahrir(chat_id, msg_id, f"Yangi ish yozildi: #{iid} {e(k['d']['nom'])}")
        await self.bajarildi_bajar(o, chat_id, iid, k["d"].get("izoh"))
        return ""

    async def mijoz_ulash(self, x: dict, kod: str):
        """Mijoz botga havola orqali ulanadi — faqat o'z ishiga «bajarildimi?» javobi uchun (I6)."""
        chat_id = x["chat"]["id"]
        t = baza.bir("SELECT * FROM mijoz_taklif WHERE kod=?", kod)
        if not t or t["ishlatilgan"]:
            return await self.yoz(chat_id, "Havola eskirgan. Ishxonadan yangisini so'rang.")
        with baza.tranz():
            baza.bajar("UPDATE mijoz_taklif SET ishlatilgan=? WHERE kod=?", vaqt.iso(), kod)
            baza.bajar("UPDATE mijoz SET tg_id=? WHERE id=?", x["from"]["id"], t["mijoz_id"])
            baza.jurnal(None, "mijoz_ulandi", f"mijoz:{t['mijoz_id']}")
        m = baza.bir("SELECT ism FROM mijoz WHERE id=?", t["mijoz_id"])
        await self.yoz(chat_id, f"Assalomu alaykum, {e(m['ism'])}! Endi bu yerga ishxonadan bajarilgan ishlar bo'yicha "
                                "qisqa so'rovlar keladi.")

    async def mijoz_xabari(self, x: dict):
        m = baza.bir("SELECT * FROM mijoz WHERE tg_id=?", x["from"]["id"])
        matn_ = (x.get("text") or x.get("caption") or "").strip()
        boss = odamlar.boshliq()
        if boss and matn_:
            hisob.xabarnoma(boss["id"], "malumot", f"Mijoz {m['ism']} botga yozdi: {matn_[:800]}")
        await self.yoz(x["chat"]["id"], "Rahmat, xabaringiz ishxonaga yetkazildi.")

    # ---------- savol, hisob, kassa ----------

    async def savol(self, o: dict, chat_id: int, savol: str):
        try:
            r = await ai.sora(savol, o)
        except ai.AiXato as ax:
            return await self.yoz(chat_id, f"Hozir javob bera olmayman: {e(ax)}. «Hisobim» tugmasi ishlaydi.")
        await self.yoz(chat_id, e(r["javob"]))
        for nom, d in r.get("manbalar", []):  # X6: asl ovozning o'zi ham — «0:14 dan eshiting»
            if nom == "xabar_qidir" and d.get("xabarlar"):
                x = d["xabarlar"][0]
                if x.get("soniya") is not None:
                    await self.ovoz_yubor(chat_id, x["xabar_id"], x["soniya"], o)
                break

    async def ovoz_yubor(self, chat_id: int, xabar_id: int, soniya: float | None, o: dict):
        xb = baza.bir("SELECT * FROM xabar WHERE id=?", xabar_id)
        if not xb or not xb["fayl"] or not os.path.exists(xb["fayl"]) or not arxiv.korishi_mumkin(o, xabar_id):
            return
        vaqt_ = f"{int(soniya) // 60}:{int(soniya) % 60:02d}" if soniya else "boshidan"
        kim = odamlar.odam(xb["odam_id"])
        try:
            await self.api("sendVoice" if xb["tur"] == "ovoz" else "sendDocument", chat_id=chat_id,
                           caption=f"Asl xabar: {kim['ism'] if kim else ''}, {vaqt.sana_matn(xb['vaqt'][:10], False)} "
                                   f"{xb['vaqt'][11:16]} — {vaqt_} dan eshiting",
                           _fayl=("voice" if xb["tur"] == "ovoz" else "document", xb["fayl"]))
        except Exception:
            log.exception("ovoz yuborilmadi")

    async def qidir(self, o: dict, chat_id: int, sorov: str):
        """Sun'iy intellektsiz qidiruv (S9): «Qidir: Karimov narx»."""
        topilgan = arxiv.qidir(sorov.strip(), o, limit=5)
        if not topilgan:
            return await self.yoz(chat_id, "Bunday xabar topilmadi.", menyu_=menyu(o))
        q = ["<b>Topilgan xabarlar</b>"]
        for x in topilgan:
            q.append(f"• {vaqt.sana_matn(x['vaqt'][:10], False)} {x['vaqt'][11:16]}, {e(x['kim'])}: «{e(x['parcha'])}»")
        await self.yoz(chat_id, "\n".join(q), menyu_=menyu(o))
        ovozli = next((x for x in topilgan if x["tur"] == "ovoz" and x["fayl"]), None)
        if ovozli:
            await self.ovoz_yubor(chat_id, ovozli["id"], ovozli["soniya"], o)

    async def usul_saqla(self, o: dict, x: dict, matn_: str):
        """O5: boshliq yoki menejer «Usul: ...» — o'zi saqlanadi, [Bekor qilish] bilan."""
        chat_id = x["chat"]["id"]
        xid, _, _ = await self.xabar_saqla(o, x)
        qatorlar = matn_.strip().split("\n", 1)
        sarlavha, tana = (qatorlar[0], qatorlar[1]) if len(qatorlar) > 1 else ("", qatorlar[0])
        try:
            uid = usullar.qosh(sarlavha, tana, o["id"], xid)
        except usullar.UsulXato as ux:
            return await self.yoz(chat_id, e(ux))
        baza.bajar("UPDATE xabar SET holat='ishlandi' WHERE id=?", xid)
        u = baza.bir("SELECT sarlavha FROM usul WHERE id=?", uid)
        await self.yoz(chat_id, f"📘 Ish usuli saqlandi: <b>{e(u['sarlavha'])}</b>\nXodimlar «qanday qilamiz?» deb so'rasa, "
                                "shundan javob beraman.", [["Bekor qilish", f"ub:{uid}"]])

    async def hisobim(self, o: dict, chat_id: int):
        v = maosh.varaq(o["id"])
        val = v["valyuta"]
        q = [f"<b>{vaqt.oy_matn(v['oy'])} · Mening hisobim</b>"]
        if v["otgan"]:
            q.append(f"O'tgan oydan: {matn.pul(v['otgan'], val)}")
        q.append(f"Hisoblandi: <b>{matn.pul(v['hisoblandi'], val)}</b>")
        for x in v["qatorlar"]:
            if x["summa"] > 0:
                q.append(f"  + {e(x['nom'])} — {matn.pul(x['summa'], val)}")
        q.append(f"Oldim: <b>{matn.pul(v['olindi'], val)}</b>")
        for x in v["qatorlar"]:
            if x["summa"] < 0:
                q.append(f"  − {e(x['nom'])}" + (f" · {vaqt.sana_matn(x['sana'], False)}" if x["sana"] else "")
                         + f" — {matn.pul(-x['summa'], val)}")
        if v["kutilmoqda_jami"]:
            q.append(f"Tasdiq kutmoqda: {matn.pul(v['kutilmoqda_jami'], val)} (hisobga hali kirmagan)")
        q.append(f"\n<b>Qolgani: {matn.pul(v['qolgani'], val)}</b>")
        qol = hisob.qoldiq_bir(f"qol:{o['id']}")
        if qol:
            q.append(f"Qo'lingizdagi ishxona puli: {matn.pul(qol)}")
        tug = None
        domen = baza.sozlama("domen")
        if domen and str(domen).startswith("https://"):
            tug = [["Oynada ochish", f"{domen.rstrip('/')}/ilova", "web"]]
        await self.yoz(chat_id, "\n".join(q), tugmalar=tug, menyu_=None if tug else menyu(o))

    async def kutayotganlar(self, o: dict, chat_id: int):
        qatorlar = baza.hammasi(
            "SELECT * FROM harakat WHERE holat IN ('faol','nizo') AND ((beruvchi_id=? AND beruvchi_holat='kutilmoqda') OR "
            "(oluvchi_id=? AND oluvchi_holat='kutilmoqda')) ORDER BY id", o["id"], o["id"])
        if odamlar.boshliqmi(o):
            qatorlar += baza.hammasi("SELECT * FROM harakat WHERE holat IN ('nizo','ruxsat_kutilmoqda') ORDER BY id")
        if not qatorlar:
            return await self.yoz(chat_id, "Sizdan kutilayotgan tasdiq yo'q.", menyu_=menyu(o))
        korildi = set()
        for h in qatorlar[:15]:
            if h["id"] in korildi:
                continue
            korildi.add(h["id"])
            if h["holat"] == "ruxsat_kutilmoqda":
                await self.yoz(chat_id, f"Ruxsat kerak: {e(hisob.qisqa_tavsif(h))}\nSabab: {e(h['qoida_buzilish'])}",
                               [[["Ruxsat", f"r:{h['id']}:1"], ["Rad", f"r:{h['id']}:0"]]])
            elif h["holat"] == "nizo" and odamlar.boshliqmi(o):
                await self.yoz(chat_id, f"Nizo: {e(hisob.qisqa_tavsif(h))}",
                               [[["Berilgan deb hisoblash", f"n:{h['id']}:1"], ["Bekor qilish", f"n:{h['id']}:0"]]])
            else:
                tomon = "o" if h["oluvchi_id"] == o["id"] and h["oluvchi_holat"] == "kutilmoqda" else "b"
                soz = ("Ha, oldim", "Yo'q, olmadim") if tomon == "o" else ("Ha, berdim", "Yo'q")
                await self.yoz(chat_id, f"{e(hisob.qisqa_tavsif(h))} · {vaqt.sana_matn(h['voqea_sana'], False)}",
                               [[[soz[0], f"t:{h['id']}:{tomon}:1"], [soz[1], f"t:{h['id']}:{tomon}:0"]]])

    async def kassa_menyu(self, o: dict, chat_id: int):
        royxat = [k for k in hisob.kassa_holati() if odamlar.hisob_korishi_mumkin(o, f"kassa:{k['id']}")]
        if not royxat:
            return await self.yoz(chat_id, "Sizga biriktirilgan kassa yo'q.", menyu_=menyu(o))
        q = ["<b>Kassalar</b>"]
        for k in royxat:
            q.append(f"{e(k['nom'])}: <b>{matn.pul(k['qoldiq'], k['valyuta'])}</b>")
            kut = k["kutilayotgan"]
            if kut["chiqim_jami"] or kut["kirim_jami"]:
                q.append(f"  tasdiq kutmoqda: chiqim {matn.pul(kut['chiqim_jami'], k['valyuta'])}, "
                         f"kirim {matn.pul(kut['kirim_jami'], k['valyuta'])}")
        await self.yoz(chat_id, "\n".join(q), [[f"Sanash: {k['nom']}", f"s:{k['id']}"] for k in royxat])

    async def maosh_menyu(self, o: dict, chat_id: int):
        if not (odamlar.boshliqmi(o) or odamlar.mumkin(o, "maosh_tolash")):
            return await self.hisobim(o, chat_id)
        q = ["<b>Maosh — to'lash kerak</b>"]
        for x in maosh.tolash_kerak():
            q.append(f"{e(x['ism'])}: {matn.pul(x['qolgani'], x['valyuta'])}")
        if odamlar.boshliqmi(o):
            b = maosh.bashorat()
            q.append(f"\nMaosh kuni {vaqt.sana_matn(b['kun'])}: kerak {matn.pul(b['kerak'])}, qo'ldagi pul "
                     f"{matn.pul(b['aniq_pul'])}" + (f" — <b>{matn.pul(b['yetmaydi'])} yetmaydi</b>" if b["yetmaydi"] else ""))
        await self.yoz(chat_id, "\n".join(q), menyu_=menyu(o))

    async def guruh(self, x: dict):
        """Ish guruhi (K1): bot admin bo'lsa xabarlarni ko'radi; kartochka yozgan odamga shaxsan boradi."""
        o = odamlar.odam_tg(x["from"]["id"])
        if not o or o["holat"] != "faol":
            return
        matn_ = x.get("text") or x.get("caption") or ""
        ovozmi = bool(x.get("voice"))
        if ovozmi and not baza.sozlama("guruh_ovoz", False):
            return
        if not ovozmi and not re.search(r"\d|ming|mln|million|so'm|dollar|\$", matn_.lower()):
            return
        if not o["tg_id"]:
            return
        xid, tur, _ = await self.xabar_saqla(o, x)
        fake = dict(x)
        fake["chat"] = {"id": o["tg_id"], "type": "private"}
        await self.xabar_ishla(o, fake, xid)

    # ---------- fon vazifalari ----------

    async def xabarnoma_yubor(self):
        """Navbatdagi xabarlarni yuboradi (bot o'chiq paytda yig'ilganlari ham)."""
        for n in baza.hammasi("SELECT * FROM xabarnoma WHERE holat='yangi' ORDER BY id LIMIT 20"):
            o = odamlar.odam(n["odam_id"])
            if not o or not o["tg_id"] or o["holat"] == "ketgan":
                baza.bajar("UPDATE xabarnoma SET holat='tg_yoq' WHERE id=?", n["id"])
                continue
            try:
                tug = json.loads(n["tugmalar"] or "[]")
                r = await self.yoz(o["tg_id"], e(n["matn"]), [tug] if tug and not isinstance(tug[0][0], list) else tug)
                baza.bajar("UPDATE xabarnoma SET holat='yuborildi', tg_msg_id=? WHERE id=?", r["message_id"], n["id"])
            except TgXato as tx:
                self._urinish[n["id"]] = self._urinish.get(n["id"], 0) + 1
                if tx.kod in (400, 403) or self._urinish[n["id"]] >= 5:
                    baza.bajar("UPDATE xabarnoma SET holat='xato', xato=? WHERE id=?", tx.tavsif[:200], n["id"])

    async def _xabarnoma_halqa(self):
        while self.ishlayapti:
            try:
                await self.xabarnoma_yubor()
            except Exception:
                log.exception("xabarnoma halqasi")
            await asyncio.sleep(2)

    async def _jadval_halqa(self):
        while self.ishlayapti:
            try:
                await self.jadval()
            except Exception:
                log.exception("jadval")
            await asyncio.sleep(60)

    def _bir_marta(self, kalit: str) -> bool:
        try:
            baza.bajar("INSERT INTO yuborildi(kalit,vaqt) VALUES(?,?)", kalit, vaqt.iso())
            return True
        except Exception:
            return False

    async def jadval(self):
        hozir = vaqt.hozir()
        bugun = hozir.date().isoformat()
        # 1. Kechki kassa sanog'i (P4)
        soat = str(baza.sozlama("kassa_sanoq_vaqti", "19:00"))
        if hozir.strftime("%H:%M") >= soat:
            for k in hisob.kassalar():
                masul = odamlar.odam(k["masul_id"]) if k["masul_id"] else None
                if k["tur"] == "chontak" or not masul or masul["holat"] != "faol":
                    continue
                if baza.bir("SELECT 1 FROM kassa_sanoq WHERE kassa_id=? AND sana=?", k["id"], bugun):
                    continue
                if self._bir_marta(f"sanoq:{k['id']}:{bugun}"):
                    hisob.xabarnoma(k["masul_id"], "sanoq", f"{k['nom']}: kun yakuni — kassani sanang.", None,
                                    [["Sanash", f"s:{k['id']}"]])
        # 2. Tasdiq eslatmalari (K5): 2 soat — eslatma, 24 soat — boshliqqa
        for h in baza.hammasi("SELECT * FROM harakat WHERE holat='faol' AND (beruvchi_holat='kutilmoqda' OR "
                              "oluvchi_holat='kutilmoqda') AND faollashgan IS NOT NULL"):
            otdi = (hozir - vaqt.hozir().fromisoformat(h["faollashgan"])).total_seconds() / 3600
            for tomon, t in (("beruvchi", "b"), ("oluvchi", "o")):
                if h[f"{tomon}_holat"] != "kutilmoqda":
                    continue
                if otdi >= 2 and self._bir_marta(f"esl2:{h['id']}:{t}"):
                    soz = ("Ha, oldim", "Yo'q, olmadim") if t == "o" else ("Ha, berdim", "Yo'q")
                    hisob.xabarnoma(h[f"{tomon}_id"], "eslatma", f"Eslatma — tasdiq kutilmoqda: {hisob.qisqa_tavsif(h)}",
                                    h["id"], [[soz[0], f"t:{h['id']}:{t}:1"], [soz[1], f"t:{h['id']}:{t}:0"]])
                if otdi >= 24 and self._bir_marta(f"esl24:{h['id']}:{t}"):
                    b = odamlar.boshliq()
                    kim = odamlar.odam(h[f"{tomon}_id"])
                    if b:
                        hisob.xabarnoma(b["id"], "malumot", f"1 kundan beri tasdiqlanmagan: {hisob.qisqa_tavsif(h)} — "
                                                            f"{kim['ism'] if kim else '?'} javob bermadi.", h["id"])
        # 3. Maosh kuni ogohlantirishi (M6)
        b = maosh.bashorat()
        if 0 <= b["qoldi_kun"] <= 5 and b["yetmaydi"] > 0 and hozir.hour >= 9:
            boss = odamlar.boshliq()
            if boss and self._bir_marta(f"maosh:{b['kun']}"):
                hisob.xabarnoma(boss["id"], "maosh", f"Maosh kuni {vaqt.sana_matn(b['kun'])}: kerak {matn.pul(b['kerak'])}, "
                                                     f"qo'ldagi pul {matn.pul(b['aniq_pul'])} — {matn.pul(b['yetmaydi'])} "
                                                     f"yetmaydi. Mijozlar qarzi: «Kutayotganlar» va panelda.")
        # 4. Ishlar: ertalabki ro'yxat, kechki savol, avto qabul (I3, I4, M4)
        await self.ish_jadval()
        await self.mijoz_jadval()
        await self.xulosa_jadval()
        # 5. Navbatdagi xabarlar (S9)
        if ai.yoqilganmi():
            for n in baza.hammasi("SELECT * FROM navbat WHERE holat='kutmoqda' AND urinish<5 ORDER BY id LIMIT 3"):
                baza.bajar("UPDATE navbat SET urinish=urinish+1 WHERE id=?", n["id"])
                xb = baza.bir("SELECT * FROM xabar WHERE id=?", n["xabar_id"])
                o = odamlar.odam(xb["odam_id"]) if xb else None
                if not o or not o["tg_id"]:
                    baza.bajar("UPDATE navbat SET holat='bekor' WHERE id=?", n["id"])
                    continue
                baza.bajar("UPDATE navbat SET holat='ishlanmoqda' WHERE id=?", n["id"])
                fake = {"chat": {"id": o["tg_id"], "type": "private"}, "message_id": xb["msg_id"], "from": {"id": o["tg_id"]}}
                try:
                    await self.xabar_ishla(o, fake, xb["id"])
                    if baza.qiymat("SELECT holat FROM xabar WHERE id=?", xb["id"]) == "ishlandi":
                        baza.bajar("UPDATE navbat SET holat='bajarildi' WHERE id=?", n["id"])
                    else:
                        baza.bajar("UPDATE navbat SET holat='bekor' WHERE id=?", n["id"])
                except Exception:
                    baza.bajar("UPDATE navbat SET holat='kutmoqda' WHERE id=?", n["id"])


    async def xulosa_jadval(self):
        """Ertalabki xulosa (ish kunlari) va dushanba — haftalik (S6, S8)."""
        hozir = vaqt.hozir()
        bugun = hozir.date()
        if hozir.strftime("%H:%M") < str(baza.sozlama("brifing_vaqti", "08:30")):
            return
        boss = odamlar.boshliq()
        if not boss:
            return
        if self._bir_marta(f"eskirt:{bugun.isoformat()}"):
            xulosa.kartalarni_eskirt()
        if not ishlar.dam_olishmi(bugun) and self._bir_marta(f"brifing:{bugun.isoformat()}"):
            x = await xulosa.yasash("kun")
            hisob.xabarnoma(boss["id"], "xulosa", x["matn"])
        hafta = f"{bugun.isocalendar()[0]}-{bugun.isocalendar()[1]}"
        if bugun.weekday() == 0 and self._bir_marta(f"haftalik:{hafta}"):
            x = await xulosa.yasash("hafta")
            hisob.xabarnoma(boss["id"], "xulosa", x["matn"])


class TgXato(Exception):
    def __init__(self, kod, tavsif):
        super().__init__(f"{kod}: {tavsif}")
        self.kod = kod
        self.tavsif = tavsif or ""


def _sanoq_matni(r: dict) -> str:
    k = r["kassa"]
    v = k["valyuta"]
    q = [f"<b>{e(k['nom'])}</b> — sanoq yozildi", f"Sanaldi: {matn.pul(r['sanalgan'], v)}",
         f"Dastur bo'yicha: {matn.pul(r['kutilgan'], v)}"]
    if r["farq"] == 0:
        q.append("✓ Mos keldi.")
    else:
        q.append(f"<b>Farq: {matn.pul(r['farq'], v)}</b>")
        kut = r["kutilayotgan"]
        if kut["chiqim"] or kut["kirim"]:
            q.append(f"Tasdiq kutayotgan yozuvlar tasdiqlansa: {matn.pul(r['agar_tasdiqlansa'], v)}")
            for h in (kut["chiqim"] + kut["kirim"])[:6]:
                q.append(f"  • {e(hisob.qisqa_tavsif(h))}")
        if r["sanalgan"] != r["agar_tasdiqlansa"]:
            q.append("Farq sababini yozing — boshliqqa boradi.")
    return "\n".join(q)
