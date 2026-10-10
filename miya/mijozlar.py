"""Mijozlar (C1, C2, C5, C6): karta, tarix, eslatmalar, uxlab qolgan mijozlar, qo'ng'iroqdan oldingi 3 qator."""
from datetime import date

from . import baza, hisob, ishlar, kurs, matn, odamlar, vadalar, vaqt


class MijozXato(Exception):
    pass


def mijoz(mid: int) -> dict | None:
    return baza.bir("SELECT * FROM mijoz WHERE id=?", mid)


def korishi_mumkin(o: dict | None, m: dict) -> bool:
    """C-g: xodim faqat o'zi mas'ul bo'lgan mijozni ko'radi."""
    if not o or o["holat"] != "faol":
        return False
    if o["rol"] in ("boshliq", "menejer", "kassir"):
        return True
    return m.get("masul_id") == o["id"]


def tahrir(mid: int, kim_id: int, **maydon) -> None:
    ruxsat = {"ism", "telefon", "telefon2", "manzil", "masul_id", "izoh", "arxiv"}  # arxiv — ro'yxatdan olinadi, o'chmaydi
    eski = mijoz(mid)
    if not eski:
        raise MijozXato("Mijoz topilmadi")
    ozgar = {k: (v if v != "" else None) for k, v in maydon.items() if k in ruxsat}
    if "arxiv" in ozgar:
        ozgar["arxiv"] = 1 if ozgar["arxiv"] else 0
    if "ism" in ozgar and not (ozgar["ism"] or "").strip():
        raise MijozXato("Ism bo'sh bo'lmasin")
    if not ozgar:
        return
    with baza.tranz():
        baza.bajar("UPDATE mijoz SET %s WHERE id=?" % ",".join(f"{k}=?" for k in ozgar), *ozgar.values(), mid)
        baza.jurnal(kim_id, "mijoz_tahrir", f"mijoz:{mid}", {k: eski.get(k) for k in ozgar}, ozgar)


# ---------- eslatmalar (C1, C-e) ----------

def eslatma_qosh(mid: int, matn_: str, yozgan_id: int | None, xabar_id: int | None = None, manba: str = "aytilgan") -> int:
    matn_ = (matn_ or "").strip()
    if not matn_:
        raise MijozXato("Eslatma bo'sh")
    eid = baza.bajar("INSERT INTO mijoz_eslatma(mijoz_id,matn,manba,xabar_id,yozgan_id,vaqt) VALUES(?,?,?,?,?,?)",
                     mid, matn_[:500], manba, xabar_id, yozgan_id, vaqt.iso())
    baza.jurnal(yozgan_id, "mijoz_eslatma", f"mijoz:{mid}", None, matn_[:200])
    return eid


def eslatma_bekor(eid: int, kim_id: int) -> None:
    baza.bajar("UPDATE mijoz_eslatma SET bekor=1 WHERE id=?", eid)
    baza.jurnal(kim_id, "mijoz_eslatma_bekor", f"eslatma:{eid}")


def eslatmalar(mid: int) -> list[dict]:
    return baza.hammasi("SELECT e.*, o.ism yozgan FROM mijoz_eslatma e LEFT JOIN odam o ON o.id=e.yozgan_id "
                        "WHERE e.mijoz_id=? AND e.bekor=0 ORDER BY e.id DESC", mid)


# ---------- xaridlar va uxlab qolganlar (C5, C-f) ----------

def xaridlar(mid: int) -> list[dict]:
    return baza.hammasi("SELECT * FROM harakat WHERE tur='sotuv' AND mijoz_id=? AND holat IN ('faol','nizo') "
                        "ORDER BY voqea_sana", mid)


def uxlash(mid: int) -> dict | None:
    """Kamida 3 ta xarid: o'rtacha oraliqdan 2 baravar uzoq kelmasa — uxlab qolgan."""
    x = xaridlar(mid)
    sanalar = sorted({r["voqea_sana"] for r in x})
    if len(sanalar) < 3:
        return None
    kunlar = [(date.fromisoformat(b) - date.fromisoformat(a)).days for a, b in zip(sanalar, sanalar[1:])]
    ortacha = sum(kunlar) / len(kunlar)
    otdi = (vaqt.bugun() - date.fromisoformat(sanalar[-1])).days
    ortacha_summa = sum(kurs.somga(r["summa"], r["valyuta"], r["voqea_sana"]) or 0 for r in x) // len(x)
    return {"ortacha_kun": round(ortacha, 1), "otdi_kun": otdi, "oxirgi": sanalar[-1], "uxlagan": otdi > 2 * max(ortacha, 1),
            "ortacha_summa": ortacha_summa, "xarid_soni": len(x)}


def uxlab_qolganlar() -> list[dict]:
    natija = []
    for m in baza.hammasi("SELECT * FROM mijoz WHERE tur='mijoz' AND birlashdi IS NULL"):
        u = uxlash(m["id"])
        if u and u["uxlagan"]:
            natija.append({**m, **u})
    natija.sort(key=lambda x: -x["ortacha_summa"])
    return natija


# ---------- karta va 3 qator (C1, C6) ----------

def qisqa_malumot(mid: int) -> list[str]:
    """Qo'ng'iroqdan oldin 3 qator: oxirgi xarid, qarzi, ochiq va'dasi, eslatma (C6)."""
    m = mijoz(mid)
    q = []
    x = xaridlar(mid)
    if x:
        r = x[-1]
        q.append(f"Oxirgi xarid: {vaqt.sana_matn(r['voqea_sana'], False)} — {matn.pul(r['summa'], r['valyuta'])}"
                 + (f" ({r['izoh']})" if r["izoh"] else ""))
    else:
        q.append("Xarid yozilmagan")
    qarz = {v: s for v, s in hisob.qoldiq(f"mijoz:{mid}").items() if s > 0}
    ish_ = vadalar.ishonch(mid)
    q.append(("Qarzi: " + ", ".join(matn.pul(s, v) for v, s in qarz.items()) if qarz else "Qarzi yo'q")
             + f" · {ish_['matn']}")
    hammasi = vadalar.royxat(mid)
    buzilgan = [v for v in hammasi if v["kim"] == "mijoz" and v["holat"] == "ochiq" and v["holat_h"] in ("buzildi", "qisman")]
    ochiq = sorted([v for v in hammasi if v["holat_h"] == "ochiq"], key=lambda v: (v["kim"] != "mijoz", v["muddat"]))
    esl = eslatmalar(mid)
    if buzilgan:  # qo'ng'iroqda eng kerakli gap — bajarilmagan va'da
        v = buzilgan[0]
        q.append(f"Va'dasini bajarmadi: {_vada_matn(v).replace(' gacha', ' edi')}")
    elif ochiq:
        v = ochiq[0]
        q.append(("Va'dasi: " if v["kim"] == "mijoz" else "Bizning va'damiz: ") + _vada_matn(v))
    elif esl:
        q.append(f"Eslatma: {esl[0]['matn']}")
    elif m and m.get("izoh"):
        q.append(f"Izoh: {m['izoh']}")
    return q


def _vada_matn(v: dict) -> str:
    if v["tur"] == "tolov":
        s = matn.pul(v["qolgan"] if v.get("qolgan") is not None else v["summa"], v["valyuta"])
        return f"{s} — {vaqt.sana_matn(v['muddat'], False)} gacha"
    return f"{v['matn']} — {vaqt.sana_matn(v['muddat'], False)} gacha"


def karta(mid: int) -> dict:
    m = mijoz(mid)
    if not m:
        raise MijozXato("Mijoz topilmadi")
    masul = odamlar.odam(m.get("masul_id"))
    return {"mijoz": m, "masul": masul["ism"] if masul else None,
            "qarz": {v: s for v, s in hisob.qoldiq(f"{m['tur']}:{mid}").items() if s},
            "ishonch": vadalar.ishonch(mid), "uxlash": uxlash(mid), "qisqa": qisqa_malumot(mid),
            "vadalar": vadalar.royxat(mid), "eslatmalar": eslatmalar(mid)}


def tarix(mid: int, limit: int = 200) -> list[dict]:
    """C2: hamma narsa vaqt bo'yicha — asl xabarga havola bilan."""
    t = baza.bir("SELECT tur FROM mijoz WHERE id=?", mid)
    kalit = f"{(t or {}).get('tur', 'mijoz')}:{mid}"
    natija = []
    for h in baza.hammasi("SELECT * FROM harakat WHERE (dan=? OR ga=? OR mijoz_id=?) AND holat!='taklif' ORDER BY id DESC "
                          "LIMIT ?", kalit, kalit, mid, limit):
        natija.append({"vaqt": h["voqea_sana"], "tur": "pul", "matn": hisob.qisqa_tavsif(h), "holat": h["holat"],
                       "xabar_id": h["xabar_id"], "harakat_id": h["id"]})
    for v in vadalar.royxat(mid):
        natija.append({"vaqt": v["yozilgan"][:10], "tur": "vada", "matn": f"Va'da: {_vada_matn(v)}",
                       "holat": vadalar.HOLAT_NOMI.get(v["holat_h"], v["holat_h"]), "xabar_id": v["xabar_id"],
                       "vada_id": v["id"]})
    for e in eslatmalar(mid):
        natija.append({"vaqt": e["vaqt"][:10], "tur": "eslatma", "matn": e["matn"], "holat": e["manba"],
                       "xabar_id": e["xabar_id"]})
    for i in baza.hammasi("SELECT * FROM ish WHERE mijoz_id=? ORDER BY id DESC LIMIT 100", mid):
        natija.append({"vaqt": (i["muddat"] or i["yaratilgan"])[:10], "tur": "ish", "matn": f"Ish: {i['nom']}",
                       "holat": ishlar.HOLAT_NOMI[i["holat"]], "xabar_id": i["xabar_id"], "ish_id": i["id"]})
    natija.sort(key=lambda x: x["vaqt"], reverse=True)
    return natija[:limit]
