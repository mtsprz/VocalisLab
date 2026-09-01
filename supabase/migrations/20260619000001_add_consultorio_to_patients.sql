-- ============================================================
-- Migration: Add consultorio field to patients
-- Date: 2026-06-19
-- ============================================================

-- Add consultorio column (text, nullable for existing patients)
ALTER TABLE patients ADD COLUMN IF NOT EXISTS consultorio text;

-- Optional: set a default for existing patients
-- UPDATE patients SET consultorio = 'Privado' WHERE consultorio IS NULL;
