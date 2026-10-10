"""Ishlar (I1–I8, M4, O2, O3).

Holatlar: yangi → (bajarildi_dalil) → bajarildi → qabul;  qayta — qayta ishlash; bekor.
Narxi bor ish bajarilgach pul «kutilmoqda»; boshliq yoki menejer qabul qilgach (yoki 24 soatda e'tiroz bo'lmasa)
xodim hisobiga «ishbay» yozuvi bo'lib tushadi. Bir necha ijrochi — ulush bo'yicha, jami narxdan bir so'm ham farqsiz.
"""
import json
import math
from datetime import date, datetime, timedelta

from . import baza, hisob, kurs, matn, odamlar, vaqt


class IshXato(Exception):
    pass


HOLAT_NOMI = {"yangi": "Bajarilmoqda", "bajarildi_dalil": "Dalil kutilmoqda", "bajarildi": "Bajarildi",
              "qabul": "Qabul qilindi", "qayta": "Qayta ishlash kerak", "bekor": "Bekor qilindi"}
DALIL_NOMI = {"rasm": "rasm", "joylashuv": "joylashuv", "mijoz": "mijoz tasdig'i", "yoq": "dalilsiz"}
OCHIQ = ("yangi", "bajarildi_dalil", "qayta")
JOY_RADIUS = 300  # metr (I-b)
AVTO_QABUL_SOAT = 24


# ---------- yordamchilar ----------

def masofa(lat1, lon1, lat2, lon2) -> float:
    r = 6371000
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def ulush_taqsim(narx: int, ijrochilar: list[dict]) -> list[tuple[int, int]]:
    """Jami narx ulushlarga bo'linadi; yaxlitlash qoldig'i birinchi ijrochiga (I-d)."""
    if not ijrochilar or not narx:
        return []
    jami = sum(max(float(x["ulush"]), 0) for x in ijrochilar) or len(ijrochilar)
    qism = [(x["odam_id"], int(narx * max(float(x["ulush"]), 0) // jami)) for x in ijrochilar]
    qoldiq = narx - sum(s for _, s in qism)
    qism[0] = (qism[0][0], qism[0][1] + qoldiq)
    return qism


def tolov_huquqi(o: dict | None) -> bool:
    return bool(o) and o["holat"] == "faol" and o["rol"] in ("boshliq", "menejer")


# ---------- o'qish ----------

def ish(ish_id: int) -> dict | None:
    r = baza.bir("SELECT * FROM ish WHERE id=?", ish_id)
    if not r:
        return None
    r["ijrochilar"] = baza.hammasi(
        "SELECT ii.*, o.ism FROM ish_ijrochi ii JOIN odam o ON o.id=ii.odam_id WHERE ii.ish_id=? ORDER BY ii.rowid",
        ish_id)
    r["dalillar"] = baza.hammasi("SELECT * FROM ish_dalil WHERE ish_id=? ORDER BY id", ish_id)
    if r["mijoz_id"]:
        m = baza.bir("SELECT ism, tg_id FROM mijoz WHERE id=?", r["mijoz_id"])
        r["mijoz"] = m["ism"] if m else None
        r["mijoz_tg"] = m["tg_id"] if m else None
    else:
        r["mijoz"] = r["mijoz_tg"] = None
    return r


def korishi_mumkin(o: dict, i: dict) -> bool:
    if not o or o["holat"] == "ketgan":
        return False
    if o["rol"] in ("boshliq", "menejer"):
        return True
    return any(x["odam_id"] == o["id"] for x in i["ijrochilar"]) or i["yaratgan_id"] == o["id"]


def ishlar(korish: dict | None = None, holat: str | None = None, odam_id: int | None = None,
           faqat_ochiq: bool = False, dan: str | None = None, gacha: str | None = None, limit: int = 300,
           holatlar: tuple | None = None, qabul_kerak: bool = False) -> list[dict]:
    shart, p = ["1=1"], []
    if holat:
        shart.append("i.holat=?")
        p.append(holat)
    if holatlar:
        shart.append("i.holat IN (%s)" % ",".join("?" * len(holatlar)))
        p += list(holatlar)
    if qabul_kerak:  # narxi bor yoki xodim o'zi aytgan — qabul qilinishi kerak (M4, I-f)
        shart.append("i.holat='bajarildi' AND (i.narx>0 OR i.manba='xodim')")
    if faqat_ochiq:
        shart.append("i.holat IN ('yangi','bajarildi_dalil','qayta')")
    if odam_id:
        shart.append("i.id IN (SELECT ish_id FROM ish_ijrochi WHERE odam_id=?)")
        p.append(odam_id)
    if korish is not None and korish["rol"] not in ("boshliq", "menejer"):
        shart.append("(i.id IN (SELECT ish_id FROM ish_ijrochi WHERE odam_id=?) OR i.yaratgan_id=?)")
        p += [korish["id"], korish["id"]]
    if dan:
        shart.append("COALESCE(i.muddat, substr(i.yaratilgan,1,10))>=?")
        p.append(dan)
    if gacha:
        shart.append("COALESCE(i.muddat, substr(i.yaratilgan,1,10))<=?")
        p.append(gacha)
    idlar = baza.hammasi("SELECT i.id FROM ish i WHERE %s ORDER BY (i.muddat IS NULL), i.muddat, i.id DESC LIMIT %d"
                         % (" AND ".join(shart), limit), *p)
    return [ish(r["id"]) for r in idlar]


def kechikdi_kun(i: dict) -> int:
    if not i["muddat"] or i["holat"] not in OCHIQ:
        return 0
    return max(0, (vaqt.bugun() - date.fromisoformat(i["muddat"])).days)


def qisqa(i: dict) -> str:
    qism = [f"#{i['id']} {i['nom']}"]
    if i.get("joy"):
        qism.append(i["joy"])
    if i.get("muddat"):
        qism.append(vaqt.sana_matn(i["muddat"], False) + (f" {i['soat']}" if i.get("soat") else ""))
    return " · ".join(qism)


# ---------- yaratish ----------

def ish_yarat(nom: str, ijrochilar: list[tuple[int, float]], yaratgan_id: int, joy: str | None = None,
              mijoz_id: int | None = None, muddat: str | None = None, soat: str | None = None,
              narx: int | None = None, valyuta: str = "UZS", dalil_turi: str | None = None,
              ish_turi: str | None = None, tavsif: str | None = None, xabar_id: int | None = None,
              lat: float | None = None, lon: float | None = None, takror_id: int | None = None,
              takror_sana: str | None = None) -> tuple[int, list]:
    kim = odamlar.odam(yaratgan_id)
    nom = (nom or "").strip()
    if not nom:
        raise IshXato("Ish nomi bo'sh")
    if not ijrochilar:
        raise IshXato("Ijrochi tanlanmagan")
    boshqaga = any(o_id != yaratgan_id for o_id, _ in ijrochilar)
    manba = "boshliq"
    if not tolov_huquqi(kim):
        if boshqaga:
            raise IshXato("Boshqa xodimga ishni faqat boshliq yoki menejer beradi")
        manba = "xodim"
        narx = None  # I-f: xodim o'zi aytgan ishning narxini boshliq qo'yadi
    if valyuta not in ("UZS", "USD"):
        raise IshXato("Valyuta noto'g'ri")
    dalil_turi = dalil_turi or baza.sozlama("dalil_standart", "rasm")
    if dalil_turi not in DALIL_NOMI:
        dalil_turi = "rasm"
    if muddat:
        muddat = muddat[:10]
        date.fromisoformat(muddat)
    xabarlar = []
    with baza.tranz():
        iid = baza.bajar(
            "INSERT INTO ish(nom,tavsif,ish_turi,joy,lat,lon,mijoz_id,muddat,soat,narx,valyuta,dalil_turi,yaratgan_id,"
            "yaratilgan,xabar_id,takror_id,takror_sana,manba) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            nom[:200], tavsif, (ish_turi or "").strip().lower() or None, joy, lat, lon, mijoz_id, muddat, soat,
            int(narx) if narx else None, valyuta, dalil_turi, yaratgan_id, vaqt.iso(), xabar_id, takror_id, takror_sana,
            manba)
        for o_id, ulush in ijrochilar:
            baza.bajar("INSERT OR IGNORE INTO ish_ijrochi(ish_id,odam_id,ulush,korildi) VALUES(?,?,?,?)",
                       iid, o_id, float(ulush or 1), vaqt.iso() if o_id == yaratgan_id else None)
        baza.jurnal(yaratgan_id, "ish_yarat", f"ish:{iid}", None, {"nom": nom, "ijrochilar": ijrochilar, "narx": narx})
        i = ish(iid)
        for x in i["ijrochilar"]:
            if x["odam_id"] != yaratgan_id:
                xabarlar.append(hisob.xabarnoma(
                    x["odam_id"], "ish", f"Sizga yangi ish ({kim['ism'] if kim else 'Tizim'}):\n{ish_matni(i)}", None,
                    [["Ko'rdim", f"ik:{iid}"]]))
    return iid, [x for x in xabarlar if x]


def ish_matni(i: dict) -> str:
    q = [i["nom"]]
    if i.get("joy"):
        q.append(f"Joy: {i['joy']}")
    if i.get("mijoz"):
        q.append(f"Mijoz: {i['mijoz']}")
    if i.get("muddat"):
        q.append(f"Muddat: {vaqt.sana_matn(i['muddat'])}" + (f", {i['soat']}" if i.get("soat") else ""))
    if i.get("narx"):
        ijr = i.get("ijrochilar") or []
        q.append(f"Narxi: {matn.pul(i['narx'], i['valyuta'])}" + (f" ({len(ijr)} kishiga ulush bilan)" if len(ijr) > 1 else ""))
    q.append(f"Dalil: {DALIL_NOMI[i['dalil_turi']]}")
    return "\n".join(q)


def korildi(ish_id: int, odam_id: int) -> None:
    baza.bajar("UPDATE ish_ijrochi SET korildi=COALESCE(korildi, ?) WHERE ish_id=? AND odam_id=?", vaqt.iso(), ish_id, odam_id)


# ---------- bajarildi va dalil (I4, I5) ----------

def _ijrochimi(i: dict, odam_id: int) -> bool:
    return any(x["odam_id"] == odam_id for x in i["ijrochilar"])


def bajarildi_dedi(ish_id: int, odam_id: int, izoh: str | None = None, xabar_id: int | None = None) -> dict:
    i = ish(ish_id)
    if not i:
        raise IshXato("Ish topilmadi")
    o = odamlar.odam(odam_id)
    if not (_ijrochimi(i, odam_id) or tolov_huquqi(o)):
        raise IshXato("Bu ish sizga berilmagan")
    if i["holat"] not in OCHIQ:
        raise IshXato(f"Bu ish holati: {HOLAT_NOMI[i['holat']].lower()}")
    with baza.tranz():
        if izoh:
            baza.bajar("UPDATE ish SET izoh=COALESCE(izoh||'\n','')||? WHERE id=?", izoh[:500], ish_id)
        baza.jurnal(odam_id, "ish_bajarildi_dedi", f"ish:{ish_id}", i["holat"], izoh)
        if i["dalil_turi"] == "yoq":
            return _yopildi(ish_id, odam_id)
        baza.bajar("UPDATE ish SET holat='bajarildi_dalil' WHERE id=?", ish_id)
    return {"holat": "bajarildi_dalil", "dalil": i["dalil_turi"], "xabarlar": []}


def dalil_qosh(ish_id: int, odam_id: int | None, tur: str, xabar_id: int | None = None, fayl: str | None = None,
               lat: float | None = None, lon: float | None = None, uzatilgan: bool = False,
               mijoz_id: int | None = None, izoh: str | None = None) -> dict:
    """Dalil qo'shiladi; ish holati dalil turi talabiga mos kelsa — bajarildi."""
    i = ish(ish_id)
    if not i:
        raise IshXato("Ish topilmadi")
    if uzatilgan:
        raise IshXato("Boshqa chatdan uzatilgan rasm yoki joylashuv dalil bo'lmaydi — o'zingiz yuboring")
    if tur not in ("rasm", "joylashuv", "mijoz"):
        raise IshXato("Dalil turi noto'g'ri")
    if odam_id and not (_ijrochimi(i, odam_id) or tolov_huquqi(odamlar.odam(odam_id))):
        raise IshXato("Bu ish sizga berilmagan")
    if i["holat"] not in OCHIQ:
        raise IshXato(f"Bu ish holati: {HOLAT_NOMI[i['holat']].lower()}")
    m = None
    if tur == "joylashuv":
        if lat is None or lon is None:
            raise IshXato("Joylashuv kelmadi")
        if i["lat"] is not None and i["lon"] is not None:
            m = masofa(lat, lon, i["lat"], i["lon"])
            if m > JOY_RADIUS:
                baza.bajar("INSERT INTO ish_dalil(ish_id,tur,xabar_id,lat,lon,masofa,odam_id,izoh,vaqt) VALUES(?,?,?,?,?,?,?,?,?)",
                           ish_id, tur, xabar_id, lat, lon, m, odam_id, "uzoqda — qabul qilinmadi", vaqt.iso())
                raise IshXato(f"Siz ish joyidan {int(m)} m uzoqdasiz — ish joyiga yetib borgach yuboring")
    with baza.tranz():
        baza.bajar("INSERT INTO ish_dalil(ish_id,tur,xabar_id,fayl,lat,lon,masofa,odam_id,mijoz_id,izoh,vaqt) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?,?)", ish_id, tur, xabar_id, fayl, lat, lon, m, odam_id, mijoz_id, izoh,
                   vaqt.iso())
        baza.jurnal(odam_id, "ish_dalil", f"ish:{ish_id}", None, {"tur": tur, "masofa": m})
        kerak = i["dalil_turi"]
        if kerak in ("yoq", tur) or (kerak == "mijoz" and tur == "rasm" and not i["mijoz_tg"]):
            return _yopildi(ish_id, odam_id or i["ijrochilar"][0]["odam_id"])
    return {"holat": i["holat"], "dalil": kerak, "xabarlar": []}


def _yopildi(ish_id: int, odam_id: int) -> dict:
    """Ish bajarildi. Narxi bo'lsa yoki xodim o'zi aytgan bo'lsa — qabul kutiladi."""
    i = ish(ish_id)
    xabarlar = []
    baza.bajar("UPDATE ish SET holat='bajarildi', bajarildi_vaqt=?, bajargan_id=? WHERE id=?", vaqt.iso(), odam_id, ish_id)
    baza.jurnal(odam_id, "ish_yopildi", f"ish:{ish_id}")
    kim = odamlar.odam(odam_id)
    for x in i["ijrochilar"]:
        if x["odam_id"] != odam_id:
            xabarlar.append(hisob.xabarnoma(x["odam_id"], "malumot",
                                            f"{kim['ism']} ishni bajarildi deb yopdi: {qisqa(i)}"))
    qabul_kerak = bool(i["narx"]) or i["manba"] == "xodim"
    qabul_qiluvchi = i["yaratgan_id"] if i["manba"] == "boshliq" else (odamlar.boshliq() or {}).get("id")
    if qabul_qiluvchi and qabul_qiluvchi != odam_id:
        matn_ = (f"Bajarildi: {qisqa(i)}\nBajardi: {kim['ism']}" +
                 (f"\nNarxi: {matn.pul(i['narx'], i['valyuta'])}" if i["narx"] else "") +
                 (f"\n{AVTO_QABUL_SOAT} soatda e'tiroz bo'lmasa o'zi qabul qilinadi." if qabul_kerak and i["narx"] else ""))
        tug = [["Qabul qilish", f"iq:{ish_id}:1"], ["Qayta ishlash", f"iq:{ish_id}:0"]]
        if i["manba"] == "xodim":
            matn_ += "\nXodim o'zi aytgan ish — narxni panelda qo'yib qabul qiling."
        xabarlar.append(hisob.xabarnoma(qabul_qiluvchi, "ish_bajarildi", matn_, None, tug))
    return {"holat": "bajarildi", "dalil": i["dalil_turi"], "xabarlar": [x for x in xabarlar if x]}


# ---------- qabul va qayta (M4) ----------

def qabul(ish_id: int, kim_id: int, narx: int | None = None, avto: bool = False) -> dict:
    i = ish(ish_id)
    if not i:
        raise IshXato("Ish topilmadi")
    kim = odamlar.odam(kim_id)
    if not avto and not tolov_huquqi(kim):
        raise IshXato("Ishni boshliq yoki menejer qabul qiladi")
    if i["holat"] != "bajarildi":
        raise IshXato("Faqat bajarilgan ish qabul qilinadi")
    if narx is not None:
        if int(narx) < 0:
            raise IshXato("Narx noto'g'ri")
        baza.bajar("UPDATE ish SET narx=? WHERE id=?", int(narx) or None, ish_id)
        i = ish(ish_id)
    yozuvlar = []
    xabarlar = []
    with baza.tranz():
        bajarilgan = (i["bajarildi_vaqt"] or vaqt.iso())[:10]
        for odam_id, summa in ulush_taqsim(i["narx"] or 0, i["ijrochilar"]):
            if summa <= 0:
                continue
            maosh_v = hisob.hisob_valyuta(f"maosh:{odam_id}") or "UZS"
            s, v = summa, i["valyuta"]
            if v != maosh_v:  # I-e: bajarilgan kungi kurs bilan maosh valyutasiga
                o = kurs.ogir(summa, v, maosh_v, bajarilgan)
                if not o:
                    raise IshXato("Valyuta kursi topilmadi")
                s, v = o[0], maosh_v
            hid = hisob.taklif("ishbay", {"summa": s, "valyuta": v, "odam_id": odam_id, "sana": bajarilgan,
                                          "izoh": f"#{ish_id} {i['nom']}"[:200]}, kim_id, manba="tizim")
            hisob.faollashtir(hid, kim_id, qoida_tekshir=False)
            yozuvlar.append(hid)
            xabarlar.append(hisob.xabarnoma(odam_id, "malumot", f"Ish qabul qilindi: {qisqa(i)}\nHisobingizga: "
                                                               f"{matn.pul(s, v)}"))
        baza.bajar("UPDATE ish SET holat='qabul', qabul_vaqt=?, qabul_id=? WHERE id=?", vaqt.iso(), kim_id, ish_id)
        baza.jurnal(kim_id, "ish_qabul", f"ish:{ish_id}", None, {"avto": avto, "yozuvlar": yozuvlar})
    return {"yozuvlar": yozuvlar, "xabarlar": [x for x in xabarlar if x]}


def qayta(ish_id: int, kim_id: int, sabab: str) -> list:
    i = ish(ish_id)
    if not i:
        raise IshXato("Ish topilmadi")
    if not tolov_huquqi(odamlar.odam(kim_id)):
        raise IshXato("Faqat boshliq yoki menejer")
    if i["holat"] not in ("bajarildi", "bajarildi_dalil"):
        raise IshXato("Faqat bajarilgan ish qaytariladi")
    if not (sabab or "").strip():
        raise IshXato("Sabab yozilsin")
    xabarlar = []
    with baza.tranz():
        baza.bajar("UPDATE ish SET holat='qayta', sabab=? WHERE id=?", sabab[:300], ish_id)
        baza.jurnal(kim_id, "ish_qayta", f"ish:{ish_id}", None, sabab)
        for x in i["ijrochilar"]:
            xabarlar.append(hisob.xabarnoma(x["odam_id"], "ish", f"Ish qayta ishlansin: {qisqa(i)}\nSabab: {sabab}", None,
                                            [["Ko'rdim", f"ik:{ish_id}"]]))
    return [x for x in xabarlar if x]


def muddat_ozgar(ish_id: int, kim_id: int, yangi: str | None, sabab: str) -> None:
    """I7: muddat faqat sababi bilan o'zgaradi."""
    i = ish(ish_id)
    if not i or i["holat"] not in OCHIQ:
        raise IshXato("Faqat ochiq ishning muddati o'zgaradi")
    if not tolov_huquqi(odamlar.odam(kim_id)):
        raise IshXato("Faqat boshliq yoki menejer")
    if not (sabab or "").strip():
        raise IshXato("Sabab yozilsin")
    if yangi:
        date.fromisoformat(yangi[:10])
    with baza.tranz():
        baza.bajar("UPDATE ish SET muddat=? WHERE id=?", yangi[:10] if yangi else None, ish_id)
        baza.jurnal(kim_id, "ish_muddat", f"ish:{ish_id}", i["muddat"], {"yangi": yangi, "sabab": sabab})


def bekor(ish_id: int, kim_id: int, sabab: str) -> None:
    i = ish(ish_id)
    if not i or i["holat"] in ("qabul", "bekor"):
        raise IshXato("Bu ishni bekor qilib bo'lmaydi")
    kim = odamlar.odam(kim_id)
    if not (tolov_huquqi(kim) or (i["manba"] == "xodim" and i["yaratgan_id"] == kim_id)):
        raise IshXato("Faqat boshliq yoki menejer")
    if not (sabab or "").strip():
        raise IshXato("Sabab yozilsin")
    with baza.tranz():
        baza.bajar("UPDATE ish SET holat='bekor', sabab=? WHERE id=?", sabab[:300], ish_id)
        baza.jurnal(kim_id, "ish_bekor", f"ish:{ish_id}", i["holat"], sabab)


def avto_qabul() -> list:
    """24 soatda e'tiroz bo'lmagan, narxi bor ishlar o'zi qabul qilinadi (M4)."""
    chegara = vaqt.iso(vaqt.hozir() - timedelta(hours=AVTO_QABUL_SOAT))
    xabarlar = []
    for r in baza.hammasi("SELECT id, yaratgan_id FROM ish WHERE holat='bajarildi' AND narx>0 AND manba='boshliq' "
                          "AND bajarildi_vaqt<=?", chegara):
        try:
            xabarlar += qabul(r["id"], r["yaratgan_id"], avto=True)["xabarlar"]
        except (IshXato, hisob.HisobXato):
            continue
    return xabarlar


def kutilayotgan_pul(odam_id: int) -> list[dict]:
    """Bajarilgan, lekin hali qabul qilinmagan ishlardan keladigan ulush (varaqda «kutilmoqda»)."""
    natija = []
    for r in baza.hammasi("SELECT i.id FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? "
                          "AND i.holat IN ('bajarildi','bajarildi_dalil') AND i.narx>0", odam_id):
        i = ish(r["id"])
        for o_id, summa in ulush_taqsim(i["narx"], i["ijrochilar"]):
            if o_id == odam_id and summa > 0:
                natija.append({"ish_id": i["id"], "nom": f"#{i['id']} {i['nom']}", "summa": summa,
                               "valyuta": i["valyuta"], "holat": i["holat"]})
    return natija


# ---------- takroriy ishlar (I8) ----------

def takroriy_qoy(nom: str, ijrochilar: list[int], davr: str, kun: int | None, kim_id: int, narx: int | None = None,
                 valyuta: str = "UZS", dalil_turi: str = "yoq", joy: str | None = None, ish_turi: str | None = None) -> int:
    if not tolov_huquqi(odamlar.odam(kim_id)):
        raise IshXato("Faqat boshliq yoki menejer")
    if davr not in ("har_kun", "har_hafta", "har_oy"):
        raise IshXato("Davr noto'g'ri")
    if davr == "har_hafta" and not (0 <= int(kun) <= 6):
        raise IshXato("Hafta kuni 0–6 bo'lsin")
    if davr == "har_oy" and not (1 <= int(kun) <= 28):
        raise IshXato("Oy kuni 1–28 bo'lsin")
    if not ijrochilar:
        raise IshXato("Ijrochi tanlanmagan")
    tid = baza.bajar("INSERT INTO takroriy_ish(nom,ijrochilar,davr,kun,narx,valyuta,dalil_turi,joy,ish_turi,yaratgan_id,"
                     "yaratilgan) VALUES(?,?,?,?,?,?,?,?,?,?,?)", nom.strip(), json.dumps(ijrochilar), davr, kun,
                     narx, valyuta, dalil_turi, joy, ish_turi, kim_id, vaqt.iso())
    baza.jurnal(kim_id, "takroriy_ish", f"takror:{tid}", None, {"nom": nom, "davr": davr, "kun": kun})
    return tid


def dam_olishmi(d: date) -> bool:
    return d.weekday() in set(baza.sozlama("dam_olish_kunlari", [6]))


def takroriy_yarat(bugun: date | None = None) -> list:
    """Bugun kerak bo'lgan takroriy ishlar yaratiladi — bir kunga bir marta (I-g)."""
    bugun = bugun or vaqt.bugun()
    xabarlar = []
    for t in baza.hammasi("SELECT * FROM takroriy_ish WHERE faol=1"):
        kerak = ((t["davr"] == "har_kun" and not dam_olishmi(bugun)) or
                 (t["davr"] == "har_hafta" and bugun.weekday() == t["kun"]) or
                 (t["davr"] == "har_oy" and bugun.day == t["kun"]))
        if not kerak:
            continue
        if baza.bir("SELECT 1 FROM ish WHERE takror_id=? AND takror_sana=?", t["id"], bugun.isoformat()):
            continue
        ijr = [(int(x), 1) for x in json.loads(t["ijrochilar"]) if odamlar.odam(int(x))]
        if not ijr:
            continue
        try:
            _, x = ish_yarat(t["nom"], ijr, t["yaratgan_id"], joy=t["joy"], muddat=bugun.isoformat(), narx=t["narx"],
                             valyuta=t["valyuta"], dalil_turi=t["dalil_turi"], ish_turi=t["ish_turi"], takror_id=t["id"],
                             takror_sana=bugun.isoformat())
            xabarlar += x
        except Exception:
            continue
    return xabarlar


# ---------- ko'nikma va taklif (O2, O3) ----------

def konikma(odam_id: int) -> list[dict]:
    """Qilgan ishlaridan: tur bo'yicha soni, vaqtida, qayta ishlangan. Ball/reyting YO'Q (O2)."""
    natija = {}
    for r in baza.hammasi(
            "SELECT i.*, (SELECT COUNT(*) FROM jurnal j WHERE j.obyekt='ish:'||i.id AND j.amal='ish_qayta') qayta_soni "
            "FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? AND i.holat IN ('bajarildi','qabul')",
            odam_id):
        tur = r["ish_turi"] or "boshqa"
        x = natija.setdefault(tur, {"tur": tur, "soni": 0, "vaqtida": 0, "qayta": 0, "oxirgi": None})
        x["soni"] += 1
        if r["muddat"] and r["bajarildi_vaqt"] and r["bajarildi_vaqt"][:10] <= r["muddat"]:
            x["vaqtida"] += 1
        x["qayta"] += r["qayta_soni"]
        x["oxirgi"] = max(x["oxirgi"] or "", (r["bajarildi_vaqt"] or "")[:10]) or None
    return sorted(natija.values(), key=lambda x: -x["soni"])


def ijrochi_taklif(ish_turi: str | None) -> list[dict]:
    """Yangi ish kimga: kim bunday ishni qilgan va hozir kimda nechta ochiq ish bor (O3) — qaror odamda."""
    natija = []
    for o in odamlar.faol_odamlar():
        if o["holat"] != "faol":
            continue
        ochiq = baza.qiymat("SELECT COUNT(*) FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? "
                            "AND i.holat IN ('yangi','bajarildi_dalil','qayta')", o["id"])
        qilgan = 0
        if ish_turi:
            qilgan = baza.qiymat("SELECT COUNT(*) FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? "
                                 "AND i.holat IN ('bajarildi','qabul') AND i.ish_turi=?", o["id"], ish_turi.lower())
        natija.append({"odam_id": o["id"], "ism": o["ism"], "qilgan": qilgan, "ochiq": ochiq})
    natija.sort(key=lambda x: (-x["qilgan"], x["ochiq"]))
    return natija


def tahrirla(ish_id: int, kim_id: int, nom: str | None = None, joy: str | None = None, muddat: str | None = "",
             soat: str | None = "", narx: int | None = -1, ijrochilar: list[int] | None = None, sabab: str = "") -> list:
    """CRM2: ochiq ishni paneldan tahrirlash (nom, joy, muddat, soat, narx, ijrochilar). Yangi ijrochiga xabar boradi."""
    i = ish(ish_id)
    if not i or i["holat"] not in OCHIQ:
        raise IshXato("Faqat ochiq ish tahrirlanadi")
    kim = odamlar.odam(kim_id)
    if not tolov_huquqi(kim):
        raise IshXato("Faqat boshliq yoki menejer")
    yangi = {"nom": (nom if nom is not None else i["nom"]).strip()[:200],
             "joy": (joy if joy is not None else i["joy"] or "").strip() or None,
             "muddat": i["muddat"] if muddat == "" else (muddat or "")[:10] or None,
             "soat": i["soat"] if soat == "" else soat or None,
             "narx": i["narx"] if narx == -1 else (int(narx) if narx else None)}
    if not yangi["nom"]:
        raise IshXato("Ish nomi bo'sh")
    if yangi["muddat"]:
        date.fromisoformat(yangi["muddat"])
    if yangi["muddat"] != i["muddat"] and not (sabab or "").strip():
        raise IshXato("Muddat o'zgarsa — sababini yozing")  # I7
    eski_ijr = {x["odam_id"] for x in i["ijrochilar"]}
    yangi_ijr = set(ijrochilar) if ijrochilar is not None else eski_ijr
    if not yangi_ijr:
        raise IshXato("Ijrochi tanlanmagan")
    xabarlar = []
    with baza.tranz():
        baza.bajar("UPDATE ish SET nom=?, joy=?, muddat=?, soat=?, narx=? WHERE id=?", yangi["nom"], yangi["joy"],
                   yangi["muddat"], yangi["soat"], yangi["narx"], ish_id)
        for o_id in eski_ijr - yangi_ijr:
            baza.bajar("DELETE FROM ish_ijrochi WHERE ish_id=? AND odam_id=?", ish_id, o_id)
            xabarlar.append(hisob.xabarnoma(o_id, "malumot", f"Ish sizdan olindi: {qisqa(i)}"))
        for o_id in yangi_ijr - eski_ijr:
            baza.bajar("INSERT OR IGNORE INTO ish_ijrochi(ish_id,odam_id,ulush) VALUES(?,?,1)", ish_id, o_id)
        baza.jurnal(kim_id, "ish_tahrir", f"ish:{ish_id}",
                    {k: i[k] for k in ("nom", "joy", "muddat", "soat", "narx")} | {"ijrochilar": sorted(eski_ijr)},
                    yangi | {"ijrochilar": sorted(yangi_ijr), "sabab": sabab or None})
        j = ish(ish_id)
        for o_id in yangi_ijr - eski_ijr:
            if o_id != kim_id:
                xabarlar.append(hisob.xabarnoma(o_id, "ish", f"Sizga ish berildi ({kim['ism']}):\n{ish_matni(j)}", None,
                                                [["Ko'rdim", f"ik:{ish_id}"]]))
        if (yangi["muddat"], yangi["soat"]) != (i["muddat"], i["soat"]):
            for o_id in (yangi_ijr & eski_ijr) - {kim_id}:
                xabarlar.append(hisob.xabarnoma(o_id, "malumot", f"Ish vaqti o'zgardi: {qisqa(j)}"))
    return [x for x in xabarlar if x]
