"""Signallar (S7, D-b): dastur o'zi topadigan holatlar — bitta joyda.

Panel «Diqqat», ertalabki va haftalik xulosa shu ro'yxatni oladi. Signal — ma'lumot, hech narsani to'xtatmaydi.
"""
from datetime import timedelta
from statistics import median

from . import baza, davomat, hisob, ishlar, kurs, maosh, matn, mijozlar, odamlar, vadalar, vaqt

TARTIB = ["nizo", "ruxsat", "vada_bugun", "maosh", "vada_buzildi", "kassa_farq", "takror_chek", "katta_xarajat",
          "nasiya", "ish_kech", "band", "bosh", "davomat", "qolda", "uxlagan", "uzoq_tasdiq"]  # bugungi ish oldinda


def _kun(n: int) -> str:
    return (vaqt.bugun() + timedelta(days=n)).isoformat()


def vada_manba(v: dict) -> dict:
    """Va'da qatori uchun: qayerdan kelgani (ovoz, matn) va mijozning va'da tarixi."""
    xb = baza.bir("SELECT tur, vaqt, davomiylik FROM xabar WHERE id=?", v["xabar_id"]) if v["xabar_id"] else None
    ish_ = vadalar.ishonch(v["mijoz_id"])
    m = mijozlar.mijoz(v["mijoz_id"]) or {}
    return {"manba": {"tur": xb["tur"], "sana": xb["vaqt"][:10], "davomiylik": xb["davomiylik"], "xabar_id": v["xabar_id"]}
            if xb else None, "ishonch": ish_["matn"] if ish_["jami"] else None,
            "ishonch_yaxshi": bool(ish_["jami"]) and ish_["vaqtida"] * 5 >= ish_["jami"] * 4,
            "ishonch_kerak": v["kim"] == "mijoz", "mijoz_botda": bool(m.get("tg_id"))}


def _som(h: dict) -> int:
    return kurs.somga(h["summa"], h["valyuta"], h["voqea_sana"]) or 0


# ---------- pul ----------

def _pul(natija: list) -> None:
    for h in baza.hammasi("SELECT * FROM harakat WHERE holat='nizo' ORDER BY id DESC LIMIT 10"):
        natija.append({"tur": "nizo", "daraja": "xavf", "matn": f"Nizo: {hisob.qisqa_tavsif(h)}",
                       "izoh": "Bir tomon «olmadim/bermadim» dedi", "harakat_id": h["id"]})
    for h in baza.hammasi("SELECT * FROM harakat WHERE holat='ruxsat_kutilmoqda' ORDER BY id DESC LIMIT 10"):
        natija.append({"tur": "ruxsat", "daraja": "kut", "matn": f"Ruxsat kerak: {hisob.qisqa_tavsif(h)}",
                       "izoh": h["qoida_buzilish"], "harakat_id": h["id"]})
    for s in baza.hammasi("SELECT s.*, k.nom, k.valyuta FROM kassa_sanoq s JOIN kassa k ON k.id=s.kassa_id "
                          "WHERE s.farq!=0 AND s.sana>=? ORDER BY s.sana DESC LIMIT 5", _kun(-7)):
        natija.append({"tur": "kassa_farq", "daraja": "xavf",
                       "matn": f"{vaqt.sana_matn(s['sana'], False)}: {s['nom']}da farq {matn.pul(s['farq'], s['valyuta'])}",
                       "izoh": s["izoh"] or "Izoh yozilmagan"})
    eski = vaqt.iso(vaqt.hozir() - timedelta(days=1))
    for h in baza.hammasi("SELECT * FROM harakat WHERE holat='faol' AND faollashgan<? AND (beruvchi_holat='kutilmoqda' "
                          "OR oluvchi_holat='kutilmoqda') ORDER BY id LIMIT 10", eski):
        natija.append({"tur": "uzoq_tasdiq", "daraja": "kut", "matn": f"1 kundan beri tasdiqlanmagan: {hisob.qisqa_tavsif(h)}",
                       "izoh": "", "harakat_id": h["id"]})
    natija.extend(katta_xarajatlar())
    natija.extend(takror_cheklar())
    for x in odamlar.faol_odamlar():
        q = hisob.qoldiq_bir(f"qol:{x['id']}")
        if q > 0:
            oxirgi = baza.qiymat("SELECT MAX(hisob_sana) FROM harakat WHERE ga=? AND holat='faol'", f"qol:{x['id']}")
            if oxirgi and oxirgi < _kun(-3):
                natija.append({"tur": "qolda", "daraja": "kut", "matn": f"{x['ism']} qo'lida {matn.pul(q)} turibdi",
                               "izoh": f"{vaqt.sana_matn(oxirgi, False)} dan beri kassaga topshirilmagan"})


def katta_xarajatlar(kun: int = 7) -> list[dict]:
    """Shu turdagi oxirgi 90 kunda kamida 5 ta xarajat bo'lsa — medianadan 3 baravar katta xarajat (D-b)."""
    natija = []
    for h in baza.hammasi("SELECT * FROM harakat WHERE tur='chiqim' AND holat IN ('faol','nizo') AND voqea_sana>=? "
                          "AND xarajat_turi_id IS NOT NULL ORDER BY id DESC LIMIT 200", _kun(-kun)):
        avval = baza.hammasi("SELECT summa, valyuta, voqea_sana FROM harakat WHERE tur='chiqim' AND holat IN ('faol','nizo') "
                             "AND xarajat_turi_id=? AND id!=? AND voqea_sana BETWEEN ? AND ?", h["xarajat_turi_id"], h["id"],
                             (vaqt.sana(h["voqea_sana"]) - timedelta(days=90)).isoformat(), h["voqea_sana"])
        if len(avval) < 5:
            continue
        odatiy = median(_som(r) for r in avval)
        if odatiy > 0 and _som(h) > 3 * odatiy:
            tur = baza.qiymat("SELECT nom FROM xarajat_turi WHERE id=?", h["xarajat_turi_id"]) or "Xarajat"
            yozgan = odamlar.odam(h["yozgan_id"])
            natija.append({"tur": "katta_xarajat", "daraja": "kut",
                           "matn": f"Odatdan katta xarajat: {tur} — {matn.pul(h['summa'], h['valyuta'])}",
                           "izoh": f"Odatda {matn.pul(int(odatiy))} atrofida · {vaqt.sana_matn(h['voqea_sana'], False)}"
                                   + (f" · yozgan {yozgan['ism']}" if yozgan else ""), "harakat_id": h["id"]})
    return natija


def takror_cheklar(kun: int = 30) -> list[dict]:
    """Bir chek rasmi ikki faol yozuvda — odam «boshqa» deb o'tkazib yuborgan (D-b)."""
    natija = []
    for r in baza.hammasi("SELECT i.xesh, GROUP_CONCAT(DISTINCT h.id) idlar FROM ilova i JOIN harakat h ON h.id=i.harakat_id "
                          "WHERE i.xesh IS NOT NULL AND h.holat IN ('faol','nizo') AND h.voqea_sana>=? GROUP BY i.xesh "
                          "HAVING COUNT(DISTINCT h.id)>1", _kun(-kun)):
        idlar = sorted(int(x) for x in r["idlar"].split(","))
        qatorlar = [hisob.harakat(i) for i in idlar]
        natija.append({"tur": "takror_chek", "daraja": "xavf",
                       "matn": f"Bitta chek {len(idlar)} marta yozilgan: {hisob.qisqa_tavsif(qatorlar[-1])}",
                       "izoh": " · ".join(f"#{h['id']} {vaqt.sana_matn(h['voqea_sana'], False)}" for h in qatorlar),
                       "harakat_id": idlar[-1]})
    return natija


# ---------- mijozlar ----------

def _mijoz(natija: list, manba: bool) -> None:
    bugun = vaqt.bugun().isoformat()
    buzilgan_mijoz = set()
    for v in vadalar.royxat(dan=_kun(-30), gacha=bugun):
        if v["holat"] != "ochiq":
            continue
        if v["holat_h"] in ("buzildi", "qisman"):
            buzilgan_mijoz.add(v["mijoz_id"])
            natija.append({"tur": "vada_buzildi", "daraja": "xavf",
                           "matn": f"Va'da bajarilmadi: {v['mijoz']} — " + (
                               matn.pul(v["qolgan"] if v["qolgan"] is not None else v["summa"], v["valyuta"])
                               if v["tur"] == "tolov" else (v["matn"] or "")),
                           "izoh": f"Muddat {vaqt.sana_matn(v['muddat'], False)}" + (
                               f" · to'langani {matn.pul(v['qoplandi'], v['valyuta'])}" if v.get("qoplandi") else ""),
                           "mijoz_id": v["mijoz_id"], "vada_id": v["id"]})
        elif v["muddat"] == bugun and v["holat_h"] == "ochiq":
            if v["kim"] == "biz":
                matn_ = f"Bugun {v['mijoz']}ga bergan va'damiz muddati: " + (
                    matn.pul(v["summa"], v["valyuta"]) if v["tur"] == "tolov" else (v["matn"] or ""))
            elif v["tur"] == "tolov":
                matn_ = (f"{v['mijoz']} bugun {matn.pul(v['qolgan'] if v['qolgan'] is not None else v['summa'], v['valyuta'])}"
                         " to'lashni va'da qilgan")
            else:
                matn_ = f"{v['mijoz']} bugun va'da qilgan: {v['matn'] or ''}"
            natija.append({"tur": "vada_bugun", "daraja": "kut", "matn": matn_, "izoh": "", "mijoz_id": v["mijoz_id"],
                           "vada_id": v["id"], "vada_tur": v["tur"], "vada_kim": v["kim"],
                           "summa_som": kurs.somga(v["qolgan"] or 0, v["valyuta"]) or 0 if v["tur"] == "tolov" else 0,
                           **(vada_manba(v) if manba else {})})
    for m in mijozlar.uxlab_qolganlar()[:5]:
        natija.append({"tur": "uxlagan", "daraja": "kut", "matn": f"{m['ism']} {m['otdi_kun']} kundan beri kelmadi",
                       "izoh": f"Odatda {m['ortacha_kun']:g} kunda bir keladi · o'rtacha xaridi "
                               f"{matn.qisqa_pul(m['ortacha_summa'])}", "mijoz_id": m["id"]})
    for q in hisob.mijoz_qarzlari():
        if q["id"] not in buzilgan_mijoz and q["muddat"] and q["muddat"] < bugun:
            natija.append({"tur": "nasiya", "daraja": "kut",
                           "matn": f"{q['ism']}: qarz muddati o'tgan ({vaqt.sana_matn(q['muddat'], False)})",
                           "izoh": ", ".join(matn.pul(s, v) for v, s in q["qarz"].items()), "mijoz_id": q["id"]})


# ---------- ishlar va odamlar ----------

def _ish(natija: list, boshliq: bool) -> None:
    for i in ishlar.ishlar(faqat_ochiq=True):
        k = ishlar.kechikdi_kun(i)
        if k:
            natija.append({"tur": "ish_kech", "daraja": "kut" if k < 3 else "xavf", "matn": f"Kechikkan ish: {ishlar.qisqa(i)}",
                           "izoh": f"{k} kun · {', '.join(x['ism'] for x in i['ijrochilar'])}", "ish_id": i["id"]})
    natija.extend(band_boshlar())
    if boshliq:
        for r in baza.hammasi("SELECT d.*, o.ism FROM davomat d JOIN odam o ON o.id=d.odam_id WHERE d.holat='sorov'"):
            natija.append({"tur": "davomat", "daraja": "kut", "matn": f"{r['ism']}: {vaqt.sana_matn(r['sana'], False)} kunini "
                                                                   f"belgilashni so'radi", "izoh": r["izoh"] or "",
                           "davomat_id": r["id"]})


def band_boshlar() -> list[dict]:
    """Haddan ortiq band va bo'sh xodimlar (D-b) — faqat oxirgi 30 kunda ish olgan xodimlar orasida."""
    xodimlar = baza.hammasi(
        "SELECT o.id, o.ism FROM odam o WHERE o.holat='faol' AND o.rol='xodim' AND o.id IN (SELECT ij.odam_id FROM "
        "ish_ijrochi ij JOIN ish i ON i.id=ij.ish_id WHERE substr(i.yaratilgan,1,10)>=?)", _kun(-30))
    if not xodimlar:
        return []
    ochiq = {r["odam_id"]: r["n"] for r in baza.hammasi(
        "SELECT ij.odam_id, COUNT(*) n FROM ish_ijrochi ij JOIN ish i ON i.id=ij.ish_id "
        "WHERE i.holat IN ('yangi','bajarildi_dalil','qayta') GROUP BY ij.odam_id")}
    ortacha = sum(ochiq.get(x["id"], 0) for x in xodimlar) / len(xodimlar)
    natija = []
    # oxirgi 3 ish kuni
    ish_kunlari, d = [], vaqt.bugun()
    while len(ish_kunlari) < 3:
        d -= timedelta(days=1)
        if not ishlar.dam_olishmi(d):
            ish_kunlari.append(d)
    for x in xodimlar:
        n = ochiq.get(x["id"], 0)
        boshqalar = [ochiq.get(y["id"], 0) for y in xodimlar if y["id"] != x["id"]]
        boshqa_ort = sum(boshqalar) / len(boshqalar) if boshqalar else 0
        if n >= 5 and n >= 2 * max(boshqa_ort, 1) and len(xodimlar) > 1:
            natija.append({"tur": "band", "daraja": "kut", "matn": f"{x['ism']}da {n} ta ochiq ish",
                           "izoh": f"Boshqalarda o'rtacha {boshqa_ort:.1f}".replace(".", ",").replace(",0", "") + " ta",
                           "odam_id": x["id"]})
        bugungi = davomat.bugungi(x["id"])
        if n == 0 and bugungi and bugungi.get("keldi") and not ishlar.dam_olishmi(vaqt.bugun()):
            bajargan = baza.qiymat("SELECT COUNT(*) FROM ish i JOIN ish_ijrochi ij ON ij.ish_id=i.id WHERE ij.odam_id=? "
                                   "AND substr(i.bajarildi_vaqt,1,10)>=?", x["id"], ish_kunlari[-1].isoformat())
            if not bajargan:
                natija.append({"tur": "bosh", "daraja": "kut", "matn": f"{x['ism']} bugun keldi, ochiq ishi yo'q",
                               "izoh": "Oxirgi 3 ish kunida bajargan ishi ham yo'q", "odam_id": x["id"]})
    return natija


# ---------- jamlash ----------

def royxat(o: dict, manba: bool = True) -> list[dict]:
    """So'ragan odam ko'ra oladigan signallar, muhimlik tartibida."""
    if not o or o["holat"] != "faol":
        return []
    boshliq = odamlar.boshliqmi(o)
    natija: list[dict] = []
    if boshliq or o["rol"] == "kassir":
        _pul(natija)
    if boshliq or odamlar.mumkin(o, "mijoz_qarz"):
        _mijoz(natija, manba)
    if ishlar.tolov_huquqi(o):
        _ish(natija, boshliq)
    if boshliq:
        b = maosh.bashorat()
        if b["yetmaydi"] > 0 and b["qoldi_kun"] <= 10:
            natija.append({"tur": "maosh", "daraja": "xavf",
                           "matn": f"Maosh kuni ({vaqt.sana_matn(b['kun'], False)}) {matn.pul(b['yetmaydi'])} yetmaydi",
                           "izoh": f"Kerak {matn.qisqa_pul(b['kerak'])} · qo'lda {matn.qisqa_pul(b['aniq_pul'])}"})
    natija.sort(key=lambda x: TARTIB.index(x["tur"]) if x["tur"] in TARTIB else len(TARTIB))
    return natija
