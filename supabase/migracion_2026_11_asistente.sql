-- VocalisLab — Migración 2026-11: asistente personal por Telegram
--
-- Cómo correrla: Supabase → SQL Editor → New query → pegar todo → Run.
-- Se puede correr más de una vez sin problema.
--
-- Guarda la configuración del asistente: chat de Telegram vinculado,
-- usuario del bot, código de vinculación y fecha del último repaso enviado.

CREATE TABLE IF NOT EXISTS asistente_config (
    clave TEXT PRIMARY KEY,
    valor JSONB,
    actualizado_at TIMESTAMPTZ DEFAULT now()
);

-- Solo el servidor (clave de servicio) accede a la tabla.
ALTER TABLE asistente_config ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
