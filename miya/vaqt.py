"""Vaqt — hamma joyda Toshkent vaqti (A5)."""
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Tashkent")
except Exception:  # tz bazasi yo'q tizimda — Toshkent UTC+5, yozgi vaqt yo'q
    TZ = timezone(timedelta(hours=5))

HAFTA = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
OYLAR = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust",
         "sentabr", "oktabr", "noyabr", "dekabr"]

_siljish = timedelta(0)  # faqat sinovlar uchun


def hozir() -> datetime:
    return datetime.now(TZ) + _siljish


def bugun() -> date:
    return hozir().date()


def iso(dt: datetime | None = None) -> str:
    return (dt or hozir()).isoformat(timespec="seconds")


def sana(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return date.fromisoformat(s[:10])


def oy(s: str | date) -> str:
    return sana(s).isoformat()[:7]


def oy_boshi(o: str) -> date:
    return date.fromisoformat(o + "-01")


def oy_oxiri(o: str) -> date:
    b = oy_boshi(o)
    keyingi = date(b.year + (b.month == 12), b.month % 12 + 1, 1)
    return keyingi - timedelta(days=1)


def oldingi_oy(o: str) -> str:
    return oy(oy_boshi(o) - timedelta(days=1))


def keyingi_oy(o: str) -> str:
    return oy(oy_oxiri(o) + timedelta(days=1))


def oylar_oraligi(dan: str, gacha: str) -> list[str]:
    natija, o = [], dan
    while o <= gacha:
        natija.append(o)
        o = keyingi_oy(o)
    return natija


def sana_matn(s: str | date, hafta_kuni: bool = True) -> str:
    d = sana(s)
    m = f"{d.day}-{OYLAR[d.month - 1]}"
    return f"{m}, {HAFTA[d.weekday()]}" if hafta_kuni else m


def oy_matn(o: str) -> str:
    b = oy_boshi(o)
    return f"{OYLAR[b.month - 1].capitalize()} {b.year}"
