import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface ClinicalData {
  paciente: any;
  anamnesis: any;
  riesgoVocal: any;
  escalas: any;
  acustica: any;
  recomendacion: any;
}

interface ClinicalContextType {
  data: ClinicalData;
  setPaciente: (d: any) => void;
  setAnamnesis: (d: any) => void;
  setRiesgoVocal: (d: any) => void;
  setEscalas: (d: any) => void;
  setAcustica: (d: any) => void;
  setRecomendacion: (d: any) => void;
  completedSteps: string[];
  markStep: (step: string) => void;
  cargarPaciente: (pacienteId: string) => Promise<void>;
  seleccionarPaciente: (pacienteStub: any) => void;
  resetClinica: () => void;
  /** Token que aumenta cada vez que termina una hidratación: los módulos
   *  recargan sus formularios locales cuando cambia. */
  cargaToken: number;
}

const ClinicalContext = createContext<ClinicalContextType | null>(null);

export function useClinical() {
  const ctx = useContext(ClinicalContext);
  if (!ctx) throw new Error('useClinical must be used within ClinicalProvider');
  return ctx;
}

const DEFAULT_DATA: ClinicalData = {
  paciente: {
    id: null,
    nombre_completo: '',
    dni: '',
    fecha_nacimiento: '',
    sexo: 'Femenino',
    ocupacion: '',
    demanda_vocal_horas: 4,
  },
  anamnesis: {
    motivo_consulta: '',
    diagnostico_orl: '',
    metodo_exploracion: '',
    sintomas: {},
    factores_riesgo: {},
    resumen_clinico: '',
    transcripcion: '',
  },
  riesgoVocal: {
    puntaje_total: 0,
    grupo: '',
    subtotales: {},
    alertas: [],
  },
  escalas: {
    grbas: { G: 0, R: 0, B: 0, A: 0, S: 0 },
    rasati: { R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 },
    vhi10_total: 0,
    vhi10_score: 0,
    tme_segundos: 0,
    tme_o: 0,
    tme_s: 0,
  },
  acustica: {
    f0_mean: null,
    f0_min: null,
    f0_max: null,
    f0_sd: null,
    jitter_local_pct: null,
    shimmer_local_pct: null,
    hnr_db: null,
    cpps_db: null,
    nhr: null,
    avqi: null,
  },
  recomendacion: null,
};

function mergeState(prev: any, next: any) {
  if (!next || typeof next !== 'object') return next ?? prev ?? {};
  const clean: any = {};
  for (const [k, v] of Object.entries(next)) {
    if (v !== undefined) clean[k] = v;
  }
  return { ...(prev || {}), ...clean };
}

/** Normaliza aliases de escalas para que todos los módulos lean lo mismo. */
function normalizeEscalas(e: any) {
  const out = { ...(e || {}) };
  if (out.vhi10_total == null && out.vhi10_score != null) out.vhi10_total = out.vhi10_score;
  if (out.vhi10_score == null && out.vhi10_total != null) out.vhi10_score = out.vhi10_total;
  if (out.tme_segundos == null && out.tme_s != null) out.tme_segundos = out.tme_s;
  if (out.tme_s == null && out.tme_segundos != null) out.tme_s = out.tme_segundos;
  if (out.tme_o == null && out.tme != null) out.tme_o = out.tme;
  return out;
}

function cacheKey(pacienteId: string) {
  return `vocalislab_clinical_${pacienteId}`;
}

function loadCache(pacienteId: string | null): ClinicalData | null {
  if (!pacienteId) return null;
  try {
    const raw = localStorage.getItem(cacheKey(pacienteId));
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

export function ClinicalProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<ClinicalData>(() => {
    try {
      const lastId = localStorage.getItem('vocalislab_last_paciente');
      if (lastId) {
        const cached = loadCache(lastId);
        if (cached) return { ...DEFAULT_DATA, ...cached };
      }
    } catch {}
    return DEFAULT_DATA;
  });
  const [completedSteps, setCompletedSteps] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem('vocalislab_completed_steps');
      if (raw) return JSON.parse(raw);
    } catch {}
    return [];
  });
  const [cargaToken, setCargaToken] = useState(0);
  const dataRef = useRef(data);
  dataRef.current = data;

  // Persistir en localStorage ante cada cambio (sobrevive refresh)
  useEffect(() => {
    try {
      const pid = dataRef.current?.paciente?.id;
      if (pid) {
        localStorage.setItem(cacheKey(pid), JSON.stringify(dataRef.current));
        localStorage.setItem('vocalislab_last_paciente', pid);
      }
      localStorage.setItem('vocalislab_completed_steps', JSON.stringify(completedSteps));
    } catch {}
  }, [data, completedSteps]);

  const markStep = (step: string) => {
    setCompletedSteps(prev => prev.includes(step) ? prev : [...prev, step]);
  };

  const setPaciente = (d: any) => setData(prev => ({ ...prev, paciente: mergeState(prev.paciente, d) }));
  const setAnamnesis = (d: any) => setData(prev => ({ ...prev, anamnesis: mergeState(prev.anamnesis, d) }));
  const setRiesgoVocal = (d: any) => setData(prev => ({ ...prev, riesgoVocal: mergeState(prev.riesgoVocal, d) }));
  const setEscalas = (d: any) => setData(prev => ({ ...prev, escalas: normalizeEscalas(mergeState(prev.escalas, d)) }));
  const setAcustica = (d: any) => setData(prev => ({ ...prev, acustica: mergeState(prev.acustica, d) }));
  const setRecomendacion = (d: any) => setData(prev => ({ ...prev, recomendacion: d }));

  /** Limpia todo el estado clínico (evita contaminar entre pacientes). */
  const resetClinica = () => {
    setData(DEFAULT_DATA);
    setCompletedSteps([]);
    try {
      localStorage.removeItem('vocalislab_completed_steps');
    } catch {}
  };

  /** Selección atómica: resetea, fija stub del paciente y marca el paso. */
  const seleccionarPaciente = (pacienteStub: any) => {
    setData({ ...DEFAULT_DATA, paciente: mergeState(DEFAULT_DATA.paciente, pacienteStub) });
    markStep('pacientes');
  };

  /** Hidrata todo el estado clínico desde el backend para un paciente. */
  const cargarPaciente = async (pacienteId: string) => {
    if (!pacienteId) return;
    resetClinica();
    try {
      const rp = await fetch(`${BACKEND_URL}/api/pacientes/${pacienteId}`);
      if (rp.ok) {
        const p = await rp.json();
        setPaciente({
          id: p.id,
          nombre_completo: p.nombre_completo || p.nombre || '',
          dni: p.dni || '',
          fecha_nacimiento: p.fecha_nacimiento || '',
          sexo: p.sexo || p.genero || 'Femenino',
          telefono: p.telefono || '',
          email: p.email || '',
          ocupacion: p.ocupacion || '',
          demanda_vocal_horas: p.demanda_vocal_horas || 4,
        });
        markStep('pacientes');
      }
    } catch {}
    try {
      const ra = await fetch(`${BACKEND_URL}/api/anamnesis?paciente_id=${pacienteId}`);
      if (ra.ok) {
        const a = await ra.json();
        if (a && a.id) {
          setAnamnesis({
            motivo_consulta: a.motivo_consulta || '',
            diagnostico_orl: a.diagnostico_orl || '',
            metodo_exploracion: a.metodo_exploracion || '',
            sintomas: a.sintomas || {},
            factores_riesgo: a.factores_riesgo || {},
            resumen_clinico: a.resumen_clinico || '',
            transcripcion: a.transcripcion_audio || '',
          });
          markStep('anamnesis');
        }
      }
    } catch {}
    try {
      const re = await fetch(`${BACKEND_URL}/api/evaluaciones?paciente_id=${pacienteId}&limit=1`);
      if (re.ok) {
        const arr = await re.json();
        const ev = Array.isArray(arr) ? arr[0] : null;
        if (ev) {
          setEscalas({
            grbas: ev.grbas || undefined,
            rasati: ev.rasati || undefined,
            vhi10_score: ev.vhi10_score,
            vhi10_detalle: ev.vhi10_detalle,
            tme_o: ev.tme_o,
            tme_s: ev.tme_s,
            indice_so: ev.indice_so,
            observaciones: ev.observaciones || '',
            f0_conversacional_hz: ev.f0_conversacional_hz,
            autopercepcion_vocal: ev.autopercepcion_vocal,
          });
          if (ev.riesgo_vocal_score != null) {
            setRiesgoVocal({
              puntaje_total: ev.riesgo_vocal_score,
              detalle: ev.riesgo_vocal_detalle,
            });
            markStep('escalas');
          } else if (ev.grbas) {
            markStep('escalas');
          }
        }
      }
    } catch {}
    try {
      const rac = await fetch(`${BACKEND_URL}/api/analisis_acusticos?paciente_id=${pacienteId}&limit=1`);
      if (rac.ok) {
        const arr = await rac.json();
        const an = Array.isArray(arr) ? arr[0] : null;
        if (an) {
          const { id, paciente_id, fecha, evaluacion_id, modo, ...mets } = an;
          setAcustica(mets);
          markStep('analisis');
        }
      }
    } catch {}
    setCargaToken(t => t + 1);
  };

  return (
    <ClinicalContext.Provider value={{
      data, setPaciente, setAnamnesis, setRiesgoVocal,
      setEscalas, setAcustica, setRecomendacion,
      completedSteps, markStep, cargarPaciente,
      seleccionarPaciente, resetClinica, cargaToken
    }}>
      {children}
    </ClinicalContext.Provider>
  );
}
