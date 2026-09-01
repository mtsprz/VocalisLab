-- Sprint 9: Dashboard Analytics
-- Fase 1: Vistas de agregación para métricas

-- ============================================
-- 1. RESUMEN GENERAL (counters by period)
-- ============================================
CREATE OR REPLACE VIEW v_analytics_summary AS
SELECT
  (SELECT count(*) FROM patients WHERE created_at >= date_trunc('month', now())) AS patients_this_month,
  (SELECT count(*) FROM patients) AS patients_total,
  (SELECT count(*) FROM sessions WHERE created_at >= date_trunc('month', now())) AS sessions_this_month,
  (SELECT count(*) FROM sessions) AS sessions_total,
  (SELECT count(*) FROM appointments WHERE date >= to_char(now(), 'YYYY-MM-DD')) AS appointments_today,
  (SELECT count(*) FROM appointments WHERE date >= to_char(date_trunc('week', now()), 'YYYY-MM-DD')) AS appointments_this_week,
  (SELECT count(*) FROM appointments WHERE date >= to_char(date_trunc('month', now()), 'YYYY-MM-DD')) AS appointments_this_month,
  (SELECT count(*) FROM clinical_history_records WHERE status = 'approved') AS histories_approved,
  (SELECT count(*) FROM clinical_history_records WHERE status = 'reviewed') AS histories_reviewed,
  (SELECT count(*) FROM clinical_history_records WHERE status = 'draft') AS histories_draft,
  (SELECT count(*) FROM home_guides WHERE status = 'sent') AS guides_sent,
  (SELECT count(*) FROM home_guides) AS guides_total,
  (SELECT count(*) FROM test_results) AS tests_total,
  now() AS computed_at;

-- ============================================
-- 2. PACIENTES POR CONSULTORIO
-- ============================================
CREATE OR REPLACE VIEW v_patients_by_consultorio AS
SELECT
  consultorio_id,
  count(*) AS total,
  count(*) FILTER (WHERE quick_status = 'active_quick') AS quick_active,
  count(*) FILTER (WHERE quick_status = 'formalized') AS formalized,
  count(*) FILTER (WHERE quick_status = 'discarded') AS discarded,
  count(*) FILTER (WHERE created_at >= date_trunc('month', now())) AS new_this_month
FROM patients
GROUP BY consultorio_id;

-- ============================================
-- 3. SESIONES POR PROFESIONAL (últimos 30 días)
-- ============================================
CREATE OR REPLACE VIEW v_sessions_by_professional AS
SELECT
  s.owner_id AS professional_id,
  p.full_name AS professional_name,
  count(*) AS total_sessions,
  count(*) FILTER (WHERE s.created_at >= date_trunc('week', now())) AS this_week,
  count(*) FILTER (WHERE s.created_at >= date_trunc('month', now())) AS this_month
FROM sessions s
LEFT JOIN profiles p ON p.id = s.owner_id
WHERE s.created_at >= now() - interval '30 days'
GROUP BY s.owner_id, p.full_name
ORDER BY total_sessions DESC;

-- ============================================
-- 4. PIPELINE HISTORIA CLÍNICA (draft→reviewed→approved)
-- ============================================
CREATE OR REPLACE VIEW v_history_pipeline AS
SELECT
  clinic_id,
  status,
  count(*) AS total,
  count(*) FILTER (WHERE created_at >= date_trunc('month', now())) AS this_month,
  avg(extract(epoch FROM (updated_at - created_at)) / 3600) AS avg_hours_to_update
FROM clinical_history_records
GROUP BY clinic_id, status;

-- ============================================
-- 5. TASA DE ACEPTACIÓN NBA (por módulo y categoría)
-- ============================================
CREATE OR REPLACE VIEW v_nba_acceptance_rates AS
SELECT
  count(*) AS total_decisions,
  count(*) FILTER (WHERE clinician_disposition = 'accepted') AS accepted,
  count(*) FILTER (WHERE clinician_disposition = 'rejected') AS rejected,
  count(*) FILTER (WHERE clinician_disposition = 'edited') AS edited,
  round(
    count(*) FILTER (WHERE clinician_disposition = 'accepted')::numeric /
    nullif(count(*), 0) * 100, 1
  ) AS acceptance_rate,
  metadata->>'moduleId' AS module_id,
  category
FROM nba_decisions
GROUP BY metadata->>'moduleId', category;

-- ============================================
-- 6. ASISTENCIA DE CITAS (por profesional y total)
-- ============================================
CREATE OR REPLACE VIEW v_appointment_attendance AS
SELECT
  professional_id,
  count(*) AS total,
  count(*) FILTER (WHERE status = 'completed') AS attended,
  count(*) FILTER (WHERE status = 'cancelled') AS cancelled,
  count(*) FILTER (WHERE status = 'pending') AS pending,
  round(
    count(*) FILTER (WHERE status = 'completed')::numeric /
    nullif(count(*), 0) * 100, 1
  ) AS attendance_rate
FROM appointments
WHERE date >= to_char(now() - interval '90 days', 'YYYY-MM-DD')
GROUP BY professional_id;

-- ============================================
-- 7. USO DE IA POR CAMPO (desde ai_metadata)
-- ============================================
CREATE OR REPLACE VIEW v_ai_usage_by_field AS
SELECT
  chr.author_id AS user_id,
  p.full_name AS user_name,
  count(*) AS total_ai_interactions,
  chr.clinic_id
FROM clinical_history_records chr
JOIN profiles p ON p.id = chr.author_id
WHERE chr.ai_metadata IS NOT NULL
  AND jsonb_array_length(chr.ai_metadata) > 0
GROUP BY chr.author_id, p.full_name, chr.clinic_id;

-- ============================================
-- 8. TESTS POR ÁREA
-- ============================================
CREATE OR REPLACE VIEW v_tests_by_area AS
SELECT
  area,
  count(*) AS total,
  round(avg(percentage), 1) AS avg_percentage,
  count(*) FILTER (WHERE created_at >= date_trunc('month', now())) AS this_month
FROM test_results
WHERE area IS NOT NULL
GROUP BY area
ORDER BY total DESC;

-- ============================================
-- 9. GUÍAS HOGAR — TASA DE ENVÍO
-- ============================================
CREATE OR REPLACE VIEW v_home_guide_delivery AS
SELECT
  status,
  delivery_method,
  count(*) AS total,
  count(*) FILTER (WHERE created_at >= date_trunc('month', now())) AS this_month
FROM home_guides
GROUP BY status, delivery_method;

-- ============================================
-- 10. DISTRIBUCIÓN DE ENVÍOS (éxito/fallo)
-- ============================================
CREATE OR REPLACE VIEW v_distribution_stats AS
SELECT
  medium,
  status,
  count(*) AS total,
  count(*) FILTER (WHERE created_at >= date_trunc('month', now())) AS this_month
FROM distribution_logs
GROUP BY medium, status;

-- ============================================
-- 11. ACTIVIDAD RECIENTE (últimas 24h)
-- ============================================
CREATE OR REPLACE VIEW v_recent_activity AS
SELECT 'patient_created' AS event_type, name AS description, created_at
FROM patients WHERE created_at >= now() - interval '24 hours'
UNION ALL
SELECT 'session_completed' AS event_type,
  'Sesión con ' || coalesce(p.name, 'paciente') AS description, s.created_at
FROM sessions s
LEFT JOIN patients p ON p.id::text = s.patient_id::text
WHERE s.created_at >= now() - interval '24 hours'
UNION ALL
SELECT 'history_approved' AS event_type,
  'Historia aprobada' AS description, chr.updated_at
FROM clinical_history_records chr
WHERE chr.status = 'approved' AND chr.updated_at >= now() - interval '24 hours'
UNION ALL
SELECT 'guide_sent' AS event_type,
  coalesce(title, 'Guía') AS description, sent_at
FROM home_guides
WHERE sent_at >= now() - interval '24 hours'
ORDER BY created_at DESC
LIMIT 20;
