-- VocalisLab — Informes ORL del paciente (OCR + banco de datos clínico)
-- Guarda los análisis que envía el ORL: archivo, texto extraído por IA,
-- datos estructurados y estado de revisión. La IA los usa vía anamnesis.
-- Idempotente: puede ejecutarse múltiples veces sin errores.

-- ============================================
-- 1. TABLA: informes_orl
-- ============================================
CREATE TABLE IF NOT EXISTS informes_orl (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  paciente_id uuid REFERENCES pacientes(id) ON DELETE CASCADE,
  fecha timestamptz DEFAULT now(),
  titulo text DEFAULT 'Informe ORL',
  tipo_informe text DEFAULT 'ORL'
    CHECK (tipo_informe IN ('ORL', 'audiometria', 'laringoscopia', 'estroboscopia', 'otro')),

  -- Archivo original
  archivo_url text,
  archivo_nombre text,
  mime text,

  -- Texto y datos extraídos por IA
  texto_extraido text,
  texto_corregido text,
  datos_estructurados jsonb DEFAULT '{}'::jsonb,
  diagnostico_principal text,
  metodo_exploracion text,
  profesional_orl text,
  fecha_informe text,

  -- Trazabilidad IA
  confianza text DEFAULT 'media' CHECK (confianza IN ('alta', 'media', 'baja')),
  modelo_ia text,
  observaciones_ia text,

  -- Flujo de revisión por el profesional
  estado text DEFAULT 'pendiente_revision'
    CHECK (estado IN ('pendiente_revision', 'validado', 'descartado')),

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_informes_orl_paciente ON informes_orl(paciente_id);
CREATE INDEX IF NOT EXISTS idx_informes_orl_estado ON informes_orl(estado);
CREATE INDEX IF NOT EXISTS idx_informes_orl_fecha ON informes_orl(fecha DESC);

-- ============================================
-- 2. RLS (mismo patrón que el resto del schema v2)
-- ============================================
ALTER TABLE informes_orl ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow access to authenticated users" ON informes_orl;
CREATE POLICY "Allow access to authenticated users" ON informes_orl
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "App backend full access" ON informes_orl;
CREATE POLICY "App backend full access" ON informes_orl
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- ============================================
-- 3. updated_at automático
-- ============================================
CREATE OR REPLACE FUNCTION update_informes_orl_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_informes_orl_updated_at ON informes_orl;
CREATE TRIGGER trigger_informes_orl_updated_at
  BEFORE UPDATE ON informes_orl
  FOR EACH ROW EXECUTE FUNCTION update_informes_orl_updated_at();

-- ============================================
-- 4. Storage bucket para los archivos originales
-- ============================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('informes-orl', 'informes-orl', false)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "App backend storage informes-orl" ON storage.objects;
CREATE POLICY "App backend storage informes-orl" ON storage.objects
  FOR ALL TO anon, authenticated
  USING (bucket_id = 'informes-orl')
  WITH CHECK (bucket_id = 'informes-orl');
