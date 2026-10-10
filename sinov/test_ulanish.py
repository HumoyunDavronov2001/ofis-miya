"""Tashqi xizmatlar bilan ulanish (haqiqiy sinovdan oldin): Anthropic, Google ovoz, Telegram — tarmoqsiz, soxta javoblar bilan."""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import ai, baza, bot as bot_m, ovoz  # noqa: E402


def soxta_httpx(monkeypatch, modul, handler):
    asl = httpx.AsyncClient

    def yasa(*a, **k):
        k.pop("transport", None)
        return asl(*a, transport=httpx.MockTransport(handler), **k)
    monkeypatch.setattr(modul.httpx, "AsyncClient", yasa)


# ---------- Anthropic kaliti ----------

@pytest.mark.parametrize("kod, kutilgan", [(200, None), (401, "Kalit noto'g'ri")])
def test_anthropic_kaliti_pulsiz_tekshiriladi(monkeypatch, kod, kutilgan):
    import anthropic
    sorovlar = []

    def handler(req):
        sorovlar.append(req.url.path)
        if kod == 200:
            return httpx.Response(200, json={"data": [], "has_more": False, "first_id": None, "last_id": None})
        return httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
    asl = anthropic.AsyncAnthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic",
                        lambda **k: asl(**k, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    assert asyncio.run(ai.tekshir("sk-sinov")) == kutilgan
    assert sorovlar == ["/v1/models"]  # matn yozdirilmaydi — pul ketmaydi


def test_umumiy_anthropic_kaliti_olinmaydi(monkeypatch, tmp_path):
    baza.boshlash(str(tmp_path / "m.db"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "boshqa-loyiha-kaliti")
    monkeypatch.delenv("MIYA_ANTHROPIC_KALIT", raising=False)
    assert ai.kalit() is None
    monkeypatch.setenv("MIYA_ANTHROPIC_KALIT", "miya-kaliti")
    assert ai.kalit() == "miya-kaliti"


# ---------- Google ovoz ----------

@pytest.mark.parametrize("kod, xabar, kutilgan", [
    (400, "RecognitionAudio not set.", None),
    (400, "API key not valid. Please pass a valid API key.", "Kalit noto'g'ri yoki bloklangan"),
    (403, "Cloud Speech-to-Text API has not been used in project 1 before or it is disabled.", "xizmati yoqilmagan")])
def test_google_kaliti_tekshiriladi(monkeypatch, kod, xabar, kutilgan):
    soxta_httpx(monkeypatch, ovoz, lambda req: httpx.Response(kod, json={"error": {"code": kod, "message": xabar}}))
    natija = asyncio.run(ovoz.tekshir("AIza-sinov"))
    assert natija == kutilgan or (kutilgan and kutilgan in natija)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yo'q")
def test_mp3_va_uzun_ovoz_opus_bolaklarga(monkeypatch, tmp_path, ish_baza=None):
    baza.boshlash(str(tmp_path / "m.db"))
    yol = tmp_path / "ovoz.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=70",
                    "-ar", "16000", str(yol)], check=True)
    yuborilgan = []

    def handler(req):
        tana = json.loads(req.content)
        yuborilgan.append((tana["config"], base64.b64decode(tana["audio"]["content"])[:4]))
        return httpx.Response(200, json={"results": [{"alternatives": [{"transcript": "salom", "words": [
            {"word": "salom", "startTime": "1.5s"}]}]}]})
    soxta_httpx(monkeypatch, ovoz, handler)
    monkeypatch.setenv("MIYA_GOOGLE_KALIT", "AIza-sinov")
    matn_, sozlar, davom = asyncio.run(ovoz.matnga(str(yol), 70))
    assert len(yuborilgan) == 2 and all(b == b"OggS" for _, b in yuborilgan)  # 55 s + 15 s, OGG/Opus
    assert yuborilgan[0][0]["sampleRateHertz"] == 48000 and yuborilgan[0][0]["languageCode"] == "uz-UZ"
    assert [s["dan"] for s in sozlar] == [1.5, 56.5]  # ikkinchi bo'lak vaqti suriladi
    assert matn_ == "salom salom" and round(davom) == 70


def test_google_400_navbatda_aylanmaydi(monkeypatch, tmp_path):
    baza.boshlash(str(tmp_path / "m.db"))
    yol = tmp_path / "v.ogg"
    yol.write_bytes(b"OggS" + b"\0" * 100)
    soxta_httpx(monkeypatch, ovoz, lambda req: httpx.Response(400, json={"error": {"message": "Invalid audio"}}))
    monkeypatch.setenv("MIYA_GOOGLE_KALIT", "AIza-sinov")
    monkeypatch.setattr(ovoz.shutil, "which", lambda n: None)  # ffmpeg'siz yo'l
    with pytest.raises(ovoz.OvozXato) as x:
        asyncio.run(ovoz.matnga(str(yol), 5))
    assert x.value.vaqtincha is False


# ---------- Telegram ----------

def test_bot_webhookni_ochiradi_va_409_ni_aytadi(tmp_path, monkeypatch):
    baza.boshlash(str(tmp_path / "m.db"))
    asl_sleep = asyncio.sleep

    async def tez(_s):  # 409 dan keyingi 10 soniyalik kutish sinovni sekinlatmasin
        await asl_sleep(0)
    monkeypatch.setattr(bot_m.asyncio, "sleep", tez)
    b = bot_m.Bot("SINOV")
    chaqiruvlar = []

    async def api(metod, **p):
        chaqiruvlar.append(metod)
        if metod == "getMe":
            return {"username": "miya_sinov_bot"}
        if metod == "getUpdates":
            b.ishlayapti = False
            raise bot_m.TgXato(409, "Conflict: terminated by other getUpdates request")
        return True
    b.api = api

    async def ish():
        await b.boshla()
        b.vazifalar[1].cancel()
        b.vazifalar[2].cancel()
        await asyncio.wait_for(asyncio.gather(b.vazifalar[0], return_exceptions=True), 5)
        await b.mijoz.aclose()
    asyncio.run(ish())
    assert chaqiruvlar[:3] == ["getMe", "deleteWebhook", "setMyCommands"]
    assert "boshqa dasturda ham ishlayapti" in b.oxirgi_xato
    assert baza.sozlama("bot_nomi") == "miya_sinov_bot"
