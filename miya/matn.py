"""Matn: pul ko'rinishi, sonni so'z bilan yozish, kirill → lotin, ism solishtirish (A3, K3, K7)."""
import difflib
import re

NBSP = " "

# ---------- pul ----------

def guruh(n: int) -> str:
    return f"{n:,}".replace(",", NBSP)


def minor(summa: float | int, valyuta: str) -> int:
    """So'm — butun so'm; dollar — sent."""
    if valyuta == "USD":
        return int(round(float(summa) * 100))
    return int(round(float(summa)))


def pul(m: int, valyuta: str = "UZS", birlik: bool = True) -> str:
    belgi = "−" if m < 0 else ""
    m = abs(int(m))
    if valyuta == "USD":
        dollar, sent = divmod(m, 100)
        s = guruh(dollar) + (f",{sent:02d}" if sent else "")
        return f"{belgi}{s}{NBSP}$" if birlik else belgi + s
    return f"{belgi}{guruh(m)}{NBSP}so'm" if birlik else belgi + guruh(m)


def qisqa_pul(m: int, valyuta: str = "UZS") -> str:
    """Kartochka va xulosa uchun: 2,7 mln so'm."""
    if valyuta == "USD":
        return pul(m, "USD")
    a = abs(m)
    belgi = "−" if m < 0 else ""
    if a >= 1_000_000_000:
        return f"{belgi}{a / 1e9:.1f}".replace(".", ",").replace(",0", "") + " mlrd so'm"
    if a >= 1_000_000:
        return f"{belgi}{a / 1e6:.1f}".replace(".", ",").replace(",0", "") + " mln so'm"
    return pul(m)


# ---------- son → so'z ----------

BIRLAR = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"]
ONLAR = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"]
DARAJA = [(10 ** 12, "trillion"), (10 ** 9, "milliard"), (10 ** 6, "million"), (10 ** 3, "ming")]


def _uch_xona(n: int) -> str:
    yuz, q = divmod(n, 100)
    on, bir = divmod(q, 10)
    qism = []
    if yuz:
        qism.append(f"{BIRLAR[yuz]} yuz")
    if on:
        qism.append(ONLAR[on])
    if bir:
        qism.append(BIRLAR[bir])
    return " ".join(qism)


def sonni_soz(n: int) -> str:
    n = int(n)
    if n == 0:
        return "nol"
    if n < 0:
        return "minus " + sonni_soz(-n)
    qism = []
    for qiymat, nom in DARAJA:
        k, n = divmod(n, qiymat)
        if k:
            qism.append(f"{_uch_xona(k)} {nom}")
    if n:
        qism.append(_uch_xona(n))
    matn = " ".join(qism)
    if matn.startswith("bir yuz") or matn.startswith("bir ming"):
        matn = matn[4:]
    return matn


def pul_soz(m: int, valyuta: str = "UZS") -> str:
    if valyuta == "USD":
        dollar, sent = divmod(abs(int(m)), 100)
        s = f"{sonni_soz(dollar)} dollar"
        return s + (f" {sonni_soz(sent)} sent" if sent else "")
    return f"{sonni_soz(m)} so'm"


# ---------- yozuv ----------

APOSTROF = re.compile(r"[‘’ʻʼ`´]")
KIRILL = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i",
    "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}
UNLI = set("aeiouаеёиоуэюяўы")


def lotinga(s: str) -> str:
    """O'zbek kirill → lotin (katta harf saqlanadi)."""
    natija = []
    oldingi = " "
    for ch in s:
        kichik = ch.lower()
        if kichik == "е":
            lot = "ye" if (not oldingi.isalpha() or oldingi.lower() in UNLI) else "e"
        else:
            lot = KIRILL.get(kichik)
        if lot is None:
            natija.append(ch)
        else:
            natija.append(lot.capitalize() if ch != kichik and lot else lot)
        oldingi = ch
    return APOSTROF.sub("'", "".join(natija))


KELISHIK = ["larning", "lardan", "larga", "larni", "laridan", "ning", "niki", "dan", "tan", "ga", "ka", "qa",
            "ni", "da", "ta", "lar", "ov"]
HURMAT = {"aka", "opa", "uka", "singil", "xola", "amaki", "domla", "ustoz", "janob", "xonim", "brat", "usta",
          "haydovchi", "kassir", "menejer", "mijoz", "dokon", "magazin", "firma"}


def norm(s: str) -> str:
    """Solishtirish uchun: kirill → lotin, kichik harf, apostrofsiz, x→h, q→k."""
    s = lotinga(s or "").lower()
    s = APOSTROF.sub("'", s).replace("'", "")
    s = s.replace("x", "h").replace("q", "k")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _variantlar(soz: str) -> set[str]:
    v = {soz}
    for q in KELISHIK:
        if q == "ov":
            continue
        if soz.endswith(q) and len(soz) - len(q) >= 3:
            v.add(soz[: -len(q)])
    return v


def _tokenlar(s: str) -> list[str]:
    return [t for t in norm(s).split() if t and t not in HURMAT and not any(
        t == h + q for h in HURMAT for q in ("ga", "ni", "dan", "ning", "da"))]


def ball(sorov: str, nom: str) -> float:
    """0..1 — so'rov (gapdagi ism) nomga qanchalik mos."""
    s_tok = _tokenlar(sorov)
    n_tok = _tokenlar(nom)
    if not s_tok or not n_tok:
        return 0.0
    # har aytilgan so'z uchun eng mos qism; o'rtachasi — «Anvar Karimov» ikkala Karimovga teng chiqmasin
    jami = 0.0
    for st in s_tok:
        eng = 0.0
        for v in _variantlar(st):
            for nt in n_tok:
                eng = max(eng, 1.0 if v == nt else difflib.SequenceMatcher(None, v, nt).ratio())
        jami += eng
    return jami / len(s_tok)


def mosla(sorov: str, nomlar: list[tuple[int, str]], chegara: float = 0.72) -> list[tuple[int, str, float]]:
    natija = [(i, n, ball(sorov, n)) for i, n in nomlar]
    natija = [x for x in natija if x[2] >= chegara]
    natija.sort(key=lambda x: -x[2])
    return natija


def yagona(moslar: list[tuple[int, str, float]]) -> tuple[int, str, float] | None:
    """Bitta aniq mos bo'lsa — o'sha; ikki o'xshash bo'lsa — None (so'rash kerak)."""
    if not moslar:
        return None
    birinchi = moslar[0]
    if birinchi[2] < 0.86:
        return None
    if len(moslar) > 1 and moslar[1][2] >= birinchi[2] - 0.08:
        return None
    return birinchi


SON_RE = re.compile(r"\d[\d\s  .,]*")


def sonlar(matn: str) -> list[float]:
    """Matndagi sonlar (mln/ming qo'shimchalari hisobga olinadi) — raqam tekshiruvi uchun (S6)."""
    natija = []
    for m in re.finditer(r"(\d[\d\s  ]*(?:[.,]\d+)?)\s*(mlrd|milliard|mln|million|ming)?", matn):
        xom = re.sub(r"[\s  ]", "", m.group(1)).replace(",", ".")
        if xom.count(".") > 1:
            xom = xom.replace(".", "")
        try:
            son = float(xom)
        except ValueError:
            continue
        birlik = (m.group(2) or "").lower()
        if birlik in ("mlrd", "milliard"):
            son *= 1e9
        elif birlik in ("mln", "million"):
            son *= 1e6
        elif birlik == "ming":
            son *= 1e3
        natija.append(son)
    return natija
