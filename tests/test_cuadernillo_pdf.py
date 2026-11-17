"""Motor real del cuadernillo (server_api/cuadernillo_pdf.py, ReportLab).

Es el que usa /api/cuadernillo/generar. Cubre las fallas encontradas:
- Una tarjeta más alta que una página hacía fallar el PDF (LayoutError).
- Galerías de varias imágenes por ejercicio.
- Reemplazos de jerga que pegaban letras ("de las cuerdass") o perdían la
  mayúscula del paso ("pausa sin respirar suave").
- Pie "Página X de Y" (sin pie en la portada).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))
for _k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_ANON_KEY"):
    os.environ.pop(_k, None)

pytest.importorskip("reportlab")
pymupdf = pytest.importorskip("pymupdf")

from cuadernillo_pdf import (  # noqa: E402
    _sanear, _simplificar, _sin_numeracion, generar_cuadernillo_pdf,
)

BANK_PATH = os.path.join(os.path.dirname(__file__), "..", "server_api", "exercise_bank.json")


def _paso(texto):
    return _sanear(_simplificar(_sin_numeracion(texto)))


def _generar(ejercicios, **kw):
    path = generar_cuadernillo_pdf(
        paciente_nombre="Paciente Prueba", titulo="Cuadernillo", sesiones=8,
        ejercicios=ejercicios, contrato={"frecuencia": "1 vez por semana"},
        profesional={"profesional_nombre": "Lic. Prueba"}, **kw)
    try:
        doc = pymupdf.open(path)
        textos = [p.get_text() for p in doc]
        doc.close()
        return textos
    finally:
        os.unlink(path)


@pytest.fixture
def imagenes(tmp_path):
    from PIL import Image
    paths = []
    for i, size in enumerate([(800, 600), (600, 900), (1000, 400), (700, 700), (500, 800)]):
        p = tmp_path / f"img{i}.png"
        Image.effect_noise(size, 60).convert("RGB").save(p)  # > 2 KB: imagen válida
        paths.append({"path": str(p), "epigrafe": f"Vista {i + 1}"})
    return paths


def test_jerga_palabra_completa_y_plural():
    assert _paso("sin golpes glóticos") == "Sin golpes de las cuerdas"
    assert "cuerdass" not in _paso("ataque glótico y cierres glóticos")
    assert _paso("Fricativa sorda") == "Sonido con aire (como la s) sorda"
    # "ATM" es sigla: no se reemplaza dentro de otras palabras.
    assert _paso("tratamiento en atmósfera seca") == "Tratamiento en atmósfera seca"
    assert _paso("Masaje de ATM y cuello").endswith("de mandíbula y cuello")


def test_paso_conserva_mayuscula_inicial():
    assert _paso("3. Apnea suave — 2-3 s") == "Pausa sin respirar suave — 2-3 s"
    assert _paso("2) inspirar por la nariz") == "Inspirar por la nariz"


def test_tarjeta_mas_alta_que_una_pagina_no_falla(imagenes):
    largo = ("Paso detallado con indicaciones de postura, respiración y emisión "
             "que ocupa varias líneas en la tarjeta. ") * 3
    ex = {"id": "tubo_agua", "name": "Tubo en agua", "description": "Descripción. " * 10,
          "steps": [largo] * 9, "duration_min": 5, "seccion_id": "sovte",
          "_ai_pre": imagenes[:1]}
    textos = _generar([ex])
    todo = "\n".join(textos)
    assert "Tubo en agua" in todo
    assert todo.count("Paso detallado") >= 9 * 3  # no se perdió ningún paso


@pytest.mark.parametrize("n_img", [1, 2, 3, 5])
def test_galerias_de_imagenes(imagenes, n_img):
    ex = {"id": "calentamiento", "name": "Rutina de calentamiento",
          "steps": [f"Paso {i}" for i in range(1, 10)], "duration_min": 10,
          "seccion_id": "higiene", "_ai_pre": imagenes[:n_img]}
    todo = "\n".join(_generar([ex]))
    for i in range(1, n_img + 1):
        assert f"Vista {i}" in todo


def test_banco_completo_y_pie_con_total():
    with open(BANK_PATH, encoding="utf-8") as f:
        bank = json.load(f)
    ejercicios = [dict(e, seccion_id=s["id"]) for s in bank["sections"] for e in s["exercises"]]
    textos = _generar(ejercicios, notas="Tomar agua.\nNo carraspear.",
                      advertencias=["No practicar con dolor."])
    total = len(textos)
    assert "Página 1 de" not in textos[0]  # la portada no lleva pie
    for n in range(2, total + 1):
        assert f"Página {n} de {total}" in textos[n - 1]
    todo = "\n".join(textos)
    assert "pendiente de carga" not in todo  # sin texto de relleno para el paciente
    assert "STOP" in todo and "No carraspear." in todo
