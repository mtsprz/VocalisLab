-- Fix: Bucket materials + CHECK constraints para multimedia
-- Resuelve: pictogram/pictogram_sequence no aceptados por DB

-- ============================================
-- 1. CREAR BUCKET 'materials' en Supabase Storage
-- ============================================
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'materials',
  'materials',
  false,
  10485760,  -- 10MB max
  ARRAY['image/png', 'image/jpeg', 'image/webp', 'application/pdf']
)
ON CONFLICT (id) DO NOTHING;

-- ============================================
-- 2. FIX CHECK CONSTRAINT: material_assets.asset_type
-- Agrega 'pictogram' y 'pictogram_sequence'
-- ============================================
ALTER TABLE material_assets DROP CONSTRAINT IF EXISTS material_assets_asset_type_check;
ALTER TABLE material_assets ADD CONSTRAINT material_assets_asset_type_check
  CHECK (asset_type IN (
    'image', 'activity_image', 'infographic', 'social_post',
    'worksheet', 'exercise_card', 'flashcard',
    'pictogram', 'pictogram_sequence'
  ));

-- ============================================
-- 3. FIX CHECK CONSTRAINT: multimedia_templates.category
-- Agrega 'pictogram'
-- ============================================
ALTER TABLE multimedia_templates DROP CONSTRAINT IF EXISTS multimedia_templates_category_check;
ALTER TABLE multimedia_templates ADD CONSTRAINT multimedia_templates_category_check
  CHECK (category IN (
    'activity', 'infographic', 'social', 'worksheet', 'flashcard', 'pictogram'
  ));

-- ============================================
-- 4. POLITICAS STORAGE simplificadas (ya existentes, re-crear por si acaso)
-- ============================================
DROP POLICY IF EXISTS "materials_insert_auth" ON storage.objects;
DROP POLICY IF EXISTS "materials_select_auth" ON storage.objects;
DROP POLICY IF EXISTS "materials_delete_auth" ON storage.objects;
DROP POLICY IF EXISTS "materials_update_auth" ON storage.objects;

CREATE POLICY "materials_insert_auth"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'materials' AND auth.uid() IS NOT NULL);

CREATE POLICY "materials_select_auth"
ON storage.objects FOR SELECT
USING (bucket_id = 'materials' AND auth.uid() IS NOT NULL);

CREATE POLICY "materials_delete_auth"
ON storage.objects FOR DELETE
USING (bucket_id = 'materials' AND auth.uid() IS NOT NULL);

CREATE POLICY "materials_update_auth"
ON storage.objects FOR UPDATE
USING (bucket_id = 'materials' AND auth.uid() IS NOT NULL);
