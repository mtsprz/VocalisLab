-- Sprint 7: Historia Clínica Híbrida + Anamnesis Dinámica
-- Fase 1: Infraestructura de Datos y Seguridad RLS

-- ============================================
-- 1. TABLA: clinical_history_templates
-- Definición de la estructura fija por consultorio
-- ============================================
CREATE TABLE IF NOT EXISTS clinical_history_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id text NOT NULL REFERENCES consultorios(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  schema_json jsonb NOT NULL, -- Estructura de secciones y campos
  version integer NOT NULL DEFAULT 1,
  is_active boolean DEFAULT true,
  created_by uuid REFERENCES profiles(id),
  updated_by uuid REFERENCES profiles(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT unique_clinic_template_name UNIQUE (clinic_id, name)
);

-- ============================================
-- 2. TABLA: clinical_history_records
-- Respuestas reales y trazabilidad de la IA
-- ============================================
CREATE TABLE IF NOT EXISTS clinical_history_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id text NOT NULL REFERENCES consultorios(id) ON DELETE CASCADE,
  patient_id uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  template_id uuid REFERENCES clinical_history_templates(id),
  template_version integer NOT NULL, -- Preserva la versión usada al momento de la creación
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'approved')),
  base_data_json jsonb NOT NULL DEFAULT '{}'::jsonb, -- Datos autocompletados/base
  ai_suggestions_json jsonb DEFAULT '{}'::jsonb, -- Sugerencias generadas por IA
  final_data_json jsonb NOT NULL DEFAULT '{}'::jsonb, -- Datos validados y aprobados por el profesional
  ai_metadata jsonb DEFAULT '{}'::jsonb, -- Trazabilidad: { prompt, response, timestamp, user_id }
  author_id uuid REFERENCES profiles(id),
  approved_by uuid REFERENCES profiles(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- ============================================
-- 3. SEGURIDAD: RLS (Row Level Security)
-- ============================================
ALTER TABLE clinical_history_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical_history_records ENABLE ROW LEVEL SECURITY;

-- POLÍTICAS PARA PLANTILLAS (clinical_history_templates)
-- Solo administradores pueden crear/editar plantillas
CREATE POLICY cht_select ON clinical_history_templates
  FOR SELECT USING (
    consultorio_id = ANY(user_consultorios()) OR user_role() = 'admin'
  );

CREATE POLICY cht_insert ON clinical_history_templates
  FOR INSERT WITH CHECK (user_role() = 'admin');

CREATE POLICY cht_update ON clinical_history_templates
  FOR UPDATE USING (user_role() = 'admin');

CREATE POLICY cht_delete ON clinical_history_templates
  FOR DELETE USING (user_role() = 'admin');

-- POLÍTICAS PARA REGISTROS (clinical_history_records)
-- Lectura: Basada en accesibilidad del paciente y consultorio
CREATE POLICY chr_select ON clinical_history_records
  FOR SELECT USING (
    is_patient_accessible(patient_id)
    AND (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin')
  );

-- Inserción: Solo profesionales o admins que tengan acceso al paciente
CREATE POLICY chr_insert ON clinical_history_records
  FOR INSERT WITH CHECK (
    is_patient_accessible(patient_id)
    AND (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin')
  );

-- Actualización: Restricciones estrictas sobre el estado 'approved'
CREATE POLICY chr_update ON clinical_history_records
  FOR UPDATE USING (
    is_patient_accessible(patient_id)
    AND (
      -- El autor puede editar si el registro está en draft o reviewed
      (author_id = auth.uid() AND status != 'approved')
      -- El admin o supervisor puede editar/aprobar siempre
      OR (user_role() IN ('admin', 'supervisor'))
    )
  )
  WITH CHECK (
    -- Evita que alguien sin rol de admin/supervisor cambie el estado a 'approved'
    (status = 'approved' AND user_role() IN ('admin', 'supervisor'))
    OR (status != 'approved')
  );

CREATE POLICY chr_delete ON clinical_//history_records
  FOR DELETE USING (user_role() = 'admin');

-- ============================================
-- 4. INDEXES para optimización
-- ============================================
CREATE INDEX idx_chr_patient_id ON clinical_history_records(patient_id);
CREATE INDEX idx_chr_clinic_id ON clinical_history_records(clinic_id);
CREATE INDEX idx_chr_status ON clinical_history_records(status);
