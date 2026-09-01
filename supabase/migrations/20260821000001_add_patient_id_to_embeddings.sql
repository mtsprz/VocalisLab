-- Add patient_id to source_embeddings for patient-specific document retrieval
ALTER TABLE source_embeddings ADD COLUMN IF NOT EXISTS patient_id UUID REFERENCES patients(id) ON DELETE SET NULL;

-- Create index for fast patient-specific searches
CREATE INDEX IF NOT EXISTS idx_source_embeddings_patient ON source_embeddings(patient_id);

-- Update match_source_embeddings to support patient-specific filtering
CREATE OR REPLACE FUNCTION match_source_embeddings (
  query_embedding extensions.vector(768),
  match_threshold float DEFAULT 0.4,
  match_count int DEFAULT 5,
  filter_patient_id uuid DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  content text,
  similarity float,
  source_title text,
  page_number int,
  patient_id uuid
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    se.id,
    se.content,
    1 - (se.embedding <=> query_embedding) AS similarity,
    cs.title AS source_title,
    se.page_number,
    se.patient_id
  FROM source_embeddings se
  JOIN clinical_sources cs ON se.source_id = cs.id
  WHERE
    (filter_patient_id IS NULL OR se.patient_id = filter_patient_id)
    AND 1 - (se.embedding <=> query_embedding) > match_threshold
  ORDER BY se.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
