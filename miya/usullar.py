"""Ish usullari (X4, O5): «buni qanday qilamiz?» — javob faqat shu yerda yozilgan matndan."""
from . import baza, qidiruv, vaqt


class UsulXato(Exception):
    pass


def qosh(sarlavha: str, matn_: str, yozgan_id: int, xabar_id: int | None = None) -> int:
    sarlavha, matn_ = (sarlavha or "").strip()[:120], (matn_ or "").strip()[:4000]
    if not matn_:
        raise UsulXato("Usul matni bo'sh")
    if not sarlavha:
        sarlavha = matn_.split("\n")[0][:60]
    uid = baza.bajar("INSERT INTO usul(sarlavha,matn,yozgan_id,xabar_id,vaqt) VALUES(?,?,?,?,?)", sarlavha, matn_, yozgan_id,
                     xabar_id, vaqt.iso())
    baza.jurnal(yozgan_id, "usul_yozildi", f"usul:{uid}", None, sarlavha)
    return uid


def tahrir(uid: int, kim_id: int, sarlavha: str, matn_: str) -> None:
    eski = baza.bir("SELECT * FROM usul WHERE id=?", uid)
    if not eski:
        raise UsulXato("Usul topilmadi")
    if not (matn_ or "").strip():
        raise UsulXato("Usul matni bo'sh")
    baza.bajar("UPDATE usul SET sarlavha=?, matn=?, yangilangan=? WHERE id=?", (sarlavha or eski["sarlavha"]).strip()[:120],
               matn_.strip()[:4000], vaqt.iso(), uid)
    baza.jurnal(kim_id, "usul_tahrir", f"usul:{uid}", eski["matn"][:300], matn_[:300])


def ochir(uid: int, kim_id: int) -> None:
    baza.bajar("UPDATE usul SET faol=0 WHERE id=?", uid)
    baza.jurnal(kim_id, "usul_ochirildi", f"usul:{uid}")


def royxat() -> list[dict]:
    return baza.hammasi("SELECT u.*, o.ism yozgan FROM usul u LEFT JOIN odam o ON o.id=u.yozgan_id WHERE u.faol=1 "
                        "ORDER BY u.sarlavha")


def qidir(savol: str, limit: int = 3) -> list[dict]:
    ildlar = qidiruv.ildizlar(savol)
    if not ildlar:
        return []
    natija = []
    for u in royxat():
        sarl = qidiruv.ball(qidiruv.tokenlar(u["sarlavha"]), ildlar)
        b = qidiruv.ball(qidiruv.tokenlar(u["sarlavha"] + " " + u["matn"]), ildlar)
        if b:
            natija.append((b + sarl, u))  # sarlavhadagi mos so'z ikki baravar og'ir
    natija.sort(key=lambda x: -x[0])
    return [u for _, u in natija[:limit]]
