-- VocalisLab — Tokens OAuth de Canva Connect API
-- Guarda access/refresh token del flujo OAuth (una sola fila id='default').
-- Idempotente.

CREATE TABLE IF NOT EXISTS canva_tokens (
  id text PRIMARY KEY DEFAULT 'default',
  access_token text,
  refresh_token text,
  scope text,
  token_type text DEFAULT 'Bearer',
  expires_at timestamptz,
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE canva_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "App backend full access" ON canva_tokens;
CREATE POLICY "App backend full access" ON canva_tokens
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
