"""S10: 50 ta nazorat savoli — asbob rejimi har sinovda ishlaydi (bepul)."""
import copy
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nazorat  # noqa: E402
from miya import kurs, vaqt  # noqa: E402


@pytest.fixture()
def namuna(tmp_path):
    asl = kurs._olib_kel
    yield nazorat.urug(str(tmp_path / "nazorat.db"))
    kurs._olib_kel = asl
    vaqt._siljish = timedelta(0)


def test_50_savol_asbob_rejimida(namuna):
    assert nazorat.asbob_tekshir(namuna) == []


def test_nazorat_xatoni_ushlaydi(namuna, monkeypatch):
    buzilgan = copy.deepcopy(nazorat.SAVOLLAR)
    buzilgan[0]["javob"] = [9_600_000]  # noto'g'ri kutilgan javob
    buzilgan[45]["javob"], buzilgan[45]["yoq"] = [], [9_650_000]  # kassirga asosiy kassa ko'rinadi — «yoq» buziladi
    monkeypatch.setattr(nazorat, "SAVOLLAR", buzilgan)
    assert [n for n, _ in nazorat.asbob_tekshir(namuna)] == [1, 46]
