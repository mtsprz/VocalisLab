"""Fechas del consultorio: todo en hora de Argentina (server_api/fechas.py)."""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import fechas as F  # noqa: E402

VIERNES = date(2026, 11, 20)


@pytest.mark.parametrize("texto,esperado", [
    ("hoy", "2026-11-20"), ("mañana", "2026-11-21"), ("pasado mañana", "2026-11-22"),
    ("jueves", "2026-11-26"), ("el jueves", "2026-11-26"), ("viernes", "2026-11-27"),
    ("este viernes", "2026-11-20"), ("el próximo lunes", "2026-11-23"), ("martes que viene", "2026-11-24"),
    ("26/11", "2026-11-26"), ("26/11/2026", "2026-11-26"), ("3/1", "2027-01-03"),
    ("26 de noviembre", "2026-11-26"), ("el 5", "2026-12-05"), ("en 3 días", "2026-11-23"),
    ("jueves 26/11", "2026-11-26"), ("Miércoles", "2026-11-25"), ("2026-12-01", "2026-12-01"),
])
def test_resolver_fecha(texto, esperado):
    assert F.resolver_fecha(texto, VIERNES).isoformat() == esperado


@pytest.mark.parametrize("texto", ["miércoles 26/11", "31/11", "cualquier día", ""])
def test_resolver_fecha_rechaza(texto):
    with pytest.raises(ValueError):
        F.resolver_fecha(texto, VIERNES)


@pytest.mark.parametrize("texto,esperado", [
    ("10", "10:00"), ("10:30", "10:30"), ("10.30", "10:30"), ("10hs", "10:00"), ("10 y media", "10:30"),
    ("9 y cuarto", "09:15"), ("5 de la tarde", "17:00"), ("17h30", "17:30"), ("a las 3", "15:00"),
    ("8 de la noche", "20:00"), ("8", "08:00"),
])
def test_resolver_hora(texto, esperado):
    assert F.resolver_hora(texto) == esperado


def test_dia_y_texto_en_hora_argentina():
    # 01:30 UTC del 21 = 22:30 del 20 en Argentina.
    assert F.dia_ar("2026-11-21T01:30:00+00:00") == "2026-11-20"
    assert F.txt("2026-11-21T01:30:00+00:00") == "vie 20/11 22:30"
    # Una fecha sola no cambia de día ni muestra hora.
    assert F.dia_ar("2026-11-20") == "2026-11-20" and F.txt("2026-11-20") == "vie 20/11"
    assert F.dia_ar("2026-11-20T10:00:00.1234567+00:00") == "2026-11-20"
    assert F.largo("2026-11-26") == "jueves 26 de noviembre de 2026"
    assert F.iso_ar(date(2026, 11, 26), "10:00") == "2026-11-26T10:00:00-03:00"
