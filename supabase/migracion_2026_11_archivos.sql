-- VocalisLab — Migración 2026-11: archivos de la ficha del paciente
--
-- Cómo correrla: Supabase → SQL Editor → New query → pegar todo → Run.
-- Se puede correr más de una vez sin problema.
--
-- Los archivos (informes ORL, fotos, videos y audios de WhatsApp) viven en
-- el Google Drive del profesional, en una carpeta por paciente. Esta tabla
-- guarda solo los datos para listarlos en la ficha y el enlace de Drive.

CREATE TABLE IF NOT EXISTS archivos_paciente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL DEFAULT 'documento',   -- informe_orl | estudio | foto | video | audio | documento
    origen TEXT NOT NULL DEFAULT 'otro',      -- whatsapp_paciente | whatsapp_orl | orl | consultorio | otro
    titulo TEXT DEFAULT '',
    fecha DATE DEFAULT CURRENT_DATE,          -- fecha del estudio o de recepción
    notas TEXT DEFAULT '',
    nombre_archivo TEXT DEFAULT '',
    mime TEXT DEFAULT '',
    tamano_bytes BIGINT DEFAULT 0,
    drive_file_id TEXT,
    drive_url TEXT,
    drive_carpeta_url TEXT,
    subido_por TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_archivos_paciente_paciente ON archivos_paciente(paciente_id, fecha DESC);

-- Solo el servidor (clave de servicio) accede a la tabla.
ALTER TABLE archivos_paciente ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
