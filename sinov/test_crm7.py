"""CRM7: chatdan buyurtma — tuzatish qoidalari, katalogdan moslash, web kartochka API, Telegram tugmalari."""
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import baza, buyurtma, odamlar, panel_taklif, tuzat, vaqt  # noqa: E402
from test_bot import bosish, ishla, muhit, natija, xabar  # noqa: E402,F401  (muhit — fixture)


def _katalog(b):
    kam = buyurtma.katalog_saqla(None, b, "IP kamera 4MP", "mahsulot", "dona", 650_000)
    dvr = buyurtma.katalog_saqla(None, b, "Videoregistrator 8 kanal", "mahsulot", "dona", 1_200_000)
    orn = buyurtma.katalog_saqla(None, b, "O'rnatish (1 kamera)", "xizmat", "dona", 150_000)
    return kam, dvr, orn


def _b(mijoz="", qatorlar=(), iqtibos="", **k):
    d = {"mijoz": mijoz, "qatorlar": [{"nom": n, "miqdor": m, "narx": p} for n, m, p in qatorlar], "manzil": "", "muddat": "",
         "izoh": "", "iqtibos": iqtibos}
    d.update(k)
    return d


def _ish(**k):
    d = {"nom": "", "ijrochilar": [], "joy": "", "mijoz": "", "muddat": "", "soat": "", "narx": 0, "valyuta": "aytilmagan",
         "ish_turi": "", "dalil": "aytilmagan", "iqtibos": ""}
    d.update(k)
    return d


def _yoz(**k):
    d = {"tur": "sotuv", "summa": 0, "birlik_noaniq": False, "valyuta": "UZS", "odam": "", "mijoz": "", "kassa": "",
         "kassa2": "", "xarajat_turi": "", "sana": "", "tolandi": 0, "muddat": "", "qoldan": False, "izoh": "", "iqtibos": ""}
    d.update(k)
    return d


def _bosh(**k):
    d = {"yozuvlar": [], "ishlar": [], "bajarildi": [], "davomat": [], "vadalar": [], "mijoz_eslatmalar": [], "xotira": [],
         "buyurtmalar": [], "muammo": "", "savol": "", "tushunilmadi": ""}
    d.update(k)
    return d


# ---------- tuzatish: takror bo'lmasin ----------

def test_tuzat_ijrochisiz_ornatish_ishi_va_malumot_takrorlanmaydi(muhit):
    gap = "Yangi mijoz Rustam, 8 ta kamera qo'yish kerak, ertaga Akmal borib o'lchasin"
    d = tuzat.tuzat(_bosh(
        buyurtmalar=[_b("Rustam", [("kamera", 8, 0)], iqtibos="8 ta kamera qo'yish kerak")],
        ishlar=[_ish(nom="8 ta kamera o'rnatish", mijoz="Rustam", iqtibos="8 ta kamera qo'yish kerak"),
                _ish(nom="O'lchash", ijrochilar=["Akmal"], mijoz="Rustam", iqtibos="ertaga Akmal borib o'lchasin")],
        xotira=[{"tur": "malumot", "matn": "Rustamga 8 ta kamera kerak", "sana": "", "soat": "", "kimga": "",
                 "iqtibos": "8 ta kamera qo'yish kerak"}],
        mijoz_eslatmalar=[{"mijoz": "Rustam", "matn": "Yangi mijoz, 8 ta kamera kerak",
                           "iqtibos": "Yangi mijoz Rustam, 8 ta kamera qo'yish kerak"}]), odamlar.odam(muhit.b), gap)
    assert len(d["buyurtmalar"]) == 1 and d["mijoz_eslatmalar"] == []
    assert [i["nom"] for i in d["ishlar"]] == ["O'lchash"]  # ijrochisi bor ish qoladi, o'rnatish — buyurtmaning o'zi
    assert d["xotira"] == []


def test_tuzat_sotilgan_buyurtma_emas_va_bosh_qator_tashlanadi(muhit):
    gap = "Sardorga 8 ta kamera sotdik, 2 mln berdi"
    d = tuzat.tuzat(_bosh(yozuvlar=[_yoz(summa=5_200_000, tolandi=2_000_000, mijoz="Sardor", iqtibos=gap)],
                          buyurtmalar=[_b("Sardor", [("kamera", 8, 0)], iqtibos=gap)]), odamlar.odam(muhit.b), gap)
    assert d["buyurtmalar"] == [] and d["yozuvlar"][0]["tur"] == "sotuv"
    d = tuzat.tuzat(_bosh(buyurtmalar=[_b("Sardor", [("", 2, 0)])]), odamlar.odam(muhit.b), "Sardor nimadir so'radi")
    assert d["buyurtmalar"] == [] and d["xotira"]  # bo'sh buyurtma tashlandi — gap xotiraga (R5)


def test_tuzat_boshqa_mijozsiz_ish_qoladi(muhit):
    d = tuzat.tuzat(_bosh(buyurtmalar=[_b("Rustam", [("IP kamera 4MP", 4, 0)], iqtibos="Rustamga 4 ta kamera kerak")],
                          ishlar=[_ish(nom="Ombor tozalash", iqtibos="omborni tozalash kerak")]),
                    odamlar.odam(muhit.b), "Rustamga 4 ta kamera kerak. Omborni tozalash kerak")
    assert [i["nom"] for i in d["ishlar"]] == ["Ombor tozalash"]


# ---------- kartochka: katalogdan dastur topadi ----------

def test_karta_katalogdan_narx_va_ornatish_soni(muhit):
    kam, dvr, orn = _katalog(muhit.b)
    c = panel_taklif.buyurtma_karta(_b("Rustam", [("IP kamera 4MP", 8, 0), ("o'rnatish", 0, 0), ("Kabel", 100, 4_000)]))
    q = {x["nom"]: x for x in c["qatorlar"]}
    assert q["IP kamera 4MP"]["katalog_id"] == kam and q["IP kamera 4MP"]["narx"] == 650_000
    assert q["O'rnatish (1 kamera)"]["katalog_id"] == orn and q["O'rnatish (1 kamera)"]["miqdor"] == 8  # har kameraga
    assert q["Kabel"]["katalog_id"] is None and q["Kabel"]["narx"] == 4_000  # katalogda yo'q — aytilgan narx bilan
    assert c["jami"] == 8 * 650_000 + 8 * 150_000 + 100 * 4_000
    # «videoregistratorlar» — qo'shimchali so'z ildizi bilan yagona mos; aytilgan narx katalog narxidan ustun
    c = panel_taklif.buyurtma_karta(_b("", [("videoregistratorlar", 2, 1_000_000)]))
    assert c["qatorlar"][0]["katalog_id"] == dvr and c["qatorlar"][0]["narx"] == 1_000_000
    # «kamera» — ikki qatorda bor (IP kamera, o'rnatish (1 kamera)): tanlanmaydi, nomzod beriladi
    c = panel_taklif.buyurtma_karta(_b("", [("kamera", 3, 0)]))
    x = c["qatorlar"][0]
    assert x["katalog_id"] is None and x["narx"] == 0 and {n["id"] for n in x["nomzodlar"]} == {kam, orn}


def test_yasash_buyurtma_kartasi_va_xodim_yaratadi(muhit):
    from miya import veb
    kam, _, orn = _katalog(muhit.b)
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Sardor Nematov',?)", vaqt.iso())
    k = panel_taklif.yasash(_bosh(buyurtmalar=[_b("Sardor Nematov", [("IP kamera 4MP", 4, 0)])]), odamlar.odam(muhit.a))
    assert k[0]["tur"] == "buyurtma" and k[0]["mijoz"]["id"] == mid
    veb.app.dependency_overrides[veb.joriy] = lambda: odamlar.odam(muhit.a)  # oddiy xodim — chat kartochkasidan
    try:
        c = TestClient(veb.app)
        c.headers["X-Miya"] = "1"
        r = c.post("/api/buyurtma", json={"mijoz_id": mid, "qatorlar": [{"katalog_id": kam, "miqdor": 4, "narx": 650000},
                                                                        {"katalog_id": orn, "miqdor": 4, "narx": 150000}]})
        assert r.status_code == 200, r.text
        b = buyurtma.bir(r.json()["id"])
        assert b["jami"] == 3_200_000 and b["masul_id"] == muhit.a and b["yaratgan_id"] == muhit.a
        x = baza.bir("SELECT matn FROM xabarnoma WHERE odam_id=? ORDER BY id DESC", muhit.b)
        assert f"Yangi buyurtma #{b['id']}" in x["matn"] and "Akmal" in x["matn"] and "3 200 000" in x["matn"].replace("\xa0", " ")
        # ishdan ketgan odam yarata olmaydi
        baza.bajar("UPDATE odam SET holat='ketgan' WHERE id=?", muhit.a)
        assert c.post("/api/buyurtma", json={"mijoz_id": mid, "qatorlar": [{"nom": "X", "miqdor": 1}]}).status_code == 403
    finally:
        veb.app.dependency_overrides.clear()


# ---------- Telegram: «✅ Yaratish / Bekor» ----------

def test_bot_buyurtma_yaratish(muhit):
    kam, _, orn = _katalog(muhit.b)
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Sardor Nematov',?)", vaqt.iso())
    muhit.ai.tushun_javob["kamera kerak"] = natija(buyurtmalar=[_b("Sardor Nematov", [("IP kamera 4MP", 8, 0), ("o'rnatish", 0, 0)],
                                                                   iqtibos="8 ta kamera kerak", manzil="Yunusobod 4")])
    ishla(muhit, xabar(103, "Sardor Nematovga 8 ta kamera kerak, o'rnatish bilan, Yunusobod 4"))
    k = muhit.tg.oxirgi(103)["matn"]
    assert "Buyurtma" in k and "IP kamera 4MP × 8" in k and "O'rnatish (1 kamera) × 8" in k and "6 400 000" in k
    assert baza.qiymat("SELECT COUNT(*) FROM ish") == 0  # o'rnatish ishi hozir berilmaydi
    data, msg = muhit.tg.tugma_data(103, "✅ Yaratish")
    ishla(muhit, bosish(103, data, msg))
    assert "yaratildi" in muhit.tg.oxirgi(103)["matn"]
    b = buyurtma.royxat()[0]
    assert b["mijoz_id"] == mid and b["jami"] == 6_400_000 and b["masul_id"] == muhit.a and b["manzil"] == "Yunusobod 4"
    assert baza.qiymat("SELECT COUNT(*) FROM xabarnoma WHERE odam_id=? AND matn LIKE 'Yangi buyurtma%'", muhit.b) == 1
    ishla(muhit, bosish(103, data, msg))  # ikkinchi bosish — takror buyurtma yo'q
    assert len(buyurtma.royxat()) == 1


def test_bot_yangi_mijoz_va_bekor(muhit):
    _katalog(muhit.b)
    muhit.ai.tushun_javob["Jasur"] = natija(buyurtmalar=[_b("Jasur", [("IP kamera 4MP", 2, 0)], iqtibos="Jasurga 2 ta kamera")])
    ishla(muhit, xabar(101, "Jasurga 2 ta kamera kerak"))
    assert "qaysi mijoz" in muhit.tg.oxirgi(101)["matn"]
    data, msg = muhit.tg.tugma_data(101, "Yangi mijoz: Jasur")
    ishla(muhit, bosish(101, data, msg))
    assert "Jasur" in muhit.tg.oxirgi(101)["matn"]
    data, msg = muhit.tg.tugma_data(101, "✅ Yaratish")
    ishla(muhit, bosish(101, data, msg))
    b = buyurtma.royxat()[0]
    assert b["mijoz"] == "Jasur" and b["masul_id"] is None and b["jami"] == 1_300_000
    assert baza.qiymat("SELECT COUNT(*) FROM xabarnoma WHERE matn LIKE 'Yangi buyurtma%'") == 0  # boshliq o'zi ochdi
    # bekor
    ishla(muhit, xabar(101, "Jasurga yana 2 ta kamera kerak"))
    data, msg = muhit.tg.tugma_data(101, "Bekor")
    ishla(muhit, bosish(101, data, msg))
    assert "yozilmadi" in muhit.tg.oxirgi(101)["matn"] and len(buyurtma.royxat()) == 1


def _v(**k):
    d = {"mijoz": "", "kim": "mijoz", "tur": "tolov", "summa": 0, "birlik_noaniq": False, "valyuta": "UZS", "muddat": "",
         "matn": "", "iqtibos": ""}
    d.update(k)
    return d


def test_belgi_ikkinchi_sorov_faqat_kerak_bolsa(muhit):
    from miya import ai
    _katalog(muhit.b)
    for gap in ("Sobirov 4 ta kamera narxini so'radi", "Rustamga 8 ta eshik kerak", "Videoregistrator so'rashdi",
                "Karimov buyurtma berdi"):
        assert ai.buyurtma_belgisi(gap), gap
    for gap in ("Benzinga 200 ming ketdi", "Akmalga 500 ming avans berdim", "ertaga bankka borishim kerak",
                "Gulnora 1 mln to'ladi"):
        assert not ai.buyurtma_belgisi(gap), gap


def test_tuzat_model_toyilishlari(muhit):
    """Haqiqiy AI nazoratida (09.10) uchragan: o'tgan zamon to'lovi va'da bo'lib, summasiz kirim takror, ta'minotchi bo'sh."""
    o = odamlar.odam(muhit.b)
    baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES('Olmos savdo','taminotchi',?)", vaqt.iso())
    d = tuzat.tuzat(_bosh(vadalar=[_v(mijoz="Gulnora", summa=1_000_000, iqtibos="Gulnora 1 mln to'ladi")]), o,
                    "Gulnora 1 mln to'ladi")
    assert d["vadalar"] == [] and [(y["tur"], y["summa"], y["mijoz"]) for y in d["yozuvlar"]] == [("kirim", 1_000_000, "Gulnora")]
    d = tuzat.tuzat(_bosh(vadalar=[_v(mijoz="Karimov", summa=2_000_000, muddat="2026-10-19", iqtibos="dushanba 2 mln beraman dedi")]),
                    o, "Karimov dushanba 2 mln beraman dedi")
    assert len(d["vadalar"]) == 1 and d["yozuvlar"] == []  # va'da — o'zgarmaydi
    gap = "Karimov 500 ming to'ladi, qolganini dushanba beradi"
    d = tuzat.tuzat(_bosh(yozuvlar=[_yoz(tur="kirim", summa=500_000, mijoz="Karimov", iqtibos="Karimov 500 ming to'ladi"),
                                    _yoz(tur="kirim", summa=0, mijoz="Karimov", iqtibos="qolganini dushanba beradi")],
                          vadalar=[_v(mijoz="Karimov", muddat="2026-10-19", iqtibos="qolganini dushanba beradi")]), o, gap)
    assert [y["summa"] for y in d["yozuvlar"]] == [500_000] and len(d["vadalar"]) == 1
    d = tuzat.tuzat(_bosh(yozuvlar=[_yoz(tur="chiqim", summa=2_000_000, iqtibos="Olmos savdoga 2 mln to'ladik")]), o,
                    "Olmos savdoga 2 mln to'ladik")
    assert d["yozuvlar"][0]["tur"] == "taminotchiga_tolov" and d["yozuvlar"][0]["mijoz"] == "Olmos savdo"
    d = tuzat.tuzat(_bosh(yozuvlar=[_yoz(tur="chiqim", summa=300_000, iqtibos="Ustaga 300 ming berdik")]), o, "Ustaga 300 ming berdik")
    assert d["yozuvlar"][0]["tur"] == "chiqim"  # ta'minotchi nomi yo'q — tegilmaydi


def test_tuzat_summasiz_kirim_vada_boladi(muhit):
    gap = "Karimov 500 ming to'ladi, qolganini dushanba beradi"
    d = tuzat.tuzat(_bosh(yozuvlar=[_yoz(tur="kirim", summa=500_000, mijoz="Karimov", iqtibos="Karimov 500 ming to'ladi"),
                                    _yoz(tur="kirim", summa=0, mijoz="Karimov", muddat="2026-10-19",
                                         iqtibos="qolganini dushanba beradi")]), odamlar.odam(muhit.b), gap)
    assert [y["summa"] for y in d["yozuvlar"]] == [500_000]
    assert [(v["mijoz"], v["tur"], v["summa"]) for v in d["vadalar"]] == [("Karimov", "tolov", 0)]
