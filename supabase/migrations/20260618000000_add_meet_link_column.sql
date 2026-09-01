-- Ensure meet_link column exists in appointments table
-- This column stores the Google Meet link for teleconsulta appointments

-- Add column if it doesn't exist (idempotent)
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS meet_link TEXT;

-- If the old camelCase column exists, migrate data and drop it
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='meetlink') THEN
    -- Copy data from old column to new column if new column is empty
    UPDATE appointments SET meet_link = meetlink WHERE meet_link IS NULL AND meetlink IS NOT NULL;
    -- Drop old column
    ALTER TABLE appointments DROP COLUMN meetlink;
  END IF;
END $$;

-- Verify
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'appointments' AND column_name = 'meet_link';
