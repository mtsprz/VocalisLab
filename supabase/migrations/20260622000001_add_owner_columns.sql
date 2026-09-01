-- Fase 2: Add owner_id columns and backfill

-- ============================================
-- 1. PATIENTS: add owner_id, rename consultorio
-- ============================================
ALTER TABLE patients ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES profiles(id);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS consultorio_id text REFERENCES consultorios(id);

-- Backfill consultorio_id from existing consultorio text
UPDATE patients SET consultorio_id = consultorio
WHERE consultorio_id IS NULL AND consultorio IS NOT NULL AND consultorio != '';

-- Note: owner_id left as NULL for existing data. New patients get owner_id from the app.

-- ============================================
-- 2. SESSIONS: add owner_id
-- ============================================
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES profiles(id);

-- Backfill from patient owner
UPDATE sessions SET owner_id = (
  SELECT p.owner_id FROM patients p WHERE p.id = sessions.patient_id
) WHERE owner_id IS NULL;

-- ============================================
-- 3. REPORTS: fix author_id type (text → uuid) (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'reports') THEN
    -- First drop FK if exists
    IF EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid = 'reports'::regclass
        AND conname LIKE '%author%'
    ) THEN
      ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_author_id_fkey;
    END IF;

    -- Delete rows with non-uuid author_id
    UPDATE reports SET author_id = NULL WHERE author_id IS NOT NULL AND author_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';

    -- Change author_id to uuid (only if currently text)
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name = 'reports' AND column_name = 'author_id' AND data_type = 'text'
    ) THEN
      ALTER TABLE reports ALTER COLUMN author_id TYPE uuid USING author_id::uuid;
    END IF;

    -- Add FK (only if not exists)
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid = 'reports'::regclass
        AND conname = 'reports_author_id_fkey'
    ) THEN
      ALTER TABLE reports ADD CONSTRAINT reports_author_id_fkey
        FOREIGN KEY (author_id) REFERENCES profiles(id);
    END IF;
  END IF;
END $$;

-- ============================================
-- 4. TEST_RESULTS: populate author_id (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_results') THEN
    UPDATE test_results SET author_id = (
      SELECT p.owner_id FROM patients p WHERE p.id = test_results.patient_id
    ) WHERE author_id IS NULL;
  END IF;
END $$;

-- ============================================
-- 5. CLINICAL_RECORDS: unify created_by → owner_id (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'clinical_records') THEN
    ALTER TABLE clinical_records ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES profiles(id);
  END IF;
END $$;

-- ============================================
-- 6. PATIENT_ANAMNESIS: ensure author_id is uuid FK (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'patient_anamnesis') THEN
    UPDATE patient_anamnesis SET author_id = (
      SELECT p.owner_id FROM patients p WHERE p.id = patient_anamnesis.patient_id
    ) WHERE author_id IS NULL;
  END IF;
END $$;

-- ============================================
-- 7. NBA_SUGGESTIONS: add owner_id (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'nba_suggestions') THEN
    ALTER TABLE nba_suggestions ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES profiles(id);
    UPDATE nba_suggestions SET owner_id = (
      SELECT p.owner_id FROM patients p WHERE p.id = nba_suggestions.patient_id
    ) WHERE owner_id IS NULL;
  END IF;
END $$;

-- ============================================
-- 8. NBA_DECISIONS: add owner_id (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'nba_decisions') THEN
    ALTER TABLE nba_decisions ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES profiles(id);
    UPDATE nba_decisions SET owner_id = (
      SELECT p.owner_id FROM patients p WHERE p.id = nba_decisions.patient_id
    ) WHERE owner_id IS NULL;
  END IF;
END $$;

-- ============================================
-- 9. HOME_GUIDES: add owner_id (if table exists)
-- ============================================
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'home_guides') THEN
    ALTER TABLE home_guides ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES profiles(id);
    UPDATE home_guides SET owner_id = (
      SELECT p.owner_id FROM patients p WHERE p.id = home_guides."patientId"
    ) WHERE owner_id IS NULL;
  END IF;
END $$;

-- ============================================
-- 10. APPOINTMENTS: rename consultorio → consultorio_id
-- ============================================
-- Only if consultorio_id doesn't exist yet
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'appointments' AND column_name = 'consultorio_id'
  ) THEN
    ALTER TABLE appointments ADD COLUMN consultorio_id text REFERENCES consultorios(id);
    UPDATE appointments SET consultorio_id = consultorio WHERE consultorio IS NOT NULL;
  END IF;
END $$;
