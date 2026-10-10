"""Maosh (M1, M2, M5, M6, M8, M9, M10).

Oylik, kunbay va foiz qismi ochiq oyda jonli hisoblanadi; oy yopilganda «hisoblandi» yozuvi bo'lib qotadi.
Ishbay, bonus, jarima, avans, to'lov — pul hisobidagi oddiy yozuvlar. Qoldiq oydan oyga o'zi o'tadi.
Soliq hisoblanmaydi — qo'lga beriladigan summa (M10).
"""
from datetime import date, timedelta

from . import baza, davomat, hisob, ishlar, kurs, matn, odamlar, vaqt

SHART_TURI = {"oylik": "Oylik", "kunbay": "Kunbay", "ishbay": "Ishbay", "foiz": "Sotuvdan foiz"}


class MaoshXato(Exception):
    pass


def boshlangan_oy() -> str:
    o = baza.sozlama("boshlangan_oy")
    if o:
        return o
    o = vaqt.oy(vaqt.bugun())
    baza.sozlama_qoy("boshlangan_oy", o)
    return o


# ---------- shartlar (M1, X5) ----------

def shartlar(odam_id: int, oy: str | None = None) -> list[dict]:
    if oy is None:
        return baza.hammasi("SELECT * FROM maosh_shart WHERE odam_id=? ORDER BY dan_sana, id", odam_id)
    b, o = vaqt.oy_boshi(oy).isoformat(), vaqt.oy_oxiri(oy).isoformat()
    return baza.hammasi("SELECT * FROM maosh_shart WHERE odam_id=? AND dan_sana<=? AND (gacha_sana IS NULL OR "
                        "gacha_sana>=?) ORDER BY dan_sana, id", odam_id, o, b)


def shart_qoy(odam_id: int, tur: str, qiymat: float, valyuta: str, dan_sana: str, kim_id: int,
              izoh: str | None = None) -> int:
    """Yangi shart eski shu turdagi shartni yopadi (o'chirmaydi) — X5."""
    if tur not in SHART_TURI:
        raise MaoshXato("Maosh turi noto'g'ri")
    if valyuta not in ("UZS", "USD"):
        raise MaoshXato("Valyuta noto'g'ri")
    if float(qiymat) < 0 or (tur == "foiz" and float(qiymat) > 100):
        raise MaoshXato("Qiymat noto'g'ri")
    dan_sana = dan_sana[:10]
    if hisob.oy_yopiqmi(vaqt.oy(dan_sana)):
        raise MaoshXato("Yopilgan oyga shart qo'yib bo'lmaydi — keyingi oydan boshlang")
    boshqa_v = baza.bir("SELECT valyuta FROM maosh_shart WHERE odam_id=? AND (gacha_sana IS NULL OR gacha_sana>=?) "
                        "AND tur!=? LIMIT 1", odam_id, dan_sana, tur)
    if boshqa_v and boshqa_v["valyuta"] != valyuta:
        raise MaoshXato("Bitta xodimning maosh qismlari bitta valyutada bo'lsin")
    with baza.tranz():
        oldingi = baza.hammasi("SELECT * FROM maosh_shart WHERE odam_id=? AND tur=? AND (gacha_sana IS NULL OR "
                               "gacha_sana>=?)", odam_id, tur, dan_sana)
        for s in oldingi:  # eski shart yopiladi; yangidan keyin boshlangan bo'lsa — umuman amal qilmaydi
            baza.bajar("UPDATE maosh_shart SET gacha_sana=? WHERE id=?",
                       (date.fromisoformat(dan_sana) - timedelta(days=1)).isoformat(), s["id"])
        sid = baza.bajar("INSERT INTO maosh_shart(odam_id,tur,qiymat,valyuta,dan_sana,izoh,yaratilgan) "
                         "VALUES(?,?,?,?,?,?,?)", odam_id, tur, float(qiymat), valyuta, dan_sana, izoh, vaqt.iso())
        baza.jurnal(kim_id, "maosh_shart", f"odam:{odam_id}", [dict(s) for s in oldingi],
                    {"tur": tur, "qiymat": qiymat, "valyuta": valyuta, "dan": dan_sana})
    return sid


def shart_tugat(shart_id: int, gacha_sana: str, kim_id: int) -> None:
    with baza.tranz():
        baza.bajar("UPDATE maosh_shart SET gacha_sana=? WHERE id=?", gacha_sana[:10], shart_id)
        baza.jurnal(kim_id, "maosh_shart_tugadi", f"shart:{shart_id}", None, gacha_sana)


def kunlar_qoy(odam_id: int, oy: str, kunlar: float, kim_id: int) -> None:
    if hisob.oy_yopiqmi(oy):
        raise MaoshXato("Bu oy yopilgan")
    if not 0 <= float(kunlar) <= 31:
        raise MaoshXato("Kunlar soni noto'g'ri")
    with baza.tranz():
        baza.bajar("INSERT INTO ish_kuni(odam_id,oy,kunlar) VALUES(?,?,?) ON CONFLICT(odam_id,oy) DO UPDATE SET "
                   "kunlar=excluded.kunlar", odam_id, oy, float(kunlar))
        baza.jurnal(kim_id, "ish_kunlari", f"odam:{odam_id}", oy, kunlar)


def ish_kunlari(odam_id: int, oy: str) -> tuple[float, bool]:
    """Kunbay kunlari: boshliq qo'lda yozgan bo'lsa — o'sha (M3-b), aks holda davomatdagi kunlar."""
    qolda = baza.qiymat("SELECT kunlar FROM ish_kuni WHERE odam_id=? AND oy=?", odam_id, oy)
    if qolda is not None:
        return float(qolda), True
    return float(davomat.oy_kunlari(odam_id, oy)), False


def valyuta(odam_id: int) -> str:
    return hisob.hisob_valyuta(f"maosh:{odam_id}") or "UZS"


def oylik_summa(odam_id: int, oy: str) -> tuple[int, str] | None:
    """Oyning to'liq oylik summasi (avans qoidasi uchun)."""
    s = [x for x in shartlar(odam_id, oy) if x["tur"] == "oylik"]
    if not s:
        return None
    oxirgi = s[-1]
    return matn.minor(oxirgi["qiymat"], oxirgi["valyuta"]), oxirgi["valyuta"]


# ---------- jonli hisob (ochiq oy) ----------

def _kesishma(s: dict, oy: str) -> tuple[date, date] | None:
    b, o = vaqt.oy_boshi(oy), vaqt.oy_oxiri(oy)
    d = max(b, date.fromisoformat(s["dan_sana"]))
    g = min(o, date.fromisoformat(s["gacha_sana"])) if s["gacha_sana"] else o
    return (d, g) if d <= g else None


def jonli(odam_id: int, oy: str) -> list[dict]:
    """Shartlardan kelib chiqadigan qismlar: oylik (kunlar ulushi bilan), kunbay, foiz."""
    if oy < boshlangan_oy() or hisob.oy_yopiqmi(oy):
        return []
    natija = []
    oy_kun = vaqt.oy_oxiri(oy).day
    for s in shartlar(odam_id, oy):
        k = _kesishma(s, oy)
        if not k:
            continue
        d, g = k
        if s["tur"] == "oylik":
            kun = (g - d).days + 1
            summa = matn.minor(s["qiymat"], s["valyuta"]) * kun // oy_kun
            izoh = "Oylik" if kun == oy_kun else f"Oylik · {kun}/{oy_kun} kun"
            natija.append({"tur": "oylik", "summa": summa, "valyuta": s["valyuta"], "izoh": izoh})
        elif s["tur"] == "kunbay":
            kunlar, qolda = ish_kunlari(odam_id, oy)
            if kunlar:
                summa = int(round(matn.minor(s["qiymat"], s["valyuta"]) * kunlar))
                belgi = " (qo'lda)" if qolda else " (davomat)"
                stavka = matn.pul(matn.minor(s["qiymat"], s["valyuta"]), s["valyuta"])
                natija.append({"tur": "kunbay", "summa": summa, "valyuta": s["valyuta"],
                               "izoh": f"Kunbay · {kunlar:g} kun{belgi} × {stavka}"})
        elif s["tur"] == "foiz":
            sotuvlar = baza.hammasi(
                "SELECT * FROM harakat WHERE tur='sotuv' AND sotuvchi_id=? AND holat IN ('faol','nizo') "
                "AND hisob_sana BETWEEN ? AND ?", odam_id, d.isoformat(), g.isoformat())
            jami = 0
            for r in sotuvlar:
                o = kurs.ogir(r["summa"], r["valyuta"], s["valyuta"], r["hisob_sana"])
                jami += o[0] if o else 0
            if jami:
                summa = int(round(jami * s["qiymat"] / 100))
                natija.append({"tur": "foiz", "summa": summa, "valyuta": s["valyuta"],
                               "izoh": f"Sotuvdan {s['qiymat']:g}% · sotuv {matn.pul(jami, s['valyuta'])}"})
    return [x for x in natija if x["summa"] > 0]


def _jonli_jami(odam_id: int, oy: str, v: str) -> int:
    return sum(x["summa"] for x in jonli(odam_id, oy) if x["valyuta"] == v)


def qarzimiz(odam_id: int, oy: str) -> int:
    """Oy oxiriga biz xodimga qancha qarzmiz (musbat) — maosh valyutasida."""
    v = valyuta(odam_id)
    kal = f"maosh:{odam_id}"
    daftar = hisob.qoldiq_bir(kal, v, gacha=vaqt.oy_oxiri(oy).isoformat())
    bosh = boshlangan_oy()
    live = sum(_jonli_jami(odam_id, m, v) for m in vaqt.oylar_oraligi(bosh, oy)) if oy >= bosh else 0
    return -daftar + live


# ---------- hisob varaqasi (M5) ----------

QATOR_NOMI = {"avans": "Avans", "maosh_tolov": "Maosh to'lovi", "qarzdan_ushlash": "Qarzdan ushlandi",
              "jarima": "Jarima", "bonus": "Bonus", "ishbay": "Ishbay", "hisoblandi": "Hisoblandi",
              "boshlangich_maosh": "Avvalgi qarzimiz", "tuzatish": "Tuzatish"}


def varaq(odam_id: int, oy: str | None = None) -> dict:
    oy = oy or vaqt.oy(vaqt.bugun())
    v = valyuta(odam_id)
    kal = f"maosh:{odam_id}"
    otgan = qarzimiz(odam_id, vaqt.oldingi_oy(oy))
    b, o = vaqt.oy_boshi(oy).isoformat(), vaqt.oy_oxiri(oy).isoformat()
    qatorlar, kutilmoqda = [], []
    for x in jonli(odam_id, oy):
        if x["valyuta"] == v:
            qatorlar.append({"nom": x["izoh"], "summa": x["summa"], "manba": "shart", "harakat_id": None,
                             "sana": None})
    for r in baza.hammasi("SELECT * FROM harakat WHERE (dan=? OR ga=?) AND holat IN ('faol','nizo') "
                          "AND hisob_sana BETWEEN ? AND ? ORDER BY hisob_sana, id", kal, kal, b, o):
        nom = QATOR_NOMI.get(r["tur"], hisob.SHABLON.get(r["tur"], (r["tur"],))[0])
        if r["izoh"] and r["tur"] in ("bonus", "jarima", "ishbay", "hisoblandi", "tuzatish"):
            nom += f" · {r['izoh']}"
        if r["kech"]:
            nom += " · kech kiritilgan"
        if r["dan"] == kal:
            if r["beruvchi_holat"] in ("kerak_emas", "tasdiq") and r["valyuta"] == v:
                qatorlar.append({"nom": nom, "summa": r["summa"], "manba": "yozuv", "harakat_id": r["id"],
                                 "sana": r["voqea_sana"]})
        else:
            summa_ga = r["summa2"] or r["summa"]
            v_ga = r["valyuta2"] or r["valyuta"]
            if v_ga != v:
                continue
            qator = {"nom": nom + (f" · {hisob.hisob_nomi(r['dan'])}" if r["dan"].startswith("kassa:") else ""),
                     "summa": -summa_ga, "manba": "yozuv", "harakat_id": r["id"], "sana": r["voqea_sana"]}
            if r["oluvchi_holat"] in ("kerak_emas", "tasdiq"):
                qatorlar.append(qator)
            elif r["oluvchi_holat"] == "kutilmoqda":
                kutilmoqda.append({**qator, "summa": summa_ga})
    ish_kut = []
    for x in ishlar.kutilayotgan_pul(odam_id):
        s_ = x["summa"]
        if x["valyuta"] != v:
            o_ = kurs.ogir(s_, x["valyuta"], v)
            s_ = o_[0] if o_ else 0
        ish_kut.append({"nom": x["nom"] + (" · dalil kutilmoqda" if x["holat"] == "bajarildi_dalil" else " · qabul kutilmoqda"),
                        "summa": s_, "ish_id": x["ish_id"]})
    hisoblandi = sum(q["summa"] for q in qatorlar if q["summa"] > 0)
    olindi = -sum(q["summa"] for q in qatorlar if q["summa"] < 0)
    qolgani = otgan + hisoblandi - olindi
    return {"odam": odamlar.odam(odam_id), "oy": oy, "valyuta": v, "otgan": otgan, "qatorlar": qatorlar,
            "hisoblandi": hisoblandi, "olindi": olindi, "kutilmoqda": kutilmoqda,
            "kutilmoqda_jami": sum(k["summa"] for k in kutilmoqda), "qolgani": qolgani,
            "ish_kutilmoqda": ish_kut, "ish_kutilmoqda_jami": sum(k["summa"] for k in ish_kut),
            "yopiq": hisob.oy_yopiqmi(oy)}


def tolash_kerak() -> list[dict]:
    """To'lovchi (kassir) uchun: faqat summa, tafsilotsiz (A2)."""
    oy = vaqt.oy(vaqt.bugun())
    natija = []
    for o in odamlar.faol_odamlar():
        if not shartlar(o["id"]) and not baza.qiymat("SELECT 1 FROM harakat WHERE (dan=? OR ga=?) LIMIT 1",
                                                     f"maosh:{o['id']}", f"maosh:{o['id']}"):
            continue
        q = qarzimiz(o["id"], oy)
        natija.append({"odam_id": o["id"], "ism": o["ism"], "qolgani": q, "valyuta": valyuta(o["id"])})
    return natija


# ---------- oyni yopish (M9) ----------

def oy_yop(oy: str, kim_id: int) -> dict:
    if not odamlar.boshliqmi(odamlar.odam(kim_id)):
        raise MaoshXato("Oyni faqat boshliq yopadi")
    joriy = vaqt.oy(vaqt.bugun())
    if oy >= joriy:
        raise MaoshXato("Faqat tugagan oy yopiladi")
    if hisob.oy_yopiqmi(oy):
        raise MaoshXato("Bu oy allaqachon yopilgan")
    oldingi = vaqt.oldingi_oy(oy)
    if oldingi >= boshlangan_oy() and not hisob.oy_yopiqmi(oldingi):
        raise MaoshXato(f"Avval {vaqt.oy_matn(oldingi)} yopilsin")
    yozildi = []
    oxiri = vaqt.oy_oxiri(oy).isoformat()
    with baza.tranz():
        odam_idlar = {r["odam_id"] for r in baza.hammasi("SELECT DISTINCT odam_id FROM maosh_shart")}
        for oid in sorted(odam_idlar):
            for x in jonli(oid, oy):
                hid = baza.bajar(
                    "INSERT INTO harakat(tur,dan,ga,summa,valyuta,odam_id,izoh,voqea_sana,hisob_sana,yozilgan,"
                    "yozgan_id,holat,manba,faollashgan) VALUES('hisoblandi',?,'ishhaqi',?,?,?,?,?,?,?,?,'faol','tizim',?)",
                    f"maosh:{oid}", x["summa"], x["valyuta"], oid, x["izoh"], oxiri, oxiri, vaqt.iso(), kim_id,
                    vaqt.iso())
                yozildi.append(hid)
        baza.bajar("INSERT INTO maosh_davr(oy,holat,yopilgan,yopgan_id) VALUES(?,'yopiq',?,?) ON CONFLICT(oy) DO "
                   "UPDATE SET holat='yopiq', yopilgan=excluded.yopilgan, yopgan_id=excluded.yopgan_id",
                   oy, vaqt.iso(), kim_id)
        baza.jurnal(kim_id, "oy_yopildi", f"oy:{oy}", None, {"yozuvlar": yozildi})
    return {"oy": oy, "yozuvlar": len(yozildi)}


# ---------- maosh kuni ogohlantirishi (M6) ----------

def maosh_kunlari() -> list[int]:
    k = baza.sozlama("maosh_kunlari", [10, 25])
    return sorted({int(x) for x in k if 1 <= int(x) <= 28}) or [10, 25]


def keyingi_maosh_kuni(bugun: date | None = None) -> date:
    bugun = bugun or vaqt.bugun()
    for oy_siljish in (0, 1):
        y, m = bugun.year, bugun.month + oy_siljish
        if m > 12:
            y, m = y + 1, 1
        for kun in maosh_kunlari():
            d = date(y, m, kun)
            if d >= bugun:
                return d
    return bugun


def bashorat() -> dict:
    """Keyingi maosh kunida pul yetadimi — faqat qo'ldagi aniq pul bo'yicha (P8)."""
    kun = keyingi_maosh_kuni()
    oy = vaqt.oy(vaqt.bugun())
    kerak = 0
    for x in tolash_kerak():
        if x["qolgani"] > 0:
            kerak += kurs.somga(x["qolgani"], x["valyuta"]) or 0
    aniq = 0
    for k in hisob.kassa_holati():
        aniq += kurs.somga(k["qoldiq"], k["valyuta"]) or 0
    return {"kun": kun.isoformat(), "qoldi_kun": (kun - vaqt.bugun()).days, "kerak": kerak, "aniq_pul": aniq,
            "yetmaydi": max(0, kerak - aniq), "oy": oy}
