-- Sprint 3: QuickMode lifecycle (quick_status)

-- 1. Add quick_status column to patients
ALTER TABLE patients
  ADD COLUMN IF NOT EXISTS quick_status text;

-- CHECK constraint: closed enum of allowed values
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'quick_status_check'
  ) THEN
    ALTER TABLE patients
      ADD CONSTRAINT quick_status_check
      CHECK (quick_status IN ('active_quick', 'formalized', 'discarded'));
  END IF;
END $$;

-- Index for fast filtering
CREATE INDEX IF NOT EXISTS idx_patients_quick_status ON patients(quick_status);

-- 2. Ensure reports.patient_id is uuid and FK is correct
DO $$
DECLARE
  col_type text;
BEGIN
  -- Check current type of patient_id
  SELECT data_type INTO col_type
  FROM information_schema.columns
  WHERE table_name = 'reports' AND column_name = 'patient_id';

  -- Drop existing FK if present
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'reports'::regclass
      AND contype = 'f'
      AND confrelid = 'patients'::regclass
  ) THEN
    ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_patient_id_fkey;
  END IF;

  -- If column is text, clean up and cast to uuid
  IF col_type = 'text' THEN
    -- Delete rows with non-uuid patient_id values
    DELETE FROM reports
    WHERE patient_id IS NOT NULL
      AND patient_id::text !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

    -- Cast to uuid
    ALTER TABLE reports ALTER COLUMN patient_id TYPE uuid USING patient_id::uuid;
  END IF;

  -- Recreate FK (column is now uuid)
  ALTER TABLE reports
    ADD CONSTRAINT reports_patient_id_fkey
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
END $$;
