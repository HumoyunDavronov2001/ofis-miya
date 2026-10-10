"""Umumiy sinov sozlamasi.

R4 (08.10): xodim yozgan pul sukut bo'yicha boshliq tasdig'i bilan kiradi. Eski sinovlar ikki tomonlama tasdiq
mantig'ini tekshiradi — ular uchun R4 o'chiriladi (sozlama «xodim_tasdiq»=0 bilan bir xil). R4 ning o'zi
test_chat_r4.py da alohida sinaladi.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from miya import hisob  # noqa: E402


@pytest.fixture(autouse=True)
def _r4_eski_sinovlarda_ochiq(monkeypatch, request):
    if not request.node.get_closest_marker("r4"):
        monkeypatch.setattr(hisob, "XODIM_TASDIQ_STANDART", "0")


def pytest_configure(config):
    config.addinivalue_line("markers", "r4: xodim yozuvi boshliq tasdig'i bilan (haqiqiy sukut)")
