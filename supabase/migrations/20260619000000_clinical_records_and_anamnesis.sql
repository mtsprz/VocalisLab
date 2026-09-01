-- ============================================================
-- Migration: Ficha Clínica Inteligente + Anamnesis Dinámica
-- Date: 2026-06-19
-- ============================================================

-- 1. Enhance patients table with identity fields
ALTER TABLE patients ADD COLUMN IF NOT EXISTS date_of_birth date;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS gender text;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS address text;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS emergency_contact text;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS emergency_phone text;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS insurance_number text;
ALTER TABLE patients ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
ALTER TABLE patients ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- 2. Create clinical_records table (1:1 with patients)
CREATE TABLE IF NOT EXISTS clinical_records (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id            uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

    chief_complaint       text,
    chief_complaint_onset text,

    personal_history      jsonb DEFAULT '{}'::jsonb,
    family_history        jsonb DEFAULT '{}'::jsonb,
    medical_history       jsonb DEFAULT '{}'::jsonb,
    developmental_history jsonb DEFAULT '{}'::jsonb,

    clinical_observations text,

    affected_areas        jsonb DEFAULT '[]'::jsonb,

    primary_diagnosis_code   text,
    primary_diagnosis_name   text,
    secondary_diagnosis_codes jsonb DEFAULT '[]'::jsonb,

    created_by  uuid REFERENCES auth.users(id),
    updated_by  uuid REFERENCES auth.users(id),
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now(),

    UNIQUE(patient_id)
);

CREATE INDEX IF NOT EXISTS idx_clinical_records_patient ON clinical_records(patient_id);

ALTER TABLE clinical_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all access" ON clinical_records FOR ALL USING (true) WITH CHECK (true);

-- 3. Create patient_anamnesis table (1:N versionable)
CREATE TABLE IF NOT EXISTS patient_anamnesis (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  uuid NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    version     integer NOT NULL DEFAULT 1,
    status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'final')),
    sections    jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes       text,
    author_id   uuid REFERENCES auth.users(id),
    created_at  timestamptz DEFAULT now(),
    updated_at  timestamptz DEFAULT now(),

    UNIQUE(patient_id, version)
);

CREATE INDEX IF NOT EXISTS idx_anamnesis_patient ON patient_anamnesis(patient_id);
CREATE INDEX IF NOT EXISTS idx_anamnesis_current ON patient_anamnesis(patient_id, status);

ALTER TABLE patient_anamnesis ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all access" ON patient_anamnesis FOR ALL USING (true) WITH CHECK (true);
