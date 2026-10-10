"""Botning buyurtma qismi (CRM7): gapdan buyurtma kartochkasi — «✅ Yaratish / Bekor».

Pul emas — boshliq tasdig'i (R4) kerak emas. Qator nomi va narxini dastur katalogdan topadi (panel_taklif.buyurtma_karta);
mijoz aniq topilmasa — o'xshash ismlar va «Yangi mijoz» tugmalari. Xodim ochsa — mas'ul o'zi, boshliqqa xabar boradi.
"""
import json

from . import baza, buyurtma, matn, odamlar, panel_taklif, vaqt
from . import tgkit as b


def _matn(c: dict) -> str:
    v = c["valyuta"]
    q = [f"🧾 <b>Buyurtma</b>" + (f" — {b.e(c['mijoz']['ism'])}" if (c.get("mijoz") or {}).get("id") else "")]
    for x in c["qatorlar"]:
        narx = matn.minor(x["narx"], v)
        q.append(f"• {b.e(x['nom'])} × {x['miqdor']:g} {b.e(x['birlik'])}"
                 + (f" — {matn.pul(round(x['miqdor'] * narx), v)}" if narx else " — <i>narxi yo'q</i>")
                 + ("" if x["katalog_id"] else " <i>(katalogda yo'q)</i>"))
    q.append(f"Jami: <b>{matn.pul(c['jami'], v)}</b>")
    for k, n in (("manzil", "Manzil"), ("izoh", "Izoh")):
        if c.get(k):
            q.append(f"{n}: {b.e(c[k])}")
    if c.get("muddat"):
        q.append(f"Qachonga: {vaqt.sana_matn(c['muddat'], False)}")
    m = c.get("mijoz") or {}
    if m.get("taxmin"):
        q.append(f"«{b.e(m['aytilgan'])}» — {b.e(m['ism'])} deb oldim, to'g'rimi?")
    elif not m.get("id"):
        q.append(f"«{b.e(m['aytilgan'])}» — qaysi mijoz?" if m.get("aytilgan") else "Qaysi mijoz uchun?")
    return "\n".join(q)


def _tugmalar(kid: int, c: dict) -> list:
    m = c.get("mijoz") or {}
    if m.get("id") and not m.get("taxmin"):
        return [[["✅ Yaratish", f"kby:{kid}:ok"], ["Bekor", f"k:{kid}:bekor"]]]
    tug = []
    if m.get("id"):  # taxmin: tanlangan + boshqa variantlar
        tug.append([f"✅ {m['ism'][:40]}", f"kby:{kid}:m{m['id']}"])
    tug += [[n["ism"][:40], f"kby:{kid}:m{n['id']}"] for n in (m.get("nomzodlar") or [])[:5]]
    if m.get("yangi"):
        tug.append([f"Yangi mijoz: {m['yangi'][:40]}", f"kby:{kid}:yangi"])
    tug.append(["Bekor", f"k:{kid}:bekor"])
    return tug


class BuyurtmaQismi:
    async def buyurtma_natija(self, o: dict, chat_id: int, natija: dict, xabar_id: int | None):
        for y in (natija.get("buyurtmalar") or [])[:3]:
            c = panel_taklif.buyurtma_karta(y)
            if not c:
                continue
            kid = baza.bajar("INSERT INTO karta(odam_id,chat_id,xabar_id,malumot,yaratilgan) VALUES(?,?,?,?,?)",
                             o["id"], chat_id, xabar_id, json.dumps(c, ensure_ascii=False), vaqt.iso())
            r = await self.yoz(chat_id, _matn(c), _tugmalar(kid, c))
            if r:
                baza.bajar("UPDATE karta SET msg_id=? WHERE id=?", r.get("message_id"), kid)

    async def buyurtma_karta_tugma(self, k: dict, o: dict, tur: str, qiymat: str, chat_id: int, msg_id: int) -> str:
        kid, c = k["id"], k["d"]
        if tur == "k" and qiymat == "bekor":
            baza.bajar("UPDATE karta SET holat='bekor' WHERE id=?", kid)
            await self.tahrir(chat_id, msg_id, "Buyurtma yozilmadi.")
            return "Bekor qilindi"
        if tur != "kby":
            return ""
        if qiymat.startswith("m") and qiymat[1:].isdigit():
            m = baza.bir("SELECT id, ism FROM mijoz WHERE id=? AND tur='mijoz'", int(qiymat[1:]))
            if not m:
                return "Mijoz topilmadi"
            c["mijoz"] = {"id": m["id"], "ism": m["ism"]}
        elif qiymat == "yangi":
            ism = ((c.get("mijoz") or {}).get("yangi") or "").strip()
            if not ism:
                return "Mijoz ismi yo'q"
            mid = baza.bajar("INSERT INTO mijoz(ism,tur,yaratilgan) VALUES(?,?,?)", ism[:120], "mijoz", vaqt.iso())
            baza.jurnal(o["id"], "mijoz_yarat", f"mijoz:{mid}", None, ism)
            c["mijoz"] = {"id": mid, "ism": ism}
        elif qiymat != "ok":
            return ""
        if not (c.get("mijoz") or {}).get("id"):
            return "Avval mijozni tanlang"
        if qiymat != "ok":  # mijoz tanlandi — kartochka yangilanadi, «Yaratish» bosiladi
            baza.bajar("UPDATE karta SET malumot=? WHERE id=?", json.dumps(c, ensure_ascii=False), kid)
            await self.tahrir(chat_id, msg_id, _matn(c), _tugmalar(kid, c))
            return "Tanlandi"
        v = c["valyuta"]
        try:
            bid = buyurtma.yarat(c["mijoz"]["id"], o["id"],
                                 [{"katalog_id": x["katalog_id"], "nom": x["nom"], "birlik": x["birlik"], "miqdor": x["miqdor"],
                                   "narx": matn.minor(x["narx"], v)} for x in c["qatorlar"]],
                                 0, v, c.get("manzil") or None, c.get("muddat") or None,
                                 None if odamlar.boshliqmi(o) else o["id"], c.get("izoh") or None)
        except buyurtma.BuyurtmaXato as x:
            return str(x)[:180]
        baza.bajar("UPDATE karta SET holat='yopiq' WHERE id=?", kid)
        buyurtma.xodimdan_xabar(bid, o)
        bb = buyurtma.bir(bid)
        await self.tahrir(chat_id, msg_id, _matn(c).split("\n«")[0] + f"\n\n✅ Buyurtma #{bid} yaratildi — "
                                           f"{matn.pul(bb['jami'], bb['valyuta'])}. Panelda: Buyurtmalar.")
        return "Yaratildi"
