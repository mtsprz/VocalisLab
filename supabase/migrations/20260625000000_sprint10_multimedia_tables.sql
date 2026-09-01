-- Sprint 10: Módulo de Materiales Multimedia
-- Tablas para assets generados y analytics de materiales
-- Idempotente: puede ejecutarse múltiples veces sin errores

-- ============================================
-- 1. TABLA: material_analytics
-- Tracking de uso de materiales
-- ============================================
CREATE TABLE IF NOT EXISTS material_analytics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  material_id uuid REFERENCES materials(id) ON DELETE CASCADE,
  event_type text NOT NULL CHECK (event_type IN (
    'used_in_guide', 'suggestion_accepted', 'suggestion_discarded',
    'material_archived', 'suggestion_offered', 'created', 'viewed',
    'downloaded', 'shared', 'generated_by_ai'
  )),
  guide_id text,
  event_context text CHECK (event_context IN (
    'suggestion', 'enrichment', 'manual_add', 'archive', 'system',
    'multimedia_creator', 'ai_generation'
  )),
  user_id uuid REFERENCES profiles(id),
  patient_id text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE material_analytics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS material_analytics_select ON material_analytics;
CREATE POLICY material_analytics_select ON material_analytics
  FOR SELECT USING (user_role() = 'admin' OR user_role() = 'supervisor' OR user_role() = 'profesional');

DROP POLICY IF EXISTS material_analytics_insert ON material_analytics;
CREATE POLICY material_analytics_insert ON material_analytics
  FOR INSERT WITH CHECK (user_role() IN ('admin', 'profesional', 'supervisor'));

CREATE INDEX IF NOT EXISTS idx_material_analytics_material_id ON material_analytics(material_id);
CREATE INDEX IF NOT EXISTS idx_material_analytics_event_type ON material_analytics(event_type);
CREATE INDEX IF NOT EXISTS idx_material_analytics_created_at ON material_analytics(created_at);

-- ============================================
-- 2. TABLA: material_assets
-- Assets multimedia generados por IA
-- ============================================
CREATE TABLE IF NOT EXISTS material_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  material_id uuid REFERENCES materials(id) ON DELETE CASCADE,
  asset_type text NOT NULL CHECK (asset_type IN (
    'image', 'activity_image', 'infographic', 'social_post',
    'worksheet', 'exercise_card', 'flashcard'
  )),
  title text NOT NULL,
  description text,
  prompt_used text,
  generation_model text,
  file_url text,
  file_path text,
  file_size integer,
  mime_type text,
  width integer,
  height integer,
  metadata jsonb DEFAULT '{}'::jsonb,
  status text DEFAULT 'active' CHECK (status IN ('active', 'archived', 'processing', 'failed')),
  error_message text,
  created_by uuid REFERENCES profiles(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE material_assets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS material_assets_select ON material_assets;
CREATE POLICY material_assets_select ON material_assets
  FOR SELECT USING (true);

DROP POLICY IF EXISTS material_assets_insert ON material_assets;
CREATE POLICY material_assets_insert ON material_assets
  FOR INSERT WITH CHECK (user_role() IN ('admin', 'profesional', 'supervisor'));

DROP POLICY IF EXISTS material_assets_update ON material_assets;
CREATE POLICY material_assets_update ON material_assets
  FOR UPDATE USING (created_by = auth.uid() OR user_role() = 'admin');

DROP POLICY IF EXISTS material_assets_delete ON material_assets;
CREATE POLICY material_assets_delete ON material_assets
  FOR DELETE USING (created_by = auth.uid() OR user_role() = 'admin');

CREATE INDEX IF NOT EXISTS idx_material_assets_material_id ON material_assets(material_id);
CREATE INDEX IF NOT EXISTS idx_material_assets_asset_type ON material_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_material_assets_status ON material_assets(status);

-- ============================================
-- 3. TABLA: multimedia_templates
-- Plantillas predefinidas para actividades
-- ============================================
CREATE TABLE IF NOT EXISTS multimedia_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  category text NOT NULL CHECK (category IN (
    'activity', 'infographic', 'social', 'worksheet', 'flashcard'
  )),
  clinical_area text,
  template_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  prompt_template text,
  example_output_url text,
  is_active boolean DEFAULT true,
  created_by uuid REFERENCES profiles(id),
  created_at timestamptz DEFAULT now()
);

ALTER TABLE multimedia_templates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS multimedia_templates_select ON multimedia_templates;
CREATE POLICY multimedia_templates_select ON multimedia_templates
  FOR SELECT USING (true);

DROP POLICY IF EXISTS multimedia_templates_insert ON multimedia_templates;
CREATE POLICY multimedia_templates_insert ON multimedia_templates
  FOR INSERT WITH CHECK (user_role() = 'admin');

DROP POLICY IF EXISTS multimedia_templates_update ON multimedia_templates;
CREATE POLICY multimedia_templates_update ON multimedia_templates
  FOR UPDATE USING (user_role() = 'admin');

DROP POLICY IF EXISTS multimedia_templates_delete ON multimedia_templates;
CREATE POLICY multimedia_templates_delete ON multimedia_templates
  FOR DELETE USING (user_role() = 'admin');

-- ============================================
-- 4. Insertar plantillas por defecto (solo si no existen)
-- ============================================
INSERT INTO multimedia_templates (name, description, category, clinical_area, template_config, prompt_template)
SELECT * FROM (VALUES
  ('Actividad de Lenguaje - Animales', 'Tarjeta con animal y nombre para estimulación del lenguaje', 'activity', 'Lenguaje',
   '{"layout": "single_image", "style": "child_friendly", "colors": ["#3B82F6", "#10B981"], "fontSize": "large"}'::jsonb,
   'Genera una imagen colorida y amigable de un/a [ANIMAL] para una actividad de logopedia infantil. Estilo cartoon, fondo blanco, colores vibrantes. El nombre del animal debe aparecer en letras grandes y claras.'),
  ('Infografía - Ejicios de Deglución', 'Infografía con ejercicios de deglución paso a paso', 'infographic', 'Deglución',
   '{"layout": "step_by_step", "style": "professional", "colors": ["#6366F1", "#8B5CF6"], "steps": 4}'::jsonb,
   'Crea una infografía profesional con [N] ejercicios de deglución para pacientes con disfagia. Estilo limpio, pasos numerados, iconos claros.'),
  ('Post para Redes - Consejo Fonoaudiológico', 'Publicación para redes sociales con consejo clínico', 'social', NULL,
   '{"layout": "square", "style": "modern", "colors": ["#F59E0B", "#EF4444"], "branding": true}'::jsonb,
   'Diseña un post cuadrado para Instagram con el siguiente consejo fonoaudiológico: [CONSEJO]. Estilo moderno, colores llamativos, texto legible.'),
  ('Tarjeta de Ejercicio - Vocal', 'Tarjeta con vocal y ejemplos para ejercitación', 'activity', 'Habla',
   '{"layout": "flashcard", "style": "playful", "colors": ["#EC4899", "#8B5CF6"]}'::jsonb,
   'Crea una tarjeta de ejercicio para practicing la vocal [VOCAL]. Incluye la letra grande, 3 palabras que contengan esa vocal, y una ilustración simple. Estilo lúdico infantil.'),
  ('Guía para Padres - Señales de Alerta', 'Infografía con señales de alerta del desarrollo del lenguaje', 'infographic', 'Lenguaje',
   '{"layout": "checklist", "style": "clinical", "colors": ["#059669", "#0D9488"]}'::jsonb,
   'Genera una guía para padres con las señales de alerta del desarrollo del lenguaje en niños de 0-5 años. Estilo clínico pero accesible, formato de checklist.')
) AS v(name, description, category, clinical_area, template_config, prompt_template)
WHERE NOT EXISTS (SELECT 1 FROM multimedia_templates WHERE name = v.name);
