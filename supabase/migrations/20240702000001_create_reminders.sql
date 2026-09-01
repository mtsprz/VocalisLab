-- Table for scheduling material deliveries/reminders
CREATE TABLE IF NOT EXISTS reminders (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  material_title TEXT NOT NULL,
  recipient_contact TEXT NOT NULL,
  medium TEXT NOT NULL, -- 'whatsapp' or 'email'
  scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
  status TEXT DEFAULT 'pending', -- 'pending', 'sent', 'failed'
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast lookup by status and scheduled time
CREATE INDEX ON reminders (status, scheduled_at);
