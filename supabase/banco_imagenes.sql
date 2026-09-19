-- VocalisLab — Banco de imágenes de ejercicios (idempotente).
-- Ejecutar una vez en el SQL Editor de Supabase si la DB no viene del schema v2.
-- Bucket público "ejercicios" + tabla ejercicio_imagenes (exercise_id -> imagen).

CREATE TABLE IF NOT EXISTS ejercicio_imagenes (
    exercise_id TEXT PRIMARY KEY,
    image_url TEXT NOT NULL,
    storage_path TEXT,
    prompt TEXT,
    proveedor TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
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

-- Lectura pública de las ilustraciones (el PDF las sirve por URL pública)
DROP POLICY IF EXISTS "Public read ejercicios" ON storage.objects;
CREATE POLICY "Public read ejercicios" ON storage.objects
FOR SELECT TO anon, authenticated USING (bucket_id = 'ejercicios');
