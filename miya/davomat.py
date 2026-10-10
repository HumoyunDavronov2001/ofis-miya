"""Davomat (M3): «Keldim / Ketdim» bitta tugma — qaysi biri ekanini dastur aniqlaydi.

Kechikish — fakt (daqiqa), jarima o'zi qo'yilmaydi. Unutilgan kunni xodim so'raydi, boshliq tasdiqlaydi.
"""
from datetime import date, datetime

from . import baza, hisob, ishlar, odamlar, vaqt


class DavomatXato(Exception):
    pass


def ish_boshlanishi() -> str:
    return str(baza.sozlama("ish_boshlanishi", "09:00"))


def ofis() -> dict | None:
    o = baza.sozlama("ofis_joylashuvi")
    if isinstance(o, dict) and o.get("lat") is not None and o.get("lon") is not None:
        return o
    return None


def kechikish(keldi_iso: str | None) -> int:
    if not keldi_iso:
        return 0
    t = datetime.fromisoformat(keldi_iso)
    soat, daqiqa = map(int, ish_boshlanishi().split(":"))
    farq = (t.hour * 60 + t.minute) - (soat * 60 + daqiqa)
    return max(0, farq)


def ofisdan_masofa(lat: float | None, lon: float | None) -> int | None:
    o = ofis()
    if lat is None or lon is None or not o:
        return None
    return int(ishlar.masofa(lat, lon, float(o["lat"]), float(o["lon"])))


def bugungi(odam_id: int, sana: str | None = None) -> dict | None:
    return baza.bir("SELECT * FROM davomat WHERE odam_id=? AND sana=?", odam_id, sana or vaqt.bugun().isoformat())


def belgila(odam_id: int, lat: float | None = None, lon: float | None = None) -> dict:
    """Kelish yoki ketishni yozadi. Qaytaradi: {"tur": keldi|ketdi|allaqachon, ...}."""
    o = odamlar.odam(odam_id)
    if not o or o["holat"] != "faol":
        raise DavomatXato("Faqat faol xodim belgilaydi")
    hozir = vaqt.iso()
    bugun = vaqt.bugun().isoformat()
    r = bugungi(odam_id, bugun)
    if not r or not r["keldi"]:
        with baza.tranz():
            if r:
                baza.bajar("UPDATE davomat SET keldi=?, keldi_lat=?, keldi_lon=?, holat='tasdiq' WHERE id=?",
                           hozir, lat, lon, r["id"])
            else:
                baza.bajar("INSERT INTO davomat(odam_id,sana,keldi,keldi_lat,keldi_lon) VALUES(?,?,?,?,?)",
                           odam_id, bugun, hozir, lat, lon)
            baza.jurnal(odam_id, "keldi", f"odam:{odam_id}", None, {"lat": lat, "lon": lon})
        return {"tur": "keldi", "vaqt": hozir, "kechikish": kechikish(hozir), "masofa": ofisdan_masofa(lat, lon),
                "joylashuvsiz": lat is None}
    if not r["ketdi"]:
        with baza.tranz():
            baza.bajar("UPDATE davomat SET ketdi=?, ketdi_lat=?, ketdi_lon=? WHERE id=?", hozir, lat, lon, r["id"])
            baza.jurnal(odam_id, "ketdi", f"odam:{odam_id}", None, {"lat": lat, "lon": lon})
        return {"tur": "ketdi", "vaqt": hozir, "keldi": r["keldi"], "masofa": ofisdan_masofa(lat, lon),
                "joylashuvsiz": lat is None}
    return {"tur": "allaqachon", "keldi": r["keldi"], "ketdi": r["ketdi"]}


def sorov(odam_id: int, sana: str, izoh: str | None = None) -> list:
    """Unutilgan kun — boshliq tasdiqlaydi (M3)."""
    d = date.fromisoformat(sana[:10])
    if d > vaqt.bugun():
        raise DavomatXato("Kelajak kuni uchun so'rab bo'lmaydi")
    if hisob.oy_yopiqmi(vaqt.oy(d)):
        raise DavomatXato("Bu oy yopilgan")
    r = bugungi(odam_id, d.isoformat())
    if r and r["keldi"] and r["holat"] == "tasdiq":
        raise DavomatXato(f"{vaqt.sana_matn(d, False)} kuni allaqachon belgilangan")
    o = odamlar.odam(odam_id)
    with baza.tranz():
        if r:
            baza.bajar("UPDATE davomat SET holat='sorov', izoh=? WHERE id=?", izoh, r["id"])
            did = r["id"]
        else:
            did = baza.bajar("INSERT INTO davomat(odam_id,sana,holat,izoh) VALUES(?,?,'sorov',?)", odam_id, d.isoformat(),
                             izoh)
        baza.jurnal(odam_id, "davomat_sorov", f"odam:{odam_id}", None, {"sana": d.isoformat(), "izoh": izoh})
        b = odamlar.boshliq()
        x = hisob.xabarnoma(b["id"], "davomat", f"{o['ism']}: {vaqt.sana_matn(d)} kuni ishda bo'lganini belgilashni "
                                                 f"unutgan." + (f"\nIzoh: {izoh}" if izoh else ""), None,
                            [["Tasdiqlash", f"dv:{did}:1"], ["Rad etish", f"dv:{did}:0"]]) if b else None
    return [x] if x else []


def sorov_hal(davomat_id: int, kim_id: int, ha: bool) -> list:
    if not odamlar.boshliqmi(odamlar.odam(kim_id)):
        raise DavomatXato("Faqat boshliq tasdiqlaydi")
    r = baza.bir("SELECT * FROM davomat WHERE id=?", davomat_id)
    if not r or r["holat"] != "sorov":
        raise DavomatXato("So'rov topilmadi yoki hal qilingan")
    with baza.tranz():
        if ha:
            keldi = r["keldi"] or f"{r['sana']}T{ish_boshlanishi()}:00+05:00"
            baza.bajar("UPDATE davomat SET holat='tasdiq', keldi=? WHERE id=?", keldi, davomat_id)
        else:
            baza.bajar("UPDATE davomat SET holat='rad' WHERE id=?", davomat_id)
        baza.jurnal(kim_id, "davomat_hal", f"odam:{r['odam_id']}", r["sana"], "tasdiq" if ha else "rad")
        x = hisob.xabarnoma(r["odam_id"], "malumot", f"{vaqt.sana_matn(r['sana'], False)} kuni — "
                                                     f"{'boshliq tasdiqladi' if ha else 'boshliq rad etdi'}.")
    return [x] if x else []


def qolda(odam_id: int, sana: str, keldi: str | None, ketdi: str | None, kim_id: int) -> None:
    """Boshliq qo'lda yozadi yoki tuzatadi (jurnal bilan)."""
    if not odamlar.boshliqmi(odamlar.odam(kim_id)):
        raise DavomatXato("Faqat boshliq")
    d = date.fromisoformat(sana[:10]).isoformat()
    if hisob.oy_yopiqmi(d[:7]):
        raise DavomatXato("Bu oy yopilgan")

    def iso(s):
        return f"{d}T{s}:00+05:00" if s else None
    eski = bugungi(odam_id, d)
    with baza.tranz():
        if eski:
            baza.bajar("UPDATE davomat SET keldi=?, ketdi=?, holat='tasdiq' WHERE id=?", iso(keldi), iso(ketdi), eski["id"])
        else:
            baza.bajar("INSERT INTO davomat(odam_id,sana,keldi,ketdi) VALUES(?,?,?,?)", odam_id, d, iso(keldi), iso(ketdi))
        baza.jurnal(kim_id, "davomat_qolda", f"odam:{odam_id}", dict(eski) if eski else None,
                    {"sana": d, "keldi": keldi, "ketdi": ketdi})


def oy_kunlari(odam_id: int, oy: str) -> int:
    return baza.qiymat("SELECT COUNT(*) FROM davomat WHERE odam_id=? AND substr(sana,1,7)=? AND holat='tasdiq' "
                       "AND keldi IS NOT NULL", odam_id, oy) or 0


def bugun_holati() -> list[dict]:
    """Panelning «Bugun odamlar» qismi: kim keldi, kim kechikdi, kimda nechta ish."""
    bugun = vaqt.bugun().isoformat()
    natija = []
    for o in odamlar.faol_odamlar():
        if o["holat"] != "faol":
            continue
        r = bugungi(o["id"], bugun)
        ochiq = baza.qiymat("SELECT COUNT(*) FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? "
                            "AND i.holat IN ('yangi','bajarildi_dalil','qayta') AND (i.muddat IS NULL OR i.muddat<=?)",
                            o["id"], bugun)
        kechikkan = baza.qiymat("SELECT COUNT(*) FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? "
                                "AND i.holat IN ('yangi','bajarildi_dalil','qayta') AND i.muddat<?", o["id"], bugun)
        bajardi = baza.qiymat("SELECT COUNT(*) FROM ish i JOIN ish_ijrochi ii ON ii.ish_id=i.id WHERE ii.odam_id=? "
                              "AND i.holat IN ('bajarildi','qabul') AND substr(i.bajarildi_vaqt,1,10)=?", o["id"], bugun)
        natija.append({"odam_id": o["id"], "ism": o["ism"], "lavozim": o["lavozim"],
                       "keldi": r["keldi"] if r and r["holat"] == "tasdiq" else None,
                       "ketdi": r["ketdi"] if r else None,
                       "kechikish": kechikish(r["keldi"]) if r and r["keldi"] else 0,
                       "masofa": ofisdan_masofa(r["keldi_lat"], r["keldi_lon"]) if r else None,
                       "joylashuvsiz": bool(r and r["keldi"] and r["keldi_lat"] is None),
                       "ochiq_ish": ochiq, "kechikkan_ish": kechikkan, "bugun_bajardi": bajardi})
    return natija
