"""Odamlar, rollar, taklif havolasi, parol, sessiya, huquqlar (A2, T2, M8, O4)."""
import hashlib
import hmac
import os
import secrets

from cryptography.fernet import Fernet

from . import baza, vaqt

ROLLAR = ("boshliq", "menejer", "kassir", "xodim")
ROL_NOMI = {"boshliq": "Boshliq", "menejer": "Menejer", "kassir": "Kassir", "xodim": "Xodim"}
TAKLIF_MUDDAT_KUN = 7


class HuquqYoq(Exception):
    pass


# ---------- shifrlash (kalitlar va ko'rinadigan parol uchun) ----------

def _fernet() -> Fernet:
    yol = os.path.join(os.path.dirname(os.path.abspath(baza.yol())), ".kalit")
    if not os.path.exists(yol):
        try:
            fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
    with open(yol, "rb") as f:
        return Fernet(f.read().strip())


def shifrla(s: str) -> str:
    return _fernet().encrypt(s.encode()).decode()


def ochish(s: str) -> str:
    return _fernet().decrypt(s.encode()).decode()


# ---------- parol ----------

def parol_xesh(parol: str) -> str:
    tuz = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", parol.encode(), tuz, 200_000)
    return f"pbkdf2${tuz.hex()}${h.hex()}"


def parol_togri(parol: str, xesh: str | None) -> bool:
    if not xesh or not xesh.startswith("pbkdf2$"):
        return False
    _, tuz, h = xesh.split("$")
    yangi = hashlib.pbkdf2_hmac("sha256", parol.encode(), bytes.fromhex(tuz), 200_000)
    return hmac.compare_digest(yangi.hex(), h)


# ---------- odam ----------

def odam(odam_id: int | None) -> dict | None:
    if odam_id is None:
        return None
    return baza.bir("SELECT * FROM odam WHERE id=?", odam_id)


def odam_tg(tg_id: int) -> dict | None:
    return baza.bir("SELECT * FROM odam WHERE tg_id=? AND holat!='ketgan'", tg_id)


def faol_odamlar(rollar: tuple[str, ...] | None = None) -> list[dict]:
    q = "SELECT * FROM odam WHERE holat!='ketgan'"
    if rollar:
        q += " AND rol IN (%s)" % ",".join("?" * len(rollar))
        return baza.hammasi(q + " ORDER BY ism", *rollar)
    return baza.hammasi(q + " ORDER BY ism")


def boshliq() -> dict | None:
    return baza.bir("SELECT * FROM odam WHERE rol='boshliq' AND holat!='ketgan' ORDER BY id LIMIT 1")


def odam_yarat(ism: str, rol: str, kim_id: int | None = None, telefon: str | None = None,
               lavozim: str | None = None, maosh_tolaydi: int = 0) -> int:
    ism = (ism or "").strip()
    if not ism:
        raise ValueError("Ism bo'sh bo'lmasin")
    if rol not in ROLLAR:
        raise ValueError("Noma'lum rol")
    with baza.tranz():
        oid = baza.bajar(
            "INSERT INTO odam(ism,rol,telefon,lavozim,maosh_tolaydi,yaratilgan) VALUES(?,?,?,?,?,?)",
            ism, rol, telefon, lavozim, 1 if (maosh_tolaydi or rol == "boshliq") else 0, vaqt.iso())
        if rol == "boshliq":
            # boshliqning o'z cho'ntagi — alohida kassa (P1)
            kid = baza.bajar("INSERT INTO kassa(nom,tur,valyuta,masul_id) VALUES(?,?,?,?)",
                             f"{ism.split()[0]} cho'ntagi", "chontak", "UZS", oid)
            baza.bajar("UPDATE odam SET kassa_id=? WHERE id=?", kid, oid)
        baza.jurnal(kim_id, "odam_yarat", f"odam:{oid}", None, {"ism": ism, "rol": rol})
    return oid


def odam_tahrir(odam_id: int, kim_id: int, **maydon) -> None:
    ruxsat = {"ism", "telefon", "lavozim", "rol", "maosh_tolaydi", "kassa_id"}
    eski = odam(odam_id)
    if not eski:
        raise ValueError("Odam topilmadi")
    ozgar = {k: v for k, v in maydon.items() if k in ruxsat and v is not None}
    if "rol" in ozgar and ozgar["rol"] not in ROLLAR:
        raise ValueError("Noma'lum rol")
    if not ozgar:
        return
    with baza.tranz():
        baza.bajar("UPDATE odam SET %s WHERE id=?" % ",".join(f"{k}=?" for k in ozgar), *ozgar.values(), odam_id)
        baza.jurnal(kim_id, "odam_tahrir", f"odam:{odam_id}", {k: eski[k] for k in ozgar}, ozgar)


def holat_qoy(odam_id: int, holat: str, kim_id: int) -> None:
    """faol / ketmoqda (faqat hisobini ko'radi) / ketgan (kirish yopiq) — O4."""
    if holat not in ("faol", "ketmoqda", "ketgan"):
        raise ValueError("Noma'lum holat")
    eski = odam(odam_id)
    with baza.tranz():
        baza.bajar("UPDATE odam SET holat=? WHERE id=?", holat, odam_id)
        if holat != "faol":
            baza.bajar("DELETE FROM sessiya WHERE odam_id=?", odam_id)
            baza.bajar("UPDATE taklif SET ishlatilgan=? WHERE odam_id=? AND ishlatilgan IS NULL", vaqt.iso(), odam_id)
        baza.jurnal(kim_id, "odam_holat", f"odam:{odam_id}", eski["holat"] if eski else None, holat)


# ---------- taklif havolasi (T2) ----------

def taklif_yarat(odam_id: int, kim_id: int) -> str:
    kod = "x" + secrets.token_urlsafe(12).replace("-", "a").replace("_", "b")  # «m…» — mijoz havolasi uchun band
    with baza.tranz():
        baza.bajar("UPDATE taklif SET ishlatilgan=? WHERE odam_id=? AND ishlatilgan IS NULL", vaqt.iso(), odam_id)
        baza.bajar("INSERT INTO taklif(kod,odam_id,yaratilgan) VALUES(?,?,?)", kod, odam_id, vaqt.iso())
        baza.jurnal(kim_id, "taklif_yarat", f"odam:{odam_id}")
    return kod


def taklif_ishlat(kod: str, tg_id: int, tg_nom: str | None) -> dict | None:
    """Bir martalik havola. Muvaffaqiyat — odam; aks holda None."""
    t = baza.bir("SELECT * FROM taklif WHERE kod=?", (kod or "").strip())
    if not t or t["ishlatilgan"]:
        return None
    if (vaqt.hozir() - vaqt.hozir().fromisoformat(t["yaratilgan"])).days >= TAKLIF_MUDDAT_KUN:
        return None
    o = odam(t["odam_id"])
    if not o or o["holat"] == "ketgan":
        return None
    boshqa = baza.bir("SELECT id FROM odam WHERE tg_id=? AND id!=?", tg_id, o["id"])
    if boshqa:
        return None
    with baza.tranz():
        baza.bajar("UPDATE taklif SET ishlatilgan=? WHERE kod=?", vaqt.iso(), t["kod"])
        baza.bajar("UPDATE odam SET tg_id=?, tg_nom=? WHERE id=?", tg_id, tg_nom, o["id"])
        baza.jurnal(o["id"], "telegram_ulandi", f"odam:{o['id']}", None, {"tg_id": tg_id})
    return odam(o["id"])


# ---------- panel paroli va sessiya ----------

def parol_qoy(odam_id: int, login: str, parol: str, kim_id: int) -> None:
    login = (login or "").strip().lower()
    if len(login) < 3 or len(parol or "") < 6:
        raise ValueError("Login kamida 3, parol kamida 6 belgi bo'lsin")
    band = baza.bir("SELECT id FROM odam WHERE login=? AND id!=?", login, odam_id)
    if band:
        raise ValueError("Bu login band")
    with baza.tranz():
        baza.bajar("UPDATE odam SET login=?, parol_xesh=?, parol_shifr=? WHERE id=?",
                   login, parol_xesh(parol), shifrla(parol), odam_id)
        baza.bajar("DELETE FROM sessiya WHERE odam_id=?", odam_id)
        baza.jurnal(kim_id, "parol_qoyildi", f"odam:{odam_id}")


def parol_kor(odam_id: int, kim_id: int) -> str | None:
    o = odam(odam_id)
    if not o or not o["parol_shifr"]:
        return None
    baza.jurnal(kim_id, "parol_korildi", f"odam:{odam_id}")
    return ochish(o["parol_shifr"])


def kirish(login: str, parol: str) -> dict | None:
    o = baza.bir("SELECT * FROM odam WHERE login=? AND holat='faol'", (login or "").strip().lower())
    if o and parol_togri(parol or "", o["parol_xesh"]):  # xodim ham kiradi — panel unga faqat o'zinikini ko'rsatadi
        return o
    return None


def _xesh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sessiya_yarat(odam_id: int) -> str:
    token = secrets.token_urlsafe(32)
    baza.bajar("INSERT INTO sessiya(token_xesh,odam_id,yaratilgan,oxirgi) VALUES(?,?,?,?)",
               _xesh(token), odam_id, vaqt.iso(), vaqt.iso())
    return token


def sessiya_odam(token: str | None) -> dict | None:
    if not token:
        return None
    s = baza.bir("SELECT * FROM sessiya WHERE token_xesh=?", _xesh(token))
    if not s:
        return None
    if (vaqt.hozir() - vaqt.hozir().fromisoformat(s["oxirgi"])).days >= 30:
        baza.bajar("DELETE FROM sessiya WHERE token_xesh=?", s["token_xesh"])
        return None
    o = odam(s["odam_id"])
    if not o or o["holat"] != "faol":
        return None
    baza.bajar("UPDATE sessiya SET oxirgi=? WHERE token_xesh=?", vaqt.iso(), s["token_xesh"])
    return o


def sessiya_tugat(token: str | None) -> None:
    if token:
        baza.bajar("DELETE FROM sessiya WHERE token_xesh=?", _xesh(token))


# ---------- huquqlar ----------

def boshliqmi(o: dict | None) -> bool:
    return bool(o) and o["rol"] == "boshliq" and o["holat"] == "faol"


def mumkin(o: dict | None, amal: str) -> bool:
    """Bo'lim darajasidagi huquq."""
    if not o or o["holat"] == "ketgan":
        return False
    if o["holat"] == "ketmoqda":
        return amal == "oz_hisobi"
    rol = o["rol"]
    if rol == "boshliq":
        return True
    jadval = {
        "kassir": {"kassa", "mijoz_qarz", "sotuv", "xarajat", "oz_hisobi"},
        "menejer": {"mijoz_qarz", "sotuv", "ishbay", "oz_hisobi"},
        "xodim": {"oz_hisobi"},
    }
    if amal == "maosh_tolash":
        return bool(o["maosh_tolaydi"])
    return amal in jadval.get(rol, set())


def hisob_korishi_mumkin(o: dict | None, kalit: str) -> bool:
    """S3/M8: kim qaysi hisobni ko'radi. Filtr sun'iy intellektga berishdan OLDIN qo'llanadi."""
    if not o or o["holat"] == "ketgan":
        return False
    if boshliqmi(o):
        return True
    tur, _, i = kalit.partition(":")
    oz = i.isdigit() and int(i) == o["id"]
    if tur in ("maosh", "xqarz", "qol"):
        return oz or (tur == "qol" and o["rol"] == "kassir")
    if o["holat"] == "ketmoqda":
        return False
    if tur == "kassa":
        k = baza.bir("SELECT masul_id, tur FROM kassa WHERE id=?", int(i) if i.isdigit() else -1)
        if not k:
            return False
        if k["masul_id"] == o["id"]:
            return True
        return o["rol"] == "kassir" and k["tur"] != "chontak"  # boshliqning shaxsiy cho'ntagi kassirga ko'rinmaydi
    if tur in ("mijoz", "taminotchi", "sotuv"):
        return o["rol"] in ("kassir", "menejer")
    if tur == "xarajat":
        return o["rol"] == "kassir"
    return False
