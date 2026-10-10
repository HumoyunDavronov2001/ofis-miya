"""Sun'iy intellekt javobini dastur bilgan narsa bilan tuzatish (bot ham, panel ham shu natijani oladi).

Model mijozlar ro'yxatini ko'rmaydi (tejash) — shuning uchun «Olmos savdoga to'ladik» ni kirim, «Botir konditsioner
oldi» ni ta'minotchidan nasiya deb o'qishi mumkin. Kim mijoz, kim ta'minotchi, kimning kassasi bor — dastur biladi.
Faqat sxema ichidagi maydonlar o'zgaradi (tur, kim, muddat) yoki ortiqcha element olib tashlanadi; ismlar matn bo'lib qoladi.
"""
import re
from datetime import date, timedelta

from . import baza, hisob, matn, vaqt


def _qaysi(ism: str) -> set[str]:
    """Ism bazada kim: {"mijoz"}, {"taminotchi"}, ikkalasi yoki bo'sh (aniq topilmasa)."""
    ism = (ism or "").strip()
    if not ism:
        return set()
    r = set()
    for tur in ("mijoz", "taminotchi"):
        variant = [(x["id"], x["ism"]) for x in
                   baza.hammasi("SELECT id, ism FROM mijoz WHERE tur=? AND birlashdi IS NULL", tur)]
        if matn.yagona(matn.mosla(ism, variant)):
            r.add(tur)
    return r


def _bir_odam(a: str, b: str) -> bool:
    a, b = matn.norm(a or ""), matn.norm(b or "")
    return bool(a and b) and (a == b or matn.ball(a, b) >= 0.86)


def _kunlar(sozlar: list[str]) -> set[int]:
    return {i for i, k in enumerate(vaqt.HAFTA) if any(s.startswith(matn.norm(k)) for s in sozlar)}


def _aniq_sana(sozlar: list[str]) -> bool:
    """«25-oktabrda», «25.10» — aniq sana aytilgan (norm'dan keyin: «25 oktabrda», «25 10»)."""
    oylar = [matn.norm(o)[:4] for o in vaqt.OYLAR]
    return any(s.startswith(tuple(oylar)) for s in sozlar) or any(
        a.isdigit() and b.isdigit() and int(a) <= 31 and int(b) <= 12 for a, b in zip(sozlar, sozlar[1:]))


def _hafta_kuni(sana: str, iqtibos: str, gap_sozlari: list[str]) -> str:
    """«dushanba borsin» — model o'tgan dushanbani yoki qo'shni kunni olsa: aytilgan hafta kunining eng yaqin
    kelgusi sanasi. Faqat bitta hafta kuni aytilgan bo'lsa (avval o'sha parchada, bo'lmasa butun gapda); «o'tgan» yoki
    aniq sana («25-oktabr») bo'lsa — tegilmaydi. Ish, va'da, qarz muddati — doim kelajakda."""
    try:
        d = date.fromisoformat((sana or "")[:10])
    except ValueError:
        return sana
    soz = matn.norm(iqtibos or "").split()
    kun, bugun = _kunlar(soz), vaqt.bugun()
    nisbiy = {"ertaga", "indinga", "indin", "bugun", "kecha", "hozir"} & set(soz)
    if not kun and d < bugun and not nisbiy and not _aniq_sana(soz) and not _aniq_sana(gap_sozlari):
        kun = _kunlar(gap_sozlari)  # model o'tgan sanani bergan, parchada kun yo'q — butun gapdan (bittasi bo'lsa)
    if len(kun) != 1 or "otgan" in soz or "otgan" in gap_sozlari:
        return sana
    w = kun.pop()
    if (d >= bugun and d.weekday() == w) or abs((d - bugun).days) > 14:
        return sana
    return (bugun + timedelta(days=(w - bugun.weekday()) % 7)).isoformat()


SON_SOZ = ("bir", "ikki", "uch", "tort", "besh", "olti", "yetti", "sakkiz", "toqqiz", "on", "yigirma", "ottiz", "qirq",
           "kirk", "ellik", "oltmish", "yetmish", "sakson", "toqson", "yuz", "ming", "mln", "million", "mlrd", "dollar")


def _nisbiy_vaqt(gap: str):
    """«20 daqiqadan keyin», «1 soatdan keyin», «yarim soatdan keyin», «2 soat 30 daqiqadan keyin» → aniq vaqt."""
    t = matn.norm(gap)
    if "keyin" not in t:
        return None
    soat = re.search(r"(\d+|yarim)\s*soat", t)
    daq = re.search(r"(\d+)\s*(?:dakika|minut)", t)  # norm: q→k («daqiqa» → «dakika»)
    if not soat and not daq:
        return None
    minut = (30 if soat and soat.group(1) == "yarim" else int(soat.group(1)) * 60 if soat else 0) + (int(daq.group(1)) if daq else 0)
    if not 0 < minut <= 24 * 60:
        return None
    return vaqt.hozir() + timedelta(minutes=minut)


def _raqamsiz(iqtibos: str | None) -> bool:
    """Parchada summa umuman yo'q (raqam ham, son so'zi ham) — demak model summani boshqa joydan olgan."""
    if not (iqtibos or "").strip() or any(ch.isdigit() for ch in iqtibos):
        return False
    return not any(s.startswith(SON_SOZ) for s in matn.norm(iqtibos).split())


def _sotuv_sozi(matn_: str) -> bool:
    return any(s.startswith(("sot", "harid")) or s in ("oldi", "olibdi", "olishdi", "olib") for s in matn.norm(matn_).split())


OTGAN_TOLOV = ("toladi", "tolashdi", "toladik", "toladim", "berdi", "tashladi", "otkazdi")  # norm: o'→o
KELAJAK = ("dedi", "aytdi", "vada", "keyin", "ertaga", "beradi", "tolaydi", "beraman", "tolayman", "beramiz", "olib")


def _otgan_tolov(iqtibos: str) -> bool:
    """«Gulnora 1 mln to'ladi» — pul allaqachon o'tgan; «beraman dedi», «ertaga to'laydi» — va'da."""
    soz = matn.norm(iqtibos or "").split()
    return any(s.startswith(OTGAN_TOLOV) for s in soz) and not any(s.startswith(KELAJAK) for s in soz)


def _taminotchi_parchada(iqtibos: str) -> str:
    """«Olmos savdoga 2 mln to'ladik» — model ismni yozmasa: parchada ta'minotchining hamma so'zi bor bo'lsa (yagona)."""
    toklar = matn.norm(iqtibos or "").split()
    mos = [r["ism"] for r in baza.hammasi("SELECT ism FROM mijoz WHERE tur='taminotchi' AND birlashdi IS NULL")
           if (n := matn.norm(r["ism"]).split()) and all(any(t.startswith(w[:max(4, len(w) - 2)]) for t in toklar) for w in n)]
    return mos[0] if len(mos) == 1 else ""


def _ustma(a: str, b: str) -> bool:
    a, b = matn.norm(a or ""), matn.norm(b or "")
    return bool(a and b) and (a in b or b in a)


def _buyurtmalar(d: dict, yozuvlar: list[dict], sozlar: list[str]) -> None:
    """CRM7: buyurtma (hali sotilmagan) — sotuv, ish va xotira bilan takrorlanmaydi."""
    natija = []
    for b in d.get("buyurtmalar") or []:
        b["qatorlar"] = [q for q in b.get("qatorlar") or [] if (q.get("nom") or "").strip()]
        if not b["qatorlar"]:
            continue
        # «8 ta kamera sotdik, 2 mln berdi» — sotib bo'lingan: pul kartochkasi (sotuv) yetadi
        if any(y.get("tur") == "sotuv" and (_bir_odam(y.get("mijoz"), b.get("mijoz")) or not (b.get("mijoz") or "").strip())
               for y in yozuvlar):
            continue
        b["muddat"] = _hafta_kuni(b.get("muddat"), b.get("iqtibos"), sozlar)
        natija.append(b)
    d["buyurtmalar"] = natija
    if not natija:
        return
    # ijrochisiz «o'rnatish kerak» ishi — buyurtmaning o'zi (o'rnatish ishi «Sotildi»da beriladi)
    def _shu(i, b):
        if _bir_odam(i.get("mijoz"), b.get("mijoz")) or _ustma(i.get("iqtibos"), b.get("iqtibos")):
            return True
        ildiz = {w[:5] for q in b["qatorlar"] for w in matn.norm(q.get("nom")).split() if len(w) >= 4} | {"ornat"}
        return not (i.get("mijoz") or "").strip() and any(
            w[:5] in ildiz for w in matn.norm(f"{i.get('nom', '')} {i.get('iqtibos', '')}").split() if len(w) >= 4)
    d["ishlar"] = [i for i in d.get("ishlar") or [] if i.get("ijrochilar") or not any(_shu(i, b) for b in natija)]
    # o'sha gapdan yasalgan «ma'lumot» — takror (uchrashuv va eslatma qoladi: ularning vaqti bor)
    d["xotira"] = [x for x in d.get("xotira") or [] if x.get("tur") != "malumot" or not any(
        _ustma(x.get("iqtibos") or x.get("matn"), b.get("iqtibos")) for b in natija)]
    # «Sobirov 4 ta kamera narxini so'radi» — mijoz eslatmasi emas, buyurtmaning o'zi
    d["mijoz_eslatmalar"] = [e for e in d.get("mijoz_eslatmalar") or [] if not any(
        _ustma(e.get("iqtibos") or e.get("matn"), b.get("iqtibos")) for b in natija)]


def tuzat(d: dict, yozgan: dict, gap: str = "") -> dict:
    sozlar = matn.norm(gap).split()
    ozi_kassasi = any(k["masul_id"] == yozgan["id"] for k in hisob.kassalar())
    # summasi ham, gapdan parchasi ham yo'q yozuv — model to'ldirgan bo'sh joy (masalan ish mijoziga «sotuv 0»)
    d["yozuvlar"] = [y for y in d.get("yozuvlar") or []
                     if (y.get("summa") or 0) or (y.get("tolandi") or 0) or (y.get("iqtibos") or "").strip()]
    yozuvlar = d["yozuvlar"]
    for i in d.get("ishlar") or []:  # «Dilshod borsin, 300 ming oladi» — ish narxi; ishbay qabulda o'zi yoziladi
        if i.get("narx"):
            ijr = i.get("ijrochilar") or []
            ish_iq = matn.norm(i.get("iqtibos") or "")
            for y in list(yozuvlar):
                if y.get("summa") != i["narx"]:
                    continue
                iq = matn.norm(y.get("iqtibos") or "")
                if ((iq and iq in ish_iq)  # «600 ming» — ish gapining o'zidan olingan
                        or (y.get("tur") in ("ishbay", "bonus", "avans", "qolga_berish")
                            and (not ijr or any(_bir_odam(y.get("odam"), x) for x in ijr)))
                        or (y.get("tur") == "sotuv" and _bir_odam(y.get("mijoz"), i.get("mijoz")))):
                    yozuvlar.remove(y)
    for y in list(yozuvlar):
        if y.get("tur") != "sotuv":
            continue
        summa, tolandi = y.get("summa") or 0, y.get("tolandi") or 0
        if summa and y.get("muddat") and _raqamsiz(y.get("iqtibos")):
            # «qolganini dushanba beradi» parchasidan sotuv yasalgan, summa boshqa joydan — bu va'da
            if not any(v.get("tur") == "tolov" and _bir_odam(v.get("mijoz"), y.get("mijoz")) for v in d.get("vadalar") or []):
                d.setdefault("vadalar", []).append(
                    {"mijoz": y.get("mijoz") or "", "kim": "mijoz", "tur": "tolov", "summa": 0, "birlik_noaniq": False,
                     "valyuta": y.get("valyuta") or "UZS", "muddat": y["muddat"], "matn": "", "iqtibos": y.get("iqtibos") or ""})
            yozuvlar.remove(y)
            continue
        manba = y.get("iqtibos") or gap
        if summa and tolandi >= summa and manba and not _sotuv_sozi(manba):
            y.update(tur="kirim", tolandi=0, muddat="")  # «Karimov 500 ming to'ladi» — sotilgani aytilmagan: to'lov
            continue
        if not summa and tolandi:  # «500 ming to'ladi, qolganini dushanba» — bu sotuv emas, to'lov + va'da
            if y.get("muddat") and not any(v.get("tur") == "tolov" and _bir_odam(v.get("mijoz"), y.get("mijoz"))
                                           for v in d.get("vadalar") or []):
                d.setdefault("vadalar", []).append(
                    {"mijoz": y.get("mijoz") or "", "kim": "mijoz", "tur": "tolov", "summa": 0, "birlik_noaniq": False,
                     "valyuta": y.get("valyuta") or "UZS", "muddat": y["muddat"], "matn": "", "iqtibos": y.get("iqtibos") or ""})
            if any(x is not y and x.get("tur") == "kirim" and (x.get("summa") or 0) == tolandi
                   and _bir_odam(x.get("mijoz"), y.get("mijoz")) for x in yozuvlar):
                yozuvlar.remove(y)  # o'sha to'lov kirim bo'lib allaqachon bor
            else:
                y.update(tur="kirim", summa=tolandi, tolandi=0, muddat="")
        elif summa and tolandi >= summa:
            y["muddat"] = ""  # to'liq to'langan sotuvda qarz muddati bo'lmaydi
    # «qolganini dushanba beradi» — model summasiz kirim deb yozsa: bu va'da (qoldiqni dastur qarzdan hisoblaydi)
    for y in list(yozuvlar):
        if y.get("tur") != "kirim" or (y.get("summa") or 0) or (y.get("tolandi") or 0):
            continue
        soz = matn.norm(y.get("iqtibos") or "").split()
        if not (y.get("muddat") or "").strip() and not any(x.startswith(KELAJAK) for x in soz):
            continue
        yozuvlar.remove(y)
        if not any(v.get("tur") == "tolov" and _bir_odam(v.get("mijoz"), y.get("mijoz")) for v in d.get("vadalar") or []):
            d.setdefault("vadalar", []).append(
                {"mijoz": y.get("mijoz") or "", "kim": "mijoz", "tur": "tolov", "summa": 0, "birlik_noaniq": False,
                 "valyuta": y.get("valyuta") or "UZS", "muddat": y.get("muddat") or "", "matn": "", "iqtibos": y.get("iqtibos") or ""})
    # «Gulnora 1 mln to'ladi» — model va'da deb yozsa (muddatsiz, o'tgan zamon): bu kirim
    for v in list(d.get("vadalar") or []):
        if (v.get("tur") == "tolov" and v.get("kim") == "mijoz" and (v.get("summa") or 0) > 0 and not (v.get("muddat") or "").strip()
                and _otgan_tolov(v.get("iqtibos"))):
            d["vadalar"].remove(v)
            if not any(y.get("tur") in ("kirim", "sotuv") and _bir_odam(y.get("mijoz"), v.get("mijoz"))
                       and v["summa"] in (y.get("summa"), y.get("tolandi")) for y in yozuvlar):
                yozuvlar.append({"tur": "kirim", "summa": v["summa"], "birlik_noaniq": bool(v.get("birlik_noaniq")),
                                 "valyuta": v.get("valyuta") or "aytilmagan", "odam": "", "mijoz": v.get("mijoz") or "",
                                 "kassa": "", "kassa2": "", "xarajat_turi": "", "sana": "", "tolandi": 0, "muddat": "",
                                 "qoldan": False, "izoh": "", "iqtibos": v.get("iqtibos") or ""})
    for y in yozuvlar:  # «Olmos savdoga 2 mln to'ladik» — mijoz bo'sh qolsa, ta'minotchi parchadan topiladi
        if y.get("tur") in ("kirim", "chiqim") and not (y.get("mijoz") or "").strip() and _otgan_tolov(y.get("iqtibos")):
            y["mijoz"] = _taminotchi_parchada(y.get("iqtibos"))
    for y in yozuvlar:  # sotuv tozalangandan keyin: «Olmos savdoga to'ladik» sotuv→kirim→ta'minotchiga
        tur, kim = y.get("tur"), _qaysi(y.get("mijoz"))
        if tur in ("kirim", "chiqim") and kim == {"taminotchi"}:
            y["tur"] = "taminotchiga_tolov"  # ta'minotchi bilan pul — bizdan unga
        elif tur == "taminotchi_nasiya" and kim == {"mijoz"}:
            y["tur"] = "sotuv"  # mijoz bizdan oldi
        elif tur == "kirim" and yozgan["rol"] != "boshliq" and (y.get("qoldan") or (
                yozgan["rol"] == "xodim" and not ozi_kassasi and not (y.get("kassa") or "").strip())):
            y["tur"] = "mijozdan_qolga"  # xodim «oldim» — pul kassada emas, uning qo'lida
            y["qoldan"] = False
            if not (y.get("odam") or "").strip():
                y["odam"] = "men"
    sotuvlar = [y for y in yozuvlar if y.get("tur") == "sotuv" and (y.get("summa") or 0) > (y.get("tolandi") or 0)]
    vadalar = []
    from .ai import _aniqlik  # aylanma import bo'lmasin
    aytilgan = _aniqlik(gap)
    for v in d.get("vadalar") or []:
        if (v.get("summa") or 0) > 0 and aytilgan and not any(abs(v["summa"] - x) <= max(ch, 0.5) for x, ch in aytilgan):
            v["summa"] = 0  # «qolganini beradi» — model o'zi hisoblagan son; qoldiqni dastur qarzdan hisoblaydi
        if (v.get("summa") or 0) > 0 and v.get("tur") == "boshqa":
            v["tur"] = "tolov"  # summali va'da — to'lov
        if v.get("tur") == "tolov" and v.get("kim") == "biz" and _qaysi(v.get("mijoz")) == {"mijoz"}:
            v["kim"] = "mijoz"  # mijoz «beraman dedi» — to'lovni mijoz qiladi
        v["muddat"] = _hafta_kuni(v.get("muddat"), v.get("iqtibos"), sozlar)
        s = next((x for x in sotuvlar if _bir_odam(x.get("mijoz"), v.get("mijoz"))), None)
        if s and v.get("tur") == "tolov":
            s["muddat"] = s.get("muddat") or v.get("muddat") or ""  # sotuv faollashganda va'da o'zi yoziladi
            continue
        vadalar.append(v)
    d["vadalar"] = vadalar
    # «qolganini dushanba beradi» parchasidan summasiz pul yozuvi ham yasalgan bo'lsa — u va'daning o'zi (takror)
    for y in list(yozuvlar):
        if not (y.get("summa") or 0) and not (y.get("tolandi") or 0) and any(
                _ustma(y.get("iqtibos"), v.get("iqtibos")) for v in vadalar):
            yozuvlar.remove(y)
    for i in d.get("ishlar") or []:
        i["muddat"] = _hafta_kuni(i.get("muddat"), i.get("iqtibos"), sozlar)
    _buyurtmalar(d, yozuvlar, sozlar)
    for x in d.get("xotira") or []:
        x["sana"] = _hafta_kuni(x.get("sana"), x.get("iqtibos"), sozlar)
    # «Akmalga ham eslat» — model ismni matnga yozib, «kimga»ni bo'sh qoldirsa (eslatma Akmalga bormay qolardi)
    kimga = re.search(r"([A-Za-z'ʻ’`]{3,})(?:ga|ka|qa)\s+(?:ham\s+)?eslat", gap or "")
    if kimga:
        for x in d.get("xotira") or []:
            if not (x.get("kimga") or "").strip():
                x["kimga"] = kimga.group(1)
    nisbiy = _nisbiy_vaqt(gap)  # «20 daqiqadan keyin eslat» — vaqtni AI emas, dastur hisoblaydi
    if nisbiy and len(d.get("xotira") or []) == 1:
        x = d["xotira"][0]
        x["sana"], x["soat"] = nisbiy.date().isoformat(), f"{nisbiy:%H:%M}"
        if x.get("tur") == "malumot":
            x["tur"] = "eslatma"
    # «ertaga 9 da omborga mol keladi» — xotira (eslatma) bo'lgan gapdan ijrochisiz ish yasalmaydi
    xot_iq = [matn.norm(x.get("iqtibos") or x.get("matn") or "") for x in d.get("xotira") or []]
    d["ishlar"] = [i for i in d.get("ishlar") or [] if i.get("ijrochilar") or not (iq := matn.norm(i.get("iqtibos") or ""))
                   or not any(q and (q in iq or iq in q) for q in xot_iq)]
    for y in yozuvlar:
        if y.get("muddat"):
            y["muddat"] = _hafta_kuni(y["muddat"], y.get("iqtibos"), sozlar)
    ish_matni = " | ".join([matn.norm(f"{i.get('iqtibos', '')} {i.get('joy', '')}") for i in d.get("ishlar") or []]
                           + [matn.norm(y.get("iqtibos") or "") for y in yozuvlar]  # pul gapidan ham eslatma yasalmaydi
                           + [matn.norm(f"{b.get('iqtibos', '')} {b.get('manzil', '')}") for b in d.get("buyurtmalar") or []])

    def _shovqin(e):  # «Yangi mijoz.», ish manzilidan olingan «Do'koni mavjud» — eslatma emas
        m_, iq = matn.norm(e.get("matn")), matn.norm(e.get("iqtibos"))
        return (m_.startswith("yangi mijoz") and len(m_.split()) <= 3) or bool(iq and iq in ish_matni)
    d["mijoz_eslatmalar"] = [e for e in d.get("mijoz_eslatmalar") or [] if not _shovqin(e)]
    # R5: ma'noli gap tashlanmaydi — model hech narsa ajratmagan bo'lsa ham xotiraga ma'lumot bo'lib yoziladi
    bosh = not any(d.get(k) for k in ("yozuvlar", "ishlar", "bajarildi", "davomat", "vadalar", "mijoz_eslatmalar", "xotira",
                                      "buyurtmalar"))
    if bosh and not (d.get("savol") or "").strip() and not (d.get("muammo") or "").strip() and len(sozlar) >= 3:
        d["xotira"] = [{"tur": "malumot", "matn": gap.strip()[:500], "sana": "", "soat": "", "kimga": "", "iqtibos": gap.strip()[:300]}]
        d["tushunilmadi"] = ""
    return d
