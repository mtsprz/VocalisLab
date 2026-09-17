# FIXES.md — Cuadernillo VocalisLab (CUADERNILLO_SPEC.md §11.4)

Registro de hallazgos por ronda de iteración. Formato: fecha, fixture,
página, problema, fix. Un fix que rompe un test anterior = regresión.

## 2026-09-16 — Ronda 0: estructura inicial (§1–§2)
- Estructura creada: `server_api/rendering/` (render.py, cuadernillo.html,
  cuadernillo.css, svg/ ×13, validators.py), `tests/`, `fixtures/` ×3.
- Motor único WeasyPrint. ReportLab congelado (no se toca).

## 2026-09-17 — Ronda 1: revisión visual fixture_a (11 págs, §9)
- p1 Portada: B1 ✓ (4 campos reales), sin footer ✓.
- p2 Contrato+leyenda+tarjeta 1: C1 ✓ (2 firmas), D1 ✓ (4 líneas),
  E1–E6 ✓ (número+código únicos, dosis, para_que, checkbox CSS, 1 chip
  de nivel, ilustración de familia + caption).
- p3–p7 tarjetas 2–12: E1–E6 ✓ en todas; E7 ✓ (STOP solo en 7.3
  "Stop si siento mareo").
- p8 Horario: thead presente, 16 filas 07–22 ✓ F1/F2.
- p9 TME Lun–Dom + nota de referencia ✓.
- p10 VHI-10: chip "33 pts (2026-09-16)" + 10 ítems + tabla de puntajes +
  nota 4–6 semanas ✓ F3; oraciones prellenadas ✓ F4.
- p11 Biblio 2 columnas + cierre G1 ✓.
- Global: A1 ✓ (footer + "Página X de 11" en p2–p11), A2 ✓ (sin solapes),
  A3 ✓ (tarjetas/tablas íntegras), A5 ✓ (sin placeholders), G2 ✓ (11 ≤ 14).
- A4 grises: paleta usa forma + etiquetas además de color (diseño apto).
- Sin violaciones → sin diff en esta ronda.

## Nota de entorno local (render)
- Windows + MSYS2 (Pango 1.58.2 / HarfBuzz 14.4.0, snapshot 2026):
  Access Violation en `hb_face_reference` al dibujar texto (todas las
  fuentes, incluso Arial). ldd limpio: es deriva ABI upstream, no dirt local.
- Consecuencia original: t1–t5/t9/t10 (requieren PDF) NO corren en esta PC.
- **FIX APLICADO (2026-09-17):** GTK3 portable 2022 (`C:\Users\Administrador\gtk3-portable\$_63_\`) + FONTCONFIG_PATH
  apuntando a `C:\Users\Administrador\.fonts-vl\` con `fonts.conf` que escanea
  `%LOCALAPPDATA%\Microsoft\Windows\Fonts` (DejaVuSans instalado a nivel usuario).
  Resultado: t1–t10 verdes, PDF + PNG renderizan correctamente en Windows.
- Variables de entorno necesarias para render local:
  `$env:PATH = 'C:\Users\Administrador\gtk3-portable\$_63_;' + $env:PATH`
  `$env:GSETTINGS_BACKEND = 'memory'`
  `$env:FONTCONFIG_PATH = 'C:\Users\Administrador\.fonts-vl'`
- Docker/CI no necesita estos fixes (Pango Debian estable).

## Lint de catálogo (t7 — §8.6)
- El lint `validators.lint_catalog` corre sobre `exercise_bank.json` y
  REPORTA sin reescribir (§8.6, §2.3).
- Hallazgo conocido y aceptado: las consignas del banco están en
  infinitivo/imperativo ("Ubicar…", "Hacer…", "Colocar…", "Repetir…",
  "Inspirar…"). La conversión a primera persona la aprueba el profesional;
  los fixtures de prueba ya usan primera persona.
- Otros patrones vigilados: espacios dobles, fragmentos pegados tipo
  ")x", paréntesis sin cerrar, palabras repetidas.
