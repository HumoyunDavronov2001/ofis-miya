"""Panel «miya» qatori: savol ham, topshiriq ham. Sun'iy intellekt soxta — tarmoqsiz, pulsiz."""
import os
import sys
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import ai, baza, hisob, maosh, odamlar, panel_taklif, vadalar, vaqt  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    vaqt._siljish = timedelta(0)
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Sardor Aliyev", "boshliq")
    k = odamlar.odam_yarat("Dilnoza Qodirova", "kassir", kim_id=b, maosh_tolaydi=1)
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", k, b)
    maosh.boshlangan_oy()
    hisob.tasdiqla(hisob.taklif("boshlangich_kassa", {"summa": 5_000_000, "kassa_id": kassa}, b), b)
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    hisob.tasdiqla(hisob.taklif("boshlangich_mijoz", {"summa": 3_000_000, "mijoz_id": mid}, b), b)
    from miya import veb
    yield {"b": b, "k": k, "a": a, "kassa": kassa, "m": mid, "veb": veb}
    veb.app.dependency_overrides.clear()
    vaqt._siljish = timedelta(0)


def klient(ish, kim):
    ish["veb"].app.dependency_overrides[ish["veb"].joriy] = lambda: odamlar.odam(kim)
    c = TestClient(ish["veb"].app)
    c.headers["X-Miya"] = "1"
    return c


def soxta_ai(monkeypatch, natija=None, javob="Javob"):
    chaqiruv = []

    async def tushun(matn_, o, **k):
        chaqiruv.append(("tushun", matn_))
        return natija or {}

    async def sora(matn_, o, tarix=None):
        chaqiruv.append(("sora", matn_))
        return {"javob": javob, "qolip": False, "manbalar": [("mijoz_qarzlari", {})]}
    monkeypatch.setattr(ai, "tushun", tushun)
    monkeypatch.setattr(ai, "sora", sora)
    return chaqiruv


GAP = {"yozuvlar": [{"tur": "kirim", "summa": 2_000_000, "valyuta": "UZS", "mijoz": "Karimov",
                     "iqtibos": "Karimov 2 mln to'ladi"}],
       "vadalar": [{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "muddat": "2026-10-16",
                    "iqtibos": "qolganini juma kuni beradi"}],
       "ishlar": [{"nom": "10 ta kamera o'rnatish", "ijrochilar": ["Akmal", "Bahodir"], "mijoz": "Rustam",
                   "muddat": "2026-10-09", "narx": 2_000_000, "ish_turi": "Kamera"}],
       "mijoz_eslatmalar": [{"mijoz": "Karimov", "matn": "Faqat kechqurun qo'ng'iroq qilinsin"}]}


def test_kartochkalar_ismlarni_dastur_topadi(ish):
    k = panel_taklif.yasash(GAP, odamlar.odam(ish["b"]))
    assert [x["tur"] for x in k] == ["pul", "ish", "vada", "eslatma"]
    pul, ish_, vada, esl = k
    assert pul["mijoz"] == {"id": ish["m"], "ism": "Anvar Karimov"}
    ozi = [x["id"] for x in hisob.kassalar() if x["masul_id"] == ish["b"]]
    assert pul["kassa_id"] == ozi[0]  # bot kabi: boshliq aytsa — o'z kassasi (kartochkada o'zgartiriladi)
    assert ish_["ijrochilar"] == [{"id": ish["a"], "ism": "Akmal Toshpo'latov"}]
    assert ish_["nomalum"][0]["aytilgan"] == "Bahodir"
    assert ish_["mijoz"]["yangi"] == "Rustam" and "id" not in ish_["mijoz"]  # bazada yo'q — yangi mijoz taklifi
    assert ish_["ish_turi"] == "kamera" and ish_["ruxsat"]
    # «qolganini» — summa aytilmagan: 3 mln qarz − shu gapdagi 2 mln to'lov
    assert vada["summa"] == 1_000_000 and vada["izoh"]
    assert esl["mijoz"]["id"] == ish["m"]


def test_xodim_boshliq_turini_yoza_olmaydi(ish):
    k = panel_taklif.yasash({"yozuvlar": [{"tur": "bonus", "summa": 100_000, "odam": "Akmal"}]}, odamlar.odam(ish["a"]))
    assert k[0]["ruxsat"] is False and k[0]["odam"]["id"] == ish["a"]


def test_savol_toglidan_toglri_javobga(ish, monkeypatch):
    ch = soxta_ai(monkeypatch)
    r = klient(ish, ish["b"]).post("/api/miya", json={"matn": "Karimov qancha qarz?"}).json()
    assert r["tur"] == "javob" and ch == [("sora", "Karimov qancha qarz?")]  # tushun chaqirilmaydi — pul tejaladi


def test_topshiriq_kartochka_qaytaradi_va_hech_narsa_yozmaydi(ish, monkeypatch):
    soxta_ai(monkeypatch, GAP)
    oldin = baza.qiymat("SELECT COUNT(*) FROM harakat")
    r = klient(ish, ish["b"]).post("/api/miya", json={"matn": "Karimov 2 mln to'ladi, qolganini juma beradi"}).json()
    assert r["tur"] == "takliflar" and len(r["takliflar"]) == 4
    assert baza.qiymat("SELECT COUNT(*) FROM harakat") == oldin  # K3: tasdiqsiz yozilmaydi
    assert baza.qiymat("SELECT COUNT(*) FROM ish") == 0 and baza.qiymat("SELECT COUNT(*) FROM vada") == 0


def test_tushunilmadi_va_faqat_savol(ish, monkeypatch):
    soxta_ai(monkeypatch, {"tushunilmadi": "Raqam yo'q"})
    c = klient(ish, ish["b"])
    assert c.post("/api/miya", json={"matn": "salom dunyo"}).json() == {"tur": "tushunilmadi", "sabab": "Raqam yo'q"}
    ch = soxta_ai(monkeypatch, {"savol": "Akmal nechta ish qildi"})
    assert c.post("/api/miya", json={"matn": "Akmal ishlari"}).json()["tur"] == "javob" and ch[-1][0] == "sora"
    assert c.post("/api/miya", json={"matn": "  "}).status_code == 400


def test_tasdiqlash_zanjiri_panel_kabi(ish, monkeypatch):
    """Panel «Tasdiqlash» tartibi: yangi mijoz → pul → ish → va'da → eslatma. To'lov va'dadan oldin tushadi,
    shuning uchun yangi va'daga hisoblanmaydi."""
    soxta_ai(monkeypatch, GAP)
    c = klient(ish, ish["b"])
    pul, ish_, vada, esl = c.post("/api/miya", json={"matn": "x"}).json()["takliflar"]
    yangi = c.post("/api/mijoz", json={"ism": ish_["mijoz"]["yangi"], "tur": "mijoz"}).json()["id"]
    r = c.post("/api/harakat", json={"tur": "kirim", "summa": pul["summa"], "valyuta": "UZS", "kassa_id": pul["kassa_id"],
                                     "mijoz_id": pul["mijoz"]["id"], "sana": pul["sana"]}).json()
    assert r["holat"] == "faol"
    iid = c.post("/api/ish", json={"nom": ish_["nom"], "ijrochilar": [{"odam_id": ish["a"], "ulush": 1}], "mijoz_id": yangi,
                                   "muddat": ish_["muddat"], "narx": ish_["narx"], "ish_turi": ish_["ish_turi"]}).json()["id"]
    vid = c.post("/api/vada", json={"mijoz_id": ish["m"], "kim": "mijoz", "tur": "tolov", "summa": vada["summa"],
                                    "valyuta": "UZS", "muddat": vada["muddat"]}).json()["id"]
    c.post(f"/api/mijoz/{ish['m']}/eslatma", json={"matn": esl["matn"]}).raise_for_status()
    assert baza.bir("SELECT mijoz_id, narx FROM ish WHERE id=?", iid) == {"mijoz_id": yangi, "narx": 2_000_000}
    assert hisob.qoldiq(f"mijoz:{ish['m']}")["UZS"] == 1_000_000
    assert baza.qiymat("SELECT summa FROM vada WHERE id=?", vid) == 1_000_000
    assert vadalar.holatlar(ish["m"])[vid]["qoplandi"] == 0  # 2 mln to'lov eski qarzga ketdi, yangi va'daga emas


def test_sotuv_muddati_vadaga_takrorlanmaydi(ish):
    """Sotuvning qarz muddati sotuvning o'zida — faollashganda va'da o'zi yoziladi; ikkinchi va'da kartochkasi chiqmaydi."""
    gap = {"yozuvlar": [{"tur": "sotuv", "summa": 2_000_000, "tolandi": 500_000, "mijoz": "Karimov"}],
           "vadalar": [{"mijoz": "Anvar Karimov", "kim": "mijoz", "tur": "tolov", "summa": 1_500_000, "muddat": "2026-10-25"}]}
    k = panel_taklif.yasash(gap, odamlar.odam(ish["b"]))
    assert [x["tur"] for x in k] == ["pul"] and k[0]["muddat"] == "2026-10-25"
    # boshqa mijozning va'dasi yoki «biz» va'dasi qoladi
    gap["vadalar"].append({"mijoz": "Karimov", "kim": "biz", "tur": "boshqa", "muddat": "2026-10-16", "matn": "eshik olib boramiz"})
    assert [x["tur"] for x in panel_taklif.yasash(gap, odamlar.odam(ish["b"]))] == ["pul", "vada"]


def test_ish_tugadi_nomidan_topiladi(ish):
    from miya import ishlar
    eshik, _ = ishlar.ish_yarat("Eshik o'rnatish", [(ish["a"], 1)], ish["b"], dalil_turi="rasm")
    ishlar.ish_yarat("Konditsioner o'rnatish", [(ish["a"], 1)], ish["b"])
    k = panel_taklif.yasash({"bajarildi": [{"ish_id": 0, "nom": "eshik", "izoh": "", "iqtibos": "eshik ishi tugadi"}]},
                            odamlar.odam(ish["b"]))
    assert k[0]["tur"] == "bajarildi" and k[0]["ish_id"] == eshik and k[0]["ruxsat"]
    r = klient(ish, ish["b"]).post(f"/api/ish/{eshik}/amal", json={"amal": "bajarildi"}).json()
    assert r["holat"] == "bajarildi"  # boshliq panelda yopsa — dalil o'rniga «panelda tasdiqladi»
    # xodim panelda yopa olmaydi (botda rasm bilan)
    assert panel_taklif.yasash({"bajarildi": [{"ish_id": 0, "nom": "konditsioner", "izoh": "", "iqtibos": ""}]},
                               odamlar.odam(ish["a"]))[0]["ruxsat"] is False


def test_salom_claude_chaqirmaydi(ish, monkeypatch):
    ch = soxta_ai(monkeypatch, {"tushunilmadi": "x"})
    c = klient(ish, ish["b"])
    for gap in ("salom", "Rahmat!", "ok"):
        assert c.post("/api/miya", json={"matn": gap}).json()["tur"] == "tushunilmadi"
    assert ch == []
    soxta_ai(monkeypatch, {"davomat": [{"tur": "keldi", "sana": "", "izoh": ""}]})
    r = c.post("/api/miya", json={"matn": "ishga keldim"}).json()  # R9: web chatda ham davomat belgilanadi
    assert r["tur"] == "xotira" and r["xotira"][0]["matn"].startswith("Keldingiz")


# ---------- tuzat: model chalkashligini dastur tuzatadi (bot ham, panel ham) ----------

def _bosh(**k):
    d = {"yozuvlar": [], "ishlar": [], "bajarildi": [], "davomat": [], "vadalar": [], "mijoz_eslatmalar": [],
         "muammo": "", "savol": "", "tushunilmadi": ""}
    d.update(k)
    return d


def test_tuzat_mijoz_va_taminotchi_yonalishi(ish):
    from miya import tuzat
    baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES('Olmos savdo','taminotchi',?)", vaqt.iso())
    b = odamlar.odam(ish["b"])
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "kirim", "summa": 2_000_000, "mijoz": "Olmos"},
                                    {"tur": "taminotchi_nasiya", "summa": 4_000_000, "mijoz": "Karimov"},
                                    {"tur": "kirim", "summa": 1_000_000, "mijoz": "Karimov"}]), b)
    assert [y["tur"] for y in d["yozuvlar"]] == ["taminotchiga_tolov", "sotuv", "kirim"]


def test_tuzat_xodim_oldim_qolida(ish):
    from miya import tuzat
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "kirim", "summa": 1_000_000, "mijoz": "Karimov", "odam": "", "kassa": ""}]),
                    odamlar.odam(ish["a"]))
    assert d["yozuvlar"][0]["tur"] == "mijozdan_qolga" and d["yozuvlar"][0]["odam"] == "men"
    # kassir (o'z kassasi bor) — kassaga kirim bo'lib qoladi
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "kirim", "summa": 1_000_000, "mijoz": "Karimov", "kassa": ""}]),
                    odamlar.odam(ish["k"]))
    assert d["yozuvlar"][0]["tur"] == "kirim"


def test_tuzat_vada_va_sana(ish):
    from miya import tuzat
    b = odamlar.odam(ish["b"])
    bugun = vaqt.bugun()
    otgan_dush = (bugun - timedelta(days=3)).isoformat()  # model o'tgan haftaning o'sha kunini olgan
    kun = vaqt.HAFTA[(bugun - timedelta(days=3)).weekday()]
    d = tuzat.tuzat(_bosh(vadalar=[{"mijoz": "Karimov", "kim": "biz", "tur": "boshqa", "summa": 2_000_000,
                                     "muddat": otgan_dush}],
                          ishlar=[{"nom": "Kamera", "muddat": otgan_dush, "joy": "Gulnoraning do'koni"}],
                          mijoz_eslatmalar=[{"mijoz": "Jasur", "matn": "Yangi mijoz."},
                                            {"mijoz": "Gulnora", "matn": "Do'koni mavjud", "iqtibos": "Gulnoraning do'koni"},
                                            {"mijoz": "Jasur", "matn": "Faqat naqd to'laydi"}]),
                    b, f"Karimov {kun} 2 mln beraman dedi, Akmal {kun}ga borsin")
    v = d["vadalar"][0]
    assert (v["tur"], v["kim"]) == ("tolov", "mijoz")
    kelasi = (date.fromisoformat(otgan_dush) + timedelta(days=7)).isoformat()
    assert v["muddat"] == kelasi and d["ishlar"][0]["muddat"] == kelasi
    assert [e["matn"] for e in d["mijoz_eslatmalar"]] == ["Faqat naqd to'laydi"]
    # «kecha to'lashi kerak edi» — hafta kuni aytilmagan: sana o'zgarmaydi
    kecha = (bugun - timedelta(days=1)).isoformat()
    d = tuzat.tuzat(_bosh(vadalar=[{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 1, "muddat": kecha}]),
                    b, "Karimov kecha to'lashi kerak edi")
    assert d["vadalar"][0]["muddat"] == kecha


def test_tuzat_sotuv_vadasi_birlashadi(ish):
    from miya import tuzat
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "sotuv", "summa": 4_000_000, "mijoz": "Karimov", "muddat": ""}],
                          vadalar=[{"mijoz": "Anvar Karimov", "kim": "biz", "tur": "tolov", "summa": 4_000_000,
                                    "muddat": "2026-10-25"}]), odamlar.odam(ish["b"]))
    assert d["vadalar"] == [] and d["yozuvlar"][0]["muddat"] == "2026-10-25"


def test_tuzat_summasiz_sotuv_tolov_boladi(ish):
    """Haiku uzun gapda «Karimov 500 ming to'ladi, qolganini dushanba» ni summasiz sotuv deb yozgan (haqiqiy hodisa)."""
    from miya import tuzat
    b = odamlar.odam(ish["b"])
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "kirim", "summa": 500_000, "mijoz": "Karimov"},
                                    {"tur": "sotuv", "summa": 0, "tolandi": 500_000, "mijoz": "Karimov", "muddat": "2026-10-19"},
                                    {"tur": "sotuv", "summa": 1_200_000, "tolandi": 1_200_000, "mijoz": "Sobirov",
                                     "muddat": "2026-10-19"}]), b)
    assert [(y["tur"], y["summa"], y.get("muddat")) for y in d["yozuvlar"]] == [
        ("kirim", 500_000, None), ("sotuv", 1_200_000, "")]  # naqd sotuvga boshqa mijozning muddati yopishmaydi
    assert [(v["mijoz"], v["tur"], v["muddat"]) for v in d["vadalar"]] == [("Karimov", "tolov", "2026-10-19")]
    # kirim yo'q bo'lsa — summasiz sotuv kirimga aylanadi
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "sotuv", "summa": 0, "tolandi": 500_000, "mijoz": "Karimov", "muddat": ""}]), b)
    assert (d["yozuvlar"][0]["tur"], d["yozuvlar"][0]["summa"]) == ("kirim", 500_000) and d["vadalar"] == []


def test_tuzat_aytilmagan_raqam_va_soxta_sotuv(ish):
    """Haqiqiy hodisa: «Karimov 500 ming to'ladi, qolganini dushanba» → model sotuv 500/500 va va'da 700 ming (o'zi
    hisoblagan) qaytardi. To'lov kirim bo'ladi, aytilmagan 700 ming olib tashlanadi — qoldiqni dastur hisoblaydi."""
    from miya import tuzat
    gap = "Bugun Karimov 500 ming to'ladi, qolganini dushanba beradi. Sobirovga 2 ta kamera sotdik 1,2 mln naqd."
    d = tuzat.tuzat(_bosh(
        yozuvlar=[{"tur": "sotuv", "summa": 500_000, "tolandi": 500_000, "mijoz": "Karimov",
                   "iqtibos": "Bugun Karimov 500 ming to'ladi, qolganini dushanba beradi"},
                  {"tur": "sotuv", "summa": 1_200_000, "tolandi": 1_200_000, "mijoz": "Sobirova",
                   "iqtibos": "Sobirovga 2 ta kamera sotdik 1,2 mln naqd"}],
        vadalar=[{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 700_000, "muddat": "2026-10-19"}]),
        odamlar.odam(ish["b"]), gap)
    assert [(y["tur"], y["summa"]) for y in d["yozuvlar"]] == [("kirim", 500_000), ("sotuv", 1_200_000)]
    assert d["vadalar"][0]["summa"] == 0
    # aytilgan summa saqlanadi; so'z bilan aytilgan (raqamsiz) gapda tekshirilmaydi
    d = tuzat.tuzat(_bosh(vadalar=[{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 1_500_000, "muddat": ""}]),
                    odamlar.odam(ish["b"]), "Karimov 1,5 mln juma beradi")
    assert d["vadalar"][0]["summa"] == 1_500_000
    d = tuzat.tuzat(_bosh(vadalar=[{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 500_000, "muddat": ""}]),
                    odamlar.odam(ish["b"]), "Karimov besh yuz ming juma beradi")
    assert d["vadalar"][0]["summa"] == 500_000


def test_tuzat_ish_narxi_alohida_ishbay_emas(ish):
    from miya import tuzat
    d = tuzat.tuzat(_bosh(ishlar=[{"nom": "Eshik", "ijrochilar": ["Akmal"], "narx": 300_000},
                                  {"nom": "Kamera", "ijrochilar": ["Akmal"], "narx": 600_000, "mijoz": "Sobirova",
                                   "iqtibos": "Akmal ertaga Sobirovning ofisiga 3 ta kamera o'rnatsin, 600 ming"}],
                          yozuvlar=[{"tur": "ishbay", "summa": 300_000, "odam": "Akmal"},
                                    {"tur": "sotuv", "summa": 600_000, "mijoz": "Sobir", "iqtibos": "600 ming"},
                                    {"tur": "avans", "summa": 200_000, "odam": "Akmal"}]), odamlar.odam(ish["b"]))
    assert [(y["tur"], y["summa"]) for y in d["yozuvlar"]] == [("avans", 200_000)]


def test_tuzat_taminotchiga_tolov_sotuv_deb_oqilsa(ish):
    """Haqiqiy hodisa: «Olmos savdoga 2 mln to'ladik» → model: sotuv 2 mln (to'liq to'langan), mijoz «Olmos»."""
    from miya import tuzat
    baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES('Olmos savdo','taminotchi',?)", vaqt.iso())
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "sotuv", "summa": 2_000_000, "tolandi": 2_000_000, "mijoz": "Olmos",
                                     "iqtibos": "Olmos savdoga 2 mln to'ladik"}]), odamlar.odam(ish["b"]))
    assert (d["yozuvlar"][0]["tur"], d["yozuvlar"][0]["summa"]) == ("taminotchiga_tolov", 2_000_000)


def test_tuzat_hafta_kuni_sanasi(ish):
    """Haqiqiy hodisa: «qolganini dushanba beradi» → model seshanba sanasini qaytardi."""
    from miya import tuzat
    b, bugun = odamlar.odam(ish["b"]), vaqt.bugun()
    dush = (bugun + timedelta(days=(0 - bugun.weekday()) % 7)).isoformat()
    xato = (date.fromisoformat(dush) + timedelta(days=1)).isoformat()
    d = tuzat.tuzat(_bosh(vadalar=[{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 0, "muddat": xato,
                                    "iqtibos": "qolganini dushanba beradi"}],
                          ishlar=[{"nom": "Eshik", "muddat": "2026-10-25", "iqtibos": "25-oktabrda eshik"}]),
                    b, "Karimov to'ladi, qolganini dushanba beradi. Akmal 25-oktabrda eshik o'rnatsin, juma kuni ham")
    assert d["vadalar"][0]["muddat"] == dush
    assert d["ishlar"][0]["muddat"] == "2026-10-25"  # aniq sana — tegilmaydi (parchada hafta kuni yo'q, gapda ikkita)


def test_tuzat_aniq_sana_gapdagi_hafta_kunidan_ozgarmaydi(ish):
    from miya import tuzat
    bugun = vaqt.bugun()
    yaqin = (bugun + timedelta(days=3)).isoformat()  # 14 kun ichidagi aniq sana
    kun_soz = f"{date.fromisoformat(yaqin).day}-{vaqt.OYLAR[date.fromisoformat(yaqin).month - 1]}da"
    d = tuzat.tuzat(_bosh(ishlar=[{"nom": "Eshik", "muddat": yaqin, "iqtibos": "eshik o'rnatsin"}],
                          vadalar=[{"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 0,
                                    "muddat": yaqin, "iqtibos": "qolganini beradi"}]),
                    odamlar.odam(ish["b"]), f"Karimov qolganini juma beradi, Akmal {kun_soz} eshik o'rnatsin")
    assert d["ishlar"][0]["muddat"] == yaqin


def test_tuzat_ertaga_boshqa_hafta_kuniga_surilmaydi(ish):
    """Haqiqiy hodisa: «Akmal ertaga ... o'rnatsin» + gapda boshqa joyda «dushanba» — ertaga qolishi kerak."""
    from miya import tuzat
    ertaga = (vaqt.bugun() + timedelta(days=1)).isoformat()
    d = tuzat.tuzat(_bosh(ishlar=[{"nom": "Kamera", "muddat": ertaga, "iqtibos": "Akmal ertaga soat 10 da kamera o'rnatsin"}]),
                    odamlar.odam(ish["b"]), "Karimov qolganini dushanba beradi. Akmal ertaga soat 10 da kamera o'rnatsin")
    assert d["ishlar"][0]["muddat"] == ertaga


def test_tuzat_raqamsiz_parchadan_sotuv_va_puldan_eslatma(ish):
    """Haqiqiy hodisalar: «qolganini dushanba beradi» → sotuv 1,2 mln (Sobirovning summasi); «1,2 mln naqd» → eslatma."""
    from miya import tuzat
    d = tuzat.tuzat(_bosh(
        yozuvlar=[{"tur": "kirim", "summa": 500_000, "mijoz": "Karimov", "iqtibos": "500 ming to'ladi"},
                  {"tur": "sotuv", "summa": 1_200_000, "tolandi": 0, "mijoz": "Karimov", "muddat": "2026-10-19",
                   "iqtibos": "qolganini dushanba beradi"},
                  {"tur": "sotuv", "summa": 1_200_000, "tolandi": 1_200_000, "mijoz": "Sobirov",
                   "iqtibos": "Sobirovga 2 ta kamera sotdik 1,2 mln naqd"}],
        mijoz_eslatmalar=[{"mijoz": "Sobirov", "matn": "Naqd to'laydi", "iqtibos": "Sobirovga 2 ta kamera sotdik 1,2 mln naqd"}]),
        odamlar.odam(ish["b"]))
    assert [(y["tur"], y["mijoz"]) for y in d["yozuvlar"]] == [("kirim", "Karimov"), ("sotuv", "Sobirov")]
    assert [(v["mijoz"], v["summa"], v["muddat"]) for v in d["vadalar"]] == [("Karimov", 0, "2026-10-19")]
    assert d["mijoz_eslatmalar"] == []
    # «besh yuz ming lik eshik oldi, pulini juma beradi» — so'z bilan aytilgan summa: sotuv qoladi
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "sotuv", "summa": 500_000, "tolandi": 0, "mijoz": "Karimov", "muddat": "2026-10-19",
                                     "iqtibos": "besh yuz ming lik eshik oldi, pulini juma beradi"}]), odamlar.odam(ish["b"]))
    assert d["yozuvlar"][0]["tur"] == "sotuv"


def test_tuzat_bosh_yozuv_tashlanadi(ish):
    from miya import tuzat
    d = tuzat.tuzat(_bosh(yozuvlar=[{"tur": "sotuv", "summa": 0, "tolandi": 0, "mijoz": "Gulnora", "iqtibos": ""},
                                    {"tur": "avans", "summa": 0, "odam": "Akmal", "iqtibos": "Akmalga avans berdim"}]),
                    odamlar.odam(ish["b"]))
    assert [y["tur"] for y in d["yozuvlar"]] == ["avans"]  # summasi aytilmagan, lekin gapda bor — so'raladi


def test_ishni_boshlash_yoriqnomasi(ish):
    c = klient(ish, ish["b"])
    q = {x["k"]: x for x in c.get("/api/bugun").json()["boshlash"]}
    assert list(q) == ["tg", "xodim", "kassa", "mijoz", "maosh", "ovoz"]
    # namunada: xodim, boshlang'ich kassa va mijoz bor; Telegram, maosh va ovoz — yo'q
    assert {k for k, x in q.items() if x["bajarildi"]} == {"xodim", "kassa", "mijoz"}
    assert q["kassa"]["misol"].startswith("Asosiy kassa")  # cho'ntak emas, haqiqiy kassa nomi
    baza.bajar("UPDATE odam SET tg_id=777 WHERE id=?", ish["b"])
    maosh.shart_qoy(ish["a"], "oylik", 4_000_000, "UZS", vaqt.bugun().isoformat(), ish["b"])
    q = {x["k"]: x for x in c.get("/api/bugun").json()["boshlash"]}
    assert not q["ovoz"]["bajarildi"] and q["tg"]["bajarildi"] and q["maosh"]["bajarildi"]
    assert "boshlash" not in klient(ish, ish["a"]).get("/api/bugun").json()  # faqat boshliqqa
