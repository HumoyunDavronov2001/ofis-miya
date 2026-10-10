"""Panel va Telegram oynasi (E, T2, T3, T4): FastAPI; bot shu jarayon ichida ishlaydi."""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import (ai, arxiv, baza, bot as bot_m, buyurtma, davomat, eksport, hisob, ishlar, kurs, maosh, matn, mijozlar, odamlar, ovoz,
               hisobot, izlash, panel_taklif, qoida, signallar, topshirish, usullar, vadalar, vaqt, xotira, xulosa, yuklash,
               zaxira)

log = logging.getLogger("miya.veb")
ILDIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEB = os.path.join(ILDIZ, "veb")
SHRIFT = os.path.join(ILDIZ, "dizayn", "shrift")
BOT: bot_m.Bot | None = None
_urinish: dict[str, list[float]] = {}

STANDART_XARAJAT = ["Ijara", "Yoqilg'i", "Material", "Kommunal", "Transport", "Oziq-ovqat", "Aloqa", "Ta'mirlash",
                    "Soliq va to'lovlar", "Boshqa"]


def bot_token() -> str | None:
    t = os.environ.get("MIYA_BOT_TOKEN")
    if t:
        return t
    s = baza.sozlama("maxfiy_bot")
    if s:
        try:
            return odamlar.ochish(s)
        except Exception:
            return None
    return None


async def bot_yoq() -> str | None:
    """Bot tokeni bo'lsa ishga tushiradi. Xato matnini qaytaradi."""
    global BOT
    if BOT:
        await BOT.toxta()
        BOT = None
    t = bot_token()
    if not t:
        return "Bot tokeni kiritilmagan"
    b = bot_m.Bot(t)
    try:
        await b.boshla()
    except Exception as x:
        await b.mijoz.aclose()
        log.warning("bot ishga tushmadi: %s", x)
        return f"Bot ishga tushmadi: {x}"
    BOT = b
    return None


async def _zaxira_halqa():
    while True:
        try:
            if zaxira.kerakmi():
                natija = await asyncio.to_thread(zaxira.ol)
                if not natija.get("butun") or not natija.get("mos"):
                    b = odamlar.boshliq()
                    if b:
                        hisob.xabarnoma(b["id"], "zaxira", "Kechki zaxira nusxasini tekshirishda muammo chiqdi — "
                                                          "panel → Sozlamalar.")
        except Exception:
            log.exception("zaxira")
        await asyncio.sleep(600)


async def _eslatma_halqa():
    """R6–R7: vaqti kelgan xotira eslatmalari → xabarnoma (bot yoqilmagan bo'lsa ham web chatga tushadi)."""
    while True:
        try:
            xotira.eslat()
        except Exception:
            log.exception("eslatma")
        await asyncio.sleep(30)


@asynccontextmanager
async def hayot(app: FastAPI):
    await bot_yoq()
    zx = asyncio.create_task(_zaxira_halqa())
    es = asyncio.create_task(_eslatma_halqa())
    yield
    zx.cancel()
    es.cancel()
    if BOT:
        await BOT.toxta()


app = FastAPI(title="Miya", lifespan=hayot, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/v", StaticFiles(directory=VEB), name="veb")
if os.path.isdir(SHRIFT):
    app.mount("/shrift", StaticFiles(directory=SHRIFT), name="shrift")


@app.middleware("http")
async def himoya(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api/") and request.headers.get("x-miya") != "1":
        return JSONResponse({"xato": "So'rov rad etildi"}, status_code=403)
    javob = await call_next(request)
    javob.headers["X-Content-Type-Options"] = "nosniff"
    javob.headers["Referrer-Policy"] = "same-origin"
    if not request.url.path.startswith("/ilova"):
        javob.headers["X-Frame-Options"] = "DENY"
    return javob


@app.exception_handler(hisob.HisobXato)
@app.exception_handler(ishlar.IshXato)
@app.exception_handler(davomat.DavomatXato)
@app.exception_handler(maosh.MaoshXato)
@app.exception_handler(qoida.QoidaXato)
@app.exception_handler(mijozlar.MijozXato)
@app.exception_handler(vadalar.VadaXato)
@app.exception_handler(usullar.UsulXato)
@app.exception_handler(topshirish.TopshirishXato)
@app.exception_handler(buyurtma.BuyurtmaXato)
@app.exception_handler(xotira.XotiraXato)
@app.exception_handler(ValueError)
async def xato_javob(request: Request, x: Exception):
    return JSONResponse({"xato": str(x)}, status_code=400)


# ---------- kirish ----------

def joriy(request: Request) -> dict:
    o = odamlar.sessiya_odam(request.cookies.get("miya_s"))
    if not o:
        raise HTTPException(401, "Kirish kerak")
    return o


def boshliq_kerak(o: dict = Depends(joriy)) -> dict:
    if not odamlar.boshliqmi(o):
        raise HTTPException(403, "Faqat boshliq uchun")
    return o


def _ip(request: Request) -> str:
    """Haqiqiy mijoz IP si. Serverda Caddy ortida (MIYA_PROXY=1, port tashqariga ochilmagan) — Caddy yozgan X-Real-IP;
    aks holda hamma foydalanuvchi bitta (Caddy) IP bo'lib, kirish urinishlari chegarasi hammaga birdan tushardi."""
    ip = request.client.host if request.client else "?"
    if (ip in ("127.0.0.1", "::1") or os.environ.get("MIYA_PROXY") == "1") and request.headers.get("x-real-ip"):
        return request.headers["x-real-ip"]
    return ip


def _cookie(javob: Response, request: Request, token: str):
    javob.set_cookie("miya_s", token, httponly=True, samesite="lax", max_age=30 * 86400,
                     secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https")


@app.get("/", response_class=HTMLResponse)
def bosh_sahifa():
    """Yangilangan JS/CSS eski keshdan olinmasligi uchun fayl vaqti bilan ?v= qo'shiladi."""
    with open(os.path.join(VEB, "panel.html"), encoding="utf-8") as f:
        html_ = f.read()
    for nom in ("panel.js", "chat.js", "crm.js", "panel.css"):
        v = int(os.path.getmtime(os.path.join(VEB, nom)))
        html_ = html_.replace(f"/v/{nom}", f"/v/{nom}?v={v}")
    return HTMLResponse(html_, headers={"Cache-Control": "no-cache"})


@app.get("/ilova", response_class=HTMLResponse)
def ilova_sahifa():
    return FileResponse(os.path.join(VEB, "ilova.html"), headers={"Cache-Control": "no-cache"})


def _sozlash_kodi_kerak() -> bool:
    """Serverda (ochiq internetda) birinchi sozlash bir martalik kod bilan — aks holda saytni birinchi topgan begona
    odam o'zini boshliq qilib olardi. Kod: docker exec miya python3 -m miya.sozlash_kodi"""
    return os.environ.get("MIYA_PROXY") == "1"


@app.get("/api/holat")
def holat():
    sozlangan = odamlar.boshliq() is not None
    return {"sozlangan": sozlangan, "kod_kerak": not sozlangan and _sozlash_kodi_kerak()}


@app.post("/api/sozlash")
async def sozlash(request: Request, response: Response):
    """Birinchi ishga tushirish: boshliq hisobi va asosiy kassa."""
    if odamlar.boshliq():
        raise HTTPException(400, "Dastur allaqachon sozlangan")
    d = await request.json()
    if _sozlash_kodi_kerak():
        k_ip, hozir = "sozlash:" + _ip(request), time.time()
        _urinish[k_ip] = [t for t in _urinish.get(k_ip, []) if hozir - t < 600]
        if len(_urinish[k_ip]) >= 5:
            raise HTTPException(429, "Ko'p urinish. 10 daqiqadan keyin qayta urinib ko'ring")
        kod = baza.sozlama("sozlash_kodi")
        if not kod or not hmac.compare_digest(str(kod), str(d.get("kod") or "").strip().upper()):
            _urinish[k_ip].append(hozir)
            raise HTTPException(403, "Sozlash kodi noto'g'ri")
    with baza.tranz():
        bid = odamlar.odam_yarat(d.get("ism", ""), "boshliq")
        odamlar.parol_qoy(bid, d.get("login", ""), d.get("parol", ""), bid)
        kid = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", bid, bid)
        if not baza.qiymat("SELECT COUNT(*) FROM xarajat_turi"):
            for n in STANDART_XARAJAT:
                baza.bajar("INSERT OR IGNORE INTO xarajat_turi(nom) VALUES(?)", n)
        maosh.boshlangan_oy()
        baza.sozlama_qoy("sozlash_kodi", None)
    _cookie(response, request, odamlar.sessiya_yarat(bid))
    return {"ok": True, "kassa_id": kid}


@app.post("/api/kirish")
async def kirish(request: Request, response: Response):
    ip = _ip(request)
    hozir = time.time()
    _urinish[ip] = [t for t in _urinish.get(ip, []) if hozir - t < 60]
    if len(_urinish[ip]) >= 8:
        raise HTTPException(429, "Ko'p urinish. Bir daqiqadan keyin qayta urinib ko'ring")
    d = await request.json()
    o = odamlar.kirish(d.get("login", ""), d.get("parol", ""))
    if not o:
        _urinish[ip].append(hozir)
        raise HTTPException(401, "Login yoki parol noto'g'ri")
    _cookie(response, request, odamlar.sessiya_yarat(o["id"]))
    baza.jurnal(o["id"], "panelga_kirdi", f"odam:{o['id']}", None, ip)
    return {"ok": True}


@app.post("/api/chiqish")
def chiqish(request: Request, response: Response):
    odamlar.sessiya_tugat(request.cookies.get("miya_s"))
    response.delete_cookie("miya_s")
    return {"ok": True}


def _vada_nishon(o: dict) -> int:
    """Chap menyudagi raqam: bugun muddati kelgan va bajarilmagan va'dalar."""
    bugun = vaqt.bugun()
    n = 0
    for v in vadalar.royxat(dan=(bugun - timedelta(days=30)).isoformat(), gacha=bugun.isoformat(), **_vada_korinadi(o)):
        if v["holat"] == "ochiq" and (v["holat_h"] in ("buzildi", "qisman") or
                                      (v["muddat"] == bugun.isoformat() and v["holat_h"] == "ochiq")):
            n += 1
    return n


def _ochiq(o: dict) -> dict:
    return {k: o[k] for k in ("id", "ism", "rol", "lavozim", "telefon", "holat", "maosh_tolaydi", "kassa_id", "login")} | {
        "telegram": bool(o["tg_id"]), "rol_nomi": odamlar.ROL_NOMI[o["rol"]]}


@app.get("/api/men")
def men(o: dict = Depends(joriy)):
    k = ai.umumiy_korish(o)  # R3: faol xodim chatda boshliqdek ko'radi va yangi mijoz qo'sha oladi
    huquq = {a: odamlar.mumkin(k, a) for a in ("kassa", "mijoz_qarz", "sotuv", "maosh_tolash", "ishbay")}
    nishon = {}
    if odamlar.boshliqmi(o) or odamlar.mumkin(o, "mijoz_qarz"):
        nishon["vadalar"] = _vada_nishon(o)
    return {"odam": _ochiq(o), "huquq": huquq, "boshliq": odamlar.boshliqmi(o), "nishon": nishon,
            "xizmat": {"bot": bool(BOT), "bot_nomi": baza.sozlama("bot_nomi"), "ai": ai.yoqilganmi(),
                       "ovoz": ovoz.yoqilganmi(), "model": ai.model()},
            "bugun": vaqt.bugun().isoformat(), "oy": vaqt.oy(vaqt.bugun())}


# ---------- yordamchilar ----------

def _pul(m: int, v: str = "UZS") -> dict:
    return {"m": m, "v": v, "t": matn.pul(m, v)}


def _harakat_json(h: dict) -> dict:
    yozgan = odamlar.odam(h["yozgan_id"])
    return {"id": h["id"], "tur": h["tur"], "nom": hisob.SHABLON.get(h["tur"], (h["tur"],))[0],
            "tavsif": hisob.qisqa_tavsif(h), "summa": _pul(h["summa"], h["valyuta"]),
            "summa2": _pul(h["summa2"], h["valyuta2"]) if h["summa2"] else None,
            "dan": hisob.hisob_nomi(h["dan"]), "ga": hisob.hisob_nomi(h["ga"]), "dan_k": h["dan"], "ga_k": h["ga"],
            "voqea_sana": h["voqea_sana"], "hisob_sana": h["hisob_sana"], "kech": h["kech"],
            "holat": h["holat"], "beruvchi_holat": h["beruvchi_holat"], "oluvchi_holat": h["oluvchi_holat"],
            "beruvchi": (odamlar.odam(h["beruvchi_id"]) or {}).get("ism"),
            "oluvchi": (odamlar.odam(h["oluvchi_id"]) or {}).get("ism"),
            "beruvchi_id": h["beruvchi_id"], "oluvchi_id": h["oluvchi_id"],
            "yozgan": yozgan["ism"] if yozgan else "Tizim", "yozilgan": h["yozilgan"], "izoh": h["izoh"],
            "iqtibos": h["iqtibos"], "manba": h["manba"], "qoida_buzilish": h["qoida_buzilish"],
            "bekor_sabab": h["bekor_sabab"], "xabar_id": h["xabar_id"], "muddat": h["muddat"],
            "odam_id": h["odam_id"], "mijoz_id": h["mijoz_id"], "xarajat_turi_id": h["xarajat_turi_id"],
            "valyuta": h["valyuta"], "bog_id": h["bog_id"]}


def _ish_json(i: dict) -> dict:
    return {"id": i["id"], "nom": i["nom"], "joy": i["joy"], "mijoz": i["mijoz"], "muddat": i["muddat"], "soat": i["soat"],
            "narx": _pul(i["narx"], i["valyuta"]) if i["narx"] else None, "dalil_turi": i["dalil_turi"],
            "dalil_nomi": ishlar.DALIL_NOMI[i["dalil_turi"]], "holat": i["holat"], "holat_nomi": ishlar.HOLAT_NOMI[i["holat"]],
            "ish_turi": i["ish_turi"], "manba": i["manba"], "kechikdi": ishlar.kechikdi_kun(i), "sabab": i["sabab"],
            "izoh": i["izoh"], "yaratilgan": i["yaratilgan"], "bajarildi_vaqt": i["bajarildi_vaqt"],
            "yaratgan": (odamlar.odam(i["yaratgan_id"]) or {}).get("ism"),
            "ijrochilar": [{"odam_id": x["odam_id"], "ism": x["ism"], "ulush": x["ulush"], "korildi": x["korildi"]}
                           for x in i["ijrochilar"]],
            "dalillar": [{"id": d_["id"], "tur": d_["tur"], "vaqt": d_["vaqt"], "masofa": d_["masofa"], "izoh": d_["izoh"],
                          "rasm": bool(d_["fayl"]), "xabar_id": d_["xabar_id"]} for d_ in i["dalillar"]]}


def _vada_json(v: dict) -> dict:
    masul = odamlar.odam(v["masul_id"])
    yozgan = odamlar.odam(v["yozgan_id"])
    return {"id": v["id"], "mijoz_id": v["mijoz_id"], "mijoz": v.get("mijoz") or "", "kim": v["kim"], "tur": v["tur"],
            "summa": _pul(v["summa"], v["valyuta"]) if v["summa"] else None, "matn": v["matn"], "muddat": v["muddat"],
            "muddat_matn": vaqt.sana_matn(v["muddat"], False), "holat": v["holat"], "holat_h": v["holat_h"],
            "holat_nomi": vadalar.HOLAT_NOMI.get(v["holat_h"], v["holat_h"]),
            "qoplandi": _pul(v["qoplandi"], v["valyuta"]) if v.get("qoplandi") is not None else None,
            "qolgan": _pul(v["qolgan"], v["valyuta"]) if v.get("qolgan") is not None else None,
            "masul_id": v["masul_id"], "masul": masul["ism"] if masul else None, "yozgan": yozgan["ism"] if yozgan else None,
            "yozilgan": v["yozilgan"], "iqtibos": v["iqtibos"], "xabar_id": v["xabar_id"], "izoh": v["izoh"],
            "harakat_id": v.get("harakat_id"), "bugun": v["muddat"] == vaqt.bugun().isoformat()}


def _xabar_qisqa(xid: int | None) -> dict | None:
    """Asl xabar (C2): ovoz yoki rasm bo'lsa — fayl havolasi, matn bo'lsa — o'zi."""
    xb = baza.bir("SELECT id, tur, matn, stt_matn, fayl, davomiylik, yashirin FROM xabar WHERE id=?", xid) if xid else None
    if not xb or xb["yashirin"]:
        return None
    return {"id": xb["id"], "tur": xb["tur"], "fayl": bool(xb["fayl"]), "davomiylik": xb["davomiylik"],
            "matn": (xb["stt_matn"] or xb["matn"] or "")[:300]}


def _vada_korinadi(o: dict) -> dict:
    """C-g: xodim faqat o'zi mas'ul va'dalarni ko'radi."""
    return {"masul_id": o["id"]} if o["rol"] == "xodim" else {}


def _mijoz_ol(mid: int, o: dict) -> dict:
    m = mijozlar.mijoz(mid)
    if not m or not mijozlar.korishi_mumkin(o, m):
        raise HTTPException(404, "Mijoz topilmadi yoki uni ko'rishga huquqingiz yo'q")
    return m


def _kassalar_json(o: dict) -> list:
    natija = []
    for k in hisob.kassa_holati():
        if not odamlar.hisob_korishi_mumkin(o, f"kassa:{k['id']}"):
            continue
        masul = odamlar.odam(k["masul_id"])
        natija.append({"id": k["id"], "nom": k["nom"], "tur": k["tur"], "valyuta": k["valyuta"],
                       "masul": masul["ism"] if masul else None, "masul_id": k["masul_id"],
                       "qoldiq": _pul(k["qoldiq"], k["valyuta"]),
                       "kutilayotgan_chiqim": _pul(k["kutilayotgan"]["chiqim_jami"], k["valyuta"]),
                       "kutilayotgan_kirim": _pul(k["kutilayotgan"]["kirim_jami"], k["valyuta"]),
                       "oxirgi_sanoq": k["oxirgi_sanoq"]})
    return natija


# ---------- Bugun ----------

@app.get("/api/bugun")
def bugun_api(o: dict = Depends(joriy)):
    bugun = vaqt.bugun()
    b_iso = bugun.isoformat()
    natija: dict = {"bugun": b_iso, "sana_matn": vaqt.sana_matn(bugun)}
    natija["kecha_yozuv"] = baza.qiymat("SELECT COUNT(*) FROM xabar WHERE substr(vaqt,1,10)=?",
                                        (bugun.fromordinal(bugun.toordinal() - 1)).isoformat())
    if odamlar.mumkin(o, "kassa") or odamlar.boshliqmi(o):
        kas = _kassalar_json(o)
        natija["kassalar"] = kas
        natija["kassa_jami"] = _pul(sum(k["qoldiq"]["m"] for k in kas if k["valyuta"] == "UZS"))
        natija["kassa_usd"] = _pul(sum(k["qoldiq"]["m"] for k in kas if k["valyuta"] == "USD"), "USD")
        oxirgi = baza.bir("SELECT * FROM kassa_sanoq ORDER BY vaqt DESC LIMIT 1")
        natija["oxirgi_sanoq"] = oxirgi
    if odamlar.mumkin(o, "mijoz_qarz") or odamlar.boshliqmi(o):
        qarzlar = hisob.mijoz_qarzlari()
        jami = sum(kurs.somga(s, v) or 0 for q in qarzlar for v, s in q["qarz"].items())
        otgan = [q for q in qarzlar if q["muddat"] and q["muddat"] < b_iso]
        natija["mijoz_qarz"] = {"jami": _pul(jami), "soni": len(qarzlar),
                                "muddati_otgan": _pul(sum(kurs.somga(s, v) or 0 for q in otgan for v, s in q["qarz"].items())),
                                "otgan_soni": len(otgan)}
    if odamlar.boshliqmi(o):
        b = maosh.bashorat()
        natija["maosh"] = {"kun": b["kun"], "kun_matn": vaqt.sana_matn(b["kun"], False), "qoldi_kun": b["qoldi_kun"],
                           "kerak": _pul(b["kerak"]), "aniq": _pul(b["aniq_pul"]), "yetmaydi": _pul(b["yetmaydi"])}
        natija["xodimlar"] = [{"id": x["odam_id"], "ism": x["ism"], "qolgani": _pul(x["qolgani"], x["valyuta"]),
                               "qolida": _pul(hisob.qoldiq_bir(f"qol:{x['odam_id']}"))} for x in maosh.tolash_kerak()]
        dushanba = bugun.fromordinal(bugun.toordinal() - bugun.weekday())
        kunlar = []
        for i in range(7):
            d = dushanba.fromordinal(dushanba.toordinal() + i)
            if d > bugun:
                break
            j = hisob.davr_jami(d.isoformat(), d.isoformat())
            kunlar.append({"sana": d.isoformat(), "kun": vaqt.HAFTA[d.weekday()][:2].capitalize(),
                           "kirim": j["kassa_kirim"], "chiqim": j["kassa_chiqim"]})
        hj = hisob.davr_jami(dushanba.isoformat(), b_iso)
        natija["hafta"] = {"kunlar": kunlar, "kirim": _pul(hj["kassa_kirim"]), "chiqim": _pul(hj["kassa_chiqim"]),
                           "sotuv": _pul(hj["sotuv"]), "xarajat": _pul(hj["xarajat"])}
    if odamlar.boshliqmi(o):
        natija["maosh"]["vada"] = _pul(vadalar.kutilayotgan_tushum(max(b["qoldi_kun"], 0))["jami"])
        natija["pul_oqimi"] = _pul_oqimi(b)
        x = xulosa.oxirgi("kun")
        natija["xulosa"] = {k: x[k] for k in ("sana", "matn", "qolip", "vaqt")} if x and x["sana"] == b_iso else None
        natija["brifing_vaqti"] = baza.sozlama("brifing_vaqti", "08:30")
    vk = _vada_korinadi(o)
    ochiq = [v for v in vadalar.royxat(faqat_ochiq=True, **vk)]
    bugungi = sorted([v for v in ochiq if v["muddat"] == b_iso], key=lambda v: v["id"])
    natija["vadalar"] = {"bugun": [_vada_json(v) for v in bugungi], "ochiq_soni": len(ochiq),
                         "bugun_tushum": _pul(sum(kurs.somga(v["qolgan"] or 0, v["valyuta"]) or 0 for v in bugungi
                                                  if v["tur"] == "tolov" and v["kim"] == "mijoz"))}
    natija["vadalar"]["nishon"] = _vada_nishon(o)
    natija["kutmoqda"] = [_harakat_json(h) for h in _kutayotganlar(o)]
    natija["diqqat"] = _diqqat(o)
    if ishlar.tolov_huquqi(o):
        natija["odamlar"] = davomat.bugun_holati()
        natija["qabul_kutmoqda"] = [_ish_json(i) for i in ishlar.ishlar(qabul_kerak=True)][:20]
    natija["mening_ishlarim"] = [_ish_json(i) for i in ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)][:20]
    if odamlar.boshliqmi(o):
        q = _boshlash(o)
        natija["boshlash"] = q if not all(x["bajarildi"] for x in q) else None
    return natija


def _boshlash(o: dict) -> list[dict]:
    """Bo'sh tizimni ishga tushirish yo'riqnomasi (faqat boshliq). Har qadam holati bazadan — o'zi belgilanadi."""
    kassalar = [k for k in hisob.kassalar() if k["tur"] != "chontak"] or hisob.kassalar()
    kassa_nom = kassalar[0]["nom"] if kassalar else "Asosiy kassa"
    xodim = baza.qiymat("SELECT COUNT(*) FROM odam WHERE rol!='boshliq' AND holat!='ketgan'")
    return [
        {"k": "tg", "nom": "Telegram'ga o'zingizni ulang", "bajarildi": bool(o.get("tg_id")),
         "izoh": "Ovozli xabar, chek rasmi va ertalabki xulosa botga keladi"},
        {"k": "xodim", "nom": "Xodimlarni qo'shing", "bajarildi": xodim > 0,
         "izoh": "Har biriga Telegram havolasi va panel paroli beriladi"},
        {"k": "kassa", "nom": "Kassalardagi pulni yozing", "bajarildi": bool(baza.qiymat(
            "SELECT COUNT(*) FROM harakat WHERE tur='boshlangich_kassa' AND holat='faol'")),
         "izoh": "Miya qatoriga yozing — kartochka chiqadi", "misol": f"{kassa_nom}da 5 mln bor"},
        {"k": "mijoz", "nom": "Mijozlar va ularning eski qarzi", "bajarildi": bool(baza.qiymat("SELECT COUNT(*) FROM mijoz")),
         "izoh": "Bir gapda bir nechtasini yozsa bo'ladi", "misol": "Karimovning eski qarzi 3 mln, Sobirovniki 1,5 mln"},
        {"k": "maosh", "nom": "Xodimlar maoshini kiriting", "bajarildi": bool(baza.qiymat("SELECT COUNT(*) FROM maosh_shart")),
         "izoh": "Oylik, kunbay yoki ishbay — maosh kuni hisobni dastur qiladi"},
        {"k": "ovoz", "nom": "Ovozli xabarlarni yoqing", "bajarildi": ovoz.yoqilganmi(),
         "izoh": "Google kaliti kerak — ovoz yozuvga aylanadi"},
    ]


def _pul_oqimi(b: dict) -> dict:
    """P8: 30 kun oldinga ikki chiziq — «aniq pul» (qo'ldagi pul, maosh kunida kerakli summa ayriladi) va
    «va'dalar bajarilsa» (ustiga ochiq to'lov va'dalari muddati bo'yicha qo'shiladi). Muddati o'tgan va'da qo'shilmaydi."""
    bugun = vaqt.bugun()
    vada_kun: dict[str, int] = {}
    for v in vadalar.kutilayotgan_tushum(30)["vadalar"]:
        vada_kun[v["muddat"]] = vada_kun.get(v["muddat"], 0) + (kurs.somga(v["qolgan"] or 0, v["valyuta"]) or 0)
    nuqtalar, aniq, qoshimcha = [], b["aniq_pul"], 0
    for i in range(31):
        d = (bugun + timedelta(days=i)).isoformat()
        if d == b["kun"]:
            aniq -= b["kerak"]
        qoshimcha += vada_kun.get(d, 0)
        nuqtalar.append({"sana": d, "aniq": aniq, "vada": aniq + qoshimcha})
    return {"nuqtalar": nuqtalar, "maosh_kun": b["kun"], "vada_jami": _pul(qoshimcha),
            "eng_kam": _pul(min(n["aniq"] for n in nuqtalar))}


def _kutayotganlar(o: dict) -> list[dict]:
    if odamlar.boshliqmi(o):
        return baza.hammasi("SELECT * FROM harakat WHERE (holat IN ('faol','nizo') AND (beruvchi_holat='kutilmoqda' OR "
                            "oluvchi_holat='kutilmoqda')) OR holat='ruxsat_kutilmoqda' ORDER BY id DESC LIMIT 50")
    return baza.hammasi("SELECT * FROM harakat WHERE holat IN ('faol','nizo') AND ((beruvchi_id=? AND "
                        "beruvchi_holat='kutilmoqda') OR (oluvchi_id=? AND oluvchi_holat='kutilmoqda') OR "
                        "(yozgan_id=? AND (beruvchi_holat='kutilmoqda' OR oluvchi_holat='kutilmoqda'))) "
                        "ORDER BY id DESC LIMIT 50", o["id"], o["id"], o["id"])


def _diqqat(o: dict) -> list[dict]:
    return signallar.royxat(o)


# ---------- kassa va pul ----------

@app.get("/api/kassalar")
def kassalar_api(o: dict = Depends(joriy)):
    return {"kassalar": _kassalar_json(ai.umumiy_korish(o))}  # R3: chatdagi xodim ham hamma kassani ko'radi


@app.post("/api/kassa")
async def kassa_yarat_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    kid = hisob.kassa_yarat(d.get("nom", "").strip() or "Kassa", d.get("tur", "naqd"), d.get("valyuta", "UZS"),
                            d.get("masul_id"), o["id"])
    return {"id": kid}


@app.post("/api/kassa/{kid}")
async def kassa_tahrir_api(kid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    eski = hisob.kassa(kid)
    if not eski:
        raise HTTPException(404, "Kassa topilmadi")
    nom = (d.get("nom") or eski["nom"]).strip()
    masul = d.get("masul_id", eski["masul_id"])
    faol = int(d.get("faol", eski["faol"]))
    with baza.tranz():
        baza.bajar("UPDATE kassa SET nom=?, masul_id=?, faol=? WHERE id=?", nom, masul, faol, kid)
        baza.jurnal(o["id"], "kassa_tahrir", f"kassa:{kid}", dict(eski), {"nom": nom, "masul_id": masul, "faol": faol})
    return {"ok": True}


@app.post("/api/kassa/{kid}/sanoq")
async def kassa_sanoq_api(kid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    kas = hisob.kassa(kid)
    if not kas:
        raise HTTPException(404, "Kassa topilmadi")
    r = hisob.kassa_sanoq(kid, matn.minor(float(d.get("summa") or 0), kas["valyuta"]), o["id"], d.get("izoh"))
    return {"kutilgan": _pul(r["kutilgan"], kas["valyuta"]), "sanalgan": _pul(r["sanalgan"], kas["valyuta"]),
            "farq": _pul(r["farq"], kas["valyuta"]), "agar": _pul(r["agar_tasdiqlansa"], kas["valyuta"])}


@app.get("/api/harakatlar")
def harakatlar_api(request: Request, o: dict = Depends(joriy)):
    q = request.query_params
    f = {k: q.get(k) for k in ("tur", "hisob", "dan", "gacha", "holat", "q") if q.get(k)}
    for k in ("odam_id", "mijoz_id", "limit", "oldin_id"):
        if q.get(k):
            f[k] = int(q[k])
    return {"harakatlar": [_harakat_json(h) for h in hisob.harakatlar(korish=o, **f)]}


@app.post("/api/harakat")
async def harakat_yarat_api(request: Request, o: dict = Depends(joriy)):
    """Paneldan kiritish — bot kartochkasi bilan bir xil qoidalar (tasdiq, takror, qoida)."""
    d = await request.json()
    tur = d.get("tur")
    if tur not in hisob.SHABLON or tur in ("tuzatish", "hisoblandi"):
        raise HTTPException(400, "Yozuv turi noto'g'ri")
    if not hisob.yozishi_mumkin(o, tur):
        raise HTTPException(403, "Bu turdagi yozuvni faqat boshliq kirita oladi")
    valyuta = d.get("valyuta") or "UZS"
    p = {"summa": matn.minor(float(d.get("summa") or 0), valyuta), "valyuta": valyuta}
    for k in ("odam_id", "mijoz_id", "kassa_id", "kassa2_id", "xarajat_turi_id", "sotuvchi_id"):
        if d.get(k):
            p[k] = int(d[k])
    for k in ("xarajat_turi", "izoh", "sana", "muddat"):
        if d.get(k):
            p[k] = str(d[k])
    if d.get("qoldan"):
        p["qoldan"] = True
    if d.get("tolandi"):
        p["tolandi"] = matn.minor(float(d["tolandi"]), valyuta)
    with baza.tranz():
        if tur == "sotuv":
            hid, kid = hisob.sotuv_tuz(p, o["id"])
        else:
            hid, kid = hisob.taklif(tur, p, o["id"], manba="panel"), None
    if d.get("takror_emas"):
        r = hisob.faollashtir(hid, o["id"])
    else:
        r = hisob.tasdiqla(hid, o["id"])
    if kid and r["holat"] == "faol":
        hisob.faollashtir(kid, o["id"])
    return {"id": hid, "holat": r["holat"], "takrorlar": [_harakat_json(t) for t in r.get("takrorlar", [])],
            "harakat": _harakat_json(hisob.harakat(hid))}


@app.post("/api/harakat/{hid}/birlashtir")
async def birlashtir_api(hid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    h = hisob.harakat(hid)
    if not h or h["yozgan_id"] != o["id"]:
        raise HTTPException(403, "Ruxsat yo'q")
    hisob.birlashtir(hid, int(d["eski_id"]), o["id"])
    return {"ok": True}


@app.get("/api/harakat/{hid}")
def harakat_bir_api(hid: int, o: dict = Depends(joriy)):
    """Bitta yozuv (eski yozuv ham ochiladi — oxirgi 400 ta ichidan qidirilmaydi)."""
    h = hisob.harakat(hid)
    k = ai.umumiy_korish(o)
    if not h or not (odamlar.hisob_korishi_mumkin(k, h["dan"]) or odamlar.hisob_korishi_mumkin(k, h["ga"])):
        raise HTTPException(404, "Yozuv topilmadi")
    return {"harakat": _harakat_json(h)}


@app.post("/api/harakat/{hid}/tuzat")
async def harakat_tuzat_api(hid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    """CRM2: tuzatish — eski yozuv bekor (tarix o'chmaydi, A4), o'rniga to'g'risi; boshliq yozgani darhol faol."""
    d = await request.json()
    h = hisob.harakat(hid)
    if not h:
        raise HTTPException(404, "Yozuv topilmadi")
    if not (d.get("sabab") or "").strip():
        raise HTTPException(400, "Tuzatish sababini yozing")
    oz = {}
    if d.get("summa") not in (None, ""):
        oz["summa"] = matn.minor(float(d["summa"]), h["valyuta"])
        if oz["summa"] <= 0:
            raise HTTPException(400, "Summa noto'g'ri")
    for k in ("kassa_id", "kassa2_id", "odam_id", "mijoz_id", "xarajat_turi_id"):
        if d.get(k):
            oz[k] = int(d[k])
    for k in ("sana", "izoh", "muddat"):
        if d.get(k) is not None:
            oz[k] = str(d[k]) or None
    yangi = hisob.tuzat(hid, o["id"], oz, d["sabab"].strip()[:200])
    r = hisob.faollashtir(yangi, o["id"])
    return {"id": yangi, "holat": r["holat"], "harakat": _harakat_json(hisob.harakat(yangi))}


@app.post("/api/harakat/{hid}/bekor")
async def bekor_api(hid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    tid = hisob.bekor_qil(hid, o["id"], d.get("sabab", ""))
    return {"ok": True, "teskari_id": tid}


@app.post("/api/harakat/{hid}/tomon")
async def tomon_api(hid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    hisob.tomon_tasdiq(hid, o["id"], d["tomon"], bool(d.get("ha")))
    return {"ok": True}


@app.post("/api/harakat/{hid}/nizo")
async def nizo_api(hid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    hisob.nizo_hal(hid, o["id"], bool(d.get("berilgan")))
    return {"ok": True}


@app.post("/api/harakat/{hid}/ruxsat")
async def ruxsat_api(hid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    r = hisob.ruxsat(hid, o["id"], bool(d.get("ha")))
    return {"holat": r["holat"]}


@app.get("/api/xarajat_turlari")
def xarajat_turlari(o: dict = Depends(joriy)):
    return {"turlar": baza.hammasi("SELECT * FROM xarajat_turi WHERE faol=1 ORDER BY nom")}


# ---------- maosh ----------

def _varaq_json(v: dict) -> dict:
    val = v["valyuta"]
    return {"odam": _ochiq(v["odam"]), "oy": v["oy"], "oy_matn": vaqt.oy_matn(v["oy"]), "valyuta": val,
            "otgan": _pul(v["otgan"], val), "hisoblandi": _pul(v["hisoblandi"], val), "olindi": _pul(v["olindi"], val),
            "kutilmoqda": [{"nom": k["nom"], "summa": _pul(k["summa"], val), "harakat_id": k["harakat_id"],
                            "sana": k["sana"]} for k in v["kutilmoqda"]],
            "kutilmoqda_jami": _pul(v["kutilmoqda_jami"], val), "qolgani": _pul(v["qolgani"], val), "yopiq": v["yopiq"],
            "ish_kutilmoqda": [{"nom": k["nom"], "summa": _pul(k["summa"], val), "ish_id": k["ish_id"]}
                               for k in v.get("ish_kutilmoqda", [])],
            "ish_kutilmoqda_jami": _pul(v.get("ish_kutilmoqda_jami", 0), val),
            "qatorlar": [{"nom": q["nom"], "summa": _pul(q["summa"], val), "harakat_id": q["harakat_id"],
                          "sana": q["sana"]} for q in v["qatorlar"]]}


@app.get("/api/maosh")
def maosh_api(request: Request, o: dict = Depends(joriy)):
    oy = request.query_params.get("oy") or vaqt.oy(vaqt.bugun())
    if odamlar.boshliqmi(o):
        royxat = []
        for x in odamlar.faol_odamlar():
            v = maosh.varaq(x["id"], oy)
            shart = [{"id": s["id"], "tur": s["tur"], "nom": maosh.SHART_TURI[s["tur"]], "qiymat": s["qiymat"],
                      "valyuta": s["valyuta"], "dan": s["dan_sana"], "gacha": s["gacha_sana"]}
                     for s in maosh.shartlar(x["id"], oy)]
            royxat.append({**_varaq_json(v), "shartlar": shart,
                           "kunlar": baza.qiymat("SELECT kunlar FROM ish_kuni WHERE odam_id=? AND oy=?", x["id"], oy)})
        davr = baza.bir("SELECT * FROM maosh_davr WHERE oy=?", oy)
        return {"oy": oy, "oy_matn": vaqt.oy_matn(oy), "royxat": royxat, "yopiq": bool(davr and davr["holat"] == "yopiq"),
                "maosh_kunlari": maosh.maosh_kunlari(), "boshlangan_oy": maosh.boshlangan_oy()}
    if odamlar.mumkin(o, "maosh_tolash"):
        return {"oy": oy, "tolash": [{"odam_id": x["odam_id"], "ism": x["ism"], "qolgani": _pul(x["qolgani"], x["valyuta"])}
                                     for x in maosh.tolash_kerak()], "oz": _varaq_json(maosh.varaq(o["id"], oy))}
    return {"oy": oy, "oz": _varaq_json(maosh.varaq(o["id"], oy))}


@app.get("/api/maosh/{odam_id}")
def maosh_bir_api(odam_id: int, request: Request, o: dict = Depends(joriy)):
    if odam_id != o["id"] and not odamlar.boshliqmi(o):
        raise HTTPException(403, "Faqat o'z hisobingiz")
    return _varaq_json(maosh.varaq(odam_id, request.query_params.get("oy")))


@app.post("/api/maosh/shart")
async def shart_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    sid = maosh.shart_qoy(int(d["odam_id"]), d["tur"], float(d["qiymat"]), d.get("valyuta", "UZS"),
                          d.get("dan") or vaqt.oy_boshi(vaqt.oy(vaqt.bugun())).isoformat(), o["id"], d.get("izoh"))
    return {"id": sid}


@app.post("/api/maosh/shart/{sid}/tugat")
async def shart_tugat_api(sid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    maosh.shart_tugat(sid, d.get("gacha") or vaqt.bugun().isoformat(), o["id"])
    return {"ok": True}


@app.post("/api/maosh/kunlar")
async def kunlar_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    maosh.kunlar_qoy(int(d["odam_id"]), d["oy"], float(d["kunlar"]), o["id"])
    return {"ok": True}


@app.post("/api/maosh/yopish")
async def yopish_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    return maosh.oy_yop(d["oy"], o["id"])


# ---------- xodimlar ----------

@app.get("/api/odamlar")
def odamlar_api(o: dict = Depends(joriy)):
    if not (odamlar.boshliqmi(o) or o["rol"] in ("kassir", "menejer")):
        return {"odamlar": [_ochiq(o)]}
    hammasi = baza.hammasi("SELECT * FROM odam ORDER BY holat='ketgan', ism")
    return {"odamlar": [_ochiq(x) | {"parol_bor": bool(x["parol_xesh"])} for x in hammasi]}


@app.post("/api/odam")
async def odam_yarat_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    with baza.tranz():  # login band bo'lsa xodim ham yaratilmaydi
        oid = odamlar.odam_yarat(d.get("ism", ""), d.get("rol", "xodim"), o["id"], d.get("telefon"), d.get("lavozim"),
                                 int(bool(d.get("maosh_tolaydi"))))
        if (d.get("login") or "").strip():
            odamlar.parol_qoy(oid, d["login"], d.get("parol", ""), o["id"])
    return {"id": oid}


@app.post("/api/odam/{oid}")
async def odam_tahrir_api(oid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    odamlar.odam_tahrir(oid, o["id"], **{k: d.get(k) for k in ("ism", "telefon", "lavozim", "rol", "maosh_tolaydi",
                                                                "kassa_id") if k in d})
    return {"ok": True}


@app.post("/api/odam/{oid}/taklif")
def taklif_api(oid: int, o: dict = Depends(boshliq_kerak)):
    kod = odamlar.taklif_yarat(oid, o["id"])
    nom = baza.sozlama("bot_nomi")
    return {"kod": kod, "havola": f"https://t.me/{nom}?start={kod}" if nom else None,
            "muddat_kun": odamlar.TAKLIF_MUDDAT_KUN}


@app.post("/api/odam/{oid}/parol")
async def parol_api(oid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    odamlar.parol_qoy(oid, d.get("login", ""), d.get("parol", ""), o["id"])
    return {"ok": True}


@app.get("/api/odam/{oid}/parol")
def parol_kor_api(oid: int, o: dict = Depends(boshliq_kerak)):
    return {"parol": odamlar.parol_kor(oid, o["id"])}


@app.post("/api/odam/{oid}/holat")
async def odam_holat_api(oid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    if oid == o["id"]:
        raise HTTPException(400, "O'zingizni cheklay olmaysiz")
    if d["holat"] == "ketgan":  # O4: kirish faqat topshirish tugagach (yoki sababi bilan) yopiladi
        topshirish.yopish(oid, o["id"], d.get("sabab"))
    else:
        odamlar.holat_qoy(oid, d["holat"], o["id"])
    return {"ok": True}


@app.get("/api/odam/{oid}/topshirish")
def topshirish_api(oid: int, o: dict = Depends(boshliq_kerak)):
    return topshirish.varaq(oid)


@app.post("/api/odam/{oid}/topshir")
async def topshir_api(oid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    return topshirish.otkaz(oid, int(d.get("kimga") or 0), o["id"], set(d.get("nimalar") or []) or None)


# ---------- mijozlar ----------

@app.get("/api/mijozlar")
def mijozlar_api(request: Request, o: dict = Depends(joriy)):
    o = ai.umumiy_korish(o)  # R3
    tur = request.query_params.get("tur") or "mijoz"
    if tur == "taminotchi" and not (odamlar.boshliqmi(o) or odamlar.mumkin(o, "mijoz_qarz")):
        raise HTTPException(403, "Ruxsat yo'q")
    qarzlar = {q["id"]: q for q in hisob.mijoz_qarzlari(tur)}
    vadali = {r["mijoz_id"] for r in baza.hammasi("SELECT DISTINCT mijoz_id FROM vada WHERE holat!='bekor'")}
    xaridli = {r["mijoz_id"]: r for r in baza.hammasi(
        "SELECT mijoz_id, COUNT(DISTINCT voqea_sana) n, MAX(voqea_sana) oxirgi FROM harakat WHERE tur='sotuv' "
        "AND holat IN ('faol','nizo') GROUP BY mijoz_id")}
    odam_nom = {x["id"]: x["ism"] for x in baza.hammasi("SELECT id, ism FROM odam")}
    natija = []
    arxiv = 1 if request.query_params.get("arxiv") == "1" else 0  # CRM2: arxivdagilar alohida
    for m in baza.hammasi("SELECT * FROM mijoz WHERE tur=? AND birlashdi IS NULL AND arxiv=? ORDER BY ism", tur, arxiv):
        if not mijozlar.korishi_mumkin(o, m):
            continue
        q = qarzlar.get(m["id"])
        x = xaridli.get(m["id"])
        ux = mijozlar.uxlash(m["id"]) if x and x["n"] >= 3 else None
        ish_ = vadalar.ishonch(m["id"]) if m["id"] in vadali else None
        ochiq = sum(1 for v in vadalar.royxat(m["id"], faqat_ochiq=True)) if m["id"] in vadali else 0
        natija.append({**m, "qarz": [_pul(s, v) for v, s in q["qarz"].items()] if q else [],
                       "qarz_som": sum(kurs.somga(s, v) or 0 for v, s in q["qarz"].items()) if q else 0,
                       "muddat": q["muddat"] if q else None, "masul": odam_nom.get(m["masul_id"]),
                       "oxirgi_xarid": x["oxirgi"] if x else None, "xarid_soni": x["n"] if x else 0,
                       "uxlagan": bool(ux and ux["uxlagan"]), "uxlash": ux, "ishonch": ish_, "ochiq_vada": ochiq})
    return {"mijozlar": natija, "tahrir": odamlar.boshliqmi(o) or o["rol"] in ("menejer", "kassir"),
            "masul_tanlash": odamlar.boshliqmi(o) or o["rol"] == "menejer"}


@app.get("/api/mijoz/{mid}")
def mijoz_karta_api(mid: int, o: dict = Depends(joriy)):
    m = _mijoz_ol(mid, o)
    k = mijozlar.karta(mid)
    belgi = {"qarz": [_pul(s, v) for v, s in k["qarz"].items()]}
    if m["tur"] == "taminotchi":  # ta'minotchida manfiy qoldiq — bizning qarzimiz
        belgi = {"qarz": [], "qarzimiz": [_pul(-s, v) for v, s in k["qarz"].items() if s < 0]}
    return {"mijoz": m, "masul": k["masul"], **belgi, "ishonch": k["ishonch"], "uxlash": k["uxlash"],
            "qisqa": k["qisqa"], "vadalar": [_vada_json(v) for v in k["vadalar"]],
            "eslatmalar": [{"id": e_["id"], "matn": e_["matn"], "manba": e_["manba"], "yozgan": e_["yozgan"],
                            "vaqt": e_["vaqt"], "xabar_id": e_["xabar_id"],
                            "bekor_mumkin": e_["yozgan_id"] == o["id"] or o["rol"] in ("boshliq", "menejer")}
                           for e_ in k["eslatmalar"]],
            "tarix": [{**t, "xabar": _xabar_qisqa(t["xabar_id"])} for t in mijozlar.tarix(mid)],
            "almashadi": [_vada_json({**v, "mijoz": m["ism"], "holat_h": "buzildi", "qoplandi": None, "qolgan": None})
                          for v in vadalar.almashadiganlar(mid)],
            "tahrir": odamlar.boshliqmi(o) or o["rol"] in ("menejer", "kassir"),
            "masul_tanlash": odamlar.boshliqmi(o) or o["rol"] == "menejer",
            "odamlar": [{"id": x["id"], "ism": x["ism"]} for x in odamlar.faol_odamlar() if x["holat"] == "faol"]}


@app.post("/api/mijoz/{mid}")
async def mijoz_tahrir_api(mid: int, request: Request, o: dict = Depends(joriy)):
    _mijoz_ol(mid, o)
    if not (odamlar.boshliqmi(o) or o["rol"] in ("menejer", "kassir")):
        raise HTTPException(403, "Ruxsat yo'q")
    d = await request.json()
    maydon = {k: d[k] for k in ("ism", "telefon", "telefon2", "manzil", "izoh", "arxiv") if k in d}
    if "masul_id" in d:
        if not (odamlar.boshliqmi(o) or o["rol"] == "menejer"):
            raise HTTPException(403, "Mas'ulni boshliq yoki menejer tanlaydi")
        maydon["masul_id"] = int(d["masul_id"]) if d["masul_id"] else None
    mijozlar.tahrir(mid, o["id"], **maydon)
    return {"ok": True}


@app.post("/api/mijoz/{mid}/eslatma")
async def mijoz_eslatma_api(mid: int, request: Request, o: dict = Depends(joriy)):
    _mijoz_ol(mid, o)
    d = await request.json()
    return {"id": mijozlar.eslatma_qosh(mid, d.get("matn", ""), o["id"], manba="panel")}


@app.post("/api/eslatma/{eid}/bekor")
def eslatma_bekor_api(eid: int, o: dict = Depends(joriy)):
    e_ = baza.bir("SELECT * FROM mijoz_eslatma WHERE id=?", eid)
    if not e_:
        raise HTTPException(404, "Topilmadi")
    if e_["yozgan_id"] != o["id"] and o["rol"] not in ("boshliq", "menejer"):
        raise HTTPException(403, "Buni faqat yozgan odam bekor qiladi")
    mijozlar.eslatma_bekor(eid, o["id"])
    return {"ok": True}


# ---------- va'dalar (C3, C4) ----------

@app.get("/api/vadalar")
def vadalar_api(request: Request, o: dict = Depends(joriy)):
    f = request.query_params.get("f") or "ochiq"
    bugun = vaqt.bugun().isoformat()
    shart = _vada_korinadi(o)
    if request.query_params.get("mijoz_id"):
        shart["mijoz_id"] = int(request.query_params["mijoz_id"])
    hammasi = vadalar.royxat(**shart)
    ochiq = [v for v in hammasi if v["holat_h"] == "ochiq"]
    buzilgan = [v for v in hammasi if v["holat"] == "ochiq" and v["holat_h"] in ("buzildi", "qisman")]
    royxat = {"ochiq": ochiq, "bugun": [v for v in ochiq if v["muddat"] == bugun], "buzilgan": buzilgan,
              "hammasi": hammasi}.get(f, ochiq)
    if f in ("ochiq", "bugun"):
        royxat = sorted(royxat, key=lambda v: (v["muddat"], v["id"]))
    tushum = vadalar.kutilayotgan_tushum(30)
    return {"vadalar": [_vada_json(v) for v in royxat[:300]], "nishon": _vada_nishon(o),
            "soni": {"ochiq": len(ochiq), "bugun": sum(1 for v in ochiq if v["muddat"] == bugun),
                     "buzilgan": len(buzilgan), "hammasi": len(hammasi)},
            "tushum": {"bugun": _pul(tushum["bugun"]), "oy": _pul(tushum["jami"])} if not shart.get("masul_id") else None}


@app.post("/api/vada")
async def vada_yoz_api(request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    m = _mijoz_ol(int(d.get("mijoz_id") or 0), o)
    v = d.get("valyuta") if d.get("valyuta") in ("UZS", "USD") else "UZS"
    summa = matn.minor(float(d["summa"]), v) if d.get("summa") not in (None, "", 0) else None
    masul = int(d["masul_id"]) if d.get("masul_id") and (odamlar.boshliqmi(o) or o["rol"] == "menejer") else None
    vid = vadalar.yoz(m["id"], d.get("muddat") or "", o["id"], kim=d.get("kim") or "mijoz", tur=d.get("tur") or "tolov",
                      summa=summa, valyuta=v, matn_=d.get("matn"), masul_id=masul)
    return {"id": vid}


@app.post("/api/vada/{vid}/tahrir")
async def vada_tahrir_api(vid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    v = vadalar.vada(vid)
    if not v:
        raise HTTPException(404, "Topilmadi")
    summa = -1
    if "summa" in d:
        summa = matn.minor(float(d["summa"]), v["valyuta"]) if d["summa"] not in (None, "", 0) else None
    vadalar.tahrirla(vid, o["id"], summa, d.get("muddat"), d.get("matn"))
    return {"ok": True}


@app.post("/api/vada/{vid}/bekor")
async def vada_bekor_api(vid: int, request: Request, o: dict = Depends(joriy)):
    v = vadalar.vada(vid)
    if not v or not (o["rol"] in ("boshliq", "menejer") or v["yozgan_id"] == o["id"]):
        raise HTTPException(403, "Va'dani boshliq, menejer yoki uni yozgan odam bekor qiladi")
    d = await request.json()
    vadalar.bekor(vid, o["id"], d.get("sabab", ""))
    return {"ok": True}


@app.post("/api/vada/{vid}/eslat")
async def vada_eslat_api(vid: int, o: dict = Depends(joriy)):
    """Mijozga eslatma — faqat tugma bosilganda va mijoz botga ulangan bo'lsa (C-h)."""
    v = vadalar.vada(vid)
    if not v or not (o["rol"] in ("boshliq", "menejer") or v["masul_id"] == o["id"]):
        raise HTTPException(403, "Ruxsat yo'q")
    m = mijozlar.mijoz(v["mijoz_id"])
    if not m or not m["tg_id"]:
        raise HTTPException(400, "Mijoz botga ulanmagan — «Mijozlar»da «Botga ulash» havolasini yuboring")
    if not BOT:
        raise HTTPException(400, "Bot ishlamayapti — Sozlamalarda bot tokenini kiriting")
    kalit = f"vada_mijozga:{vid}:{vaqt.bugun().isoformat()}"
    if baza.bir("SELECT 1 FROM yuborildi WHERE kalit=?", kalit):
        raise HTTPException(400, "Bugun allaqachon eslatilgan")
    from .bot_mijoz import mijozga_matn
    await BOT.yoz(m["tg_id"], mijozga_matn(v, m))
    baza.bajar("INSERT OR IGNORE INTO yuborildi(kalit,vaqt) VALUES(?,?)", kalit, vaqt.iso())
    baza.jurnal(o["id"], "vada_mijozga_eslatildi", f"vada:{vid}")
    return {"ok": True}


@app.post("/api/vada/{vid}/yop")
async def vada_yop_api(vid: int, request: Request, o: dict = Depends(joriy)):
    v = vadalar.vada(vid)
    if not v or not (o["rol"] in ("boshliq", "menejer") or o["id"] in (v["masul_id"], v["yozgan_id"])):
        raise HTTPException(403, "Ruxsat yo'q")
    d = await request.json()
    vadalar.boshqa_yop(vid, o["id"], bool(d.get("bajarildi")))
    return {"ok": True}


@app.post("/api/mijoz")
async def mijoz_yarat_api(request: Request, o: dict = Depends(joriy)):
    if not odamlar.boshliqmi(ai.umumiy_korish(o)):  # R3: har bir faol xodim (pul emas — tasdiq shart emas)
        raise HTTPException(403, "Ruxsat yo'q")
    d = await request.json()
    ism = (d.get("ism") or "").strip()
    if not ism:
        raise HTTPException(400, "Ism kiritilsin")
    mid = baza.bajar("INSERT INTO mijoz(ism,telefon,izoh,tur,yaratilgan) VALUES(?,?,?,?,?)", ism, d.get("telefon"),
                     d.get("izoh"), d.get("tur") if d.get("tur") in ("mijoz", "taminotchi") else "mijoz", vaqt.iso())
    baza.jurnal(o["id"], "mijoz_yarat", f"mijoz:{mid}", None, ism)
    return {"id": mid}


@app.post("/api/mijoz/import/korib")
async def mijoz_import_korib_api(fayl: UploadFile = File(...), tur: str = Form("mijoz"), o: dict = Depends(boshliq_kerak)):
    """CRM5: Excel'ni ko'rib chiqish — hech narsa yozilmaydi."""
    mazmun = await fayl.read()
    if len(mazmun) > 5 * 1024 * 1024:
        raise HTTPException(400, "Fayl 5 MB dan katta")
    try:
        return yuklash.korib_chiq(mazmun, "taminotchi" if tur == "taminotchi" else "mijoz")
    except yuklash.YuklashXato as x:
        raise HTTPException(400, str(x))


@app.post("/api/mijoz/import/yoz")
async def mijoz_import_yoz_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    try:
        r = yuklash.yoz([x for x in d.get("qatorlar") or [] if x.get("holat") == "yangi"], o["id"],
                        "taminotchi" if d.get("tur") == "taminotchi" else "mijoz")
    except yuklash.YuklashXato as x:
        raise HTTPException(400, str(x))
    return r


@app.post("/api/mijoz/{mid}/birlashtir")
async def mijoz_birlashtir_api(mid: int, request: Request, o: dict = Depends(joriy)):
    """Ikki kartani birlashtirish (K7): yozuvlar ko'chadi, eski karta yashiriladi."""
    if not (odamlar.boshliqmi(o) or o["rol"] == "menejer"):
        raise HTTPException(403, "Ruxsat yo'q")
    d = await request.json()
    kimga = int(d["kimga"])
    if kimga == mid:
        raise HTTPException(400, "O'ziga birlashtirib bo'lmaydi")
    eski, yangi = baza.bir("SELECT * FROM mijoz WHERE id=?", mid), baza.bir("SELECT * FROM mijoz WHERE id=?", kimga)
    if not eski or not yangi or eski["tur"] != yangi["tur"]:
        raise HTTPException(400, "Kartalar topilmadi yoki turi har xil")
    t = eski["tur"]
    with baza.tranz():
        baza.bajar("UPDATE harakat SET mijoz_id=? WHERE mijoz_id=?", kimga, mid)
        baza.bajar("UPDATE harakat SET dan=? WHERE dan=?", f"{t}:{kimga}", f"{t}:{mid}")
        baza.bajar("UPDATE harakat SET ga=? WHERE ga=?", f"{t}:{kimga}", f"{t}:{mid}")
        for jadval in ("vada", "mijoz_eslatma", "ish", "ish_dalil", "mijoz_taklif"):
            baza.bajar(f"UPDATE {jadval} SET mijoz_id=? WHERE mijoz_id=?", kimga, mid)
        baza.bajar("UPDATE mijoz SET tg_id=COALESCE(tg_id,?), masul_id=COALESCE(masul_id,?), telefon=COALESCE(telefon,?), "
                   "manzil=COALESCE(manzil,?) WHERE id=?", eski["tg_id"], eski.get("masul_id"), eski["telefon"],
                   eski.get("manzil"), kimga)
        baza.bajar("UPDATE mijoz SET birlashdi=?, tg_id=NULL WHERE id=?", kimga, mid)
        baza.jurnal(o["id"], "mijoz_birlashtirildi", f"mijoz:{mid}", None, {"kimga": kimga})
    return {"ok": True}


# ---------- xulosa (S6, S8) ----------

@app.get("/api/xulosa")
def xulosa_api(request: Request, o: dict = Depends(boshliq_kerak)):
    tur = request.query_params.get("tur") or "kun"
    x = xulosa.oxirgi(tur)
    return {"xulosa": {k: x[k] for k in ("tur", "sana", "matn", "qolip", "vaqt")} if x else None,
            "vaqt": baza.sozlama("brifing_vaqti", "08:30")}


@app.post("/api/xulosa/yasash")
async def xulosa_yasash_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    x = await xulosa.yasash("hafta" if d.get("tur") == "hafta" else "kun", majburan=True)
    return {"xulosa": {k: x[k] for k in ("tur", "sana", "matn", "qolip", "vaqt")}}


# ---------- xotira arxivi (X1, X6) ----------

@app.get("/api/arxiv")
def arxiv_api(request: Request, o: dict = Depends(joriy)):
    q = (request.query_params.get("q") or "").strip()[:200]
    tur = request.query_params.get("tur") or None
    if tur not in (None, "ovoz", "matn", "rasm", "fayl"):
        tur = None
    if q:
        return {"xabarlar": arxiv.qidir(q, o, limit=30, tur=tur), "qidiruv": True}
    oid = int(request.query_params.get("odam_id") or 0) or None
    return {"xabarlar": arxiv.oxirgilar(o, limit=60, tur=tur, odam_id=oid), "qidiruv": False,
            "odamlar": [{"id": x["id"], "ism": x["ism"]} for x in odamlar.faol_odamlar()] if odamlar.boshliqmi(o) else []}


# ---------- ish usullari (O5) ----------

def _usul_huquq(o: dict) -> bool:
    return o["rol"] in ("boshliq", "menejer") and o["holat"] == "faol"


@app.get("/api/usullar")
def usullar_api(o: dict = Depends(joriy)):
    return {"usullar": usullar.royxat(), "tahrir": _usul_huquq(o)}


@app.post("/api/usul")
async def usul_qosh_api(request: Request, o: dict = Depends(joriy)):
    if not _usul_huquq(o):
        raise HTTPException(403, "Usulni boshliq yoki menejer yozadi")
    d = await request.json()
    return {"id": usullar.qosh(d.get("sarlavha", ""), d.get("matn", ""), o["id"])}


@app.post("/api/usul/{uid}")
async def usul_tahrir_api(uid: int, request: Request, o: dict = Depends(joriy)):
    if not _usul_huquq(o):
        raise HTTPException(403, "Usulni boshliq yoki menejer yozadi")
    d = await request.json()
    if d.get("ochir"):
        usullar.ochir(uid, o["id"])
    else:
        usullar.tahrir(uid, o["id"], d.get("sarlavha", ""), d.get("matn", ""))
    return {"ok": True}


# ---------- Excel (E5) ----------

def _excel(baytlar: bytes, nom: str) -> Response:
    return Response(baytlar, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"', "Cache-Control": "no-store"})


@app.get("/api/eksport/kassa")
def eksport_kassa_api(request: Request, o: dict = Depends(joriy)):
    if not (odamlar.boshliqmi(o) or odamlar.mumkin(o, "kassa")):
        raise HTTPException(403, "Ruxsat yo'q")
    bugun = vaqt.bugun()
    dan = (request.query_params.get("dan") or vaqt.oy_boshi(vaqt.oy(bugun)).isoformat())[:10]
    gacha = (request.query_params.get("gacha") or bugun.isoformat())[:10]
    vaqt.sana(dan), vaqt.sana(gacha)
    return _excel(eksport.kassa(o, dan, gacha), eksport.fayl_nomi("kassa", f"{dan}_{gacha}"))


@app.get("/api/eksport/maosh")
def eksport_maosh_api(request: Request, o: dict = Depends(boshliq_kerak)):
    oy = (request.query_params.get("oy") or vaqt.oy(vaqt.bugun()))[:7]
    vaqt.oy_boshi(oy)
    return _excel(eksport.maosh_(oy), eksport.fayl_nomi("maosh", oy))


@app.get("/api/hisobot")
def hisobot_api(dan: str, gacha: str, o: dict = Depends(boshliq_kerak)):
    """CRM3: davr hisoboti — foyda-zarar, xarajat turlari, sotuv (mijoz/sotuvchi), kassa aylanmasi, qarzlar muddati."""
    try:
        d = hisobot.davr(dan, gacha)
    except ValueError as x:
        raise HTTPException(400, str(x) or "Sana noto'g'ri")
    p = lambda m: _pul(m)  # noqa: E731 — so'mda
    f = d["foyda"]
    return {"dan": d["dan"], "gacha": d["gacha"],
            "foyda": {k: p(f[k]) for k in ("sotuv", "xarajat", "ishhaqi", "foyda", "kassa_kirim", "kassa_chiqim")}
            | {"oy_yopilmagan": f["oy_yopilmagan"]},
            "xarajat_turlar": [{"nom": x["nom"], "summa": p(x["summa"]), "ulush": x["ulush"]} for x in d["xarajat_turlar"]],
            "sotuv_mijoz": [{"id": x["id"], "ism": x["ism"], "soni": x["soni"], "summa": p(x["summa"])} for x in d["sotuv_mijoz"]],
            "sotuv_sotuvchi": [{"ism": x["ism"], "soni": x["soni"], "summa": p(x["summa"])} for x in d["sotuv_sotuvchi"]],
            "sotuv_mahsulot": [{"nom": x["nom"], "birlik": x["birlik"], "miqdor": x["miqdor"], "summa": p(x["summa"])}
                               for x in d["sotuv_mahsulot"]],
            "kassalar": [{"nom": k["nom"], **{f_: _pul(k[f_], k["valyuta"]) for f_ in ("boshida", "kirim", "chiqim", "oxirida")}}
                         for k in d["kassalar"]],
            "qarz_yoshi": [{"kalit": b["kalit"], "nom": b["nom"], "soni": b["soni"], "summa": p(b["summa"]),
                            "mijozlar": [{"id": m["id"], "ism": m["ism"], "summa": p(m["summa"]), "muddat": m["muddat"]}
                                         for m in b["mijozlar"][:20]]} for b in d["qarz_yoshi"]]}


@app.get("/api/eksport/hisobot")
def eksport_hisobot_api(dan: str, gacha: str, o: dict = Depends(boshliq_kerak)):
    try:
        d = hisobot.davr(dan, gacha)
    except ValueError as x:
        raise HTTPException(400, str(x) or "Sana noto'g'ri")
    return _excel(eksport.hisobot(d), eksport.fayl_nomi("hisobot", f"{d['dan']}_{d['gacha']}"))


@app.get("/api/eksport/qarzlar")
def eksport_qarzlar_api(o: dict = Depends(joriy)):
    if not (odamlar.boshliqmi(o) or odamlar.mumkin(o, "mijoz_qarz")):
        raise HTTPException(403, "Ruxsat yo'q")
    return _excel(eksport.qarzlar(o), eksport.fayl_nomi("qarzlar", vaqt.bugun().isoformat()))


# ---------- qoidalar ----------

@app.get("/api/qoidalar")
def qoidalar_api(o: dict = Depends(joriy)):
    return {"qoidalar": qoida.faol_qoidalar(), "turlar": {k: v["nom"] for k, v in qoida.TURLAR.items()}}


@app.post("/api/qoida")
async def qoida_qoy_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    qid = qoida.qoy(d["tur"], d.get("param") or {}, o["id"], d.get("matn"))
    return {"id": qid}


@app.post("/api/qoida/matndan")
async def qoida_matndan_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    try:
        r = await ai.qoida_tushun(d.get("matn", ""))
    except ai.AiXato as x:
        raise HTTPException(503, str(x))
    if r["tur"] == "tushmaydi":
        return {"tushmadi": True, "sabab": r.get("sabab") or "Bu qoidani dastur tekshira olmaydi"}
    param = {"foiz": r["foiz"], "soni": r["soni"], "kamida": r["soni"] or 3, "summa": matn.minor(r["summa"], r["valyuta"]),
             "valyuta": r["valyuta"]}
    try:
        p = qoida.tozala(r["tur"], param)
    except qoida.QoidaXato as x:
        return {"tushmadi": True, "sabab": str(x)}
    return {"tur": r["tur"], "param": p, "matn": qoida.qoida_matni(r["tur"], p)}


@app.post("/api/qoida/{qid}/ochir")
def qoida_ochir_api(qid: int, o: dict = Depends(boshliq_kerak)):
    qoida.ochir(qid, o["id"])
    return {"ok": True}


# ---------- savol (miya) ----------

@app.post("/api/sorash")
async def sorash_api(request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    savol = (d.get("savol") or "").strip()[:500]
    if not savol:
        raise HTTPException(400, "Savol bo'sh")
    try:
        r = await ai.sora(savol, o)
    except ai.AiXato as x:
        raise HTTPException(503, str(x))
    return {"javob": r["javob"], "qolip": r["qolip"],
            "manbalar": [{"asbob": n, "natija": d_} for n, d_ in r["manbalar"]]}


def _davomat_va_muammo(natija: dict, o: dict) -> list[dict]:
    """Chatdagi «keldim», «ketdim», «kecha keldim, unutibman», muammo — bot bilan bir xil (R9)."""
    q = []
    for dv in (natija.get("davomat") or [])[:2]:
        try:
            if dv.get("tur") in ("keldi", "ketdi"):
                r = davomat.belgila(o["id"])
                if r["tur"] == "keldi":
                    m = f"Keldingiz: {r['vaqt'][11:16]}" + (f" · {r['kechikish']} daqiqa kechikish" if r["kechikish"] else "")
                elif r["tur"] == "ketdi":
                    m = f"Ketdingiz: {r['vaqt'][11:16]}"
                else:
                    m = "Bugun kelish va ketish allaqachon belgilangan"
                q.append({"tur": "davomat", "matn": m})
            elif dv.get("tur") == "unutilgan" and dv.get("sana"):
                davomat.sorov(o["id"], dv["sana"][:10], dv.get("izoh") or None)
                q.append({"tur": "davomat", "matn": f"{vaqt.sana_matn(dv['sana'][:10])} kuni uchun so'rov boshliqqa yuborildi"})
        except (ValueError, davomat.DavomatXato) as x:
            q.append({"tur": "davomat", "matn": str(x)})
    if (natija.get("muammo") or "").strip():
        boss = odamlar.boshliq()
        if boss and boss["id"] != o["id"]:
            hisob.xabarnoma(boss["id"], "malumot", f"{o['ism']} muammo aytdi: {natija['muammo'][:500]}")
            q.append({"tur": "muammo", "matn": "Muammo boshliqqa yetkazildi"})
    return q


async def _miya_ishla(matn_: str, o: dict) -> dict:
    """Bitta miya (R9): savol → javob; pul/ish/va'da → kartochkalar (tasdiq bilan); qolgan hamma gap → xotira (darhol)."""
    if matn.norm(matn_).strip(" .!") in bot_m.GAPLASHUV:  # «salom», «rahmat» — Claude chaqirilmaydi
        return {"tur": "tushunilmadi", "sabab": "Savol yoki topshiriq yozing"}

    async def javob():
        r = await ai.sora(matn_, o)
        return {"tur": "javob", "javob": r["javob"], "qolip": r["qolip"],
                "manbalar": [{"asbob": n, "natija": d_} for n, d_ in r["manbalar"]]}
    # R8: web'da yozilgan gap ham umumiy xotiraga (arxiv, «nima kelishgan edik?» qidiruvi)
    xid = baza.bajar("INSERT INTO xabar(odam_id,tur,matn,vaqt,holat) VALUES(?,?,?,?,'ishlandi')", o["id"], "matn", matn_,
                     vaqt.iso())
    try:
        if bot_m.savolmi(matn_):
            return await javob()
        natija = await ai.tushun(matn_, o, ochiq_ishlar=ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True))
        eslab = xotira.saqla_natija(natija.get("xotira"), o, xid)  # R5: pul emas — darhol saqlanadi
        eslab += _davomat_va_muammo(natija, o)
        takliflar = panel_taklif.yasash(natija, o)
        if not takliflar and not eslab and (natija.get("savol") or "").strip():
            return await javob()
    except ai.AiXato as x:
        raise HTTPException(503, str(x))
    if eslab and not takliflar:
        return {"tur": "xotira", "xotira": eslab}
    if not takliflar:
        return {"tur": "tushunilmadi", "sabab": natija.get("tushunilmadi") or "Bu gapdan yozuv yoki ish topilmadi"}
    return {"tur": "takliflar", "takliflar": takliflar, "xotira": eslab}


@app.post("/api/miya")
async def miya_api(request: Request, o: dict = Depends(joriy)):
    """Bosh sahifadagi miya qatori (tarixsiz)."""
    d = await request.json()
    matn_ = (d.get("matn") or "").strip()[:1500]
    if not matn_:
        raise HTTPException(400, "Bo'sh")
    return await _miya_ishla(matn_, o)


# ---------- CRM1: kalendar va eslatmalar (chatsiz) ----------

def _xotira_json(x: dict) -> dict:
    yozgan, kimga = odamlar.odam(x["yozgan_id"]), odamlar.odam(x["kimga_id"]) if x["kimga_id"] else None
    return {"id": x["id"], "tur": x["tur"], "matn": x["matn"], "sana": x["sana"], "soat": x["soat"], "holat": x["holat"],
            "eslat_vaqt": x["eslat_vaqt"], "eslatildi": x["eslatildi"], "iqtibos": x["iqtibos"],
            "yozgan": yozgan["ism"] if yozgan else None, "kimga_id": x["kimga_id"], "kimga": kimga["ism"] if kimga else None,
            "qachon": xotira.qachon(x), "vaqt": x["vaqt"]}


@app.get("/api/xotira")
def xotira_royxat_api(request: Request, o: dict = Depends(joriy)):
    q = request.query_params
    royxat = xotira.royxat(q.get("dan") or None, q.get("gacha") or None, q.get("sorov") or "",
                           faqat_ochiq=q.get("ochiq") == "1", limit=min(int(q.get("limit") or 200), 500))
    if q.get("tur") in xotira.TURLAR:
        royxat = [x for x in royxat if x["tur"] == q["tur"]]
    return {"xotira": [_xotira_json(x) for x in royxat]}


@app.post("/api/xotira")
async def xotira_qosh_api(request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    try:
        xid = xotira.qosh(d.get("tur"), d.get("matn") or "", o["id"], d.get("sana") or None, d.get("soat") or None,
                          int(d["kimga_id"]) if d.get("kimga_id") else None)
    except xotira.XotiraXato as x:
        raise HTTPException(400, str(x))
    x = xotira.bir(xid)
    return {"xotira": _xotira_json(x), "matn": xotira.tasdiq_matni(x)}


@app.post("/api/xotira/{xid}")
async def xotira_tahrir_api(xid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    try:
        if d.get("holat"):
            xotira.holat_qoy(xid, d["holat"], o["id"])
            x = xotira.bir(xid)
        else:
            x = xotira.tahrirla(xid, o["id"], d.get("tur"), d.get("matn"), d.get("sana", ""), d.get("soat", ""),
                                (int(d["kimga_id"]) if d.get("kimga_id") else None) if "kimga_id" in d else -1)
    except xotira.XotiraXato as e_:
        raise HTTPException(400, str(e_))
    return {"xotira": _xotira_json(x), "matn": xotira.tasdiq_matni(x).replace("Eslab qoldim", "Saqlandi", 1)}


@app.get("/api/kalendar")
def kalendar_api(dan: str, gacha: str, o: dict = Depends(joriy)):
    """Bitta kalendar: uchrashuv/eslatmalar, ish muddatlari, va'dalar, maosh kunlari (CRM1)."""
    dan, gacha = dan[:10], gacha[:10]
    if dan > gacha:
        raise HTTPException(400, "Sana oralig'i noto'g'ri")
    voqealar = []
    for x in xotira.royxat(dan, gacha, limit=500):
        voqealar.append({"tur": x["tur"], "id": x["id"], "sana": x["sana"], "soat": x["soat"] or "", "matn": x["matn"],
                         "holat": x["holat"], "kim": (odamlar.odam(x["kimga_id"] or x["yozgan_id"]) or {}).get("ism")})
    bugun = vaqt.bugun().isoformat()
    for i in ishlar.ishlar(korish=ai.umumiy_korish(o), dan=dan, gacha=gacha):
        if i["holat"] == "bekor" or not i["muddat"]:
            continue
        voqealar.append({"tur": "ish", "id": i["id"], "sana": i["muddat"], "soat": i["soat"] or "", "matn": i["nom"],
                         "holat": i["holat"], "kim": ", ".join(x["ism"] for x in i["ijrochilar"]),
                         "kechikkan": i["holat"] in ishlar.OCHIQ and i["muddat"] < bugun})
    for v in vadalar.royxat(dan=dan, gacha=gacha):
        if v["holat"] == "bekor":
            continue
        voqealar.append({"tur": "vada", "id": v["id"], "sana": v["muddat"], "soat": "", "holat": v["holat_h"],
                         "matn": f"{v.get('mijoz') or ''}: " + (matn.pul(v["qolgan"] if v.get("qolgan") is not None else v["summa"],
                                                                        v["valyuta"]) if v["summa"] else v["matn"] or "va'da"),
                         "kim": v.get("mijoz") or ""})
    d = vaqt.sana(dan)
    while d.isoformat() <= gacha:
        if d.day in maosh.maosh_kunlari():
            voqealar.append({"tur": "maosh", "id": None, "sana": d.isoformat(), "soat": "", "matn": "Maosh kuni", "holat": ""})
        d = d.fromordinal(d.toordinal() + 1)
    voqealar.sort(key=lambda v: (v["sana"], v["soat"] or "99", v["tur"]))
    return {"voqealar": voqealar, "bugun": bugun}


# ---------- CRM4: umumiy qidiruv ----------

@app.get("/api/qidiruv")
def qidiruv_api(q: str = "", o: dict = Depends(boshliq_kerak)):
    r = izlash.izla(q, o)
    return {"q": q,
            "mijozlar": [{"id": m["id"], "ism": m["ism"], "tur": m["tur"], "telefon": m["telefon"], "manzil": m["manzil"],
                          "arxiv": bool(m["arxiv"])} for m in r["mijozlar"]],
            "buyurtmalar": [_buyurtma_json(b) for b in r["buyurtmalar"]],
            "ishlar": [_ish_json(i) for i in r["ishlar"]],
            "yozuvlar": [_harakat_json(h) for h in r["yozuvlar"]],
            "xotira": [_xotira_json(x) for x in r["xotira"]],
            "xabarlar": [{"id": x["id"], "kim": x["kim"], "vaqt": x["vaqt"], "parcha": x["parcha"], "tur": x["tur_nomi"]}
                         for x in r["xabarlar"]]}


# ---------- CRM6: katalog va buyurtmalar ----------

def _katalog_json(k: dict) -> dict:
    return {"id": k["id"], "nom": k["nom"], "tur": k["tur"], "birlik": k["birlik"], "narx": _pul(k["narx"], k["valyuta"]),
            "valyuta": k["valyuta"], "tannarx": _pul(k["tannarx"], k["valyuta"]) if k["tannarx"] is not None else None,
            "izoh": k["izoh"], "faol": bool(k["faol"])}


def _buyurtma_json(b: dict, toliq: bool = False) -> dict:
    v = b["valyuta"]
    d = {"id": b["id"], "mijoz_id": b["mijoz_id"], "mijoz": b["mijoz"], "bosqich": b["bosqich"],
         "bosqich_nomi": buyurtma.NOMI[b["bosqich"]], "jami": _pul(b["jami"], v), "chegirma": _pul(b["chegirma"], v),
         "valyuta": v, "manzil": b["manzil"], "muddat": b["muddat"], "masul_id": b["masul_id"], "masul": b["masul"],
         "izoh": b["izoh"], "sotuv_id": b["sotuv_id"], "ish_id": b["ish_id"], "bekor_sabab": b["bekor_sabab"],
         "yaratilgan": b["yaratilgan"], "bosqich_vaqt": b["bosqich_vaqt"],
         "bosqichda_kun": (vaqt.bugun() - vaqt.sana(b["bosqich_vaqt"])).days,
         "qatorlar": [{"id": q["id"], "katalog_id": q["katalog_id"], "nom": q["nom"], "birlik": q["birlik"], "miqdor": q["miqdor"],
                       "narx": _pul(q["narx"], v), "summa": _pul(round(q["miqdor"] * q["narx"]), v)} for q in b["qatorlar"]]}
    if toliq:
        d["tarix"] = [{"matn": t["matn"], "kim": t["kim"], "vaqt": t["vaqt"], "bosqich": t["bosqich"]} for t in b["tarix"]]
        if b["sotuv_id"]:
            h = hisob.harakat(b["sotuv_id"])
            d["sotuv"] = {"holat": h["holat"], "tavsif": hisob.qisqa_tavsif(h)} if h else None
            d["qarz"] = _pul(hisob.qoldiq(f"mijoz:{b['mijoz_id']}").get(v, 0), v)
    return d


def _qatorlar_minor(qatorlar: list | None, valyuta: str) -> list | None:
    if qatorlar is None:
        return None
    return [{"katalog_id": q.get("katalog_id"), "nom": q.get("nom"), "birlik": q.get("birlik"), "miqdor": q.get("miqdor"),
             "narx": matn.minor(float(q["narx"]), valyuta) if q.get("narx") not in (None, "") else None} for q in qatorlar]


@app.get("/api/katalog")
def katalog_api(request: Request, o: dict = Depends(joriy)):
    q = request.query_params
    return {"katalog": [_katalog_json(k) for k in buyurtma.katalog(q.get("hammasi") != "1", q.get("q") or "")]}


@app.post("/api/katalog")
@app.post("/api/katalog/{kid}")
async def katalog_saqla_api(request: Request, kid: int | None = None, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    v = d.get("valyuta") or "UZS"
    kid = buyurtma.katalog_saqla(kid, o["id"], d.get("nom") or "", d.get("tur") or "mahsulot", d.get("birlik") or "dona",
                                 matn.minor(float(d.get("narx") or 0), v), v,
                                 matn.minor(float(d["tannarx"]), v) if d.get("tannarx") not in (None, "") else None,
                                 d.get("izoh"), d.get("faol", True))
    return _katalog_json(baza.bir("SELECT * FROM katalog WHERE id=?", kid))


@app.get("/api/buyurtmalar")
def buyurtmalar_api(request: Request, o: dict = Depends(boshliq_kerak)):
    q = request.query_params
    royxat = buyurtma.royxat(q.get("bosqich") or None, int(q["mijoz_id"]) if q.get("mijoz_id") else None, q.get("q") or "")
    return {"buyurtmalar": [_buyurtma_json(b) for b in royxat], "bosqichlar": buyurtma.NOMI}


@app.get("/api/buyurtma/{bid}")
def buyurtma_bir_api(bid: int, o: dict = Depends(boshliq_kerak)):
    b = buyurtma.bir(bid)
    if not b:
        raise HTTPException(404, "Topilmadi")
    return _buyurtma_json(b, toliq=True)


@app.post("/api/buyurtma")
async def buyurtma_yarat_api(request: Request, o: dict = Depends(joriy)):
    """Boshliq — panelda; xodim — chat kartochkasidan (CRM7, R3: boshliq nomidan). Pul emas — R4 tasdig'i kerak emas."""
    boss = odamlar.boshliqmi(o)
    if not boss and o["holat"] != "faol":
        raise HTTPException(403, "Ruxsat yo'q")
    d = await request.json()
    v = d.get("valyuta") or "UZS"
    masul = int(d["masul_id"]) if d.get("masul_id") else None if boss else o["id"]  # xodim ochsa — mas'ul o'zi
    bid = buyurtma.yarat(int(d.get("mijoz_id") or 0), o["id"], _qatorlar_minor(d.get("qatorlar") or [], v),
                         matn.minor(float(d.get("chegirma") or 0), v), v, d.get("manzil"), d.get("muddat"),
                         masul, d.get("izoh"))
    buyurtma.xodimdan_xabar(bid, o)
    return _buyurtma_json(buyurtma.bir(bid), toliq=True)


@app.post("/api/buyurtma/{bid}")
async def buyurtma_tahrir_api(bid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    b = buyurtma.bir(bid)
    if not b:
        raise HTTPException(404, "Topilmadi")
    v = d.get("valyuta") or b["valyuta"]
    o_ = {k: d.get(k) for k in ("manzil", "izoh", "muddat")}
    if "masul_id" in d:
        o_["masul_id"] = int(d["masul_id"]) if d["masul_id"] else None
    if d.get("mijoz_id"):
        o_["mijoz_id"] = int(d["mijoz_id"])
    if "qatorlar" in d:
        o_["qatorlar"] = _qatorlar_minor(d["qatorlar"], v)
    if d.get("chegirma") is not None:
        o_["chegirma"] = matn.minor(float(d["chegirma"] or 0), v)
    if d.get("valyuta"):
        o_["valyuta"] = v
    return _buyurtma_json(buyurtma.tahrirla(bid, o["id"], **o_), toliq=True)


@app.post("/api/buyurtma/{bid}/bosqich")
async def buyurtma_bosqich_api(bid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    return _buyurtma_json(buyurtma.bosqich_qoy(bid, o["id"], d.get("bosqich") or "", d.get("sabab") or ""), toliq=True)


@app.post("/api/buyurtma/{bid}/sotildi")
async def buyurtma_sotildi_api(bid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    b = buyurtma.bir(bid)
    if not b:
        raise HTTPException(404, "Topilmadi")
    v = b["valyuta"]
    ish = d.get("ish") or None
    if ish:
        ish = {**ish, "narx": matn.minor(float(ish["narx"]), v) if ish.get("narx") not in (None, "", 0) else None}
    r = buyurtma.sotildi(bid, o["id"], matn.minor(float(d.get("tolandi") or 0), v),
                         int(d["kassa_id"]) if d.get("kassa_id") else None, d.get("qarz_muddati"), ish)
    return {"holat": r["holat"], "sotuv_id": r["sotuv_id"], "ish_id": r["ish_id"], "buyurtma": _buyurtma_json(r["buyurtma"], toliq=True)}


# ---------- chat (R1–R2, R9): boshliq ham, xodimlar ham — bitta miya ----------

def _chat_qisqa(r: dict) -> str:
    if r["tur"] == "javob":
        return r["javob"]
    if r["tur"] == "tushunilmadi":
        return r["sabab"]
    q = [x["matn"] for x in r.get("xotira") or []]
    if r.get("takliflar"):
        q.append(f"{len(r['takliflar'])} ta yozuv tasdiqlashni kutmoqda")
    return "\n".join(q)


def _tugma_holati(data: str, o: dict) -> bool:
    """Xabarnoma tugmasi hali kerakmi (Telegram'da yoki web'da javob berilgan bo'lsa — yo'q)."""
    q = data.split(":")
    try:
        if q[0] == "r":
            h = hisob.harakat(int(q[1]))
            return bool(h) and h["holat"] == "ruxsat_kutilmoqda" and odamlar.boshliqmi(o)
        if q[0] == "n":
            h = hisob.harakat(int(q[1]))
            return bool(h) and h["holat"] == "nizo" and odamlar.boshliqmi(o)
        if q[0] == "t":
            h = hisob.harakat(int(q[1]))
            tomon = {"o": "oluvchi", "b": "beruvchi"}[q[2]]
            return bool(h) and h["holat"] == "faol" and h[f"{tomon}_holat"] == "kutilmoqda" and h[f"{tomon}_id"] == o["id"]
        if q[0] in ("xb", "xk"):
            x = xotira.bir(int(q[1]))
            return bool(x) and x["holat"] == "ochiq"
    except (ValueError, KeyError, IndexError):
        return False
    return False  # boshqa tugmalar hozircha faqat Telegram'da


def _chat_element(r: dict, manba: str, o: dict) -> dict:
    if manba == "c":
        return {"k": f"c{r['id']}", "kim": r["kim"], "matn": r["matn"], "vaqt": r["vaqt"],
                "malumot": json.loads(r["malumot"]) if r["malumot"] else None}
    tug = json.loads(r["tugmalar"] or "[]")
    qatorlar = tug if tug and isinstance(tug[0][0], list) else [tug] if tug else []
    tugmalar = [[t[0], t[1]] for qator in qatorlar for t in qator if _tugma_holati(t[1], o)]
    holat = None  # javob berilgan savol — qayta ochilganda natijasi ko'rinsin
    if qatorlar and not tugmalar:
        q = qatorlar[0][0][1].split(":")
        if q[0] in ("r", "t", "n") and q[1].isdigit():
            h = hisob.harakat(int(q[1]))
            holat = {"faol": "✓ Tasdiqlangan", "bekor": "✗ Rad etilgan", "nizo": "Nizo — boshliqda"}.get(h["holat"]) if h else None
        elif q[0] in ("xb", "xk") and q[1].isdigit():
            x = xotira.bir(int(q[1]))
            holat = {"bajarildi": "✓ Bajarildi", "bekor": "Bekor qilingan"}.get(x["holat"]) if x else None
    return {"k": f"n{r['id']}", "kim": "miya", "matn": r["matn"], "vaqt": r["vaqt"], "tur": r["tur"], "tugmalar": tugmalar,
            "holat": holat}


@app.get("/api/chat")
def chat_tarix_api(keyin: str | None = None, o: dict = Depends(joriy)):
    """Chat tarixi: o'zi yozgani, miya javoblari va miya o'zi yuborganlari (eslatma, tasdiq so'rovi, xulosa)."""
    shart, p = ("AND vaqt>?", [keyin]) if keyin else ("", [])
    c = baza.hammasi(f"SELECT * FROM chat WHERE odam_id=? {shart} ORDER BY id DESC LIMIT 80", o["id"], *p)
    n = baza.hammasi(f"SELECT * FROM xabarnoma WHERE odam_id=? {shart} ORDER BY id DESC LIMIT 60", o["id"], *p)
    hammasi = [_chat_element(r, "c", o) for r in c] + [_chat_element(r, "n", o) for r in n]
    hammasi.sort(key=lambda x: (x["vaqt"], x["k"]))
    return {"xabarlar": hammasi[-100:], "hozir": vaqt.iso()}


@app.post("/api/chat")
async def chat_yoz_api(request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    matn_ = (d.get("matn") or "").strip()[:1500]
    if not matn_:
        raise HTTPException(400, "Bo'sh")
    cid = baza.bajar("INSERT INTO chat(odam_id,kim,matn,vaqt) VALUES(?,?,?,?)", o["id"], "odam", matn_, vaqt.iso())
    r = await _miya_ishla(matn_, o)
    mid = baza.bajar("INSERT INTO chat(odam_id,kim,matn,malumot,vaqt) VALUES(?,?,?,?,?)", o["id"], "miya",
                     _chat_qisqa(r) or "—", json.dumps(r, ensure_ascii=False, default=str), vaqt.iso())
    return {"odam": _chat_element(baza.bir("SELECT * FROM chat WHERE id=?", cid), "c", o),
            "miya": _chat_element(baza.bir("SELECT * FROM chat WHERE id=?", mid), "c", o)}


@app.post("/api/chat/{cid}/yakun")
async def chat_yakun_api(cid: int, request: Request, o: dict = Depends(joriy)):
    """Kartochkalar tasdiqlandi yoki bekor qilindi — qayta ochilganda yana chiqmasin."""
    c = baza.bir("SELECT * FROM chat WHERE id=? AND odam_id=? AND kim='miya'", cid, o["id"])
    if not c:
        raise HTTPException(404, "Topilmadi")
    d = await request.json()
    r = json.loads(c["malumot"] or "{}")
    r["yakun"] = [str(x)[:300] for x in d.get("natija") or []][:20]
    baza.bajar("UPDATE chat SET malumot=? WHERE id=?", json.dumps(r, ensure_ascii=False, default=str), cid)
    return {"ok": True}


@app.post("/api/chat/tugma")
async def chat_tugma_api(request: Request, o: dict = Depends(joriy)):
    """Miya yuborgan xabardagi tugma (tasdiqlash, rad, bajarildi) — Telegram'dagi bilan bir xil amal."""
    data = ((await request.json()).get("data") or "")
    if not _tugma_holati(data, o):
        raise HTTPException(409, "Bu savolga allaqachon javob berilgan")
    q = data.split(":")
    if q[0] == "r":
        hisob.ruxsat(int(q[1]), o["id"], q[2] == "1")
        return {"matn": "✓ Tasdiqlandi" if q[2] == "1" else "✗ Rad etildi"}
    if q[0] == "n":
        hisob.nizo_hal(int(q[1]), o["id"], q[2] == "1")
        return {"matn": "✓ Berilgan deb hisoblandi" if q[2] == "1" else "✗ Bekor qilindi"}
    if q[0] == "t":
        hisob.tomon_tasdiq(int(q[1]), o["id"], {"o": "oluvchi", "b": "beruvchi"}[q[2]], q[3] == "1")
        return {"matn": "✓ Tasdiqladingiz" if q[3] == "1" else "✗ Rad etdingiz — boshliqqa yuborildi"}
    xotira.holat_qoy(int(q[1]), "bajarildi" if q[0] == "xb" else "bekor", o["id"])
    return {"matn": "✓ Bajarildi" if q[0] == "xb" else "Bekor qilindi"}


# ---------- sozlamalar ----------

@app.get("/api/sozlamalar")
def sozlamalar_api(o: dict = Depends(boshliq_kerak)):
    oy = vaqt.oy(vaqt.bugun())
    sarf = baza.bir("SELECT COALESCE(SUM(narx),0) narx, COUNT(*) soni FROM ai_sarf WHERE substr(vaqt,1,7)=?", oy)
    stt = baza.bir("SELECT COALESCE(SUM(narx),0) narx, COALESCE(SUM(soniya),0) soniya FROM stt_sarf WHERE substr(vaqt,1,7)=?", oy)
    return {"ai_model": ai.model(), "modellar": list(ai.NARX), "maosh_kunlari": maosh.maosh_kunlari(),
            "kassa_sanoq_vaqti": baza.sozlama("kassa_sanoq_vaqti", "19:00"), "domen": baza.sozlama("domen", ""),
            "guruh_ovoz": bool(baza.sozlama("guruh_ovoz", False)),
            "kalitlar": {"bot": bool(bot_token()), "anthropic": bool(ai.kalit()), "google": bool(ovoz.kalit())},
            "bot_ishlayapti": bool(BOT), "bot_nomi": baza.sozlama("bot_nomi"), "bot_xato": BOT.oxirgi_xato if BOT else None,
            "sarf": {"ai_dollar": round(sarf["narx"], 2), "ai_soni": sarf["soni"], "ovoz_dollar": round(stt["narx"], 2),
                     "ovoz_daqiqa": round(stt["soniya"] / 60, 1)},
            "xarajat_turlari": baza.hammasi("SELECT * FROM xarajat_turi ORDER BY faol DESC, nom"),
            "zaxira": baza.sozlama("oxirgi_zaxira"), "zaxira_yol2": baza.sozlama("zaxira_yol2", ""),
            "ertalab_vaqti": baza.sozlama("ertalab_vaqti", "08:00"), "kechki_vaqt": baza.sozlama("kechki_vaqt", "18:00"),
            "brifing_vaqti": baza.sozlama("brifing_vaqti", "08:30"),
            "ish_boshlanishi": davomat.ish_boshlanishi(), "dam_olish_kunlari": baza.sozlama("dam_olish_kunlari", [6]),
            "dalil_standart": baza.sozlama("dalil_standart", "rasm"), "ofis_joylashuvi": davomat.ofis()}


@app.post("/api/sozlamalar")
async def sozlamalar_saqla(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    if "ai_model" in d:
        if d["ai_model"] not in ai.NARX:
            raise HTTPException(400, "Noma'lum model")
        baza.sozlama_qoy("ai_model", d["ai_model"], o["id"])
    if "maosh_kunlari" in d:
        kunlar = sorted({int(x) for x in d["maosh_kunlari"] if 1 <= int(x) <= 28})
        if not kunlar:
            raise HTTPException(400, "Maosh kunlari 1–28 oralig'ida bo'lsin")
        baza.sozlama_qoy("maosh_kunlari", kunlar, o["id"])
    if "kassa_sanoq_vaqti" in d:
        v = str(d["kassa_sanoq_vaqti"])
        if not (len(v) == 5 and v[2] == ":" and v[:2].isdigit() and v[3:].isdigit()):
            raise HTTPException(400, "Vaqt SS:DD ko'rinishida bo'lsin")
        baza.sozlama_qoy("kassa_sanoq_vaqti", v, o["id"])
    if "domen" in d:
        dm = (d["domen"] or "").strip().rstrip("/")
        if dm and not dm.startswith("https://"):
            raise HTTPException(400, "Domen https:// bilan boshlansin")
        baza.sozlama_qoy("domen", dm, o["id"])
    if "guruh_ovoz" in d:
        baza.sozlama_qoy("guruh_ovoz", bool(d["guruh_ovoz"]), o["id"])
    for kalit in ("ertalab_vaqti", "kechki_vaqt", "ish_boshlanishi", "brifing_vaqti"):
        if kalit in d:
            v = str(d[kalit])
            if not (len(v) == 5 and v[2] == ":" and v[:2].isdigit() and v[3:].isdigit()):
                raise HTTPException(400, "Vaqt SS:DD ko'rinishida bo'lsin")
            baza.sozlama_qoy(kalit, v, o["id"])
    if "dam_olish_kunlari" in d:
        baza.sozlama_qoy("dam_olish_kunlari", sorted({int(x) for x in d["dam_olish_kunlari"] if 0 <= int(x) <= 6}), o["id"])
    if "dalil_standart" in d:
        if d["dalil_standart"] not in ishlar.DALIL_NOMI:
            raise HTTPException(400, "Dalil turi noto'g'ri")
        baza.sozlama_qoy("dalil_standart", d["dalil_standart"], o["id"])
    if "ofis_joylashuvi" in d:
        oj = d["ofis_joylashuvi"]
        if oj:
            lat, lon = float(oj["lat"]), float(oj["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise HTTPException(400, "Koordinata noto'g'ri")
            baza.sozlama_qoy("ofis_joylashuvi", {"lat": lat, "lon": lon}, o["id"])
        else:
            baza.sozlama_qoy("ofis_joylashuvi", None, o["id"])
    if "zaxira_yol2" in d:
        yol2 = (d["zaxira_yol2"] or "").strip()
        if yol2 and not os.path.isabs(yol2):
            raise HTTPException(400, "Ikkinchi zaxira joyi to'liq yo'l bo'lsin (masalan /mnt/disk2/miya)")
        baza.sozlama_qoy("zaxira_yol2", yol2, o["id"])
    if d.get("xarajat_turi_yangi"):
        baza.bajar("INSERT OR IGNORE INTO xarajat_turi(nom) VALUES(?)", str(d["xarajat_turi_yangi"]).strip()[:60])
    if d.get("xarajat_turi_ochir"):
        baza.bajar("UPDATE xarajat_turi SET faol=0 WHERE id=?", int(d["xarajat_turi_ochir"]))
    return {"ok": True}


@app.post("/api/kalit")
async def kalit_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    tur, q = d.get("tur"), (d.get("qiymat") or "").strip()
    nomlar = {"bot": "maxfiy_bot", "anthropic": "maxfiy_anthropic", "google": "maxfiy_google"}
    if tur not in nomlar:
        raise HTTPException(400, "Noma'lum kalit")
    xato = None
    if q and tur == "anthropic":  # noto'g'ri kalit saqlanmaydi — pulsiz tekshiruv
        xato = await ai.tekshir(q)
    elif q and tur == "google":
        xato = await ovoz.tekshir(q)
    if xato:
        return {"ok": False, "xato": xato}
    baza.sozlama_qoy(nomlar[tur], odamlar.shifrla(q) if q else None, o["id"])
    if tur == "bot":
        xato = await bot_yoq()
    return {"ok": xato is None, "xato": xato}


@app.post("/api/zaxira")
async def zaxira_api(o: dict = Depends(boshliq_kerak)):
    natija = await asyncio.to_thread(zaxira.ol)
    baza.jurnal(o["id"], "zaxira_olindi", None, None, {k: v for k, v in natija.items() if k != "yol"})
    return natija


@app.get("/api/jurnal")
def jurnal_api(request: Request, o: dict = Depends(boshliq_kerak)):
    limit = min(int(request.query_params.get("limit") or 100), 500)
    qatorlar = baza.hammasi("SELECT * FROM jurnal ORDER BY id DESC LIMIT ?", limit)
    for r in qatorlar:
        kim = odamlar.odam(r["kim_id"])
        r["kim"] = kim["ism"] if kim else "Tizim"
    return {"jurnal": qatorlar}


@app.get("/api/fayl/{xabar_id}")
def fayl_api(xabar_id: int, o: dict = Depends(joriy)):
    xb = baza.bir("SELECT * FROM xabar WHERE id=?", xabar_id)
    if not xb or not xb["fayl"] or xb["yashirin"]:
        raise HTTPException(404, "Fayl topilmadi")
    if not (odamlar.boshliqmi(o) or xb["odam_id"] == o["id"] or o["rol"] in ("kassir", "menejer")):
        raise HTTPException(403, "Ruxsat yo'q")
    return FileResponse(xb["fayl"])


# ---------- ishlar (I) ----------

@app.get("/api/ishlar")
def ishlar_api(request: Request, o: dict = Depends(joriy)):
    q = request.query_params
    f = q.get("f") or "ochiq"
    royxat = ishlar.ishlar(korish=o, odam_id=int(q["odam_id"]) if q.get("odam_id") else None,
                           faqat_ochiq=f == "ochiq", qabul_kerak=f == "qabul",
                           holatlar=("bajarildi", "qabul") if f == "bajarilgan" else None,
                           dan=q.get("dan") or None, gacha=q.get("gacha") or None)
    return {"ishlar": [_ish_json(i) for i in royxat], "turlar": sorted({i["ish_turi"] for i in royxat if i["ish_turi"]})}


@app.post("/api/ish")
async def ish_yarat_api(request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    ijr = [(int(x["odam_id"]), float(x.get("ulush") or 1)) for x in d.get("ijrochilar") or []]
    valyuta = d.get("valyuta") or "UZS"
    narx = matn.minor(float(d["narx"]), valyuta) if d.get("narx") else None
    iid, _ = ishlar.ish_yarat(d.get("nom", ""), ijr, o["id"], joy=d.get("joy") or None, mijoz_id=d.get("mijoz_id") or None,
                              muddat=d.get("muddat") or None, soat=d.get("soat") or None, narx=narx, valyuta=valyuta,
                              dalil_turi=d.get("dalil_turi"), ish_turi=d.get("ish_turi"), tavsif=d.get("tavsif"),
                              lat=d.get("lat"), lon=d.get("lon"))
    return {"id": iid}


@app.get("/api/ish/{iid}")
def ish_bir_api(iid: int, o: dict = Depends(joriy)):
    i = ishlar.ish(iid)
    if not i or not ishlar.korishi_mumkin(o, i):
        raise HTTPException(404, "Ish topilmadi")
    return _ish_json(i)


@app.post("/api/ish/{iid}/amal")
async def ish_amal_api(iid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    amal = d.get("amal")
    if amal == "qabul":
        narx = matn.minor(float(d["narx"]), ishlar.ish(iid)["valyuta"]) if d.get("narx") not in (None, "") else None
        ishlar.qabul(iid, o["id"], narx=narx)
    elif amal == "qayta":
        ishlar.qayta(iid, o["id"], d.get("sabab", ""))
    elif amal == "muddat":
        ishlar.muddat_ozgar(iid, o["id"], d.get("muddat") or None, d.get("sabab", ""))
    elif amal == "bekor":
        ishlar.bekor(iid, o["id"], d.get("sabab", ""))
    elif amal == "bajarildi":
        if not ishlar.tolov_huquqi(o):
            raise HTTPException(403, "Panelda ishni faqat boshliq yoki menejer yopadi — xodim botda yopadi")
        r = ishlar.bajarildi_dedi(iid, o["id"], d.get("izoh"))
        if r["holat"] == "bajarildi_dalil":
            ishlar.dalil_qosh(iid, o["id"], "rasm", izoh=f"panelda {o['ism']} tasdiqladi")
    else:
        raise HTTPException(400, "Noma'lum amal")
    return _ish_json(ishlar.ish(iid))


@app.post("/api/ish/{iid}/tahrir")
async def ish_tahrir_api(iid: int, request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    i = ishlar.ish(iid)
    if not i:
        raise HTTPException(404, "Topilmadi")
    narx = -1
    if "narx" in d:
        narx = matn.minor(float(d["narx"]), i["valyuta"]) if d["narx"] not in (None, "", 0) else None
    ishlar.tahrirla(iid, o["id"], d.get("nom"), d.get("joy"), d.get("muddat", ""), d.get("soat", ""), narx,
                    [int(x) for x in d["ijrochilar"]] if d.get("ijrochilar") is not None else None, d.get("sabab") or "")
    return _ish_json(ishlar.ish(iid))


@app.get("/api/ish_dalil/{dalil_id}")
def ish_dalil_api(dalil_id: int, o: dict = Depends(joriy)):
    r = baza.bir("SELECT * FROM ish_dalil WHERE id=?", dalil_id)
    i = ishlar.ish(r["ish_id"]) if r else None
    if not r or not r["fayl"] or not i or not ishlar.korishi_mumkin(o, i):
        raise HTTPException(404, "Dalil topilmadi")
    return FileResponse(r["fayl"])


@app.get("/api/ish_taklif")
def ish_taklif_api(request: Request, o: dict = Depends(joriy)):
    return {"taklif": ishlar.ijrochi_taklif(request.query_params.get("tur") or None)}


@app.get("/api/takroriy")
def takroriy_api(o: dict = Depends(joriy)):
    r = baza.hammasi("SELECT * FROM takroriy_ish WHERE faol=1 ORDER BY id")
    for x in r:
        x["ijrochilar"] = [{"id": i, "ism": (odamlar.odam(i) or {}).get("ism")} for i in json.loads(x["ijrochilar"])]
    return {"takroriy": r}


@app.post("/api/takroriy")
async def takroriy_qoy_api(request: Request, o: dict = Depends(joriy)):
    d = await request.json()
    valyuta = d.get("valyuta") or "UZS"
    tid = ishlar.takroriy_qoy(d.get("nom", ""), [int(x) for x in d.get("ijrochilar") or []], d.get("davr"),
                              int(d["kun"]) if d.get("kun") not in (None, "") else None, o["id"],
                              narx=matn.minor(float(d["narx"]), valyuta) if d.get("narx") else None, valyuta=valyuta,
                              dalil_turi=d.get("dalil_turi") or "yoq", joy=d.get("joy"), ish_turi=d.get("ish_turi"))
    return {"id": tid}


@app.post("/api/takroriy/{tid}/ochir")
def takroriy_ochir_api(tid: int, o: dict = Depends(joriy)):
    if not ishlar.tolov_huquqi(o):
        raise HTTPException(403, "Faqat boshliq yoki menejer")
    baza.bajar("UPDATE takroriy_ish SET faol=0 WHERE id=?", tid)
    baza.jurnal(o["id"], "takroriy_ochirildi", f"takror:{tid}")
    return {"ok": True}


# ---------- davomat (M3) ----------

@app.get("/api/davomat")
def davomat_api(request: Request, o: dict = Depends(joriy)):
    if not ishlar.tolov_huquqi(o):
        raise HTTPException(403, "Ruxsat yo'q")
    oy = request.query_params.get("oy") or vaqt.oy(vaqt.bugun())
    qatorlar = baza.hammasi("SELECT d.*, o.ism FROM davomat d JOIN odam o ON o.id=d.odam_id WHERE substr(d.sana,1,7)=? "
                            "ORDER BY d.sana DESC, o.ism", oy)
    for r in qatorlar:
        r["kechikish"] = davomat.kechikish(r["keldi"]) if r["keldi"] else 0
        r["masofa"] = davomat.ofisdan_masofa(r["keldi_lat"], r["keldi_lon"])
    return {"oy": oy, "bugun": davomat.bugun_holati(), "qatorlar": qatorlar}


@app.post("/api/davomat/{did}/hal")
async def davomat_hal_api(did: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    davomat.sorov_hal(did, o["id"], bool(d.get("ha")))
    return {"ok": True}


@app.post("/api/davomat/qolda")
async def davomat_qolda_api(request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    davomat.qolda(int(d["odam_id"]), d["sana"], d.get("keldi") or None, d.get("ketdi") or None, o["id"])
    return {"ok": True}


# ---------- xodim kartasi (O1, O2) ----------

@app.get("/api/odam/{oid}/karta")
def odam_karta_api(oid: int, o: dict = Depends(joriy)):
    if oid != o["id"] and not odamlar.boshliqmi(o):
        raise HTTPException(403, "Ruxsat yo'q")
    x = odamlar.odam(oid)
    if not x:
        raise HTTPException(404, "Topilmadi")
    oy = vaqt.oy(vaqt.bugun())
    return {"odam": _ochiq(x) | {"kirgan_sana": x["kirgan_sana"], "yaqin_telefon": x["yaqin_telefon"], "izoh": x["izoh"]},
            "konikma": ishlar.konikma(oid),
            "ochiq_ishlar": [_ish_json(i) for i in ishlar.ishlar(odam_id=oid, faqat_ochiq=True)],
            "davomat_oy": davomat.oy_kunlari(oid, oy),
            "kechikishlar": sum(1 for r in baza.hammasi("SELECT keldi FROM davomat WHERE odam_id=? AND substr(sana,1,7)=? "
                                                         "AND keldi IS NOT NULL AND holat='tasdiq'", oid, oy)
                                if davomat.kechikish(r["keldi"]) > 0),
            "hujjatlar": baza.hammasi("SELECT id, nom, vaqt FROM odam_hujjat WHERE odam_id=? ORDER BY id DESC", oid),
            "shartlar": [{"tur": maosh.SHART_TURI[s["tur"]], "qiymat": s["qiymat"], "valyuta": s["valyuta"],
                          "dan": s["dan_sana"]} for s in maosh.shartlar(oid, oy)] if odamlar.boshliqmi(o) or oid == o["id"] else []}


@app.post("/api/odam/{oid}/qoshimcha")
async def odam_qoshimcha_api(oid: int, request: Request, o: dict = Depends(boshliq_kerak)):
    d = await request.json()
    eski = odamlar.odam(oid)
    with baza.tranz():
        baza.bajar("UPDATE odam SET kirgan_sana=?, yaqin_telefon=?, izoh=? WHERE id=?",
                   d.get("kirgan_sana") or None, d.get("yaqin_telefon") or None, d.get("izoh") or None, oid)
        baza.jurnal(o["id"], "odam_tahrir", f"odam:{oid}",
                    {k: eski[k] for k in ("kirgan_sana", "yaqin_telefon", "izoh")}, d)
    return {"ok": True}


@app.post("/api/odam/{oid}/hujjat")
async def hujjat_yukla_api(oid: int, fayl: UploadFile = File(...), nom: str = Form(""), o: dict = Depends(boshliq_kerak)):
    mazmun = await fayl.read()
    if len(mazmun) > 15 * 1024 * 1024:
        raise HTTPException(400, "Fayl 15 MB dan katta")
    kengaytma = os.path.splitext(fayl.filename or "")[1].lower()
    if kengaytma not in (".jpg", ".jpeg", ".png", ".pdf", ".webp", ".heic"):
        raise HTTPException(400, "Faqat rasm yoki PDF")
    papka = os.path.join(os.path.dirname(os.path.abspath(baza.yol())), "hujjatlar", str(oid))
    os.makedirs(papka, exist_ok=True)
    yol = os.path.join(papka, f"{int(time.time() * 1000)}{kengaytma}")
    with open(yol, "wb") as f:
        f.write(mazmun)
    hid = baza.bajar("INSERT INTO odam_hujjat(odam_id,nom,fayl,yuklagan_id,vaqt) VALUES(?,?,?,?,?)",
                     oid, (nom or fayl.filename or "Hujjat")[:120], yol, o["id"], vaqt.iso())
    baza.jurnal(o["id"], "hujjat_yuklandi", f"odam:{oid}", None, nom or fayl.filename)
    return {"id": hid}


@app.get("/api/hujjat/{hid}")
def hujjat_api(hid: int, o: dict = Depends(joriy)):
    r = baza.bir("SELECT * FROM odam_hujjat WHERE id=?", hid)
    if not r or not (odamlar.boshliqmi(o) or r["odam_id"] == o["id"]):
        raise HTTPException(404, "Topilmadi")
    baza.jurnal(o["id"], "hujjat_korildi", f"odam:{r['odam_id']}", None, r["nom"])
    return FileResponse(r["fayl"])


@app.post("/api/mijoz/{mid}/taklif")
def mijoz_taklif_api(mid: int, o: dict = Depends(joriy)):
    if not (odamlar.boshliqmi(o) or o["rol"] == "menejer"):
        raise HTTPException(403, "Ruxsat yo'q")
    import secrets
    kod = secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")
    baza.bajar("INSERT INTO mijoz_taklif(kod,mijoz_id,yaratilgan) VALUES(?,?,?)", kod, mid, vaqt.iso())
    nom = baza.sozlama("bot_nomi")
    return {"havola": f"https://t.me/{nom}?start=m{kod}" if nom else None, "kod": kod}


# ---------- Telegram oynasi (T3) ----------

def tg_tekshir(init_data: str) -> dict | None:
    """Telegram imzosini tekshiradi — aks holda begona odam boshqaning hisobini ochardi."""
    token = bot_token()
    if not token or not init_data:
        return None
    juftlar = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    xesh = juftlar.pop("hash", None)
    if not xesh:
        return None
    tekshir = "\n".join(f"{k}={v}" for k, v in sorted(juftlar.items()))
    maxfiy = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(maxfiy, tekshir.encode(), hashlib.sha256).hexdigest(), xesh):
        return None
    if time.time() - int(juftlar.get("auth_date", "0")) > 86400:
        return None
    try:
        user = json.loads(juftlar.get("user", "{}"))
    except ValueError:
        return None
    return odamlar.odam_tg(int(user.get("id", 0)))


def ilova_odam(request: Request) -> dict:
    o = tg_tekshir(request.headers.get("x-tg-init", ""))
    if not o:
        raise HTTPException(401, "Telegram orqali oching")
    return o


@app.get("/api/ilova/hisobim")
def ilova_hisobim(request: Request, o: dict = Depends(ilova_odam)):
    v = _varaq_json(maosh.varaq(o["id"], request.query_params.get("oy")))
    v["qolida"] = _pul(hisob.qoldiq_bir(f"qol:{o['id']}"))
    v["kutmoqda_men"] = [_harakat_json(h) for h in baza.hammasi(
        "SELECT * FROM harakat WHERE holat IN ('faol','nizo') AND ((beruvchi_id=? AND beruvchi_holat='kutilmoqda') OR "
        "(oluvchi_id=? AND oluvchi_holat='kutilmoqda')) ORDER BY id DESC", o["id"], o["id"])]
    return v


@app.get("/api/ilova/ishlar")
def ilova_ishlar(request: Request, o: dict = Depends(ilova_odam)):
    return {"ishlar": [_ish_json(i) for i in ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True)]}


@app.post("/api/ilova/dalil")
async def ilova_dalil(request: Request, ish_id: int = Form(...), fayl: UploadFile = File(...),
                      o: dict = Depends(ilova_odam)):
    mazmun = await fayl.read()
    if len(mazmun) > 15 * 1024 * 1024:
        raise HTTPException(400, "Rasm 15 MB dan katta")
    i = ishlar.ish(ish_id)
    if not i:
        raise HTTPException(404, "Ish topilmadi")
    if i["holat"] in ("yangi", "qayta"):
        ishlar.bajarildi_dedi(ish_id, o["id"])
    sana = vaqt.bugun()
    papka = os.path.join(os.path.dirname(os.path.abspath(baza.yol())), "fayllar", f"{sana:%Y}", f"{sana:%m}")
    os.makedirs(papka, exist_ok=True)
    yol = os.path.join(papka, f"ilova-{ish_id}-{int(time.time() * 1000)}.jpg")
    with open(yol, "wb") as f:
        f.write(mazmun)
    r = ishlar.dalil_qosh(ish_id, o["id"], "rasm", fayl=yol)
    return {"holat": r["holat"]}


@app.post("/api/ilova/tomon")
async def ilova_tomon(request: Request, o: dict = Depends(ilova_odam)):
    d = await request.json()
    hisob.tomon_tasdiq(int(d["harakat_id"]), o["id"], d["tomon"], bool(d.get("ha")))
    return {"ok": True}
