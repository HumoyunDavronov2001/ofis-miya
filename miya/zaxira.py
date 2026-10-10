"""Zaxira (T1): har kecha baza nusxasi 2 joyga, 14 kun saqlanadi; har nusxa ochib tekshiriladi."""
import glob
import os
import shutil
import sqlite3

from . import baza, vaqt

SAQLASH_KUN = 14
VAQT = "03:30"


def papka() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(baza.yol())), "zaxira")


def tekshir(yol: str) -> dict:
    """Nusxani alohida ochib butunligini va yozuvlar sonini tekshiradi."""
    c = sqlite3.connect(f"file:{yol}?mode=ro", uri=True)
    try:
        butun = c.execute("PRAGMA integrity_check").fetchone()[0]
        soni = c.execute("SELECT COUNT(*) FROM harakat").fetchone()[0]
        odam = c.execute("SELECT COUNT(*) FROM odam").fetchone()[0]
    finally:
        c.close()
    return {"butun": butun == "ok", "harakat": soni, "odam": odam}


def ol(qayerga: str | None = None) -> dict:
    p = qayerga or papka()
    os.makedirs(p, exist_ok=True)
    nom = f"miya-{vaqt.bugun().isoformat()}.db"
    yol = os.path.join(p, nom)
    manba = sqlite3.connect(baza.yol())
    nusxa = sqlite3.connect(yol + ".tmp")
    try:
        manba.backup(nusxa)
    finally:
        nusxa.close()
        manba.close()
    os.replace(yol + ".tmp", yol)
    kalit = os.path.join(os.path.dirname(os.path.abspath(baza.yol())), ".kalit")
    if os.path.exists(kalit):  # shifrlangan kalit va parollarni ochish uchun kerak
        shutil.copy2(kalit, os.path.join(p, ".kalit"))
        os.chmod(os.path.join(p, ".kalit"), 0o600)
    natija = tekshir(yol)
    jonli = baza.qiymat("SELECT COUNT(*) FROM harakat")
    natija["mos"] = natija["harakat"] == jonli
    natija["yol"] = yol
    for eski in sorted(glob.glob(os.path.join(p, "miya-*.db")))[:-SAQLASH_KUN]:
        os.remove(eski)
    ikkinchi = baza.sozlama("zaxira_yol2")
    if ikkinchi:
        try:
            os.makedirs(ikkinchi, exist_ok=True)
            shutil.copy2(yol, os.path.join(ikkinchi, nom))
            if os.path.exists(os.path.join(p, ".kalit")):
                shutil.copy2(os.path.join(p, ".kalit"), os.path.join(ikkinchi, ".kalit"))
            natija["ikkinchi"] = tekshir(os.path.join(ikkinchi, nom))["butun"]
            for eski in sorted(glob.glob(os.path.join(ikkinchi, "miya-*.db")))[:-SAQLASH_KUN]:
                os.remove(eski)
        except OSError as x:
            natija["ikkinchi_xato"] = str(x)
    natija["vaqt"] = vaqt.iso()
    baza.sozlama_qoy("oxirgi_zaxira", natija)
    return natija


def kerakmi() -> bool:
    if vaqt.hozir().strftime("%H:%M") < VAQT:
        return False
    oxirgi = baza.sozlama("oxirgi_zaxira") or {}
    return not str(oxirgi.get("vaqt", "")).startswith(vaqt.bugun().isoformat())
