"""Markaziy bank kursi (P11). Kun kursi bazada saqlanadi; internet bo'lmasa oxirgi ma'lum kurs."""
import time

import httpx

from . import baza, vaqt

_xato: dict[tuple[str, str], float] = {}  # internet yo'q bo'lsa har so'rovda 6 soniya kutmaslik uchun

URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/{v}/{s}/"


def _olib_kel(valyuta: str, sana: str) -> float | None:
    try:
        r = httpx.get(URL.format(v=valyuta, s=sana), timeout=6)
        r.raise_for_status()
        d = r.json()
        if d:
            return float(str(d[0]["Rate"]).replace(",", "."))
    except Exception:
        return None
    return None


def kurs(sana: str | None = None, valyuta: str = "USD") -> float | None:
    """1 birlik valyuta necha so'm. Topilmasa None."""
    if valyuta == "UZS":
        return 1.0
    sana = (sana or vaqt.bugun().isoformat())[:10]
    r = baza.bir("SELECT kurs FROM kurs WHERE sana=? AND valyuta=?", sana, valyuta)
    if r:
        return r["kurs"]
    if sana <= vaqt.bugun().isoformat() and time.monotonic() - _xato.get((valyuta, sana), -1e9) > 600:
        k = _olib_kel(valyuta, sana)
        if k:
            baza.bajar("INSERT OR REPLACE INTO kurs(sana,valyuta,kurs) VALUES(?,?,?)", sana, valyuta, k)
            return k
        _xato[(valyuta, sana)] = time.monotonic()
    r = baza.bir("SELECT kurs FROM kurs WHERE valyuta=? AND sana<=? ORDER BY sana DESC LIMIT 1", valyuta, sana)
    return r["kurs"] if r else None


def kurs_qoy(sana: str, valyuta: str, k: float) -> None:
    baza.bajar("INSERT OR REPLACE INTO kurs(sana,valyuta,kurs) VALUES(?,?,?)", sana[:10], valyuta, float(k))


def somga(minor: int, valyuta: str, sana: str | None = None) -> int | None:
    """Valyutadagi summani so'mga o'giradi (hisobotlar uchun)."""
    if valyuta == "UZS":
        return minor
    k = kurs(sana, valyuta)
    if k is None:
        return None
    return int(round(minor / 100 * k))


def ogir(minor: int, dan: str, ga: str, sana: str | None = None) -> tuple[int, float] | None:
    """dan valyutadagi summani ga valyutaga o'giradi: (summa, kurs)."""
    if dan == ga:
        return minor, 1.0
    k = kurs(sana, "USD")
    if k is None:
        return None
    if dan == "USD" and ga == "UZS":
        return int(round(minor / 100 * k)), k
    if dan == "UZS" and ga == "USD":
        return int(round(minor / k * 100)), k
    return None
