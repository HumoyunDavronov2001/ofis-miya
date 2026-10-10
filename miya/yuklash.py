"""CRM5: mijozlarni Excel'dan yuklash — avval ko'rib chiqiladi (hech narsa yozilmaydi), keyin tanlanganlari yoziladi.

Ustunlar sarlavhasidan taniladi (ism/mijoz, telefon, manzil, qarz, izoh); sarlavha topilmasa — 1-ustun ism, 2-ustun
telefon. Takror (ism yoki telefon bazada bor) — o'tkazib yuboriladi. Eski qarz — «Mijozning avvaldan qarzi» yozuvi.
"""
import io
import re

from openpyxl import load_workbook

from . import baza, hisob, matn, vaqt

USTUN = {
    "ism": ("ism", "mijoz", "nomi", "fio", "f i o", "name", "klient", "kontragent", "familiya"),  # «nom» emas — «nomer»
    "telefon": ("telefon", "tel", "phone", "raqam", "nomer", "mobil"),
    "manzil": ("manzil", "adres", "address", "joy", "manzili"),
    "qarz": ("qarz", "qarzi", "dolg", "debt", "balans", "saldo", "summa"),
    "izoh": ("izoh", "eslatma", "note", "comment", "primechanie"),
}
CHEKLOV = 5000  # bir faylda eng ko'pi shuncha qator


class YuklashXato(Exception):
    pass


def _sarlavha(qator: tuple) -> dict[str, int]:
    xarita = {}
    for i, v in enumerate(qator):
        t = matn.norm(str(v or ""))
        if not t:
            continue
        for kalit, sozlar in USTUN.items():
            if kalit not in xarita and any(t.startswith(matn.norm(s)) for s in sozlar):  # norm: q→k, x→h («qarzi»→«karzi»)
                xarita[kalit] = i
                break
    return xarita if "ism" in xarita else {}


def _son(v) -> int | None:
    """«1 500 000», «1,5 mln», 1500000.0 → so'm. Bo'sh — 0; tushunilmasa — None."""
    if v is None or v == "":
        return 0
    if isinstance(v, (int, float)):
        return int(round(v))
    t = str(v).lower().replace("\xa0", " ").strip()
    k = 1_000_000 if re.search(r"mln|million", t) else 1000 if re.search(r"ming|\bk\b", t) else 1
    t = re.sub(r"[^\d.,-]", "", t)
    if re.search(r"[.,]\d{1,2}$", t):
        t = t.replace(",", ".")
        t = t[:t.rfind(".")].replace(".", "") + t[t.rfind("."):]
    else:
        t = t.replace(",", "").replace(".", "")
    try:
        return int(round(float(t) * k))
    except ValueError:
        return None


def _tel(v) -> str:
    t = str(v or "").strip()
    if isinstance(v, float) and v.is_integer():
        t = str(int(v))
    return t[:40]


def korib_chiq(mazmun: bytes, tur: str = "mijoz") -> dict:
    try:
        wb = load_workbook(io.BytesIO(mazmun), read_only=True, data_only=True)
    except Exception as x:
        raise YuklashXato("Excel fayl ochilmadi (.xlsx bo'lsin)") from x
    ws = wb.active
    qatorlar = [q for q in ws.iter_rows(values_only=True)][: CHEKLOV + 20]
    wb.close()
    xarita, boshi = {}, 0
    for i, q in enumerate(qatorlar[:10]):  # eng ko'p ustun tanilgan qator — sarlavha («Mijozlar ro'yxati» nomi emas)
        x = _sarlavha(q)
        if len(x) > len(xarita):
            xarita, boshi = x, i + 1
    if not xarita:
        xarita = {"ism": 0, "telefon": 1}
    bor_ism = {matn.norm(r["ism"]) for r in baza.hammasi("SELECT ism FROM mijoz WHERE tur=? AND birlashdi IS NULL", tur)}
    bor_tel = {re.sub(r"\D", "", r["telefon"] or "")[-9:] for r in baza.hammasi("SELECT telefon FROM mijoz WHERE telefon IS NOT NULL")}
    natija, korilgan = [], set()
    for n, q in enumerate(qatorlar[boshi:boshi + CHEKLOV], boshi + 1):
        ol = lambda k: q[xarita[k]] if k in xarita and xarita[k] < len(q) else None  # noqa: E731
        ism = str(ol("ism") or "").strip()[:120]
        if not ism:
            continue
        tel = _tel(ol("telefon"))
        qarz = _son(ol("qarz"))
        tel9 = re.sub(r"\D", "", tel)[-9:]
        kalit = matn.norm(ism)
        if kalit in bor_ism or (len(tel9) == 9 and tel9 in bor_tel):
            holat, sabab = "takror", "bazada bor"
        elif kalit in korilgan:
            holat, sabab = "takror", "faylda ikki marta"
        elif qarz is None:
            holat, sabab = "xato", "qarz raqam emas"
        else:
            holat, sabab = "yangi", ""
        korilgan.add(kalit)
        natija.append({"qator": n, "ism": ism, "telefon": tel, "manzil": str(ol("manzil") or "").strip()[:200],
                       "qarz": qarz or 0, "izoh": str(ol("izoh") or "").strip()[:300], "holat": holat, "sabab": sabab})
    return {"qatorlar": natija, "ustunlar": {k: v + 1 for k, v in xarita.items()},
            "soni": {h: sum(1 for x in natija if x["holat"] == h) for h in ("yangi", "takror", "xato")}}


def yoz(qatorlar: list[dict], kim_id: int, tur: str = "mijoz") -> dict:
    """Faqat «yangi» qatorlar yoziladi (qayta tekshiriladi — oradan kimdir qo'shgan bo'lishi mumkin)."""
    if tur not in ("mijoz", "taminotchi"):
        raise YuklashXato("Tur noto'g'ri")
    bor = {matn.norm(r["ism"]) for r in baza.hammasi("SELECT ism FROM mijoz WHERE tur=? AND birlashdi IS NULL", tur)}
    qoshildi = qarz_soni = 0
    with baza.tranz():
        for x in qatorlar[:CHEKLOV]:
            ism = (x.get("ism") or "").strip()[:120]
            if not ism or matn.norm(ism) in bor:
                continue
            mid = baza.bajar("INSERT INTO mijoz(ism,telefon,manzil,izoh,tur,yaratilgan) VALUES(?,?,?,?,?,?)", ism,
                             (x.get("telefon") or None), (x.get("manzil") or None), (x.get("izoh") or None), tur, vaqt.iso())
            bor.add(matn.norm(ism))
            qoshildi += 1
            qarz = int(x.get("qarz") or 0)
            if qarz > 0:
                shablon = "boshlangich_mijoz" if tur == "mijoz" else "boshlangich_taminotchi"
                hid = hisob.taklif(shablon, {"summa": qarz, "mijoz_id": mid, "izoh": "Excel'dan yuklandi"}, kim_id,
                                   manba="import")
                hisob.faollashtir(hid, kim_id)
                qarz_soni += 1
        baza.jurnal(kim_id, "mijoz_import", f"{tur}", None, {"qoshildi": qoshildi, "qarz": qarz_soni})
    return {"qoshildi": qoshildi, "qarz_yozildi": qarz_soni, "otkazildi": len(qatorlar) - qoshildi}
