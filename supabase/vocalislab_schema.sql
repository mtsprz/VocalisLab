-- VocalisLab Database & Storage Schema for Supabase

-- 1. Table 'pacientes'
CREATE TABLE IF NOT EXISTS pacientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre TEXT NOT NULL,
    edad INT,
    genero TEXT,
    email TEXT,
    telefono TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Table 'evaluaciones_vocales'
CREATE TABLE IF NOT EXISTS evaluaciones_vocales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paciente_id UUID REFERENCES pacientes(id) ON DELETE CASCADE,
    f0_mean FLOAT,
    jitter_local FLOAT,
    shimmer_local FLOAT,
    hnr FLOAT,
    cpps FLOAT,
    avqi FLOAT,
    grbas TEXT,
    rasati TEXT,
    tmf FLOAT,
    synthesis_text TEXT,
    audio_sustained_url TEXT,
    audio_reading_url TEXT,
    pdf_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Enable Row Level Security (RLS)
ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluaciones_vocales ENABLE ROW LEVEL SECURITY;

-- Allow public access for prototype development (or secure with auth as needed)
CREATE POLICY "Allow public access to pacientes" ON pacientes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow public access to evaluaciones_vocales" ON evaluaciones_vocales FOR ALL USING (true) WITH CHECK (true);

-- 4. Storage Bucket 'muestras-voz'
INSERT INTO storage.buckets (id, name, public) 
VALUES ('muestras-voz', 'muestras-voz', true)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for bucket 'muestras-voz'
CREATE POLICY "Public Access to muestras-voz"
ON storage.objects FOR SELECT
USING (bucket_id = 'muestras-voz');

CREATE POLICY "Public Upload to muestras-voz"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'muestras-voz');
