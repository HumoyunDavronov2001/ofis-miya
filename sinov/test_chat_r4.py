"""R3, R4, R9: xodim boshliqdek ko'radi; xodim yozgan pul boshliq tasdig'i bilan; web chat — bitta miya."""
import os
import sys
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import ai, baza, hisob, maosh, odamlar, vaqt, xotira  # noqa: E402


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
    from miya import veb
    yield {"b": b, "k": k, "a": a, "kassa": kassa, "veb": veb}
    veb.app.dependency_overrides.clear()
    vaqt._siljish = timedelta(0)


def klient(ish, kim):
    ish["veb"].app.dependency_overrides[ish["veb"].joriy] = lambda: odamlar.odam(kim)
    c = TestClient(ish["veb"].app)
    c.headers["X-Miya"] = "1"
    return c


def _chiqim(ish, kim, summa=200_000):
    return klient(ish, kim).post("/api/harakat", json={"tur": "chiqim", "summa": summa, "kassa_id": ish["kassa"],
                                                       "xarajat_turi": "Benzin"}).json()


@pytest.mark.r4
def test_xodim_yozuvi_boshliq_tasdigisiz_kirmaydi(ish):
    r = _chiqim(ish, ish["k"])
    assert r["holat"] == "ruxsat_kutilmoqda"
    assert hisob.qoldiq(f"kassa:{ish['kassa']}")["UZS"] == 5_000_000  # hisobga kirmadi
    # boshliqning chatida «Tasdiqlaysizmi?» — tugmalari bilan
    boss = klient(ish, ish["b"])
    n = [x for x in boss.get("/api/chat").json()["xabarlar"] if x.get("tur") == "ruxsat"][0]
    assert n["matn"].startswith("Tasdiqlaysizmi?") and n["tugmalar"][0][1] == f"r:{r['id']}:1"
    assert boss.post("/api/chat/tugma", json={"data": f"r:{r['id']}:1"}).json()["matn"].startswith("✓")
    assert hisob.harakat(r["id"])["holat"] == "faol"
    assert hisob.qoldiq(f"kassa:{ish['kassa']}")["UZS"] == 4_800_000
    # javob berilgan savolning tugmasi qayta chiqmaydi, ikkinchi bosish — 409
    n = [x for x in boss.get("/api/chat").json()["xabarlar"] if x.get("tur") == "ruxsat"][0]
    assert n["tugmalar"] == [] and n["holat"] == "✓ Tasdiqlangan"
    assert boss.post("/api/chat/tugma", json={"data": f"r:{r['id']}:1"}).status_code == 409
    # xodim boshqa birovning tasdiq tugmasini bosa olmaydi
    r2 = _chiqim(ish, ish["a"], 100_000)
    assert klient(ish, ish["a"]).post("/api/chat/tugma", json={"data": f"r:{r2['id']}:1"}).status_code == 409


@pytest.mark.r4
def test_boshliq_yozuvi_va_sozlama(ish):
    assert _chiqim(ish, ish["b"])["holat"] == "faol"
    baza.sozlama_qoy("xodim_tasdiq", "0")  # boshliq xohlasa — eski tartib (darhol)
    assert _chiqim(ish, ish["k"], 150_000)["holat"] == "faol"  # boshqa summa — takror emas


def test_xodim_boshliqdek_koradi(ish):
    """R3: faol xodim chatda boshliqning asboblari bilan ishlaydi; ketgan — yo'q."""
    x = odamlar.odam(ish["a"])
    nomlar = {t["name"] for t in ai.asboblar(ai.umumiy_korish(x))}
    assert {"kassalar", "xodim_hisobi", "davr_jami", "mijoz_qarzlari"} <= nomlar
    assert ai.asbob_bajar(ai.umumiy_korish(x), "kassalar", {})["kassalar"]
    baza.bajar("UPDATE odam SET holat='ketgan' WHERE id=?", ish["a"])
    assert "kassalar" not in {t["name"] for t in ai.asboblar(ai.umumiy_korish(odamlar.odam(ish["a"])))}


def test_chat_tarixi_va_yakun(ish, monkeypatch):
    async def tushun(matn_, o, **k):
        return {"yozuvlar": [{"tur": "chiqim", "summa": 300_000, "xarajat_turi": "Benzin", "iqtibos": "benzinga 300"}],
                "ishlar": [], "vadalar": [], "mijoz_eslatmalar": [], "savol": "", "tushunilmadi": "",
                "xotira": [{"tur": "uchrashuv", "matn": "Baxmal hokimligi", "sana": "2030-01-02", "soat": "11:00",
                            "kimga": "", "iqtibos": ""}]}
    monkeypatch.setattr(ai, "tushun", tushun)
    c = klient(ish, ish["a"])
    r = c.post("/api/chat", json={"matn": "benzinga 300 ming, 2-yanvar 11 da hokimlik"}).json()
    assert r["odam"]["kim"] == "odam" and r["miya"]["malumot"]["tur"] == "takliflar"
    assert "Eslab qoldim" in r["miya"]["matn"]
    t = c.get("/api/chat").json()["xabarlar"]
    assert [x["kim"] for x in t] == ["odam", "miya"]
    cid = int(r["miya"]["k"][1:])
    c.post(f"/api/chat/{cid}/yakun", json={"natija": ["Xarajat: Benzin — boshliq ruxsatini kutmoqda"]}).raise_for_status()
    assert c.get("/api/chat").json()["xabarlar"][-1]["malumot"]["yakun"] == ["Xarajat: Benzin — boshliq ruxsatini kutmoqda"]
    # boshqa odamning chati ko'rinmaydi
    assert klient(ish, ish["b"]).get("/api/chat").json()["xabarlar"] == []


def test_eslatma_chatga_tushadi_va_belgilanadi(ish):
    xid = xotira.qosh("eslatma", "Bankka borish", ish["a"], vaqt.bugun().isoformat(), None)
    baza.bajar("UPDATE xotira SET eslat_vaqt=? WHERE id=?", vaqt.iso(), xid)
    assert xotira.eslat() == 1
    c = klient(ish, ish["a"])
    n = c.get("/api/chat").json()["xabarlar"][-1]
    assert n["tur"] == "xotira" and [t[1] for t in n["tugmalar"]] == [f"xb:{xid}", f"xk:{xid}"]
    c.post("/api/chat/tugma", json={"data": f"xb:{xid}"}).raise_for_status()
    assert xotira.bir(xid)["holat"] == "bajarildi" and c.get("/api/chat").json()["xabarlar"][-1]["tugmalar"] == []


def test_kim_nima_yozdi_asbobi(ish):
    """R8: «Akmal bugun nima yozdi?» — xabarlar (web chat ham) bitta xotirada."""
    baza.bajar("INSERT INTO xabar(odam_id,tur,matn,vaqt,holat) VALUES(?,?,?,?,'ishlandi')", ish["a"], "matn",
               "Sobirov ofisiga kamera o'rnatdim", vaqt.iso())
    baza.bajar("INSERT INTO xabar(odam_id,tur,stt_matn,vaqt,holat) VALUES(?,?,?,?,'ishlandi')", ish["k"], "ovoz",
               "Kassani sanadim", vaqt.iso())
    d = ai.asbob_bajar(ai.umumiy_korish(odamlar.odam(ish["b"])), "xabarlar", {"ism": "Akmal"})
    assert [x["matn"] for x in d["xabarlar"]] == ["Sobirov ofisiga kamera o'rnatdim"]
    d = ai.asbob_bajar(ai.umumiy_korish(odamlar.odam(ish["a"])), "xabarlar", {})
    assert {x["kim"] for x in d["xabarlar"]} == {"Akmal Toshpo'latov", "Dilnoza Qodirova"} and d["xabarlar"][1]["ovoz"]
