"""Xodim ketganda topshirish varaqasi (O4, D-e).

Varaq o'zi yig'iladi; ish, mijoz, va'da va kassa bir tugma bilan boshqa odamga o'tadi. Kirish yopilishi —
hammasi nolga tushganda; aks holda boshliq sababini yozadi (jurnalga).
"""
from . import baza, hisob, ishlar, maosh, matn, odamlar, vadalar, vaqt


class TopshirishXato(Exception):
    pass


def varaq(odam_id: int) -> dict:
    o = odamlar.odam(odam_id)
    if not o:
        raise TopshirishXato("Xodim topilmadi")
    ochiq_ishlar = ishlar.ishlar(odam_id=odam_id, faqat_ochiq=True)
    qolida = {v: s for v, s in hisob.qoldiq(f"qol:{odam_id}").items() if s}
    qarzi = {v: s for v, s in hisob.qoldiq(f"xqarz:{odam_id}").items() if s}
    kassalar = []
    for k in hisob.kassa_holati():
        if k["masul_id"] == odam_id:
            kassalar.append({"id": k["id"], "nom": k["nom"], "valyuta": k["valyuta"], "qoldiq": k["qoldiq"]})
    mijozlar_ = baza.hammasi("SELECT id, ism FROM mijoz WHERE masul_id=? AND birlashdi IS NULL ORDER BY ism", odam_id)
    vadalar_ = [v for v in vadalar.royxat(masul_id=odam_id) if v["holat"] == "ochiq" and v["holat_h"] not in ("vaqtida", "kech")]
    kutmoqda = baza.hammasi("SELECT * FROM harakat WHERE holat IN ('faol','nizo') AND ((beruvchi_id=? AND "
                            "beruvchi_holat='kutilmoqda') OR (oluvchi_id=? AND oluvchi_holat='kutilmoqda'))", odam_id, odam_id)
    v = maosh.varaq(odam_id)
    tayyor = not (ochiq_ishlar or qolida or qarzi or kassalar or mijozlar_ or vadalar_ or kutmoqda or v["qolgani"])
    return {"odam": {"id": o["id"], "ism": o["ism"], "holat": o["holat"], "rol": o["rol"]},
            "ishlar": [{"id": i["id"], "qisqa": ishlar.qisqa(i)} for i in ochiq_ishlar],
            "qolida": [{"summa": s, "valyuta": val, "matn": matn.pul(s, val)} for val, s in qolida.items()],
            "qarzi": [{"summa": s, "valyuta": val, "matn": matn.pul(s, val)} for val, s in qarzi.items()],
            "kassalar": kassalar, "mijozlar": mijozlar_,
            "vadalar": [{"id": x["id"], "mijoz": x["mijoz"], "muddat": x["muddat"],
                         "matn": matn.pul(x["summa"], x["valyuta"]) if x["tur"] == "tolov" else x["matn"]} for x in vadalar_],
            "kutmoqda": [{"id": h["id"], "tavsif": hisob.qisqa_tavsif(h)} for h in kutmoqda],
            "maosh_qolgani": {"summa": v["qolgani"], "valyuta": v["valyuta"], "matn": matn.pul(v["qolgani"], v["valyuta"])},
            "tayyor": tayyor}


def otkaz(odam_id: int, kimga_id: int, kim_id: int, nimalar: set[str] | None = None) -> dict:
    """Ish, mijoz, va'da, kassa — boshqa odamga. Qaytaradi: nechtasi o'tdi."""
    nimalar = nimalar or {"ishlar", "mijozlar", "vadalar", "kassalar"}
    kimga = odamlar.odam(kimga_id)
    if not kimga or kimga["holat"] != "faol" or kimga_id == odam_id:
        raise TopshirishXato("Qabul qiluvchi faol xodim bo'lsin")
    natija = {"ishlar": 0, "mijozlar": 0, "vadalar": 0, "kassalar": 0}
    with baza.tranz():
        if "ishlar" in nimalar:
            for i in ishlar.ishlar(odam_id=odam_id, faqat_ochiq=True):
                if any(x["odam_id"] == kimga_id for x in i["ijrochilar"]):
                    baza.bajar("DELETE FROM ish_ijrochi WHERE ish_id=? AND odam_id=?", i["id"], odam_id)
                else:
                    baza.bajar("UPDATE ish_ijrochi SET odam_id=?, korildi=NULL WHERE ish_id=? AND odam_id=?", kimga_id,
                               i["id"], odam_id)
                natija["ishlar"] += 1
        if "mijozlar" in nimalar:
            natija["mijozlar"] = baza.qiymat("SELECT COUNT(*) FROM mijoz WHERE masul_id=?", odam_id) or 0
            baza.bajar("UPDATE mijoz SET masul_id=? WHERE masul_id=?", kimga_id, odam_id)
        if "vadalar" in nimalar:
            natija["vadalar"] = baza.qiymat("SELECT COUNT(*) FROM vada WHERE masul_id=? AND holat='ochiq'", odam_id) or 0
            baza.bajar("UPDATE vada SET masul_id=? WHERE masul_id=? AND holat='ochiq'", kimga_id, odam_id)
        if "kassalar" in nimalar:
            for k in baza.hammasi("SELECT id FROM kassa WHERE masul_id=?", odam_id):
                kal = f"kassa:{k['id']}"
                baza.bajar("UPDATE kassa SET masul_id=? WHERE id=?", kimga_id, k["id"])
                # tasdiq kutayotgan kassa yozuvlari yangi mas'ulga o'tadi — eskisi endi «berdim/oldim» demaydi
                baza.bajar("UPDATE harakat SET beruvchi_id=? WHERE dan=? AND beruvchi_id=? AND beruvchi_holat='kutilmoqda'",
                           kimga_id, kal, odam_id)
                baza.bajar("UPDATE harakat SET oluvchi_id=? WHERE ga=? AND oluvchi_id=? AND oluvchi_holat='kutilmoqda'",
                           kimga_id, kal, odam_id)
                natija["kassalar"] += 1
        baza.jurnal(kim_id, "topshirildi", f"odam:{odam_id}", None, {"kimga": kimga_id, **natija})
        jami = [f"{n} ta {s}" for s, n in (("ish", natija["ishlar"]), ("mijoz", natija["mijozlar"]),
                                          ("va'da", natija["vadalar"]), ("kassa", natija["kassalar"])) if n]
        if jami:
            ketuvchi = odamlar.odam(odam_id)
            hisob.xabarnoma(kimga_id, "malumot", f"{ketuvchi['ism'] if ketuvchi else 'Xodim'}dan sizga o'tdi: "
                                                 + ", ".join(jami) + ". Panelda yoki «Ishlarim»da ko'ring.")
    return natija


def yopish(odam_id: int, kim_id: int, sabab: str | None = None) -> dict:
    """Kirish yopiladi (ketgan). Varaq to'liq bo'lmasa — faqat sabab bilan."""
    v = varaq(odam_id)
    if not v["tayyor"] and not (sabab or "").strip():
        raise TopshirishXato("Topshirish tugamagan — ish, pul yoki maosh qoldig'i bor. Baribir yopish uchun sababini yozing")
    with baza.tranz():
        odamlar.holat_qoy(odam_id, "ketgan", kim_id)
        if not v["tayyor"]:
            baza.jurnal(kim_id, "topshirishsiz_yopildi", f"odam:{odam_id}", None, (sabab or "").strip()[:300])
    return v
