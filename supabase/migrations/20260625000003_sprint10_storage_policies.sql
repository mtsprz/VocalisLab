-- Sprint 10: Storage policies para bucket 'materials'
-- Aislamiento por consultorio en uploads de imágenes
-- Idempotente: seguro de re-ejecutar

-- ============================================
-- 1. POLITICA: Upload
-- ============================================
DROP POLICY IF EXISTS "materials_insert_own_consultorio" ON storage.objects;
CREATE POLICY "materials_insert_own_consultorio"
ON storage.objects
FOR INSERT
WITH CHECK (
  bucket_id = 'materials'
  AND (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    OR
    (
      auth.uid() IS NOT NULL
      AND (storage.foldername(name))[1] = ANY(
        SELECT UNNEST(consultorio_ids) FROM profiles WHERE id = auth.uid()
      )
    )
  )
);

-- ============================================
-- 2. POLITICA: Select
-- ============================================
DROP POLICY IF EXISTS "materials_select_own_consultorio" ON storage.objects;
CREATE POLICY "materials_select_own_consultorio"
ON storage.objects
FOR SELECT
USING (
  bucket_id = 'materials'
  AND (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    OR
    (
      auth.uid() IS NOT NULL
      AND (storage.foldername(name))[1] = ANY(
        SELECT UNNEST(consultorio_ids) FROM profiles WHERE id = auth.uid()
      )
    )
  )
);

-- ============================================
-- 3. POLITICA: Delete
-- ============================================
DROP POLICY IF EXISTS "materials_delete_own_consultorio" ON storage.objects;
CREATE POLICY "materials_delete_own_consultorio"
ON storage.objects
FOR DELETE
USING (
  bucket_id = 'materials'
  AND (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    OR
    (
      auth.uid() IS NOT NULL
      AND (storage.foldername(name))[1] = ANY(
        SELECT UNNEST(consultorio_ids) FROM profiles WHERE id = auth.uid()
      )
    )
  )
);

-- ============================================
-- 4. POLITICA: Update
-- ============================================
DROP POLICY IF EXISTS "materials_update_own_consultorio" ON storage.objects;
CREATE POLICY "materials_update_own_consultorio"
ON storage.objects
FOR UPDATE
USING (
  bucket_id = 'materials'
  AND (
    (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    OR
    (
      auth.uid() IS NOT NULL
      AND (storage.foldername(name))[1] = ANY(
        SELECT UNNEST(consultorio_ids) FROM profiles WHERE id = auth.uid()
      )
    )
  )
);
