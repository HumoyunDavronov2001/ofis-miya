"""R5–R8: umumiy xotira — uchrashuv, eslatma, ma'lumot; eslatish vaqtini dastur hisoblaydi; «tushunarsiz» yo'q."""
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import ai, baza, odamlar, tuzat, vaqt, xotira  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    # bugun 2026-10-15 payshanba 09:00 (Toshkent)
    vaqt._siljish = timedelta(0)
    vaqt._siljish = datetime(2026, 10, 15, 9, 0, tzinfo=vaqt.TZ) - vaqt.hozir()
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Sardor Aliyev", "boshliq")
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    from miya import veb
    yield {"b": b, "a": a, "veb": veb}
    veb.app.dependency_overrides.clear()
    vaqt._siljish = timedelta(0)


def test_eslatish_vaqti_qoidasi(ish):
    assert xotira.eslat_vaqti("2026-10-16", "11:00").startswith("2026-10-16T10:00")  # 1 soat oldin
    assert xotira.eslat_vaqti("2026-10-15", "09:30").startswith("2026-10-15T09:15")  # 1 soat o'tgan — 15 daqiqa oldin
    assert xotira.eslat_vaqti("2026-10-15", "09:10").startswith("2026-10-15T09:10")  # 15 daqiqa ham o'tgan — o'z vaqtida
    assert xotira.eslat_vaqti("2026-10-15", "08:50") is None  # voqea o'tib ketgan — eslatilmaydi
    # «20 daqiqadan keyin eslat», «soat 15 da qo'ng'iroq qilishni eslat» — aynan o'sha vaqtda
    assert xotira.eslat_vaqti("2026-10-15", "09:20", "eslatma").startswith("2026-10-15T09:20")
    assert xotira.eslat_vaqti("2026-10-15", "15:00", "eslatma").startswith("2026-10-15T15:00")
    assert xotira.eslat_vaqti("2026-10-17", None).startswith("2026-10-17T08:30")  # faqat kun — ertalabki xulosa vaqti
    assert xotira.eslat_vaqti("2026-10-15", None) is None  # bugun, ertalab o'tgan
    assert xotira.eslat_vaqti(None, None) is None  # ma'lumot — eslatilmaydi


def test_saqlash_tasdiq_va_eslatish(ish):
    o = odamlar.odam(ish["b"])
    r = xotira.saqla_natija([{"tur": "uchrashuv", "matn": "Baxmal hokimligi chaqirgan — loyihalar bo'yicha",
                              "sana": "2026-10-16", "soat": "11:00", "kimga": "", "iqtibos": "ertaga 11 da Baxmalga"}], o)
    assert r[0]["matn"] == ("Eslab qoldim: ertaga (16-oktabr, juma) soat 11:00 — Baxmal hokimligi chaqirgan — loyihalar "
                            "bo'yicha. 10:00 da eslataman.")
    assert xotira.eslat() == 0  # hali vaqti emas
    vaqt._siljish += timedelta(days=1, hours=1, minutes=1)  # 16-oktabr 10:01
    assert xotira.eslat() == 1 and xotira.eslat() == 0  # bir marta
    n = baza.bir("SELECT * FROM xabarnoma WHERE tur='xotira'")
    assert n["odam_id"] == ish["b"] and "Baxmal" in n["matn"] and "xb:" in n["tugmalar"]


def test_kimga_va_malumot(ish):
    o = odamlar.odam(ish["b"])
    r = xotira.saqla_natija([{"tur": "eslatma", "matn": "Karimovga qo'ng'iroq qilsin", "sana": "2026-10-17", "soat": "",
                              "kimga": "Akmal", "iqtibos": ""},
                             {"tur": "malumot", "matn": "Hokimlik loyihalar ro'yxatini so'radi", "sana": "", "soat": "",
                              "kimga": "", "iqtibos": ""}], o)
    x1, x2 = xotira.bir(r[0]["id"]), xotira.bir(r[1]["id"])
    assert x1["kimga_id"] == ish["a"] and "(sizga va Akmal Toshpo'latovga)" in r[0]["matn"]
    assert x2["eslat_vaqt"] is None and r[1]["matn"] == "Eslab qoldim: Hokimlik loyihalar ro'yxatini so'radi."
    # R8: qidiruv — so'z bo'yicha ham, sana bo'yicha ham
    assert [x["id"] for x in xotira.royxat(sorov="hokimlik")] == [x2["id"]]
    assert [x["id"] for x in xotira.royxat("2026-10-17", "2026-10-17")] == [x1["id"]]
    tool = ai.asbob_bajar(odamlar.odam(ish["a"]), "xotira", {"sozlar": "hokimlik"})
    assert tool["xotira"][0]["matn"].startswith("Hokimlik")


def test_tushunarsiz_yoq(ish):
    """R5: model hech narsa ajratmasa ham ma'noli gap xotiraga tushadi."""
    bosh = {"yozuvlar": [], "ishlar": [], "bajarildi": [], "davomat": [], "vadalar": [], "mijoz_eslatmalar": [],
            "xotira": [], "muammo": "", "savol": "", "tushunilmadi": "aniq emas"}
    d = tuzat.tuzat(dict(bosh), odamlar.odam(ish["b"]), "hokimlikdan loyihalar haqida so'rashdi")
    assert d["xotira"][0]["tur"] == "malumot" and not d["tushunilmadi"]
    d = tuzat.tuzat(dict(bosh, xotira=[]), odamlar.odam(ish["b"]), "asd")
    assert d["xotira"] == []  # ma'nosiz — tashlanadi


def test_web_miya_xotirani_darhol_saqlaydi(ish, monkeypatch):
    async def tushun(matn_, o, **k):
        return {"yozuvlar": [], "ishlar": [], "vadalar": [], "mijoz_eslatmalar": [], "savol": "", "tushunilmadi": "",
                "xotira": [{"tur": "uchrashuv", "matn": "Baxmal hokimligi", "sana": "2026-10-16", "soat": "11:00",
                            "kimga": "", "iqtibos": matn_}]}
    monkeypatch.setattr(ai, "tushun", tushun)
    ish["veb"].app.dependency_overrides[ish["veb"].joriy] = lambda: odamlar.odam(ish["b"])
    c = TestClient(ish["veb"].app)
    c.headers["X-Miya"] = "1"
    r = c.post("/api/miya", json={"matn": "ertaga 11 da Baxmalga hokimlikka chaqirishgan"}).json()
    assert r["tur"] == "xotira" and r["xotira"][0]["matn"].startswith("Eslab qoldim")
    x = baza.bir("SELECT * FROM xotira")
    assert x["xabar_id"] and baza.bir("SELECT matn FROM xabar WHERE id=?", x["xabar_id"])["matn"].startswith("ertaga 11")


def test_kimga_aytilsa_ikkalasiga_eslatiladi(ish):
    xotira.qosh("uchrashuv", "Karimov bilan uchrashuv", ish["b"], "2026-10-15", "15:00", kimga_id=ish["a"])
    vaqt._siljish += timedelta(hours=5, minutes=1)  # 14:01
    assert xotira.eslat() == 1
    assert sorted(r["odam_id"] for r in baza.hammasi("SELECT odam_id FROM xabarnoma WHERE tur='xotira'")) == sorted([ish["a"], ish["b"]])


def test_xotira_bilan_ijrochisiz_ish_takrorlanmaydi(ish):
    bosh = {"yozuvlar": [], "bajarildi": [], "davomat": [], "vadalar": [], "mijoz_eslatmalar": [], "muammo": "",
            "savol": "", "tushunilmadi": ""}
    gap = "ertaga ertalab 9 da omborga mol keladi"
    d = tuzat.tuzat(dict(bosh, xotira=[{"tur": "malumot", "matn": "Omborga mol keladi", "sana": "2026-10-16", "soat": "09:00",
                                        "kimga": "", "iqtibos": gap}],
                         ishlar=[{"nom": "Mol qabul qilish", "ijrochilar": [], "iqtibos": gap},
                                 {"nom": "Kamera", "ijrochilar": [], "iqtibos": ""},
                                 {"nom": "Eshik", "ijrochilar": ["Akmal"], "iqtibos": gap}]), odamlar.odam(ish["a"]), gap)
    assert [i["nom"] for i in d["ishlar"]] == ["Kamera", "Eshik"]


def test_nisbiy_vaqtni_dastur_hisoblaydi(ish):
    bosh = {"yozuvlar": [], "ishlar": [], "bajarildi": [], "davomat": [], "vadalar": [], "mijoz_eslatmalar": [],
            "muammo": "", "savol": "", "tushunilmadi": ""}
    for gap, soat in (("20 daqiqadan keyin Karimovga qo'ng'iroq qilishni eslat", "09:20"),
                      ("yarim soatdan keyin eslat: dori ichish", "09:30"), ("2 soatdan keyin bankka bor", "11:00")):
        d = tuzat.tuzat(dict(bosh, xotira=[{"tur": "malumot", "matn": "x", "sana": "", "soat": "", "kimga": "", "iqtibos": gap}]),
                        odamlar.odam(ish["b"]), gap)
        assert (d["xotira"][0]["sana"], d["xotira"][0]["soat"], d["xotira"][0]["tur"]) == ("2026-10-15", soat, "eslatma"), gap
    r = xotira.saqla_natija(d["xotira"], odamlar.odam(ish["b"]))
    assert r[0]["matn"].endswith("11:00 da eslataman.")


def test_akmalga_ham_eslat(ish):
    bosh = {"yozuvlar": [], "ishlar": [], "bajarildi": [], "davomat": [], "vadalar": [], "mijoz_eslatmalar": [],
            "muammo": "", "savol": "", "tushunilmadi": ""}
    gap = "1 soatdan keyin Akmalga ham eslat: kamerani tekshirish"
    d = tuzat.tuzat(dict(bosh, xotira=[{"tur": "eslatma", "matn": "Kamerani tekshirish", "sana": "", "soat": "", "kimga": "",
                                        "iqtibos": gap}]), odamlar.odam(ish["b"]), gap)
    r = xotira.saqla_natija(d["xotira"], odamlar.odam(ish["b"]))
    assert xotira.bir(r[0]["id"])["kimga_id"] == ish["a"] and "sizga va Akmal" in r[0]["matn"]
    # «Karimovga qo'ng'iroq qilishni eslat» — Karimov xodim emas: kimga bo'sh qoladi (yozganga eslatiladi)
    gap = "20 daqiqadan keyin Karimovga qo'ng'iroq qilishni eslat"
    d = tuzat.tuzat(dict(bosh, xotira=[{"tur": "eslatma", "matn": "Karimovga qo'ng'iroq", "sana": "", "soat": "", "kimga": "",
                                        "iqtibos": gap}]), odamlar.odam(ish["b"]), gap)
    assert xotira.bir(xotira.saqla_natija(d["xotira"], odamlar.odam(ish["b"]))[0]["id"])["kimga_id"] is None
