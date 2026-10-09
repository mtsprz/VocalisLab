-- VocalisLab — Sesiones Companion offline + evolución de voz por sesión.
-- Ejecutar UNA vez en el SQL Editor de Supabase, en este orden respecto a otros archivos:
--   vocalislab_schema_v2.sql (o superior) ANTES (requiere tabla pacientes).
-- Idempotente: todo CREATE IF NOT EXISTS / ADD IF NOT EXISTS. No toca tablas existentes
-- salvo ADD COLUMN en pacientes (sexo_referencia, f0_ref_min/max_hz).
-- Decisión documentada (docs/companion-api.md § auth): profesional único; todas las
-- tablas llevan profesional_google_id para migrar a multi-profesional solo con
-- usuarios + policies. El enforcement efectivo hoy es en el backend (service_role
-- bypasea RLS); las policies aquí son permisivas como el resto del esquema.

-- ─── 0. Extensión de pacientes (overrides de referencia, editables) ───
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS sexo_referencia TEXT DEFAULT '';
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS f0_ref_min_hz FLOAT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS f0_ref_max_hz FLOAT;

-- ─── 1. Dispositivos Companion (tokens hasheados, revocables) ───
CREATE TABLE IF NOT EXISTS companion_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profesional_google_id TEXT NOT NULL,
    device_name TEXT DEFAULT '',
    token_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ,
    revoked BOOLEAN DEFAULT false,
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_companion_devices_prof ON companion_devices(profesional_google_id);

CREATE TABLE IF NOT EXISTS companion_pairing_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    profesional_google_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT false,
    used_at TIMESTAMPTZ,
    used_by_device_id UUID REFERENCES companion_devices(id) ON DELETE SET NULL
);

-- ─── 2. Sesiones grabadas offline ───
CREATE TABLE IF NOT EXISTS companion_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    profesional_google_id TEXT NOT NULL,
    device_id UUID REFERENCES companion_devices(id) ON DELETE SET NULL,
    device_session_id TEXT UNIQUE NOT NULL,
    recorded_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT now(),
    audio_storage_path TEXT,
    audio_mime TEXT,
    audio_size_bytes BIGINT,
    audio_duration_sec NUMERIC,
    audio_codec TEXT,
    audio_bitrate_kbps INT,
    status TEXT DEFAULT 'uploaded' CHECK (status IN ('uploaded','processing','processed','error')),
    dsp_version TEXT DEFAULT '',
    device_info JSONB DEFAULT '{}',
    consent_recorded BOOLEAN DEFAULT false,
    error_detail TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_companion_sessions_patient ON companion_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_companion_sessions_status ON companion_sessions(status);
CREATE INDEX IF NOT EXISTS idx_companion_sessions_prof ON companion_sessions(profesional_google_id);

-- Clips WAV cortos de vocal sostenida (revisión de jitter/shimmer/HNR)
CREATE TABLE IF NOT EXISTS session_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES companion_sessions(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL CHECK (task_type IN ('vocal_sostenida_a','conteo','lectura','conversacion_espontanea')),
    storage_path TEXT NOT NULL,
    mime TEXT DEFAULT 'audio/wav',
    size_bytes BIGINT,
    duration_sec NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_clips_session ON session_clips(session_id);

-- ─── 3. Segmentos por tarea ───
CREATE TABLE IF NOT EXISTS session_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES companion_sessions(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL CHECK (task_type IN ('vocal_sostenida_a','conteo','lectura','conversacion_espontanea')),
    speaker TEXT NOT NULL CHECK (speaker IN ('paciente','fonoaudiologo')),
    start_sec NUMERIC NOT NULL,
    end_sec NUMERIC NOT NULL,
    CHECK (end_sec > start_sec),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_segments_session ON session_segments(session_id);

-- ─── 4. Acústica por tarea (métricas oficiales = calculadas localmente sobre PCM) ───
CREATE TABLE IF NOT EXISTS session_acoustics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES companion_sessions(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL CHECK (task_type IN ('vocal_sostenida_a','conteo','lectura','conversacion_espontanea')),
    UNIQUE (session_id, task_type),
    f0_mean_hz FLOAT,
    f0_median_hz FLOAT,
    f0_sd_hz FLOAT,
    f0_sd_semitones FLOAT,
    f0_p5_hz FLOAT,
    f0_p95_hz FLOAT,
    f0_min_hz FLOAT,
    f0_max_hz FLOAT,
    voiced_fraction FLOAT,
    intensity_mean_db FLOAT,
    intensity_sd_db FLOAT,
    mpt_sec FLOAT,
    jitter_pct FLOAT,
    shimmer_pct FLOAT,
    hnr_db FLOAT,
    f0_histogram JSONB DEFAULT '{}',
    f0_contour JSONB DEFAULT '[]',
    dsp_version TEXT DEFAULT '',
    validada BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_acoustics_session ON session_acoustics(session_id);

-- ─── 5. Transcripciones ───
CREATE TABLE IF NOT EXISTS session_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES companion_sessions(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL CHECK (speaker IN ('paciente','fonoaudiologo')),
    start_sec NUMERIC NOT NULL,
    end_sec NUMERIC NOT NULL,
    text TEXT DEFAULT '',
    source TEXT DEFAULT 'ai' CHECK (source IN ('ai','manual')),
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_transcripts_session ON session_transcripts(session_id);

-- ─── 6. Borradores de anamnesis (nunca escriben la ficha directo) ───
CREATE TABLE IF NOT EXISTS anamnesis_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL UNIQUE REFERENCES companion_sessions(id) ON DELETE CASCADE,
    motivo_consulta TEXT DEFAULT '',
    sintomatologia_vocal TEXT DEFAULT '',
    habitos_vocales TEXT DEFAULT '',
    observaciones_clinicas TEXT DEFAULT '',
    plan_sugerido TEXT DEFAULT '',
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','approved','discarded')),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─── 7. Rangos de referencia (orientativos, editables) ───
CREATE TABLE IF NOT EXISTS reference_ranges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sexo_referencia TEXT NOT NULL,
    edad_min INT NOT NULL,
    edad_max INT NOT NULL,
    f0_min_hz FLOAT NOT NULL,
    f0_max_hz FLOAT NOT NULL,
    fuente TEXT DEFAULT '',
    UNIQUE (sexo_referencia, edad_min, edad_max)
);
INSERT INTO reference_ranges (sexo_referencia, edad_min, edad_max, f0_min_hz, f0_max_hz, fuente)
VALUES
    ('masculino', 18, 99, 100, 130, 'Orientativo editable — criterio clínico'),
    ('femenino', 18, 99, 190, 225, 'Orientativo editable — criterio clínico'),
    ('ninex', 4, 10, 240, 300, 'Orientativo editable — criterio clínico')
ON CONFLICT (sexo_referencia, edad_min, edad_max) DO NOTHING;

-- ─── 8. Cola de procesamiento (sobrevive reinicios vía lease) ───
CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL UNIQUE REFERENCES companion_sessions(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'queued' CHECK (status IN ('queued','processing','done','error')),
    attempts INT DEFAULT 0,
    next_retry_at TIMESTAMPTZ DEFAULT now(),
    lease_at TIMESTAMPTZ,
    last_error TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);

-- ─── 9. Log de accesos al audio ───
CREATE TABLE IF NOT EXISTS audio_access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES companion_sessions(id) ON DELETE SET NULL,
    actor TEXT DEFAULT '',
    accion TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audio_access_session ON audio_access_log(session_id);

-- ─── 10. Vista de evolución por paciente y tarea ───
DROP VIEW IF EXISTS voice_progress;
CREATE VIEW voice_progress AS
SELECT
    s.patient_id,
    a.task_type,
    s.id AS session_id,
    s.recorded_at,
    ROW_NUMBER() OVER (PARTITION BY s.patient_id, a.task_type ORDER BY s.recorded_at NULLS LAST, s.created_at) AS session_number,
    a.f0_median_hz, a.f0_sd_semitones, a.intensity_mean_db,
    a.jitter_pct, a.shimmer_pct, a.hnr_db, a.mpt_sec,
    a.validada
FROM companion_sessions s
JOIN session_acoustics a ON a.session_id = s.id
WHERE s.status = 'processed'
ORDER BY s.patient_id, a.task_type, s.recorded_at NULLS LAST;

-- ─── 11. RLS (permisiva como el resto del esquema; enforcement real en backend) ───
ALTER TABLE companion_devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE companion_pairing_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE companion_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_acoustics ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE anamnesis_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE reference_ranges ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audio_access_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "App backend full access companion" ON companion_devices;
DROP POLICY IF EXISTS "App backend full access companion" ON companion_pairing_codes;
DROP POLICY IF EXISTS "App backend full access companion" ON companion_sessions;
DROP POLICY IF EXISTS "App backend full access companion" ON session_clips;
DROP POLICY IF EXISTS "App backend full access companion" ON session_segments;
DROP POLICY IF EXISTS "App backend full access companion" ON session_acoustics;
DROP POLICY IF EXISTS "App backend full access companion" ON session_transcripts;
DROP POLICY IF EXISTS "App backend full access companion" ON anamnesis_drafts;
DROP POLICY IF EXISTS "App backend full access companion" ON reference_ranges;
DROP POLICY IF EXISTS "App backend full access companion" ON processing_jobs;
DROP POLICY IF EXISTS "App backend full access companion" ON audio_access_log;

CREATE POLICY "App backend full access companion" ON companion_devices FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON companion_pairing_codes FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON companion_sessions FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON session_clips FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON session_segments FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON session_acoustics FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON session_transcripts FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON anamnesis_drafts FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON reference_ranges FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON processing_jobs FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access companion" ON audio_access_log FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- ─── 12. Bucket privado de audios ───
INSERT INTO storage.buckets (id, name, public)
VALUES ('companion-audio-vault', 'companion-audio-vault', false)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "App backend storage companion" ON storage.objects;
CREATE POLICY "App backend storage companion" ON storage.objects
FOR ALL TO anon, authenticated
USING (bucket_id = 'companion-audio-vault') WITH CHECK (bucket_id = 'companion-audio-vault');
