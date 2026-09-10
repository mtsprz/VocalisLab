import React, { createContext, useContext, useState, ReactNode } from 'react';

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
  return { ...(prev || {}), ...next };
}

export function ClinicalProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<ClinicalData>(DEFAULT_DATA);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  const markStep = (step: string) => {
    setCompletedSteps(prev => prev.includes(step) ? prev : [...prev, step]);
  };

  const setPaciente = (d: any) => setData(prev => ({ ...prev, paciente: mergeState(prev.paciente, d) }));
  const setAnamnesis = (d: any) => setData(prev => ({ ...prev, anamnesis: mergeState(prev.anamnesis, d) }));
  const setRiesgoVocal = (d: any) => setData(prev => ({ ...prev, riesgoVocal: mergeState(prev.riesgoVocal, d) }));
  const setEscalas = (d: any) => setData(prev => ({ ...prev, escalas: mergeState(prev.escalas, d) }));
  const setAcustica = (d: any) => setData(prev => ({ ...prev, acustica: mergeState(prev.acustica, d) }));
  const setRecomendacion = (d: any) => setData(prev => ({ ...prev, recomendacion: d }));

  return (
    <ClinicalContext.Provider value={{
      data, setPaciente, setAnamnesis, setRiesgoVocal,
      setEscalas, setAcustica, setRecomendacion,
      completedSteps, markStep
    }}>
      {children}
    </ClinicalContext.Provider>
  );
}
