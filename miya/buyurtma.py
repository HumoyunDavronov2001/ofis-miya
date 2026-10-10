"""CRM6: katalog (mahsulot/xizmat) va buyurtmalar — yangi → taklif → sotildi → bajarildi (yoki bekor).

Jami, bosqich o'tishlari va «sotildi»da hisobga sotuv yozishni dastur boshqaradi (raqamni hech kim qo'lda hisoblamaydi).
Summalar minor birlikda (so'm yoki sent), miqdor — kasr bo'lishi mumkin (2,5 metr).
"""
from . import baza, hisob, ishlar, matn, odamlar, qidiruv, vaqt

BOSQICHLAR = ("yangi", "taklif", "sotildi", "bajarildi", "bekor")
NOMI = {"yangi": "Yangi", "taklif": "Taklif berildi", "sotildi": "Sotildi", "bajarildi": "Bajarildi", "bekor": "Bekor"}
OCHIQ = ("yangi", "taklif")  # qatorlar faqat shu bosqichlarda o'zgaradi


class BuyurtmaXato(Exception):
    pass


# ---------- katalog ----------

def katalog(faqat_faol: bool = True, sorov: str = "") -> list[dict]:
    qator = baza.hammasi("SELECT * FROM katalog" + (" WHERE faol=1" if faqat_faol else "") + " ORDER BY faol DESC, nom")
    if sorov:
        s = matn.norm(sorov)
        qator = [k for k in qator if s in matn.norm(f"{k['nom']} {k['izoh'] or ''}")]
    return qator


def katalog_saqla(kid: int | None, kim_id: int, nom: str, tur: str = "mahsulot", birlik: str = "dona", narx: int = 0,
                  valyuta: str = "UZS", tannarx: int | None = None, izoh: str | None = None, faol: bool = True) -> int:
    nom = (nom or "").strip()[:200]
    if not nom:
        raise BuyurtmaXato("Nomi yozilsin")
    if tur not in ("mahsulot", "xizmat") or valyuta not in ("UZS", "USD"):
        raise BuyurtmaXato("Turi yoki valyutasi noto'g'ri")
    if narx < 0 or (tannarx is not None and tannarx < 0):
        raise BuyurtmaXato("Narx manfiy bo'lmaydi")
    qiymat = (nom, tur, (birlik or "dona").strip()[:20], int(narx), valyuta, tannarx, (izoh or "").strip()[:300] or None,
              1 if faol else 0)
    if kid:
        eski = baza.bir("SELECT * FROM katalog WHERE id=?", kid)
        if not eski:
            raise BuyurtmaXato("Topilmadi")
        baza.bajar("UPDATE katalog SET nom=?, tur=?, birlik=?, narx=?, valyuta=?, tannarx=?, izoh=?, faol=? WHERE id=?",
                   *qiymat, kid)
        baza.jurnal(kim_id, "katalog_tahrir", f"katalog:{kid}", {"narx": eski["narx"], "faol": eski["faol"]},
                    {"narx": narx, "faol": faol})
        return kid
    kid = baza.bajar("INSERT INTO katalog(nom,tur,birlik,narx,valyuta,tannarx,izoh,faol,yaratilgan) VALUES(?,?,?,?,?,?,?,?,?)",
                     *qiymat, vaqt.iso())
    baza.jurnal(kim_id, "katalog_qosh", f"katalog:{kid}", None, nom)
    return kid


def katalog_top(nom: str) -> tuple[dict | None, list[dict]]:
    """CRM7: gapdagi nom → katalog qatori (AI emas, dastur topadi). (aniq mos | None, nomzodlar)."""
    faol = katalog()
    n = matn.norm(nom)
    if not n or not faol:
        return None, []
    aynan = [k for k in faol if matn.norm(k["nom"]) == n]
    if len(aynan) == 1:
        return aynan[0], []
    ild = qidiruv.ildizlar(nom)
    hammasi = [k for k in faol if ild and all(any(qidiruv.mos(t, i) for t in qidiruv.tokenlar(k["nom"])) for i in ild)]
    if len(hammasi) == 1:
        return hammasi[0], []
    mos = matn.mosla(nom, [(k["id"], k["nom"]) for k in faol], 0.6)
    bitta = matn.yagona(mos)
    if bitta and not hammasi:
        return next(k for k in faol if k["id"] == bitta[0]), []
    return None, (hammasi or [next(k for k in faol if k["id"] == m_[0]) for m_ in mos])[:5]


def xodimdan_xabar(bid: int, o: dict) -> None:
    """Xodim chatdan buyurtma ochsa — boshliqqa xabar (R7: Telegram va web chatga bir xil navbatdan)."""
    boss = odamlar.boshliq()
    if not boss or boss["id"] == o["id"]:
        return
    b = bir(bid)
    qator = ", ".join(f"{q['nom']} × {q['miqdor']:g}" for q in b["qatorlar"][:4]) + (" …" if len(b["qatorlar"]) > 4 else "")
    hisob.xabarnoma(boss["id"], "malumot", f"Yangi buyurtma #{bid} ({o['ism']}): {b['mijoz']} — {qator}. "
                                           f"Jami {matn.pul(b['jami'], b['valyuta'])}")


# ---------- buyurtma ----------

def jami(b: dict, qatorlar: list[dict]) -> int:
    return max(0, sum(round(q["miqdor"] * q["narx"]) for q in qatorlar) - (b["chegirma"] or 0))


def _tarix(bid: int, kim_id: int | None, matn_: str, bosqich: str | None = None) -> None:
    baza.bajar("INSERT INTO buyurtma_tarix(buyurtma_id,bosqich,matn,kim_id,vaqt) VALUES(?,?,?,?,?)",
               bid, bosqich, matn_[:300], kim_id, vaqt.iso())


def _qatorlar_yoz(bid: int, qatorlar: list[dict]) -> None:
    baza.bajar("DELETE FROM buyurtma_qator WHERE buyurtma_id=?", bid)
    for i, q in enumerate(qatorlar):
        nom = (q.get("nom") or "").strip()[:200]
        k = baza.bir("SELECT * FROM katalog WHERE id=?", int(q["katalog_id"])) if q.get("katalog_id") else None
        if not nom and k:
            nom = k["nom"]
        if not nom:
            continue
        miqdor = float(q.get("miqdor") or 1)
        if miqdor <= 0:
            raise BuyurtmaXato(f"«{nom}» — miqdor noto'g'ri")
        narx = int(q.get("narx") if q.get("narx") is not None else (k["narx"] if k else 0))
        if narx < 0:
            raise BuyurtmaXato(f"«{nom}» — narx manfiy bo'lmaydi")
        baza.bajar("INSERT INTO buyurtma_qator(buyurtma_id,katalog_id,nom,birlik,miqdor,narx,tartib) VALUES(?,?,?,?,?,?,?)",
                   bid, k["id"] if k else None, nom, (q.get("birlik") or (k["birlik"] if k else "dona"))[:20], miqdor, narx, i)


def _ish_bilan_yangila(b: dict) -> dict:
    """Bog'langan holatlar bo'yicha o'zi yangilanadi: o'rnatish ishi bajarilsa — «bajarildi»; sotuv boshliq tomonidan
    rad etilsa yoki bekor qilinsa — «taklif»ga qaytadi (hisobda sotuv yo'q bo'lsa, «sotildi» deb turmasin)."""
    if b["bosqich"] == "sotildi" and b["sotuv_id"]:
        h = hisob.harakat(b["sotuv_id"])
        if not h or h["holat"] == "bekor":
            baza.bajar("UPDATE buyurtma SET bosqich='taklif', sotuv_id=NULL, bosqich_vaqt=? WHERE id=?", vaqt.iso(), b["id"])
            _tarix(b["id"], None, "Sotuv yozuvi bekor qilindi — buyurtma taklif bosqichiga qaytdi", "taklif")
            return baza.bir("SELECT * FROM buyurtma WHERE id=?", b["id"])
    if b["bosqich"] == "sotildi" and b["ish_id"]:
        i = ishlar.ish(b["ish_id"])
        if i and i["holat"] in ("bajarildi", "qabul"):
            baza.bajar("UPDATE buyurtma SET bosqich='bajarildi', bosqich_vaqt=? WHERE id=? AND bosqich='sotildi'", vaqt.iso(), b["id"])
            _tarix(b["id"], None, f"O'rnatish ishi #{i['id']} bajarildi — buyurtma yopildi", "bajarildi")
            b = baza.bir("SELECT * FROM buyurtma WHERE id=?", b["id"])
    return b


def bir(bid: int) -> dict | None:
    b = baza.bir("SELECT * FROM buyurtma WHERE id=?", bid)
    if not b:
        return None
    b = _ish_bilan_yangila(b)
    b["qatorlar"] = baza.hammasi("SELECT * FROM buyurtma_qator WHERE buyurtma_id=? ORDER BY tartib, id", bid)
    b["jami"] = jami(b, b["qatorlar"])
    b["mijoz"] = (baza.bir("SELECT ism FROM mijoz WHERE id=?", b["mijoz_id"]) or {}).get("ism", "?")
    b["masul"] = (odamlar.odam(b["masul_id"]) or {}).get("ism") if b["masul_id"] else None
    b["tarix"] = baza.hammasi("SELECT t.*, o.ism kim FROM buyurtma_tarix t LEFT JOIN odam o ON o.id=t.kim_id "
                              "WHERE buyurtma_id=? ORDER BY t.id", bid)
    return b


def royxat(bosqich: str | None = None, mijoz_id: int | None = None, sorov: str = "", limit: int = 500) -> list[dict]:
    shart, p = ["1=1"], []
    if bosqich in BOSQICHLAR:
        shart.append("bosqich=?")
        p.append(bosqich)
    if mijoz_id:
        shart.append("mijoz_id=?")
        p.append(mijoz_id)
    natija = []
    for b in baza.hammasi(f"SELECT * FROM buyurtma WHERE {' AND '.join(shart)} ORDER BY id DESC LIMIT {int(limit)}", *p):
        b = bir(b["id"])
        if sorov and matn.norm(sorov) not in matn.norm(f"#{b['id']} {b['mijoz']} {' '.join(q['nom'] for q in b['qatorlar'])} "
                                                       f"{b['izoh'] or ''} {b['manzil'] or ''}"):
            continue
        natija.append(b)
    return natija


def yarat(mijoz_id: int, kim_id: int, qatorlar: list[dict], chegirma: int = 0, valyuta: str = "UZS",
          manzil: str | None = None, muddat: str | None = None, masul_id: int | None = None, izoh: str | None = None) -> int:
    if not baza.bir("SELECT id FROM mijoz WHERE id=?", mijoz_id):
        raise BuyurtmaXato("Mijoz tanlanmagan")
    if valyuta not in ("UZS", "USD") or chegirma < 0:
        raise BuyurtmaXato("Valyuta yoki chegirma noto'g'ri")
    with baza.tranz():
        bid = baza.bajar("INSERT INTO buyurtma(mijoz_id,valyuta,chegirma,manzil,muddat,masul_id,izoh,yaratgan_id,yaratilgan,"
                         "bosqich_vaqt) VALUES(?,?,?,?,?,?,?,?,?,?)", mijoz_id, valyuta, int(chegirma), manzil or None,
                         (muddat or "")[:10] or None, masul_id, izoh or None, kim_id, vaqt.iso(), vaqt.iso())
        _qatorlar_yoz(bid, qatorlar)
        _tarix(bid, kim_id, "Buyurtma yaratildi", "yangi")
        baza.jurnal(kim_id, "buyurtma_yarat", f"buyurtma:{bid}", None, {"mijoz_id": mijoz_id})
    return bid


def tahrirla(bid: int, kim_id: int, **d) -> dict:
    b = baza.bir("SELECT * FROM buyurtma WHERE id=?", bid)
    if not b:
        raise BuyurtmaXato("Topilmadi")
    if b["bosqich"] in ("bajarildi", "bekor"):
        raise BuyurtmaXato("Yopilgan buyurtma o'zgarmaydi")
    pul_qismi = {"qatorlar", "chegirma", "valyuta", "mijoz_id"} & {k for k, v in d.items() if v is not None}
    if pul_qismi and b["bosqich"] not in OCHIQ:
        raise BuyurtmaXato("Sotilgan buyurtmaning narxi o'zgarmaydi — sotuv yozuvini tuzating yoki bekor qilib qayta yozing")
    with baza.tranz():
        for k in ("manzil", "izoh"):
            if d.get(k) is not None:
                baza.bajar(f"UPDATE buyurtma SET {k}=? WHERE id=?", d[k].strip()[:300] or None, bid)
        if d.get("muddat") is not None:
            baza.bajar("UPDATE buyurtma SET muddat=? WHERE id=?", d["muddat"][:10] or None, bid)
        if "masul_id" in d:
            baza.bajar("UPDATE buyurtma SET masul_id=? WHERE id=?", d["masul_id"], bid)
        if d.get("mijoz_id"):
            baza.bajar("UPDATE buyurtma SET mijoz_id=? WHERE id=?", int(d["mijoz_id"]), bid)
        if d.get("valyuta") in ("UZS", "USD"):
            baza.bajar("UPDATE buyurtma SET valyuta=? WHERE id=?", d["valyuta"], bid)
        if d.get("chegirma") is not None:
            if int(d["chegirma"]) < 0:
                raise BuyurtmaXato("Chegirma manfiy bo'lmaydi")
            baza.bajar("UPDATE buyurtma SET chegirma=? WHERE id=?", int(d["chegirma"]), bid)
        if d.get("qatorlar") is not None:
            _qatorlar_yoz(bid, d["qatorlar"])
        baza.jurnal(kim_id, "buyurtma_tahrir", f"buyurtma:{bid}", None, sorted(k for k, v in d.items() if v is not None))
    return bir(bid)


def bosqich_qoy(bid: int, kim_id: int, yangi: str, sabab: str = "") -> dict:
    """Oddiy o'tishlar: yangi ↔ taklif, sotildi → bajarildi, → bekor. «Sotildi» — alohida (sotildi())."""
    b = bir(bid)
    if not b:
        raise BuyurtmaXato("Topilmadi")
    eski = b["bosqich"]
    if yangi == eski:
        return b
    if yangi == "sotildi":
        raise BuyurtmaXato("Sotish — «Sotildi» oynasi orqali (to'lov va qarz yoziladi)")
    if eski in ("bajarildi", "bekor"):
        raise BuyurtmaXato("Yopilgan buyurtma")
    if yangi in OCHIQ and eski not in OCHIQ:
        raise BuyurtmaXato("Sotilgan buyurtma ortga qaytmaydi — bekor qilib qayta yozing")
    if yangi == "bajarildi" and eski != "sotildi":
        raise BuyurtmaXato("Avval sotilsin")
    if yangi == "bekor":
        if not (sabab or "").strip():
            raise BuyurtmaXato("Bekor qilish sababini yozing")
        with baza.tranz():
            if b["sotuv_id"] and hisob.harakat(b["sotuv_id"])["holat"] != "bekor":
                hisob.bekor_qil(b["sotuv_id"], kim_id, f"buyurtma #{bid} bekor: {sabab}")
            if b["ish_id"]:
                i = ishlar.ish(b["ish_id"])
                if i and i["holat"] in ishlar.OCHIQ:
                    ishlar.bekor(b["ish_id"], kim_id, f"buyurtma #{bid} bekor: {sabab}")
            baza.bajar("UPDATE buyurtma SET bosqich='bekor', bekor_sabab=?, bosqich_vaqt=? WHERE id=?", sabab.strip()[:300],
                       vaqt.iso(), bid)
            _tarix(bid, kim_id, f"Bekor qilindi: {sabab.strip()}", "bekor")
        return bir(bid)
    if yangi not in BOSQICHLAR:
        raise BuyurtmaXato("Bosqich noto'g'ri")
    baza.bajar("UPDATE buyurtma SET bosqich=?, bosqich_vaqt=? WHERE id=?", yangi, vaqt.iso(), bid)
    _tarix(bid, kim_id, f"{NOMI[eski]} → {NOMI[yangi]}", yangi)
    return bir(bid)


def sotildi(bid: int, kim_id: int, tolandi: int = 0, kassa_id: int | None = None, qarz_muddati: str | None = None,
            ish: dict | None = None) -> dict:
    """Hisobga sotuv (jami summa; to'langani — kassaga, qolgani qarz; muddat — va'da). Xohlasa o'rnatish ishi beriladi."""
    b = bir(bid)
    if not b:
        raise BuyurtmaXato("Topilmadi")
    if b["bosqich"] not in OCHIQ:
        raise BuyurtmaXato("Bu buyurtma allaqachon sotilgan yoki yopilgan")
    if b["jami"] <= 0:
        raise BuyurtmaXato("Buyurtmada narxli qator yo'q")
    if tolandi < 0 or tolandi > b["jami"]:
        raise BuyurtmaXato("To'langan summa noto'g'ri")
    if tolandi and not kassa_id:
        raise BuyurtmaXato("Pul qaysi kassaga tushdi — tanlang")
    if tolandi < b["jami"] and not qarz_muddati:
        raise BuyurtmaXato("Qolgan qarzni qachon to'laydi — sanani tanlang")
    nomlar = ", ".join(f"{q['nom']} × {q['miqdor']:g}" for q in b["qatorlar"])[:200]
    p = {"summa": b["jami"], "valyuta": b["valyuta"], "tolandi": tolandi, "mijoz_id": b["mijoz_id"], "sotuvchi_id": kim_id,
         "izoh": f"Buyurtma #{bid}: {nomlar}"}
    if kassa_id:
        p["kassa_id"] = int(kassa_id)
    if tolandi < b["jami"]:
        p["muddat"] = qarz_muddati[:10]
    natija = {"ish_id": None}
    with baza.tranz():
        sid, kid = hisob.sotuv_tuz(p, kim_id)
        r = hisob.faollashtir(sid, kim_id)  # buyurtma aniq — «takror» so'ralmaydi; R4/qoidalar faollashtir ichida
        if kid and r["holat"] == "faol":
            hisob.faollashtir(kid, kim_id)
        natija.update(sotuv_id=sid, holat=r["holat"])
        baza.bajar("UPDATE buyurtma SET bosqich='sotildi', sotuv_id=?, bosqich_vaqt=? WHERE id=?", sid, vaqt.iso(), bid)
        _tarix(bid, kim_id, f"Sotildi: {matn.pul(b['jami'], b['valyuta'])}"
                            + (f", to'landi {matn.pul(tolandi, b['valyuta'])}" if tolandi else "")
                            + (f", qolgani {qarz_muddati[:10]} gacha" if tolandi < b["jami"] else ""), "sotildi")
        if ish and ish.get("ijrochilar"):
            iid, _ = ishlar.ish_yarat(ish.get("nom") or f"O'rnatish: {b['mijoz']} (buyurtma #{bid})",
                                      [(int(x), 1) for x in ish["ijrochilar"]], kim_id, joy=b["manzil"],
                                      mijoz_id=b["mijoz_id"], muddat=ish.get("muddat") or b["muddat"], soat=ish.get("soat"),
                                      narx=ish.get("narx") or None, valyuta=b["valyuta"], ish_turi="buyurtma",
                                      tavsif=nomlar)
            baza.bajar("UPDATE buyurtma SET ish_id=? WHERE id=?", iid, bid)
            _tarix(bid, kim_id, f"O'rnatish ishi #{iid} berildi", "sotildi")
            natija["ish_id"] = iid
    return natija | {"buyurtma": bir(bid)}


def mahsulot_sotuvi(dan: str, gacha: str) -> list[dict]:
    """Hisobot uchun: davrda sotilgan (sotuvi faol) buyurtma qatorlari — mahsulot bo'yicha miqdor va summa (so'mda)."""
    from . import kurs
    jamlama: dict[str, dict] = {}
    for r in baza.hammasi(
            "SELECT q.*, b.valyuta, b.chegirma, h.hisob_sana, b.id bid FROM buyurtma_qator q JOIN buyurtma b ON b.id=q.buyurtma_id "
            "JOIN harakat h ON h.id=b.sotuv_id WHERE h.holat IN ('faol','nizo') AND h.hisob_sana BETWEEN ? AND ?", dan, gacha):
        k = jamlama.setdefault(r["nom"], {"nom": r["nom"], "birlik": r["birlik"], "miqdor": 0, "summa": 0})
        k["miqdor"] += r["miqdor"]
        k["summa"] += kurs.somga(round(r["miqdor"] * r["narx"]), r["valyuta"], r["hisob_sana"]) or 0
    return sorted(jamlama.values(), key=lambda x: -x["summa"])
