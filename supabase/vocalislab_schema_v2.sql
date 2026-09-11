-- =========================================================
-- VOCALISLAB PRO v2.0 — SCHEMA MAESTRO IDEMPOTENTE
-- Diseñado para poder ejecutarse 1 o 100 veces sin errores
-- =========================================================

-- 1. TABLA PACIENTES
CREATE TABLE IF NOT EXISTS pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    nombre_completo TEXT NOT NULL,
    dni TEXT UNIQUE NOT NULL
);

ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS sexo TEXT CHECK (sexo IN ('Masculino', 'Femenino', 'Otro', ''));
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS telefono TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS ocupacion TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS demanda_vocal_horas INT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS derivador TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS notas_iniciales TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT true;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now());

-- 2. TABLA ANAMNESIS
CREATE TABLE IF NOT EXISTS anamnesis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now(),
    motivo_consulta TEXT,
    diagnostico_orl TEXT,
    metodo_exploracion TEXT,
    sintomas JSONB DEFAULT '{}',
    factores_riesgo JSONB DEFAULT '{}',
    resumen_clinico TEXT,
    transcripcion_audio TEXT,
    muestra_vocal_url TEXT,
    duracion_consulta_s FLOAT,
    audio_url TEXT
);

ALTER TABLE anamnesis ADD COLUMN IF NOT EXISTS resumen_clinico TEXT;

-- 3. TABLA EVALUACIONES CLÍNICAS
CREATE TABLE IF NOT EXISTS evaluaciones_clinicas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    anamnesis_id UUID REFERENCES anamnesis(id) ON DELETE SET NULL,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now(),
    grbas JSONB DEFAULT '{}',
    rasati JSONB DEFAULT '{}',
    vhi10_score INT,
    vhi10_detalle JSONB DEFAULT '{}',
    riesgo_vocal_score INT,
    riesgo_vocal_detalle JSONB DEFAULT '{}',
    tme_o FLOAT,
    tme_s FLOAT,
    indice_so FLOAT,
    f0_conversacional_hz FLOAT,
    extension_vocal_min TEXT,
    extension_vocal_max TEXT,
    autopercepcion_vocal INT,
    autopercepcion_momentos JSONB DEFAULT '{}',
    observaciones TEXT
);

-- 4. TABLA ANÁLISIS ACÚSTICOS
CREATE TABLE IF NOT EXISTS analisis_acusticos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    evaluacion_id UUID REFERENCES evaluaciones_clinicas(id) ON DELETE SET NULL,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now(),
    audio_url TEXT,
    duracion_s FLOAT,
    sample_rate_hz INT,
    f0_mean FLOAT,
    f0_min FLOAT,
    f0_max FLOAT,
    f0_sd FLOAT,
    f0_range FLOAT,
    jitter_local_pct FLOAT,
    jitter_rap_pct FLOAT,
    jitter_ppq5_pct FLOAT,
    shimmer_local_pct FLOAT,
    shimmer_apq3_pct FLOAT,
    shimmer_apq5_pct FLOAT,
    hnr_db FLOAT,
    cpps_db FLOAT,
    nhr FLOAT,
    nne_db FLOAT,
    avqi FLOAT,
    avqi_calculable BOOLEAN DEFAULT false,
    f1_hz FLOAT,
    f2_hz FLOAT,
    f3_hz FLOAT,
    f4_hz FLOAT,
    intensity_mean_db FLOAT,
    spectral_tilt_slope FLOAT,
    spectral_tilt_intercept FLOAT,
    graficos_json JSONB DEFAULT '{}',
    cross_check JSONB DEFAULT '{}',
    modo TEXT DEFAULT 'clinico'
);

-- 5. TABLA CUADERNILLOS TERAPÉUTICOS
CREATE TABLE IF NOT EXISTS cuadernillos_paciente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT now(),
    titulo TEXT,
    cantidad_sesiones INT DEFAULT 8,
    ejercicios_seleccionados JSONB DEFAULT '[]',
    preset_usado TEXT,
    contrato_terapeutico JSONB DEFAULT '{}',
    cronograma JSONB DEFAULT '{}',
    pdf_url TEXT,
    enviado_whatsapp BOOLEAN DEFAULT false,
    enviado_email BOOLEAN DEFAULT false,
    notas_profesional TEXT
);

-- 6. TABLA AGENDA / TURNOS
CREATE TABLE IF NOT EXISTS turnos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    fecha_hora TIMESTAMP WITH TIME ZONE NOT NULL,
    duracion_min INT DEFAULT 45,
    tipo TEXT CHECK (tipo IN ('primera_vez', 'control', 'seguimiento', 'evaluacion', 'terapia')) DEFAULT 'control',
    estado TEXT CHECK (estado IN ('programado', 'confirmado', 'completado', 'cancelado', 'no_asistio')) DEFAULT 'programado',
    modalidad TEXT DEFAULT 'PRESENCIAL',
    motivo TEXT DEFAULT 'Consulta de Voz',
    meet_link TEXT,
    google_event_id TEXT,
    notas TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

ALTER TABLE turnos ADD COLUMN IF NOT EXISTS modalidad TEXT DEFAULT 'PRESENCIAL';
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS motivo TEXT DEFAULT 'Consulta de Voz';
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS meet_link TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS google_event_id TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_meeting_id TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_password TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_join_url TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_start_url TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS zoom_status TEXT DEFAULT 'pendiente';
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS teleconsulta_provider TEXT;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS fecha_sincronizacion TIMESTAMPTZ;
ALTER TABLE turnos ADD COLUMN IF NOT EXISTS ultima_error_sincronizacion TEXT;
CREATE INDEX IF NOT EXISTS idx_turnos_google_event ON turnos(google_event_id);
CREATE INDEX IF NOT EXISTS idx_turnos_zoom_meeting ON turnos(zoom_meeting_id);

-- 6c. TABLA SESIONES DE TELECONSULTA (notas, ejercicios, duración, incidencias)
CREATE TABLE IF NOT EXISTS sesiones_teleconsulta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    turno_id UUID REFERENCES turnos(id) ON DELETE CASCADE,
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    fecha_inicio TIMESTAMPTZ DEFAULT now(),
    fecha_fin TIMESTAMPTZ,
    duracion_min INT,
    notas TEXT DEFAULT '',
    ejercicios_realizados JSONB DEFAULT '[]',
    incidencias_tecnicas TEXT DEFAULT '',
    resumen_final TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sesiones_turno ON sesiones_teleconsulta(turno_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_paciente ON sesiones_teleconsulta(paciente_id);

-- 6b. MIGRACIÓN v1 → v2 (la tabla pacientes del schema v1 no tiene estas columnas
-- y trae un NOT NULL legacy en "nombre" que bloquea los INSERT del backend)
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS nombre_completo TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS sexo TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS fecha_nacimiento DATE;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS ocupacion TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS demanda_vocal_horas INT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS notas_iniciales TEXT;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT true;
ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now());
ALTER TABLE pacientes ALTER COLUMN nombre DROP NOT NULL;

-- 7. ÍNDICES (con IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_pacientes_dni ON pacientes(dni);
CREATE INDEX IF NOT EXISTS idx_pacientes_activo ON pacientes(activo);
CREATE INDEX IF NOT EXISTS idx_anamnesis_paciente ON anamnesis(paciente_id);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_paciente ON evaluaciones_clinicas(paciente_id);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_fecha ON evaluaciones_clinicas(fecha);
CREATE INDEX IF NOT EXISTS idx_analisis_paciente ON analisis_acusticos(paciente_id);
CREATE INDEX IF NOT EXISTS idx_cuadernillos_paciente ON cuadernillos_paciente(paciente_id);
CREATE INDEX IF NOT EXISTS idx_turnos_fecha ON turnos(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_turnos_paciente ON turnos(paciente_id);
CREATE INDEX IF NOT EXISTS idx_turnos_estado ON turnos(estado);

-- 8. HABILITAR RLS
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE anamnesis ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluaciones_clinicas ENABLE ROW LEVEL SECURITY;
ALTER TABLE analisis_acusticos ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuadernillos_paciente ENABLE ROW LEVEL SECURITY;
ALTER TABLE turnos ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios_google ENABLE ROW LEVEL SECURITY;
ALTER TABLE sesiones_teleconsulta ENABLE ROW LEVEL SECURITY;

-- 9. POLÍTICAS RLS (Borrado preventivo antes de crear para evitar el error 42710)
DO $$
BEGIN
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON pacientes;
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON anamnesis;
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON evaluaciones_clinicas;
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON analisis_acusticos;
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON cuadernillos_paciente;
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON turnos;

    DROP POLICY IF EXISTS "Service role full access" ON pacientes;
    DROP POLICY IF EXISTS "Service role full access" ON anamnesis;
    DROP POLICY IF EXISTS "Service role full access" ON evaluaciones_clinicas;
    DROP POLICY IF EXISTS "Service role full access" ON analisis_acusticos;
    DROP POLICY IF EXISTS "Service role full access" ON cuadernillos_paciente;
    DROP POLICY IF EXISTS "Service role full access" ON turnos;
    DROP POLICY IF EXISTS "Allow access to authenticated users" ON usuarios_google;
    DROP POLICY IF EXISTS "Service role full access" ON usuarios_google;
END $$;

CREATE POLICY "Allow access to authenticated users" ON pacientes FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Allow access to authenticated users" ON anamnesis FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Allow access to authenticated users" ON evaluaciones_clinicas FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Allow access to authenticated users" ON analisis_acusticos FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Allow access to authenticated users" ON cuadernillos_paciente FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Allow access to authenticated users" ON turnos FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 9b. ACCESO BACKEND (el backend usa la clave anon: sin estas policies los INSERT/UPDATE fallan con 500/401)
DROP POLICY IF EXISTS "App backend full access" ON pacientes;
DROP POLICY IF EXISTS "App backend full access" ON anamnesis;
DROP POLICY IF EXISTS "App backend full access" ON evaluaciones_clinicas;
DROP POLICY IF EXISTS "App backend full access" ON analisis_acusticos;
DROP POLICY IF EXISTS "App backend full access" ON cuadernillos_paciente;
DROP POLICY IF EXISTS "App backend full access" ON turnos;
DROP POLICY IF EXISTS "App backend full access" ON usuarios_google;
DROP POLICY IF EXISTS "App backend full access" ON sesiones_teleconsulta;
CREATE POLICY "App backend full access" ON pacientes FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON anamnesis FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON evaluaciones_clinicas FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON analisis_acusticos FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON cuadernillos_paciente FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON turnos FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON usuarios_google FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "App backend full access" ON sesiones_teleconsulta FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- 10. TRIGGER UPDATED_AT
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_pacientes_updated_at ON pacientes;
CREATE TRIGGER trigger_pacientes_updated_at
    BEFORE UPDATE ON pacientes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 11. TABLA USUARIOS GOOGLE (OAuth 2.0)
CREATE TABLE IF NOT EXISTS usuarios_google (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    google_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    name TEXT,
    picture TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_usuarios_google_email ON usuarios_google(email);

DROP POLICY IF EXISTS "Allow access to authenticated users" ON usuarios_google;
CREATE POLICY "Allow access to authenticated users" ON usuarios_google FOR ALL TO authenticated USING (true) WITH CHECK (true);
