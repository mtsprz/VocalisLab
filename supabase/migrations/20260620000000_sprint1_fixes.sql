-- Sprint 1: Fixes críticos de capa de entrada clínica
-- 1. FK type mismatch: clinical_records + patient_anamnesis patient_id uuid → text
-- 2. Column naming: "obraSocial" → obra_social
-- 3. Test results table creation

-- ============================================================
-- 1. FIX FK TYPE MISMATCH
-- ============================================================
-- patients.id is TEXT, but clinical_records.patient_id and
-- patient_anamnesis.patient_id were uuid with FK references.
-- We must drop the FK, alter the column type, and recreate the FK.

-- clinical_records
ALTER TABLE clinical_records DROP CONSTRAINT IF EXISTS clinical_records_patient_id_fkey;
ALTER TABLE clinical_records ALTER COLUMN patient_id TYPE text;
ALTER TABLE clinical_records ADD CONSTRAINT clinical_records_patient_id_fkey
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- patient_anamnesis
ALTER TABLE patient_anamnesis DROP CONSTRAINT IF EXISTS patient_anamnesis_patient_id_fkey;
ALTER TABLE patient_anamnesis ALTER COLUMN patient_id TYPE text;
ALTER TABLE patient_anamnesis ADD CONSTRAINT patient_anamnesis_patient_id_fkey
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

-- ============================================================
-- 2. FIX COLUMN NAMING: "obraSocial" → obra_social
-- ============================================================
-- The DB has quoted "obraSocial" (camelCase) but the code writes obra_social (snake_case).
-- Rename the column to snake_case for consistency.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'patients' AND column_name = 'obraSocial'
    ) THEN
        ALTER TABLE patients RENAME COLUMN "obraSocial" TO obra_social;
    END IF;
END $$;

-- Also add obra_social if it doesn't exist at all (some DB setups)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'patients' AND column_name = 'obra_social'
    ) THEN
        ALTER TABLE patients ADD COLUMN IF NOT EXISTS obra_social text;
    END IF;
END $$;

-- ============================================================
-- 3. TEST RESULTS TABLE
-- ============================================================
-- Normalized table for standardized test results.
-- Supports versioning: a patient can take the same test multiple times.

CREATE TABLE IF NOT EXISTS test_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id text NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    test_id text NOT NULL,
    test_name text NOT NULL,
    test_acronym text,
    area text,
    subtest_scores jsonb NOT NULL DEFAULT '[]',
    raw_score numeric,
    max_score numeric,
    percentage numeric,
    percentile numeric,
    classification text,
    age_at_test integer,
    test_date date NOT NULL DEFAULT CURRENT_DATE,
    observations text,
    clinician_notes text,
    author_id uuid REFERENCES auth.users(id),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_test_results_patient ON test_results(patient_id);
CREATE INDEX IF NOT EXISTS idx_test_results_patient_test ON test_results(patient_id, test_id);
CREATE INDEX IF NOT EXISTS idx_test_results_date ON test_results(test_date DESC);

-- RLS policies
ALTER TABLE test_results ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'test_results' AND policyname = 'test_results_select'
    ) THEN
        CREATE POLICY test_results_select ON test_results FOR SELECT USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'test_results' AND policyname = 'test_results_insert'
    ) THEN
        CREATE POLICY test_results_insert ON test_results FOR INSERT WITH CHECK (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'test_results' AND policyname = 'test_results_update'
    ) THEN
        CREATE POLICY test_results_update ON test_results FOR UPDATE USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'test_results' AND policyname = 'test_results_delete'
    ) THEN
        CREATE POLICY test_results_delete ON test_results FOR DELETE USING (true);
    END IF;
END $$;
