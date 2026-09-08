import React from 'react';
import { UserPlus, Mic, Shield, Activity, Sparkles, FileText, Check } from 'lucide-react';
import { useClinical } from './ClinicalContext';

interface Props {
  activeModule: string;
  onNavigate: (m: string) => void;
}

const STEPS = [
  { id: 'pacientes', label: 'Admisión', icon: UserPlus },
  { id: 'anamnesis', label: 'Anamnesis', icon: Mic },
  { id: 'escalas', label: 'Riesgo & Escalas', icon: Shield },
  { id: 'analisis', label: 'Análisis Praat', icon: Activity },
  { id: 'recomendacion', label: 'Motor IA', icon: Sparkles },
  { id: 'cuadernillo', label: 'Cuadernillo', icon: FileText },
];

export default function ClinicalStepper({ activeModule, onNavigate }: Props) {
  const { completedSteps, data } = useClinical();

  const activeIdx = STEPS.findIndex(s => s.id === activeModule);

  return (
    <div className="flex items-center gap-1 overflow-x-auto py-2 px-1 scrollbar-hide">
      {STEPS.map((step, idx) => {
        const isCompleted = completedSteps.includes(step.id);
        const isActive = step.id === activeModule;
        const isPast = idx < activeIdx || isCompleted;
        const Icon = step.icon;

        return (
          <React.Fragment key={step.id}>
            <button
              onClick={() => onNavigate(step.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/25'
                  : isPast
                    ? 'bg-indigo-100 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800'
                    : 'bg-gray-100 dark:bg-gray-800/50 text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-800'
              }`}
            >
              {isPast && !isActive ? (
                <Check size={13} className="text-indigo-500 dark:text-indigo-400" />
              ) : (
                <Icon size={13} />
              )}
              <span className="hidden md:inline">{step.label}</span>
            </button>
            {idx < STEPS.length - 1 && (
              <div className={`w-4 h-px flex-shrink-0 ${
                idx < activeIdx ? 'bg-indigo-300 dark:bg-indigo-700' : 'bg-gray-200 dark:bg-gray-800'
              }`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
