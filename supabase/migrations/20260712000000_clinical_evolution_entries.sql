-- clinical_evolution_entries: stores longitudinal clinical evolution data per patient
-- patients.id is TEXT (not uuid), so patient_id must be text too

DROP TABLE IF EXISTS clinical_evolution_entries CASCADE;

CREATE TABLE clinical_evolution_entries (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_id text NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  axis text NOT NULL,
  date text NOT NULL,
  source text NOT NULL DEFAULT 'manual',
  source_id text,
  signs jsonb DEFAULT '[]'::jsonb,
  measures jsonb DEFAULT '{}'::jsonb,
  risk_level text NOT NULL DEFAULT 'normal',
  notes text DEFAULT '',
  actions jsonb DEFAULT '[]'::jsonb,
  status text DEFAULT 'active',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evolution_entries_patient ON clinical_evolution_entries(patient_id);
CREATE INDEX IF NOT EXISTS idx_evolution_entries_axis ON clinical_evolution_entries(axis);
CREATE INDEX IF NOT EXISTS idx_evolution_entries_date ON clinical_evolution_entries(date DESC);

ALTER TABLE clinical_evolution_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated full access on clinical_evolution_entries"
  ON clinical_evolution_entries
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);
