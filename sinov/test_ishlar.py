"""2-bosqich: ishlar, dalil, qabul → pul, takroriy ish, davomat, ko'nikma."""
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import baza, davomat, hisob, ishlar, kurs, maosh, odamlar, vaqt  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    vaqt._siljish = timedelta(0)
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Rustam Aliyev", "boshliq")
    m = odamlar.odam_yarat("Malika Menejer", "menejer", kim_id=b)
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    d = odamlar.odam_yarat("Dilshod Rahimov", "xodim", kim_id=b)
    maosh.boshlangan_oy()
    yield {"b": b, "m": m, "a": a, "d": d}
    vaqt._siljish = timedelta(0)


def test_ulush_jami_narxdan_farqsiz():
    q = ishlar.ulush_taqsim(1_000_000, [{"odam_id": 1, "ulush": 1}, {"odam_id": 2, "ulush": 1}, {"odam_id": 3, "ulush": 1}])
    assert sum(s for _, s in q) == 1_000_000 and q[0][1] == 333_334
    q = ishlar.ulush_taqsim(900_000, [{"odam_id": 1, "ulush": 2}, {"odam_id": 2, "ulush": 1}])
    assert q == [(1, 600_000), (2, 300_000)]


def test_xodim_boshqaga_ish_bera_olmaydi(ish):
    with pytest.raises(ishlar.IshXato):
        ishlar.ish_yarat("O'rnatish", [(ish["d"], 1)], ish["a"])
    iid, _ = ishlar.ish_yarat("O'zim qildim", [(ish["a"], 1)], ish["a"], narx=500_000)
    assert ishlar.ish(iid)["narx"] is None and ishlar.ish(iid)["manba"] == "xodim"  # I-f


def test_ish_dalil_qabul_pul(ish):
    iid, x = ishlar.ish_yarat("Kafel yotqizish", [(ish["a"], 1), (ish["d"], 1)], ish["m"], joy="Chilonzor",
                              narx=900_000, dalil_turi="rasm", ish_turi="Kafel")
    assert {n["odam_id"] for n in x} == {ish["a"], ish["d"]}
    r = ishlar.bajarildi_dedi(iid, ish["a"])
    assert r["holat"] == "bajarildi_dalil" and r["dalil"] == "rasm"
    v = maosh.varaq(ish["a"])
    assert v["ish_kutilmoqda_jami"] == 450_000 and v["qolgani"] == 0  # kutilmoqda — hisobga kirmagan
    with pytest.raises(ishlar.IshXato):
        ishlar.dalil_qosh(iid, ish["a"], "rasm", fayl="x.jpg", uzatilgan=True)  # uzatilgan rasm dalil emas
    r = ishlar.dalil_qosh(iid, ish["a"], "rasm", fayl="x.jpg")
    assert r["holat"] == "bajarildi"
    assert any(n["odam_id"] == ish["m"] for n in r["xabarlar"])  # qabul so'rovi ish beruvchiga
    with pytest.raises(ishlar.IshXato):
        ishlar.qabul(iid, ish["a"])  # xodim o'zi qabul qila olmaydi
    ishlar.qabul(iid, ish["m"])
    assert maosh.varaq(ish["a"])["qolgani"] == 450_000
    assert maosh.varaq(ish["d"])["qolgani"] == 450_000
    assert ishlar.ish(iid)["holat"] == "qabul"
    k = ishlar.konikma(ish["a"])
    assert k[0]["tur"] == "kafel" and k[0]["soni"] == 1


def test_qayta_ishlash_va_muddat(ish):
    iid, _ = ishlar.ish_yarat("Bo'yash", [(ish["a"], 1)], ish["b"], dalil_turi="yoq",
                              muddat=(vaqt.bugun() - timedelta(days=2)).isoformat())
    assert ishlar.kechikdi_kun(ishlar.ish(iid)) == 2
    with pytest.raises(ishlar.IshXato):
        ishlar.muddat_ozgar(iid, ish["b"], vaqt.bugun().isoformat(), "")  # sababsiz
    ishlar.muddat_ozgar(iid, ish["b"], vaqt.bugun().isoformat(), "mijoz uyda yo'q edi")
    r = ishlar.bajarildi_dedi(iid, ish["a"])
    assert r["holat"] == "bajarildi"  # dalil talab qilinmaydi
    ishlar.qayta(iid, ish["b"], "bir devor chala qolgan")
    assert ishlar.ish(iid)["holat"] == "qayta"
    assert ishlar.bajarildi_dedi(iid, ish["a"])["holat"] == "bajarildi"


def test_joylashuv_dalili_masofa(ish):
    iid, _ = ishlar.ish_yarat("Yetkazish", [(ish["d"], 1)], ish["b"], dalil_turi="joylashuv", lat=41.3111, lon=69.2797)
    ishlar.bajarildi_dedi(iid, ish["d"])
    with pytest.raises(ishlar.IshXato):
        ishlar.dalil_qosh(iid, ish["d"], "joylashuv", lat=41.3500, lon=69.2797)  # ~4 km
    r = ishlar.dalil_qosh(iid, ish["d"], "joylashuv", lat=41.3112, lon=69.2799)
    assert r["holat"] == "bajarildi"


def test_avto_qabul_24_soat(ish):
    iid, _ = ishlar.ish_yarat("Montaj", [(ish["a"], 1)], ish["b"], narx=300_000, dalil_turi="yoq")
    ishlar.bajarildi_dedi(iid, ish["a"])
    assert not ishlar.avto_qabul()
    vaqt._siljish = timedelta(hours=25)
    ishlar.avto_qabul()
    assert ishlar.ish(iid)["holat"] == "qabul"
    assert maosh.varaq(ish["a"], vaqt.oy(ishlar.ish(iid)["bajarildi_vaqt"]))["qolgani"] == 300_000


def test_dollar_narx_som_maoshga(ish):
    kurs.kurs_qoy(vaqt.bugun().isoformat(), "USD", 12_000)
    iid, _ = ishlar.ish_yarat("Server o'rnatish", [(ish["a"], 1)], ish["b"], narx=10_000, valyuta="USD", dalil_turi="yoq")
    ishlar.bajarildi_dedi(iid, ish["a"])
    ishlar.qabul(iid, ish["b"])
    assert maosh.varaq(ish["a"])["qolgani"] == 1_200_000  # I-e


def test_takroriy_ish_bir_marta(ish):
    ishlar.takroriy_qoy("Ombor tozalash", [ish["d"]], "har_kun", None, ish["b"])
    bugun = vaqt.bugun()
    if ishlar.dam_olishmi(bugun):
        bugun = bugun + timedelta(days=1)
    ishlar.takroriy_yarat(bugun)
    ishlar.takroriy_yarat(bugun)
    assert baza.qiymat("SELECT COUNT(*) FROM ish WHERE takror_id IS NOT NULL") == 1
    yakshanba = bugun + timedelta(days=(6 - bugun.weekday()) % 7)
    ishlar.takroriy_yarat(yakshanba)
    assert baza.qiymat("SELECT COUNT(*) FROM ish WHERE takror_sana=?", yakshanba.isoformat()) == 0  # I-g


def test_ijrochi_taklifi(ish):
    for _ in range(2):
        iid, _ = ishlar.ish_yarat("Kafel", [(ish["a"], 1)], ish["b"], ish_turi="kafel", dalil_turi="yoq")
        ishlar.bajarildi_dedi(iid, ish["a"])
    ishlar.ish_yarat("Kafel 3", [(ish["a"], 1)], ish["b"], ish_turi="kafel")
    t = ishlar.ijrochi_taklif("kafel")
    assert t[0]["odam_id"] == ish["a"] and t[0]["qilgan"] == 2 and t[0]["ochiq"] == 1


def test_davomat_keldi_ketdi_va_kunbay(ish):
    baza.sozlama_qoy("ish_boshlanishi", "00:00")
    r = davomat.belgila(ish["d"], 41.31, 69.27)
    assert r["tur"] == "keldi" and r["kechikish"] >= 0
    assert davomat.belgila(ish["d"])["tur"] == "ketdi"
    assert davomat.belgila(ish["d"])["tur"] == "allaqachon"
    oy = vaqt.oy(vaqt.bugun())
    maosh.shart_qoy(ish["d"], "kunbay", 200_000, "UZS", vaqt.oy_boshi(oy).isoformat(), ish["b"])
    assert maosh.varaq(ish["d"])["qolgani"] == 200_000  # 1 kun davomat bo'yicha
    maosh.kunlar_qoy(ish["d"], oy, 3, ish["b"])
    assert maosh.varaq(ish["d"])["qolgani"] == 600_000  # boshliq qo'lda yozgani ustun (M3-b)


def test_unutilgan_kun_sorovi(ish):
    kecha = (vaqt.bugun() - timedelta(days=1)).isoformat()
    x = davomat.sorov(ish["a"], kecha, "telefonim o'chgan edi")
    assert x and x[0]["odam_id"] == ish["b"]
    did = baza.qiymat("SELECT id FROM davomat WHERE odam_id=?", ish["a"])
    with pytest.raises(davomat.DavomatXato):
        davomat.sorov_hal(did, ish["m"], True)  # faqat boshliq
    davomat.sorov_hal(did, ish["b"], True)
    assert davomat.oy_kunlari(ish["a"], vaqt.oy(kecha)) == 1


def test_ish_korish_huquqi(ish):
    iid, _ = ishlar.ish_yarat("Maxfiy ish", [(ish["d"], 1)], ish["b"])
    a = odamlar.odam(ish["a"])
    assert not ishlar.korishi_mumkin(a, ishlar.ish(iid))
    assert all(i["id"] != iid for i in ishlar.ishlar(korish=a))
    assert ishlar.korishi_mumkin(odamlar.odam(ish["m"]), ishlar.ish(iid))  # O-a: menejer hammasini ko'radi
