-- VocalisLab — Migración 2026-11: autoevaluación del paciente por enlace
--
-- Cómo correrla: Supabase → SQL Editor → New query → pegar todo → Run.
-- Se puede correr más de una vez sin problema.
--
-- El paciente completa desde un enlace (sin entrar a la app) su
-- autopercepción, el VHI-10 y el cuestionario de riesgo vocal. Acá quedan
-- sus respuestas y puntajes hasta que el profesional los carga en la
-- evaluación (Riesgo & Escalas).

CREATE TABLE IF NOT EXISTS autoevaluaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT UNIQUE NOT NULL,
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    estado TEXT NOT NULL DEFAULT 'pendiente',       -- pendiente | completada
    instrumentos JSONB DEFAULT '["autopercepcion","vhi10","riesgo"]'::jsonb,
    creada_at TIMESTAMPTZ DEFAULT now(),
    vence_at TIMESTAMPTZ,
    completada_at TIMESTAMPTZ,
    respuestas JSONB DEFAULT '{}'::jsonb,           -- {"VHI10": {...}, "RiesgoVocal": {...}}
    vhi10_score INT,
    riesgo_vocal_score INT,
    autopercepcion INT,
    comentario TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_autoevaluaciones_paciente ON autoevaluaciones(paciente_id, creada_at DESC);

-- Solo el servidor (clave de servicio) accede a la tabla.
ALTER TABLE autoevaluaciones ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
