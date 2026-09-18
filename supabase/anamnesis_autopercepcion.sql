-- Anamnesis: persistir autopercepción de la voz (0-10) y antecedentes de salud.
-- La autopercepción de la sesión 1 es la línea de base y se compara en sesión 8.
-- Idempotente. El backend tolera la ausencia de estas columnas (las quita y reintenta).
ALTER TABLE anamnesis ADD COLUMN IF NOT EXISTS autopercepcion_voz INT;
ALTER TABLE anamnesis ADD COLUMN IF NOT EXISTS antecedentes_salud TEXT;
COMMENT ON COLUMN anamnesis.autopercepcion_voz IS 'Autovaloración de la voz 0-10. Sesión 1 = línea de base.';
