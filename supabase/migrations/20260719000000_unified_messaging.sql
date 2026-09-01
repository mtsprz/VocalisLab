-- ============================================
-- UNIFIED MESSAGING INBOX
-- ============================================

-- Threads: unified conversation view per patient
CREATE TABLE IF NOT EXISTS message_threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID REFERENCES patients(id) ON DELETE CASCADE,
  channel TEXT NOT NULL CHECK (channel IN ('gmail', 'telegram', 'whatsapp')),
  subject TEXT,
  last_message_at TIMESTAMPTZ DEFAULT now(),
  unread_count INT DEFAULT 0,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Individual messages
CREATE TABLE IF NOT EXISTS message_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID REFERENCES message_threads(id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  sender_name TEXT,
  sender_email TEXT,
  content TEXT,
  attachments JSONB DEFAULT '[]',
  external_id TEXT,
  read_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Email templates for clinical communication
CREATE TABLE IF NOT EXISTS email_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  category TEXT,
  subject_template TEXT,
  body_template TEXT,
  variables JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_message_threads_patient ON message_threads(patient_id);
CREATE INDEX IF NOT EXISTS idx_message_threads_channel ON message_threads(channel);
CREATE INDEX IF NOT EXISTS idx_message_threads_last_msg ON message_threads(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON message_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON message_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_external ON message_messages(external_id);

-- RLS
ALTER TABLE message_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all access for message_threads" ON message_threads FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all access for message_messages" ON message_messages FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all access for email_templates" ON email_templates FOR ALL USING (true) WITH CHECK (true);
