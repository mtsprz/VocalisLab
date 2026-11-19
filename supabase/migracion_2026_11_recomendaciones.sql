-- VocalisLab — Migración 2026-11: recomendaciones del motor terapéutico
--
-- Cómo correrla: Supabase → SQL Editor → New query → pegar todo → Run.
-- Se puede correr más de una vez sin problema.
--
-- Cada plan que genera el motor terapéutico se guarda con su fecha, para no
-- perderlo al cambiar de sección y para ver los anteriores.

CREATE TABLE IF NOT EXISTS recomendaciones_terapeuticas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    creada_at TIMESTAMPTZ DEFAULT now(),
    recomendacion JSONB NOT NULL,
    contexto JSONB DEFAULT '{}'::jsonb,   -- qué datos se usaron y cuáles faltaban
    notas TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_recomendaciones_paciente ON recomendaciones_terapeuticas(paciente_id, creada_at DESC);

ALTER TABLE recomendaciones_terapeuticas ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
