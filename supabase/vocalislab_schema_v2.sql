-- ============================================
-- VocalisLab Pro — Schema Completo v2.0
-- Plataforma Clínica Fonoaudiológica Integral
-- ============================================

-- 1. PACIENTES
CREATE TABLE IF NOT EXISTS pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    nombre_completo TEXT NOT NULL,
    dni TEXT UNIQUE NOT NULL,
    fecha_nacimiento DATE,
    sexo TEXT CHECK (sexo IN ('Masculino', 'Femenino', 'Otro', '')),
    telefono TEXT,
    email TEXT,
    ocupacion TEXT,
    demanda_vocal_horas INT,
    derivador TEXT,
    notas_iniciales TEXT,
    activo BOOLEAN DEFAULT true
);

-- 2. ANAMNESIS
CREATE TABLE IF NOT EXISTS anamnesis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now(),
    motivo_consulta TEXT,
    diagnostico_orl TEXT,
    metodo_exploracion TEXT,
    sintomas JSONB DEFAULT '{}',
    factores_riesgo JSONB DEFAULT '{}',
    transcripcion_audio TEXT,
    muestra_vocal_url TEXT,
    duracion_consulta_s FLOAT,
    audio_url TEXT
);

-- 3. EVALUACIONES CLÍNICAS (GRBAS, RASATI, VHI, TME, Riesgo)
CREATE TABLE IF NOT EXISTS evaluaciones_clinicas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    anamnesis_id UUID REFERENCES anamnesis(id) ON DELETE SET NULL,
    fecha TIMESTAMP WITH TIME O DEFAULT now(),
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

-- 4. ANÁLISIS ACÚSTICOS (Praat / Motor VocalisLab)
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

-- 5. CUADERNILLOS TERAPÉUTICOS
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

-- 6. AGENDA / TURNOS
CREATE TABLE IF NOT EXISTS turnos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    fecha_hora TIMESTAMP WITH TIME ZONE NOT NULL,
    duracion_min INT DEFAULT 30,
    tipo TEXT CHECK (tipo IN ('primera_vez', 'control', 'seguimiento', 'evaluacion', 'terapia')) DEFAULT 'control',
    estado TEXT CHECK (estado IN ('programado', 'confirmado', 'completado', 'cancelado', 'no_asistio')) DEFAULT 'programado',
    notas TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- 7. ÍNDICES
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

-- 8. RLS (Row Level Security)
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE anamnesis ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluaciones_clinicas ENABLE ROW LEVEL SECURITY;
ALTER TABLE analisis_acusticos ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuadernillos_paciente ENABLE ROW LEVEL SECURITY;
ALTER TABLE turnos ENABLE ROW LEVEL SECURITY;

-- Políticas: acceso completo para service role (backend)
CREATE POLICY "Service role full access" ON pacientes FOR ALL USING (true);
CREATE POLICY "Service role full access" ON anamnesis FOR ALL USING (true);
CREATE POLICY "Service role full access" ON evaluaciones_clinicas FOR ALL USING (true);
CREATE POLICY "Service role full access" ON analisis_acusticos FOR ALL USING (true);
CREATE POLICY "Service role full access" ON cuadernillos_paciente FOR ALL USING (true);
CREATE POLICY "Service role full access" ON turnos FOR ALL USING (true);

-- 9. TRIGGER para updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_pacientes_updated_at
    BEFORE UPDATE ON pacientes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
