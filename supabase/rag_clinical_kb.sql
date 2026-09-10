-- =========================================================
-- VOCALISLAB PRO — RAG CLINICAL KNOWLEDGE BASE (Primary Cache)
-- Tablas: patologias, ejercicios, patologia_ejercicio_relacion
-- Idempotente: puede ejecutarse multiples veces sin errores.
-- Ejecutar en Supabase SQL Editor DESPUES de vocalislab_schema_v2.sql
-- =========================================================

-- 1. PATOLOGIAS ------------------------------------------------
CREATE TABLE IF NOT EXISTS patologias (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    categoria TEXT DEFAULT 'funcional',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 2. EJERCICIOS (catálogo estructurado espejo de exercise_bank.json)
CREATE TABLE IF NOT EXISTS ejercicios (
    id TEXT PRIMARY KEY,
    seccion_id TEXT DEFAULT 'general',
    nombre TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    pasos JSONB DEFAULT '[]'::jsonb,
    duracion_min INT DEFAULT 5,
    dificultad TEXT DEFAULT 'basico',
    indicaciones JSONB DEFAULT '[]'::jsonb,
    contraindicaciones JSONB DEFAULT '[]'::jsonb,
    fuente TEXT DEFAULT 'Farias 2012/2016',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 3. MATRIZ PATOLOGIA <-> EJERCICIO -----------------------------
CREATE TABLE IF NOT EXISTS patologia_ejercicio_relacion (
    patologia_id TEXT REFERENCES patologias(id) ON DELETE CASCADE,
    ejercicio_id TEXT REFERENCES ejercicios(id) ON DELETE CASCADE,
    peso INT DEFAULT 5 CHECK (peso BETWEEN 1 AND 10),
    trigger_clinico TEXT DEFAULT '',
    PRIMARY KEY (patologia_id, ejercicio_id)
);

-- Indices para latencia <50ms ----------------------------------
CREATE INDEX IF NOT EXISTS idx_rel_patologia ON patologia_ejercicio_relacion(patologia_id);
CREATE INDEX IF NOT EXISTS idx_rel_ejercicio ON patologia_ejercicio_relacion(ejercicio_id);
CREATE INDEX IF NOT EXISTS idx_ejercicios_seccion ON ejercicios(seccion_id);

-- RLS (lectura/escritura para usuarios autenticados + service role)
ALTER TABLE patologias ENABLE ROW LEVEL SECURITY;
ALTER TABLE ejercicios ENABLE ROW LEVEL SECURITY;
ALTER TABLE patologia_ejercicio_relacion ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for authenticated" ON patologias;
CREATE POLICY "Allow all for authenticated" ON patologias FOR ALL TO authenticated USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all for authenticated" ON ejercicios;
CREATE POLICY "Allow all for authenticated" ON ejercicios FOR ALL TO authenticated USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Allow all for authenticated" ON patologia_ejercicio_relacion;
CREATE POLICY "Allow all for authenticated" ON patologia_ejercicio_relacion FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- SEED: patologias ----------------------------------------------
INSERT INTO patologias (id, nombre, descripcion, categoria) VALUES
  ('dmt', 'DMT — Disfonia por Tension Muscular (I a IV)', 'Hiperfuncion, acortamiento supraglotico y constriccion. Abordaje: Le Huche, descontracturacion, descenso laringeo, SOVTE.', 'funcional'),
  ('nodulo', 'Nodulos Cordales / Lesiones Exofiticas', 'Edema en punto nodular por microtrauma. Abordaje: SOVTE (LaxVox), ataque suave, descenso laringeo.', 'organica-funcional'),
  ('paralisis', 'Paralisis Cordal / Incompetencia Glotica', 'Deficit de cierre cordal. Abordaje: apoyo costodiafragmatico, empuje, resonancia anterior.', 'neurologica'),
  ('presbifonia', 'Presbifonia / Atrofia Cordal', 'Arqueamiento senil. Abordaje: tonificacion, popote estrecho, proyeccion.', 'degenerativa'),
  ('fonastenia', 'Fonastenia / Fatiga Vocal Ocupacional', 'Cansancio vocal en docentes. Abordaje: economia vocal (SOVTE), resonancia, pausas.', 'funcional'),
  ('rlf', 'Reflujo Laringofaringeo (RLF)', 'Irritacion interaritenoidea con carraspeo cronico. Abordaje: higiene digestiva, hidratacion, vibracion suave.', 'inflamatoria'),
  ('edema_reinke', 'Edema de Reinke / Degeneracion Polipoidea', 'Aumento de masa en espacio de Reinke. Abordaje: disminuir impacto, resonancia, SOVTE.', 'organica'),
  ('pre_estreno', 'Acondicionamiento y Mantenimiento Vocal', 'Rutina de preparacion para profesionales de la voz hablada y cantada.', 'preventiva')
ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion, categoria = EXCLUDED.categoria;

-- SEED: ejercicios nucleo (espejo de exercise_bank.json) --------
INSERT INTO ejercicios (id, seccion_id, nombre, descripcion, duracion_min, dificultad, indicaciones, fuente) VALUES
  ('le_huche', 'corporal', 'Tecnica de Relajacion Diferencial (Le Huche)', 'Secuencia respiratoria con /f/ y /sh/, apnea y descenso tensional.', 5, 'basico', '["dmt","nodulo","fonastenia"]', 'Le Huche / Farias 2012'),
  ('masaje_laringeo', 'laringeo', 'Masaje Circumlaringeo Manual', 'Masaje circular en espacio tirohioideo para descender laringe elevada.', 4, 'basico', '["dmt","nodulo","edema_reinke"]', 'Farias 2016'),
  ('descenso_laringeo', 'laringeo', 'Bostezo-Suspiro Activo', 'Apertura faringea y descenso fisiologico de laringe.', 3, 'basico', '["dmt","rlf"]', 'Farias 2012'),
  ('tubo_agua', 'sovte', 'Lax Vox / Tubo Sumergido en Agua', 'Fonacion en tubo de silicona sumergido 1.5 cm. Masaje glotico por contrapresion.', 5, 'basico', '["dmt","nodulo","fonastenia","edema_reinke"]', 'Titze / Farias 2016'),
  ('tubo_lax_vox', 'sovte', 'SOVTE Tubo de Resonancia en Agua (LaxVox)', 'Alias clinico de tubo_agua con burbujeo parejo y glissandos.', 6, 'intermedio', '["nodulo","edema_reinke","fonastenia"]', 'Titze'),
  ('vibracion_labial', 'sovte', 'Vibracion de Labios y Lengua (Trill)', 'Oscilacion /brrr/ o /rrr/ para equilibrar impedancia acustica.', 4, 'basico', '["dmt","nodulo"]', 'Farias 2012'),
  ('tracto_vocal_semiocluido', 'sovte', 'SOVTE Vibracion Labial/Lingual', 'Tracto vocal semiocluido para ecualizar presiones.', 5, 'basico', '["nodulo","dmt","fonastenia"]', 'Titze'),
  ('humming_m', 'resonancia', 'Resonancia Anterior con /m/', 'Colocacion en mascara facial con oclusion bilabial relajada.', 4, 'basico', '["rlf","fonastenia","paralisis"]', 'Farias 2016'),
  ('humming_mascara', 'resonancia', 'Humming /m/ en Mascara Facial', 'Alias clinico de humming_m con foco anterior.', 5, 'basico', '["rlf","fonastenia","paralisis"]', 'Farias 2016'),
  ('respiracion_abdominal', 'respiratorio', 'Respiracion Costo-Diafragmatica', 'Patron eficiente sin elevacion clavicular.', 5, 'basico', '["paralisis","presbifonia","general"]', 'Le Huche'),
  ('empuje_glotico', 'respiratorio', 'Tecnica de Cierre Aumentado / Empuje', 'Adosamiento cordal en paralisis o incompetencia glotica.', 4, 'avanzado', '["paralisis","presbifonia"]', 'Farias 2016'),
  ('expansion_costo_lateral', 'respiratorio', 'Expansion Costo-Lateral y Apoyo', 'Apertura costal lateral con manos en parrilla costal.', 4, 'basico', '["paralisis","presbifonia"]', 'Farias 2012'),
  ('frases_balanceadas', 'resonancia', 'Frases Foneticamente Balanceadas', 'Transferencia de patrones funcionales al habla conversacional.', 6, 'basico', '["general","nodulo"]', 'Farias 2012'),
  ('calentamiento', 'higiene', 'Protocolo de Calentamiento Vocal', 'Rutina pre-exigencia de 6 minutos.', 6, 'basico', '["general","pre_estreno"]', 'Farias 2016'),
  ('enfriamiento', 'higiene', 'Protocolo de Enfriamiento y Reposo', 'Desaceleracion post-exigencia para evitar edema reactivo.', 5, 'basico', '["general","pre_estreno"]', 'Farias 2016'),
  ('pautas_rlf', 'higiene', 'Pautas Antirreflujo Laringofaringeo', 'Higiene digestiva para controlar irritacion acida.', 3, 'basico', '["rlf"]', 'Guia clinica 2016')
ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion;

-- SEED: matriz de pesos ------------------------------------------
INSERT INTO patologia_ejercicio_relacion (patologia_id, ejercicio_id, peso, trigger_clinico) VALUES
  ('dmt','le_huche',10,'GRBAS T>=2 o tension cervical'),
  ('dmt','masaje_laringeo',9,'Laringe elevada / dolor a la palpacion'),
  ('dmt','descenso_laringeo',9,'Hiperfuncion isometrica'),
  ('dmt','tubo_agua',8,'Constriccion supraglotica'),
  ('dmt','vibracion_labial',7,'Ataque duro'),
  ('nodulo','tubo_agua',10,'Lesion exofitica / edema punto nodular'),
  ('nodulo','masaje_laringeo',8,'Hiperfuncion compensatoria'),
  ('nodulo','humming_m',8,'Ataque brusco'),
  ('nodulo','respiracion_abdominal',7,'Soplo espiratorio corto'),
  ('paralisis','empuje_glotico',10,'Brecha glotica / soplo audible'),
  ('paralisis','respiracion_abdominal',9,'TME acortado'),
  ('paralisis','expansion_costo_lateral',8,'Apoyo insuficiente'),
  ('paralisis','humming_m',7,'Resonancia posterior'),
  ('presbifonia','empuje_glotico',9,'Arqueamiento / escape aereo senil'),
  ('presbifonia','expansion_costo_lateral',8,'Intensidad reducida'),
  ('fonastenia','tubo_agua',9,'Fatiga vocal vespertina en docentes'),
  ('fonastenia','humming_m',8,'Carraspeo por esfuerzo'),
  ('rlf','pautas_rlf',10,'Carraspeo cronico / pirosis'),
  ('rlf','humming_m',7,'Edema interaritenoideo'),
  ('edema_reinke','tubo_agua',9,'Masa aumentada / voz grave rasposa'),
  ('pre_estreno','calentamiento',10,'Pre-jornada vocal'),
  ('pre_estreno','enfriamiento',9,'Post-jornada vocal')
ON CONFLICT (patologia_id, ejercicio_id) DO UPDATE SET peso = EXCLUDED.peso, trigger_clinico = EXCLUDED.trigger_clinico;
