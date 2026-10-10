"""Bot uchun umumiy yordamchilar: matn qochirish, menyu, tugmalar, summa va sana o'qish, kartochka saqlash."""
import html
import json
import re
from datetime import date, timedelta

from . import baza, vaqt

JOY = {"text": "Keldim / Ketdim", "request_location": True}
MENYU = {
    "xodim": [["Ishlarim", "Hisobim"], [JOY, "Xarajat"], ["Kutayotganlar", "Yordam"]],
    "kassir": [["Kirim", "Xarajat", "Avans"], ["Sotuv", "Kassa", "Ishlarim"], ["Hisobim", "Kutayotganlar", JOY]],
    "menejer": [["Ishlar", "Sotuv", "Kirim"], ["Ishlarim", "Kutayotganlar", JOY], ["Hisobim", "Yordam"]],
    "boshliq": [["Kirim", "Xarajat", "Avans"], ["Sotuv", "Kassa", "Maosh"], ["Ishlar", "Kutayotganlar", "Yordam"]],
}


def e(s) -> str:
    return html.escape(str(s or ""), quote=False)


def menyu(o: dict) -> dict:
    tugmalar = [["Hisobim"]] if o["holat"] == "ketmoqda" else MENYU.get(o["rol"], MENYU["xodim"])
    return {"keyboard": [[t if isinstance(t, dict) else {"text": t} for t in q] for q in tugmalar],
            "resize_keyboard": True, "is_persistent": True}


def menyu_sozlari(o: dict) -> set:
    return {t["text"] for q in menyu(o)["keyboard"] for t in q}


def _tugma(t: list) -> dict:
    if len(t) > 2 and t[2] == "web":
        return {"text": t[0], "web_app": {"url": t[1]}}
    return {"text": t[0][:60], "callback_data": t[1]}


def inline(tugmalar: list) -> dict:
    """[[matn, data], ...] yoki [[[matn, data], ...], ...] (qatorlar)."""
    qatorlar = []
    for q in tugmalar:
        if q and isinstance(q[0], list):
            qatorlar.append([_tugma(t) for t in q])
        else:
            qatorlar.append([_tugma(q)])
    return {"inline_keyboard": qatorlar}


def summa_oqi(s: str) -> tuple[float | None, str | None, bool]:
    """(son, valyuta|None, birlik_noaniq). «500 ming», «1,5 mln», «$200», «200 dollar», «750000»."""
    s = (s or "").lower().replace(" ", " ").strip()
    valyuta = "USD" if ("$" in s or "dollar" in s or "usd" in s) else (
        "UZS" if ("so'm" in s or "som" in s or "сўм" in s) else None)
    m = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(mlrd|milliard|mln|million|млн|ming|минг|тыс|k)?", s)
    if not m:
        return None, valyuta, False
    xom = m.group(1).replace(" ", "")
    if re.search(r"[.,]\d{1,2}$", xom):
        xom = xom.replace(",", ".")
    else:
        xom = xom.replace(",", "").replace(".", "")
    try:
        son = float(xom)
    except ValueError:
        return None, valyuta, False
    birlik = m.group(2) or ""
    if birlik in ("mlrd", "milliard"):
        son *= 1e9
    elif birlik in ("mln", "million", "млн"):
        son *= 1e6
    elif birlik in ("ming", "минг", "тыс", "k"):
        son *= 1e3
    noaniq = not birlik and valyuta is None and son < 1000
    return son, valyuta, noaniq


def sana_oqi(s: str, kelajak: bool = False) -> str | None:
    """«bugun», «kecha», «ertaga», «7.10», «07.10.2026» → YYYY-MM-DD. kelajak=False bo'lsa kelajak sanasi rad."""
    s = (s or "").strip().lower()
    bugun = vaqt.bugun()
    sozlar = {"bugun": 0, "kecha": -1, "o'tgan kuni": -2, "otgan kuni": -2, "avvalgi kuni": -2,
              "ertaga": 1, "indinga": 2, "indin": 2}
    if s in sozlar:
        d = bugun + timedelta(days=sozlar[s])
        return d.isoformat() if kelajak or d <= bugun else None
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", s)
    if not m:
        return None
    kun, oy = int(m.group(1)), int(m.group(2))
    yil = int(m.group(3)) if m.group(3) else bugun.year
    if yil < 100:
        yil += 2000
    try:
        d = date(yil, oy, kun)
    except ValueError:
        return None
    if not kelajak and d > bugun:
        return None
    return d.isoformat()


_sana_oqi = sana_oqi


def _karta(kid: int) -> dict | None:
    r = baza.bir("SELECT * FROM karta WHERE id=?", kid)
    if r:
        r["d"] = json.loads(r["malumot"])
    return r


def _karta_saqla(kid: int, d: dict, **ustun) -> None:
    sets = ", ".join(["malumot=?"] + [f"{k}=?" for k in ustun])
    baza.bajar(f"UPDATE karta SET {sets} WHERE id=?", json.dumps(d, ensure_ascii=False), *ustun.values(), kid)


def KARTA_TUGMA(kid: int) -> list:
    return [[["To'g'ri", f"k:{kid}:ok"], ["Tuzatish", f"k:{kid}:tuz"]], ["Bekor qilish", f"k:{kid}:bekor"]]
