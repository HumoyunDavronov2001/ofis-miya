"""R5–R6: umumiy xotira — uchrashuv, eslatma, ma'lumot (pul, ish, va'da bo'lmagan hamma gap).

Darhol saqlanadi (pul emas — tasdiq kerak emas). Qachon eslatishni sun'iy intellekt emas, dastur hisoblaydi.
"""
import re
from datetime import datetime, timedelta

from . import baza, hisob, matn, odamlar, vaqt

TURLAR = ("uchrashuv", "eslatma", "malumot")


class XotiraXato(Exception):
    pass


def _sana(s: str | None) -> str | None:
    s = (s or "")[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def _soat(s: str | None) -> str | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", (s or "").strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m and int(m.group(1)) < 24 and int(m.group(2)) < 60 else None


def eslat_vaqti(sana: str | None, soat: str | None, tur: str = "uchrashuv") -> str | None:
    """R6: uchrashuv — 1 soat oldin (o'tgan bo'lsa 15 daqiqa oldin, u ham o'tgan bo'lsa — o'z vaqtida);
    eslatma («soat 15 da qo'ng'iroq qilishni eslat», «20 daqiqadan keyin eslat») — aynan o'sha vaqtda;
    faqat kuni aytilgan — o'sha kuni ertalabki xulosa vaqtida."""
    if not sana:
        return None
    hozir = vaqt.hozir()
    if soat:
        voqea = datetime.fromisoformat(f"{sana}T{soat}").replace(tzinfo=hozir.tzinfo)
        for oldin in ((0,) if tur == "eslatma" else (60, 15, 0)):
            t = voqea - timedelta(minutes=oldin)
            if t > hozir:
                return vaqt.iso(t)
        return None
    t = datetime.fromisoformat(f"{sana}T{baza.sozlama('brifing_vaqti', '08:30')}").replace(tzinfo=hozir.tzinfo)
    return vaqt.iso(t) if t > hozir else None


def qosh(tur: str, matn_: str, yozgan_id: int, sana: str | None = None, soat: str | None = None,
         kimga_id: int | None = None, xabar_id: int | None = None, iqtibos: str | None = None) -> int:
    matn_ = (matn_ or "").strip()
    if not matn_:
        raise XotiraXato("Bo'sh")
    if tur not in TURLAR:
        tur = "uchrashuv" if soat else "eslatma" if sana else "malumot"
    sana = _sana(sana)
    soat = _soat(soat) if sana else None  # soat kunsiz ma'nosiz
    xid = baza.bajar("INSERT INTO xotira(tur,matn,sana,soat,eslat_vaqt,yozgan_id,kimga_id,xabar_id,iqtibos,vaqt) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?)", tur, matn_[:500], sana, soat, eslat_vaqti(sana, soat, tur), yozgan_id,
                     kimga_id, xabar_id, (iqtibos or "")[:300], vaqt.iso())
    baza.jurnal(yozgan_id, "xotira_qosh", f"xotira:{xid}", None, {"tur": tur, "sana": sana, "soat": soat})
    return xid


def bir(xid: int) -> dict | None:
    return baza.bir("SELECT * FROM xotira WHERE id=?", xid)


def qachon(x: dict) -> str:
    if not x.get("sana"):
        return ""
    bugun = vaqt.bugun().isoformat()
    kun = {bugun: "bugun", (vaqt.bugun() + timedelta(days=1)).isoformat(): "ertaga"}.get(x["sana"])
    s = f"{kun} ({vaqt.sana_matn(x['sana'])})" if kun else vaqt.sana_matn(x["sana"])
    return s + (f" soat {x['soat']}" if x.get("soat") else "")


def tasdiq_matni(x: dict) -> str:
    """Saqlangandan keyingi javob: nima eslab qolindi va qachon eslatiladi."""
    q = qachon(x)
    m = f"Eslab qoldim: {q + ' — ' if q else ''}{x['matn']}"
    if x.get("eslat_vaqt"):
        e = datetime.fromisoformat(x["eslat_vaqt"])
        kun = "" if e.date() == vaqt.bugun() or e.date().isoformat() == x.get("sana") else f"{vaqt.sana_matn(e.date(), False)} "
        m += f". {kun}{e:%H:%M} da eslataman"
    elif x.get("sana") and x["tur"] != "malumot" and x["sana"] >= vaqt.bugun().isoformat():
        m += ". Vaqti o'tib ketgan — eslatmayman"
    if x.get("kimga_id") and x["kimga_id"] != x["yozgan_id"] and x.get("eslat_vaqt"):
        k = odamlar.odam(x["kimga_id"])
        if k:
            m += f" (sizga va {k['ism']}ga)"
    return m + "."


def eslatish_kerak() -> list[dict]:
    return baza.hammasi("SELECT * FROM xotira WHERE eslatildi IS NULL AND holat='ochiq' AND eslat_vaqt IS NOT NULL "
                        "AND eslat_vaqt<=? ORDER BY eslat_vaqt", vaqt.iso())


def eslat() -> int:
    """Vaqti kelgan eslatmalar → xabarnoma navbati (Telegram ham, web chat ham shundan oladi). Takrorlanmaydi."""
    n = 0
    for x in eslatish_kerak():
        with baza.tranz() as c:
            if c.execute("UPDATE xotira SET eslatildi=? WHERE id=? AND eslatildi IS NULL", (vaqt.iso(), x["id"])).rowcount == 0:
                continue  # boshqa jarayon allaqachon eslatgan
            # kimga aytilgan bo'lsa — unga ham, yozganga ham (uchrashuvda odatda ikkalasi qatnashadi)
            for kimga in dict.fromkeys(i for i in (x["kimga_id"], x["yozgan_id"]) if i):
                hisob.xabarnoma(kimga, "xotira", f"⏰ Eslatma: {qachon(x)} — {x['matn']}", None,
                                [["Bajarildi", f"xb:{x['id']}"], ["Bekor", f"xk:{x['id']}"]])
            n += 1
    return n


def holat_qoy(xid: int, holat: str, kim_id: int) -> None:
    if holat not in ("bajarildi", "bekor", "ochiq"):
        raise XotiraXato("Holat noto'g'ri")
    x = bir(xid)
    if not x:
        raise XotiraXato("Topilmadi")
    baza.bajar("UPDATE xotira SET holat=? WHERE id=?", holat, xid)
    baza.jurnal(kim_id, "xotira_holat", f"xotira:{xid}", x["holat"], holat)


def royxat(dan: str | None = None, gacha: str | None = None, sorov: str = "", faqat_ochiq: bool = False,
           limit: int = 50) -> list[dict]:
    """R8: umumiy xotira hammaga ochiq (R3). Sana oralig'i yoki so'z bo'yicha."""
    shart, p = ["holat!='bekor'"], []
    if faqat_ochiq:
        shart.append("holat='ochiq'")
    if dan:
        shart.append("sana>=?")
        p.append(dan)
    if gacha:
        shart.append("sana<=?")
        p.append(gacha)
    qatorlar = baza.hammasi(f"SELECT * FROM xotira WHERE {' AND '.join(shart)} ORDER BY (sana IS NULL), sana, soat, id DESC "
                            f"LIMIT {int(limit) * (4 if sorov else 1)}", *p)
    if sorov:
        sozlar = [s for s in matn.norm(sorov).split() if len(s) >= 3]
        qatorlar = [x for x in qatorlar if any(s[:5] in matn.norm(f"{x['matn']} {x['iqtibos'] or ''}") for s in sozlar)]
    return qatorlar[:limit]


def bugungilar(sana: str | None = None) -> list[dict]:
    """Ertalabki xulosa uchun: shu kungi uchrashuv va eslatmalar."""
    return baza.hammasi("SELECT * FROM xotira WHERE sana=? AND holat='ochiq' ORDER BY (soat IS NULL), soat, id",
                        sana or vaqt.bugun().isoformat())


def _kimga(ism: str, o: dict) -> int | None:
    ism = (ism or "").strip()
    if not ism or matn.norm(ism) in ("men", "ozim", "o zim"):
        return None
    variant = [(x["id"], x["ism"]) for x in odamlar.faol_odamlar() if x["holat"] == "faol"]
    bitta = matn.yagona(matn.mosla(ism, variant))
    return bitta[0] if bitta and bitta[0] != o["id"] else None


def saqla_natija(elementlar: list[dict], o: dict, xabar_id: int | None = None) -> list[dict]:
    """tushun() «xotira» elementlari → bazaga (tasdiqsiz, R5). Bot ham, web chat ham shuni chaqiradi."""
    natija = []
    for y in (elementlar or [])[:8]:
        if not (y.get("matn") or "").strip():
            continue
        xid = qosh(y.get("tur"), y["matn"], o["id"], y.get("sana"), y.get("soat"), _kimga(y.get("kimga"), o), xabar_id,
                   y.get("iqtibos"))
        x = bir(xid)
        natija.append({"id": xid, "tur": x["tur"], "matn": tasdiq_matni(x)})
    return natija


def tahrirla(xid: int, kim_id: int, tur: str | None = None, matn_: str | None = None, sana: str | None = "",
             soat: str | None = "", kimga_id: int | None = -1) -> dict:
    """CRM1: paneldan tahrirlash. Vaqt o'zgarsa — eslatish qayta hisoblanadi (eslatilgan bo'lsa ham yana eslatadi)."""
    x = bir(xid)
    if not x:
        raise XotiraXato("Topilmadi")
    yangi = {"tur": tur if tur in TURLAR else x["tur"], "matn": (matn_ if matn_ is not None else x["matn"]).strip()[:500],
             "sana": x["sana"] if sana == "" else _sana(sana), "kimga_id": x["kimga_id"] if kimga_id == -1 else kimga_id}
    yangi["soat"] = (x["soat"] if soat == "" else _soat(soat)) if yangi["sana"] else None
    if not yangi["matn"]:
        raise XotiraXato("Matn bo'sh")
    vaqt_ozgardi = (yangi["sana"], yangi["soat"], yangi["tur"]) != (x["sana"], x["soat"], x["tur"])
    eslat = eslat_vaqti(yangi["sana"], yangi["soat"], yangi["tur"]) if vaqt_ozgardi else x["eslat_vaqt"]
    baza.bajar("UPDATE xotira SET tur=?, matn=?, sana=?, soat=?, kimga_id=?, eslat_vaqt=?, eslatildi=? WHERE id=?",
               yangi["tur"], yangi["matn"], yangi["sana"], yangi["soat"], yangi["kimga_id"], eslat,
               None if vaqt_ozgardi else x["eslatildi"], xid)
    baza.jurnal(kim_id, "xotira_tahrir", f"xotira:{xid}", {k: x[k] for k in yangi}, yangi)
    return bir(xid)
