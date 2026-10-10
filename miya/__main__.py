"""Ishga tushirish: python3 -m miya [--port 8090] [--baza malumot/miya.db]"""
import argparse
import logging
import os
import re

import uvicorn

from . import baza


class _Yashir(logging.Formatter):
    """Jurnalga (ekran, docker logs) Telegram tokeni va kalitlar tushmasin — xato matnidagi URL'da ham."""
    SIR = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|([?&]key=)[^&\s\"']+")

    def format(self, rec):
        return self.SIR.sub(lambda m: (m.group(1) or "") + "***" if m.group(1) else "***", super().format(rec))


def main():
    ap = argparse.ArgumentParser(description="MIYA — ofis xotirasi")
    ap.add_argument("--port", type=int, default=int(os.environ.get("MIYA_PORT", 8090)))
    ap.add_argument("--host", default=os.environ.get("MIYA_HOST", "127.0.0.1"))
    ildiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--baza", default=os.environ.get("MIYA_BAZA", os.path.join(ildiz, "malumot", "miya.db")))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for h in logging.getLogger().handlers:
        h.setFormatter(_Yashir("%(asctime)s %(name)s %(levelname)s %(message)s"))
    for nom in ("httpx", "httpcore"):  # har so'rov URL'i (token bilan) yozilmasin
        logging.getLogger(nom).setLevel(logging.WARNING)
    baza.boshlash(a.baza)
    from .veb import app
    # serverda faqat Caddy ulanadi (port ochilmagan) — uning X-Forwarded-Proto si ishonchli (cookie «secure» uchun)
    ishonchli = "*" if os.environ.get("MIYA_PROXY") == "1" else "127.0.0.1"
    uvicorn.run(app, host=a.host, port=a.port, proxy_headers=True, forwarded_allow_ips=ishonchli)


if __name__ == "__main__":
    main()
