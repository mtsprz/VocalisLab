"""Guardia clínica del cuadernillo (auditoría C4 + regla de exclusión).

- Todo preset del banco debe traer `advertencia` STOP imprimible.
- verificar_contraindicaciones debe excluir ejercicios con tag contra el
  diagnóstico (ej: empuje_glotico no sale con lesión exofítica).
- precauciones_por_bank_id debe cubrir los ejercicios del banco que tienen
  contraindicaciones (si una ficha existe, el STOP llega al PDF).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

BANK_PATH = os.path.join(os.path.dirname(__file__), "..", "server_api", "exercise_bank.json")
FICHAS_PATH = os.path.join(os.path.dirname(__file__), "..", "server_api", "fichas_clinicas.json")

# Presets de mantenimiento puro pueden llevar advertencia leve, pero igual
# deben traer el campo (aunque sea la pauta general).
CATEGORIAS_EXIGIDAS = {"organicas", "minimas_estructurales", "congenitas", "funcionales", "mantenimiento"}


def _bank():
    with open(BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_presets_con_advertencia():
    bank = _bank()
    sin = [p.get("id") for p in bank.get("presets", [])
           if p.get("categoria") in CATEGORIAS_EXIGIDAS and not (p.get("advertencia") or "").strip()]
    assert not sin, f"Presets sin advertencia STOP imprimible: {sin}"


def test_guardia_excluye_empuje_en_exofitica():
    from recomendar_motor import verificar_contraindicaciones
    seguros, excluidos = verificar_contraindicaciones(
        ["empuje_glotico", "tubo_agua", "humming_m"],
        "Nódulo cordal bilateral, lesión exofítica en tercio medio",
    )
    ids_fuera = {x["id"] for x in excluidos}
    assert "empuje_glotico" in ids_fuera, "empuje_glotico debió excluirse con nódulos"
    assert "tubo_agua" in [e for e in seguros], "tubo_agua es seguro y no debe excluirse"


def test_guardia_no_excluye_sin_diagnostico():
    from recomendar_motor import verificar_contraindicaciones
    seguros, excluidos = verificar_contraindicaciones(["empuje_glotico", "tubo_agua"], "")
    assert excluidos == [], "sin diagnóstico no se excluye nada"
    assert set(seguros) == {"empuje_glotico", "tubo_agua"}


def test_contra_tags_con_mapa():
    """Todo tag de contraindicación usado en el banco debe existir en CONTRA_MAP."""
    from recomendar_motor import CONTRA_MAP
    bank = _bank()
    tags = set()
    for s in bank.get("sections", []):
        for e in s.get("exercises", []):
            for t in (e.get("contraindications") or []):
                tags.add(t)
    sin_mapa = sorted(t for t in tags if t not in CONTRA_MAP)
    assert not sin_mapa, f"Tags sin cobertura en CONTRA_MAP (guardia ciega): {sin_mapa}"


def test_bank_schema_completo():
    """Todo ejercicio del banco (incluidos los de la edición ampliada) trae
    los campos que el PDF y el frontend necesitan."""
    bank = _bank()
    ids = []
    for s in bank.get("sections", []):
        assert s.get("id"), "sección sin id"
        for e in s.get("exercises", []):
            assert e.get("id"), f"ejercicio sin id en sección {s.get('id')}"
            ids.append(e["id"])
            assert (e.get("name") or "").strip(), f"{e['id']}: sin nombre"
            assert len(e.get("steps", []) or []) >= 1, f"{e['id']}: sin pasos"
            assert isinstance(e.get("duration_min"), int), f"{e['id']}: sin duration_min"
            assert e.get("difficulty") in ("basico", "intermedio", "avanzado"), \
                f"{e['id']}: difficulty inválida"
    assert len(ids) == len(set(ids)), "IDs de ejercicio duplicados"


def test_precauciones_cubren_ejercicios_con_contra():
    """Si un ejercicio del banco declara contraindicaciones, debe existir
    texto de precaución imprimible (ficha con bank_id) o el STOP no sale."""
    from recomendar_motor import precauciones_por_bank_id
    bank = _bank()
    prec = precauciones_por_bank_id()
    faltan = []
    for s in bank.get("sections", []):
        for e in s.get("exercises", []):
            if (e.get("contraindications") or []) and not prec.get(str(e.get("id", "")).lower()):
                faltan.append(e.get("id"))
    assert not faltan, f"Ejercicios con contraindicaciones pero sin texto STOP: {faltan}"
