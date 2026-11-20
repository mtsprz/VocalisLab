-- VocalisLab — Migración 2026-11: sesiones de la sala virtual
--
-- Cómo correrla: Supabase → SQL Editor → New query → pegar todo → Run.
-- Se puede correr más de una vez sin problema.
--
-- Cada medición guardada desde la sala virtual (en vivo con el paciente):
-- modo (habla, nota sostenida, canto, TMF), nota objetivo, consigna y
-- resultados. Antes se guardaba todo como "F0 conversacional" y una nota
-- cantada se mezclaba con la voz del habla.

CREATE TABLE IF NOT EXISTS sala_sesiones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    creada_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    modo TEXT NOT NULL,                      -- habla | nota | canto | tmf
    duracion_s REAL,
    objetivo JSONB,                          -- {"hz": 220, "nota": "La3", "tolerancia_cents": 50}
    consigna TEXT DEFAULT '',
    resultados JSONB NOT NULL DEFAULT '{}'::jsonb,  -- mediana, p5, p95, min, max, sd_st, en_objetivo_pct, tmf_s, n
    contorno JSONB,                          -- F0 resumida (hasta 600 valores)
    notas TEXT DEFAULT '',
    companion_session_id UUID                -- solo modo habla: la F0 que suma a la evolución conversacional
);
CREATE INDEX IF NOT EXISTS sala_sesiones_paciente_idx ON sala_sesiones (paciente_id, creada_at DESC);

-- Solo el servidor (clave de servicio) accede a la tabla.
ALTER TABLE sala_sesiones ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
