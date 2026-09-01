-- Sprint 7: Tablas de Historia Clínica (FIX - sin errores de sintaxis)

CREATE TABLE IF NOT EXISTS clinical_history_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id text NOT NULL REFERENCES consultorios(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  schema_json jsonb NOT NULL,
  version integer NOT NULL DEFAULT 1,
  is_active boolean DEFAULT true,
  created_by uuid REFERENCES profiles(id),
  updated_by uuid REFERENCES profiles(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT unique_clinic_template_name UNIQUE (clinic_id, name)
);

CREATE TABLE IF NOT EXISTS clinical_history_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id text NOT NULL REFERENCES consultorios(id) ON DELETE CASCADE,
  patient_id uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  template_id uuid REFERENCES clinical_history_templates(id),
  template_version integer NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'approved')),
  base_data_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  ai_suggestions_json jsonb DEFAULT '{}'::jsonb,
  final_data_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  ai_metadata jsonb DEFAULT '[]'::jsonb,
  author_id uuid REFERENCES profiles(id),
  approved_by uuid REFERENCES profiles(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE clinical_history_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical_history_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY cht_select ON clinical_history_templates FOR SELECT USING (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin');
CREATE POLICY cht_insert ON clinical_history_templates FOR INSERT WITH CHECK (user_role() = 'admin');
CREATE POLICY cht_update ON clinical_history_templates FOR UPDATE USING (user_role() = 'admin');
CREATE POLICY cht_delete ON clinical_history_templates FOR DELETE USING (user_role() = 'admin');

CREATE POLICY chr_select ON clinical_history_records FOR SELECT USING (is_patient_accessible(patient_id) AND (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin'));
CREATE POLICY chr_insert ON clinical_history_records FOR INSERT WITH CHECK (is_patient_accessible(patient_id) AND (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin'));
CREATE POLICY chr_update ON clinical_history_records FOR UPDATE USING (is_patient_accessible(patient_id) AND ((author_id = auth.uid() AND status != 'approved') OR (user_role() IN ('admin', 'supervisor')))) WITH CHECK ((status = 'approved' AND user_role() IN ('admin', 'supervisor')) OR (status != 'approved'));
CREATE POLICY chr_delete ON clinical_history_records FOR DELETE USING (user_role() = 'admin');

CREATE INDEX IF NOT EXISTS idx_chr_patient_id ON clinical_history_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_chr_clinic_id ON clinical_history_records(clinic_id);
CREATE INDEX IF NOT EXISTS idx_chr_status ON clinical_history_records(status);
