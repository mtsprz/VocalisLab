-- Sprint 8: QA End-to-End
-- Fase 1: Fix RLS policies for clinical_history tables
-- Fase 2: Server-side validation triggers

-- ============================================
-- FASE 1: FIX RLS POLICIES
-- ============================================

-- 1a. Drop existing broken policies on clinical_history_templates
DROP POLICY IF EXISTS cht_select ON clinical_history_templates;
DROP POLICY IF EXISTS cht_insert ON clinical_history_templates;
DROP POLICY IF EXISTS cht_update ON clinical_history_templates;
DROP POLICY IF EXISTS cht_delete ON clinical_history_templates;

-- 1b. Recreate with correct column name (clinic_id, not consultorio_id)
CREATE POLICY cht_select ON clinical_history_templates
  FOR SELECT USING (
    clinic_id = ANY(user_consultorios()) OR user_role() = 'admin'
  );

CREATE POLICY cht_insert ON clinical_history_templates
  FOR INSERT WITH CHECK (user_role() = 'admin');

CREATE POLICY cht_update ON clinical_history_templates
  FOR UPDATE USING (user_role() = 'admin');

CREATE POLICY cht_delete ON clinical_history_templates
  FOR DELETE USING (user_role() = 'admin');

-- 1c. Drop existing broken policies on clinical_history_records
DROP POLICY IF EXISTS chr_select ON clinical_history_records;
DROP POLICY IF EXISTS chr_insert ON clinical_history_records;
DROP POLICY IF EXISTS chr_update ON clinical_history_records;
DROP POLICY IF EXISTS chr_delete ON clinical_history_records;

-- 1d. Recreate with fixed syntax and proper scoping
CREATE POLICY chr_select ON clinical_history_records
  FOR SELECT USING (
    is_patient_accessible(patient_id)
    AND (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin')
  );

CREATE POLICY chr_insert ON clinical_history_records
  FOR INSERT WITH CHECK (
    is_patient_accessible(patient_id)
    AND (clinic_id = ANY(user_consultorios()) OR user_role() = 'admin')
  );

CREATE POLICY chr_update ON clinical_history_records
  FOR UPDATE USING (
    is_patient_accessible(patient_id)
    AND (
      (author_id = auth.uid() AND status != 'approved')
      OR (user_role() IN ('admin', 'supervisor'))
    )
  )
  WITH CHECK (
    (status = 'approved' AND user_role() IN ('admin', 'supervisor'))
    OR (status != 'approved')
  );

CREATE POLICY chr_delete ON clinical_history_records
  FOR DELETE USING (user_role() = 'admin');

-- ============================================
-- FASE 2: SERVER-SIDE VALIDATION TRIGGERS
-- ============================================

-- 2a. Function: validate required fields before approve
CREATE OR REPLACE FUNCTION validate_clinical_history_approval()
RETURNS TRIGGER AS $$
DECLARE
  schema_json JSONB;
  section JSONB;
  field JSONB;
  field_key TEXT;
  base_val TEXT;
  final_val TEXT;
  missing_fields TEXT[] := '{}';
BEGIN
  -- Only validate on status change to 'approved'
  IF NEW.status = 'approved' AND (OLD.status IS DISTINCT FROM 'approved') THEN
    -- Get the template schema
    SELECT t.schema_json INTO schema_json
    FROM clinical_history_templates t
    WHERE t.id = NEW.template_id;

    IF schema_json IS NULL THEN
      RAISE EXCEPTION 'Template not found for clinical history record';
    END IF;

    -- Check each required field
    FOR section IN SELECT * FROM jsonb_array_elements(schema_json)
    LOOP
      FOR field IN SELECT * FROM jsonb_array_elements(section->'fields')
      LOOP
        IF (field->>'required')::boolean = true THEN
          field_key := section->'section_id' || '__' || field->'id';
          base_val := NEW.base_data_json->>field_key;
          final_val := NEW.final_data_json->>field_key;

          -- Field must have content in either base or final data
          IF (base_val IS NULL OR trim(base_val) = '')
             AND (final_val IS NULL OR trim(final_val) = '') THEN
            missing_fields := array_append(missing_fields, field->>'label');
          END IF;
        END IF;
      END LOOP;
    END LOOP;

    -- Block approval if required fields are missing
    IF array_length(missing_fields, 1) > 0 THEN
      RAISE EXCEPTION 'Cannot approve: required fields are empty: %',
        array_to_string(missing_fields, ', ');
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2b. Attach trigger to clinical_history_records
DROP TRIGGER IF EXISTS trg_validate_approval ON clinical_history_records;
CREATE TRIGGER trg_validate_approval
  BEFORE UPDATE OF status ON clinical_history_records
  FOR EACH ROW
  EXECUTE FUNCTION validate_clinical_history_approval();

-- 2c. Function: validate required sections in anamnesis before finalizing
CREATE OR REPLACE FUNCTION validate_anamnesis_completion()
RETURNS TRIGGER AS $$
DECLARE
  motivo_val TEXT;
BEGIN
  -- Only validate when status changes to 'final'
  IF NEW.status = 'final' AND (OLD.status IS DISTINCT FROM 'final') THEN
    -- motivo_principal is the only hard-required field in anamnesis
    motivo_val := NEW.sections->'motivo_consulta'->>'motivo_principal';

    IF motivo_val IS NULL OR trim(motivo_val) = '' THEN
      RAISE EXCEPTION 'Cannot finalize anamnesis: "Motivo de consulta" is required';
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2d. Attach trigger to patient_anamnesis
DROP TRIGGER IF EXISTS trg_validate_anamnesis ON patient_anamnesis;
CREATE TRIGGER trg_validate_anamnesis
  BEFORE UPDATE OF status ON patient_anamnesis
  FOR EACH ROW
  EXECUTE FUNCTION validate_anamnesis_completion();

-- ============================================
-- NOTES:
-- Run this migration AFTER 20260622000003_clinical_history_setup.sql
-- The template schema_json is iterated server-side to enforce
-- required fields even if the frontend is bypassed.
-- ============================================
