"""SQLite: ulanish, sxema, tranzaksiya, sozlamalar, jurnal (A4).

Ulanish autocommit rejimida; bir nechta yozuv birga bo'lishi kerak bo'lsa — `with tranz():`.
Jarayon ichida yozuvlar bitta qulf orqali o'tadi (bot va panel bir jarayonda).
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager

from . import vaqt

SXEMA = """
CREATE TABLE IF NOT EXISTS sozlama (kalit TEXT PRIMARY KEY, qiymat TEXT);

CREATE TABLE IF NOT EXISTS odam (
  id INTEGER PRIMARY KEY,
  ism TEXT NOT NULL,
  telefon TEXT,
  lavozim TEXT,
  rol TEXT NOT NULL CHECK (rol IN ('boshliq','menejer','kassir','xodim')),
  tg_id INTEGER UNIQUE,
  tg_nom TEXT,
  holat TEXT NOT NULL DEFAULT 'faol' CHECK (holat IN ('faol','ketmoqda','ketgan')),
  maosh_tolaydi INTEGER NOT NULL DEFAULT 0,
  login TEXT UNIQUE,
  parol_xesh TEXT,
  parol_shifr TEXT,
  kassa_id INTEGER,
  yaratilgan TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS taklif (kod TEXT PRIMARY KEY, odam_id INTEGER NOT NULL, yaratilgan TEXT NOT NULL,
  ishlatilgan TEXT);
CREATE TABLE IF NOT EXISTS sessiya (token_xesh TEXT PRIMARY KEY, odam_id INTEGER NOT NULL, yaratilgan TEXT NOT NULL,
  oxirgi TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS mijoz (
  id INTEGER PRIMARY KEY, ism TEXT NOT NULL, telefon TEXT, izoh TEXT,
  tur TEXT NOT NULL DEFAULT 'mijoz' CHECK (tur IN ('mijoz','taminotchi')),
  tg_id INTEGER, birlashdi INTEGER, yaratilgan TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kassa (
  id INTEGER PRIMARY KEY, nom TEXT NOT NULL,
  tur TEXT NOT NULL CHECK (tur IN ('naqd','karta','bank','chontak')),
  valyuta TEXT NOT NULL DEFAULT 'UZS' CHECK (valyuta IN ('UZS','USD')),
  masul_id INTEGER, faol INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS xarajat_turi (id INTEGER PRIMARY KEY, nom TEXT NOT NULL UNIQUE, faol INTEGER NOT NULL DEFAULT 1);

CREATE TABLE IF NOT EXISTS xabar (
  id INTEGER PRIMARY KEY, odam_id INTEGER, chat_id INTEGER, msg_id INTEGER,
  tur TEXT NOT NULL, matn TEXT, fayl TEXT, davomiylik REAL, stt_matn TEXT, stt_sozlar TEXT,
  uzatilgan TEXT, vaqt TEXT NOT NULL, holat TEXT NOT NULL DEFAULT 'yangi', yashirin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS harakat (
  id INTEGER PRIMARY KEY,
  tur TEXT NOT NULL,
  dan TEXT NOT NULL, ga TEXT NOT NULL,
  summa INTEGER NOT NULL CHECK (summa > 0), valyuta TEXT NOT NULL,
  summa2 INTEGER, valyuta2 TEXT, kurs REAL,
  odam_id INTEGER, mijoz_id INTEGER, xarajat_turi_id INTEGER, sotuvchi_id INTEGER,
  izoh TEXT, iqtibos TEXT,
  voqea_sana TEXT NOT NULL, hisob_sana TEXT NOT NULL, kech INTEGER NOT NULL DEFAULT 0,
  yozilgan TEXT NOT NULL, yozgan_id INTEGER, xabar_id INTEGER,
  holat TEXT NOT NULL DEFAULT 'taklif'
    CHECK (holat IN ('taklif','ruxsat_kutilmoqda','faol','nizo','bekor')),
  beruvchi_holat TEXT NOT NULL DEFAULT 'kerak_emas',
  oluvchi_holat TEXT NOT NULL DEFAULT 'kerak_emas',
  beruvchi_id INTEGER, oluvchi_id INTEGER,
  bog_id INTEGER, asos_id INTEGER, bekor_sabab TEXT,
  manba TEXT NOT NULL DEFAULT 'aytilgan',
  qoida_buzilish TEXT,
  muddat TEXT,
  faollashgan TEXT
);
CREATE INDEX IF NOT EXISTS ix_harakat_dan ON harakat(dan, holat);
CREATE INDEX IF NOT EXISTS ix_harakat_ga ON harakat(ga, holat);
CREATE INDEX IF NOT EXISTS ix_harakat_sana ON harakat(hisob_sana);
CREATE TABLE IF NOT EXISTS harakat_manba (harakat_id INTEGER NOT NULL, xabar_id INTEGER NOT NULL,
  PRIMARY KEY (harakat_id, xabar_id));
CREATE TABLE IF NOT EXISTS ilova (id INTEGER PRIMARY KEY, harakat_id INTEGER, xabar_id INTEGER, fayl TEXT,
  tur TEXT, xesh TEXT, vaqt TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS kassa_sanoq (id INTEGER PRIMARY KEY, kassa_id INTEGER NOT NULL, sana TEXT NOT NULL,
  sanalgan INTEGER NOT NULL, kutilgan INTEGER NOT NULL, farq INTEGER NOT NULL, izoh TEXT, kim_id INTEGER,
  vaqt TEXT NOT NULL, UNIQUE (kassa_id, sana));

CREATE TABLE IF NOT EXISTS maosh_shart (id INTEGER PRIMARY KEY, odam_id INTEGER NOT NULL,
  tur TEXT NOT NULL CHECK (tur IN ('oylik','kunbay','ishbay','foiz')),
  qiymat REAL NOT NULL, valyuta TEXT NOT NULL DEFAULT 'UZS',
  dan_sana TEXT NOT NULL, gacha_sana TEXT, izoh TEXT, yaratilgan TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maosh_davr (oy TEXT PRIMARY KEY, holat TEXT NOT NULL DEFAULT 'ochiq',
  yopilgan TEXT, yopgan_id INTEGER);
CREATE TABLE IF NOT EXISTS ish_kuni (odam_id INTEGER NOT NULL, oy TEXT NOT NULL, kunlar REAL NOT NULL,
  PRIMARY KEY (odam_id, oy));

CREATE TABLE IF NOT EXISTS qoida (id INTEGER PRIMARY KEY, tur TEXT NOT NULL, param TEXT NOT NULL, matn TEXT,
  faol INTEGER NOT NULL DEFAULT 1, yaratilgan TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS jurnal (id INTEGER PRIMARY KEY, vaqt TEXT NOT NULL, kim_id INTEGER, amal TEXT NOT NULL,
  obyekt TEXT, oldin TEXT, keyin TEXT);
CREATE TABLE IF NOT EXISTS kurs (sana TEXT NOT NULL, valyuta TEXT NOT NULL, kurs REAL NOT NULL,
  PRIMARY KEY (sana, valyuta));
CREATE TABLE IF NOT EXISTS ai_sarf (id INTEGER PRIMARY KEY, vaqt TEXT NOT NULL, maqsad TEXT, model TEXT,
  kirish INTEGER, chiqish INTEGER, kesh_oqish INTEGER, kesh_yozish INTEGER, narx REAL);
CREATE TABLE IF NOT EXISTS stt_sarf (id INTEGER PRIMARY KEY, vaqt TEXT NOT NULL, soniya REAL, narx REAL);

CREATE TABLE IF NOT EXISTS karta (id INTEGER PRIMARY KEY, odam_id INTEGER NOT NULL, chat_id INTEGER,
  msg_id INTEGER, xabar_id INTEGER, malumot TEXT NOT NULL, holat TEXT NOT NULL DEFAULT 'ochiq',
  yaratilgan TEXT NOT NULL, harakat_id INTEGER);
CREATE TABLE IF NOT EXISTS suhbat (odam_id INTEGER PRIMARY KEY, holat TEXT, malumot TEXT, vaqt TEXT);
CREATE TABLE IF NOT EXISTS navbat (id INTEGER PRIMARY KEY, xabar_id INTEGER NOT NULL, sabab TEXT, vaqt TEXT NOT NULL,
  urinish INTEGER NOT NULL DEFAULT 0, holat TEXT NOT NULL DEFAULT 'kutmoqda');
CREATE TABLE IF NOT EXISTS xabarnoma (id INTEGER PRIMARY KEY, odam_id INTEGER NOT NULL, tur TEXT NOT NULL,
  harakat_id INTEGER, matn TEXT NOT NULL, tugmalar TEXT, holat TEXT NOT NULL DEFAULT 'yangi',
  vaqt TEXT NOT NULL, tg_msg_id INTEGER, xato TEXT);
CREATE TABLE IF NOT EXISTS yuborildi (kalit TEXT PRIMARY KEY, vaqt TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS ish (
  id INTEGER PRIMARY KEY, nom TEXT NOT NULL, tavsif TEXT, ish_turi TEXT, joy TEXT, lat REAL, lon REAL,
  mijoz_id INTEGER, muddat TEXT, soat TEXT, narx INTEGER, valyuta TEXT NOT NULL DEFAULT 'UZS',
  dalil_turi TEXT NOT NULL DEFAULT 'rasm' CHECK (dalil_turi IN ('rasm','joylashuv','mijoz','yoq')),
  holat TEXT NOT NULL DEFAULT 'yangi'
    CHECK (holat IN ('yangi','bajarildi_dalil','bajarildi','qabul','qayta','bekor')),
  yaratgan_id INTEGER, yaratilgan TEXT NOT NULL, xabar_id INTEGER, takror_id INTEGER, takror_sana TEXT,
  bajarildi_vaqt TEXT, bajargan_id INTEGER, qabul_vaqt TEXT, qabul_id INTEGER, sabab TEXT, izoh TEXT,
  manba TEXT NOT NULL DEFAULT 'boshliq'
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_ish_takror ON ish(takror_id, takror_sana);
CREATE TABLE IF NOT EXISTS ish_ijrochi (ish_id INTEGER NOT NULL, odam_id INTEGER NOT NULL, ulush REAL NOT NULL DEFAULT 1,
  korildi TEXT, PRIMARY KEY (ish_id, odam_id));
CREATE TABLE IF NOT EXISTS ish_dalil (id INTEGER PRIMARY KEY, ish_id INTEGER NOT NULL, tur TEXT NOT NULL, xabar_id INTEGER,
  fayl TEXT, lat REAL, lon REAL, masofa REAL, odam_id INTEGER, mijoz_id INTEGER, izoh TEXT, vaqt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS takroriy_ish (id INTEGER PRIMARY KEY, nom TEXT NOT NULL, ijrochilar TEXT NOT NULL,
  davr TEXT NOT NULL CHECK (davr IN ('har_kun','har_hafta','har_oy')), kun INTEGER, narx INTEGER,
  valyuta TEXT NOT NULL DEFAULT 'UZS', dalil_turi TEXT NOT NULL DEFAULT 'yoq', joy TEXT, ish_turi TEXT,
  faol INTEGER NOT NULL DEFAULT 1, yaratgan_id INTEGER, yaratilgan TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS davomat (id INTEGER PRIMARY KEY, odam_id INTEGER NOT NULL, sana TEXT NOT NULL,
  keldi TEXT, ketdi TEXT, keldi_lat REAL, keldi_lon REAL, ketdi_lat REAL, ketdi_lon REAL,
  holat TEXT NOT NULL DEFAULT 'tasdiq' CHECK (holat IN ('tasdiq','sorov','rad')), izoh TEXT, UNIQUE (odam_id, sana));
CREATE TABLE IF NOT EXISTS odam_hujjat (id INTEGER PRIMARY KEY, odam_id INTEGER NOT NULL, nom TEXT, fayl TEXT NOT NULL,
  yuklagan_id INTEGER, vaqt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mijoz_taklif (kod TEXT PRIMARY KEY, mijoz_id INTEGER NOT NULL, yaratilgan TEXT NOT NULL,
  ishlatilgan TEXT);

CREATE TABLE IF NOT EXISTS vada (id INTEGER PRIMARY KEY, mijoz_id INTEGER NOT NULL,
  kim TEXT NOT NULL DEFAULT 'mijoz' CHECK (kim IN ('mijoz','biz')),
  tur TEXT NOT NULL DEFAULT 'tolov' CHECK (tur IN ('tolov','boshqa')),
  summa INTEGER, valyuta TEXT NOT NULL DEFAULT 'UZS', matn TEXT, muddat TEXT NOT NULL,
  yozilgan TEXT NOT NULL, yozgan_id INTEGER, masul_id INTEGER, xabar_id INTEGER, iqtibos TEXT,
  holat TEXT NOT NULL DEFAULT 'ochiq' CHECK (holat IN ('ochiq','bajarildi','bajarilmadi','bekor')),
  yopilgan TEXT, yopgan_id INTEGER, izoh TEXT, harakat_id INTEGER);
CREATE INDEX IF NOT EXISTS ix_vada_mijoz ON vada(mijoz_id, holat);
CREATE TABLE IF NOT EXISTS usul (id INTEGER PRIMARY KEY, sarlavha TEXT NOT NULL, matn TEXT NOT NULL, yozgan_id INTEGER,
  xabar_id INTEGER, vaqt TEXT NOT NULL, yangilangan TEXT, faol INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS xulosa (id INTEGER PRIMARY KEY, tur TEXT NOT NULL CHECK (tur IN ('kun','hafta')), sana TEXT NOT NULL,
  matn TEXT NOT NULL, qolip INTEGER NOT NULL DEFAULT 1, faktlar TEXT, vaqt TEXT NOT NULL, UNIQUE (tur, sana));
CREATE TABLE IF NOT EXISTS mijoz_eslatma (id INTEGER PRIMARY KEY, mijoz_id INTEGER NOT NULL, matn TEXT NOT NULL,
  manba TEXT NOT NULL DEFAULT 'aytilgan', xabar_id INTEGER, yozgan_id INTEGER, vaqt TEXT NOT NULL,
  bekor INTEGER NOT NULL DEFAULT 0);

-- R5: umumiy xotira — uchrashuv, eslatma, ma'lumot (pul/ish/va'da bo'lmagan hamma gap)
CREATE TABLE IF NOT EXISTS xotira (id INTEGER PRIMARY KEY,
  tur TEXT NOT NULL CHECK (tur IN ('uchrashuv','eslatma','malumot')), matn TEXT NOT NULL,
  sana TEXT, soat TEXT, eslat_vaqt TEXT, eslatildi TEXT,
  holat TEXT NOT NULL DEFAULT 'ochiq' CHECK (holat IN ('ochiq','bajarildi','bekor')),
  yozgan_id INTEGER NOT NULL, kimga_id INTEGER, xabar_id INTEGER, iqtibos TEXT, vaqt TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS xotira_eslat ON xotira(eslat_vaqt) WHERE eslatildi IS NULL AND holat='ochiq';

-- CRM6: katalog va buyurtmalar (summalar minor birlikda: so'm yoki sent)
CREATE TABLE IF NOT EXISTS katalog (id INTEGER PRIMARY KEY, nom TEXT NOT NULL,
  tur TEXT NOT NULL DEFAULT 'mahsulot' CHECK (tur IN ('mahsulot','xizmat')), birlik TEXT NOT NULL DEFAULT 'dona',
  narx INTEGER NOT NULL DEFAULT 0, valyuta TEXT NOT NULL DEFAULT 'UZS', tannarx INTEGER, izoh TEXT,
  faol INTEGER NOT NULL DEFAULT 1, yaratilgan TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS buyurtma (id INTEGER PRIMARY KEY, mijoz_id INTEGER NOT NULL,
  bosqich TEXT NOT NULL DEFAULT 'yangi' CHECK (bosqich IN ('yangi','taklif','sotildi','bajarildi','bekor')),
  valyuta TEXT NOT NULL DEFAULT 'UZS', chegirma INTEGER NOT NULL DEFAULT 0, manzil TEXT, muddat TEXT, masul_id INTEGER,
  izoh TEXT, sotuv_id INTEGER, ish_id INTEGER, bekor_sabab TEXT, yaratgan_id INTEGER, yaratilgan TEXT NOT NULL,
  bosqich_vaqt TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS buyurtma_qator (id INTEGER PRIMARY KEY, buyurtma_id INTEGER NOT NULL, katalog_id INTEGER,
  nom TEXT NOT NULL, birlik TEXT NOT NULL DEFAULT 'dona', miqdor REAL NOT NULL DEFAULT 1, narx INTEGER NOT NULL DEFAULT 0,
  tartib INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS buyurtma_qator_b ON buyurtma_qator(buyurtma_id);
CREATE TABLE IF NOT EXISTS buyurtma_tarix (id INTEGER PRIMARY KEY, buyurtma_id INTEGER NOT NULL, bosqich TEXT,
  matn TEXT NOT NULL, kim_id INTEGER, vaqt TEXT NOT NULL);

-- R9: web chat tarixi (odam yozgani va miya javobi; miya o'zi yuborgani — xabarnoma'dan)
CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY, odam_id INTEGER NOT NULL,
  kim TEXT NOT NULL CHECK (kim IN ('odam','miya')), matn TEXT NOT NULL, malumot TEXT, xabar_id INTEGER, vaqt TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chat_odam ON chat(odam_id, id);
"""

# eski bazaga yangi ustunlar (CREATE TABLE IF NOT EXISTS ularni qo'shmaydi)
USTUNLAR = {"odam": [("kirgan_sana", "TEXT"), ("yaqin_telefon", "TEXT"), ("izoh", "TEXT")],
            "mijoz": [("manzil", "TEXT"), ("masul_id", "INTEGER"), ("telefon2", "TEXT"), ("arxiv", "INTEGER NOT NULL DEFAULT 0")],
            "vada": [("harakat_id", "INTEGER")]}

_yol: str | None = None
_mahalliy = threading.local()
_qulf = threading.RLock()


def boshlash(yol: str) -> None:
    """Baza yo'lini o'rnatadi va sxemani yaratadi."""
    global _yol
    _yol = yol
    _mahalliy.__dict__.clear()
    os.makedirs(os.path.dirname(os.path.abspath(yol)), exist_ok=True)
    c = ula()
    c.executescript(SXEMA)
    for jadval, ustunlar in USTUNLAR.items():
        bor = {r[1] for r in c.execute(f"PRAGMA table_info({jadval})")}
        for nom, tur in ustunlar:
            if nom not in bor:
                c.execute(f"ALTER TABLE {jadval} ADD COLUMN {nom} {tur}")


def yol() -> str:
    if not _yol:
        raise RuntimeError("baza.boshlash() chaqirilmagan")
    return _yol


def ula() -> sqlite3.Connection:
    c = getattr(_mahalliy, "c", None)
    if c is not None and getattr(_mahalliy, "yol", None) == _yol:
        return c
    c = sqlite3.connect(yol(), isolation_level=None, timeout=15, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=15000")
    c.execute("PRAGMA foreign_keys=ON")
    _mahalliy.c = c
    _mahalliy.yol = _yol
    _mahalliy.chuqurlik = 0
    return c


@contextmanager
def tranz():
    """Atomar yozuv. Ichma-ich chaqirilsa tashqi tranzaksiya ishlatiladi."""
    c = ula()
    with _qulf:
        if _mahalliy.chuqurlik:
            _mahalliy.chuqurlik += 1
            try:
                yield c
            finally:
                _mahalliy.chuqurlik -= 1
            return
        c.execute("BEGIN IMMEDIATE")
        _mahalliy.chuqurlik = 1
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise
        finally:
            _mahalliy.chuqurlik = 0


def bir(sql: str, *p) -> dict | None:
    r = ula().execute(sql, p).fetchone()
    return dict(r) if r else None


def hammasi(sql: str, *p) -> list[dict]:
    return [dict(r) for r in ula().execute(sql, p).fetchall()]


def qiymat(sql: str, *p):
    r = ula().execute(sql, p).fetchone()
    return r[0] if r else None


def bajar(sql: str, *p) -> int:
    with tranz() as c:
        cur = c.execute(sql, p)
        return cur.lastrowid


# ---------- sozlamalar ----------

def sozlama(kalit: str, standart=None):
    r = bir("SELECT qiymat FROM sozlama WHERE kalit=?", kalit)
    if r is None or r["qiymat"] is None:
        return standart
    try:
        return json.loads(r["qiymat"])
    except ValueError:
        return r["qiymat"]


def sozlama_qoy(kalit: str, q, kim_id: int | None = None) -> None:
    eski = sozlama(kalit)
    with tranz() as c:
        c.execute("INSERT INTO sozlama(kalit,qiymat) VALUES(?,?) ON CONFLICT(kalit) DO UPDATE SET qiymat=excluded.qiymat",
                  (kalit, json.dumps(q, ensure_ascii=False)))
        if not kalit.startswith("maxfiy_"):
            jurnal(kim_id, "sozlama", kalit, eski, q)
        else:
            jurnal(kim_id, "sozlama", kalit, "***", "***")


# ---------- jurnal ----------

def jurnal(kim_id: int | None, amal: str, obyekt: str | None = None, oldin=None, keyin=None) -> None:
    def j(x):
        if x is None or isinstance(x, str):
            return x
        return json.dumps(x, ensure_ascii=False, default=str)
    with tranz() as c:
        c.execute("INSERT INTO jurnal(vaqt,kim_id,amal,obyekt,oldin,keyin) VALUES(?,?,?,?,?,?)",
                  (vaqt.iso(), kim_id, amal, obyekt, j(oldin), j(keyin)))
