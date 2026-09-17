"""Tests de layout del cuadernillo (CUADERNILLO_SPEC.md §10).

Corren sobre los 3 fixtures de §2. Requieren WeasyPrint + Pango.
"""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server_api.rendering import render as R
from server_api.rendering import validators as V

FIXTURES = {
    "a": os.path.join(ROOT, "fixtures", "prescripcion_a.json"),
    "b": os.path.join(ROOT, "fixtures", "prescripcion_b.json"),
    "c": os.path.join(ROOT, "fixtures", "prescripcion_c.json"),
}
SVG_DIR = os.path.join(ROOT, "server_api", "rendering", "svg")

FOOTER_PROF = "Lic. Matías Pérez"
FOOTER_PAG = re.compile(r"Página \d+ de \d+")


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory):
    """Renderiza los 3 fixtures una vez. Devuelve {key: pdf_path}."""
    out = {}
    tmp = tmp_path_factory.mktemp("cuadernillos")
    for key, path in FIXTURES.items():
        data = R.load_fixture(path)
        R.validate_prescription(data)
        pdf = os.path.join(str(tmp), f"cuadernillo_{key}.pdf")
        R.render_pdf(data, SVG_DIR, pdf)
        out[key] = pdf
    return out


def _pages(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    try:
        return [p.get_text() for p in doc]
    finally:
        doc.close()


def _words(pdf_path, pageno):
    import fitz
    doc = fitz.open(pdf_path)
    try:
        return doc.load_page(pageno).get_text("words")
    finally:
        doc.close()


def _lines(words):
    """Agrupa words en líneas por banda-y (tolerancia 2pt)."""
    ws = sorted(words, key=lambda w: (round(w[1] / 2), w[0]))
    lines = []
    for w in ws:
        placed = False
        for ln in lines:
            if abs(ln["y0"] - w[1]) <= 2:
                ln["words"].append(w)
                ln["y0"] = min(ln["y0"], w[1])
                ln["y1"] = max(ln["y1"], w[3])
                ln["x0"] = min(ln["x0"], w[0])
                ln["x1"] = max(ln["x1"], w[2])
                placed = True
                break
        if not placed:
            lines.append({"y0": w[1], "y1": w[3], "x0": w[0],
                          "x1": w[2], "words": [w]})
    for ln in lines:
        ln["text"] = " ".join(w[4] for w in sorted(ln["words"],
                                                   key=lambda w: w[0]))
    return lines


# t1 — sin placeholders
def test_t1_no_placeholder(pdfs):
    for key, pdf in pdfs.items():
        for i, txt in enumerate(_pages(pdf)):
            assert "Sin especificar" not in txt, f"{key} p{i + 1}"


# t2 — sin solapes entre palabras (> 2pt en ambos ejes).
# Nivel palabra (no línea): una misma fila visual con dos tamaños de fuente
# no debe reportarse como solape; solo colisiones reales texto-sobre-texto.
def test_t2_no_overlap(pdfs):
    for key, pdf in pdfs.items():
        import fitz
        doc = fitz.open(pdf)
        n = len(doc)
        doc.close()
        for p in range(n):
            ws = sorted(_words(pdf, p), key=lambda w: (w[1], w[0]))
            for i in range(len(ws)):
                x0, y0, x1, y1, txt = ws[i][:5]
                for j in range(i + 1, len(ws)):
                    a0, b0, a1, b1, t2 = ws[j][:5]
                    if a0 >= y1 - 2:
                        break
                    yo = min(y1, b1) - max(y0, b0)
                    if yo > 2:
                        xo = min(x1, a1) - max(x0, a0)
                        assert xo <= 2, (
                            f"{key} p{p + 1} solape: {txt[:30]!r} / "
                            f"{t2[:30]!r}")


# t3 — ningún header de tarjeta queda último en la página
def test_t3_no_orphan(pdfs):
    import fitz
    patron = re.compile(r"^\d+\s+\d+\.\d+\s+\S")
    for key, pdf in pdfs.items():
        doc = fitz.open(pdf)
        try:
            for p in range(len(doc) - 1):
                page = doc.load_page(p)
                h = page.rect.height
                lines = [ln for ln in _lines(page.get_text("words"))
                         if ln["y1"] < h - 60]
                if not lines:
                    continue
                ultima = lines[-1]["text"].strip()
                assert not patron.match(ultima), (
                    f"{key} p{p + 1} header huérfano: {ultima[:50]!r}")
        finally:
            doc.close()


# t4 — footer en todas las páginas menos portada
def test_t4_footer(pdfs):
    for key, pdf in pdfs.items():
        for i, txt in enumerate(_pages(pdf)):
            if i == 0:
                continue
            assert FOOTER_PROF in txt, f"{key} p{i + 1} sin firma"
            assert FOOTER_PAG.search(txt), f"{key} p{i + 1} sin Página X de Y"


# t5 — presupuesto de páginas
def test_t5_page_budget(pdfs):
    import fitz
    doc = fitz.open(pdfs["a"])
    try:
        assert len(doc) <= 14, f"fixture_a: {len(doc)} páginas (> 14)"
    finally:
        doc.close()


# t6 — mapeo familia/primitiva
def test_t6_family_mapping():
    svg_dir = SVG_DIR
    for key, path in FIXTURES.items():
        data = R.load_fixture(path)
        assert V.validar_familias(data["ejercicios"]) == []
        for ex in data["ejercicios"]:
            ov = (ex.get("ilustracion") or "").strip()
            if ov == "tabla_registro":
                assert ex["familia"] == "habla"
                continue
            archivo, _cap = V.ilustracion_para(
                ex["familia"], "", ov)
            if archivo is None:  # higiene → sin ilustración (§6)
                assert ex["familia"] == "higiene"
                continue
            assert os.path.exists(os.path.join(svg_dir, archivo)), archivo


# t7 — lint de catálogo documentado
def test_t7_catalog_lint():
    with open(os.path.join(ROOT, "server_api", "exercise_bank.json"),
              encoding="utf-8") as f:
        bank = json.load(f)
    hallazgos = V.lint_catalog(bank)
    if hallazgos:
        with open(os.path.join(ROOT, "FIXES.md"), encoding="utf-8") as f:
            fixes = f.read()
        assert "lint de catálogo" in fixes.lower(), (
            "hallazgos de lint sin documentar en FIXES.md:\n"
            + "\n".join(hallazgos[:20]))


# t8 — bboxes de SVG
def test_t8_svg_bbox():
    svg_dir = SVG_DIR
    archivos = sorted(f for f in os.listdir(svg_dir) if f.endswith(".svg"))
    assert 1 <= len(archivos) <= 13, f"{len(archivos)} SVGs (máx 13)"
    for arch in archivos:
        _, errores = V.svg_text_boxes(os.path.join(svg_dir, arch))
        assert errores == [], f"{arch}: {errores}"


# t9 — tablas íntegras (thead presente si hay cuerpo)
def test_t9_tables_intact(pdfs):
    # "Sábado" solo aparece en el cuerpo del TME (el weekly es L–V):
    # si hay cuerpo sin thead, la tabla saltó sin repetir encabezado.
    pares = [("Viernes", "07:00"), ("Mejor valor", "Sábado"),
             ("Enunciado", "Mi voz me dificulta"),
             ("Cuándo la uso", "Buenos días")]
    for key, pdf in pdfs.items():
        for i, txt in enumerate(_pages(pdf)):
            for thead, cuerpo in pares:
                if cuerpo in txt:
                    assert thead in txt, (
                        f"{key} p{i + 1}: cuerpo sin thead ({cuerpo!r})")


# t10 — smoke render (implícito en el fixture pdfs)
def test_t10_render_smoke(pdfs):
    import fitz
    for key, pdf in pdfs.items():
        assert os.path.getsize(pdf) > 5000, key
        doc = fitz.open(pdf)
        try:
            assert len(doc) >= 3, key
        finally:
            doc.close()
