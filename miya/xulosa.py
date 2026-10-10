"""Ertalabki va haftalik xulosa (S6, S8, D-a, D-c).

Faktlarni dastur yig'adi va hisoblaydi. Sun'iy intellekt faqat shu faktlardan matn yozadi; matndagi har raqam faktlar
bilan solishtiriladi — mos kelmasa (yoki sun'iy intellekt o'chiq bo'lsa) tayyor qolip yuboriladi.
"""
import json
from datetime import date, timedelta

from . import ai, baza, hisob, ishlar, kurs, maosh, matn, odamlar, signallar, vadalar, vaqt, xotira


def _p(minor: int, valyuta: str = "UZS") -> dict:
    return {"summa": minor / 100 if valyuta == "USD" else minor, "valyuta": valyuta, "korinish": matn.pul(minor, valyuta)}


def _kassalar() -> dict:
    jami, royxat = 0, []
    for k in hisob.kassa_holati():
        royxat.append({"kassa": k["nom"], "qoldiq": _p(k["qoldiq"], k["valyuta"])})
        jami += kurs.somga(k["qoldiq"], k["valyuta"]) or 0
    return {"royxat": royxat, "jami_somda": _p(jami)}


def _davr(dan: str, gacha: str) -> dict:
    j = hisob.davr_jami(dan, gacha)
    return {"sotuv": j["sotuv"], "xarajat": j["xarajat"], "kirim": j["kassa_kirim"], "chiqim": j["kassa_chiqim"],
            "xarajat_turlar": j["xarajat_turlar"]}


def oldingi_ish_kuni(d: date) -> date:
    d -= timedelta(days=1)
    for _ in range(7):
        if not ishlar.dam_olishmi(d):
            return d
        d -= timedelta(days=1)
    return d


# ---------- ertalabki (S6) ----------

def ertalab_faktlar() -> dict:
    bugun = vaqt.bugun()
    kecha = oldingi_ish_kuni(bugun)
    kd = _davr(kecha.isoformat(), kecha.isoformat())
    boss = odamlar.boshliq()
    sig = signallar.royxat(boss, manba=False) if boss else []
    tushum = [v for v in vadalar.royxat(dan=bugun.isoformat(), gacha=bugun.isoformat(), faqat_ochiq=True)
              if v["tur"] == "tolov" and v["kim"] == "mijoz"]
    bugungi_ish = [i for i in ishlar.ishlar(faqat_ochiq=True) if i["muddat"] == bugun.isoformat()]
    kechikkan = [i for i in ishlar.ishlar(faqat_ochiq=True) if ishlar.kechikdi_kun(i)]
    b = maosh.bashorat()
    return {
        "bugun": bugun.isoformat(), "bugun_matn": vaqt.sana_matn(bugun), "kecha": kecha.isoformat(),
        "kecha_matn": vaqt.sana_matn(kecha, False),
        "kassa": _kassalar(),
        "kecha_davr": {k: _p(v) for k, v in kd.items() if k != "xarajat_turlar"},
        "bugun_tushum": {"jami": _p(sum(kurs.somga(v["qolgan"] or 0, v["valyuta"]) or 0 for v in tushum)),
                         "royxat": [{"mijoz": v["mijoz"], "summa": _p(v["qolgan"] or 0, v["valyuta"])} for v in tushum]},
        "ishlar": {"bugun_muddati": len(bugungi_ish), "kechikkan": len(kechikkan),
                   "kechikkanlar": [ishlar.qisqa(i) for i in kechikkan[:5]]},
        "maosh": {"kun": vaqt.sana_matn(b["kun"], False), "qoldi_kun": b["qoldi_kun"], "kerak": _p(b["kerak"]),
                  "qolda": _p(b["aniq_pul"]), "yetmaydi": _p(b["yetmaydi"])} if b["qoldi_kun"] <= 7 else None,
        "signallar": [{"tur": s["tur"], "matn": s["matn"], "izoh": s.get("izoh") or ""} for s in sig[:8]],
        "signal_soni": len(sig),
        # R7: bugungi uchrashuv va eslatmalar (xotiradan)
        "kun_tartibi": [{"soat": x["soat"] or "", "matn": x["matn"]} for x in xotira.bugungilar(bugun.isoformat())[:10]],
    }


def ertalab_qolip(f: dict) -> str:
    q = [f"Xayrli tong! {f['bugun_matn']}."]
    if f.get("kun_tartibi"):
        q.append("Bugun: " + "; ".join(f"{x['soat'] + ' — ' if x['soat'] else ''}{x['matn']}" for x in f["kun_tartibi"]) + ".")
    q.append(f"Kassalarda: {f['kassa']['jami_somda']['korinish']}.")
    k = f["kecha_davr"]
    if any(v["summa"] for v in k.values()):
        q.append(f"{f['kecha_matn']}: kirim {k['kirim']['korinish']}, chiqim {k['chiqim']['korinish']}, "
                 f"sotuv {k['sotuv']['korinish']}.")
    t = f["bugun_tushum"]
    if t["royxat"]:
        q.append(f"Bugun kutilayotgan tushum: {t['jami']['korinish']} — "
                 + ", ".join(f"{x['mijoz']} {x['summa']['korinish']}" for x in t["royxat"][:4]) + ".")
    i = f["ishlar"]
    if i["bugun_muddati"] or i["kechikkan"]:
        q.append(f"Ishlar: bugun muddati {i['bugun_muddati']} ta, kechikkan {i['kechikkan']} ta.")
    m = f["maosh"]
    if m and m["yetmaydi"]["summa"]:
        q.append(f"Maosh kuni {m['kun']}: {m['yetmaydi']['korinish']} yetmaydi.")
    for s in f["signallar"][:4]:
        if s["tur"] not in ("vada_bugun", "maosh", "ish_kech"):
            q.append(f"• {s['matn']}")
    return "\n".join(q)


# ---------- haftalik (S8) ----------

def hafta_faktlar() -> dict:
    bugun = vaqt.bugun()
    dushanba = bugun - timedelta(days=bugun.weekday())
    dan, gacha = dushanba - timedelta(days=7), dushanba - timedelta(days=1)
    odan, ogacha = dan - timedelta(days=7), dan - timedelta(days=1)
    joriy, oldingi = _davr(dan.isoformat(), gacha.isoformat()), _davr(odan.isoformat(), ogacha.isoformat())
    farq = {k: _p(joriy[k] - oldingi[k]) for k in ("sotuv", "xarajat", "kirim", "chiqim")}
    bajarilgan = baza.qiymat("SELECT COUNT(*) FROM ish WHERE holat IN ('bajarildi','qabul') AND "
                             "substr(bajarildi_vaqt,1,10) BETWEEN ? AND ?", dan.isoformat(), gacha.isoformat()) or 0
    kech_bajarilgan = baza.qiymat("SELECT COUNT(*) FROM ish WHERE holat IN ('bajarildi','qabul') AND muddat IS NOT NULL AND "
                                  "substr(bajarildi_vaqt,1,10) BETWEEN ? AND ? AND substr(bajarildi_vaqt,1,10)>muddat",
                                  dan.isoformat(), gacha.isoformat()) or 0
    ochiq_kech = len([i for i in ishlar.ishlar(faqat_ochiq=True) if ishlar.kechikdi_kun(i)])
    vs = {"vaqtida": 0, "kech": 0, "qisman": 0, "buzildi": 0}
    for v in vadalar.royxat(dan=dan.isoformat(), gacha=gacha.isoformat()):
        if v["kim"] == "mijoz" and v["holat_h"] in vs:
            vs[v["holat_h"]] += 1
    eski = vaqt.iso(vaqt.hozir() - timedelta(days=1))
    tasdiqsiz = baza.hammasi("SELECT * FROM harakat WHERE holat='faol' AND faollashgan<? AND (beruvchi_holat='kutilmoqda' "
                             "OR oluvchi_holat='kutilmoqda') ORDER BY id", eski)
    nizolar = baza.hammasi("SELECT * FROM harakat WHERE holat='nizo' ORDER BY id")
    kartalar = baza.hammasi("SELECT k.*, o.ism FROM karta k LEFT JOIN odam o ON o.id=k.odam_id WHERE k.holat='ochiq' "
                            "AND k.yaratilgan<? ORDER BY k.id", eski)
    navbat = baza.qiymat("SELECT COUNT(*) FROM navbat WHERE holat='kutmoqda'") or 0
    return {
        "dan": dan.isoformat(), "gacha": gacha.isoformat(),
        "davr_matn": f"{vaqt.sana_matn(dan, False)} — {vaqt.sana_matn(gacha, False)}",
        "hafta": {k: _p(joriy[k]) for k in ("sotuv", "xarajat", "kirim", "chiqim")},
        "oldingi_haftadan_farq": farq,
        "eng_katta_xarajatlar": [{"tur": t, "summa": _p(s)} for t, s in
                                 sorted(joriy["xarajat_turlar"].items(), key=lambda x: -x[1])[:3]],
        "ishlar": {"bajarilgan": bajarilgan, "kech_bajarilgan": kech_bajarilgan, "hozir_kechikkan": ochiq_kech},
        "vadalar": vs,
        "aniqlanmaganlar": {
            "tasdiqlanmagan": [{"tavsif": hisob.qisqa_tavsif(h), "sana": h["voqea_sana"]} for h in tasdiqsiz[:10]],
            "tasdiqlanmagan_soni": len(tasdiqsiz),
            "nizolar": [hisob.qisqa_tavsif(h) for h in nizolar[:10]],
            "ochiq_kartalar": [{"kim": k["ism"] or "?", "tur": json.loads(k["malumot"]).get("tur", "?"),
                                "sana": k["yaratilgan"][:10]} for k in kartalar[:10]],
            "ochiq_kartalar_soni": len(kartalar),
            "navbatdagi_xabarlar": navbat,
        },
    }


def _farq_matn(p: dict) -> str:
    s = p["summa"]
    return "o'zgarmadi" if not s else (f"+{p['korinish']}" if s > 0 else p["korinish"])


def hafta_qolip(f: dict) -> str:
    h, fq = f["hafta"], f["oldingi_haftadan_farq"]
    q = [f"Haftalik xulosa: {f['davr_matn']}.",
         f"Sotuv {h['sotuv']['korinish']} ({_farq_matn(fq['sotuv'])}), xarajat {h['xarajat']['korinish']} "
         f"({_farq_matn(fq['xarajat'])}).",
         f"Kassaga kirim {h['kirim']['korinish']}, chiqim {h['chiqim']['korinish']}."]
    i = f["ishlar"]
    q.append(f"Ishlar: {i['bajarilgan']} ta bajarildi ({i['kech_bajarilgan']} tasi kech), hozir {i['hozir_kechikkan']} ta "
             "kechikkan.")
    v = f["vadalar"]
    if sum(v.values()):
        q.append(f"Va'dalar: {v['vaqtida']} tasi vaqtida, {v['kech']} tasi kech, {v['qisman']} tasi qisman, "
                 f"{v['buzildi']} tasi buzildi.")
    a = f["aniqlanmaganlar"]
    qism = []
    if a["tasdiqlanmagan_soni"]:
        qism.append(f"{a['tasdiqlanmagan_soni']} ta yozuv 1 kundan beri tasdiqlanmagan")
    if a["nizolar"]:
        qism.append(f"{len(a['nizolar'])} ta nizo")
    if a["ochiq_kartalar_soni"]:
        qism.append(f"{a['ochiq_kartalar_soni']} ta kartochka yopilmay qolgan")
    if a["navbatdagi_xabarlar"]:
        qism.append(f"{a['navbatdagi_xabarlar']} ta xabar ishlanmay navbatda")
    q.append("Aniqlanmaganlar: " + ("; ".join(qism) if qism else "yo'q") + ".")
    return "\n".join(q)


# ---------- yasash va saqlash ----------

async def yasash(tur: str = "kun", majburan: bool = False) -> dict:
    """Xulosani yasaydi (bir kunga bittadan) — sun'iy intellekt matni raqam tekshiruvidan o'tsa o'sha, aks holda qolip."""
    sana = vaqt.bugun().isoformat()
    bor = baza.bir("SELECT * FROM xulosa WHERE tur=? AND sana=?", tur, sana)
    if bor and not majburan:
        return bor
    f = ertalab_faktlar() if tur == "kun" else hafta_faktlar()
    qolip_matn = ertalab_qolip(f) if tur == "kun" else hafta_qolip(f)
    matn_, qolip = qolip_matn, 1
    if ai.yoqilganmi():
        try:
            yozilgan = await ai.xulosa_yoz(f, tur)
            manba: list[float] = []
            ai._son_royxati(f, manba)
            manba += [abs(x) for x in manba]  # farq manfiy bo'lsa ham matnda «1,2 mln kam» deb yoziladi
            if yozilgan and ai.raqamlar_togri(yozilgan, manba):
                matn_, qolip = yozilgan, 0
        except ai.AiXato:
            pass
    baza.bajar("INSERT INTO xulosa(tur,sana,matn,qolip,faktlar,vaqt) VALUES(?,?,?,?,?,?) ON CONFLICT(tur,sana) DO UPDATE "
               "SET matn=excluded.matn, qolip=excluded.qolip, faktlar=excluded.faktlar, vaqt=excluded.vaqt",
               tur, sana, matn_, qolip, json.dumps(f, ensure_ascii=False, default=str), vaqt.iso())
    return baza.bir("SELECT * FROM xulosa WHERE tur=? AND sana=?", tur, sana)


def oxirgi(tur: str = "kun") -> dict | None:
    return baza.bir("SELECT * FROM xulosa WHERE tur=? ORDER BY sana DESC LIMIT 1", tur)


def kartalarni_eskirt() -> int:
    """7 kundan eski ochiq kartochka «eskirdi» — asl xabar qoladi (D-c)."""
    chegara = vaqt.iso(vaqt.hozir() - timedelta(days=7))
    n = baza.qiymat("SELECT COUNT(*) FROM karta WHERE holat='ochiq' AND yaratilgan<?", chegara) or 0
    if n:
        baza.bajar("UPDATE karta SET holat='eskirdi' WHERE holat='ochiq' AND yaratilgan<?", chegara)
    return n
