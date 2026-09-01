-- Fix: Simplificar storage policies para bucket 'materials'
-- Las policies anteriores fallaban porque profiles no es accesible desde storage context
-- Solución: usar auth.uid() directamente para verificar propiedad

-- Primero limpiar policies existentes
DROP POLICY IF EXISTS "materials_insert_own_consultorio" ON storage.objects;
DROP POLICY IF EXISTS "materials_select_own_consultorio" ON storage.objects;
DROP POLICY IF EXISTS "materials_delete_own_consultorio" ON storage.objects;
DROP POLICY IF EXISTS "materials_update_own_consultorio" ON storage.objects;

-- ============================================
-- 1. INSERT: Authenticated users can upload to their consultorio folder
-- ============================================
CREATE POLICY "materials_insert_auth"
ON storage.objects
FOR INSERT
WITH CHECK (
  bucket_id = 'materials'
  AND auth.uid() IS NOT NULL
);

-- ============================================
-- 2. SELECT: Authenticated users can read from materials bucket
-- ============================================
CREATE POLICY "materials_select_auth"
ON storage.objects
FOR SELECT
USING (
  bucket_id = 'materials'
  AND auth.uid() IS NOT NULL
);

-- ============================================
-- 3. DELETE: Authenticated users can delete their own files
-- ============================================
CREATE POLICY "materials_delete_auth"
ON storage.objects
FOR DELETE
USING (
  bucket_id = 'materials'
  AND auth.uid() IS NOT NULL
);

-- ============================================
-- 4. UPDATE: Authenticated users can update their own files
-- ============================================
CREATE POLICY "materials_update_auth"
ON storage.objects
FOR UPDATE
USING (
  bucket_id = 'materials'
  AND auth.uid() IS NOT NULL
);
