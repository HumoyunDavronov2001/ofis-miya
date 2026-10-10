"""Nazorat savollari (S10, D-h): o'zgarmas namuna baza + 50 savol + qo'lda hisoblangan aniq javob.

Asbob rejimi (bepul, pytest bilan har o'zgarishda): kerakli asbob natijasida to'g'ri raqam bor, taqiqlangani yo'q.
To'liq rejim (haqiqiy Claude — pul sarflaydi, faqat ruxsat bilan):
    python3 sinov/nazorat.py --toliq
Namuna bazada «bugun» 2026-10-15 (payshanba) 12:00 ga qotirilgan — javoblar kalendarga bog'liq emas.
"""
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import ai, baza, hisob, ishlar, kurs, maosh, odamlar, usullar, vadalar, vaqt  # noqa: E402

BUGUN = (2026, 10, 15)


def payt(m: int, d: int, soat: int = 10) -> None:
    vaqt._siljish = datetime(2026, m, d, soat, 0, tzinfo=vaqt.TZ) - datetime.now(vaqt.TZ)


def _faol(hid: int, kim: int) -> int:
    if hisob.tasdiqla(hid, kim)["holat"] == "takror":
        hisob.faollashtir(hid, kim)
    return hid


def urug(yol: str) -> dict:
    """Namuna ishxona: 5 odam, 3 kassa, 4 mijoz, 1 ta'minotchi, oktabrning 1–14 kunlari."""
    kurs._olib_kel = lambda *a: None  # internetsiz — kurs bazadan
    payt(10, 1)
    baza.boshlash(yol)
    baza.sozlama_qoy("xodim_tasdiq", "0")  # namuna tarixi: yozuvlar darhol kiradi (R4 — test_chat_r4.py da)
    b = odamlar.odam_yarat("Rustam Aliyev", "boshliq")
    k = odamlar.odam_yarat("Dilnoza Qodirova", "kassir", kim_id=b, maosh_tolaydi=1)
    mn = odamlar.odam_yarat("Malika Yusupova", "menejer", kim_id=b)
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    d = odamlar.odam_yarat("Dilshod Rahimov", "xodim", kim_id=b)
    maosh.boshlangan_oy()
    kurs.kurs_qoy("2026-10-01", "USD", 12_000)
    asosiy = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", k, b)
    dollar = hisob.kassa_yarat("Dollar kassa", "naqd", "USD", k, b)
    chontak = hisob.kassa_yarat("Rustam cho'ntagi", "chontak", "UZS", b, b)
    odamlar.odam_tahrir(k, b, kassa_id=asosiy)
    for kassa_, summa in ((asosiy, 10_000_000), (dollar, 100_000), (chontak, 2_000_000)):
        hisob.tasdiqla(hisob.taklif("boshlangich_kassa", {"summa": summa, "kassa_id": kassa_, "valyuta":
                                                          "USD" if kassa_ == dollar else "UZS"}, b), b)
    maosh.shart_qoy(a, "oylik", 4_000_000, "UZS", "2026-10-01", b)
    maosh.shart_qoy(d, "kunbay", 200_000, "UZS", "2026-10-01", b)
    m = {}
    for ism in ("Anvar Karimov", "Botir Sobirov", "Gulnora Azimova", "Sardor Nazarov"):
        m[ism.split()[0]] = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES(?,?)", ism, vaqt.iso())
    olmos = baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES('Olmos savdo','taminotchi',?)", vaqt.iso())
    usullar.qosh("Konditsioner o'rnatish", "Ichki blok poldan kamida 2,2 metr balandda o'rnatiladi, quvur uzunligi "
                                           "5 metrgacha, vakuum 15 daqiqa tortiladi.", b)

    def chiqim(summa, tur, kim=k, kassa_=asosiy, valyuta="UZS"):
        return _faol(hisob.taklif("chiqim", {"summa": summa, "kassa_id": kassa_, "xarajat_turi": tur, "valyuta": valyuta},
                                  kim), kim)

    def sotuv(mijoz, summa, tolandi, muddat=None):
        p = {"summa": summa, "tolandi": tolandi, "mijoz_id": mijoz, "kassa_id": asosiy}
        if muddat:
            p["muddat"] = muddat
        sid, kid = hisob.sotuv_tuz(p, k)
        _faol(sid, k)
        if kid:
            _faol(kid, k)

    def avans(odam_, summa, tasdiq=True):
        hid = hisob.taklif("avans", {"summa": summa, "kassa_id": asosiy, "odam_id": odam_}, k)
        hisob.tasdiqla(hid, k)
        if tasdiq:
            hisob.tomon_tasdiq(hid, odam_, "oluvchi", True)

    payt(10, 2); chiqim(3_000_000, "Ijara")  # noqa: E702
    payt(10, 3); chiqim(300_000, "Benzin")  # noqa: E702
    payt(10, 4); sotuv(m["Botir"], 2_500_000, 2_500_000)  # noqa: E702
    payt(10, 5); avans(a, 1_000_000)  # noqa: E702
    payt(10, 6); chiqim(350_000, "Benzin")  # noqa: E702
    payt(10, 7); sotuv(m["Anvar"], 8_000_000, 3_000_000, "2026-10-20")  # noqa: E702 — 5 mln va'da
    payt(10, 8)
    chiqim(1_200_000, "Material")
    _faol(hisob.taklif("taminotchi_nasiya", {"summa": 6_000_000, "mijoz_id": olmos, "xarajat_turi": "Material",
                                             "muddat": "2026-10-25"}, b), b)
    payt(10, 9)
    _faol(hisob.taklif("kirim", {"summa": 2_000_000, "kassa_id": asosiy, "mijoz_id": m["Anvar"]}, k), k)
    chiqim(10_000, "Ehtiyot qism", kassa_=dollar, valyuta="USD")  # 100 $
    payt(10, 10)
    avans(d, 500_000)
    _faol(hisob.taklif("egasi_oldi", {"summa": 1_000_000, "kassa_id": chontak}, b), b)
    payt(10, 11); sotuv(m["Gulnora"], 4_000_000, 1_000_000, "2026-10-14")  # noqa: E702 — 3 mln va'da, buziladi
    payt(10, 12); avans(a, 500_000, tasdiq=False)  # noqa: E702 — Akmal hali «oldim» demagan
    payt(10, 13)
    _faol(hisob.taklif("taminotchiga_tolov", {"summa": 2_000_000, "kassa_id": asosiy, "mijoz_id": olmos}, k), k)
    _faol(hisob.taklif("boshlangich_mijoz", {"summa": 1_200_000, "mijoz_id": m["Sardor"]}, b), b)
    vadalar.yoz(m["Sardor"], "2026-10-15", b, summa=1_200_000)
    vadalar.yoz(m["Anvar"], "2026-10-16", b, tur="boshqa", matn_="Shartnoma nusxasini olib keladi")
    ishlar.ish_yarat("Eshik o'rnatish", [(a, 1)], b, muddat="2026-10-13", ish_turi="eshik")
    ishlar.ish_yarat("Konditsioner o'rnatish", [(a, 1)], b, muddat="2026-10-17", ish_turi="konditsioner")
    iid, _ = ishlar.ish_yarat("Pol yotqizish", [(d, 1)], b, muddat="2026-10-13", dalil_turi="yoq")
    ishlar.bajarildi_dedi(iid, d)
    gap = "Karimov bilan narxni metri 45 000 so'mdan kelishdik, ertaga olib ketadi"
    baza.bajar("INSERT INTO xabar(odam_id,tur,stt_matn,stt_sozlar,davomiylik,vaqt,holat) VALUES(?,?,?,?,?,?,?)", a, "ovoz",
               gap, json.dumps([{"soz": w, "dan": i * 0.7} for i, w in enumerate(gap.split())]), 9, vaqt.iso(), "ishlandi")
    payt(10, 14)
    hid = hisob.taklif("chiqim", {"summa": 150_000, "kassa_id": asosiy, "xarajat_turi": "Ofis"}, b)
    hisob.tasdiqla(hid, b)  # kassir hali «berdim» demagan
    maosh.kunlar_qoy(d, "2026-10", 10, b)
    payt(*BUGUN[1:], soat=12)
    return {"boshliq": b, "kassir": k, "menejer": mn, "xodim": a, "dilshod": d}


OY = {"dan": "2026-10-01", "gacha": "2026-10-15"}
# javob — asbob natijasida (va to'liq rejimda javob matnida) bo'lishi shart; yoq — bo'lmasligi shart
SAVOLLAR = [
    {"kim": "boshliq", "savol": "Asosiy kassada qancha pul bor?", "asbob": "kassalar", "javob": [9_650_000]},
    {"kim": "boshliq", "savol": "Dollar kassada necha dollar bor?", "asbob": "kassalar", "javob": [900]},
    {"kim": "boshliq", "savol": "Cho'ntagimda qancha pul qoldi?", "asbob": "kassalar", "javob": [1_000_000]},
    {"kim": "boshliq", "savol": "So'm kassalarida jami qancha pul bor?", "asbob": "kassalar", "javob": [10_650_000]},
    {"kim": "boshliq", "savol": "Asosiy kassadan tasdiq kutayotgan chiqim qancha?", "asbob": "kassalar", "javob": [150_000]},
    {"kim": "boshliq", "savol": "Akmalga shu oy qancha maosh hisoblandi?", "asbob": "xodim_hisobi",
     "param": {"ism": "Akmal"}, "javob": [4_000_000]},
    {"kim": "boshliq", "savol": "Akmal shu oy qancha avans oldi?", "asbob": "xodim_hisobi", "param": {"ism": "Akmal"},
     "javob": [1_000_000]},
    {"kim": "boshliq", "savol": "Akmalga hali qancha berishimiz kerak?", "asbob": "xodim_hisobi", "param": {"ism": "Akmal"},
     "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Akmal tasdiqlamagan avans qancha?", "asbob": "xodim_hisobi", "param": {"ism": "Akmal"},
     "javob": [500_000]},
    {"kim": "boshliq", "savol": "Dilshodga qancha qarzmiz?", "asbob": "xodim_hisobi", "param": {"ism": "Dilshod"},
     "javob": [1_500_000]},
    {"kim": "boshliq", "savol": "Dilshodga shu oy qancha ish haqi yozildi?", "asbob": "xodim_hisobi",
     "param": {"ism": "Dilshod"}, "javob": [2_000_000]},
    {"kim": "boshliq", "savol": "Dilshod oktabrda necha kun ishladi?", "asbob": "xodim_hisobi", "param": {"ism": "Dilshod"},
     "javob": [10]},
    {"kim": "boshliq", "savol": "Kimga qancha maosh to'lash kerak?", "asbob": "tolash_kerak",
     "javob": [3_000_000, 1_500_000]},
    {"kim": "boshliq", "savol": "Maosh kuniga qancha pul kerak bo'ladi?", "asbob": "maosh_bashorati", "javob": [4_500_000]},
    {"kim": "boshliq", "savol": "Maosh kuniga pul yetadimi, qo'lda qancha bor?", "asbob": "maosh_bashorati",
     "javob": [21_450_000]},
    {"kim": "boshliq", "savol": "Oktabrda qancha sotuv bo'ldi?", "asbob": "davr_jami", "param": OY, "javob": [14_500_000]},
    {"kim": "boshliq", "savol": "Oktabrda jami qancha xarajat qildik?", "asbob": "davr_jami", "param": OY,
     "javob": [12_200_000]},
    {"kim": "boshliq", "savol": "Oktabrda benzinga qancha ketdi?", "asbob": "davr_jami", "param": OY, "javob": [650_000]},
    {"kim": "boshliq", "savol": "Oktabrda materialga qancha ketdi?", "asbob": "davr_jami", "param": OY,
     "javob": [7_200_000]},
    {"kim": "boshliq", "savol": "Oktabrda ijaraga qancha to'ladik?", "asbob": "davr_jami", "param": OY, "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Oktabrda kassaga qancha pul tushdi?", "asbob": "davr_jami", "param": OY,
     "javob": [8_500_000]},
    {"kim": "boshliq", "savol": "Oktabrda kassadan qancha pul chiqdi?", "asbob": "davr_jami", "param": OY,
     "javob": [10_050_000]},
    {"kim": "boshliq", "savol": "Ehtiyot qismga so'mda qancha sarfladik?", "asbob": "davr_jami", "param": OY,
     "javob": [1_200_000]},
    {"kim": "boshliq", "savol": "5-oktabrdan 11-oktabrgacha qancha sotuv bo'ldi?", "asbob": "davr_jami",
     "param": {"dan": "2026-10-05", "gacha": "2026-10-11"}, "javob": [12_000_000]},
    {"kim": "boshliq", "savol": "Karimov bizga qancha qarz?", "asbob": "mijoz_qarzlari", "param": {"ism": "Karimov"},
     "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Gulnora Azimova qancha qarz?", "asbob": "mijoz_qarzlari", "param": {"ism": "Gulnora"},
     "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Sardorning qarzi qancha?", "asbob": "mijoz_qarzlari", "param": {"ism": "Sardor"},
     "javob": [1_200_000]},
    {"kim": "boshliq", "savol": "Olmos savdoga qancha qarzmiz?", "asbob": "mijoz_qarzlari",
     "param": {"ism": "Olmos", "taminotchi": True}, "javob": [4_000_000]},
    {"kim": "boshliq", "savol": "Bugun kim pul to'lashi kerak?", "asbob": "vadalar", "param": {"holat": "bugun"},
     "javob": [1_200_000]},
    {"kim": "boshliq", "savol": "Qaysi mijoz va'dasini bajarmadi?", "asbob": "vadalar", "param": {"holat": "buzilgan"},
     "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Karimovning va'dasidan qancha qoldi?", "asbob": "vadalar",
     "param": {"holat": "ochiq", "mijoz": "Karimov"}, "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Karimovga qo'ng'iroq qilaman — u haqida qisqa ayt", "asbob": "mijoz_haqida",
     "param": {"ism": "Karimov"}, "javob": [3_000_000]},
    {"kim": "boshliq", "savol": "Botir Sobirov oxirgi marta qanchaga xarid qildi?", "asbob": "mijoz_haqida",
     "param": {"ism": "Botir"}, "javob": [2_500_000]},
    {"kim": "boshliq", "savol": "Oxirgi xarajat qancha bo'ldi?", "asbob": "yozuvlar", "param": {"tur": "chiqim", "soni": 5},
     "javob": [150_000]},
    {"kim": "boshliq", "savol": "Akmalga qachon qancha avans berildi?", "asbob": "yozuvlar",
     "param": {"tur": "avans", "xodim": "Akmal"}, "javob": [1_000_000, 500_000]},
    {"kim": "boshliq", "savol": "Karimovdan qancha pul tushgan?", "asbob": "yozuvlar",
     "param": {"tur": "kirim", "mijoz": "Karimov"}, "javob": [3_000_000, 2_000_000]},
    {"kim": "boshliq", "savol": "14-oktabr kuni nima yozildi?", "asbob": "yozuvlar",
     "param": {"dan": "2026-10-14", "gacha": "2026-10-14"}, "javob": [150_000]},
    {"kim": "boshliq", "savol": "Ta'minotchiga oktabrda qancha to'ladik?", "asbob": "yozuvlar",
     "param": {"tur": "taminotchiga_tolov"}, "javob": [2_000_000]},
    {"kim": "boshliq", "savol": "Men kassadan o'zim uchun qancha oldim?", "asbob": "yozuvlar", "param": {"tur": "egasi_oldi"},
     "javob": [1_000_000]},
    {"kim": "boshliq", "savol": "Akmalning nechta ochiq ishi bor?", "asbob": "ishlar",
     "param": {"holat": "ochiq", "xodim": "Akmal"}, "javob": [2]},
    {"kim": "boshliq", "savol": "Nechta ish kechikyapti?", "asbob": "ishlar", "param": {"holat": "kechikkan"}, "javob": [1]},
    {"kim": "boshliq", "savol": "Konditsionerni qanday o'rnatamiz, vakuum necha daqiqa?", "asbob": "ish_usuli",
     "param": {"savol": "konditsioner o'rnatish"}, "javob": [15]},
    {"kim": "boshliq", "savol": "Karimov bilan narxni qanday kelishgan edik?", "asbob": "xabar_qidir",
     "param": {"sozlar": "Karimov narx"}, "javob": [45_000]},
    {"kim": "menejer", "savol": "Karimov qancha qarz?", "asbob": "mijoz_qarzlari", "param": {"ism": "Karimov"},
     "javob": [3_000_000]},
    {"kim": "kassir", "savol": "Asosiy kassada qancha bor?", "asbob": "kassalar", "javob": [9_650_000]},
    # R3 (08.10): faol xodim chatda boshliqdek ko'radi — avval bu uchtasi «ko'rsatilmasin» edi
    {"kim": "kassir", "savol": "Rustamning cho'ntagida qancha bor?", "asbob": "kassalar", "javob": [1_000_000]},
    {"kim": "kassir", "savol": "Kimga qancha maosh berishim kerak?", "asbob": "tolash_kerak",
     "javob": [3_000_000, 1_500_000]},
    {"kim": "kassir", "savol": "Akmalning oyligi qancha?", "asbob": "xodim_hisobi", "param": {"ism": "Akmal"},
     "javob": [4_000_000]},
    {"kim": "xodim", "savol": "Mening hisobim qancha, qancha olishim kerak?", "asbob": "mening_hisobim",
     "javob": [3_000_000, 500_000]},
    {"kim": "xodim", "savol": "Dilshodga qancha maosh beriladi?", "asbob": "xodim_hisobi", "param": {"ism": "Dilshod"},
     "javob": [1_500_000]},
]
assert len(SAVOLLAR) == 50


SOZ_SON = {"bir": 1, "bitta": 1, "ikki": 2, "ikkita": 2, "uch": 3, "uchta": 3, "to'rt": 4, "to'rtta": 4, "besh": 5,
           "beshta": 5}


def _soz_sonlar(matn_: str) -> list[float]:
    """«Bitta ish kechikyapti» — 1 (kichik sonlar so'z bilan yozilsa ham to'g'ri hisoblanadi)."""
    import re
    return [float(SOZ_SON[w]) for w in re.findall(r"[a-z']+", matn_.lower().replace("ʻ", "'").replace("’", "'"))
            if w in SOZ_SON]


def _bor(son: float, sonlar: list[float]) -> bool:
    return any(abs(son - x) <= 0.5 for x in sonlar)


def asbob_tekshir(odamlar_: dict) -> list[tuple[int, str]]:
    """Har savol uchun asbob natijasi. Qaytaradi: xatolar ro'yxati (raqam, sabab)."""
    xatolar = []
    for n, s in enumerate(SAVOLLAR, 1):
        o = ai.umumiy_korish(odamlar.odam(odamlar_[s["kim"]]))  # chatdagi kabi (R3)
        d = ai.asbob_bajar(o, s["asbob"], dict(s.get("param") or {}))
        if s.get("xato"):
            if "xato" not in d:
                xatolar.append((n, "huquqsiz ma'lumot berildi"))
            continue
        if "xato" in d:
            xatolar.append((n, d["xato"]))
            continue
        sonlar: list[float] = []
        ai._son_royxati(d, sonlar)
        for j in s["javob"]:
            if not _bor(j, sonlar):
                xatolar.append((n, f"{j} topilmadi"))
        for j in s.get("yoq", []):
            if _bor(j, sonlar):
                xatolar.append((n, f"{j} ko'rinmasligi kerak edi"))
    return xatolar


async def toliq_tekshir(odamlar_: dict) -> list[dict]:
    """Haqiqiy sun'iy intellekt bilan: javob matnidagi raqamlar."""
    natija = []
    faqat = {int(x) for x in os.environ.get("NAZORAT_FAQAT", "").split(",") if x.strip()}
    for n, s in enumerate(SAVOLLAR, 1):
        if faqat and n not in faqat:
            continue
        o = odamlar.odam(odamlar_[s["kim"]])
        r = await ai.sora(s["savol"], o)
        sonlar = [x for x, _ in ai._aniqlik(r["javob"])] + _soz_sonlar(r["javob"])
        xato = [f"{j} yo'q" for j in s["javob"] if not _bor(j, sonlar)]
        xato += [f"{j} chiqmasligi kerak edi" for j in s.get("yoq", []) if _bor(j, sonlar)]
        natija.append({"n": n, "savol": s["savol"], "javob": r["javob"], "qolip": r["qolip"], "xato": xato,
                       "chaqiruvlar": r.get("chaqiruvlar", [])})
        print(f"{n:2}. {'✓' if not xato else '✗'} {s['savol']}\n    → {r['javob'][:300]}"
              + (f"\n    ! {xato} · asboblar: {r.get('chaqiruvlar')}" if xato else ""))
    return natija


def main():
    papka = tempfile.mkdtemp(prefix="miya-nazorat-")
    odamlar_ = urug(os.path.join(papka, "nazorat.db"))
    xatolar = asbob_tekshir(odamlar_)
    print(f"Asbob rejimi: {50 - len({n for n, _ in xatolar})}/50" + "".join(f"\n  {n}: {s}" for n, s in xatolar))
    if "--toliq" in sys.argv:
        if not ai.yoqilganmi():
            sys.exit("Sun'iy intellekt kaliti yo'q (MIYA_ANTHROPIC_KALIT muhit o'zgaruvchisi)")
        natija = asyncio.run(toliq_tekshir(odamlar_))
        togri = sum(1 for x in natija if not x["xato"])
        sarf = baza.qiymat("SELECT COALESCE(SUM(narx),0) FROM ai_sarf") or 0
        print(f"To'liq rejim: {togri}/{len(natija)} · sarf ${sarf:.2f}")
        with open(os.path.join(papka, "natija.json"), "w") as f:
            json.dump(natija, f, ensure_ascii=False, indent=1)
        print("Natija:", os.path.join(papka, "natija.json"))


if __name__ == "__main__":
    main()
