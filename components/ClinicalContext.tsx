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

export function ClinicalProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<ClinicalData>({
    paciente: null,
    anamnesis: null,
    riesgoVocal: null,
    escalas: null,
    acustica: null,
    recomendacion: null,
  });
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  const markStep = (step: string) => {
    setCompletedSteps(prev => prev.includes(step) ? prev : [...prev, step]);
  };

  const setPaciente = (d: any) => setData(prev => ({ ...prev, paciente: d }));
  const setAnamnesis = (d: any) => setData(prev => ({ ...prev, anamnesis: d }));
  const setRiesgoVocal = (d: any) => setData(prev => ({ ...prev, riesgoVocal: d }));
  const setEscalas = (d: any) => setData(prev => ({ ...prev, escalas: d }));
  const setAcustica = (d: any) => setData(prev => ({ ...prev, acustica: d }));
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
