"""CRM4: umumiy qidiruv — mijozlar, buyurtmalar, ishlar, pul yozuvlari, xotira, xabarlar bitta qatordan.

O'zbekcha: kirill/lotin bir xil, qo'shimchali so'z ildizi bilan («Karimovga» → «karimov»), telefon — raqamlari bo'yicha.
Hamma so'z topilishi kerak (VA). Natija har guruhda eng ko'pi 8 ta.
"""
import re

from . import arxiv, baza, buyurtma, hisob, ishlar, qidiruv, xotira

GURUH_SONI = 8


def _raqam(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _mos(matn_: str, ildlar: list[str]) -> bool:
    toklar = qidiruv.tokenlar(matn_)
    return bool(ildlar) and all(any(qidiruv.mos(t, i) for t in toklar) for i in ildlar)


def izla(sorov: str, o: dict) -> dict:
    sorov = (sorov or "").strip()[:100]
    ildlar = qidiruv.ildizlar(sorov) or [qidiruv.ildiz(t) for t in qidiruv.tokenlar(sorov) if len(t) >= 2]
    raqam = _raqam(sorov) if len(_raqam(sorov)) >= 4 else ""
    bosh = {"mijozlar": [], "buyurtmalar": [], "ishlar": [], "yozuvlar": [], "xotira": [], "xabarlar": []}
    if not ildlar and not raqam:
        return bosh

    for m in baza.hammasi("SELECT * FROM mijoz WHERE birlashdi IS NULL ORDER BY arxiv, ism"):
        if (raqam and (raqam in _raqam(m["telefon"]) or raqam in _raqam(m["telefon2"]))) or \
                _mos(f"{m['ism']} {m['manzil'] or ''} {m['izoh'] or ''}", ildlar):
            bosh["mijozlar"].append(m)
            if len(bosh["mijozlar"]) >= GURUH_SONI:
                break

    raqam_id = int(_raqam(sorov)) if sorov.lstrip("#").isdigit() else None  # «#12» — raqam bo'yicha
    for b in buyurtma.royxat(limit=300):
        matn_ = f"{b['mijoz']} {' '.join(q['nom'] for q in b['qatorlar'])} {b['manzil'] or ''} {b['izoh'] or ''}"
        if b["id"] == raqam_id or _mos(matn_, ildlar):
            bosh["buyurtmalar"].append(b)
            if len(bosh["buyurtmalar"]) >= GURUH_SONI:
                break

    for r in baza.hammasi("SELECT id FROM ish ORDER BY id DESC LIMIT 1000"):
        i = ishlar.ish(r["id"])
        matn_ = f"{i['nom']} {i['joy'] or ''} {i['tavsif'] or ''} {i['mijoz'] or ''} {' '.join(x['ism'] for x in i['ijrochilar'])}"
        if i["id"] == raqam_id or _mos(matn_, ildlar):
            bosh["ishlar"].append(i)
            if len(bosh["ishlar"]) >= GURUH_SONI:
                break

    bosh["yozuvlar"] = hisob.harakatlar(korish=o, q=sorov, limit=GURUH_SONI)
    bosh["xotira"] = [x for x in xotira.royxat(limit=500) if x["holat"] != "bekor"
                      and _mos(f"{x['matn']} {x['iqtibos'] or ''}", ildlar)][:GURUH_SONI]
    bosh["xabarlar"] = arxiv.qidir(sorov, o, limit=GURUH_SONI) if ildlar else []
    return bosh
