"""Xotira arxivi (X1, X6): asl xabarni topish — ovozda topilgan so'z boshlangan soniya bilan.

Huquq (D-d): boshliq — hamma xabar; qolganlar — faqat o'zi yozgani (maosh gaplari boshqaga ochilmasin, M8).
Yashirilgan rasm hech qachon chiqmaydi.
"""
import json

from . import baza, matn, odamlar, qidiruv

TUR_NOMI = {"ovoz": "Ovozli xabar", "matn": "Yozma xabar", "rasm": "Rasm", "fayl": "Fayl"}


def _shart(o: dict) -> tuple[str, list]:
    if odamlar.boshliqmi(o):
        return "x.yashirin=0", []
    return "x.yashirin=0 AND x.odam_id=?", [o["id"]]


def _json(x: dict, ildlar: list[str] | None = None) -> dict:
    asl = x["stt_matn"] or x["matn"] or ""
    soniya = None
    if ildlar and x["tur"] == "ovoz" and x["stt_sozlar"]:
        try:
            sozlar = json.loads(x["stt_sozlar"])
        except ValueError:
            sozlar = []
        if sozlar:
            toklar = [matn.norm(s.get("soz") or "") for s in sozlar]
            joy = qidiruv.eng_yaxshi_joy(toklar, ildlar)
            soniya = max(0.0, float(sozlar[joy].get("dan") or 0) - 1.0)
    return {"id": x["id"], "vaqt": x["vaqt"], "kim": x["kim"] or "—", "tur": x["tur"],
            "tur_nomi": TUR_NOMI.get(x["tur"], x["tur"]), "uzatilgan": x["uzatilgan"],
            "matn": asl[:1000], "parcha": qidiruv.parcha(asl, ildlar) if ildlar and asl else asl[:200],
            "soniya": soniya, "davomiylik": x["davomiylik"], "fayl": bool(x["fayl"])}


def qidir(sorov: str, o: dict, limit: int = 10, tur: str | None = None) -> list[dict]:
    """Eng mos xabarlar: ko'p ildiz uchragani oldinda, teng bo'lsa yangisi."""
    ildlar = qidiruv.ildizlar(sorov)
    if not ildlar:
        return []
    shart, p = _shart(o)
    if tur:
        shart += " AND x.tur=?"
        p.append(tur)
    nomzod = []
    for x in baza.hammasi(f"SELECT x.*, od.ism kim FROM xabar x LEFT JOIN odam od ON od.id=x.odam_id WHERE {shart} "
                          "AND COALESCE(x.stt_matn, x.matn, '')!='' ORDER BY x.id DESC LIMIT 20000", *p):
        b = qidiruv.ball(qidiruv.tokenlar(x["stt_matn"] or x["matn"] or ""), ildlar)
        if b:
            nomzod.append((b, x))
    if not nomzod:
        return []
    eng = max(b for b, _ in nomzod)
    kerak = max(1, -(-len(ildlar) * 6 // 10))  # kamida 60 % ildiz — aks holda faqat eng yaxshilari
    nomzod = [(b, x) for b, x in nomzod if b >= min(kerak, eng)]
    nomzod.sort(key=lambda bx: (-bx[0], -bx[1]["id"]))
    return [{**_json(x, ildlar), "ball": b, "jami": len(ildlar)} for b, x in nomzod[:limit]]


def oxirgilar(o: dict, limit: int = 40, tur: str | None = None, odam_id: int | None = None) -> list[dict]:
    shart, p = _shart(o)
    if tur:
        shart += " AND x.tur=?"
        p.append(tur)
    if odam_id and odamlar.boshliqmi(o):
        shart += " AND x.odam_id=?"
        p.append(odam_id)
    return [_json(x) for x in baza.hammasi(f"SELECT x.*, od.ism kim FROM xabar x LEFT JOIN odam od ON od.id=x.odam_id "
                                           f"WHERE {shart} ORDER BY x.id DESC LIMIT ?", *p, limit)]


def korishi_mumkin(o: dict, xabar_id: int) -> bool:
    x = baza.bir("SELECT odam_id, yashirin FROM xabar WHERE id=?", xabar_id)
    return bool(x) and not x["yashirin"] and (odamlar.boshliqmi(o) or x["odam_id"] == o["id"])
