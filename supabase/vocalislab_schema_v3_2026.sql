-- ============================================================================
-- VOCALISLAB PRO v3.0 — SCHEMA EDICIÓN 2026 (MANUAL DE REHABILITACIÓN VOCAL)
-- Lic. Matías Pérez — M.P. 7276
-- Idempotente y compatible con esquema existente
-- ============================================================================

-- 1. TABLA EVALUACIONES VHI-10 (Sección 3 del Manual)
CREATE TABLE IF NOT EXISTS evaluations_vhi10 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    evaluacion_clinica_id UUID REFERENCES evaluaciones_clinicas(id) ON DELETE SET NULL,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    
    q1_ruido INT CHECK (q1_ruido BETWEEN 0 AND 4) DEFAULT 0,
    q2_oyentes_ruido INT CHECK (q2_oyentes_ruido BETWEEN 0 AND 4) DEFAULT 0,
    q3_trabajo_personal INT CHECK (q3_trabajo_personal BETWEEN 0 AND 4) DEFAULT 0,
    q4_tension_hablar INT CHECK (q4_tension_hablar BETWEEN 0 AND 4) DEFAULT 0,
    q5_calidad_impredecible INT CHECK (q5_calidad_impredecible BETWEEN 0 AND 4) DEFAULT 0,
    q6_corta_sin_aire INT CHECK (q6_corta_sin_aire BETWEEN 0 AND 4) DEFAULT 0,
    q7_esfuerzo_producir INT CHECK (q7_esfuerzo_producir BETWEEN 0 AND 4) DEFAULT 0,
    q8_voz_ronca_aspera INT CHECK (q8_voz_ronca_aspera BETWEEN 0 AND 4) DEFAULT 0,
    q9_limita_vida_social INT CHECK (q9_limita_vida_social BETWEEN 0 AND 4) DEFAULT 0,
    q10_gente_no_comprende INT CHECK (q10_gente_no_comprende BETWEEN 0 AND 4) DEFAULT 0,
    
    total_score INT DEFAULT 0,
    grado_impacto TEXT DEFAULT 'Impacto mínimo',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 2. TABLA CUESTIONARIO DE RIESGO VOCAL DE 5 ÁREAS (Sección 4 del Manual)
CREATE TABLE IF NOT EXISTS risk_assessment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    evaluacion_clinica_id UUID REFERENCES evaluaciones_clinicas(id) ON DELETE SET NULL,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    
    area_a_habitos_vocales JSONB NOT NULL DEFAULT '{}',   -- Máx 18 pts
    area_b_estado_emocional JSONB NOT NULL DEFAULT '{}',  -- Máx 15 pts
    area_c_condiciones_bio JSONB NOT NULL DEFAULT '{}',   -- Máx 18 pts
    area_d_condiciones_amb JSONB NOT NULL DEFAULT '{}',   -- Máx 12 pts
    area_e_habitos_vida JSONB NOT NULL DEFAULT '{}',      -- Máx 15 pts
    
    subtotal_a INT NOT NULL DEFAULT 0,
    subtotal_b INT NOT NULL DEFAULT 0,
    subtotal_c INT NOT NULL DEFAULT 0,
    subtotal_d INT NOT NULL DEFAULT 0,
    subtotal_e INT NOT NULL DEFAULT 0,
    total_score INT DEFAULT 0,
    
    prioridades_compromiso JSONB NOT NULL DEFAULT '[]', -- Array de 3 prioridades
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 3. TABLA SEGUIMIENTO DIARIO TME /s/ (Sección 5 del Manual)
CREATE TABLE IF NOT EXISTS tme_tracker (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    cuadernillo_id UUID REFERENCES cuadernillos_paciente(id) ON DELETE SET NULL,
    fecha_medicion DATE NOT NULL DEFAULT CURRENT_DATE,
    dia_semana TEXT DEFAULT 'Lunes',
    
    medicion_1_s FLOAT NOT NULL DEFAULT 0,
    medicion_2_s FLOAT NOT NULL DEFAULT 0,
    medicion_3_s FLOAT NOT NULL DEFAULT 0,
    mejor_valor_s FLOAT NOT NULL DEFAULT 0,
    
    observaciones TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 4. CATÁLOGO DE EJERCICIOS ESTRUCTURADO (Secciones 7 a 12 del Manual)
CREATE TABLE IF NOT EXISTS exercise_catalog (
    id TEXT PRIMARY KEY,
    seccion_numero INT NOT NULL,
    modulo_nombre TEXT NOT NULL,
    nombre TEXT NOT NULL,
    dosis_frecuencia TEXT NOT NULL,
    descripcion_biomecanica TEXT NOT NULL,
    secuencia_pasos JSONB NOT NULL DEFAULT '[]',
    sensacion_objetivo TEXT,
    criterio_calidad TEXT,
    precauciones TEXT,
    indicaciones_patologicas JSONB DEFAULT '[]',
    contraindicaciones JSONB DEFAULT '[]',
    referencias_apa JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- 5. TABLA REGISTRO DE HABLA ESPONTÁNEA Y FRASES PERSONALIZADAS
CREATE TABLE IF NOT EXISTS paciente_frases_personalizadas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID NOT NULL REFERENCES pacientes(id) ON DELETE CASCADE,
    oracion TEXT NOT NULL,
    contexto_uso TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- INDEXACIÓN
CREATE INDEX IF NOT EXISTS idx_vhi10_paciente ON evaluations_vhi10(paciente_id);
CREATE INDEX IF NOT EXISTS idx_risk_paciente ON risk_assessment(paciente_id);
CREATE INDEX IF NOT EXISTS idx_tme_paciente_fecha ON tme_tracker(paciente_id, fecha_medicion);

-- HABILITAR RLS
ALTER TABLE evaluations_vhi10 ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_assessment ENABLE ROW LEVEL SECURITY;
ALTER TABLE tme_tracker ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE paciente_frases_personalizadas ENABLE ROW LEVEL SECURITY;

-- POLÍTICAS RLS IDEMPOTENTES
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow full access to evaluations_vhi10') THEN
        CREATE POLICY "Allow full access to evaluations_vhi10" ON evaluations_vhi10 FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow full access to risk_assessment') THEN
        CREATE POLICY "Allow full access to risk_assessment" ON risk_assessment FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow full access to tme_tracker') THEN
        CREATE POLICY "Allow full access to tme_tracker" ON tme_tracker FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow full access to exercise_catalog') THEN
        CREATE POLICY "Allow full access to exercise_catalog" ON exercise_catalog FOR ALL USING (true) WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow full access to paciente_frases_personalizadas') THEN
        CREATE POLICY "Allow full access to paciente_frases_personalizadas" ON paciente_frases_personalizadas FOR ALL USING (true) WITH CHECK (true);
    END IF;
END $$;
