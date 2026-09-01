-- ============================================
-- DIARIO DE TRABAJO UNIFICADO — Vista SQL
-- All patient_id cast to text for UNION compatibility
-- ============================================

CREATE OR REPLACE VIEW v_work_journal AS

-- 1. Pacientes creados
SELECT
  'paciente_creado'::text AS event_type,
  'Paciente creado'::text AS category,
  p.name AS description,
  p.id::text AS patient_id,
  p.name AS patient_name,
  NULL::text AS detail,
  p.created_at
FROM patients p

UNION ALL

-- 2. Sesiones
SELECT
  'sesion'::text,
  'Sesion clinica'::text,
  'Sesion con ' || coalesce(p.name, 'paciente')::text,
  s.patient_id::text,
  p.name,
  left(coalesce(s.summary, ''), 200),
  s.created_at
FROM sessions s
LEFT JOIN patients p ON p.id::text = s.patient_id::text

UNION ALL

-- 3. Informes generados
SELECT
  'informe'::text,
  'Informe clinico'::text,
  r.title::text,
  r.patient_id::text,
  p.name,
  r.type,
  r.created_at
FROM reports r
LEFT JOIN patients p ON p.id::text = r.patient_id::text

UNION ALL

-- 4. Alertas gestionadas
SELECT
  'alerta_gestionada'::text,
  'Alerta'::text,
  fal.action::text,
  fal.patient_id::text,
  p.name,
  left(coalesce(fal.notes, ''), 200),
  fal.created_at
FROM follow_up_audit_log fal
LEFT JOIN patients p ON p.id::text = fal.patient_id::text

UNION ALL

-- 5. Decisiones NBA (sugerencias IA aceptadas/rechazadas)
SELECT
  'decision_nba'::text,
  'Decision IA'::text,
  ns.title::text,
  nd.patient_id::text,
  p.name,
  nd.clinician_disposition,
  nd.created_at
FROM nba_decisions nd
LEFT JOIN nba_suggestions ns ON ns.id = nd.suggestion_id
LEFT JOIN patients p ON p.id::text = nd.patient_id::text

UNION ALL

-- 6. Guias de hogar enviadas
SELECT
  'guia_enviada'::text,
  'Guia de hogar'::text,
  coalesce(hg.title, 'Guia')::text,
  hg."patientId"::text,
  p.name,
  hg.status,
  coalesce(hg.sent_at, hg.created_at)
FROM home_guides hg
LEFT JOIN patients p ON p.id::text = hg."patientId"::text
WHERE hg.sent_at IS NOT NULL

UNION ALL

-- 7. Evolucion clinica
SELECT
  'evolucion'::text,
  'Evolucion clinica'::text,
  cee.axis::text,
  cee.patient_id::text,
  p.name,
  left(coalesce(cee.notes, ''), 200),
  cee.created_at
FROM clinical_evolution_entries cee
LEFT JOIN patients p ON p.id::text = cee.patient_id::text

ORDER BY created_at DESC;
