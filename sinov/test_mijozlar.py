"""3-bosqich: va'dalar daftari (to'lovlarni taqsimlash, holatlar), mijoz kartasi, uxlab qolganlar, nasiya qoidasi."""
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import baza, hisob, kurs, maosh, mijozlar, odamlar, qoida, vadalar, vaqt  # noqa: E402


@pytest.fixture()
def ish(tmp_path):
    vaqt._siljish = timedelta(0)
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Rustam Aliyev", "boshliq")
    k = odamlar.odam_yarat("Dilnoza Qodirova", "kassir", kim_id=b, maosh_tolaydi=1)
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    d = odamlar.odam_yarat("Dilshod Rahimov", "xodim", kim_id=b)
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", k, b)
    maosh.boshlangan_oy()
    hisob.tasdiqla(hisob.taklif("boshlangich_kassa", {"summa": 5_000_000, "kassa_id": kassa}, b), b)
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    yield {"b": b, "k": k, "a": a, "d": d, "kassa": kassa, "m": mid}
    vaqt._siljish = timedelta(0)


def kun(n: int) -> str:
    return (vaqt.bugun() + timedelta(days=n)).isoformat()


def siljit(n: int) -> None:
    vaqt._siljish += timedelta(days=n)


def faol(hid: int, kim: int) -> int:
    if hisob.tasdiqla(hid, kim)["holat"] == "takror":
        hisob.faollashtir(hid, kim)
    return hid


def tolov(ish, summa, sana=None, xabar_id=None, valyuta="UZS", mid=None):
    p = {"summa": summa, "kassa_id": ish["kassa"], "mijoz_id": mid or ish["m"], "valyuta": valyuta}
    if sana:
        p["sana"] = sana
    return faol(hisob.taklif("kirim", p, ish["b"], xabar_id), ish["b"])


def sotuv(ish, summa, tolandi=0, muddat=None, sana=None, kim=None, mid=None):
    p = {"summa": summa, "tolandi": tolandi, "mijoz_id": mid or ish["m"], "kassa_id": ish["kassa"]}
    if muddat:
        p["muddat"] = muddat
    if sana:
        p["sana"] = sana
    sid, kid = hisob.sotuv_tuz(p, kim or ish["b"])
    r = hisob.tasdiqla(sid, kim or ish["b"])
    if r["holat"] == "takror":
        r = hisob.faollashtir(sid, kim or ish["b"])
    if kid and r["holat"] == "faol":
        faol(kid, kim or ish["b"])
    return sid, r


def holat(vid: int) -> str:
    return vadalar.holati(vadalar.vada(vid))


# ---------- to'lov va'dalari (C4, C-b, C-c) ----------

def test_vaqtida_bajarildi(ish):
    vid = vadalar.yoz(ish["m"], kun(3), ish["b"], summa=2_000_000)
    assert holat(vid) == "ochiq"
    siljit(1)
    tolov(ish, 2_000_000)
    assert holat(vid) == "vaqtida"
    assert vadalar.ishonch(ish["m"])["matn"] == "oldingi 1 ta va'dadan 1 tasi vaqtida"


def test_qisman_va_buzildi(ish):
    v1 = vadalar.yoz(ish["m"], kun(2), ish["b"], summa=2_000_000)
    siljit(1)
    tolov(ish, 500_000)
    assert holat(v1) == "ochiq"  # muddat hali o'tmagan
    siljit(2)
    assert holat(v1) == "qisman"
    m2 = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Botir Sobirov',?)", vaqt.iso())
    v2 = vadalar.yoz(m2, kun(1), ish["b"], summa=1_000_000)
    siljit(2)
    assert holat(v2) == "buzildi"


def test_kech_bajarildi(ish):
    vid = vadalar.yoz(ish["m"], kun(1), ish["b"], summa=1_000_000)
    siljit(3)
    assert holat(vid) == "buzildi"
    tolov(ish, 1_000_000)
    assert holat(vid) == "kech"


def test_vadadan_oldingi_tolov_hisoblanmaydi(ish):
    tolov(ish, 2_000_000, sana=kun(-1))
    vid = vadalar.yoz(ish["m"], kun(2), ish["b"], summa=2_000_000)
    r = [v for v in vadalar.royxat(ish["m"]) if v["id"] == vid][0]
    assert r["qoplandi"] == 0 and r["holat_h"] == "ochiq"


def test_bir_xabardagi_tolov_shu_vadaga_yozilmaydi(ish):
    xid = baza.bajar("INSERT INTO xabar(odam_id,tur,matn,vaqt) VALUES(?,?,?,?)", ish["b"], "matn",
                     "Karimov 1 mln berdi, qolganini jumada beradi", vaqt.iso())
    vid = vadalar.yoz(ish["m"], kun(3), ish["b"], summa=2_000_000, xabar_id=xid)
    tolov(ish, 1_000_000, xabar_id=xid)  # va'dadan keyin yozilgan bo'lsa ham
    assert [v for v in vadalar.royxat(ish["m"]) if v["id"] == vid][0]["qoplandi"] == 0


def test_ikki_vada_muddat_tartibida(ish):
    v1 = vadalar.yoz(ish["m"], kun(2), ish["b"], summa=1_000_000)
    v2 = vadalar.yoz(ish["m"], kun(5), ish["b"], summa=1_000_000)
    siljit(1)
    tolov(ish, 1_500_000)
    r = {v["id"]: v for v in vadalar.royxat(ish["m"])}
    assert r[v1]["qoplandi"] == 1_000_000 and r[v2]["qoplandi"] == 500_000  # bitta to'lov ikki marta yozilmaydi
    siljit(5)
    assert holat(v1) == "vaqtida" and holat(v2) == "qisman"


def test_yangi_vada_buzilganini_yopadi(ish):
    eski = vadalar.yoz(ish["m"], kun(1), ish["b"], summa=2_000_000)
    siljit(3)
    assert [v["id"] for v in vadalar.almashadiganlar(ish["m"])] == [eski]
    yangi = vadalar.yoz(ish["m"], kun(4), ish["b"], summa=2_000_000)
    assert vadalar.vada(eski)["holat"] == "bajarilmadi"
    siljit(2)
    tolov(ish, 2_000_000)
    assert holat(yangi) == "vaqtida"
    assert holat(eski) == "buzildi"  # keyingi to'lov eskisiga ketmadi
    assert vadalar.ishonch(ish["m"])["vaqtida"] == 1


def test_kech_kiritilgan_tolov_holatni_tuzatadi(ish):
    vid = vadalar.yoz(ish["m"], kun(2), ish["b"], summa=1_000_000)
    yozilgan_kun = kun(1)
    siljit(5)
    assert holat(vid) == "buzildi"
    tolov(ish, 1_000_000, sana=yozilgan_kun)  # aslida muddatida to'lagan, kech kiritildi
    assert holat(vid) == "vaqtida"


def test_dollar_vada_somda_tolandi(ish):
    vid = vadalar.yoz(ish["m"], kun(3), ish["b"], summa=10_000, valyuta="USD")  # 100 $
    siljit(1)
    kurs.kurs_qoy(kun(0), "USD", 12_000)
    tolov(ish, 1_200_000)
    assert holat(vid) == "vaqtida"


def test_bekor_qilingan_vada_hisobga_kirmaydi(ish):
    vid = vadalar.yoz(ish["m"], kun(1), ish["b"], summa=1_000_000)
    with pytest.raises(vadalar.VadaXato):
        vadalar.bekor(vid, ish["b"], "")
    vadalar.bekor(vid, ish["b"], "adashib yozilgan")
    siljit(3)
    assert holat(vid) == "bekor"
    assert vadalar.ishonch(ish["m"])["jami"] == 0


def test_boshqa_vada_qolda_yopiladi(ish):
    v1 = vadalar.yoz(ish["m"], kun(2), ish["b"], tur="boshqa", matn_="hujjatni olib keladi")
    v2 = vadalar.yoz(ish["m"], kun(1), ish["b"], tur="boshqa", matn_="namunani qaytaradi")
    vadalar.boshqa_yop(v1, ish["a"], True)
    assert holat(v1) == "vaqtida"
    siljit(2)
    assert holat(v2) == "buzildi"
    with pytest.raises(vadalar.VadaXato):
        vadalar.yoz(ish["m"], kun(1), ish["b"], tur="boshqa")  # nima va'da qilingani yo'q
    with pytest.raises(vadalar.VadaXato):
        vadalar.yoz(ish["m"], kun(1), ish["b"], summa=0)  # to'lov va'dasida summa yo'q


def test_masul_mijozdan_olinadi(ish):
    baza.bajar("UPDATE mijoz SET masul_id=? WHERE id=?", ish["a"], ish["m"])
    vid = vadalar.yoz(ish["m"], kun(1), ish["b"], summa=1_000_000)
    assert vadalar.vada(vid)["masul_id"] == ish["a"]


def test_kutilayotgan_tushum(ish):
    vadalar.yoz(ish["m"], kun(0), ish["b"], summa=1_000_000)
    vadalar.yoz(ish["m"], kun(10), ish["b"], summa=2_000_000)
    vadalar.yoz(ish["m"], kun(40), ish["b"], summa=5_000_000)  # 30 kundan keyin — kirmaydi
    t = vadalar.kutilayotgan_tushum(30)
    assert t["bugun"] == 1_000_000 and t["jami"] == 3_000_000


# ---------- nasiyali sotuv → va'da ----------

def test_nasiyali_sotuv_vada_yozadi(ish):
    sid, _ = sotuv(ish, 5_000_000, tolandi=2_000_000, muddat=kun(7))
    v = baza.bir("SELECT * FROM vada WHERE harakat_id=?", sid)
    assert v and v["summa"] == 3_000_000 and v["muddat"] == kun(7)
    assert hisob.mijoz_qarzlari()[0]["muddat"] == kun(7)
    hisob.bekor_qil(sid, ish["b"], "xato yozildi")
    assert vadalar.vada(v["id"])["holat"] == "bekor"


def test_muddatsiz_yoki_tolangan_sotuv_vada_yozmaydi(ish):
    sotuv(ish, 1_000_000)
    sotuv(ish, 2_000_000, tolandi=2_000_000, muddat=kun(3))
    assert baza.qiymat("SELECT COUNT(*) FROM vada") == 0


def test_taminotchi_qarz_muddati(ish):
    t = baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES('Olmos savdo','taminotchi',?)", vaqt.iso())
    faol(hisob.taklif("taminotchi_nasiya", {"summa": 3_000_000, "mijoz_id": t, "muddat": kun(2)}, ish["b"]), ish["b"])
    q = hisob.mijoz_qarzlari("taminotchi")
    assert q[0]["muddat"] == kun(2) and q[0]["qarz"] == {"UZS": 3_000_000}


# ---------- nasiya qoidasi (Q-a) ----------

def test_nasiya_ishonch_qoidasi(ish):
    qoida.qoy("nasiya_ishonch", {"foiz": 60, "kamida": 3}, ish["b"])
    for i in range(3):  # 3 ta va'da: 1 tasi vaqtida
        vadalar.yoz(ish["m"], kun(1), ish["b"], summa=100_000)
        if i == 0:
            vaqt._siljish += timedelta(hours=1)
            tolov(ish, 100_000)
        siljit(2)
    assert vadalar.ishonch(ish["m"])["vaqtida"] == 1
    sid, r = sotuv(ish, 1_000_000, tolandi=200_000, kim=ish["k"])
    assert r["holat"] == "ruxsat_kutilmoqda" and "1 tasi vaqtida" in hisob.harakat(sid)["qoida_buzilish"]
    sid2, r2 = sotuv(ish, 300_000, tolandi=300_000, kim=ish["k"])  # nasiyasiz — qoida tegmaydi
    assert r2["holat"] == "faol"
    yangi = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Yangi mijoz',?)", vaqt.iso())
    _, r3 = sotuv(ish, 500_000, kim=ish["k"], mid=yangi)  # va'da tarixi yo'q — tekshirilmaydi
    assert r3["holat"] == "faol"


def test_ruxsatdan_keyin_boglangan_tolov_ham_yoziladi(ish):
    qoida.qoy("nasiya_chegara", {"summa": 100_000, "valyuta": "UZS"}, ish["b"])
    sid, r = sotuv(ish, 1_000_000, tolandi=400_000, muddat=kun(5), kim=ish["k"])
    assert r["holat"] == "ruxsat_kutilmoqda"
    hisob.ruxsat(sid, ish["b"], True)
    kirim = baza.bir("SELECT * FROM harakat WHERE bog_id=? AND id!=?", sid, sid)
    assert kirim["holat"] == "faol"  # to'langan qism kassaga tushdi
    assert hisob.qoldiq_bir(f"mijoz:{ish['m']}") == 600_000
    assert baza.bir("SELECT summa FROM vada WHERE harakat_id=?", sid)["summa"] == 600_000


def test_rad_etilsa_boglangan_tolov_ham_bekor(ish):
    qoida.qoy("nasiya_chegara", {"summa": 100_000, "valyuta": "UZS"}, ish["b"])
    sid, _ = sotuv(ish, 1_000_000, tolandi=400_000, kim=ish["k"])
    hisob.ruxsat(sid, ish["b"], False)
    assert baza.qiymat("SELECT holat FROM harakat WHERE bog_id=? AND id!=?", sid, sid) == "bekor"


# ---------- mijoz kartasi (C1, C2, C5, C6, C-g) ----------

def test_uxlab_qolgan_mijoz(ish):
    for n in (41, 34, 27, 20):
        sotuv(ish, 1_000_000, tolandi=1_000_000, sana=kun(-n))
    u = mijozlar.uxlash(ish["m"])
    assert u["ortacha_kun"] == 7 and u["otdi_kun"] == 20 and u["uxlagan"]
    assert [m["id"] for m in mijozlar.uxlab_qolganlar()] == [ish["m"]]
    ikkinchi = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Kam xaridli',?)", vaqt.iso())
    for n in (60, 30):
        sotuv(ish, 500_000, tolandi=500_000, sana=kun(-n), mid=ikkinchi)
    tolov(ish, 100_000, mid=ikkinchi)  # to'lov xarid emas (C-f)
    assert mijozlar.uxlash(ikkinchi) is None


def test_eslatma_va_qisqa_malumot(ish):
    sotuv(ish, 3_000_000, tolandi=1_000_000, muddat=kun(5))
    eid = mijozlar.eslatma_qosh(ish["m"], "Faqat naqd to'laydi", ish["a"])
    q = [x.replace("\xa0", " ") for x in mijozlar.qisqa_malumot(ish["m"])]
    assert q[0].startswith("Oxirgi xarid:") and "3 000 000" in q[0]
    assert "Qarzi: 2 000 000 so'm" in q[1] and "va'da tarixi yo'q" in q[1]
    assert q[2].startswith("Va'dasi: 2 000 000 so'm")
    assert mijozlar.eslatmalar(ish["m"])[0]["matn"] == "Faqat naqd to'laydi"
    mijozlar.eslatma_bekor(eid, ish["a"])
    assert mijozlar.eslatmalar(ish["m"]) == []


def test_tarix_hammasini_korsatadi(ish):
    sotuv(ish, 3_000_000, tolandi=1_000_000, muddat=kun(5))
    mijozlar.eslatma_qosh(ish["m"], "Do'koni Chorsuda", ish["b"])
    turlar = {x["tur"] for x in mijozlar.tarix(ish["m"])}
    assert turlar == {"pul", "vada", "eslatma"}


def test_mijozni_kim_koradi(ish):
    m = mijozlar.mijoz(ish["m"])
    assert mijozlar.korishi_mumkin(odamlar.odam(ish["k"]), m)
    assert not mijozlar.korishi_mumkin(odamlar.odam(ish["a"]), m)
    mijozlar.tahrir(ish["m"], ish["b"], masul_id=ish["a"], manzil="Chorsu bozori")
    m = mijozlar.mijoz(ish["m"])
    assert mijozlar.korishi_mumkin(odamlar.odam(ish["a"]), m)
    assert not mijozlar.korishi_mumkin(odamlar.odam(ish["d"]), m)
    assert m["manzil"] == "Chorsu bozori"


def test_yangi_sotuvning_tolovi_eski_vadaga_yozilmaydi(ish):
    vid = vadalar.yoz(ish["m"], kun(3), ish["b"], summa=1_000_000)
    siljit(1)
    sotuv(ish, 4_000_000, tolandi=1_500_000)  # yangi mol uchun to'landi
    assert [v for v in vadalar.royxat(ish["m"]) if v["id"] == vid][0]["qoplandi"] == 0
    tolov(ish, 1_000_000)  # alohida to'lov — eski qarz uchun
    assert holat(vid) == "vaqtida"


def test_savol_asboblari_huquq_bilan(ish):
    from miya import ai
    vadalar.yoz(ish["m"], kun(0), ish["b"], summa=1_000_000)
    kassir, akmal = odamlar.odam(ish["k"]), odamlar.odam(ish["a"])
    d = ai.asbob_bajar(kassir, "mijoz_haqida", {"ism": "Karimov"})
    assert d["mijoz"] == "Anvar Karimov" and d["ochiq_vadalar"][0]["summa"]["summa"] == 1_000_000
    assert "xato" in ai.asbob_bajar(akmal, "mijoz_haqida", {"ism": "Karimov"})  # mas'ul emas (C-g)
    assert ai.asbob_bajar(akmal, "vadalar", {"holat": "bugun"})["vadalar"] == []
    mijozlar.tahrir(ish["m"], ish["b"], masul_id=ish["a"])
    assert "xato" not in ai.asbob_bajar(akmal, "mijoz_haqida", {"ism": "Karimov"})
    assert len(ai.asbob_bajar(kassir, "vadalar", {"holat": "bugun"})["vadalar"]) == 1
