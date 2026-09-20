-- VocalisLab — Banco de imágenes v2: galería ordenada con epígrafes.
-- Ejecutar UNA vez en el SQL Editor de Supabase, DESPUÉS de banco_imagenes.sql
-- (si ya lo ejecutaste; si no, este archivo solo también alcanza: es autónomo).
-- Idempotente: se puede correr varias veces sin romper nada.
-- Las asignaciones existentes migran como imagen única (orden 0).

CREATE TABLE IF NOT EXISTS ejercicio_imagenes (
    exercise_id TEXT,
    image_url TEXT NOT NULL,
    storage_path TEXT,
    prompt TEXT,
    proveedor TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE ejercicio_imagenes ADD COLUMN IF NOT EXISTS orden INT DEFAULT 0;
ALTER TABLE ejercicio_imagenes ADD COLUMN IF NOT EXISTS epigrafe TEXT DEFAULT '';

-- Normalizar nulos heredados antes de la PK compuesta
UPDATE ejercicio_imagenes SET orden = 0 WHERE orden IS NULL;
UPDATE ejercicio_imagenes SET epigrafe = '' WHERE epigrafe IS NULL;

-- Pasar de PK (exercise_id) a PK (exercise_id, orden)
ALTER TABLE ejercicio_imagenes DROP CONSTRAINT IF EXISTS ejercicio_imagenes_pkey;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ejercicio_imagenes_ex_orden_pkey') THEN
        ALTER TABLE ejercicio_imagenes ADD CONSTRAINT ejercicio_imagenes_ex_orden_pkey PRIMARY KEY (exercise_id, orden);
    END IF;
END $$;

ALTER TABLE ejercicio_imagenes ENABLE ROW LEVEL SECURITY;

INSERT INTO storage.buckets (id, name, public)
VALUES ('ejercicios', 'ejercicios', true)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "App backend full access" ON ejercicio_imagenes;
CREATE POLICY "App backend full access" ON ejercicio_imagenes
FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "App backend storage" ON storage.objects;
CREATE POLICY "App backend storage" ON storage.objects
FOR ALL TO anon, authenticated USING (bucket_id = 'ejercicios') WITH CHECK (bucket_id = 'ejercicios');

DROP POLICY IF EXISTS "Public read ejercicios" ON storage.objects;
CREATE POLICY "Public read ejercicios" ON storage.objects
FOR SELECT TO anon, authenticated USING (bucket_id = 'ejercicios');
