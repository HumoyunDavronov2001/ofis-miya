"""Bot oqimlari: soxta Telegram va soxta sun'iy intellekt bilan, boshidan oxirigacha."""
import asyncio
import json
import os
import sys
from datetime import timedelta
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import ai, baza, bot as bot_m, hisob, maosh, odamlar, ovoz, vaqt  # noqa: E402


class SoxtaTelegram:
    """Bot.api o'rniga: yuborilgan xabarlarni yozib boradi."""

    def __init__(self):
        self.yuborilgan = []
        self.msg = 1000

    async def api(self, metod, **p):
        if metod in ("sendMessage", "editMessageText"):
            self.msg += 1
            rm = p.get("reply_markup")
            self.yuborilgan.append({"metod": metod, "chat": p.get("chat_id"), "matn": (p.get("text") or "").replace("\xa0", " "),
                                    "tugmalar": rm if isinstance(rm, dict) else json.loads(rm) if rm else None,
                                    "msg_id": p.get("message_id") or self.msg})
            return {"message_id": p.get("message_id") or self.msg}
        if metod in ("sendVoice", "sendDocument"):
            self.yuborilgan.append({"metod": metod, "chat": p.get("chat_id"), "matn": p.get("caption") or "",
                                    "fayl": p.get("_fayl"), "tugmalar": None, "msg_id": 0})
            return {"message_id": 0}
        return True

    def oxirgi(self, chat=None):
        for x in reversed(self.yuborilgan):
            if chat is None or x["chat"] == chat:
                return x
        return None

    def tugma_data(self, chat, matn_):
        x = self.oxirgi(chat)
        for qator in (x["tugmalar"] or {}).get("inline_keyboard", []):
            for t in qator:
                if t["text"].replace("\xa0", " ").startswith(matn_):
                    return t["callback_data"], x["msg_id"]
        raise AssertionError(f"«{matn_}» tugmasi yo'q: {x}")


def blok(**k):
    return SimpleNamespace(**k)


class SoxtaAI:
    """tushun: matndagi kalit so'zga qarab tayyor javob; sora: asbob → javob."""

    def __init__(self):
        self.tushun_javob = {}
        self.savol_javob = None
        self.xato = None
        self.messages = self

    async def create(self, **kw):
        if self.xato:
            raise self.xato
        usage = blok(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        if "tools" in kw:  # savol-javob
            oxirgi = kw["messages"][-1]
            if isinstance(oxirgi["content"], str):
                asbob, kirish = self.savol_javob["asbob"]
                return blok(content=[blok(type="tool_use", id="t1", name=asbob, input=kirish)], usage=usage,
                            stop_reason="tool_use")
            return blok(content=[blok(type="text", text=self.savol_javob["matn"])], usage=usage, stop_reason="end_turn")
        matn_ = kw["messages"][0]["content"][-1]["text"]
        for kalit, javob in self.tushun_javob.items():
            if kalit in matn_:
                return blok(content=[blok(type="text", text=json.dumps(javob))], usage=usage, stop_reason="end_turn")
        return blok(content=[blok(type="text", text=json.dumps({"yozuvlar": [], "savol": "", "tushunilmadi": "x"}))],
                    usage=usage, stop_reason="end_turn")


def yozuv(**k):
    d = {"tur": "chiqim", "summa": 0, "birlik_noaniq": False, "valyuta": "aytilmagan", "odam": "", "mijoz": "",
         "kassa": "", "kassa2": "", "xarajat_turi": "", "sana": "", "tolandi": 0, "muddat": "", "qoldan": False,
         "izoh": "", "iqtibos": ""}
    d.update(k)
    return d


@pytest.fixture()
def muhit(tmp_path):
    vaqt._siljish = timedelta(0)
    baza.boshlash(str(tmp_path / "miya.db"))
    b = odamlar.odam_yarat("Rustam Aliyev", "boshliq")
    k = odamlar.odam_yarat("Dilnoza Qodirova", "kassir", kim_id=b, maosh_tolaydi=1)
    a = odamlar.odam_yarat("Akmal Toshpo'latov", "xodim", kim_id=b)
    d = odamlar.odam_yarat("Dilshod Rahimov", "xodim", kim_id=b)
    kassa = hisob.kassa_yarat("Asosiy kassa", "naqd", "UZS", k, b)
    odamlar.odam_tahrir(k, b, kassa_id=kassa)
    maosh.boshlangan_oy()
    h = hisob.taklif("boshlangich_kassa", {"summa": 5_000_000, "kassa_id": kassa}, b)
    hisob.tasdiqla(h, b)
    for oid, tg in ((b, 101), (k, 102), (a, 103), (d, 104)):
        baza.bajar("UPDATE odam SET tg_id=? WHERE id=?", tg, oid)
    tg = SoxtaTelegram()
    bot = bot_m.Bot("SINOV")
    bot.api = tg.api

    async def fayl(file_id, nom):
        yol = str(tmp_path / nom)
        with open(yol, "wb") as f:
            f.write(b"OggS")
        return yol
    bot.fayl_yukla = fayl
    sai = SoxtaAI()
    ai.KLIENT = sai
    ovoz.SOXTA = None
    yield SimpleNamespace(b=b, k=k, a=a, d=d, kassa=kassa, tg=tg, bot=bot, ai=sai)
    ai.KLIENT = None
    ovoz.SOXTA = None


_msg = [0]


def xabar(tg_id, matn_=None, **qosh):
    _msg[0] += 1
    m = {"message_id": _msg[0], "from": {"id": tg_id, "username": f"u{tg_id}"},
         "chat": {"id": tg_id, "type": "private"}}
    if matn_ is not None:
        m["text"] = matn_
    m.update(qosh)
    return {"update_id": _msg[0], "message": m}


def bosish(tg_id, data, msg_id):
    _msg[0] += 1
    return {"update_id": _msg[0], "callback_query": {"id": str(_msg[0]), "from": {"id": tg_id}, "data": data,
                                                     "message": {"message_id": msg_id, "chat": {"id": tg_id}}}}


def ishla(m, u):
    asyncio.run(m.bot.ishla(u))


def kassa_q(m):
    return hisob.qoldiq_bir(f"kassa:{m.kassa}")


# ---------- sinovlar ----------

def test_begona_odamga_hech_narsa(muhit):
    ishla(muhit, xabar(999, "salom"))
    assert "yopiq bot" in muhit.tg.oxirgi(999)["matn"]
    ishla(muhit, xabar(999, "/start yolgon"))
    assert "yopiq bot" in muhit.tg.oxirgi(999)["matn"]


def test_taklif_havolasi_bilan_ulanish(muhit):
    yangi = odamlar.odam_yarat("Sardor Yusupov", "xodim", muhit.b)
    kod = odamlar.taklif_yarat(yangi, muhit.b)
    ishla(muhit, xabar(555, f"/start {kod}"))
    assert "Xush kelibsiz, Sardor" in muhit.tg.oxirgi(555)["matn"]
    assert odamlar.odam_tg(555)["id"] == yangi


def test_avans_kartochka_va_ikki_tomon(muhit):
    muhit.ai.tushun_javob["500 ming avans"] = {"yozuvlar": [yozuv(tur="avans", summa=500000, valyuta="UZS",
                                                                  odam="Akmal", iqtibos="Akmalga 500 ming avans berdim")],
                                              "savol": "", "tushunilmadi": ""}
    ishla(muhit, xabar(102, "Akmalga 500 ming avans berdim"))
    karta = muhit.tg.oxirgi(102)
    assert "500 000 so'm" in karta["matn"] and "besh yuz ming so'm" in karta["matn"]
    assert "Akmal «oldim»" in karta["matn"]
    assert kassa_q(muhit) == 5_000_000  # «To'g'ri» bosilmaguncha hech narsa yozilmaydi
    data, mid = muhit.tg.tugma_data(102, "To'g'ri")
    ishla(muhit, bosish(102, data, mid))
    assert kassa_q(muhit) == 4_500_000
    assert "Akmal tasdig'i kutilmoqda" in muhit.tg.oxirgi(102)["matn"]
    asyncio.run(muhit.bot.xabarnoma_yubor())
    sorov = muhit.tg.oxirgi(103)
    assert "Oldingizmi?" in sorov["matn"]
    data, mid = muhit.tg.tugma_data(103, "Ha, oldim")
    ishla(muhit, bosish(103, data, mid))
    assert hisob.qoldiq_bir(f"maosh:{muhit.a}") == 500_000


def test_noaniq_birlik_soraladi(muhit):
    muhit.ai.tushun_javob["500 berdim"] = {"yozuvlar": [yozuv(tur="avans", summa=500, birlik_noaniq=True, odam="Akmal")],
                                          "savol": "", "tushunilmadi": ""}
    ishla(muhit, xabar(102, "Akmalga 500 berdim"))
    assert "qaysi biri?" in muhit.tg.oxirgi(102)["matn"]
    data, mid = muhit.tg.tugma_data(102, "500 000 so'm")
    ishla(muhit, bosish(102, data, mid))
    assert "<b>500 000 so'm</b>" in muhit.tg.oxirgi(102)["matn"]


def test_ikki_karimov_tanlanadi(muhit):
    for ism in ("Anvar Karimov", "Botir Karimov"):
        baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES(?,?)", ism, vaqt.iso())
    muhit.ai.tushun_javob["Karimov"] = {"yozuvlar": [yozuv(tur="kirim", summa=3000000, valyuta="UZS", mijoz="Karimov")],
                                       "savol": "", "tushunilmadi": ""}
    ishla(muhit, xabar(102, "Karimov 3 mln to'ladi"))
    assert "qaysi mijoz" in muhit.tg.oxirgi(102)["matn"]
    data, mid = muhit.tg.tugma_data(102, "Anvar Karimov")
    ishla(muhit, bosish(102, data, mid))
    karta = muhit.tg.oxirgi(102)
    assert "Anvar Karimov" in karta["matn"]
    data, mid = muhit.tg.tugma_data(102, "To'g'ri")
    ishla(muhit, bosish(102, data, mid))
    assert kassa_q(muhit) == 8_000_000


def test_tugma_bilan_xarajat_sun_iy_intellektsiz(muhit):
    ai.KLIENT = None
    ishla(muhit, xabar(102, "Xarajat"))
    assert "Summani yozing" in muhit.tg.oxirgi(102)["matn"]
    ishla(muhit, xabar(102, "320 ming"))
    karta = muhit.tg.oxirgi(102)
    assert "320 000 so'm" in karta["matn"] and "Asosiy kassa" in karta["matn"]
    data, mid = muhit.tg.tugma_data(102, "To'g'ri")
    ishla(muhit, bosish(102, data, mid))
    assert kassa_q(muhit) == 4_680_000


def test_takror_birlashadi(muhit):
    muhit.ai.tushun_javob["avans berdim"] = {"yozuvlar": [yozuv(tur="avans", summa=500000, valyuta="UZS", odam="Akmal")],
                                            "savol": "", "tushunilmadi": ""}
    muhit.ai.tushun_javob["avans oldim"] = {"yozuvlar": [yozuv(tur="avans", summa=500000, valyuta="UZS")],
                                           "savol": "", "tushunilmadi": ""}
    ishla(muhit, xabar(102, "Akmalga 500 ming avans berdim"))
    data, mid = muhit.tg.tugma_data(102, "To'g'ri")
    ishla(muhit, bosish(102, data, mid))
    ishla(muhit, xabar(103, "500 ming avans oldim"))
    assert "allaqachon yozgan" in muhit.tg.oxirgi(103)["matn"]  # yangi yozuv emas — tasdiq
    data, mid = muhit.tg.tugma_data(103, "Ha, oldim")
    ishla(muhit, bosish(103, data, mid))
    assert kassa_q(muhit) == 4_500_000
    assert hisob.qoldiq_bir(f"maosh:{muhit.a}") == 500_000
    # boshqa avans bo'lsa — kartochka davom etadi
    ishla(muhit, xabar(103, "500 ming avans oldim"))
    assert "Qaysi kassa?" in muhit.tg.oxirgi(103)["matn"]


def test_savol_javob_va_raqam_tekshiruvi(muhit):
    maosh.shart_qoy(muhit.d, "oylik", 4_200_000, "UZS", vaqt.oy_boshi(vaqt.oy(vaqt.bugun())).isoformat(), muhit.b)
    muhit.ai.tushun_javob["qancha qarzmiz"] = {"yozuvlar": [], "savol": "Dilshodga qancha qarzmiz?", "tushunilmadi": ""}
    muhit.ai.savol_javob = {"asbob": ("xodim_hisobi", {"ism": "Dilshod"}),
                            "matn": "Dilshod Rahimovga 4 200 000 so'm qarzmiz (shu oy oyligi)."}
    ishla(muhit, xabar(101, "Dilshodga qancha qarzmiz?"))
    assert "4 200 000 so'm qarzmiz" in muhit.tg.oxirgi(101)["matn"]
    # sun'iy intellekt raqamni o'zgartirsa — tayyor qolip
    muhit.ai.savol_javob["matn"] = "Dilshodga 4 700 000 so'm qarzmiz."
    ishla(muhit, xabar(101, "Dilshodga qancha qarzmiz?"))
    javob = muhit.tg.oxirgi(101)["matn"]
    assert "4 700 000" not in javob and "qolgani 4 200 000" in javob


def test_xodim_boshqaning_maoshini_bilolmaydi(muhit):
    maosh.shart_qoy(muhit.d, "oylik", 4_200_000, "UZS", vaqt.oy_boshi(vaqt.oy(vaqt.bugun())).isoformat(), muhit.b)
    akmal = odamlar.odam(muhit.a)
    r = ai.asbob_bajar(akmal, "xodim_hisobi", {"ism": "Dilshod"})
    assert "huquqingiz yo'q" in r["xato"]
    assert "xodim_hisobi" not in [x["name"] for x in ai.asboblar(akmal)]


def test_kassa_sanogi_bot_orqali(muhit):
    ishla(muhit, bosish(102, f"s:{muhit.kassa}", 1))
    assert "qancha pul bor" in muhit.tg.oxirgi(102)["matn"]
    ishla(muhit, xabar(102, "4 900 000"))
    assert "Farq: −100 000 so'm" in muhit.tg.oxirgi(102)["matn"]
    ishla(muhit, xabar(102, "taksi uchun berildi, yozilmagan"))
    assert baza.bir("SELECT izoh FROM kassa_sanoq")["izoh"].startswith("taksi")


def test_ovozli_xabar(muhit):
    async def stt(yol):
        return "Benzinga 300 ming ketdi", [{"soz": "Benzinga", "dan": 0.2}]
    ovoz.SOXTA = stt
    muhit.ai.tushun_javob["Benzinga"] = {"yozuvlar": [yozuv(tur="chiqim", summa=300000, valyuta="UZS",
                                                             xarajat_turi="Yoqilg'i")], "savol": "", "tushunilmadi": ""}
    ishla(muhit, xabar(102, None, voice={"file_id": "f1", "file_unique_id": "u1", "duration": 4}))
    matnlar = [x["matn"] for x in muhit.tg.yuborilgan if x["chat"] == 102]
    assert any("Eshitildi" in m for m in matnlar)
    assert "300 000 so'm" in muhit.tg.oxirgi(102)["matn"] and "Yoqilg'i" in muhit.tg.oxirgi(102)["matn"]


def test_sun_iy_intellekt_ishlamasa_navbat(muhit):
    muhit.ai.xato = RuntimeError("credit balance is too low")
    ishla(muhit, xabar(102, "Akmalga 500 ming avans berdim"))
    assert "navbatga qo'ydim" in muhit.tg.oxirgi(102)["matn"]
    assert baza.qiymat("SELECT COUNT(*) FROM navbat WHERE holat='kutmoqda'") == 1
    muhit.ai.xato = None
    muhit.ai.tushun_javob["500 ming avans"] = {"yozuvlar": [yozuv(tur="avans", summa=500000, valyuta="UZS", odam="Akmal")],
                                              "savol": "", "tushunilmadi": ""}
    asyncio.run(muhit.bot.jadval())
    assert "500 000 so'm" in muhit.tg.oxirgi(102)["matn"]
    assert baza.qiymat("SELECT holat FROM navbat") == "bajarildi"


def test_bonusni_xodim_yoza_olmaydi(muhit):
    muhit.ai.tushun_javob["bonus"] = {"yozuvlar": [yozuv(tur="bonus", summa=100000, valyuta="UZS", odam="Dilshod")],
                                     "savol": "", "tushunilmadi": ""}
    ishla(muhit, xabar(103, "Dilshodga 100 ming bonus"))
    assert "faqat boshliq" in muhit.tg.oxirgi(103)["matn"]


def test_hisobim(muhit):
    maosh.shart_qoy(muhit.a, "oylik", 4_000_000, "UZS", vaqt.oy_boshi(vaqt.oy(vaqt.bugun())).isoformat(), muhit.b)
    ishla(muhit, xabar(103, "Hisobim"))
    m = muhit.tg.oxirgi(103)["matn"]
    assert "Mening hisobim" in m and "Qolgani: 4 000 000 so'm" in m


def test_telegram_oyna_imzosi(muhit, monkeypatch):
    """T3: imzosiz yoki soxta initData bilan boshqa xodim hisobini ochib bo'lmaydi."""
    import hashlib
    import hmac
    import time
    import urllib.parse
    from miya import veb
    monkeypatch.setenv("MIYA_BOT_TOKEN", "123:SINOV")
    user = json.dumps({"id": 103, "first_name": "Akmal"})
    juft = {"auth_date": str(int(time.time())), "query_id": "q1", "user": user}
    tekshir = "\n".join(f"{k}={v}" for k, v in sorted(juft.items()))
    maxfiy = hmac.new(b"WebAppData", b"123:SINOV", hashlib.sha256).digest()
    juft["hash"] = hmac.new(maxfiy, tekshir.encode(), hashlib.sha256).hexdigest()
    togri = urllib.parse.urlencode(juft)
    assert veb.tg_tekshir(togri)["id"] == muhit.a
    soxta = dict(juft, user=json.dumps({"id": 101, "first_name": "Akmal"}))  # boshliq id'si bilan
    assert veb.tg_tekshir(urllib.parse.urlencode(soxta)) is None
    eski = dict(juft, auth_date=str(int(time.time()) - 3 * 86400))
    assert veb.tg_tekshir(urllib.parse.urlencode(eski)) is None
    assert veb.tg_tekshir("") is None


# ---------- 2-bosqich: ishlar va davomat ----------

def natija(**k):
    d = {"yozuvlar": [], "ishlar": [], "bajarildi": [], "davomat": [], "muammo": "", "savol": "", "tushunilmadi": ""}
    d.update(k)
    return d


def ish_y(**k):
    d = {"nom": "", "ijrochilar": [], "joy": "", "mijoz": "", "muddat": "", "soat": "", "narx": 0, "valyuta": "aytilmagan",
         "ish_turi": "", "dalil": "aytilmagan", "iqtibos": ""}
    d.update(k)
    return d


def test_ish_berish_bajarish_dalil_qabul(muhit):
    from miya import ishlar
    ertaga = (vaqt.bugun() + timedelta(days=1)).isoformat()
    muhit.ai.tushun_javob["kafel"] = natija(ishlar=[ish_y(nom="Kafel yotqizish", ijrochilar=["Akmal"], joy="Chilonzor",
                                                         muddat=ertaga, narx=300000, valyuta="UZS", ish_turi="kafel")])
    ishla(muhit, xabar(101, "Akmal ertaga Chilonzorga borib kafel yotqizsin, 300 ming"))
    karta = muhit.tg.oxirgi(101)["matn"]
    assert "Yangi ish" in karta and "Akmal" in karta and "300 000 so'm" in karta and "Dalil: rasm" in karta
    data, mid = muhit.tg.tugma_data(101, "To'g'ri")
    ishla(muhit, bosish(101, data, mid))
    iid = baza.qiymat("SELECT id FROM ish")
    assert "Ish berildi" in muhit.tg.oxirgi(101)["matn"]
    asyncio.run(muhit.bot.xabarnoma_yubor())
    assert "Sizga yangi ish" in muhit.tg.oxirgi(103)["matn"]
    data, mid = muhit.tg.tugma_data(103, "Ko'rdim")
    ishla(muhit, bosish(103, data, mid))
    assert baza.qiymat("SELECT korildi FROM ish_ijrochi WHERE ish_id=?", iid)
    # Akmal: «tugatdim» → tasdiq → rasm → yopiladi
    muhit.ai.tushun_javob["tugatdim"] = natija(bajarildi=[{"ish_id": iid, "nom": "", "izoh": "", "iqtibos": "tugatdim"}])
    ishla(muhit, xabar(103, "Chilonzordagi ishni tugatdim"))
    assert "Bajarildi deb belgilaymi?" in muhit.tg.oxirgi(103)["matn"]
    data, mid = muhit.tg.tugma_data(103, "Ha, bajarildi")
    ishla(muhit, bosish(103, data, mid))
    assert "rasmini yuboring" in muhit.tg.oxirgi(103)["matn"]
    ishla(muhit, xabar(103, None, photo=[{"file_id": "r1", "file_unique_id": "ur1"}]))
    assert "Ish yopildi" in muhit.tg.oxirgi(103)["matn"]
    assert ishlar.ish(iid)["holat"] == "bajarildi"
    assert maosh.varaq(muhit.a)["ish_kutilmoqda_jami"] == 300_000
    asyncio.run(muhit.bot.xabarnoma_yubor())
    data, mid = muhit.tg.tugma_data(101, "Qabul qilish")
    ishla(muhit, bosish(101, data, mid))
    assert maosh.varaq(muhit.a)["qolgani"] == 300_000


def test_uzatilgan_rasm_dalil_emas(muhit):
    from miya import ishlar
    iid, _ = ishlar.ish_yarat("Bo'yash", [(muhit.a, 1)], muhit.b, dalil_turi="rasm")
    ishla(muhit, bosish(103, f"id:{iid}", 1))
    ishla(muhit, xabar(103, None, photo=[{"file_id": "r2", "file_unique_id": "ur2"}],
                       forward_origin={"type": "user", "sender_user": {"first_name": "Begona"}}))
    assert "uzatilgan" in muhit.tg.oxirgi(103)["matn"].lower()
    assert ishlar.ish(iid)["holat"] == "bajarildi_dalil"


def test_ijrochi_taklif_tugmalari(muhit):
    muhit.ai.tushun_javob["eshik"] = natija(ishlar=[ish_y(nom="Eshik o'rnatish", ish_turi="eshik")])
    ishla(muhit, xabar(101, "Yunusobodda eshik o'rnatish kerak"))
    assert "Kimga beriladi?" in muhit.tg.oxirgi(101)["matn"]
    data, mid = muhit.tg.tugma_data(101, "Dilshod")
    ishla(muhit, bosish(101, data, mid))
    assert "Dilshod Rahimov" in muhit.tg.oxirgi(101)["matn"]


def test_xodim_boshqaga_ish_berolmaydi_botda(muhit):
    muhit.ai.tushun_javob["borsin"] = natija(ishlar=[ish_y(nom="Ombor", ijrochilar=["Dilshod"])])
    ishla(muhit, xabar(103, "Dilshod omborga borsin"))
    assert "boshliq yoki menejer" in muhit.tg.oxirgi(103)["matn"]


def test_royxatda_yoq_ish_xodim_aytgan(muhit):
    from miya import ishlar
    muhit.ai.tushun_javob["eshik o'rnatdim"] = natija(bajarildi=[{"ish_id": 0, "nom": "Sergelida eshik o'rnatish",
                                                                   "izoh": "", "iqtibos": ""}])
    ishla(muhit, xabar(104, "Bugun Sergelida eshik o'rnatdim"))
    data, mid = muhit.tg.tugma_data(104, "Ha")
    ishla(muhit, bosish(104, data, mid))
    i = ishlar.ishlar()[0]
    assert i["manba"] == "xodim" and i["narx"] is None and i["holat"] == "bajarildi_dalil"


def test_davomat_joylashuv_bilan(muhit):
    from miya import davomat
    ishla(muhit, xabar(103, None, location={"latitude": 41.31, "longitude": 69.27}))
    assert "Keldingiz" in muhit.tg.oxirgi(103)["matn"]
    ishla(muhit, xabar(103, None, location={"latitude": 41.31, "longitude": 69.27}))
    assert "Ketdingiz" in muhit.tg.oxirgi(103)["matn"]
    assert davomat.bugungi(muhit.a)["ketdi"]
    ishla(muhit, xabar(104, "keldim"))
    assert "joylashuvsiz" in muhit.tg.oxirgi(104)["matn"]


def test_ertalabki_royxat_va_kechki_savol(muhit):
    from miya import ishlar
    bugun = vaqt.bugun()
    while ishlar.dam_olishmi(bugun):
        bugun += timedelta(days=1)
    nishon = vaqt.hozir().replace(year=bugun.year, month=bugun.month, day=bugun.day, hour=18, minute=30)
    vaqt._siljish = nishon - (vaqt.hozir() - vaqt._siljish)
    iid, _ = ishlar.ish_yarat("Hisobot topshirish", [(muhit.a, 1)], muhit.b, muddat=bugun.isoformat())
    asyncio.run(muhit.bot.ish_jadval())
    asyncio.run(muhit.bot.ish_jadval())  # ikkinchi marta — takror xabar yo'q
    asyncio.run(muhit.bot.xabarnoma_yubor())
    matnlar = [x["matn"] for x in muhit.tg.yuborilgan if x["chat"] == 103]
    assert sum("Bugungi ishlaringiz" in m for m in matnlar) == 1
    assert sum("Bugun nima qildingiz?" in m for m in matnlar) == 1
    assert not [x for x in muhit.tg.yuborilgan if x["chat"] == 104]  # ishi yo'q xodimga xabar bormaydi


def test_mijoz_tasdigi(muhit):
    from miya import ishlar
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    baza.bajar("INSERT INTO mijoz_taklif(kod,mijoz_id,yaratilgan) VALUES('abc',?,?)", mid, vaqt.iso())
    ishla(muhit, xabar(777, "/start mabc"))
    assert "Assalomu alaykum, Anvar" in muhit.tg.oxirgi(777)["matn"]
    iid, _ = ishlar.ish_yarat("Konditsioner o'rnatish", [(muhit.a, 1)], muhit.b, mijoz_id=mid, dalil_turi="mijoz")
    ishla(muhit, bosish(103, f"id:{iid}", 1))
    assert "Mijozdan tasdiq so'raldi" in muhit.tg.oxirgi(103)["matn"]
    data, mid_ = muhit.tg.tugma_data(777, "Ha, bajarildi")
    ishla(muhit, bosish(777, data, mid_))
    assert ishlar.ish(iid)["holat"] == "bajarildi"
    ishla(muhit, xabar(777, "Rahmat, yaxshi ishladi"))
    assert "yetkazildi" in muhit.tg.oxirgi(777)["matn"]


# ---------- 3-bosqich: va'dalar va mijoz eslatmalari ----------

def vada_y(**k):
    d = {"mijoz": "Karimov", "kim": "mijoz", "tur": "tolov", "summa": 0, "birlik_noaniq": False, "valyuta": "aytilmagan",
         "muddat": "", "matn": "", "iqtibos": ""}
    d.update(k)
    return d


def ertalab(soat=9):
    nishon = vaqt.hozir().replace(hour=soat, minute=0)
    vaqt._siljish = nishon - (vaqt.hozir() - vaqt._siljish)


def test_vada_kartochkasi_muddat_soraladi(muhit):
    from miya import vadalar
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    muhit.ai.tushun_javob["to'layman"] = {"yozuvlar": [], "vadalar": [vada_y(summa=2_000_000, valyuta="UZS",
                                                                            iqtibos="2 mln to'layman dedi")]}
    ishla(muhit, xabar(101, "Karimov 2 mln to'layman dedi"))
    assert "Qachongacha?" in muhit.tg.oxirgi(101)["matn"]
    assert not baza.qiymat("SELECT COUNT(*) FROM vada")  # tasdiqsiz yozilmaydi (C-d)
    data, msg = muhit.tg.tugma_data(101, "Ertaga")
    ishla(muhit, bosish(101, data, msg))
    karta = muhit.tg.oxirgi(101)["matn"]
    assert "To'laydi: <b>2 000 000 so'm</b>" in karta and "va'da tarixi yo'q" in karta
    data, msg = muhit.tg.tugma_data(101, "To'g'ri")
    ishla(muhit, bosish(101, data, msg))
    v = vadalar.royxat(mid)[0]
    assert v["summa"] == 2_000_000 and v["muddat"] == (vaqt.bugun() + timedelta(days=1)).isoformat()
    assert "Va'da yozildi" in muhit.tg.oxirgi(101)["matn"]


def test_vada_yozib_muddat_va_butun_qarz(muhit):
    from miya import vadalar
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    h = hisob.taklif("boshlangich_mijoz", {"summa": 3_000_000, "mijoz_id": mid}, muhit.b)
    hisob.tasdiqla(h, muhit.b)
    muhit.ai.tushun_javob["qarzini"] = {"yozuvlar": [], "vadalar": [vada_y()]}
    ishla(muhit, xabar(101, "Karimov qarzini beradi dedi"))
    data, msg = muhit.tg.tugma_data(101, "Butun qarzi — 3 000 000")
    ishla(muhit, bosish(101, data, msg))
    ishla(muhit, xabar(101, "juma"))
    assert "To'laydi: <b>3 000 000 so'm</b>" in muhit.tg.oxirgi(101)["matn"]
    data, msg = muhit.tg.tugma_data(101, "To'g'ri")
    ishla(muhit, bosish(101, data, msg))
    assert vaqt.sana(vadalar.royxat(mid)[0]["muddat"]).weekday() == 4


def test_mijoz_eslatmasi_ozi_saqlanadi(muhit):
    mid = baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    muhit.ai.tushun_javob["naqd"] = {"yozuvlar": [], "mijoz_eslatmalar": [
        {"mijoz": "Karimov", "matn": "Faqat naqd to'laydi", "iqtibos": "Karimov faqat naqd to'laydi"}]}
    ishla(muhit, xabar(103, "Karimov faqat naqd to'laydi"))
    assert "eslatma saqlandi" in muhit.tg.oxirgi(103)["matn"]
    assert baza.qiymat("SELECT COUNT(*) FROM mijoz_eslatma WHERE mijoz_id=? AND bekor=0", mid) == 1
    data, msg = muhit.tg.tugma_data(103, "Bekor qilish")
    ishla(muhit, bosish(104, data, msg))  # boshqa xodim bekor qila olmaydi
    assert baza.qiymat("SELECT COUNT(*) FROM mijoz_eslatma WHERE bekor=0") == 1
    ishla(muhit, bosish(103, data, msg))
    assert baza.qiymat("SELECT COUNT(*) FROM mijoz_eslatma WHERE bekor=0") == 0


def test_vada_eslatmalari_jadvalda(muhit):
    from miya import vadalar
    mid = baza.bajar("INSERT INTO mijoz(ism,masul_id,tg_id,yaratilgan) VALUES('Anvar Karimov',?,777,?)", muhit.a, vaqt.iso())
    ertalab()
    vid = vadalar.yoz(mid, vaqt.bugun().isoformat(), muhit.b, summa=1_000_000)
    asyncio.run(muhit.bot.mijoz_jadval())
    asyncio.run(muhit.bot.mijoz_jadval())  # takror xabar yo'q
    asyncio.run(muhit.bot.xabarnoma_yubor())
    akmal = [x for x in muhit.tg.yuborilgan if x["chat"] == 103]
    assert len(akmal) == 1 and "Bugun va'da muddati" in akmal[0]["matn"]
    data, msg = muhit.tg.tugma_data(103, "Mijozga eslatish")  # mijoz botga ulangan
    ishla(muhit, bosish(103, data, msg))
    assert "to'lov muddati" in muhit.tg.oxirgi(777)["matn"]
    vaqt._siljish += timedelta(days=1)
    asyncio.run(muhit.bot.mijoz_jadval())
    asyncio.run(muhit.bot.mijoz_jadval())
    asyncio.run(muhit.bot.xabarnoma_yubor())
    for chat in (103, 101):  # mas'ul va boshliqqa bir marta
        assert sum("Va'da bajarilmadi" in x["matn"] for x in muhit.tg.yuborilgan if x["chat"] == chat) == 1
    assert vadalar.holati(vadalar.vada(vid)) == "buzildi"


def test_sotuv_kartasida_vada_tarixi(muhit):
    baza.bajar("INSERT INTO mijoz(ism,yaratilgan) VALUES('Anvar Karimov',?)", vaqt.iso())
    muddat = (vaqt.bugun() + timedelta(days=7)).isoformat()
    muhit.ai.tushun_javob["nasiyaga"] = {"yozuvlar": [yozuv(tur="sotuv", summa=5_000_000, valyuta="UZS", mijoz="Karimov",
                                                            tolandi=2_000_000, muddat=muddat)]}
    ishla(muhit, xabar(101, "Karimovga 5 mln ga nasiyaga sotdim, 2 mln berdi"))
    karta = muhit.tg.oxirgi(101)["matn"]
    assert "nasiya: 3 000 000 so'm" in karta and "va'da tarixi yo'q" in karta
    assert "to'lash va'dasi ham yoziladi" in karta
    data, msg = muhit.tg.tugma_data(101, "To'g'ri")
    ishla(muhit, bosish(101, data, msg))
    assert baza.qiymat("SELECT summa FROM vada") == 3_000_000


# ---------- 4-bosqich: usul, qidiruv, xulosa, ketgan xodim ----------

def test_usul_botda_saqlanadi_va_bekor(muhit):
    from miya import usullar
    ishla(muhit, xabar(101, "Usul: Kafel yotqizish\nAvval pol tekislanadi, keyin elim surtiladi"))
    assert "Ish usuli saqlandi" in muhit.tg.oxirgi(101)["matn"]
    assert usullar.qidir("kafel qanday")[0]["sarlavha"] == "Kafel yotqizish"
    ishla(muhit, xabar(103, "Usul: xodim yozolmaydi"))  # xodim — oddiy xabar sifatida ketadi
    assert len(usullar.royxat()) == 1
    data, msg = muhit.tg.tugma_data(101, "Bekor qilish")
    ishla(muhit, bosish(101, data, msg))
    assert usullar.royxat() == []


def test_qidir_ovozni_yuboradi(muhit, tmp_path):
    yol = tmp_path / "ovoz.ogg"
    yol.write_bytes(b"OggS")
    gap = "Karimov bilan narxni metri 45 mingdan kelishdik"
    sozlar = [{"soz": w, "dan": i * 1.0 + 10} for i, w in enumerate(gap.split())]
    baza.bajar("INSERT INTO xabar(odam_id,tur,stt_matn,stt_sozlar,fayl,davomiylik,vaqt,holat) VALUES(?,?,?,?,?,?,?,?)",
               muhit.b, "ovoz", gap, json.dumps(sozlar), str(yol), 30, vaqt.iso(), "ishlandi")
    ishla(muhit, xabar(101, "Qidir: Karimov narx"))
    matnlar = [x for x in muhit.tg.yuborilgan if x["chat"] == 101]
    assert "45 mingdan" in matnlar[-2]["matn"]
    assert matnlar[-1]["metod"] == "sendVoice" and "0:09 dan eshiting" in matnlar[-1]["matn"]
    ishla(muhit, xabar(103, "Qidir: Karimov narx"))  # boshqaning xabari xodimga ochilmaydi
    assert "topilmadi" in muhit.tg.oxirgi(103)["matn"]


def test_ertalabki_xulosa_bir_marta(muhit):
    from miya import ishlar
    bugun = vaqt.bugun()
    while ishlar.dam_olishmi(bugun) or bugun.weekday() == 0:
        bugun += timedelta(days=1)
    nishon = vaqt.hozir().replace(year=bugun.year, month=bugun.month, day=bugun.day, hour=8, minute=40)
    vaqt._siljish = nishon - (vaqt.hozir() - vaqt._siljish)
    ai.KLIENT = None
    asyncio.run(muhit.bot.xulosa_jadval())
    asyncio.run(muhit.bot.xulosa_jadval())
    asyncio.run(muhit.bot.xabarnoma_yubor())
    boss = [x for x in muhit.tg.yuborilgan if x["chat"] == 101]
    assert len(boss) == 1 and "Xayrli tong" in boss[0]["matn"] and "5 000 000" in boss[0]["matn"]


def test_ketgan_xodimga_xabar_bormaydi_eslatma_boshliqqa(muhit):
    from miya import vadalar
    mid = baza.bajar("INSERT INTO mijoz(ism,masul_id,yaratilgan) VALUES('Anvar Karimov',?,?)", muhit.a, vaqt.iso())
    odamlar.holat_qoy(muhit.a, "ketmoqda", muhit.b)
    ertalab()
    vadalar.yoz(mid, vaqt.bugun().isoformat(), muhit.d, summa=1_000_000)
    asyncio.run(muhit.bot.mijoz_jadval())
    hisob.xabarnoma(muhit.a, "malumot", "sinov")
    odamlar.holat_qoy(muhit.a, "ketgan", muhit.b)
    asyncio.run(muhit.bot.xabarnoma_yubor())
    assert not [x for x in muhit.tg.yuborilgan if x["chat"] == 103]
    assert any("Bugun va'da muddati" in x["matn"] for x in muhit.tg.yuborilgan if x["chat"] == 101)


def test_tejash_gaplashuv_va_savol_togridan(muhit):
    chaqiruv = []
    asl = muhit.ai.create

    async def sanovchi(**kw):
        chaqiruv.append("tools" in kw)
        return await asl(**kw)
    muhit.ai.create = sanovchi
    ishla(muhit, xabar(101, "Rahmat"))
    assert "Xo'p" in muhit.tg.oxirgi(101)["matn"] and chaqiruv == []  # Claude chaqirilmadi
    muhit.ai.savol_javob = {"asbob": ("kassalar", {}), "matn": "Asosiy kassada 5 000 000 so'm bor."}
    ishla(muhit, xabar(101, "Kassada qancha pul bor?"))
    assert "5 000 000" in muhit.tg.oxirgi(101)["matn"]
    assert chaqiruv == [True, True]  # faqat savol-javob: «tushunish» bosqichi o'tkazib yuborildi


def test_xodim_havolasi_m_bilan_boshlansa_ham(muhit):
    yangi = odamlar.odam_yarat("Malika Yusupova", "xodim", muhit.b)
    baza.bajar("INSERT INTO taklif(kod,odam_id,yaratilgan) VALUES('mABC123xyz',?,?)", yangi, vaqt.iso())  # eski kod
    ishla(muhit, xabar(556, "/start mABC123xyz"))
    assert "Xush kelibsiz, Malika" in muhit.tg.oxirgi(556)["matn"]
    assert odamlar.taklif_yarat(yangi, muhit.b).startswith("x")
