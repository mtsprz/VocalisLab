-- HARDENING: Dedicated Reports System
-- This script replaces the reports array in the patients table with a dedicated table.

-- 1. Create the Reports table
CREATE TABLE IF NOT EXISTS reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id text NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    title text NOT NULL,
    type text NOT NULL, -- 'valoracion', 'proceso', 'etc'
    content text NOT NULL, -- HTML content of the report
    version int DEFAULT 1,
    clinical_snapshot jsonb, -- Snapshot of variables used: { "diagnosis": "...", "age": 5 }
    author_id text, -- User who created/modified the report
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

-- 2. Enable RLS
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all access for reports" ON reports FOR ALL USING (true) WITH CHECK (true);

-- 3. Performance Index
CREATE INDEX IF NOT EXISTS idx_reports_patient_id ON reports(patient_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(type);

-- 4. Trigger for updated_at
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_reports_modtime
    BEFORE UPDATE ON reports
    FOR EACH ROW
    EXECUTE PROCEDURE update_modified_column();
