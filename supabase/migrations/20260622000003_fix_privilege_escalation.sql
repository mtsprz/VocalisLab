-- Fix BUG-1: Prevent self privilege escalation
-- Users cannot change their own role. Only admins can change roles.

-- 1. Simplify profiles_update: users can update own profile, admins can update anyone
-- Remove the old policy and replace with a permissive one
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'profiles') THEN
    DROP POLICY IF EXISTS profiles_update ON profiles;
    CREATE POLICY profiles_update ON profiles
      FOR UPDATE USING (
        id = auth.uid() OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
      );
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. Trigger: block non-admin from modifying role column on their own row
CREATE OR REPLACE FUNCTION prevent_self_role_change()
RETURNS trigger AS $$
BEGIN
  IF NEW.role IS DISTINCT FROM OLD.role THEN
    IF (SELECT role FROM profiles WHERE id = auth.uid()) != 'admin' THEN
      RAISE EXCEPTION 'Only admins can change user roles';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_prevent_self_role_change ON profiles;
CREATE TRIGGER trg_prevent_self_role_change
  BEFORE UPDATE ON profiles
  FOR EACH ROW
  EXECUTE FUNCTION prevent_self_role_change();
