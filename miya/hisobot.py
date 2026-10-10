"""CRM3: hisobotlar — davr bo'yicha. Hamma raqamni dastur hisoblaydi (so'mda; dollar shu kundagi kurs bilan).

Foyda-zarar: sotuv − xarajat − ish haqi (yozilgani). Boshlang'ich qoldiq va egasining o'z puli daromad ham, xarajat
ham emas (P2). Oylik maosh oy yopilganda yoziladi — shu sabab joriy oyda ish haqi to'liq emas (hisobotda aytiladi).
"""
from datetime import date, timedelta

from . import baza, buyurtma, hisob, kurs, maosh, odamlar, vaqt

YOSH = (("muddati_kelmagan", "Muddati kelmagan"), ("1_30", "1–30 kun o'tgan"), ("31_60", "31–60 kun"),
        ("61_90", "61–90 kun"), ("90_plus", "90 kundan ko'p"), ("muddatsiz", "Muddati yozilmagan"))


def _som(r: dict) -> int:
    return kurs.somga(r["summa"], r["valyuta"], r["hisob_sana"]) or 0


def _yosh(muddat: str | None, bugun: date) -> str:
    if not muddat:
        return "muddatsiz"
    kun = (bugun - date.fromisoformat(muddat[:10])).days
    if kun <= 0:
        return "muddati_kelmagan"
    return "1_30" if kun <= 30 else "31_60" if kun <= 60 else "61_90" if kun <= 90 else "90_plus"


def davr(dan: str, gacha: str) -> dict:
    dan, gacha = dan[:10], gacha[:10]
    date.fromisoformat(dan), date.fromisoformat(gacha)
    if dan > gacha:
        raise ValueError("Sana oralig'i noto'g'ri")
    j = hisob.davr_jami(dan, gacha)
    qatorlar = baza.hammasi("SELECT * FROM harakat WHERE holat IN ('faol','nizo') AND hisob_sana BETWEEN ? AND ?", dan, gacha)

    # sotuv — mijoz va sotuvchi bo'yicha
    mijoz_s: dict[int | None, dict] = {}
    sotuvchi_s: dict[int | None, dict] = {}
    for r in qatorlar:
        if r["dan"] != "sotuv":
            continue
        for d, k in ((mijoz_s, r["mijoz_id"]), (sotuvchi_s, r["sotuvchi_id"])):
            x = d.setdefault(k, {"summa": 0, "soni": 0})
            x["summa"] += _som(r)
            x["soni"] += 1
    nomlar = {m["id"]: m["ism"] for m in baza.hammasi("SELECT id, ism FROM mijoz")}
    mijoz_r = sorted(({"id": k, "ism": nomlar.get(k, "Mijozsiz"), **v} for k, v in mijoz_s.items()),
                     key=lambda x: -x["summa"])
    sotuvchi_r = sorted(({"id": k, "ism": (odamlar.odam(k) or {}).get("ism", "Ko'rsatilmagan") if k else "Ko'rsatilmagan", **v}
                         for k, v in sotuvchi_s.items()), key=lambda x: -x["summa"])

    # xarajat turlari — ulushi bilan
    xj = j["xarajat"] or 0
    xarajat_r = sorted(({"nom": k, "summa": v, "ulush": round(v * 100 / xj) if xj else 0}
                        for k, v in j["xarajat_turlar"].items() if v), key=lambda x: -x["summa"])

    # kassa aylanmasi
    oldin = (date.fromisoformat(dan) - timedelta(days=1)).isoformat()
    kassa_r = []
    for k in hisob.kassalar():
        kal = f"kassa:{k['id']}"
        kir = sum((r["summa2"] or r["summa"]) for r in qatorlar if r["ga"] == kal and r["oluvchi_holat"] in ("kerak_emas", "tasdiq"))
        chiq = sum(r["summa"] for r in qatorlar if r["dan"] == kal and r["beruvchi_holat"] in ("kerak_emas", "tasdiq"))
        kassa_r.append({"id": k["id"], "nom": k["nom"], "valyuta": k["valyuta"],
                        "boshida": hisob.qoldiq_bir(kal, k["valyuta"], oldin), "kirim": kir, "chiqim": chiq,
                        "oxirida": hisob.qoldiq_bir(kal, k["valyuta"], gacha)})

    # qarzlar yoshi (bugungi holat bo'yicha — davrga bog'liq emas)
    bugun = vaqt.bugun()
    yosh = {k: {"summa": 0, "soni": 0, "mijozlar": []} for k, _ in YOSH}
    for q in hisob.mijoz_qarzlari("mijoz"):
        s = sum(kurs.somga(v_s, v) or 0 for v, v_s in q["qarz"].items() if v_s > 0)
        if s <= 0:
            continue
        b = yosh[_yosh(q["muddat"], bugun)]
        b["summa"] += s
        b["soni"] += 1
        b["mijozlar"].append({"id": q["id"], "ism": q["ism"], "summa": s, "muddat": q["muddat"]})
    for b in yosh.values():
        b["mijozlar"].sort(key=lambda x: -x["summa"])

    joriy_oy = vaqt.oy(bugun)
    return {"dan": dan, "gacha": gacha,
            "foyda": {"sotuv": j["sotuv"], "xarajat": j["xarajat"], "ishhaqi": j["ishhaqi_yozilgan"],
                      "foyda": j["sotuv"] - j["xarajat"] - j["ishhaqi_yozilgan"],
                      "kassa_kirim": j["kassa_kirim"], "kassa_chiqim": j["kassa_chiqim"],
                      # davrda maoshi hali «hisoblandi» bo'lmagan (yopilmagan) oy bor — ish haqi to'liq emas
                      "oy_yopilmagan": any(not hisob.oy_yopiqmi(o) for o in vaqt.oylar_oraligi(dan[:7], min(gacha[:7], joriy_oy))
                                           if o >= maosh.boshlangan_oy())},
            "xarajat_turlar": xarajat_r, "sotuv_mijoz": mijoz_r, "sotuv_sotuvchi": sotuvchi_r, "kassalar": kassa_r,
            "sotuv_mahsulot": buyurtma.mahsulot_sotuvi(dan, gacha),
            "qarz_yoshi": [{"kalit": k, "nom": n, **yosh[k]} for k, n in YOSH]}
