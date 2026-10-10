"""Va'dalar daftari (C3, C4, P8).

To'lov va'dasining holati saqlanmaydi — har safar to'lovlardan hisoblanadi (C-c): to'lovlar muddat tartibida
(avval muddati yaqin va'daga) taqsimlanadi, va'dadan oldingi to'lov hisobga olinmaydi, bir to'lov ikki marta
yozilmaydi (C-b). Boshqa va'da (hujjat, mol olib kelish) — muddatida mas'ul o'zi yopadi.
"""
from datetime import date, timedelta

from . import baza, kurs, matn, odamlar, vaqt


class VadaXato(Exception):
    pass


HOLAT_NOMI = {"vaqtida": "Vaqtida bajarildi", "kech": "Kech bajarildi", "qisman": "Qisman", "buzildi": "Buzildi",
              "ochiq": "Kutilmoqda", "bekor": "Bekor qilingan", "bajarilmadi": "Bajarilmadi"}


def _ogir(summa: int, dan: str, ga: str, sana: str) -> int:
    if dan == ga:
        return summa
    o = kurs.ogir(summa, dan, ga, sana)
    return o[0] if o else 0


def vada(vid: int) -> dict | None:
    return baza.bir("SELECT * FROM vada WHERE id=?", vid)


def yoz(mijoz_id: int, muddat: str, yozgan_id: int, kim: str = "mijoz", tur: str = "tolov", summa: int | None = None,
        valyuta: str = "UZS", matn_: str | None = None, xabar_id: int | None = None, iqtibos: str | None = None,
        masul_id: int | None = None, harakat_id: int | None = None) -> int:
    if not baza.bir("SELECT 1 FROM mijoz WHERE id=?", mijoz_id):
        raise VadaXato("Mijoz topilmadi")
    if kim not in ("mijoz", "biz") or tur not in ("tolov", "boshqa"):
        raise VadaXato("Va'da turi noto'g'ri")
    if tur == "tolov" and (not summa or int(summa) <= 0):
        raise VadaXato("To'lov va'dasida summa bo'lsin")
    if tur == "boshqa" and not (matn_ or "").strip():
        raise VadaXato("Nima va'da qilingani yozilsin")
    if valyuta not in ("UZS", "USD"):
        raise VadaXato("Valyuta noto'g'ri")
    date.fromisoformat(muddat[:10])
    if not masul_id:
        m = baza.bir("SELECT masul_id FROM mijoz WHERE id=?", mijoz_id)
        masul_id = (m or {}).get("masul_id") or yozgan_id
    with baza.tranz():
        hozir = vaqt.iso()
        if tur == "tolov" and kim == "mijoz":
            for v in almashadiganlar(mijoz_id):
                baza.bajar("UPDATE vada SET holat='bajarilmadi', yopilgan=?, yopgan_id=?, izoh=? WHERE id=?", hozir,
                           yozgan_id, "Yangi va'da berildi", v["id"])
        vid = baza.bajar("INSERT INTO vada(mijoz_id,kim,tur,summa,valyuta,matn,muddat,yozilgan,yozgan_id,masul_id,xabar_id,"
                         "iqtibos,harakat_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", mijoz_id, kim, tur,
                         int(summa) if summa else None, valyuta, (matn_ or "").strip() or None, muddat[:10], hozir,
                         yozgan_id, masul_id, xabar_id, iqtibos, harakat_id)
        baza.jurnal(yozgan_id, "vada_yozildi", f"vada:{vid}", None,
                    {"mijoz": mijoz_id, "tur": tur, "summa": summa, "muddat": muddat})
    return vid


def sotuvdan(h: dict, kim_id: int) -> int | None:
    """Nasiyali sotuvda qarzni to'lash muddati aytilgan bo'lsa — bu ham to'lov va'dasi (C3)."""
    if h["tur"] != "sotuv" or not h["muddat"] or not h["mijoz_id"]:
        return None
    if baza.bir("SELECT 1 FROM vada WHERE harakat_id=? AND holat!='bekor'", h["id"]):
        return None
    tolandi = baza.qiymat("SELECT COALESCE(SUM(summa),0) FROM harakat WHERE bog_id=? AND id!=? AND tur='kirim' "
                          "AND holat!='bekor'", h["id"], h["id"]) or 0
    nasiya = h["summa"] - tolandi
    if nasiya <= 0:
        return None
    try:  # va'da yozilmasa ham pul yozuvi to'xtamasin
        return yoz(h["mijoz_id"], h["muddat"], kim_id, summa=nasiya, valyuta=h["valyuta"], xabar_id=h["xabar_id"],
                   iqtibos=h["iqtibos"], harakat_id=h["id"],
                   masul_id=baza.qiymat("SELECT masul_id FROM mijoz WHERE id=?", h["mijoz_id"]) or h["sotuvchi_id"])
    except (VadaXato, ValueError):
        return None


def harakat_bekor(hid: int, kim_id: int) -> None:
    for v in baza.hammasi("SELECT id FROM vada WHERE harakat_id=? AND holat!='bekor'", hid):
        bekor(v["id"], kim_id, f"sotuv #{hid} bekor qilindi")


def almashadiganlar(mijoz_id: int) -> list[dict]:
    """C-b2: muddati o'tgan, to'liq to'lanmagan va'dalar — yangi to'lov va'dasi bilan yopiladi."""
    h = holatlar(mijoz_id)
    return [v for v in baza.hammasi("SELECT * FROM vada WHERE mijoz_id=? AND tur='tolov' AND kim='mijoz' AND holat='ochiq'",
                                    mijoz_id) if h.get(v["id"], {}).get("holat") in ("qisman", "buzildi")]


def bekor(vid: int, kim_id: int, sabab: str) -> None:
    v = vada(vid)
    if not v or v["holat"] == "bekor":
        raise VadaXato("Va'da topilmadi")
    if not (sabab or "").strip():
        raise VadaXato("Sabab yozilsin")
    with baza.tranz():
        baza.bajar("UPDATE vada SET holat='bekor', izoh=?, yopilgan=?, yopgan_id=? WHERE id=?", sabab[:300], vaqt.iso(),
                   kim_id, vid)
        baza.jurnal(kim_id, "vada_bekor", f"vada:{vid}", None, sabab)


def boshqa_yop(vid: int, kim_id: int, bajarildi: bool) -> None:
    v = vada(vid)
    if not v or v["tur"] != "boshqa" or v["holat"] != "ochiq":
        raise VadaXato("Ochiq «boshqa» va'da topilmadi")
    with baza.tranz():
        baza.bajar("UPDATE vada SET holat=?, yopilgan=?, yopgan_id=? WHERE id=?",
                   "bajarildi" if bajarildi else "bajarilmadi", vaqt.iso(), kim_id, vid)
        baza.jurnal(kim_id, "vada_yopildi", f"vada:{vid}", None, bajarildi)


# ---------- to'lov va'dalarining holati (C-b, C-c) ----------

def _tolovlar(mijoz_id: int) -> list[dict]:
    """Mijozdan kelgan pullar (kassaga yoki xodim qo'liga) — vaqt tartibida. Sotuvning o'zida to'langan qismi
    kirmaydi: u yangi mol uchun, eski qarz va'dasi uchun emas."""
    return baza.hammasi(
        "SELECT id, summa, valyuta, voqea_sana, yozilgan, xabar_id FROM harakat WHERE dan=? AND holat IN ('faol','nizo') "
        "AND beruvchi_holat IN ('kerak_emas','tasdiq') AND tur IN ('kirim','mijozdan_qolga') AND bog_id IS NULL "
        "ORDER BY voqea_sana, id", f"mijoz:{mijoz_id}")


def _tegishli(t: dict, v: dict) -> bool:
    """To'lov shu va'daga yoziladimi: va'dadan keyin bo'lgan, bir xabardan emas, va'da yopilishidan oldin (C-b, C-b2)."""
    v_sana = v["yozilgan"][:10]
    if t["voqea_sana"] < v_sana or (t["voqea_sana"] == v_sana and t["yozilgan"] <= v["yozilgan"]):
        return False
    if t["xabar_id"] and t["xabar_id"] == v["xabar_id"]:
        return False  # «1 mln berdi, qolganini jumada beradi» — bu to'lov shu va'da uchun emas
    if v["holat"] == "bajarilmadi" and v["yopilgan"]:
        y_sana = v["yopilgan"][:10]
        if t["voqea_sana"] > y_sana or (t["voqea_sana"] == y_sana and t["yozilgan"] >= v["yopilgan"]):
            return False
    return True


def holatlar(mijoz_id: int) -> dict[int, dict]:
    """Har bir to'lov va'dasi: {qoplandi, muddatgacha, holat, qolgan}."""
    vadalar = baza.hammasi("SELECT * FROM vada WHERE mijoz_id=? AND tur='tolov' AND kim='mijoz' AND holat!='bekor' "
                           "ORDER BY muddat, id", mijoz_id)
    natija = {v["id"]: {"qoplandi": 0, "muddatgacha": 0} for v in vadalar}
    if not vadalar:
        return natija
    bugun = vaqt.bugun().isoformat()
    for t in _tolovlar(mijoz_id):
        qoldiq_ = t["summa"]
        t_sana = t["voqea_sana"]
        for v in vadalar:
            if qoldiq_ <= 0:
                break
            n = natija[v["id"]]
            kerak = v["summa"] - n["qoplandi"]
            if kerak <= 0 or not _tegishli(t, v):
                continue
            olindi = min(_ogir(qoldiq_, t["valyuta"], v["valyuta"], t_sana), kerak)
            if olindi <= 0:
                continue
            n["qoplandi"] += olindi
            if t_sana <= v["muddat"]:
                n["muddatgacha"] += olindi
            qoldiq_ -= olindi if v["valyuta"] == t["valyuta"] else _ogir(olindi, v["valyuta"], t["valyuta"], t_sana)
    for v in vadalar:
        n = natija[v["id"]]
        n["qolgan"] = max(0, v["summa"] - n["qoplandi"])
        if n["muddatgacha"] >= v["summa"]:
            n["holat"] = "vaqtida"
        elif v["muddat"] >= bugun and v["holat"] == "ochiq":
            n["holat"] = "ochiq"
        elif n["qoplandi"] >= v["summa"]:
            n["holat"] = "kech"
        elif n["muddatgacha"] > 0:
            n["holat"] = "qisman"
        else:
            n["holat"] = "buzildi"
    return natija


def holati(v: dict) -> str:
    if v["holat"] == "bekor":
        return "bekor"
    if v["tur"] == "boshqa" or v["kim"] == "biz":
        if v["holat"] == "bajarildi":
            return "vaqtida" if (v["yopilgan"] or "")[:10] <= v["muddat"] else "kech"
        if v["holat"] == "bajarilmadi":
            return "buzildi"
        return "ochiq" if v["muddat"] >= vaqt.bugun().isoformat() else "buzildi"
    return holatlar(v["mijoz_id"]).get(v["id"], {}).get("holat", "ochiq")


def royxat(mijoz_id: int | None = None, faqat_ochiq: bool = False, dan: str | None = None,
           gacha: str | None = None, masul_id: int | None = None) -> list[dict]:
    shart, p = ["1=1"], []
    if mijoz_id:
        shart.append("v.mijoz_id=?")
        p.append(mijoz_id)
    if dan:
        shart.append("v.muddat>=?")
        p.append(dan)
    if gacha:
        shart.append("v.muddat<=?")
        p.append(gacha)
    if masul_id:
        shart.append("v.masul_id=?")
        p.append(masul_id)
    qatorlar = baza.hammasi("SELECT v.*, m.ism mijoz FROM vada v JOIN mijoz m ON m.id=v.mijoz_id WHERE %s "
                            "ORDER BY v.muddat DESC, v.id DESC LIMIT 500" % " AND ".join(shart), *p)
    kesh: dict[int, dict] = {}
    natija = []
    for v in qatorlar:
        if v["tur"] == "tolov" and v["kim"] == "mijoz" and v["holat"] != "bekor":
            if v["mijoz_id"] not in kesh:
                kesh[v["mijoz_id"]] = holatlar(v["mijoz_id"])
            h = kesh[v["mijoz_id"]].get(v["id"], {})
            v.update(holat_h=h.get("holat", "ochiq"), qoplandi=h.get("qoplandi", 0), qolgan=h.get("qolgan", v["summa"]))
        else:
            v.update(holat_h=holati(v), qoplandi=None, qolgan=None)
        if faqat_ochiq and v["holat_h"] != "ochiq":
            continue
        natija.append(v)
    return natija


def ishonch(mijoz_id: int, n: int = 5) -> dict:
    """«Oldingi 5 va'dadan 4 tasi vaqtida» (C4) — faqat yakunlangan va'dalar, eng oxirgilari."""
    yakun = [v for v in royxat(mijoz_id) if v["kim"] == "mijoz" and v["holat_h"] in ("vaqtida", "kech", "qisman", "buzildi")]
    yakun.sort(key=lambda v: (v["muddat"], v["id"]), reverse=True)
    oxirgi = yakun[:n]
    vaqtida = sum(1 for v in oxirgi if v["holat_h"] == "vaqtida")
    return {"jami": len(oxirgi), "vaqtida": vaqtida,
            "matn": f"oldingi {len(oxirgi)} ta va'dadan {vaqtida} tasi vaqtida" if oxirgi else "va'da tarixi yo'q"}


def kutilayotgan_tushum(kun: int = 30) -> dict:
    """P8: ochiq to'lov va'dalarining qolgan qismi (so'mda), muddati bo'yicha."""
    bugun = vaqt.bugun()
    gacha = (bugun + timedelta(days=kun)).isoformat()
    jami, bugungi, royxat_ = 0, 0, []
    for v in royxat(faqat_ochiq=True, gacha=gacha):
        if v["tur"] != "tolov" or v["kim"] != "mijoz":
            continue
        som = kurs.somga(v["qolgan"] or 0, v["valyuta"]) or 0
        jami += som
        if v["muddat"] == bugun.isoformat():
            bugungi += som
        royxat_.append(v)
    return {"jami": jami, "bugun": bugungi, "vadalar": royxat_}


def tahrirla(vid: int, kim_id: int, summa: int | None = -1, muddat: str | None = None, matn_: str | None = None) -> dict:
    """CRM2: va'dani paneldan tahrirlash (summa, muddat, izoh). Holat har safar qayta hisoblanadi — saqlanmaydi."""
    v = baza.bir("SELECT * FROM vada WHERE id=?", vid)
    if not v or v["holat"] != "ochiq":
        raise VadaXato("Faqat ochiq va'da tahrirlanadi")
    yangi = {"summa": v["summa"] if summa == -1 else summa, "muddat": (muddat or v["muddat"])[:10],
             "matn": v["matn"] if matn_ is None else (matn_.strip()[:300] or None)}
    date.fromisoformat(yangi["muddat"])
    if v["tur"] == "tolov" and v["kim"] == "mijoz" and not yangi["summa"]:
        raise VadaXato("To'lov va'dasida summa bo'lsin")
    baza.bajar("UPDATE vada SET summa=?, muddat=?, matn=? WHERE id=?", yangi["summa"], yangi["muddat"], yangi["matn"], vid)
    baza.jurnal(kim_id, "vada_tahrir", f"vada:{vid}", {k: v[k] for k in yangi}, yangi)
    return baza.bir("SELECT * FROM vada WHERE id=?", vid)
