-- FIX: PostgREST 500 error on profiles/patients/appointments
-- Root cause: profiles_select policy has self-referencing subquery
-- that crashes PostgREST schema evaluation
-- Safe to re-run (idempotent)

-- ============================================
-- 1. FIX profiles_select: replace self-reference with SECURITY DEFINER function
-- ============================================
DROP POLICY IF EXISTS profiles_select ON profiles;
CREATE POLICY profiles_select ON profiles
  FOR SELECT USING (
    id = auth.uid()
    OR user_role() = 'admin'
  );

-- ============================================
-- 2. FIX profiles_insert: same pattern
-- ============================================
DROP POLICY IF EXISTS profiles_insert ON profiles;
CREATE POLICY profiles_insert ON profiles
  FOR INSERT WITH CHECK (
    id = auth.uid()
    OR user_role() = 'admin'
  );

-- ============================================
-- 3. FIX profiles_update: same pattern
-- ============================================
DROP POLICY IF EXISTS profiles_update ON profiles;
CREATE POLICY profiles_update ON profiles
  FOR UPDATE USING (
    id = auth.uid()
    OR user_role() = 'admin'
  );

-- ============================================
-- 4. FIX profiles_delete: same pattern
-- ============================================
DROP POLICY IF EXISTS profiles_delete ON profiles;
CREATE POLICY profiles_delete ON profiles
  FOR DELETE USING (
    user_role() = 'admin'
  );

-- ============================================
-- 5. Reload PostgREST schema cache
-- ============================================
SELECT pg_notify('pgrst', 'reload schema');
