-- VocalisLab Database & Storage Schema for Supabase
-- Ejecutar en Supabase SQL Editor

-- 1. Tabla 'pacientes'
CREATE TABLE IF NOT EXISTS pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre TEXT NOT NULL,
    dni TEXT,
    edad INT,
    genero TEXT,
    email TEXT,
    telefono TEXT,
    motivo_consulta TEXT,
    derivador TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Tabla 'evaluaciones_vocales'
CREATE TABLE IF NOT EXISTS evaluaciones_vocales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    nombre_paciente TEXT NOT NULL,
    dni TEXT,
    edad INT,
    sexo TEXT,
    motivo TEXT,
    derivador TEXT,
    f0_mean FLOAT,
    jitter_local FLOAT,
    shimmer_local FLOAT,
    hnr FLOAT,
    cpps FLOAT,
    avqi FLOAT,
    grbas TEXT,
    rasati TEXT,
    tmf FLOAT,
    sintesis_ia TEXT,
    audio_sustained_url TEXT,
    audio_reading_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Habilitar RLS
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluaciones_vocales ENABLE ROW LEVEL SECURITY;

-- 4. Politicas RLS (acceso publico para prototipo)
CREATE POLICY "public_read_pacientes" ON pacientes FOR SELECT USING (true);
CREATE POLICY "public_insert_pacientes" ON pacientes FOR INSERT WITH CHECK (true);
CREATE POLICY "public_update_pacientes" ON pacientes FOR UPDATE USING (true);
CREATE POLICY "public_delete_pacientes" ON pacientes FOR DELETE USING (true);

CREATE POLICY "public_read_evaluaciones" ON evaluaciones_vocales FOR SELECT USING (true);
CREATE POLICY "public_insert_evaluaciones" ON evaluaciones_vocales FOR INSERT WITH CHECK (true);
CREATE POLICY "public_update_evaluaciones" ON evaluaciones_vocales FOR UPDATE USING (true);
CREATE POLICY "public_delete_evaluaciones" ON evaluaciones_vocales FOR DELETE USING (true);

-- 5. GRANT para que los roles anon/authenticated puedan acceder via Data API
GRANT ALL ON pacientes TO anon;
GRANT ALL ON pacientes TO authenticated;
GRANT ALL ON evaluaciones_vocales TO anon;
GRANT ALL ON evaluaciones_vocales TO authenticated;

-- 6. Storage Bucket
INSERT INTO storage.buckets (id, name, public)
VALUES ('muestras-voz', 'muestras-voz', true)
ON CONFLICT (id) DO NOTHING;

-- 7. Storage Policies
CREATE POLICY "public_select_muestras" ON storage.objects
    FOR SELECT USING (bucket_id = 'muestras-voz');

CREATE POLICY "public_insert_muestras" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'muestras-voz');

CREATE POLICY "public_delete_muestras" ON storage.objects
    FOR DELETE USING (bucket_id = 'muestras-voz');

-- 8. Index para busquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_evaluaciones_paciente_id ON evaluaciones_vocales(paciente_id);
CREATE INDEX IF NOT EXISTS idx_evaluaciones_created_at ON evaluaciones_vocales(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pacientes_dni ON pacientes(dni);
