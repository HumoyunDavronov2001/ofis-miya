"""Yadro sinovlari: pul hisobi, ikki tomonlama tasdiq, takror, kassa sanog'i, maosh, qoidalar, huquqlar."""
import json
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import baza, hisob, kurs, maosh, matn, odamlar, qoida, vaqt  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    vaqt._siljish = timedelta(0)
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Rustam Aliyev", "boshliq")
    k = odamlar.odam_yarat("Dilnoza Qodirova", "kassir", kim_id=b, maosh_tolaydi=1)
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    d = odamlar.odam_yarat("Dilshod Rahimov", "xodim", kim_id=b)
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", k, b)
    odamlar.odam_tahrir(k, b, kassa_id=kassa)
    maosh.boshlangan_oy()
    hid = hisob.taklif("boshlangich_kassa", {"summa": 5_000_000, "kassa_id": kassa}, b)
    hisob.tasdiqla(hid, b)
    yield {"b": b, "k": k, "a": a, "d": d, "kassa": kassa}
    vaqt._siljish = timedelta(0)


def kassa_q(ish):
    return hisob.qoldiq_bir(f"kassa:{ish['kassa']}")


# ---------- matn ----------

def test_son_soz_va_pul():
    assert matn.sonni_soz(500_000) == "besh yuz ming"
    assert matn.sonni_soz(1_500_000) == "bir million besh yuz ming"
    assert matn.sonni_soz(100_000) == "yuz ming"
    assert matn.sonni_soz(2_700_000) == "ikki million yetti yuz ming"
    assert matn.sonni_soz(1000) == "ming"
    assert matn.pul(4_350_000) == "4 350 000 so'm"
    assert matn.pul(125050, "USD") == "1 250,50 $"
    assert matn.minor(12.5, "USD") == 1250


def test_kirill_va_ism_moslash():
    assert matn.lotinga("Тошпўлатов") == "To'shpo'latov" or matn.norm("Тошпўлатов") == "toshpolatov"
    assert matn.norm("Тошпўлатов") == "toshpolatov"
    nomlar = [(1, "Anvar Karimov"), (2, "Botir Karimov"), (3, "Akmal Toshpo'latov"), (4, "Malika Yusupova")]
    assert matn.yagona(matn.mosla("Akmalga", nomlar))[0] == 3
    assert matn.yagona(matn.mosla("Каримовга", nomlar)) is None  # ikki Karimov — so'raladi (K7)
    assert matn.yagona(matn.mosla("Anvar Karimov", nomlar))[0] == 1
    assert matn.yagona(matn.mosla("Malika", nomlar))[0] == 4  # -ka qo'shimchasi deb kesilmaydi


def test_matndagi_sonlar():
    assert 2_700_000 in matn.sonlar("Qolgani 2 700 000 so'm")
    assert 2_700_000 in matn.sonlar("taxminan 2,7 mln")


# ---------- ikki tomonlama tasdiq (K5) ----------

def test_kassir_berdi_xodim_tasdiqlaydi(ish):
    hid = hisob.taklif("avans", {"summa": 500_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["k"])
    r = hisob.tasdiqla(hid, ish["k"])
    assert r["holat"] == "faol"
    h = hisob.harakat(hid)
    assert h["beruvchi_holat"] == "tasdiq" and h["oluvchi_holat"] == "kutilmoqda"
    assert kassa_q(ish) == 4_500_000  # kassadan darhol chiqdi
    assert hisob.qoldiq_bir(f"maosh:{ish['a']}") == 0  # Akmal hisobiga hali kirmadi
    assert any(x["odam_id"] == ish["a"] for x in r["xabarlar"])
    hisob.tomon_tasdiq(hid, ish["a"], "oluvchi", True)
    assert hisob.qoldiq_bir(f"maosh:{ish['a']}") == 500_000


def test_xodim_yozdi_kassir_tasdiqlaydi(ish):
    hid = hisob.taklif("avans", {"summa": 300_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["a"])
    hisob.tasdiqla(hid, ish["a"])
    h = hisob.harakat(hid)
    assert h["oluvchi_holat"] == "tasdiq" and h["beruvchi_holat"] == "kutilmoqda"
    assert kassa_q(ish) == 5_000_000  # kassir tasdiqlamaguncha kassadan chiqmaydi
    kut = hisob.kutilayotgan(f"kassa:{ish['kassa']}")
    assert kut["chiqim_jami"] == 300_000
    hisob.tomon_tasdiq(hid, ish["k"], "beruvchi", True)
    assert kassa_q(ish) == 4_700_000


def test_nizo_va_bekor(ish):
    hid = hisob.taklif("avans", {"summa": 200_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["k"])
    hisob.tasdiqla(hid, ish["k"])
    x = hisob.tomon_tasdiq(hid, ish["a"], "oluvchi", False)
    assert hisob.harakat(hid)["holat"] == "nizo"
    assert any(n["odam_id"] == ish["b"] for n in x)
    with pytest.raises(hisob.HisobXato):
        hisob.nizo_hal(hid, ish["k"], False)  # faqat boshliq
    hisob.nizo_hal(hid, ish["b"], False)
    assert hisob.harakat(hid)["holat"] == "bekor"
    assert kassa_q(ish) == 5_000_000


def test_begona_bilan_tasdiq_kerak_emas(ish):
    m = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    hid = hisob.taklif("kirim", {"summa": 2_000_000, "kassa_id": ish["kassa"], "mijoz_id": m}, ish["k"])
    hisob.tasdiqla(hid, ish["k"])
    h = hisob.harakat(hid)
    assert h["beruvchi_holat"] == "kerak_emas" and h["oluvchi_holat"] == "tasdiq"
    assert kassa_q(ish) == 7_000_000


# ---------- takror (K10) ----------

def test_ikki_kishi_bir_voqeani_yozdi(ish):
    h1 = hisob.taklif("avans", {"summa": 500_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["k"])
    hisob.tasdiqla(h1, ish["k"])
    h2 = hisob.taklif("avans", {"summa": 500_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["a"])
    r = hisob.tasdiqla(h2, ish["a"])
    assert r["holat"] == "takror" and r["takrorlar"][0]["id"] == h1
    hisob.birlashtir(h2, h1, ish["a"])
    assert hisob.harakat(h2)["holat"] == "bekor"
    assert hisob.harakat(h1)["oluvchi_holat"] == "tasdiq"  # Akmalning xabari — uning tasdig'i
    assert kassa_q(ish) == 4_500_000  # ikki marta emas
    assert hisob.qoldiq_bir(f"maosh:{ish['a']}") == 500_000


# ---------- xodim qo'lidagi pul (P10) ----------

def test_xodim_qolidagi_pul(ish):
    m = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Baraka',?)", vaqt.iso())
    h = hisob.taklif("mijozdan_qolga", {"summa": 2_000_000, "odam_id": ish["a"], "mijoz_id": m}, ish["a"])
    hisob.tasdiqla(h, ish["a"])
    assert hisob.qoldiq_bir(f"qol:{ish['a']}") == 2_000_000
    h = hisob.taklif("chiqim", {"summa": 300_000, "odam_id": ish["a"], "qoldan": True, "xarajat_turi": "Material"},
                     ish["a"])
    hisob.tasdiqla(h, ish["a"])
    assert hisob.qoldiq_bir(f"qol:{ish['a']}") == 1_700_000
    h = hisob.taklif("qoldan_qaytarish", {"summa": 1_700_000, "odam_id": ish["a"], "kassa_id": ish["kassa"]}, ish["a"])
    hisob.tasdiqla(h, ish["a"])
    assert hisob.qoldiq_bir(f"qol:{ish['a']}") == 0
    assert kassa_q(ish) == 5_000_000  # kassir hali qabul qilmadi
    hisob.tomon_tasdiq(h, ish["k"], "oluvchi", True)
    assert kassa_q(ish) == 6_700_000


# ---------- kassa sanog'i va kech yozuv (P4) ----------

def test_kassa_sanogi_va_kech_yozuv(ish):
    r = hisob.kassa_sanoq(ish["kassa"], 4_900_000, ish["k"], "100 ming yo'q")
    assert r["farq"] == -100_000
    assert any(x["odam_id"] == ish["b"] for x in r["xabarlar"])
    kecha = vaqt.bugun().isoformat()
    vaqt._siljish = timedelta(days=1)  # ertasi kun
    hid = hisob.taklif("chiqim", {"summa": 100_000, "kassa_id": ish["kassa"], "xarajat_turi": "Yoqilg'i",
                                  "sana": kecha}, ish["k"])
    hisob.tasdiqla(hid, ish["k"])
    h = hisob.harakat(hid)
    assert h["voqea_sana"] == kecha and h["hisob_sana"] == vaqt.bugun().isoformat() and h["kech"] == 1
    assert baza.bir("SELECT * FROM kassa_sanoq WHERE sana=?", kecha)["kutilgan"] == 5_000_000  # o'zgarmadi


def test_sanoq_kutilayotgan_bilan(ish):
    hid = hisob.taklif("avans", {"summa": 300_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["a"])
    hisob.tasdiqla(hid, ish["a"])
    r = hisob.kassa_sanoq(ish["kassa"], 4_700_000, ish["k"])
    assert r["farq"] == -300_000 and r["agar_tasdiqlansa"] == 4_700_000
    assert not r["xabarlar"]  # kutilayotgan yozuv farqni tushuntiradi


# ---------- egasi oldi, sotuv, foyda (P2, P9, P7) ----------

def test_egasi_oldi_foydaga_kirmaydi(ish):
    hid = hisob.taklif("egasi_oldi", {"summa": 1_000_000, "kassa_id": ish["kassa"]}, ish["k"])
    hisob.tasdiqla(hid, ish["k"])
    hisob.tomon_tasdiq(hid, ish["b"], "oluvchi", True)
    bugun = vaqt.bugun().isoformat()
    j = hisob.davr_jami(bugun, bugun)
    assert j["xarajat"] == 0 and kassa_q(ish) == 4_000_000


def test_sotuv_nasiya_va_foiz(ish):
    maosh.shart_qoy(ish["d"], "foiz", 5, "UZS", vaqt.oy_boshi(vaqt.oy(vaqt.bugun())).isoformat(), ish["b"])
    m = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    sid, kid = hisob.sotuv_tuz({"summa": 10_000_000, "tolandi": 4_000_000, "mijoz_id": m, "kassa_id": ish["kassa"],
                                "sotuvchi_id": ish["d"]}, ish["k"])
    hisob.tasdiqla(sid, ish["k"])
    hisob.tasdiqla(kid, ish["k"])
    assert hisob.qoldiq_bir(f"mijoz:{m}") == 6_000_000
    qarzlar = hisob.mijoz_qarzlari()
    assert qarzlar[0]["qarz"]["UZS"] == 6_000_000
    v = maosh.varaq(ish["d"])
    assert any(q["nom"].startswith("Sotuvdan 5%") and q["summa"] == 500_000 for q in v["qatorlar"])
    bugun = vaqt.bugun().isoformat()
    assert hisob.davr_jami(bugun, bugun)["sotuv"] == 10_000_000


# ---------- maosh varaqasi va oyni yopish (M5, M9) ----------

def test_maosh_varaqasi_va_oy_yopish(ish):
    oy = vaqt.oy(vaqt.bugun())
    maosh.shart_qoy(ish["a"], "oylik", 4_000_000, "UZS", vaqt.oy_boshi(oy).isoformat(), ish["b"])
    h1 = hisob.taklif("avans", {"summa": 1_000_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["k"])
    hisob.tasdiqla(h1, ish["k"])
    hisob.tomon_tasdiq(h1, ish["a"], "oluvchi", True)
    h2 = hisob.taklif("avans", {"summa": 500_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["k"])
    hisob.tasdiqla(h2, ish["k"])  # Akmal hali tasdiqlamadi
    v = maosh.varaq(ish["a"], oy)
    assert v["hisoblandi"] == 4_000_000 and v["olindi"] == 1_000_000
    assert v["kutilmoqda_jami"] == 500_000
    assert v["qolgani"] == 3_000_000 == maosh.qarzimiz(ish["a"], oy)
    # keyingi oyga o'tamiz va oyni yopamiz
    vaqt._siljish = (vaqt.oy_oxiri(oy) - vaqt.bugun()) + timedelta(days=2)
    keyingi = vaqt.oy(vaqt.bugun())
    with pytest.raises(maosh.MaoshXato):
        maosh.oy_yop(keyingi, ish["b"])  # joriy oy yopilmaydi
    with pytest.raises(maosh.MaoshXato):
        maosh.oy_yop(oy, ish["k"])  # faqat boshliq
    maosh.oy_yop(oy, ish["b"])
    v2 = maosh.varaq(ish["a"], keyingi)
    assert v2["otgan"] == 3_000_000  # qoldiq o'tdi
    # yopilgan oydagi avansni Akmal endi tasdiqlasa — yozuv joyida, oy raqamlari o'zgarmaydi
    hisob.tomon_tasdiq(h2, ish["a"], "oluvchi", True)
    yopiq_avval = maosh.varaq(ish["a"], oy)
    assert yopiq_avval["yopiq"]
    # yopilgan oyga kech yozuv — bugungi sana bilan tushadi
    h3 = hisob.taklif("bonus", {"summa": 200_000, "odam_id": ish["a"], "sana": vaqt.oy_oxiri(oy).isoformat(),
                                "izoh": "o'tgan oy uchun"}, ish["b"])
    hisob.tasdiqla(h3, ish["b"])
    assert hisob.harakat(h3)["hisob_sana"] == vaqt.bugun().isoformat()
    assert maosh.varaq(ish["a"], oy)["qolgani"] == yopiq_avval["qolgani"]


def test_teskari_yozuv_yopiq_davrda(ish):
    r = hisob.taklif("chiqim", {"summa": 50_000, "kassa_id": ish["kassa"], "xarajat_turi": "Boshqa"}, ish["k"])
    hisob.tasdiqla(r, ish["k"])
    hisob.kassa_sanoq(ish["kassa"], 4_950_000, ish["k"])
    vaqt._siljish = timedelta(days=1)
    tid = hisob.bekor_qil(r, ish["k"], "noto'g'ri yozilgan")
    assert tid and hisob.harakat(r)["holat"] == "faol"  # eski yozuv joyida
    assert hisob.harakat(tid)["hisob_sana"] == vaqt.bugun().isoformat()
    assert kassa_q(ish) == 5_000_000


# ---------- qoidalar (Q) ----------

def test_avans_qoidasi_ruxsat(ish):
    oy = vaqt.oy(vaqt.bugun())
    maosh.shart_qoy(ish["a"], "oylik", 4_000_000, "UZS", vaqt.oy_boshi(oy).isoformat(), ish["b"])
    qoida.qoy("avans_foiz", {"foiz": 30}, ish["b"], "avans 30 foizdan oshmasin")
    hid = hisob.taklif("avans", {"summa": 1_500_000, "kassa_id": ish["kassa"], "odam_id": ish["a"]}, ish["k"])
    r = hisob.tasdiqla(hid, ish["k"])
    assert r["holat"] == "ruxsat_kutilmoqda"
    assert kassa_q(ish) == 5_000_000
    hisob.ruxsat(hid, ish["b"], True)
    assert hisob.harakat(hid)["holat"] == "faol" and kassa_q(ish) == 3_500_000
    with pytest.raises(qoida.QoidaXato):
        qoida.qoy("yaxshi_ishlaganga_bonus", {}, ish["b"])


def test_boshliq_qoidadan_ozod(ish):
    qoida.qoy("xarajat_chegara", {"summa": 1_000_000}, ish["b"])
    hid = hisob.taklif("chiqim", {"summa": 2_000_000, "kassa_id": ish["kassa"]}, ish["b"])
    assert hisob.tasdiqla(hid, ish["b"])["holat"] == "faol"
    hid = hisob.taklif("chiqim", {"summa": 2_500_000, "kassa_id": ish["kassa"]}, ish["k"])
    assert hisob.tasdiqla(hid, ish["k"])["holat"] == "ruxsat_kutilmoqda"


# ---------- valyuta (P11) ----------

def test_dollar_kassadan_som_maoshga(ish):
    kurs.kurs_qoy(vaqt.bugun().isoformat(), "USD", 12_000)
    usd = hisob.kassa_yarat("Dollar kassa", "naqd", "USD", ish["k"], ish["b"])
    hid = hisob.taklif("boshlangich_kassa", {"summa": 100_000, "valyuta": "USD", "kassa_id": usd}, ish["b"])
    hisob.tasdiqla(hid, ish["b"])
    hid = hisob.taklif("avans", {"summa": 10_000, "valyuta": "USD", "kassa_id": usd, "odam_id": ish["a"]}, ish["k"])
    hisob.tasdiqla(hid, ish["k"])
    hisob.tomon_tasdiq(hid, ish["a"], "oluvchi", True)
    h = hisob.harakat(hid)
    assert h["summa2"] == 1_200_000 and h["valyuta2"] == "UZS"
    assert hisob.qoldiq(f"kassa:{usd}") == {"USD": 90_000}
    assert hisob.qoldiq_bir(f"maosh:{ish['a']}") == 1_200_000
    with pytest.raises(hisob.HisobXato):
        hisob.taklif("chiqim", {"summa": 100, "valyuta": "UZS", "kassa_id": usd}, ish["k"])


# ---------- huquqlar (S3, M8, T2) ----------

def test_huquqlar(ish):
    a, d, k = odamlar.odam(ish["a"]), odamlar.odam(ish["d"]), odamlar.odam(ish["k"])
    assert odamlar.hisob_korishi_mumkin(a, f"maosh:{ish['a']}")
    assert not odamlar.hisob_korishi_mumkin(a, f"maosh:{ish['d']}")
    assert not odamlar.hisob_korishi_mumkin(k, f"maosh:{ish['a']}")  # kassir tafsilotni ko'rmaydi
    assert odamlar.mumkin(k, "maosh_tolash") and not odamlar.mumkin(d, "maosh_tolash")
    assert odamlar.hisob_korishi_mumkin(k, f"kassa:{ish['kassa']}")
    assert not odamlar.hisob_korishi_mumkin(a, f"kassa:{ish['kassa']}")
    hid = hisob.taklif("bonus", {"summa": 100_000, "odam_id": ish["d"]}, ish["a"])
    with pytest.raises(hisob.HisobXato):
        hisob.tasdiqla(hid, ish["a"])  # bonusni faqat boshliq yozadi
    royxat = hisob.harakatlar(korish=a)
    assert all(r["odam_id"] in (ish["a"], None) or r["yozgan_id"] == ish["a"] for r in royxat)


def test_taklif_havolasi_bir_martalik(ish):
    kod = odamlar.taklif_yarat(ish["a"], ish["b"])
    assert odamlar.taklif_ishlat(kod, 111, "akmal")["id"] == ish["a"]
    assert odamlar.taklif_ishlat(kod, 222, "boshqa") is None
    assert odamlar.taklif_ishlat("yolgon-kod", 333, "x") is None
    kod2 = odamlar.taklif_yarat(ish["d"], ish["b"])
    assert odamlar.taklif_ishlat(kod2, 111, "akmal") is None  # bitta Telegram — bitta odam


def test_parol_va_sessiya(ish):
    odamlar.parol_qoy(ish["b"], "rustam", "maxfiy123", ish["b"])
    assert odamlar.kirish("rustam", "noto'g'ri") is None
    o = odamlar.kirish("Rustam", "maxfiy123")
    assert o["id"] == ish["b"]
    assert odamlar.parol_kor(ish["b"], ish["b"]) == "maxfiy123"
    t = odamlar.sessiya_yarat(o["id"])
    assert odamlar.sessiya_odam(t)["id"] == ish["b"]
    odamlar.holat_qoy(ish["b"], "ketgan", ish["b"])
    assert odamlar.sessiya_odam(t) is None


def test_kelajak_sanasi_harakat_emas(ish):
    ertaga = (vaqt.bugun() + timedelta(days=1)).isoformat()
    with pytest.raises(hisob.HisobXato):
        hisob.taklif("kirim", {"summa": 100, "kassa_id": ish["kassa"], "sana": ertaga}, ish["k"])


def test_jurnal_yoziladi(ish):
    hid = hisob.taklif("chiqim", {"summa": 10_000, "kassa_id": ish["kassa"]}, ish["k"])
    hisob.tasdiqla(hid, ish["k"])
    hisob.bekor_qil(hid, ish["k"], "xato")
    amallar = [r["amal"] for r in baza.hammasi("SELECT amal FROM jurnal WHERE obyekt=?", f"harakat:{hid}")]
    assert "harakat_faol" in amallar and "harakat_bekor" in amallar


def test_zaxira_nusxa(ish, tmp_path):
    from miya import zaxira
    baza.sozlama_qoy("zaxira_yol2", str(tmp_path / "ikkinchi"))
    odamlar.parol_qoy(ish["b"], "rustam", "maxfiy123", ish["b"])  # shifr kaliti paydo bo'ladi
    n = zaxira.ol()
    assert n["butun"] and n["mos"] and n["ikkinchi"]
    assert os.path.exists(os.path.join(os.path.dirname(n["yol"]), ".kalit"))
    assert not zaxira.kerakmi() or vaqt.hozir().strftime("%H:%M") < zaxira.VAQT


def test_serverda_birinchi_sozlash_kod_bilan(tmp_path, monkeypatch):
    import asyncio
    import subprocess
    from fastapi import HTTPException, Response
    from starlette.requests import Request
    from miya import veb
    vaqt._siljish = timedelta(0)
    baza.boshlash(str(tmp_path / "s.db"))
    monkeypatch.setenv("MIYA_PROXY", "1")
    assert veb.holat() == {"sozlangan": False, "kod_kerak": True}
    kod = subprocess.run([sys.executable, "-m", "miya.sozlash_kodi"], capture_output=True, text=True,
                         env={**os.environ, "MIYA_BAZA": str(tmp_path / "s.db")},
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).stdout.strip()
    assert len(kod) == 8

    def sorov(tana):
        async def qabul():
            return {"type": "http.request", "body": json.dumps(tana).encode()}
        return Request({"type": "http", "method": "POST", "path": "/api/sozlash", "headers": [], "client": ("1.2.3.4", 1),
                        "scheme": "https", "query_string": b"", "server": ("x", 443)}, qabul)
    with pytest.raises(HTTPException) as x:
        asyncio.run(veb.sozlash(sorov({"ism": "Begona", "login": "begona", "parol": "123456", "kod": "XXXXXXXX"}), Response()))
    assert x.value.status_code == 403 and odamlar.boshliq() is None
    asyncio.run(veb.sozlash(sorov({"ism": "Rustam Aliyev", "login": "rustam", "parol": "1234567", "kod": kod.lower()}), Response()))
    assert odamlar.boshliq()["ism"] == "Rustam Aliyev" and baza.sozlama("sozlash_kodi") is None


def test_xodim_login_parol_bilan_kiradi(ish):
    odamlar.parol_qoy(ish["a"], "akmal", "akmal123", ish["b"])
    assert odamlar.kirish("Akmal", "akmal123")["id"] == ish["a"]  # xodim ham panelga kiradi
    assert odamlar.kirish("akmal", "noto'g'ri") is None
    assert odamlar.parol_kor(ish["a"], ish["b"]) == "akmal123"  # boshliq doimiy parolni ko'radi
    with pytest.raises(ValueError):
        odamlar.parol_qoy(ish["d"], "akmal", "dilshod1", ish["b"])  # login band
