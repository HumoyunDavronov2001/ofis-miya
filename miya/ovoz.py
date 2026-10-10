"""Ovoz → matn (K2): Google Speech-to-Text (o'zbekcha). Kalit — API kaliti.

Telegram ovozli xabari OGG/Opus. 55 soniyadan uzun bo'lsa ffmpeg bilan bo'laklarga bo'linadi.
So'zlarning vaqti saqlanadi — keyin «o'sha joyidan eshittirish» uchun (X2, X6).
"""
import asyncio
import base64
import os
import shutil
import subprocess
import tempfile

import httpx

from . import baza, odamlar, vaqt

URL = "https://speech.googleapis.com/v1/speech:recognize"
DAQIQA_NARXI = 0.024  # $ — standart model, taxminiy
BOLAK = 55


class OvozXato(Exception):
    def __init__(self, xabar: str, vaqtincha: bool = True):
        super().__init__(xabar)
        self.vaqtincha = vaqtincha


SOXTA = None  # sinovlarda: async def(fayl_yoli) -> (matn, sozlar)


def kalit() -> str | None:
    k = os.environ.get("MIYA_GOOGLE_KALIT")
    if k:
        return k
    shifr = baza.sozlama("maxfiy_google")
    if shifr:
        try:
            return odamlar.ochish(shifr)
        except Exception:
            return None
    return None


def yoqilganmi() -> bool:
    return SOXTA is not None or bool(kalit())


def _davomiylik(yol: str) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", yol],
                           capture_output=True, text=True, timeout=20)
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0.0


def _bolakla(yol: str, papka: str) -> list[str]:
    """Har qanday ovoz (mp3, m4a, 16 kHz ogg) → OGG/Opus 48 kHz mono, 55 soniyalik bo'laklar — Google shuni kutadi."""
    chiq = os.path.join(papka, "b%03d.ogg")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", yol, "-vn", "-f", "segment", "-segment_time", str(BOLAK),
                    "-c:a", "libopus", "-ar", "48000", "-ac", "1", chiq], check=True, timeout=120)
    return sorted(os.path.join(papka, f) for f in os.listdir(papka) if f.startswith("b"))


def _xato_matni(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error", {}).get("message", ""))[:300]
    except ValueError:
        return r.text[:300]


async def _tanit(mijoz: httpx.AsyncClient, k: str, mazmun: bytes) -> tuple[str, list]:
    tana = {"config": {"encoding": "OGG_OPUS", "sampleRateHertz": 48000, "languageCode": "uz-UZ",
                       "enableWordTimeOffsets": True, "enableAutomaticPunctuation": True},
            "audio": {"content": base64.b64encode(mazmun).decode()}}
    r = await mijoz.post(URL, params={"key": k}, json=tana, timeout=60)
    if r.status_code in (401, 403) or (r.status_code == 400 and "API key" in _xato_matni(r)):
        raise OvozXato("Ovoz xizmati kaliti noto'g'ri yoki xizmat yoqilmagan", vaqtincha=False)
    if r.status_code == 400:  # qayta urinish foyda bermaydi — navbatda aylanib qolmasin
        raise OvozXato(f"Ovozni o'qib bo'lmadi: {_xato_matni(r)}", vaqtincha=False)
    if r.status_code >= 400:
        raise OvozXato(f"Ovoz xizmati xatosi ({r.status_code})")
    natijalar = r.json().get("results", [])
    matnlar, sozlar = [], []
    for n in natijalar:
        alt = (n.get("alternatives") or [{}])[0]
        if alt.get("transcript"):
            matnlar.append(alt["transcript"].strip())
        for s in alt.get("words", []):
            sozlar.append({"soz": s.get("word"), "dan": float(str(s.get("startTime", "0s")).rstrip("s") or 0)})
    return " ".join(matnlar), sozlar


async def matnga(yol: str, davom: float | None = None) -> tuple[str, list, float]:
    """(matn, so'zlar vaqti bilan, davomiylik soniya). davom — Telegram aytgan uzunlik (ffprobe bo'lmasa)."""
    if SOXTA is not None:
        m, s = await SOXTA(yol)
        return m, s, 1.0
    k = kalit()
    if not k:
        raise OvozXato("Ovozni matnga aylantirish sozlanmagan", vaqtincha=False)
    if shutil.which("ffprobe"):
        davom = await asyncio.to_thread(_davomiylik, yol) or davom
    davom = float(davom or 0)
    matnlar, sozlar = [], []
    async with httpx.AsyncClient() as mijoz:
        if shutil.which("ffmpeg"):
            with tempfile.TemporaryDirectory() as papka:
                try:
                    bolaklar = await asyncio.to_thread(_bolakla, yol, papka)
                except (subprocess.SubprocessError, OSError) as x:
                    raise OvozXato("Ovoz faylini o'qib bo'lmadi", vaqtincha=False) from x
                for i, b in enumerate(bolaklar):
                    with open(b, "rb") as f:
                        m, s = await _tanit(mijoz, k, f.read())
                    matnlar.append(m)
                    sozlar += [{**x, "dan": x["dan"] + i * BOLAK} for x in s]
        else:  # ffmpeg yo'q: Telegram ovozi o'zi OGG/Opus 48 kHz — 1 daqiqagacha to'g'ridan-to'g'ri ketadi
            if davom > 59:
                raise OvozXato("1 daqiqadan uzun ovoz uchun serverga ffmpeg o'rnatilishi kerak", vaqtincha=False)
            with open(yol, "rb") as f:
                m, s = await _tanit(mijoz, k, f.read())
            matnlar.append(m)
            sozlar += s
    baza.bajar("INSERT INTO stt_sarf(vaqt,soniya,narx) VALUES(?,?,?)", vaqt.iso(), davom,
               round(davom / 60 * DAQIQA_NARXI, 5))
    return " ".join(x for x in matnlar if x).strip(), sozlar, davom


async def tekshir(k: str) -> str | None:
    """Kalit to'g'rimi va xizmat yoqilganmi — pulsiz: bo'sh ovoz yuboriladi (kalit to'g'ri bo'lsa «audio yo'q» xatosi)."""
    async with httpx.AsyncClient() as mijoz:
        try:
            r = await mijoz.post(URL, params={"key": k}, timeout=20,
                                 json={"config": {"encoding": "OGG_OPUS", "sampleRateHertz": 48000, "languageCode": "uz-UZ"},
                                       "audio": {"content": ""}})
        except httpx.HTTPError:
            return "Google'ga ulanib bo'lmadi — internetni tekshiring"
    xato = _xato_matni(r)
    if r.status_code == 200 or (r.status_code == 400 and "API key" not in xato):
        return None
    if r.status_code == 403:
        return "Kalit to'g'ri, lekin Speech-to-Text xizmati yoqilmagan (Google Cloud → APIs → Speech-to-Text → Enable)"
    return "Kalit noto'g'ri yoki bloklangan"
