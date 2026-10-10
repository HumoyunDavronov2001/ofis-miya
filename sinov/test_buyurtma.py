"""CRM6: katalog va buyurtmalar — jami, bosqichlar, «sotildi» hisobga, o'rnatish ishi, bekor, hisobot."""
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import baza, buyurtma, hisob, hisobot, ishlar, maosh, odamlar, vadalar, vaqt  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    vaqt._siljish = timedelta(0)
    vaqt._siljish = datetime(2026, 10, 15, 9, 0, tzinfo=vaqt.TZ) - vaqt.hozir()
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Sardor Aliyev", "boshliq")
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", b, b)
    maosh.boshlangan_oy()
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Rustam Karimov',?)", vaqt.iso())
    from miya import veb
    veb.app.dependency_overrides[veb.joriy] = lambda: odamlar.odam(b)
    c = TestClient(veb.app)
    c.headers["X-Miya"] = "1"
    yield {"b": b, "a": a, "kassa": kassa, "m": mid, "c": c}
    veb.app.dependency_overrides.clear()
    vaqt._siljish = timedelta(0)


def _katalog(c):
    kam = c.post("/api/katalog", json={"nom": "IP kamera 4MP", "narx": 650_000, "birlik": "dona"}).json()
    ornat = c.post("/api/katalog", json={"nom": "O'rnatish", "tur": "xizmat", "narx": 150_000}).json()
    kabel = c.post("/api/katalog", json={"nom": "Kabel UTP", "narx": 4_500, "birlik": "metr"}).json()
    return kam, ornat, kabel


def test_katalog_va_buyurtma_jami(ish):
    c = ish["c"]
    kam, ornat, kabel = _katalog(c)
    assert c.post(f"/api/katalog/{kam['id']}", json={"nom": "IP kamera 4MP", "narx": 700_000}).json()["narx"]["m"] == 700_000
    c.post(f"/api/katalog/{kabel['id']}", json={"nom": "Kabel UTP", "narx": 4_500, "birlik": "metr", "faol": False}).raise_for_status()
    assert [k["nom"] for k in c.get("/api/katalog").json()["katalog"]] == ["IP kamera 4MP", "O'rnatish"]  # faol emas — yashirin
    b = c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "manzil": "Yunusobod 5", "chegirma": 100_000, "qatorlar": [
        {"katalog_id": kam["id"], "miqdor": 10},                       # narx katalogdan: 700 000
        {"katalog_id": ornat["id"], "miqdor": 10, "narx": 120_000},    # narx qo'lda o'zgartirilgan
        {"katalog_id": kabel["id"], "miqdor": 85.5},                   # 85,5 metr × 4 500
        {"nom": "Yo'l haqi", "miqdor": 1, "narx": 50_000}]}).json()
    assert b["jami"]["m"] == 10 * 700_000 + 10 * 120_000 + round(85.5 * 4_500) + 50_000 - 100_000
    assert b["bosqich"] == "yangi" and len(b["qatorlar"]) == 4
    b = c.post(f"/api/buyurtma/{b['id']}/bosqich", json={"bosqich": "taklif"}).json()
    assert b["bosqich"] == "taklif" and b["tarix"][-1]["matn"] == "Yangi → Taklif berildi"
    b = c.post(f"/api/buyurtma/{b['id']}", json={"chegirma": 0, "qatorlar": [{"katalog_id": kam["id"], "miqdor": 8}]}).json()
    assert b["jami"]["m"] == 8 * 700_000


def test_sotildi_hisobga_va_ish_bajarilganda_yopiladi(ish):
    c = ish["c"]
    kam, ornat, _ = _katalog(c)
    bid = c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "manzil": "Yunusobod 5", "qatorlar": [
        {"katalog_id": kam["id"], "miqdor": 4}, {"katalog_id": ornat["id"], "miqdor": 4}]}).json()["id"]  # 3 200 000
    assert c.post(f"/api/buyurtma/{bid}/sotildi", json={"tolandi": 1_000_000}).status_code == 400  # kassa tanlanmagan
    assert c.post(f"/api/buyurtma/{bid}/sotildi", json={"tolandi": 1_000_000, "kassa_id": ish["kassa"]}).status_code == 400  # muddat
    r = c.post(f"/api/buyurtma/{bid}/sotildi", json={"tolandi": 1_000_000, "kassa_id": ish["kassa"], "qarz_muddati": "2026-10-25",
                                                    "ish": {"ijrochilar": [ish["a"]], "muddat": "2026-10-17", "narx": 300_000}}).json()
    assert r["holat"] == "faol" and r["buyurtma"]["bosqich"] == "sotildi"
    h = hisob.harakat(r["sotuv_id"])
    assert (h["tur"], h["summa"], h["mijoz_id"]) == ("sotuv", 3_200_000, ish["m"]) and "Buyurtma #" in h["izoh"]
    assert hisob.qoldiq(f"kassa:{ish['kassa']}")["UZS"] == 1_000_000
    assert hisob.qoldiq(f"mijoz:{ish['m']}")["UZS"] == 2_200_000
    assert [v["muddat"] for v in vadalar.royxat(ish["m"])] == ["2026-10-25"]  # qarz muddati — va'da
    i = ishlar.ish(r["ish_id"])
    assert i["joy"] == "Yunusobod 5" and i["narx"] == 300_000 and [x["odam_id"] for x in i["ijrochilar"]] == [ish["a"]]
    assert c.post(f"/api/buyurtma/{bid}", json={"qatorlar": []}).status_code == 400  # sotilgan — narx o'zgarmaydi
    ishlar.bajarildi_dedi(r["ish_id"], ish["a"])
    ishlar.dalil_qosh(r["ish_id"], ish["a"], "rasm", izoh="sinov")
    assert c.get(f"/api/buyurtma/{bid}").json()["bosqich"] == "bajarildi"  # ish bajarildi — buyurtma o'zi yopildi


def test_bekor_va_sotuv_rad_etilsa(ish):
    c = ish["c"]
    kam, _, _ = _katalog(c)
    bid = c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "qatorlar": [{"katalog_id": kam["id"], "miqdor": 2}]}).json()["id"]
    assert c.post(f"/api/buyurtma/{bid}/bosqich", json={"bosqich": "sotildi"}).status_code == 400  # faqat «Sotildi» oynasi
    r = c.post(f"/api/buyurtma/{bid}/sotildi", json={"tolandi": 1_300_000, "kassa_id": ish["kassa"]}).json()
    assert hisob.qoldiq(f"kassa:{ish['kassa']}")["UZS"] == 1_300_000
    assert c.post(f"/api/buyurtma/{bid}/bosqich", json={"bosqich": "bekor"}).status_code == 400  # sababsiz
    b = c.post(f"/api/buyurtma/{bid}/bosqich", json={"bosqich": "bekor", "sabab": "mijoz voz kechdi"}).json()
    assert b["bosqich"] == "bekor" and hisob.harakat(r["sotuv_id"])["holat"] == "bekor"
    assert hisob.qoldiq(f"kassa:{ish['kassa']}").get("UZS", 0) == 0  # bog'langan to'lov ham bekor
    # sotuv tashqaridan bekor qilinsa — buyurtma «taklif»ga qaytadi
    bid2 = c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "qatorlar": [{"katalog_id": kam["id"], "miqdor": 1}]}).json()["id"]
    r2 = c.post(f"/api/buyurtma/{bid2}/sotildi", json={"qarz_muddati": "2026-10-30"}).json()
    hisob.bekor_qil(r2["sotuv_id"], ish["b"], "xato yozilgan")
    assert c.get(f"/api/buyurtma/{bid2}").json()["bosqich"] == "taklif"


def test_hisobot_mahsulotlar(ish):
    c = ish["c"]
    kam, ornat, _ = _katalog(c)
    for miqdor in (4, 6):
        bid = c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "qatorlar": [
            {"katalog_id": kam["id"], "miqdor": miqdor}, {"katalog_id": ornat["id"], "miqdor": miqdor}]}).json()["id"]
        c.post(f"/api/buyurtma/{bid}/sotildi", json={"qarz_muddati": "2026-10-30"}).raise_for_status()
    c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "qatorlar": [{"katalog_id": kam["id"], "miqdor": 100}]})  # sotilmagan
    m = {x["nom"]: x for x in hisobot.davr("2026-10-01", "2026-10-31")["sotuv_mahsulot"]}
    assert (m["IP kamera 4MP"]["miqdor"], m["IP kamera 4MP"]["summa"]) == (10, 6_500_000)
    assert m["O'rnatish"]["summa"] == 1_500_000


def test_chat_buyurtmalarni_koradi(ish):
    from miya import ai
    c = ish["c"]
    kam, _, _ = _katalog(c)
    bid = c.post("/api/buyurtma", json={"mijoz_id": ish["m"], "qatorlar": [{"katalog_id": kam["id"], "miqdor": 3}]}).json()["id"]
    d = ai.asbob_bajar(odamlar.odam(ish["b"]), "buyurtmalar", {"mijoz": "Karimov"})
    assert d["soni"] == 1 and d["buyurtmalar"][0]["raqam"] == bid and d["buyurtmalar"][0]["jami"]["summa"] == 1_950_000
    assert ai.asbob_bajar(odamlar.odam(ish["b"]), "buyurtmalar", {"bosqich": "sotildi"})["soni"] == 0
