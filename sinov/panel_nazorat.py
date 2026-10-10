"""Panel «miya» qatori — HAQIQIY sun'iy intellekt bilan nazorat (pullik, ~$0.15): gap → kartochkalar to'g'rimi.

Namuna baza nazorat.py dagi bilan bir xil («bugun» 2026-10-15 payshanba). Ishlatish:
    MIYA_ANTHROPIC_KALIT=... python3 sinov/panel_nazorat.py [3,7]   # raqamlar — faqat shu holatlar
"""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from miya import ai, baza, buyurtma, ishlar, panel_taklif, odamlar  # noqa: E402
import nazorat  # noqa: E402

ERTAGA, SHANBA, DUSHANBA = "2026-10-16", "2026-10-17", "2026-10-19"


def _id(nom):
    return baza.qiymat("SELECT id FROM mijoz WHERE ism=?", nom)


def _kassa(nom):
    return baza.qiymat("SELECT id FROM kassa WHERE nom=?", nom)


def pul(tur, summa, **sh):
    return {"tur": "pul", "harakat_tur": tur, "summa": summa, **sh}


def holatlar(od):
    """(kim, gap, kutilgan kartochkalar). Maydon qiymati: aniq qiymat yoki tekshiruvchi funksiya."""
    a, d, k = od["xodim"], od["dilshod"], od["kassir"]
    anvar, botir, gulnora, sardor = (_id(x) for x in ("Anvar Karimov", "Botir Sobirov", "Gulnora Azimova", "Sardor Nazarov"))
    olmos = _id("Olmos savdo")
    mij = lambda i: lambda m: bool(m) and m.get("id") == i  # noqa: E731
    yangi = lambda ism: lambda m: bool(m) and not m.get("id") and (m.get("yangi") or "").lower().startswith(ism)  # noqa: E731
    odam = lambda i: lambda r: bool(r) and r.get("id") == i  # noqa: E731
    ijr = lambda *ids: lambda x: {i["id"] for i in x} == set(ids)  # noqa: E731
    bor = lambda soz: lambda s: soz in (s or "").lower()  # noqa: E731
    qat = lambda *q: lambda x: sorted((r["nom"], r["miqdor"], r["narx"]) for r in x) == sorted(q)  # noqa: E731
    KAM, ORN, DVR = "IP kamera 4MP", "O'rnatish (1 kamera)", "Videoregistrator 8 kanal"
    return [
        ("boshliq", "Karimov 1 mln to'ladi, qolganini dushanba beradi",
         [pul("kirim", 1_000_000, mijoz=mij(anvar)),
          {"tur": "vada", "vtur": "tolov", "summa": 2_000_000, "muddat": DUSHANBA, "mijoz": mij(anvar)}]),
        ("boshliq", "Yangi mijoz Jasur, 5 ta kamera o'rnatish kerak, Dilshod shanba borsin, 1,5 mln oladi",
         [{"tur": "ish", "ijrochilar": ijr(d), "mijoz": yangi("jasur"), "muddat": SHANBA, "narx": 1_500_000},
          {"tur": "buyurtma", "mijoz": yangi("jasur"), "qatorlar": lambda x: any(r["nom"] == KAM and r["miqdor"] == 5 for r in x)}]),
        ("boshliq", "Benzinga 200 ming ketdi, Akmalga 500 ming avans berdim",
         [pul("chiqim", 200_000, xarajat_turi=bor("benzin")), pul("avans", 500_000, odam=odam(a))]),
        ("boshliq", "Gulnora ertaga 3 mln olib keladi",
         [{"tur": "vada", "vtur": "tolov", "kim": "mijoz", "summa": 3_000_000, "muddat": ERTAGA, "mijoz": mij(gulnora)}]),
        ("boshliq", "Sobirov faqat kechqurun qo'ng'iroq qilishni so'radi, ruscha gaplashadi",
         [{"tur": "eslatma", "mijoz": mij(botir)}]),
        ("boshliq", "Olmos savdoga 2 mln to'ladik", [pul("taminotchiga_tolov", 2_000_000, mijoz=mij(olmos))]),
        ("boshliq", "Sardorga ertaga shartnomani olib boramiz deb va'da berdik",
         [{"tur": "vada", "kim": "biz", "vtur": "boshqa", "muddat": ERTAGA, "mijoz": mij(sardor)}]),
        ("boshliq", "Akmal ertaga soat 10 da Karimovning uyiga konditsioner o'rnatsin, Yunusobod 5-kvartal",
         [{"tur": "ish", "ijrochilar": ijr(a), "mijoz": mij(anvar), "muddat": ERTAGA, "soat": "10:00", "joy": bor("yunusobod")}]),
        ("boshliq", "Dollar kassadan 50 dollar ehtiyot qismga ketdi",
         [pul("chiqim", 50, valyuta="USD", kassa_id=_kassa("Dollar kassa"), xarajat_turi=bor("ehtiyot"))]),
        ("boshliq", "Karimovga 2 mln lik eshik sotdik, 500 ming berdi, qolganini 25-oktabrda beradi",
         [pul("sotuv", 2_000_000, tolandi=500_000, muddat="2026-10-25", mijoz=mij(anvar))]),
        ("boshliq", "Dilshodga 100 ming jarima", [pul("jarima", 100_000, odam=odam(d))]),
        ("boshliq", "Sardor 100 dollar berdi", [pul("kirim", 100, valyuta="USD", mijoz=mij(sardor), kassa_id=_kassa("Dollar kassa"))]),
        ("boshliq", "Botir aka 4 mln lik konditsioner oldi, pulini keyin beradi",
         [pul("sotuv", 4_000_000, mijoz=mij(botir), tolandi=0)]),
        ("boshliq", "Eshik o'rnatish ishi tugadi", [{"tur": "bajarildi", "ish_id": od["eshik"]}]),
        ("boshliq", "Karimov dushanba 2 mln beraman dedi",
         [{"tur": "vada", "vtur": "tolov", "summa": 2_000_000, "muddat": DUSHANBA, "mijoz": mij(anvar)}]),
        ("boshliq", "Kecha Akmalga 200 ming qarz berdim", [pul("xodim_qarz", 200_000, odam=odam(a), sana="2026-10-14")]),
        ("boshliq", "Gulnora 1 mln to'ladi", [pul("kirim", 1_000_000, mijoz=mij(gulnora))]),
        ("boshliq", "Bugun Karimov 500 ming to'ladi, Sobirovga 2 ta kamera sotdik 1,2 mln naqd, Dilshod ertaga Gulnoraning "
                    "do'koniga borib eshik o'rnatsin",
         [pul("kirim", 500_000, mijoz=mij(anvar)), pul("sotuv", 1_200_000, tolandi=1_200_000, mijoz=mij(botir)),
          {"tur": "ish", "ijrochilar": ijr(d), "mijoz": mij(gulnora), "muddat": ERTAGA}]),
        ("boshliq", "Bugun Karimov 500 ming to'ladi, qolganini dushanba beradi. Sobirovga 2 ta kamera sotdik 1,2 mln naqd. "
                    "Dilshod ertaga Gulnoraning do'koniga borib eshik o'rnatsin, 300 ming oladi",
         [pul("kirim", 500_000, mijoz=mij(anvar)),
          {"tur": "vada", "vtur": "tolov", "summa": 2_500_000, "muddat": DUSHANBA, "mijoz": mij(anvar)},
          pul("sotuv", 1_200_000, tolandi=1_200_000, mijoz=mij(botir), muddat=lambda m: not m),
          {"tur": "ish", "ijrochilar": ijr(d), "mijoz": mij(gulnora), "muddat": ERTAGA, "narx": 300_000}]),
        ("boshliq", "Karimov 1 mln to'ladi, qolganini dushanba beradi. Akmal ertaga soat 10 da Sobirovning ofisiga 3 ta "
                    "kamera o'rnatsin, 600 ming. Olmos savdoga 2 mln to'ladik",
         [pul("kirim", 1_000_000, mijoz=mij(anvar)), pul("taminotchiga_tolov", 2_000_000, mijoz=mij(olmos)),
          {"tur": "vada", "vtur": "tolov", "summa": 2_000_000, "muddat": DUSHANBA, "mijoz": mij(anvar)},
          {"tur": "ish", "ijrochilar": ijr(a), "mijoz": mij(botir), "muddat": ERTAGA, "soat": "10:00", "narx": 600_000}]),
        ("xodim", "Benzinga 100 ming o'z pulimdan ishlatdim, Karimovdan 1 mln oldim, eshik ishini tugatdim",
         [pul("chiqim", 100_000, qoldan=True, odam=odam(a)), pul("mijozdan_qolga", 1_000_000, odam=odam(a), mijoz=mij(anvar)),
          {"tur": "bajarildi", "ish_id": od["eshik"], "ruxsat": False}]),
        ("xodim", "Benzinga 100 ming o'z pulimdan ishlatdim", [pul("chiqim", 100_000, qoldan=True, odam=odam(a))]),
        ("xodim", "Karimovdan 1 mln oldim", [pul("mijozdan_qolga", 1_000_000, odam=odam(a), mijoz=mij(anvar))]),
        ("kassir", "Akmalga 300 ming maosh berdim", [pul("maosh_tolov", 300_000, odam=odam(a), kassa_id=_kassa("Asosiy kassa"))]),
        ("menejer", "Dilshod bilan Akmal dushanba Sobirovning ofisiga 3 ta kamera o'rnatsin",
         [{"tur": "ish", "ijrochilar": ijr(a, d), "mijoz": mij(botir), "muddat": DUSHANBA}]),
        # CRM7: chatdan buyurtma — qator nomi va narxini dastur katalogdan topadi
        ("boshliq", "Yangi mijoz Bekzod, 8 ta kamera kerak, o'rnatish bilan, Chilonzor 12",
         [{"tur": "buyurtma", "mijoz": yangi("bekzod"), "qatorlar": qat((KAM, 8, 650_000), (ORN, 8, 150_000)),
           "jami": 6_400_000, "manzil": bor("chilonzor")}]),
        ("xodim", "Sobirov 4 ta kamera narxini so'radi",
         [{"tur": "buyurtma", "mijoz": mij(botir), "qatorlar": lambda x: [(r["nom"], r["miqdor"]) for r in x] == [(KAM, 4)]}]),
        ("boshliq", "Gulnoraga 2 ta videoregistrator kerak, har biri 1 mln dan, juma kuni olib borish kerak",
         [{"tur": "buyurtma", "mijoz": mij(gulnora), "qatorlar": qat((DVR, 2, 1_000_000)), "muddat": "2026-10-16"}]),
    ]


def mos(karta, kut):
    for k, v in kut.items():
        q = karta.get(k)
        if callable(v):
            if not v(q):
                return f"{k}={q!r}"
        elif q != v:
            return f"{k}={q!r} (kutilgan {v!r})"
    return None


def tekshir(kartalar, kutilgan):
    xato, qoldi = [], list(kartalar)
    for kut in kutilgan:
        nomzod = [c for c in qoldi if c["tur"] == kut["tur"] and c.get("harakat_tur") == kut.get("harakat_tur")]
        if not nomzod:
            xato.append(f"yo'q: {kut['tur']} {kut.get('harakat_tur', '')}")
            continue
        sabablar = [(c, mos(c, kut)) for c in nomzod]
        togri = next((c for c, s in sabablar if not s), None)
        if togri:
            qoldi.remove(togri)
        else:
            xato.append(f"{kut['tur']} {kut.get('harakat_tur', '')}: {sabablar[0][1]}")
            qoldi.remove(sabablar[0][0])
    xato += [f"ortiqcha: {c['tur']} {c.get('harakat_tur', '')}" for c in qoldi]
    return xato


async def yugur(od, tanlov):
    natija = []
    for n, (kim, gap, kut) in enumerate(holatlar(od), 1):
        if tanlov and n not in tanlov:
            continue
        o = odamlar.odam(od[kim])
        t = await ai.tushun(gap, o, ochiq_ishlar=ishlar.ishlar(odam_id=o["id"], faqat_ochiq=True))
        kartalar = panel_taklif.yasash(t, o)
        xato = tekshir(kartalar, kut)
        natija.append({"n": n, "kim": kim, "gap": gap, "xato": xato, "kartalar": kartalar, "ai": t})
        print(f"{n:2}. {'✓' if not xato else '✗'} [{kim}] {gap}" + (f"\n    ! {xato}" if xato else ""))
    return natija


def main():
    if not ai.yoqilganmi():
        sys.exit("MIYA_ANTHROPIC_KALIT kerak")
    tanlov = {int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if x.strip()}
    papka = tempfile.mkdtemp(prefix="miya-panel-nazorat-")
    od = nazorat.urug(os.path.join(papka, "n.db"))
    for nom, tur, narx in (("IP kamera 4MP", "mahsulot", 650_000), ("O'rnatish (1 kamera)", "xizmat", 150_000),
                           ("Videoregistrator 8 kanal", "mahsulot", 1_200_000), ("Kabel UTP", "mahsulot", 4_500)):
        buyurtma.katalog_saqla(None, od["boshliq"], nom, tur, "metr" if "Kabel" in nom else "dona", narx)
    od["eshik"] = baza.qiymat("SELECT id FROM ish WHERE nom='Eshik o''rnatish'")
    natija = asyncio.run(yugur(od, tanlov))
    sarf = baza.qiymat("SELECT COALESCE(SUM(narx),0) FROM ai_sarf") or 0
    print(f"Natija: {sum(1 for x in natija if not x['xato'])}/{len(natija)} · sarf ${sarf:.3f}")
    with open(os.path.join(papka, "natija.json"), "w") as f:
        json.dump(natija, f, ensure_ascii=False, indent=1, default=str)
    print("Batafsil:", os.path.join(papka, "natija.json"))


if __name__ == "__main__":
    main()
