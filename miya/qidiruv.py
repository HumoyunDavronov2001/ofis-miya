"""O'zbekcha so'z qidiruvi (X6, O5): kirill/lotin bir xil, qo'shimchali so'z ildizi bo'yicha («Karimovga» → «karimov»)."""
from . import matn

# savol so'zlari — qidiruvda ma'no bermaydi
TOXTA = {"bilan", "kanday", "kanaka", "edi", "edik", "edingiz", "nima", "nimani", "kachon", "kim", "kimga", "va", "ham",
         "uchun", "haqida", "boyicha", "gapirgan", "gaplashgan", "kelishgan", "kelishdik", "aytgan", "aytdi", "degan",
         "dedi", "kaysi", "bu", "shu", "u", "men", "biz", "siz", "ular", "mi", "chi", "esa", "endi", "bor", "yok",
         "kerak", "kilamiz", "kilish", "kilinadi", "kanday kilib", "buni", "uni", "shuni", "ekan", "edimi", "deb",
         "topib", "top", "ber", "korsat", "eslat", "esla", "eshit", "eshittir", "ovoz", "ovozni", "habar", "habarni"}
QOSHIMCHA = sorted({"larning", "laridan", "larini", "lardan", "larga", "larni", "ning", "niki", "dagi", "dan", "tan",
                    "ga", "ka", "ni", "da", "ta", "lar", "ini", "imiz", "ingiz", "si", "ini", "dek", "cha", "mi"},
                   key=len, reverse=True)


def ildiz(soz: str) -> str:
    s = matn.norm(soz)
    for q in QOSHIMCHA:
        if s.endswith(q) and len(s) - len(q) >= 4:
            return s[: -len(q)]
    return s


def ildizlar(sorov: str) -> list[str]:
    natija = []
    for t in matn.norm(sorov).split():
        if t in TOXTA or len(t) < 3:
            continue
        i = ildiz(t)
        if i not in natija:
            natija.append(i)
    return natija


def tokenlar(matn_: str) -> list[str]:
    return matn.norm(matn_).split()


def mos(token: str, ild: str) -> bool:
    return token.startswith(ild) if len(ild) >= 4 else token == ild


def ball(toklar: list[str], ildlar: list[str]) -> int:
    """Nechta ildiz matnda uchradi."""
    return sum(1 for i in ildlar if any(mos(t, i) for t in toklar))


def eng_yaxshi_joy(toklar: list[str], ildlar: list[str], oyna: int = 8) -> int:
    """Ildizlar eng zich uchragan joyning boshi (so'z tartibi) — ovozda shu soniyadan eshittiriladi."""
    eng, joy = -1, 0
    for i in range(len(toklar)):
        b = ball(toklar[i:i + oyna], ildlar)
        if b > eng:
            eng, joy = b, i
        if b == len(ildlar):
            break
    # birinchi mos so'zgacha suriladi
    for k in range(joy, min(joy + oyna, len(toklar))):
        if any(mos(toklar[k], i) for i in ildlar):
            return k
    return joy


def parcha(matn_: str, ildlar: list[str], soz_soni: int = 18) -> str:
    sozlar = matn_.split()
    toklar = [matn.norm(s) for s in sozlar]
    joy = eng_yaxshi_joy(toklar, ildlar)
    bosh = max(0, joy - 4)
    qism = " ".join(sozlar[bosh:bosh + soz_soni])
    return ("… " if bosh else "") + qism + (" …" if bosh + soz_soni < len(sozlar) else "")
