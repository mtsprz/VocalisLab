-- VocalisLab — Migración 2026-11: centros de atención y agenda de Fonoar
--
-- Cómo correrla: Supabase → tu proyecto → SQL Editor → New query → pegar
-- todo este archivo → Run. Se puede correr más de una vez sin problema.
--
-- Qué hace:
-- 1. Pacientes: centro (fonoar_la_plata | due_brandsen | virtual), obra
--    social y origen (ej. "agenda_fonoar").
-- 2. DNI opcional: la agenda de Fonoar no trae DNI. Sigue siendo único
--    cuando se carga.
-- 3. Turnos: centro y obra social del turno.
--
-- Mientras no se corra, la app sigue funcionando: los pacientes se crean sin
-- centro ni obra social y, si el DNI es obligatorio, con uno provisorio
-- ("SD-…") que después se puede corregir.

ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS centro TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS obra_social TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS origen TEXT;
ALTER TABLE pacientes ALTER COLUMN dni DROP NOT NULL;

ALTER TABLE turnos ADD COLUMN IF NOT EXISTS centro TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS obra_social TEXT;

CREATE INDEX IF NOT EXISTS idx_pacientes_centro ON pacientes(centro);

-- Para que el servidor vea las columnas nuevas de inmediato.
NOTIFY pgrst, 'reload schema';
