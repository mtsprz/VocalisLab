-- Enable pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Table for source documents
CREATE TABLE IF NOT EXISTS clinical_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  validated_by TEXT,
  source_url TEXT,
  page_count INTEGER DEFAULT 1,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for chunks (RAG)
CREATE TABLE IF NOT EXISTS source_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES clinical_sources(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  embedding extensions.vector(768),

  -- Metadata per chunk
  page_number INTEGER,
  section_title TEXT,
  tags TEXT[],
  confidence_score FLOAT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast semantic search (HNSW works without minimum row count)
CREATE INDEX IF NOT EXISTS idx_source_embeddings_embedding
  ON source_embeddings USING hnsw (embedding extensions.vector_cosine_ops);

-- Function for vector similarity search
CREATE OR REPLACE FUNCTION match_source_embeddings (
  query_embedding extensions.vector(768),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id UUID,
  content TEXT,
  similarity float,
  source_title TEXT,
  page_number INTEGER
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
    se.page_number
  FROM source_embeddings se
  JOIN clinical_sources cs ON se.source_id = cs.id
  WHERE 1 - (se.embedding <=> query_embedding) > match_threshold
  ORDER BY se.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Enable RLS
ALTER TABLE clinical_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_embeddings ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users full access
CREATE POLICY "Authenticated users can manage clinical_sources"
  ON clinical_sources FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Authenticated users can manage source_embeddings"
  ON source_embeddings FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);
