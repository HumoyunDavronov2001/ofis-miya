"""CRM: panel chatsiz to'liq ishlaydi (CRM1 — kalendar va eslatmalar)."""
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import baza, hisob, ishlar, maosh, odamlar, vadalar, vaqt, xotira  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    vaqt._siljish = timedelta(0)
    vaqt._siljish = datetime(2026, 10, 15, 9, 0, tzinfo=vaqt.TZ) - vaqt.hozir()  # payshanba 09:00
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Sardor Aliyev", "boshliq")
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    maosh.boshlangan_oy()
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    from miya import veb
    veb.app.dependency_overrides[veb.joriy] = lambda: odamlar.odam(b)
    c = TestClient(veb.app)
    c.headers["X-Miya"] = "1"
    yield {"b": b, "a": a, "m": mid, "c": c}
    veb.app.dependency_overrides.clear()
    vaqt._siljish = timedelta(0)


def test_xotira_qoshish_tahrirlash_holat(ish):
    c = ish["c"]
    r = c.post("/api/xotira", json={"tur": "uchrashuv", "matn": "Baxmal hokimligi", "sana": "2026-10-16", "soat": "11:00",
                                    "kimga_id": ish["a"]}).json()
    xid = r["xotira"]["id"]
    assert r["matn"].endswith("10:00 da eslataman (sizga va Akmal Toshpo'latovga).")
    # vaqt o'zgarsa — eslatish qayta hisoblanadi, eslatilgan bo'lsa ham yana eslatadi
    baza.bajar("UPDATE xotira SET eslatildi=? WHERE id=?", vaqt.iso(), xid)
    x = c.post(f"/api/xotira/{xid}", json={"soat": "15:00", "matn": "Baxmal hokimligi — loyihalar"}).json()["xotira"]
    assert x["soat"] == "15:00" and x["eslat_vaqt"].startswith("2026-10-16T14:00") and x["eslatildi"] is None
    assert x["kimga_id"] == ish["a"]  # yuborilmagan maydon o'zgarmaydi
    assert c.post(f"/api/xotira/{xid}", json={"holat": "bajarildi"}).json()["xotira"]["holat"] == "bajarildi"
    assert c.post("/api/xotira", json={"matn": "  "}).status_code == 400
    m = c.post("/api/xotira", json={"tur": "malumot", "matn": "Hokimlik loyihalar ro'yxatini so'radi"}).json()["xotira"]
    assert [x["id"] for x in c.get("/api/xotira?sorov=hokimlik&tur=malumot").json()["xotira"]] == [m["id"]]


def test_kalendar_hammasi_bir_joyda(ish):
    c = ish["c"]
    xotira.qosh("uchrashuv", "Baxmal hokimligi", ish["b"], "2026-10-16", "11:00")
    ishlar.ish_yarat("Eshik o'rnatish", [(ish["a"], 1)], ish["b"], muddat="2026-10-13")  # kechikkan
    ishlar.ish_yarat("Kamera", [(ish["a"], 1)], ish["b"], muddat="2026-10-17", soat="10:00")
    hisob.tasdiqla(hisob.taklif("boshlangich_mijoz", {"summa": 3_000_000, "mijoz_id": ish["m"]}, ish["b"]), ish["b"])
    vadalar.yoz(ish["m"], "2026-10-20", ish["b"], summa=1_000_000)
    v = c.get("/api/kalendar?dan=2026-10-01&gacha=2026-10-31").json()["voqealar"]
    turlar = [(x["tur"], x["sana"]) for x in v if x["tur"] != "maosh"]
    assert turlar == [("ish", "2026-10-13"), ("uchrashuv", "2026-10-16"), ("ish", "2026-10-17"), ("vada", "2026-10-20")]
    assert [x for x in v if x["tur"] == "ish"][0]["kechikkan"] is True
    assert [x for x in v if x["tur"] == "vada"][0]["matn"].replace("\xa0", " ") == "Anvar Karimov: 1 000 000 so'm"
    assert {x["sana"] for x in v if x["tur"] == "maosh"} == {f"2026-10-{d:02d}" for d in maosh.maosh_kunlari()}
    assert c.get("/api/kalendar?dan=2026-10-31&gacha=2026-10-01").status_code == 400


# ---------- CRM2: tahrirlash ----------

def test_pul_yozuvini_tuzatish(ish):
    c = ish["c"]
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", ish["b"], ish["b"])
    hisob.tasdiqla(hisob.taklif("boshlangich_kassa", {"summa": 1_000_000, "kassa_id": kassa}, ish["b"]), ish["b"])
    r = c.post("/api/harakat", json={"tur": "chiqim", "summa": 200_000, "kassa_id": kassa, "xarajat_turi": "Benzin"}).json()
    assert c.get(f"/api/harakat/{r['id']}").json()["harakat"]["summa"]["m"] == 200_000
    assert c.post(f"/api/harakat/{r['id']}/tuzat", json={"summa": 250_000}).status_code == 400  # sababsiz
    t = c.post(f"/api/harakat/{r['id']}/tuzat", json={"summa": 250_000, "izoh": "chek bo'yicha", "sabab": "summa xato"}).json()
    assert t["holat"] == "faol" and t["harakat"]["summa"]["m"] == 250_000
    assert hisob.harakat(r["id"])["holat"] == "bekor" and hisob.harakat(t["id"])["asos_id"] == r["id"]  # tarix o'chmaydi
    assert hisob.qoldiq(f"kassa:{kassa}")["UZS"] == 750_000


def test_vada_va_ish_tahriri(ish):
    c = ish["c"]
    d = odamlar.odam_yarat("Dilshod Rahimov", "xodim", kim_id=ish["b"])
    vid = vadalar.yoz(ish["m"], "2026-10-20", ish["b"], summa=1_000_000)
    c.post(f"/api/vada/{vid}/tahrir", json={"summa": 1_500_000, "muddat": "2026-10-22", "matn": "qolgan qismi"}).raise_for_status()
    v = vadalar.vada(vid)
    assert (v["summa"], v["muddat"], v["matn"]) == (1_500_000, "2026-10-22", "qolgan qismi")
    assert c.post(f"/api/vada/{vid}/tahrir", json={"summa": ""}).status_code == 400  # to'lov va'dasi summasiz bo'lmaydi
    iid, _ = ishlar.ish_yarat("Kamera", [(ish["a"], 1)], ish["b"], muddat="2026-10-17")
    assert c.post(f"/api/ish/{iid}/tahrir", json={"muddat": "2026-10-18"}).status_code == 400  # I7: sababsiz muddat yo'q
    j = c.post(f"/api/ish/{iid}/tahrir", json={"nom": "10 ta kamera", "muddat": "2026-10-18", "soat": "10:00",
                                               "narx": 600_000, "ijrochilar": [d], "sabab": "mijoz so'radi"}).json()
    assert (j["nom"], j["muddat"], j["soat"], j["narx"]["m"]) == ("10 ta kamera", "2026-10-18", "10:00", 600_000)
    assert [x["odam_id"] for x in ishlar.ish(iid)["ijrochilar"]] == [d]
    xabar = {(n["odam_id"], n["tur"]) for n in baza.hammasi("SELECT odam_id, tur FROM xabarnoma")}
    assert (d, "ish") in xabar and (ish["a"], "malumot") in xabar  # yangisiga ish, eskisiga «sizdan olindi»
    assert c.post(f"/api/ish/{iid}/tahrir", json={"ijrochilar": []}).status_code == 400


def test_mijoz_arxivi(ish):
    c = ish["c"]
    c.post(f"/api/mijoz/{ish['m']}", json={"arxiv": True}).raise_for_status()
    assert c.get("/api/mijozlar").json()["mijozlar"] == []
    assert [m["id"] for m in c.get("/api/mijozlar?arxiv=1").json()["mijozlar"]] == [ish["m"]]
    c.post(f"/api/mijoz/{ish['m']}", json={"arxiv": False}).raise_for_status()
    assert [m["id"] for m in c.get("/api/mijozlar").json()["mijozlar"]] == [ish["m"]]


# ---------- CRM3: hisobotlar (namuna baza — nazorat.py bilan bir xil, raqamlar qo'lda hisoblangan) ----------

def test_hisobot_namuna_bazada(tmp_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import nazorat
    from miya import hisobot
    nazorat.urug(str(tmp_path / "n.db"))
    try:
        d = hisobot.davr("2026-10-01", "2026-10-15")
        f = d["foyda"]
        assert (f["sotuv"], f["xarajat"], f["foyda"]) == (14_500_000, 12_200_000, 2_300_000) and f["oy_yopilmagan"]
        assert {x["nom"]: x["summa"] for x in d["xarajat_turlar"]} == {
            "Material": 7_200_000, "Ijara": 3_000_000, "Ehtiyot qism": 1_200_000, "Benzin": 650_000, "Ofis": 150_000}
        assert [(x["ism"], x["summa"]) for x in d["sotuv_mijoz"]][0] == ("Anvar Karimov", 8_000_000)
        k = {x["nom"]: x for x in d["kassalar"]}
        assert (k["Asosiy kassa"]["kirim"], k["Asosiy kassa"]["chiqim"], k["Asosiy kassa"]["oxirida"]) == (18_500_000, 8_850_000, 9_650_000)
        assert k["Dollar kassa"]["oxirida"] == 90_000  # 900 $ (sentlarda)
        y = {b["kalit"]: b for b in d["qarz_yoshi"]}
        assert [m["ism"] for m in y["1_30"]["mijozlar"]] == ["Gulnora Azimova"] and y["muddati_kelmagan"]["summa"] == 4_200_000
        # boshqa davr: oktabr boshi — kassa boshidagi qoldiq oldingi kunlardan
        d2 = hisobot.davr("2026-10-05", "2026-10-15")
        assert {x["nom"]: x for x in d2["kassalar"]}["Asosiy kassa"]["boshida"] == 10_000_000 - 3_000_000 - 300_000 + 2_500_000
        with pytest.raises(ValueError):
            hisobot.davr("2026-10-15", "2026-10-01")
    finally:
        vaqt._siljish = timedelta(0)


# ---------- CRM4: qidiruv va sahifalash; CRM5: Excel'dan yuklash ----------

def test_umumiy_qidiruv_va_sahifalash(ish):
    c = ish["c"]
    baza.bajar("UPDATE mijoz SET telefon='+998 90 123 45 67', manzil='Yunusobod 5' WHERE id=?", ish["m"])
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", ish["b"], ish["b"])
    hisob.tasdiqla(hisob.taklif("boshlangich_kassa", {"summa": 5_000_000, "kassa_id": kassa}, ish["b"]), ish["b"])
    for i in range(5):
        c.post("/api/harakat", json={"tur": "chiqim", "summa": 10_000 + i, "kassa_id": kassa, "xarajat_turi": "Benzin"}).raise_for_status()
    c.post("/api/harakat", json={"tur": "kirim", "summa": 777_000, "kassa_id": kassa, "mijoz_id": ish["m"],
                                 "izoh": "kamera uchun oldindan"}).raise_for_status()
    ishlar.ish_yarat("Kamera o'rnatish", [(ish["a"], 1)], ish["b"], joy="Yunusobod 5", mijoz_id=ish["m"])
    xotira.qosh("malumot", "Karimov kreditga olmoqchi", ish["b"])
    r = c.get("/api/qidiruv?q=Karimovga").json()  # qo'shimchali so'z — ildizi bo'yicha
    assert [m["id"] for m in r["mijozlar"]] == [ish["m"]] and len(r["xotira"]) == 1
    assert any(h["summa"]["m"] == 777_000 for h in r["yozuvlar"]) and r["ishlar"][0]["nom"] == "Kamera o'rnatish"
    assert [m["id"] for m in c.get("/api/qidiruv?q=4567").json()["mijozlar"]] == [ish["m"]]  # telefon raqami
    assert c.get("/api/qidiruv?q=yunusobod").json()["ishlar"]  # manzil
    # kassa jadvali: matn va raqam bo'yicha, sahifalash
    assert [h["summa"]["m"] for h in c.get("/api/harakatlar?q=oldindan").json()["harakatlar"]] == [777_000]
    assert [h["summa"]["m"] for h in c.get("/api/harakatlar?q=10003").json()["harakatlar"]] == [10_003]
    bir = c.get("/api/harakatlar?tur=chiqim&limit=2").json()["harakatlar"]
    ikki = c.get(f"/api/harakatlar?tur=chiqim&limit=2&oldin_id={bir[-1]['id']}").json()["harakatlar"]
    assert [h["summa"]["m"] for h in bir + ikki] == [10_004, 10_003, 10_002, 10_001]


def _excel(qatorlar):
    import io
    from openpyxl import Workbook
    wb = Workbook()
    for q in qatorlar:
        wb.active.append(q)
    f = io.BytesIO()
    wb.save(f)
    return f.getvalue()


def test_excel_import(ish):
    c = ish["c"]
    baza.bajar("UPDATE mijoz SET telefon='901234567' WHERE id=?", ish["m"])
    fayl = _excel([["Mijozlar ro'yxati"], ["F.I.O", "Tel. raqami", "Manzili", "Qarzi", "Izoh"],
                   ["Botir Sobirov", "+998 91 111 22 33", "Chilonzor", "1 500 000", "naqd"],
                   ["Gulnora Azimova", 998931112233, None, 2.5e6, None],
                   ["Anvar K.", "+998 90 123 45 67", "", "", ""],                  # telefon bazada bor — takror
                   ["Botir Sobirov", "", "", "", ""],                             # faylda ikki marta
                   ["Sardor Nazarov", "", "", "ko'p", ""], [None, None]])         # qarz raqam emas; bo'sh qator
    r = c.post("/api/mijoz/import/korib", files={"fayl": ("m.xlsx", fayl)}, data={"tur": "mijoz"}).json()
    assert r["ustunlar"] == {"ism": 1, "telefon": 2, "manzil": 3, "qarz": 4, "izoh": 5}
    assert [(x["ism"], x["holat"]) for x in r["qatorlar"]] == [
        ("Botir Sobirov", "yangi"), ("Gulnora Azimova", "yangi"), ("Anvar K.", "takror"), ("Botir Sobirov", "takror"),
        ("Sardor Nazarov", "xato")]
    assert r["qatorlar"][1]["telefon"] == "998931112233" and r["qatorlar"][1]["qarz"] == 2_500_000
    assert baza.qiymat("SELECT COUNT(*) FROM mijoz") == 1  # ko'rib chiqishda hech narsa yozilmaydi
    y = c.post("/api/mijoz/import/yoz", json={"qatorlar": r["qatorlar"], "tur": "mijoz"}).json()
    assert y == {"qoshildi": 2, "qarz_yozildi": 2, "otkazildi": 0}
    bot = baza.qiymat("SELECT id FROM mijoz WHERE ism='Botir Sobirov'")
    assert hisob.qoldiq(f"mijoz:{bot}")["UZS"] == 1_500_000
    assert c.post("/api/mijoz/import/korib", files={"fayl": ("x.xlsx", b"emas")}).status_code == 400
