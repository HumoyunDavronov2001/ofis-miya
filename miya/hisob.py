"""Pul hisobi — ikki yoqlama yozuv (P, K5, K6, K10, P4, A4).

Har harakat bir hisobdan (`dan`) boshqasiga (`ga`) pul yoki qiymat o'tkazadi. Hisob qoldig'i = kirgan − chiqqan.
Hisob kalitlari:
  kassa:N   — kassa (naqd, karta, bank, boshliq cho'ntagi)
  qol:N     — N-xodim qo'lidagi pul (kassaga topshirilmagan)
  maosh:N   — N-xodim bilan maosh hisobi (manfiy = biz unga qarzmiz)
  xqarz:N   — N-xodimga berilgan qarz (musbat = u bizga qarz)
  mijoz:N   — mijoz (musbat = u bizga qarz)
  taminotchi:N — ta'minotchi (manfiy = biz unga qarzmiz)
  xarajat:N — xarajat turi
  sotuv, ishhaqi, egasi, boshlangich, boshqa_kirim — umumiy hisoblar

Ikki tomonlama tasdiq: `dan` tomoni beruvchi tasdiqlaganda, `ga` tomoni oluvchi tasdiqlaganda hisobga kiradi.
Raqamni faqat shu modul hisoblaydi — sun'iy intellekt bu yerga faqat taklif yuboradi (X3).
"""
import json
from datetime import datetime, timedelta

from . import baza, kurs, matn, odamlar, qoida, vadalar, vaqt


class HisobXato(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato (o'zbekcha)."""


SHABLON = {
    # tur: (nom, dan, ga, pul_otadi)
    "kirim": ("Kirim", "mijoz_yoki_boshqa", "kassa", True),
    "chiqim": ("Xarajat", "kassa_yoki_qol", "xarajat", True),
    "otkazma": ("Kassadan kassaga", "kassa", "kassa2", True),
    "avans": ("Avans", "kassa", "maosh", True),
    "maosh_tolov": ("Maosh to'lovi", "kassa", "maosh", True),
    "qolga_berish": ("Xodimga xarajat uchun pul", "kassa", "qol", True),
    "qoldan_qaytarish": ("Xodim pulni kassaga topshirdi", "qol", "kassa", True),
    "mijozdan_qolga": ("Xodim mijozdan pul oldi", "mijoz", "qol", True),
    "sotuv": ("Sotuv", "sotuv", "mijoz", False),
    "egasi_oldi": ("Egasi oldi", "kassa", "egasi", True),
    "egasi_qoydi": ("Egasi qo'ydi", "egasi", "kassa", True),
    "xodim_qarz": ("Xodimga qarz", "kassa", "xqarz", True),
    "qarz_qaytdi": ("Xodim qarzini qaytardi", "xqarz", "kassa", True),
    "qarzdan_ushlash": ("Qarz maoshdan ushlandi", "xqarz", "maosh", False),
    "bonus": ("Bonus", "maosh", "ishhaqi", False),
    "ishbay": ("Ishbay ish haqi", "maosh", "ishhaqi", False),
    "jarima": ("Jarima", "ishhaqi", "maosh", False),
    "hisoblandi": ("Maosh hisoblandi", "maosh", "ishhaqi", False),
    "taminotchi_nasiya": ("Nasiyaga olindi", "taminotchi", "xarajat", False),
    "taminotchiga_tolov": ("Ta'minotchiga to'lov", "kassa", "taminotchi", True),
    "boshlangich_kassa": ("Kassadagi boshlang'ich pul", "boshlangich", "kassa", False),
    "boshlangich_maosh": ("Xodimga avvaldan qarzimiz", "maosh", "boshlangich", False),
    "boshlangich_mijoz": ("Mijozning avvaldan qarzi", "boshlangich", "mijoz", False),
    "boshlangich_taminotchi": ("Ta'minotchiga avvaldan qarzimiz", "taminotchi", "boshlangich", False),
    "tuzatish": ("Tuzatish (teskari yozuv)", "", "", False),
}
ODAM_KERAK = {"avans", "maosh_tolov", "qolga_berish", "qoldan_qaytarish", "mijozdan_qolga", "xodim_qarz",
              "qarz_qaytdi", "qarzdan_ushlash", "bonus", "ishbay", "jarima", "hisoblandi", "boshlangich_maosh"}
MIJOZ_KERAK = {"mijozdan_qolga", "sotuv", "taminotchi_nasiya", "taminotchiga_tolov", "boshlangich_mijoz",
               "boshlangich_taminotchi"}
FAQAT_BOSHLIQ = {"bonus", "jarima", "hisoblandi", "boshlangich_kassa", "boshlangich_maosh", "boshlangich_mijoz",
                 "boshlangich_taminotchi", "qarzdan_ushlash"}
SANALADI = ("faol", "nizo")
TAKROR_SOAT = 2


# ---------- hisob kalitlari ----------

def ajrat(kalit: str) -> tuple[str, int | None]:
    t, _, i = kalit.partition(":")
    return t, (int(i) if i.isdigit() else None)


def kassa(kassa_id: int | None) -> dict | None:
    return baza.bir("SELECT * FROM kassa WHERE id=?", kassa_id) if kassa_id else None


def kassalar(faqat_faol: bool = True) -> list[dict]:
    return baza.hammasi("SELECT * FROM kassa %s ORDER BY tur='chontak', id" % ("WHERE faol=1" if faqat_faol else ""))


def kassa_yarat(nom: str, tur: str, valyuta: str, masul_id: int | None, kim_id: int) -> int:
    if tur not in ("naqd", "karta", "bank", "chontak") or valyuta not in ("UZS", "USD"):
        raise HisobXato("Kassa turi yoki valyutasi noto'g'ri")
    with baza.tranz():
        kid = baza.bajar("INSERT INTO kassa(nom,tur,valyuta,masul_id) VALUES(?,?,?,?)",
                         nom.strip(), tur, valyuta, masul_id)
        baza.jurnal(kim_id, "kassa_yarat", f"kassa:{kid}", None, {"nom": nom, "tur": tur, "valyuta": valyuta})
    return kid


def hisob_valyuta(kalit: str) -> str | None:
    """Qat'iy valyutali hisoblar: kassa — o'z valyutasi, maosh — maosh valyutasi. Qolganlari erkin (None)."""
    t, i = ajrat(kalit)
    if t == "kassa":
        k = kassa(i)
        return k["valyuta"] if k else None
    if t == "maosh":
        r = baza.bir("SELECT valyuta FROM maosh_shart WHERE odam_id=? ORDER BY dan_sana DESC, id DESC LIMIT 1", i)
        return r["valyuta"] if r else "UZS"
    return None


def masul(kalit: str) -> int | None:
    """Hisob uchun javobgar ishxona odami (tasdiq beradigan). Tashqi hisob — None."""
    t, i = ajrat(kalit)
    if t == "kassa":
        k = kassa(i)
        return k["masul_id"] if k else None
    if t in ("qol", "maosh", "xqarz"):
        return i
    if t == "egasi":
        b = odamlar.boshliq()
        return b["id"] if b else None
    return None


def hisob_nomi(kalit: str) -> str:
    t, i = ajrat(kalit)
    if t == "kassa":
        k = kassa(i)
        return k["nom"] if k else "kassa"
    if t in ("qol", "maosh", "xqarz"):
        o = odamlar.odam(i)
        ism = o["ism"] if o else "?"
        return {"qol": f"{ism} qo'lidagi pul", "maosh": f"{ism} maoshi", "xqarz": f"{ism} qarzi"}[t]
    if t in ("mijoz", "taminotchi"):
        m = baza.bir("SELECT ism FROM mijoz WHERE id=?", i)
        return m["ism"] if m else "?"
    if t == "xarajat":
        x = baza.bir("SELECT nom FROM xarajat_turi WHERE id=?", i)
        return f"Xarajat: {x['nom']}" if x else "Xarajat"
    return {"sotuv": "Sotuv", "ishhaqi": "Ish haqi", "egasi": "Egasi", "boshlangich": "Boshlang'ich qoldiq",
            "boshqa_kirim": "Boshqa kirim"}.get(t, kalit)


# ---------- qoldiq ----------

def qoldiq(kalit: str, gacha: str | None = None) -> dict[str, int]:
    """Valyuta bo'yicha qoldiq (minor birlikda). Faqat tasdiqlangan tomonlar sanaladi."""
    shart_sana = " AND hisob_sana<=?" if gacha else ""
    p = (kalit, gacha) if gacha else (kalit,)
    natija: dict[str, int] = {}
    for r in baza.hammasi(
            "SELECT COALESCE(valyuta2,valyuta) v, SUM(COALESCE(summa2,summa)) s FROM harakat WHERE ga=? "
            "AND holat IN ('faol','nizo') AND oluvchi_holat IN ('kerak_emas','tasdiq')" + shart_sana + " GROUP BY v", *p):
        natija[r["v"]] = natija.get(r["v"], 0) + r["s"]
    for r in baza.hammasi(
            "SELECT valyuta v, SUM(summa) s FROM harakat WHERE dan=? "
            "AND holat IN ('faol','nizo') AND beruvchi_holat IN ('kerak_emas','tasdiq')" + shart_sana + " GROUP BY v", *p):
        natija[r["v"]] = natija.get(r["v"], 0) - r["s"]
    return {v: s for v, s in natija.items() if s}


def qoldiq_bir(kalit: str, valyuta: str = "UZS", gacha: str | None = None) -> int:
    return qoldiq(kalit, gacha).get(valyuta, 0)


def kutilayotgan(kalit: str) -> dict:
    """Tasdiqlanmagan tomonlar: chiqim (beruvchi kutmoqda) va kirim (oluvchi kutmoqda)."""
    chiq = baza.hammasi("SELECT * FROM harakat WHERE dan=? AND holat IN ('faol','nizo') AND beruvchi_holat='kutilmoqda'",
                        kalit)
    kir = baza.hammasi("SELECT * FROM harakat WHERE ga=? AND holat IN ('faol','nizo') AND oluvchi_holat='kutilmoqda'",
                       kalit)
    return {"chiqim": chiq, "kirim": kir,
            "chiqim_jami": sum(r["summa"] for r in chiq),
            "kirim_jami": sum((r["summa2"] or r["summa"]) for r in kir)}


def kassa_holati() -> list[dict]:
    natija = []
    for k in kassalar():
        kal = f"kassa:{k['id']}"
        kut = kutilayotgan(kal)
        oxirgi = baza.bir("SELECT * FROM kassa_sanoq WHERE kassa_id=? ORDER BY sana DESC LIMIT 1", k["id"])
        natija.append({**k, "qoldiq": qoldiq_bir(kal, k["valyuta"]), "kutilayotgan": kut, "oxirgi_sanoq": oxirgi})
    return natija


# ---------- sanalar ----------

def _oxirgi_sanoq(kassa_id: int) -> str | None:
    return baza.qiymat("SELECT MAX(sana) FROM kassa_sanoq WHERE kassa_id=?", kassa_id)


def oy_yopiqmi(oy: str) -> bool:
    return baza.qiymat("SELECT holat FROM maosh_davr WHERE oy=?", oy) == "yopiq"


def _hisob_sana(voqea_sana: str, dan: str, ga: str) -> tuple[str, int]:
    """Sanalgan kun va yopilgan oy qayta ochilmaydi (P4, M9): kech yozuv bugungi kunga tushadi."""
    bugun = vaqt.bugun().isoformat()
    for kal in (dan, ga):
        t, i = ajrat(kal)
        if t == "kassa":
            s = _oxirgi_sanoq(i)
            if s and voqea_sana <= s and voqea_sana < bugun:
                return bugun, 1
        if t in ("maosh", "xqarz") and oy_yopiqmi(vaqt.oy(voqea_sana)):
            return bugun, 1
    return voqea_sana, 0


# ---------- taklif (kartochka) ----------

def _xarajat_turi_id(nom_yoki_id) -> int:
    if isinstance(nom_yoki_id, int):
        return nom_yoki_id
    nom = (nom_yoki_id or "Boshqa").strip() or "Boshqa"
    r = baza.bir("SELECT id FROM xarajat_turi WHERE lower(nom)=lower(?)", nom)
    if r:
        return r["id"]
    return baza.bajar("INSERT INTO xarajat_turi(nom) VALUES(?)", nom[:1].upper() + nom[1:])


def hisoblarni_tuz(tur: str, p: dict) -> tuple[str, str]:
    """Shablon + parametrlar → (dan, ga)."""
    if tur not in SHABLON or tur == "tuzatish":
        raise HisobXato("Noma'lum yozuv turi")
    _, dan_r, ga_r, _ = SHABLON[tur]

    def rol(r: str) -> str:
        if r == "kassa":
            if not p.get("kassa_id"):
                raise HisobXato("Qaysi kassa — aniqlanmadi")
            return f"kassa:{p['kassa_id']}"
        if r == "kassa2":
            if not p.get("kassa2_id"):
                raise HisobXato("Qaysi kassaga — aniqlanmadi")
            return f"kassa:{p['kassa2_id']}"
        if r in ("maosh", "qol", "xqarz"):
            if not p.get("odam_id"):
                raise HisobXato("Qaysi xodim — aniqlanmadi")
            return f"{r}:{p['odam_id']}"
        if r == "mijoz":
            if not p.get("mijoz_id"):
                raise HisobXato("Qaysi mijoz — aniqlanmadi")
            return f"mijoz:{p['mijoz_id']}"
        if r == "taminotchi":
            if not p.get("mijoz_id"):
                raise HisobXato("Qaysi ta'minotchi — aniqlanmadi")
            return f"taminotchi:{p['mijoz_id']}"
        if r == "mijoz_yoki_boshqa":
            return f"mijoz:{p['mijoz_id']}" if p.get("mijoz_id") else "boshqa_kirim"
        if r == "kassa_yoki_qol":
            if p.get("qoldan") and p.get("odam_id"):
                return f"qol:{p['odam_id']}"
            return rol("kassa")
        if r == "xarajat":
            return f"xarajat:{_xarajat_turi_id(p.get('xarajat_turi_id') or p.get('xarajat_turi'))}"
        return r

    dan, ga = rol(dan_r), rol(ga_r)
    if dan == ga:
        raise HisobXato("Pul o'sha hisobning o'ziga o'tkazilmaydi")
    return dan, ga


def taklif(tur: str, p: dict, yozgan_id: int | None, xabar_id: int | None = None, manba: str = "aytilgan") -> int:
    """Kartochka uchun taklif yozuvi (hali hisobga kirmaydi)."""
    summa = int(p.get("summa") or 0)
    valyuta = p.get("valyuta") or "UZS"
    if summa <= 0:
        raise HisobXato("Summa aniqlanmadi")
    if valyuta not in ("UZS", "USD"):
        raise HisobXato("Valyuta noto'g'ri")
    if tur in ODAM_KERAK and not p.get("odam_id"):
        raise HisobXato("Qaysi xodim — aniqlanmadi")
    if tur in MIJOZ_KERAK and not p.get("mijoz_id"):
        raise HisobXato("Qaysi mijoz — aniqlanmadi")
    dan, ga = hisoblarni_tuz(tur, p)
    voqea = (p.get("sana") or vaqt.bugun().isoformat())[:10]
    if voqea > vaqt.bugun().isoformat():
        raise HisobXato("Kelajakdagi sana — bu va'da bo'lishi mumkin, pul harakati emas")
    # valyutalar mos kelmasa — o'sha kungi kurs bilan ikkinchi summa (P11)
    summa2 = valyuta2 = k = None
    dan_v, ga_v = hisob_valyuta(dan), hisob_valyuta(ga)
    if dan_v and dan_v != valyuta:
        raise HisobXato(f"{hisob_nomi(dan)} — {dan_v} kassasi, summa {valyuta} da aytildi")
    if ga_v and ga_v != valyuta:
        ogir = kurs.ogir(summa, valyuta, ga_v, voqea)
        if not ogir:
            raise HisobXato("Valyuta kursi topilmadi — kursni kiriting")
        summa2, k = ogir
        valyuta2 = ga_v
    hid = baza.bajar(
        "INSERT INTO harakat(tur,dan,ga,summa,valyuta,summa2,valyuta2,kurs,odam_id,mijoz_id,xarajat_turi_id,"
        "sotuvchi_id,izoh,iqtibos,voqea_sana,hisob_sana,yozilgan,yozgan_id,xabar_id,holat,manba,muddat) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'taklif',?,?)",
        tur, dan, ga, summa, valyuta, summa2, valyuta2, k, p.get("odam_id"), p.get("mijoz_id"),
        ajrat(ga)[1] if ga.startswith("xarajat:") else None, p.get("sotuvchi_id"), p.get("izoh"),
        p.get("iqtibos"), voqea, voqea, vaqt.iso(), yozgan_id, xabar_id, manba, p.get("muddat"))
    if xabar_id:
        baza.bajar("INSERT OR IGNORE INTO harakat_manba(harakat_id,xabar_id) VALUES(?,?)", hid, xabar_id)
    return hid


def harakat(hid: int) -> dict | None:
    return baza.bir("SELECT * FROM harakat WHERE id=?", hid)


def yozishi_mumkin(o: dict, tur: str) -> bool:
    if not o or o["holat"] != "faol":
        return False
    if tur in FAQAT_BOSHLIQ:
        return o["rol"] == "boshliq"
    if tur == "ishbay":
        return o["rol"] in ("boshliq", "menejer")
    if tur in ("egasi_oldi", "egasi_qoydi"):
        return o["rol"] in ("boshliq", "kassir")
    return True


# ---------- takror (K10) ----------

def takrorlar(hid: int) -> list[dict]:
    h = harakat(hid)
    if not h:
        return []
    vaqt0 = datetime.fromisoformat(h["yozilgan"])
    dan_v = (vaqt0 - timedelta(hours=TAKROR_SOAT)).isoformat(timespec="seconds")
    gacha_v = (vaqt0 + timedelta(hours=TAKROR_SOAT)).isoformat(timespec="seconds")
    turlar = {h["tur"]}
    if h["tur"] in ("avans", "maosh_tolov"):
        turlar = {"avans", "maosh_tolov"}
    nomzod = baza.hammasi(
        "SELECT * FROM harakat WHERE id!=? AND holat IN ('faol','taklif','ruxsat_kutilmoqda','nizo') "
        "AND summa=? AND valyuta=? AND COALESCE(odam_id,0)=COALESCE(?,0) AND COALESCE(mijoz_id,0)=COALESCE(?,0) "
        "AND COALESCE(xarajat_turi_id,0)=COALESCE(?,0) "
        "AND tur IN (%s) AND ((yozilgan BETWEEN ? AND ?) OR voqea_sana=?) ORDER BY id" % ",".join("?" * len(turlar)),
        hid, h["summa"], h["valyuta"], h["odam_id"], h["mijoz_id"], h["xarajat_turi_id"], *turlar, dan_v, gacha_v,
        h["voqea_sana"])
    # bir xil chek rasmi
    xeshlar = [r["xesh"] for r in baza.hammasi("SELECT xesh FROM ilova WHERE harakat_id=? AND xesh IS NOT NULL", hid)]
    if xeshlar:
        for r in baza.hammasi(
                "SELECT DISTINCT h.* FROM ilova i JOIN harakat h ON h.id=i.harakat_id WHERE i.xesh IN (%s) AND h.id!=? "
                "AND h.holat!='bekor'" % ",".join("?" * len(xeshlar)), *xeshlar, hid):
            if r["id"] not in {n["id"] for n in nomzod}:
                nomzod.append(r)
    return [n for n in nomzod if n["holat"] != "taklif" or n["yozgan_id"] != h["yozgan_id"]]


def birlashtir(yangi_id: int, eski_id: int, kim_id: int) -> list[dict]:
    """Takror — yangisi bekor, manbasi eskisiga qo'shiladi; yozgan odam kutilayotgan tomon bo'lsa — tasdiq."""
    yangi, eski = harakat(yangi_id), harakat(eski_id)
    if not yangi or not eski:
        raise HisobXato("Yozuv topilmadi")
    xabarlar = []
    with baza.tranz():
        baza.bajar("UPDATE harakat SET holat='bekor', bekor_sabab=? WHERE id=?", f"takror: #{eski_id}", yangi_id)
        if yangi["xabar_id"]:
            baza.bajar("INSERT OR IGNORE INTO harakat_manba(harakat_id,xabar_id) VALUES(?,?)", eski_id, yangi["xabar_id"])
        baza.bajar("UPDATE ilova SET harakat_id=? WHERE harakat_id=?", eski_id, yangi_id)
        baza.jurnal(kim_id, "takror_birlashtirildi", f"harakat:{eski_id}", {"yangi": yangi_id}, None)
        if eski["holat"] in ("faol", "nizo"):
            if eski["beruvchi_holat"] == "kutilmoqda" and eski["beruvchi_id"] == kim_id:
                xabarlar += tomon_tasdiq(eski_id, kim_id, "beruvchi", True)
            elif eski["oluvchi_holat"] == "kutilmoqda" and eski["oluvchi_id"] == kim_id:
                xabarlar += tomon_tasdiq(eski_id, kim_id, "oluvchi", True)
    return xabarlar


# ---------- faollashtirish va tasdiq (K5, K6, Q2) ----------

def xabarnoma(odam_id: int | None, tur: str, matn_: str, harakat_id: int | None = None,
              tugmalar: list | None = None) -> dict | None:
    """Botga chiqadigan xabar navbati (bot o'chiq bo'lsa ham yo'qolmaydi)."""
    if not odam_id:
        return None
    xid = baza.bajar("INSERT INTO xabarnoma(odam_id,tur,harakat_id,matn,tugmalar,vaqt) VALUES(?,?,?,?,?,?)",
                     odam_id, tur, harakat_id, matn_, json.dumps(tugmalar or [], ensure_ascii=False), vaqt.iso())
    return {"id": xid, "odam_id": odam_id, "tur": tur}


def tasdiqla(hid: int, kim_id: int) -> dict:
    """Yozgan odam kartochkani tasdiqladi → qoidalar → faol yoki ruxsat kutilmoqda.

    Qaytaradi: {"holat": ..., "takrorlar": [...], "xabarlar": [...]}
    """
    h = harakat(hid)
    if not h or h["holat"] != "taklif":
        raise HisobXato("Bu yozuv allaqachon ishlangan")
    kim = odamlar.odam(kim_id)
    if not yozishi_mumkin(kim, h["tur"]):
        raise HisobXato("Bu turdagi yozuvni faqat boshliq kirita oladi")
    tak = takrorlar(hid)
    if tak:
        return {"holat": "takror", "takrorlar": tak, "xabarlar": []}
    return faollashtir(hid, kim_id)


XODIM_TASDIQ_STANDART = "1"  # R4: sozlama «xodim_tasdiq» bo'lmasa — xodim yozuvi boshliq tasdig'isiz kirmaydi


def faollashtir(hid: int, kim_id: int, qoida_tekshir: bool = True) -> dict:
    h = harakat(hid)
    kim = odamlar.odam(kim_id)
    xabarlar = []
    with baza.tranz():
        buzilish = None  # None — boshliq tasdig'i kerak emas; ro'yxat (bo'sh ham) — kerak
        if qoida_tekshir and not odamlar.boshliqmi(kim):
            # R4: xodim yozgan pul — boshliq tasdig'i bilan (sozlama, sukut — yoqilgan); qoida buzilsa sababi ham aytiladi
            buzilish = qoida.tekshir(h, kim)
            if not buzilish and baza.sozlama("xodim_tasdiq", XODIM_TASDIQ_STANDART) != "1":
                buzilish = None
        if buzilish is not None:
            baza.bajar("UPDATE harakat SET holat='ruxsat_kutilmoqda', qoida_buzilish=? WHERE id=?",
                       "; ".join(buzilish) or None, hid)
            b = odamlar.boshliq()
            if b:
                xabarlar.append(xabarnoma(
                    b["id"], "ruxsat",
                    f"Tasdiqlaysizmi?\n{qisqa_tavsif(harakat(hid))}\nYozgan: {kim['ism']}"
                    + (f"\nDiqqat: {'; '.join(buzilish)}" if buzilish else ""),
                    hid, [["✅ Tasdiqlash", f"r:{hid}:1"], ["Rad etish", f"r:{hid}:0"]]))
            baza.jurnal(kim_id, "ruxsat_soraldi", f"harakat:{hid}", None, buzilish)
            return {"holat": "ruxsat_kutilmoqda", "takrorlar": [], "xabarlar": [x for x in xabarlar if x]}
        hisob_sana, kech = _hisob_sana(h["voqea_sana"], h["dan"], h["ga"])
        pul_otadi = SHABLON[h["tur"]][3]
        b_id, o_id = masul(h["dan"]), masul(h["ga"])

        def tomon(m_id):
            if not pul_otadi or m_id is None:
                return "kerak_emas"
            return "tasdiq" if m_id == h["yozgan_id"] or m_id == kim_id else "kutilmoqda"

        b_h, o_h = tomon(b_id), tomon(o_id)
        baza.bajar("UPDATE harakat SET holat='faol', hisob_sana=?, kech=?, beruvchi_id=?, oluvchi_id=?, "
                   "beruvchi_holat=?, oluvchi_holat=?, faollashgan=? WHERE id=?",
                   hisob_sana, kech, b_id, o_id, b_h, o_h, vaqt.iso(), hid)
        baza.jurnal(kim_id, "harakat_faol", f"harakat:{hid}", None,
                    {"tur": h["tur"], "summa": h["summa"], "valyuta": h["valyuta"], "kech": kech})
        h = harakat(hid)
        if b_h == "kutilmoqda":
            xabarlar.append(_tasdiq_sorov(h, "beruvchi"))
        if o_h == "kutilmoqda":
            xabarlar.append(_tasdiq_sorov(h, "oluvchi"))
        # pul otmaydigan, lekin xodimga tegishli yozuv — xabar (bonus, jarima, ishbay)
        if not pul_otadi and h["odam_id"] and h["odam_id"] != kim_id and h["tur"] in ("bonus", "jarima", "ishbay",
                                                                                     "qarzdan_ushlash"):
            xabarlar.append(xabarnoma(h["odam_id"], "malumot", f"{qisqa_tavsif(h)}\nYozdi: {kim['ism']}", hid))
        if h["tur"] == "sotuv":
            vadalar.sotuvdan(h, kim_id)
    return {"holat": "faol", "takrorlar": [], "xabarlar": [x for x in xabarlar if x]}


def _tasdiq_sorov(h: dict, tomon: str) -> dict | None:
    kim = odamlar.odam(h["yozgan_id"])
    yozgan = kim["ism"] if kim else "Tizim"
    nom = SHABLON[h["tur"]][0]
    s = matn.pul(h["summa"], h["valyuta"])
    soz = matn.pul_soz(h["summa"], h["valyuta"])
    sana = vaqt.sana_matn(h["voqea_sana"])
    if tomon == "oluvchi":
        oluvchi_nom = hisob_nomi(h["ga"])
        savol = "Oldingizmi?" if ajrat(h["ga"])[0] != "kassa" else f"{oluvchi_nom}ga tushdimi?"
        matn_ = (f"{nom}\n{yozgan} {s} ({soz}) berilganini yozdi.\nQayerdan: {hisob_nomi(h['dan'])} · {sana}\n{savol}")
        tugma = [["Ha, oldim", f"t:{h['id']}:o:1"], ["Yo'q, olmadim", f"t:{h['id']}:o:0"]]
        return xabarnoma(h["oluvchi_id"], "tasdiq", matn_, h["id"], tugma)
    matn_ = (f"{nom}\n{yozgan} {hisob_nomi(h['dan'])}dan {s} ({soz}) chiqqanini yozdi.\n"
             f"Kimga: {hisob_nomi(h['ga'])} · {sana}\nBerdingizmi?")
    tugma = [["Ha, berdim", f"t:{h['id']}:b:1"], ["Yo'q", f"t:{h['id']}:b:0"]]
    return xabarnoma(h["beruvchi_id"], "tasdiq", matn_, h["id"], tugma)


def tomon_tasdiq(hid: int, kim_id: int, tomon: str, ha: bool) -> list[dict]:
    """Ikkinchi tomon javobi. «Yo'q» — nizo, boshliqqa (K5)."""
    h = harakat(hid)
    if not h or h["holat"] not in ("faol", "nizo"):
        raise HisobXato("Bu yozuv endi faol emas")
    maydon, id_maydon = ("beruvchi_holat", "beruvchi_id") if tomon == "beruvchi" else ("oluvchi_holat", "oluvchi_id")
    if h[id_maydon] != kim_id:
        raise HisobXato("Bu tasdiq sizga tegishli emas")
    if h[maydon] not in ("kutilmoqda",):
        raise HisobXato("Javob allaqachon berilgan")
    xabarlar = []
    with baza.tranz():
        baza.bajar(f"UPDATE harakat SET {maydon}=? WHERE id=?", "tasdiq" if ha else "rad", hid)
        baza.jurnal(kim_id, "tomon_tasdiq" if ha else "tomon_rad", f"harakat:{hid}", tomon, ha)
        if not ha:
            baza.bajar("UPDATE harakat SET holat='nizo' WHERE id=?", hid)
            b = odamlar.boshliq()
            kim = odamlar.odam(kim_id)
            h2 = harakat(hid)
            if b:
                xabarlar.append(xabarnoma(
                    b["id"], "nizo",
                    f"Nizo: {qisqa_tavsif(h2)}\n{kim['ism']} «{'olmadim' if tomon == 'oluvchi' else 'bermadim'}» dedi.",
                    hid, [["Berilgan deb hisoblash", f"n:{hid}:1"], ["Bekor qilish", f"n:{hid}:0"]]))
            if h["yozgan_id"] and h["yozgan_id"] != (b or {}).get("id"):
                xabarlar.append(xabarnoma(h["yozgan_id"], "malumot",
                                          f"{kim['ism']} yozuvingizni tasdiqlamadi: {qisqa_tavsif(h2)}. Boshliq hal qiladi.",
                                          hid))
    return [x for x in xabarlar if x]


def nizo_hal(hid: int, boshliq_id: int, berilgan: bool) -> None:
    h = harakat(hid)
    if not h or h["holat"] != "nizo":
        raise HisobXato("Nizo topilmadi")
    if not odamlar.boshliqmi(odamlar.odam(boshliq_id)):
        raise HisobXato("Nizoni faqat boshliq hal qiladi")
    with baza.tranz():
        if berilgan:
            baza.bajar("UPDATE harakat SET holat='faol', beruvchi_holat=CASE WHEN beruvchi_holat='rad' THEN 'tasdiq' "
                       "ELSE beruvchi_holat END, oluvchi_holat=CASE WHEN oluvchi_holat='rad' THEN 'tasdiq' "
                       "ELSE oluvchi_holat END WHERE id=?", hid)
        baza.jurnal(boshliq_id, "nizo_hal", f"harakat:{hid}", None, "berilgan" if berilgan else "bekor")
        if not berilgan:
            bekor_qil(hid, boshliq_id, "nizo: boshliq bekor qildi", tekshir=False)


def ruxsat(hid: int, boshliq_id: int, ha: bool) -> dict:
    h = harakat(hid)
    if not h or h["holat"] != "ruxsat_kutilmoqda":
        raise HisobXato("Ruxsat kutilayotgan yozuv topilmadi")
    if not odamlar.boshliqmi(odamlar.odam(boshliq_id)):
        raise HisobXato("Ruxsatni faqat boshliq beradi")
    boglangan = [r["id"] for r in baza.hammasi("SELECT id FROM harakat WHERE bog_id=? AND id!=? AND holat='taklif'",
                                                hid, hid)]  # sotuvning hozir to'langan qismi
    if not ha:
        with baza.tranz():
            baza.bajar("UPDATE harakat SET holat='bekor', bekor_sabab='boshliq rad etdi' WHERE id=?", hid)
            for b_id in boglangan:
                baza.bajar("UPDATE harakat SET holat='bekor', bekor_sabab='boshliq rad etdi' WHERE id=?", b_id)
            baza.jurnal(boshliq_id, "ruxsat_rad", f"harakat:{hid}")
            x = xabarnoma(h["yozgan_id"], "malumot", f"Boshliq rad etdi: {qisqa_tavsif(h)}", hid)
        return {"holat": "bekor", "xabarlar": [x] if x else []}
    baza.jurnal(boshliq_id, "ruxsat_berildi", f"harakat:{hid}")
    baza.bajar("UPDATE harakat SET holat='taklif' WHERE id=?", hid)
    natija = faollashtir(hid, h["yozgan_id"], qoida_tekshir=False)
    for b_id in boglangan:
        natija["xabarlar"] += faollashtir(b_id, h["yozgan_id"], qoida_tekshir=False)["xabarlar"]
    x = xabarnoma(h["yozgan_id"], "malumot", f"Boshliq ruxsat berdi: {qisqa_tavsif(harakat(hid))}", hid)
    if x:
        natija["xabarlar"].append(x)
    return natija


# ---------- bekor qilish va tuzatish (A4) ----------

def _yopiq_davrda(h: dict) -> bool:
    for kal in (h["dan"], h["ga"]):
        t, i = ajrat(kal)
        if t == "kassa":
            s = _oxirgi_sanoq(i)
            if s and h["hisob_sana"] <= s and h["hisob_sana"] < vaqt.bugun().isoformat():
                return True
        if t in ("maosh", "xqarz") and oy_yopiqmi(vaqt.oy(h["hisob_sana"])):
            return True
    return False


def ozgartirishi_mumkin(h: dict, o: dict) -> bool:
    if not o or o["holat"] != "faol":
        return False
    if o["rol"] in ("boshliq", "kassir"):
        return True
    if h["yozgan_id"] == o["id"]:
        yozilgan = datetime.fromisoformat(h["yozilgan"])
        return vaqt.hozir() - yozilgan < timedelta(hours=24)
    return False


def bekor_qil(hid: int, kim_id: int, sabab: str, tekshir: bool = True) -> int | None:
    """Faol yozuv: yopiq davrda bo'lsa — bugungi sana bilan teskari yozuv; aks holda bekor. Qaytaradi: teskari id."""
    h = harakat(hid)
    if not h or h["holat"] == "bekor":
        raise HisobXato("Yozuv topilmadi yoki allaqachon bekor")
    if tekshir and not ozgartirishi_mumkin(h, odamlar.odam(kim_id)):
        raise HisobXato("Bu yozuvni o'zgartirish huquqingiz yo'q (24 soatdan keyin — boshliq yoki kassir)")
    if not (sabab or "").strip():
        raise HisobXato("Sabab yozilsin")
    with baza.tranz():
        if h["holat"] in ("faol", "nizo") and _yopiq_davrda(h):
            bugun = vaqt.bugun().isoformat()
            tid = baza.bajar(
                "INSERT INTO harakat(tur,dan,ga,summa,valyuta,summa2,valyuta2,kurs,odam_id,mijoz_id,xarajat_turi_id,"
                "izoh,voqea_sana,hisob_sana,kech,yozilgan,yozgan_id,holat,beruvchi_holat,oluvchi_holat,beruvchi_id,"
                "oluvchi_id,asos_id,manba,faollashgan) VALUES('tuzatish',?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,'faol',?,?,?,?,?,"
                "'tizim',?)",
                h["ga"], h["dan"], h["summa2"] or h["summa"], h["valyuta2"] or h["valyuta"],
                h["summa"] if h["summa2"] else None, h["valyuta"] if h["summa2"] else None, h["kurs"],
                h["odam_id"], h["mijoz_id"], h["xarajat_turi_id"], f"#{hid} bekor qilindi: {sabab}",
                bugun, bugun, vaqt.iso(), kim_id, h["oluvchi_holat"], h["beruvchi_holat"], h["oluvchi_id"],
                h["beruvchi_id"], hid, vaqt.iso())
            baza.bajar("UPDATE harakat SET bekor_sabab=? WHERE id=?", f"teskari yozuv #{tid}: {sabab}", hid)
            baza.jurnal(kim_id, "teskari_yozuv", f"harakat:{hid}", None, {"teskari": tid, "sabab": sabab})
            vadalar.harakat_bekor(hid, kim_id)
            return tid
        baza.bajar("UPDATE harakat SET holat='bekor', bekor_sabab=? WHERE id=?", sabab, hid)
        baza.jurnal(kim_id, "harakat_bekor", f"harakat:{hid}", h["holat"], sabab)
        vadalar.harakat_bekor(hid, kim_id)
        bog = baza.hammasi("SELECT id FROM harakat WHERE bog_id=? AND id!=? AND holat!='bekor'", hid, hid)
        for b in bog:
            bekor_qil(b["id"], kim_id, f"bog'liq #{hid}: {sabab}", tekshir=False)
    return None


def tuzat(hid: int, kim_id: int, ozgarish: dict, sabab: str) -> int:
    """Eski yozuv bekor (yoki teskari), o'rniga yangi taklif — tomonlar qayta tasdiqlaydi (A4)."""
    h = harakat(hid)
    if not h or h["holat"] not in ("faol", "nizo", "ruxsat_kutilmoqda"):
        raise HisobXato("Faqat faol yozuv tuzatiladi")
    if h["bog_id"]:
        raise HisobXato("Sotuv va uning to'lovi bog'langan: sotuvni bekor qilib, qaytadan kiriting")
    p = {"summa": h["summa"], "valyuta": h["valyuta"], "odam_id": h["odam_id"], "mijoz_id": h["mijoz_id"],
         "xarajat_turi_id": h["xarajat_turi_id"], "sotuvchi_id": h["sotuvchi_id"], "izoh": h["izoh"],
         "sana": h["voqea_sana"], "muddat": h["muddat"], "iqtibos": h["iqtibos"]}
    t, i = ajrat(h["dan"])
    if t == "kassa":
        p["kassa_id"] = i
    if t == "qol":
        p["qoldan"] = True
    t2, i2 = ajrat(h["ga"])
    if t2 == "kassa":
        p["kassa_id" if t != "kassa" else "kassa2_id"] = i2
    p.update({k: v for k, v in ozgarish.items() if v is not None})
    with baza.tranz():
        bekor_qil(hid, kim_id, f"tuzatildi: {sabab}")
        yangi = taklif(h["tur"], p, kim_id, h["xabar_id"], manba="tuzatish")
        baza.bajar("UPDATE harakat SET asos_id=? WHERE id=?", hid, yangi)
    return yangi


# ---------- sotuv (P9) ----------

def sotuv_tuz(p: dict, yozgan_id: int, xabar_id: int | None = None) -> tuple[int, int | None]:
    """Sotuv + hozir to'langan qismi (kirim) — bog'langan ikki taklif. Qolgani avtomatik nasiya."""
    with baza.tranz():
        sid = taklif("sotuv", {**p, "sotuvchi_id": p.get("sotuvchi_id") or yozgan_id}, yozgan_id, xabar_id)
        kid = None
        tolandi = int(p.get("tolandi") or 0)
        if tolandi > 0:
            if tolandi > int(p["summa"]):
                raise HisobXato("To'langan summa sotuvdan katta")
            kid = taklif("kirim", {**p, "summa": tolandi, "muddat": None}, yozgan_id, xabar_id)
            baza.bajar("UPDATE harakat SET bog_id=? WHERE id IN (?,?)", sid, sid, kid)
    return sid, kid


# ---------- kassa sanog'i (P4) ----------

def kassa_sanoq(kassa_id: int, sanalgan: int, kim_id: int, izoh: str | None = None) -> dict:
    k = kassa(kassa_id)
    if not k:
        raise HisobXato("Kassa topilmadi")
    o = odamlar.odam(kim_id)
    if not (odamlar.boshliqmi(o) or k["masul_id"] == kim_id or (o and o["rol"] == "kassir")):
        raise HisobXato("Bu kassani sanash huquqingiz yo'q")
    kal = f"kassa:{kassa_id}"
    kutilgan = qoldiq_bir(kal, k["valyuta"])
    kut = kutilayotgan(kal)
    farq = int(sanalgan) - kutilgan
    agar = kutilgan - kut["chiqim_jami"] + kut["kirim_jami"]
    bugun = vaqt.bugun().isoformat()
    with baza.tranz():
        baza.bajar("INSERT INTO kassa_sanoq(kassa_id,sana,sanalgan,kutilgan,farq,izoh,kim_id,vaqt) "
                   "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(kassa_id,sana) DO UPDATE SET sanalgan=excluded.sanalgan, "
                   "kutilgan=excluded.kutilgan, farq=excluded.farq, izoh=excluded.izoh, kim_id=excluded.kim_id, "
                   "vaqt=excluded.vaqt", kassa_id, bugun, int(sanalgan), kutilgan, farq, izoh, kim_id, vaqt.iso())
        baza.jurnal(kim_id, "kassa_sanoq", f"kassa:{kassa_id}", None,
                    {"sanalgan": sanalgan, "kutilgan": kutilgan, "farq": farq})
        xabarlar = []
        if farq and int(sanalgan) != agar:
            b = odamlar.boshliq()
            if b and b["id"] != kim_id:
                xabarlar.append(xabarnoma(
                    b["id"], "kassa_farq",
                    f"Kassa farqi: {k['nom']}\nSanaldi {matn.pul(int(sanalgan), k['valyuta'])}, "
                    f"kutilgan {matn.pul(kutilgan, k['valyuta'])}\nFarq: {matn.pul(farq, k['valyuta'])}"
                    + (f"\nIzoh: {izoh}" if izoh else "\nIzoh hali yozilmagan"), None))
    return {"kassa": k, "sanalgan": int(sanalgan), "kutilgan": kutilgan, "farq": farq, "kutilayotgan": kut,
            "agar_tasdiqlansa": agar, "xabarlar": [x for x in xabarlar if x]}


# ---------- hisobotlar (P5, P7) ----------

def mijoz_qarzlari(tur: str = "mijoz") -> list[dict]:
    natija = []
    for m in baza.hammasi("SELECT * FROM mijoz WHERE tur=? AND birlashdi IS NULL ORDER BY ism", tur):
        q = qoldiq(f"{tur}:{m['id']}")
        q = {v: (s if tur == "mijoz" else -s) for v, s in q.items()}
        q = {v: s for v, s in q.items() if s > 0}
        if q:
            muddat = None
            if tur == "mijoz":  # ochiq yoki bajarilmagan to'lov va'dasining eng yaqin muddati
                ochiq = [v["muddat"] for v in vadalar.royxat(m["id"]) if v["kim"] == "mijoz" and v["tur"] == "tolov"
                         and v["holat"] == "ochiq" and v["holat_h"] in ("ochiq", "qisman", "buzildi")]
                muddat = min(ochiq) if ochiq else None
            if not muddat:  # va'dasiz eski nasiya: sotuv (mijoz) yoki nasiyaga olish (ta'minotchi) muddati
                ustun = "ga" if tur == "mijoz" else "dan"
                muddat = baza.qiymat(f"SELECT MIN(muddat) FROM harakat WHERE {ustun}=? AND holat='faol' AND muddat IS NOT "
                                     "NULL AND id NOT IN (SELECT harakat_id FROM vada WHERE harakat_id IS NOT NULL)",
                                     f"{tur}:{m['id']}")
            natija.append({**m, "qarz": q, "muddat": muddat})
    return natija


def davr_jami(dan: str, gacha: str) -> dict:
    """So'mda: sotuv, xarajat (turlari bilan), kassaga kirim/chiqim."""
    def som(r):
        return kurs.somga(r["summa"], r["valyuta"], r["hisob_sana"]) or 0

    qatorlar = baza.hammasi("SELECT * FROM harakat WHERE holat IN ('faol','nizo') AND hisob_sana BETWEEN ? AND ?",
                            dan, gacha)
    sotuv = sum(som(r) for r in qatorlar if r["dan"] == "sotuv")
    xarajat_turlar: dict[str, int] = {}
    for r in qatorlar:
        if r["ga"].startswith("xarajat:"):
            nom = hisob_nomi(r["ga"]).replace("Xarajat: ", "")
            xarajat_turlar[nom] = xarajat_turlar.get(nom, 0) + som(r)
        elif r["dan"].startswith("xarajat:"):
            nom = hisob_nomi(r["dan"]).replace("Xarajat: ", "")
            xarajat_turlar[nom] = xarajat_turlar.get(nom, 0) - som(r)
    # boshlang'ich qoldiq va egasining o'z puli — daromad ham, xarajat ham emas (P2)
    tashqi = ("kassa:", "boshlangich", "egasi")
    kassa_kirim = sum(som(r) for r in qatorlar if r["ga"].startswith("kassa:") and not r["dan"].startswith(tashqi)
                      and r["oluvchi_holat"] in ("kerak_emas", "tasdiq"))
    kassa_chiqim = sum(som(r) for r in qatorlar if r["dan"].startswith("kassa:") and not r["ga"].startswith(tashqi)
                       and r["beruvchi_holat"] in ("kerak_emas", "tasdiq"))
    ishhaqi = sum(som(r) for r in qatorlar if r["ga"] == "ishhaqi") - sum(som(r) for r in qatorlar if r["dan"] == "ishhaqi")
    return {"sotuv": sotuv, "xarajat": sum(xarajat_turlar.values()), "xarajat_turlar": xarajat_turlar,
            "kassa_kirim": kassa_kirim, "kassa_chiqim": kassa_chiqim, "ishhaqi_yozilgan": ishhaqi}


def qisqa_tavsif(h: dict) -> str:
    nom = SHABLON.get(h["tur"], (h["tur"],))[0]
    if h.get("xarajat_turi_id"):  # «Xarajat: Benzin» — turi ko'rinmasa, savolga javob topilmasdi
        x = baza.bir("SELECT nom FROM xarajat_turi WHERE id=?", h["xarajat_turi_id"])
        if x:
            nom += f": {x['nom']}"
    qism = [nom]
    if h.get("odam_id"):
        o = odamlar.odam(h["odam_id"])
        if o:
            qism.append(o["ism"])
    if h.get("mijoz_id"):
        m = baza.bir("SELECT ism FROM mijoz WHERE id=?", h["mijoz_id"])
        if m:
            qism.append(m["ism"])
    qism.append(matn.pul(h["summa"], h["valyuta"]))
    return " · ".join(qism)


def harakatlar(korish: dict | None = None, **f) -> list[dict]:
    """Ro'yxat (panel va savol-javob uchun). `korish` — so'ragan odam: huquq filtri (S3)."""
    shart, p = ["1=1"], []
    if f.get("holat"):
        shart.append("holat=?")
        p.append(f["holat"])
    else:
        shart.append("holat!='taklif'")
    if f.get("tur"):
        shart.append("tur=?")
        p.append(f["tur"])
    if f.get("hisob"):
        shart.append("(dan=? OR ga=?)")
        p += [f["hisob"], f["hisob"]]
    if f.get("odam_id"):
        shart.append("odam_id=?")
        p.append(f["odam_id"])
    if f.get("mijoz_id"):
        shart.append("mijoz_id=?")
        p.append(f["mijoz_id"])
    if f.get("dan"):
        shart.append("hisob_sana>=?")
        p.append(f["dan"])
    if f.get("gacha"):
        shart.append("hisob_sana<=?")
        p.append(f["gacha"])
    if f.get("oldin_id"):  # sahifalash: «yana ko'rsatish» — shu yozuvdan eskilari
        shart.append("id<?")
        p.append(int(f["oldin_id"]))
    limit = int(f.get("limit") or 200)
    q = (f.get("q") or "").strip()
    olish = 3000 if q else limit * 3  # matn qidiruvi Python'da (kirill/lotin, qo'shimchalar) — ko'proq olinadi
    qatorlar = baza.hammasi("SELECT * FROM harakat WHERE %s ORDER BY id DESC LIMIT %d" % (" AND ".join(shart), olish), *p)
    if korish is not None and not odamlar.boshliqmi(korish):
        qatorlar = [r for r in qatorlar if r["yozgan_id"] == korish["id"]
                    or odamlar.hisob_korishi_mumkin(korish, r["dan"]) or odamlar.hisob_korishi_mumkin(korish, r["ga"])]
    if q:
        from . import qidiruv
        ildlar = qidiruv.ildizlar(q) or [qidiruv.ildiz(t) for t in qidiruv.tokenlar(q)]
        raqam = "".join(ch for ch in q if ch.isdigit())
        son = int(raqam) if raqam and len(raqam) == len(q.replace(" ", "").lstrip("#")) else None  # faqat raqam yozilgan

        def mos(r):
            if son is not None and (r["id"] == son or r["summa"] == son or r["summa"] == son * 100):
                return True
            toklar = qidiruv.tokenlar(f"{qisqa_tavsif(r)} {r['izoh'] or ''} {r['iqtibos'] or ''}")
            return bool(ildlar) and all(any(qidiruv.mos(t, i) for t in toklar) for i in ildlar)
        qatorlar = [r for r in qatorlar if mos(r)]
    return qatorlar[:limit]
