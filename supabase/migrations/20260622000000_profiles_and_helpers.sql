-- Fase 1: Multi-user foundation

-- ============================================
-- 1. TABLA PROFILES
-- ============================================
CREATE TABLE IF NOT EXISTS profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email text NOT NULL,
  full_name text NOT NULL,
  avatar_url text,
  role text NOT NULL DEFAULT 'profesional'
    CHECK (role IN ('admin', 'profesional', 'secretaria', 'supervisor')),
  consultorio_ids text[] DEFAULT '{}',
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- RLS: users see their own profile, admins see all
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS profiles_select ON profiles;
CREATE POLICY profiles_select ON profiles
  FOR SELECT USING (
    id = auth.uid()
    OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
  );

DROP POLICY IF EXISTS profiles_insert ON profiles;
CREATE POLICY profiles_insert ON profiles
  FOR INSERT WITH CHECK (
    id = auth.uid()
  );

DROP POLICY IF EXISTS profiles_update ON profiles;
CREATE POLICY profiles_update ON profiles
  FOR UPDATE USING (
    id = auth.uid()
    OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
  );

DROP POLICY IF EXISTS profiles_delete ON profiles;
CREATE POLICY profiles_delete ON profiles
  FOR DELETE USING (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
  );

-- Trigger: auto-create profile on user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO profiles (id, email, full_name, avatar_url)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(
      NEW.raw_user_meta_data->>'full_name',
      NEW.raw_user_meta_data->>'name',
      split_part(NEW.email, '@', 1)
    ),
    COALESCE(
      NEW.raw_user_meta_data->>'avatar_url',
      NEW.raw_user_meta_data->>'picture',
      NULL
    )
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ============================================
-- 2. TABLA CONSULTORIOS
-- ============================================
CREATE TABLE IF NOT EXISTS consultorios (
  id text PRIMARY KEY,
  name text NOT NULL,
  color text DEFAULT 'blue',
  icon text DEFAULT '🏥',
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now()
);

-- RLS: read for all, write for admins only
ALTER TABLE consultorios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS consultorios_select ON consultorios;
CREATE POLICY consultorios_select ON consultorios
  FOR SELECT USING (true);

DROP POLICY IF EXISTS consultorios_insert ON consultorios;
CREATE POLICY consultorios_insert ON consultorios
  FOR INSERT WITH CHECK (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
  );

DROP POLICY IF EXISTS consultorios_update ON consultorios;
CREATE POLICY consultorios_update ON consultorios
  FOR UPDATE USING (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
  );

DROP POLICY IF EXISTS consultorios_delete ON consultorios;
CREATE POLICY consultorios_delete ON consultorios
  FOR DELETE USING (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
  );

-- Seed default consultorios
INSERT INTO consultorios (id, name, color, icon) VALUES
  ('consultorio_1', 'Consultorio 1', 'blue', '🏥'),
  ('consultorio_2', 'Consultorio 2', 'purple', '🏥'),
  ('privado', 'Privado', 'emerald', '🏠'),
  ('online', 'Online', 'cyan', '💻'),
  ('clinica', 'Clínica', 'amber', '🏨')
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- 3. HELPER FUNCTIONS
-- ============================================
CREATE OR REPLACE FUNCTION user_role()
RETURNS text AS $$
  SELECT COALESCE(
    (SELECT role FROM profiles WHERE id = auth.uid()),
    'profesional'  -- default when no profile (dev bypass)
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION user_consultorios()
RETURNS text[] AS $$
  SELECT COALESCE(
    (SELECT consultorio_ids FROM profiles WHERE id = auth.uid()),
    ARRAY['consultorio_1', 'consultorio_2', 'privado', 'online', 'clinica']::text[]  -- dev: all consultorios
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

CREATE OR REPLACE FUNCTION user_is_admin()
RETURNS boolean AS $$
  SELECT user_role() = 'admin';
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ============================================
-- 4. SEED: local dev user profile
-- ============================================
-- NOTE: The dev profile cannot be seeded here because the dev user
-- doesn't exist in auth.users yet. It's created from the frontend
-- on first bypass login via ProfileService.ensureDevProfile().

