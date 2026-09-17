# FIXES.md — Cuadernillo VocalisLab (CUADERNILLO_SPEC.md §11.4)

Registro de hallazgos por ronda de iteración. Formato: fecha, fixture,
página, problema, fix. Un fix que rompe un test anterior = regresión.

## 2026-09-16 — Ronda 0: estructura inicial (§1–§2)
- Estructura creada: `server_api/rendering/` (render.py, cuadernillo.html,
  cuadernillo.css, svg/ ×13, validators.py), `tests/`, `fixtures/` ×3.
- Motor único WeasyPrint. ReportLab congelado (no se toca).

## Lint de catálogo (t7 — §8.6)
- El lint `validators.lint_catalog` corre sobre `exercise_bank.json` y
  REPORTA sin reescribir (§8.6, §2.3).
- Hallazgo conocido y aceptado: las consignas del banco están en
  infinitivo/imperativo ("Ubicar…", "Hacer…", "Colocar…", "Repetir…",
  "Inspirar…"). La conversión a primera persona la aprueba el profesional;
  los fixtures de prueba ya usan primera persona.
- Otros patrones vigilados: espacios dobles, fragmentos pegados tipo
  ")x", paréntesis sin cerrar, palabras repetidas.
