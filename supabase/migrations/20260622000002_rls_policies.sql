-- Fase 3: Replace all open RLS policies with scoped policies
-- Idempotent: safe to re-run

-- ============================================
-- HELPER: check if patient is accessible
-- ============================================
CREATE OR REPLACE FUNCTION is_patient_accessible(patient_uuid uuid)
RETURNS boolean AS $$
  SELECT EXISTS (
    SELECT 1 FROM patients
    WHERE id = patient_uuid
      AND (
        owner_id = auth.uid()
        OR consultorio_id = ANY(user_consultorios())
        OR user_role() = 'admin'
        OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
      )
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ============================================
-- 1. PATIENTS
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'patients') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON patients;
    DROP POLICY IF EXISTS patients_select ON patients;
    DROP POLICY IF EXISTS patients_insert ON patients;
    DROP POLICY IF EXISTS patients_update ON patients;
    DROP POLICY IF EXISTS patients_delete ON patients;

    CREATE POLICY patients_select ON patients FOR SELECT USING (
      owner_id = auth.uid() OR consultorio_id = ANY(user_consultorios()) OR user_role() = 'admin'
      OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
    );
    CREATE POLICY patients_insert ON patients FOR INSERT WITH CHECK (
      owner_id = auth.uid() OR consultorio_id = ANY(user_consultorios()) OR user_role() = 'admin'
      OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
    );
    CREATE POLICY patients_update ON patients FOR UPDATE USING (
      owner_id = auth.uid() OR user_role() = 'admin'
    );
    CREATE POLICY patients_delete ON patients FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 2. SESSIONS
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'sessions') THEN
    DROP POLICY IF EXISTS "Enable all access" ON sessions;
    DROP POLICY IF EXISTS sessions_select ON sessions;
    DROP POLICY IF EXISTS sessions_insert ON sessions;
    DROP POLICY IF EXISTS sessions_update ON sessions;
    DROP POLICY IF EXISTS sessions_delete ON sessions;

    CREATE POLICY sessions_select ON sessions FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY sessions_insert ON sessions FOR INSERT WITH CHECK (
      (is_patient_accessible(patient_id) AND owner_id = auth.uid())
      OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
    );
    CREATE POLICY sessions_update ON sessions FOR UPDATE USING (owner_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY sessions_delete ON sessions FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 3. REPORTS
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'reports') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON reports;
    DROP POLICY IF EXISTS reports_select ON reports;
    DROP POLICY IF EXISTS reports_insert ON reports;
    DROP POLICY IF EXISTS reports_update ON reports;
    DROP POLICY IF EXISTS reports_delete ON reports;

    CREATE POLICY reports_select ON reports FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY reports_insert ON reports FOR INSERT WITH CHECK (
      (is_patient_accessible(patient_id) AND author_id = auth.uid())
      OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
    );
    CREATE POLICY reports_update ON reports FOR UPDATE USING (author_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY reports_delete ON reports FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 4. TEST_RESULTS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_results') THEN
    DROP POLICY IF EXISTS "test_results_select" ON test_results;
    DROP POLICY IF EXISTS "test_results_insert" ON test_results;
    DROP POLICY IF EXISTS "test_results_update" ON test_results;
    DROP POLICY IF EXISTS "test_results_delete" ON test_results;

    CREATE POLICY test_results_select ON test_results FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY test_results_insert ON test_results FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
    CREATE POLICY test_results_update ON test_results FOR UPDATE USING (author_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY test_results_delete ON test_results FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 5. CLINICAL_RECORDS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'clinical_records') THEN
    DROP POLICY IF EXISTS "Enable all access" ON clinical_records;
    DROP POLICY IF EXISTS clinical_records_select ON clinical_records;
    DROP POLICY IF EXISTS clinical_records_insert ON clinical_records;
    DROP POLICY IF EXISTS clinical_records_update ON clinical_records;
    DROP POLICY IF EXISTS clinical_records_delete ON clinical_records;

    CREATE POLICY clinical_records_select ON clinical_records FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY clinical_records_insert ON clinical_records FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
    CREATE POLICY clinical_records_update ON clinical_records FOR UPDATE USING (owner_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY clinical_records_delete ON clinical_records FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 6. PATIENT_ANAMNESIS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'patient_anamnesis') THEN
    DROP POLICY IF EXISTS "Enable all access" ON patient_anamnesis;
    DROP POLICY IF EXISTS patient_anamnesis_select ON patient_anamnesis;
    DROP POLICY IF EXISTS patient_anamnesis_insert ON patient_anamnesis;
    DROP POLICY IF EXISTS patient_anamnesis_update ON patient_anamnesis;
    DROP POLICY IF EXISTS patient_anamnesis_delete ON patient_anamnesis;

    CREATE POLICY patient_anamnesis_select ON patient_anamnesis FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY patient_anamnesis_insert ON patient_anamnesis FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
    CREATE POLICY patient_anamnesis_update ON patient_anamnesis FOR UPDATE USING (author_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY patient_anamnesis_delete ON patient_anamnesis FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 7. NBA_SUGGESTIONS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'nba_suggestions') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON nba_suggestions;
    DROP POLICY IF EXISTS nba_suggestions_select ON nba_suggestions;
    DROP POLICY IF EXISTS nba_suggestions_insert ON nba_suggestions;
    DROP POLICY IF EXISTS nba_suggestions_update ON nba_suggestions;

    CREATE POLICY nba_suggestions_select ON nba_suggestions FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY nba_suggestions_insert ON nba_suggestions FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
    CREATE POLICY nba_suggestions_update ON nba_suggestions FOR UPDATE USING (owner_id = auth.uid() OR user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 8. NBA_DECISIONS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'nba_decisions') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON nba_decisions;
    DROP POLICY IF EXISTS nba_decisions_select ON nba_decisions;
    DROP POLICY IF EXISTS nba_decisions_insert ON nba_decisions;

    CREATE POLICY nba_decisions_select ON nba_decisions FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY nba_decisions_insert ON nba_decisions FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 9. HOME_GUIDES (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'home_guides') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON home_guides;
    DROP POLICY IF EXISTS home_guides_select ON home_guides;
    DROP POLICY IF EXISTS home_guides_insert ON home_guides;
    DROP POLICY IF EXISTS home_guides_update ON home_guides;
    DROP POLICY IF EXISTS home_guides_delete ON home_guides;

    CREATE POLICY home_guides_select ON home_guides FOR SELECT USING (is_patient_accessible("patientId"::uuid));
    CREATE POLICY home_guides_insert ON home_guides FOR INSERT WITH CHECK (is_patient_accessible("patientId"::uuid));
    CREATE POLICY home_guides_update ON home_guides FOR UPDATE USING (owner_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY home_guides_delete ON home_guides FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 10. APPOINTMENTS
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'appointments') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON appointments;
    DROP POLICY IF EXISTS appointments_select ON appointments;
    DROP POLICY IF EXISTS appointments_insert ON appointments;
    DROP POLICY IF EXISTS appointments_update ON appointments;
    DROP POLICY IF EXISTS appointments_delete ON appointments;

    CREATE POLICY appointments_select ON appointments FOR SELECT USING (
      professional_id = auth.uid() OR consultorio_id = ANY(user_consultorios()) OR user_role() = 'admin'
      OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
    );
    CREATE POLICY appointments_insert ON appointments FOR INSERT WITH CHECK (
      professional_id = auth.uid() OR user_role() = 'admin'
      OR NOT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid())
    );
    CREATE POLICY appointments_update ON appointments FOR UPDATE USING (professional_id = auth.uid() OR user_role() = 'admin');
    CREATE POLICY appointments_delete ON appointments FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 11. CLINICAL_FACTS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'clinical_facts') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON clinical_facts;
    DROP POLICY IF EXISTS clinical_facts_select ON clinical_facts;
    DROP POLICY IF EXISTS clinical_facts_insert ON clinical_facts;

    CREATE POLICY clinical_facts_select ON clinical_facts FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY clinical_facts_insert ON clinical_facts FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 12. ANALYSIS_HISTORY (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'analysis_history') THEN
    DROP POLICY IF EXISTS "Enable all access for all users" ON analysis_history;
    DROP POLICY IF EXISTS analysis_history_select ON analysis_history;
    DROP POLICY IF EXISTS analysis_history_insert ON analysis_history;

    CREATE POLICY analysis_history_select ON analysis_history FOR SELECT USING (is_patient_accessible(patient_id));
    CREATE POLICY analysis_history_insert ON analysis_history FOR INSERT WITH CHECK (is_patient_accessible(patient_id));
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 13. MATERIALS (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'materials') THEN
    DROP POLICY IF EXISTS "Allow public read access" ON materials;
    DROP POLICY IF EXISTS "Enable all access for all users" ON materials;
    DROP POLICY IF EXISTS materials_select ON materials;
    DROP POLICY IF EXISTS materials_insert ON materials;
    DROP POLICY IF EXISTS materials_update ON materials;
    DROP POLICY IF EXISTS materials_delete ON materials;

    CREATE POLICY materials_select ON materials FOR SELECT USING (true);
    CREATE POLICY materials_insert ON materials FOR INSERT WITH CHECK (user_role() IN ('admin', 'profesional', 'supervisor'));
    CREATE POLICY materials_update ON materials FOR UPDATE USING (user_role() = 'admin');
    CREATE POLICY materials_delete ON materials FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================
-- 14. REPORT_TEMPLATES (optional)
-- ============================================
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'report_templates') THEN
    DROP POLICY IF EXISTS "Allow all access to report_templates" ON report_templates;
    DROP POLICY IF EXISTS report_templates_select ON report_templates;
    DROP POLICY IF EXISTS report_templates_insert ON report_templates;
    DROP POLICY IF EXISTS report_templates_update ON report_templates;
    DROP POLICY IF EXISTS report_templates_delete ON report_templates;

    CREATE POLICY report_templates_select ON report_templates FOR SELECT USING (true);
    CREATE POLICY report_templates_insert ON report_templates FOR INSERT WITH CHECK (user_role() = 'admin');
    CREATE POLICY report_templates_update ON report_templates FOR UPDATE USING (user_role() = 'admin');
    CREATE POLICY report_templates_delete ON report_templates FOR DELETE USING (user_role() = 'admin');
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
