-- ═══════════════════════════════════════════════════════════════════════
-- Valores normativos de F0 (tono medio hablado) — VocalisLab / Companion
-- Fuentes: Wilson (1973) niñez/adolescencia; Colton, Casper & Leonard (2011)
-- adultos por década; rangos generales adultos y presbifonía según criterio
-- clínico provisto por el profesional (2026-10-11).
--
-- Regla de selección (igual en web, backend y app):
--   override del paciente > fila cuya franja de edad contiene la edad
--   (≤ 18 años: 'ninex', sin distinción de sexo; ≥ 19: por sexo; si hay
--   varias, la franja más angosta) > sin edad: rango general del sexo >
--   sin sexo ni edad: sin comparación.
-- f0_min_hz / f0_max_hz = rango de referencia; f0_promedio_*_hz = promedio
-- esperado (un valor o un intervalo).
-- Idempotente: se puede correr más de una vez.
-- ═══════════════════════════════════════════════════════════════════════

ALTER TABLE reference_ranges ADD COLUMN IF NOT EXISTS f0_promedio_min_hz FLOAT;
ALTER TABLE reference_ranges ADD COLUMN IF NOT EXISTS f0_promedio_max_hz FLOAT;

-- Semillas genéricas anteriores (reemplazadas por esta tabla).
DELETE FROM reference_ranges WHERE fuente LIKE 'Orientativo editable%';

INSERT INTO reference_ranges
  (sexo_referencia, edad_min, edad_max, f0_min_hz, f0_max_hz, f0_promedio_min_hz, f0_promedio_max_hz, fuente)
VALUES
  -- Niñez y adolescencia (Wilson, 1973) — sin distinción de sexo
  ('ninex',  1,  2, 370, 525, 445, 445, 'Wilson (1973)'),
  ('ninex',  3,  3, 340, 460, 400, 400, 'Wilson (1973)'),
  ('ninex',  4,  4, 320, 425, 375, 375, 'Wilson (1973)'),
  ('ninex',  5,  5, 300, 390, 350, 350, 'Wilson (1973)'),
  ('ninex',  6,  6, 280, 365, 325, 325, 'Wilson (1973)'),
  ('ninex',  7,  8, 260, 330, 295, 295, 'Wilson (1973)'),
  ('ninex',  9,  9, 220, 300, 260, 260, 'Wilson (1973)'),
  ('ninex', 10, 11, 185, 275, 225, 235, 'Wilson (1973)'),
  ('ninex', 12, 13, 155, 245, 195, 210, 'Wilson (1973)'),
  ('ninex', 14, 15, 130, 220, 165, 190, 'Wilson (1973)'),
  ('ninex', 16, 18, 100, 180, 125, 150, 'Wilson (1973)'),

  -- Adultos: rango general (se usa si no hay fecha de nacimiento)
  ('masculino', 19, 120, 100, 165, 132, 138.8, 'Rango general adulto'),
  ('femenino',  19, 120, 190, 262, 209.3, 224, 'Rango general adulto'),

  -- Adultos por década (Colton, Casper & Leonard, 2011): promedio por
  -- década dentro del rango general adulto.
  ('masculino', 19, 29, 100, 165, 118, 120, 'Colton, Casper & Leonard (2011)'),
  ('masculino', 30, 39, 100, 165, 112, 112, 'Colton, Casper & Leonard (2011)'),
  ('masculino', 40, 49, 100, 165, 100, 107, 'Colton, Casper & Leonard (2011)'),
  ('masculino', 50, 59, 100, 165, 118, 118, 'Colton, Casper & Leonard (2011)'),
  ('masculino', 60, 69, 100, 165, 112, 127, 'Colton, Casper & Leonard (2011)'),
  -- Presbifonía masculina: ascenso de F0 (≈130–146 Hz)
  ('masculino', 70, 120, 100, 165, 132, 146, 'Colton, Casper & Leonard (2011); presbifonía'),

  ('femenino', 19, 29, 190, 262, 192, 224, 'Colton, Casper & Leonard (2011)'),
  ('femenino', 30, 39, 190, 262, 196, 196, 'Colton, Casper & Leonard (2011)'),
  ('femenino', 40, 49, 190, 262, 189, 195, 'Colton, Casper & Leonard (2011)'),
  ('femenino', 50, 59, 190, 262, 189, 195, 'Colton, Casper & Leonard (2011)'),
  -- Presbifonía femenina (postmenopausia): descenso de F0 (≈175–190 Hz);
  -- el límite inferior baja a 175 para no marcar como patológico un
  -- descenso esperable.
  ('femenino', 60, 69, 175, 262, 175, 200, 'Colton, Casper & Leonard (2011); presbifonía'),
  ('femenino', 70, 120, 175, 262, 200, 202, 'Colton, Casper & Leonard (2011); presbifonía')
ON CONFLICT (sexo_referencia, edad_min, edad_max) DO UPDATE SET
  f0_min_hz = EXCLUDED.f0_min_hz,
  f0_max_hz = EXCLUDED.f0_max_hz,
  f0_promedio_min_hz = EXCLUDED.f0_promedio_min_hz,
  f0_promedio_max_hz = EXCLUDED.f0_promedio_max_hz,
  fuente = EXCLUDED.fuente;
