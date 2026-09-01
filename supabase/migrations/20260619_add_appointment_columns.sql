-- Add missing columns to appointments table for Google Calendar sync and extended scheduling
ALTER TABLE appointments
  ADD COLUMN IF NOT EXISTS google_event_id text,
  ADD COLUMN IF NOT EXISTS professional_id text,
  ADD COLUMN IF NOT EXISTS start_time text,
  ADD COLUMN IF NOT EXISTS end_time text,
  ADD COLUMN IF NOT EXISTS duration integer DEFAULT 30,
  ADD COLUMN IF NOT EXISTS origin text DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS location text,
  ADD COLUMN IF NOT EXISTS room_id text,
  ADD COLUMN IF NOT EXISTS consultorio text,
  ADD COLUMN IF NOT EXISTS color_id text,
  ADD COLUMN IF NOT EXISTS notes text,
  ADD COLUMN IF NOT EXISTS status_changed_at text,
  ADD COLUMN IF NOT EXISTS status_changed_by text,
  ADD COLUMN IF NOT EXISTS cancellation_reason text,
  ADD COLUMN IF NOT EXISTS reschedule_reason text;

-- Add index for google_event_id lookups
CREATE INDEX IF NOT EXISTS idx_appointments_google_event_id ON appointments (google_event_id);
