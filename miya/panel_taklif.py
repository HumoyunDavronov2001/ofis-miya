"""Panelning «miya» qatori: savol ham, topshiriq ham (bot bilan bir xil tushunish).

Sun'iy intellekt gapdan yozuv, ish, va'da, eslatma ajratadi; bu yerda ismlar dastur tomonidan topiladi va panel uchun
tayyor kartochkalar yasaladi. Hech narsa o'zi yozilmaydi — boshliq kartochkani ko'rib «Tasdiqlash» bosadi (K3).
"""
import re

from . import baza, buyurtma, hisob, ishlar, matn, odamlar, vaqt


def _odam(ism: str, o: dict) -> dict | None:
    ism = (ism or "").strip()
    if not ism:
        return None
    if ism.lower() in ("men", "o'zim", "ozim"):
        return {"id": o["id"], "ism": o["ism"]}
    variant = [(x["id"], x["ism"]) for x in odamlar.faol_odamlar() if x["holat"] == "faol"]
    mos = matn.mosla(ism, variant)
    bitta = matn.yagona(mos)
    if bitta:
        return {"id": bitta[0], "ism": bitta[1]}
    if len(mos) == 1:  # yagona o'xshash («Dilshot» → Dilshod) — tanlanadi, kartochkada «to'g'rimi?» deyiladi
        return {"id": mos[0][0], "ism": mos[0][1], "aytilgan": ism, "taxmin": True}
    return {"aytilgan": ism, "nomzodlar": [{"id": i, "ism": n} for i, n, _ in mos[:5]]}


def _pul_odam(y: dict, tur: str, o: dict) -> dict | None:
    """Bot bilan bir xil: xodim «oldim», «o'z pulimdan» desa — ism aytilmasa ham yozgan odamning o'zi."""
    if not (y.get("odam") or "").strip() and o["rol"] in ("xodim", "menejer") and tur in (
            "avans", "maosh_tolov", "qolga_berish", "qoldan_qaytarish", "mijozdan_qolga", "chiqim"):
        return {"id": o["id"], "ism": o["ism"]}
    return _odam(y.get("odam"), o)


def _mijoz(ism: str, tur: str = "mijoz") -> dict | None:
    ism = (ism or "").strip()
    if not ism:
        return None
    variant = [(r["id"], r["ism"]) for r in baza.hammasi("SELECT id, ism FROM mijoz WHERE tur=? AND birlashdi IS NULL", tur)]
    mos = matn.mosla(ism, variant)
    bitta = matn.yagona(mos)
    if bitta:
        return {"id": bitta[0], "ism": bitta[1]}
    yangi = ism[:1].upper() + ism[1:]
    if len(mos) == 1:  # «Sobir» → Botir Sobirov: tanlanadi, lekin «to'g'rimi?» va «+ Yangi» ham ko'rinadi
        return {"id": mos[0][0], "ism": mos[0][1], "aytilgan": ism, "taxmin": True, "yangi": yangi}
    return {"aytilgan": ism, "nomzodlar": [{"id": i, "ism": n} for i, n, _ in mos[:5]], "yangi": yangi}


def _sana(s: str) -> str | None:
    s = (s or "")[:10]
    return s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else None


def _kassa(nom: str, o: dict, valyuta: str | None) -> int | None:
    korish = {**o, "rol": "boshliq"} if o["holat"] == "faol" else o  # R3 (ai.umumiy_korish bilan bir xil)
    kassalar = [k for k in hisob.kassalar() if odamlar.hisob_korishi_mumkin(korish, f"kassa:{k['id']}")]
    if nom:
        mos = matn.yagona(matn.mosla(nom, [(k["id"], k["nom"]) for k in kassalar], 0.6))
        if mos:
            return mos[0]
    if o.get("kassa_id") and any(k["id"] == o["kassa_id"] and (not valyuta or k["valyuta"] == valyuta) for k in kassalar):
        return o["kassa_id"]
    ozi = [k for k in kassalar if k["masul_id"] == o["id"] and (not valyuta or k["valyuta"] == valyuta)]
    if len(ozi) == 1:
        return ozi[0]["id"]
    mos_v = sorted([k for k in kassalar if not valyuta or k["valyuta"] == valyuta],
                   key=lambda k: k["tur"] == "chontak")  # boshliqning cho'ntagi — oxirgi tanlov
    return mos_v[0]["id"] if mos_v else None


def _bir_mijoz(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    if a.get("id") or b.get("id"):
        return a.get("id") == b.get("id")
    return matn.norm(a.get("aytilgan") or "") == matn.norm(b.get("aytilgan") or "")


def _tugadi(y: dict, o: dict) -> dict:
    """«Eshik ishi tugadi» — qaysi ish: id (o'z ishlari promptda) yoki nomi bo'yicha ochiq ishlardan dastur topadi."""
    ochiq = ishlar.ishlar(korish=o, faqat_ochiq=True, limit=100)
    ish_ = next((i for i in ochiq if i["id"] == y.get("ish_id")), None)
    nomzod = []
    if not ish_:
        mos = matn.mosla(y.get("nom") or y.get("iqtibos") or "", [(i["id"], i["nom"]) for i in ochiq], 0.5)
        bitta = matn.yagona(mos)
        if bitta:
            ish_ = next(i for i in ochiq if i["id"] == bitta[0])
        else:
            nomzod = [m_[0] for m_ in mos[:5]]
    return {"tur": "bajarildi", "ish_id": ish_["id"] if ish_ else None, "aytilgan": y.get("nom") or "",
            "nomzodlar": nomzod, "ochiq": [{"id": i["id"], "nom": i["nom"],
                                            "ijrochilar": ", ".join(x["ism"] for x in i.get("ijrochilar") or [])}
                                           for i in ochiq[:30]],
            "izoh": y.get("izoh") or "", "iqtibos": y.get("iqtibos") or "", "ruxsat": ishlar.tolov_huquqi(o)}


def buyurtma_karta(y: dict) -> dict | None:
    """CRM7: gapdagi buyurtma → kartochka. Qator nomini katalogdan DASTUR topadi; narx — gapda aytilgan bo'lsa o'sha,
    aks holda katalogdan; topilmasa — erkin qator. Narxlar asosiy birlikda (so'm yoki dollar), jami — minor."""
    qatorlar = []
    for q in (y.get("qatorlar") or [])[:20]:
        nom = (q.get("nom") or "").strip()[:200]
        if not nom:
            continue
        k, nomzod = buyurtma.katalog_top(nom)
        qatorlar.append({"katalog_id": k["id"] if k else None, "nom": k["nom"] if k else nom[:1].upper() + nom[1:],
                         "aytilgan": nom, "birlik": k["birlik"] if k else "dona", "miqdor": max(0.0, float(q.get("miqdor") or 0)),
                         "_narx": max(0.0, float(q.get("narx") or 0)), "_k": k,
                         "nomzodlar": [{"id": x["id"], "nom": x["nom"]} for x in nomzod]})
    if not qatorlar:
        return None
    v = next((x["_k"]["valyuta"] for x in qatorlar if x["_k"]), "UZS")  # bitta buyurtma — bitta valyuta
    mahsulot = [x for x in qatorlar if x["_k"] and x["_k"]["tur"] == "mahsulot" and x["miqdor"] > 0]
    for x in qatorlar:
        k, aytilgan = x.pop("_k"), x.pop("_narx")
        if not x["miqdor"]:  # «o'rnatish bilan» — xizmat soni aytilmasa, yagona mahsulot soniga teng (har biriga)
            x["miqdor"] = mahsulot[0]["miqdor"] if k and k["tur"] == "xizmat" and len(mahsulot) == 1 else 1
        x["narx"] = aytilgan if aytilgan else ((k["narx"] / 100 if v == "USD" else k["narx"]) if k and k["valyuta"] == v else 0)
    jami = sum(round(x["miqdor"] * matn.minor(x["narx"], v)) for x in qatorlar)
    return {"tur": "buyurtma", "mijoz": _mijoz(y.get("mijoz")), "qatorlar": qatorlar, "valyuta": v, "jami": jami,
            "jami_t": matn.pul(jami, v), "manzil": (y.get("manzil") or "").strip()[:300], "muddat": _sana(y.get("muddat")),
            "izoh": (y.get("izoh") or "").strip()[:300], "iqtibos": y.get("iqtibos") or ""}


def yasash(natija: dict, o: dict) -> list[dict]:
    """tushun() natijasi → panel kartochkalari."""
    k = []
    for y in (natija.get("yozuvlar") or [])[:5]:
        tur = y.get("tur")
        if tur not in hisob.SHABLON or tur in ("tuzatish", "hisoblandi"):
            continue
        v = y.get("valyuta") if y.get("valyuta") in ("UZS", "USD") else None
        tamin = tur in ("taminotchi_nasiya", "taminotchiga_tolov", "boshlangich_taminotchi")
        k.append({"tur": "pul", "harakat_tur": tur, "nom": hisob.SHABLON[tur][0], "summa": y.get("summa") or 0,
                  "birlik_noaniq": bool(y.get("birlik_noaniq")), "valyuta": v or "UZS",
                  "odam": _pul_odam(y, tur, o) if (tur in hisob.ODAM_KERAK or y.get("qoldan")) else None,
                  "mijoz": _mijoz(y.get("mijoz"), "taminotchi" if tamin else "mijoz"),
                  "mijoz_turi": "taminotchi" if tamin else "mijoz",
                  "kassa_id": _kassa(y.get("kassa"), o, v) if tur not in ("sotuv", "taminotchi_nasiya") or y.get("tolandi")
                  else None,
                  "xarajat_turi": y.get("xarajat_turi") or ("Boshqa" if tur == "chiqim" else ""),
                  "sana": _sana(y.get("sana")) or vaqt.bugun().isoformat(), "tolandi": y.get("tolandi") or 0,
                  "muddat": _sana(y.get("muddat")), "qoldan": bool(y.get("qoldan")), "izoh": y.get("izoh") or "",
                  "iqtibos": y.get("iqtibos") or "", "ruxsat": hisob.yozishi_mumkin(o, tur)})
    for y in (natija.get("ishlar") or [])[:5]:
        if not (y.get("nom") or "").strip():
            continue
        ijr, nomalum = [], []
        for ism in y.get("ijrochilar") or []:
            r = _odam(ism, o)
            if r and r.get("id"):
                ijr.append(r)
            elif r:
                nomalum.append(r)
        narx_v = y.get("valyuta") if y.get("valyuta") in ("UZS", "USD") else "UZS"
        k.append({"tur": "ish", "nom": y["nom"].strip()[:200], "ijrochilar": ijr, "nomalum": nomalum,
                  "mijoz": _mijoz(y.get("mijoz")), "joy": y.get("joy") or "", "muddat": _sana(y.get("muddat")),
                  "soat": y.get("soat") if re.fullmatch(r"\d{1,2}:\d{2}", y.get("soat") or "") else "",
                  "narx": y.get("narx") or 0, "valyuta": narx_v, "ish_turi": (y.get("ish_turi") or "").lower(),
                  "dalil": y.get("dalil") if y.get("dalil") in ishlar.DALIL_NOMI else baza.sozlama("dalil_standart", "rasm"),
                  "taklif": ishlar.ijrochi_taklif(y.get("ish_turi"))[:8], "iqtibos": y.get("iqtibos") or "",
                  "ruxsat": ishlar.tolov_huquqi(o)})
    for y in (natija.get("vadalar") or [])[:5]:
        summa = y.get("summa") or 0
        vtur = y.get("tur") if y.get("tur") in ("tolov", "boshqa") else ("tolov" if summa else "boshqa")
        k.append({"tur": "vada", "mijoz": _mijoz(y.get("mijoz")), "kim": y.get("kim") if y.get("kim") in ("mijoz", "biz")
                  else "mijoz", "vtur": vtur, "summa": summa, "birlik_noaniq": bool(y.get("birlik_noaniq")),
                  "valyuta": y.get("valyuta") if y.get("valyuta") in ("UZS", "USD") else "UZS",
                  "muddat": _sana(y.get("muddat")), "matn": y.get("matn") or "", "iqtibos": y.get("iqtibos") or ""})
    # «qolganini juma beradi»: va'da summasi aytilmagan — dastur qarzdan hisoblaydi (shu xabardagi to'lov ayirilib)
    for v in k:
        if v["tur"] == "vada" and v["vtur"] == "tolov" and not v["summa"] and v["mijoz"] and v["mijoz"].get("id"):
            mid = v["mijoz"]["id"]
            qarz = hisob.qoldiq(f"mijoz:{mid}").get(v["valyuta"], 0)
            tolov = sum(matn.minor(x["summa"], x["valyuta"]) for x in k if x["tur"] == "pul" and x["harakat_tur"] == "kirim"
                        and x["mijoz"] and x["mijoz"].get("id") == mid and x["valyuta"] == v["valyuta"])
            qolgan = qarz - tolov
            if qolgan > 0:
                v["summa"] = qolgan / 100 if v["valyuta"] == "USD" else qolgan
                v["izoh"] = "qolgan qarzidan hisoblandi"
    # sotuvning qarz muddati — sotuvning o'zida (faollashganda va'da o'zi yoziladi); alohida va'da kartochkasi takror bo'lardi
    for v in [x for x in k if x["tur"] == "vada" and x["vtur"] == "tolov" and x["kim"] == "mijoz"]:
        s_ = next((x for x in k if x["tur"] == "pul" and x["harakat_tur"] == "sotuv" and _bir_mijoz(x["mijoz"], v["mijoz"])),
                  None)
        if s_:
            s_["muddat"] = s_["muddat"] or v["muddat"]
            k.remove(v)
    for y in (natija.get("bajarildi") or [])[:5]:
        k.append(_tugadi(y, o))
    for y in (natija.get("buyurtmalar") or [])[:3]:
        c = buyurtma_karta(y)
        if c:
            k.append(c)
    for y in (natija.get("mijoz_eslatmalar") or [])[:5]:
        if (y.get("matn") or "").strip():
            k.append({"tur": "eslatma", "mijoz": _mijoz(y.get("mijoz")), "matn": y["matn"].strip()[:300],
                      "iqtibos": y.get("iqtibos") or ""})
    return k
