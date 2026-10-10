"""Birinchi sozlash kodi (serverda): python3 -m miya.sozlash_kodi — kodni chiqaradi (yo'q bo'lsa yaratadi)."""
import os
import secrets

from . import baza, odamlar

baza.boshlash(os.environ.get("MIYA_BAZA", "malumot/miya.db"))
if odamlar.boshliq():
    print("Dastur allaqachon sozlangan — kod kerak emas.")
else:
    kod = baza.sozlama("sozlash_kodi")
    if not kod:
        kod = "".join(secrets.choice("23456789ABCDEFGHJKMNPQRSTUVWXYZ") for _ in range(8))
        baza.sozlama_qoy("sozlash_kodi", kod)
    print(kod)
