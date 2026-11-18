-- VocalisLab — Migración 2026-11: alumnos de canto
--
-- Cómo correrla: Supabase → SQL Editor → New query → pegar todo → Run.
-- Se puede correr más de una vez sin problema. Requiere antes la migración
-- de centros (migracion_2026_11_centros.sql).
--
-- tipo_atencion: 'voz' (paciente de fonoaudiología) o 'canto' (alumno).
-- datos_canto: edad, horario fijo y estado de pago por mes, tal como vienen
--              de la planilla "ALUMNOS DE CANTO" que comparte Fonoar.

ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS tipo_atencion TEXT DEFAULT 'voz';
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS datos_canto JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_pacientes_tipo_atencion ON pacientes(tipo_atencion);

NOTIFY pgrst, 'reload schema';
