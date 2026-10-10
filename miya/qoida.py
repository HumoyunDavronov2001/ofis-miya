"""Boshliq qoidalari (Q1, Q2) — faqat tayyor turlar; tekshiruvni dastur qiladi, sun'iy intellekt emas."""
import json

from . import baza, kurs, matn, vaqt

TURLAR = {
    "avans_foiz": {"nom": "Avans chegarasi", "param": {"foiz": float},
                   "matn": lambda p: f"Bir oyda avanslar oylik maoshning {p['foiz']:g} foizidan oshmasin"},
    "avans_soni": {"nom": "Oyiga avanslar soni", "param": {"soni": int},
                   "matn": lambda p: f"Bir xodimga oyiga {p['soni']} martadan ko'p avans berilmasin"},
    "xarajat_chegara": {"nom": "Xarajat chegarasi", "param": {"summa": int, "valyuta": str},
                        "matn": lambda p: f"{matn.pul(p['summa'], p.get('valyuta', 'UZS'))} dan katta xarajat — "
                                          f"faqat boshliq ruxsati bilan"},
    "nasiya_chegara": {"nom": "Nasiya chegarasi", "param": {"summa": int, "valyuta": str},
                       "matn": lambda p: f"Bir mijozning qarzi {matn.pul(p['summa'], p.get('valyuta', 'UZS'))} dan "
                                         f"oshsa — faqat boshliq ruxsati bilan"},
    "nasiya_ishonch": {"nom": "Nasiya — ishonchli mijozga", "param": {"foiz": float, "kamida": int},
                       "matn": lambda p: f"Nasiya faqat va'dalarining kamida {p['foiz']:g} foizini vaqtida bajargan "
                                         f"mijozga (kamida {p['kamida']} ta va'dasi bo'lsa)"},
}


class QoidaXato(Exception):
    pass


def tozala(tur: str, param: dict) -> dict:
    if tur not in TURLAR:
        raise QoidaXato("Bu turdagi qoidani dastur tekshira olmaydi")
    natija = {}
    for k, t in TURLAR[tur]["param"].items():
        if k == "valyuta":
            natija[k] = param.get(k) or "UZS"
            if natija[k] not in ("UZS", "USD"):
                raise QoidaXato("Valyuta noto'g'ri")
            continue
        if param.get(k) in (None, ""):
            raise QoidaXato(f"Qoidada «{k}» qiymati yo'q")
        natija[k] = t(param[k])
        if natija[k] <= 0:
            raise QoidaXato("Qiymat musbat bo'lsin")
    return natija


def qoida_matni(tur: str, param: dict) -> str:
    return TURLAR[tur]["matn"](param)


def qoy(tur: str, param: dict, kim_id: int, asl_matn: str | None = None) -> int:
    p = tozala(tur, param)
    with baza.tranz():
        qid = baza.bajar("INSERT INTO qoida(tur,param,matn,yaratilgan) VALUES(?,?,?,?)",
                         tur, json.dumps(p), asl_matn, vaqt.iso())
        baza.jurnal(kim_id, "qoida_qoyildi", f"qoida:{qid}", None, {"tur": tur, "param": p})
    return qid


def ochir(qid: int, kim_id: int) -> None:
    with baza.tranz():
        baza.bajar("UPDATE qoida SET faol=0 WHERE id=?", qid)
        baza.jurnal(kim_id, "qoida_ochirildi", f"qoida:{qid}")


def faol_qoidalar() -> list[dict]:
    natija = []
    for r in baza.hammasi("SELECT * FROM qoida WHERE faol=1 ORDER BY id"):
        r["param"] = json.loads(r["param"])
        r["tavsif"] = qoida_matni(r["tur"], r["param"])
        natija.append(r)
    return natija


def _som(summa: int, valyuta: str, sana: str) -> int:
    return kurs.somga(summa, valyuta, sana) or 0


def tekshir(h: dict, kim: dict | None) -> list[str]:
    """Taklif qilingan harakat qoidalarga mosmi. Buzilishlar ro'yxati (bo'sh — mos)."""
    from . import hisob, maosh  # aylanma importdan saqlanish
    buzilish = []
    oy = vaqt.oy(h["voqea_sana"])
    for q in faol_qoidalar():
        p, tur = q["param"], q["tur"]
        if tur in ("avans_foiz", "avans_soni") and h["tur"] == "avans" and h["odam_id"]:
            oldingi = baza.hammasi(
                "SELECT * FROM harakat WHERE tur='avans' AND odam_id=? AND holat IN ('faol','nizo','ruxsat_kutilmoqda') "
                "AND substr(voqea_sana,1,7)=? AND id!=?", h["odam_id"], oy, h["id"])
            if tur == "avans_soni" and len(oldingi) + 1 > p["soni"]:
                buzilish.append(f"bu oyda {len(oldingi) + 1}-avans (chegara: {p['soni']})")
            if tur == "avans_foiz":
                oylik = maosh.oylik_summa(h["odam_id"], oy)
                if oylik:
                    v = oylik[1]
                    jami = sum((r["summa2"] or r["summa"]) for r in oldingi) + (h["summa2"] or h["summa"])
                    chegara = int(oylik[0] * p["foiz"] / 100)
                    if jami > chegara:
                        buzilish.append(f"oydagi avanslar {matn.pul(jami, v)} — oylikning {p['foiz']:g}% i "
                                        f"{matn.pul(chegara, v)}")
        if tur == "xarajat_chegara" and h["tur"] == "chiqim":
            if _som(h["summa"], h["valyuta"], h["voqea_sana"]) > _som(p["summa"], p["valyuta"], h["voqea_sana"]):
                buzilish.append(f"xarajat {matn.pul(h['summa'], h['valyuta'])} — chegara "
                                f"{matn.pul(p['summa'], p['valyuta'])}")
        if tur == "nasiya_chegara" and h["tur"] == "sotuv" and h["mijoz_id"]:
            hozirgi = hisob.qoldiq(f"mijoz:{h['mijoz_id']}")
            qarz = sum(_som(s, v, h["voqea_sana"]) for v, s in hozirgi.items())
            tolandi = baza.qiymat("SELECT COALESCE(SUM(summa),0) FROM harakat WHERE bog_id=? AND id!=? AND tur='kirim' "
                                  "AND holat!='bekor'", h["id"], h["id"]) or 0
            yangi = qarz + _som(h["summa"] - tolandi, h["valyuta"], h["voqea_sana"])
            if yangi > _som(p["summa"], p["valyuta"], h["voqea_sana"]):
                buzilish.append(f"mijoz qarzi {matn.pul(yangi)} bo'ladi — chegara {matn.pul(p['summa'], p['valyuta'])}")
        if tur == "nasiya_ishonch" and h["tur"] == "sotuv" and h["mijoz_id"]:
            tolandi = baza.qiymat("SELECT COALESCE(SUM(summa),0) FROM harakat WHERE bog_id=? AND id!=? AND tur='kirim' "
                                  "AND holat!='bekor'", h["id"], h["id"]) or 0
            if h["summa"] - tolandi > 0:
                from . import vadalar
                i = vadalar.ishonch(h["mijoz_id"], n=10)
                if i["jami"] >= p["kamida"] and i["vaqtida"] * 100 < p["foiz"] * i["jami"]:
                    buzilish.append(f"mijoz {i['matn']} — kamida {p['foiz']:g}% kerak")
    return buzilish
