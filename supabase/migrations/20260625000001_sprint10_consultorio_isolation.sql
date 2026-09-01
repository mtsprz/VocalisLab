-- Sprint 10: Aislamiento por consultorio en material_assets
-- Modelo híbrido: templates globales, assets por consultorio
-- Ejecutar en Supabase SQL Editor

-- ============================================
-- 1. AGREGAR COLUMNA consultorio_id
-- ============================================
ALTER TABLE material_assets
  ADD COLUMN IF NOT EXISTS consultorio_id text REFERENCES consultorios(id);

-- ============================================
-- 2. BACKFILL SEGURO
-- Registros existentes sin consultorio → NULL (globales, no accesibles por RLS)
-- Si hay solo 1 consultorio en el sistema, se puede backfill automático
-- ============================================

-- Opción A: Backfill automático solo si hay UN consultorio activo
DO $$
DECLARE
  single_consultorio text;
  count_consultorios bigint;
BEGIN
  SELECT COUNT(*) INTO count_consultorios FROM consultorios;

  IF count_consultorios = 1 THEN
    SELECT id INTO single_consultorio FROM consultorios LIMIT 1;
    UPDATE material_assets
      SET consultorio_id = single_consultorio
      WHERE consultorio_id IS NULL;
    RAISE NOTICE 'Backfilled % assets to consultorio %', FOUND, single_consultorio;
  ELSE
    RAISE NOTICE 'Multiple consultorios exist (%). Manual backfill needed.', count_consultorios;
  END IF;
END $$;

-- Opción B: Backfill manual (descomentar si es necesario)
-- UPDATE material_assets SET consultorio_id = 'ID_DEL_CONSULTORIO' WHERE consultorio_id IS NULL;

-- ============================================
-- 3. ÍNDICE para queries por consultorio
-- ============================================
CREATE INDEX IF NOT EXISTS idx_material_assets_consultorio_id
  ON material_assets(consultorio_id);

-- ============================================
-- 4. REEMPLAZAR POLÍTICAS RLS
-- ============================================

-- Dropear políticas viejas (sin consultorio_id)
DROP POLICY IF EXISTS material_assets_select ON material_assets;
DROP POLICY IF EXISTS material_assets_insert ON material_assets;
DROP POLICY IF EXISTS material_assets_update ON material_assets;
DROP POLICY IF EXISTS material_assets_delete ON material_assets;

-- SELECT: usuario ve assets de SU consultorio + admin ve todo
CREATE POLICY material_assets_select ON material_assets
  FOR SELECT USING (
    consultorio_id = ANY(user_consultorios())
    OR user_role() = 'admin'
  );

-- INSERT: usuario solo puede crear en SU consultorio
CREATE POLICY material_assets_insert ON material_assets
  FOR INSERT WITH CHECK (
    consultorio_id = ANY(user_consultorios())
    OR user_role() = 'admin'
  );

-- UPDATE: owner o admin, solo en su consultorio
CREATE POLICY material_assets_update ON material_assets
  FOR UPDATE USING (
    (created_by = auth.uid() AND consultorio_id = ANY(user_consultorios()))
    OR user_role() = 'admin'
  );

-- DELETE: admin o owner en su consultorio
CREATE POLICY material_assets_delete ON material_assets
  FOR DELETE USING (
    (created_by = auth.uid() AND consultorio_id = ANY(user_consultorios()))
    OR user_role() = 'admin'
  );

-- ============================================
-- 5. material_analytics: hereda aislamiento
-- Los analytics apuntan a material_id (FK a materials)
-- Pero los assets se filtran por consultorio
-- La política de analytics se mantiene abierta
-- (los eventos son del usuario, no del consultorio)
-- ============================================
-- No se modifica material_analytics: los eventos se registran
-- por usuario, y el filtrado por consultorio se hace
-- en el frontend al consultar assets.

-- ============================================
-- 6. VERIFICACIÓN
-- ============================================
-- Ejecutar para confirmar:
-- SELECT id, title, consultorio_id, status FROM material_assets LIMIT 10;
-- SELECT policyname, qual FROM pg_policies WHERE tablename = 'material_assets';
