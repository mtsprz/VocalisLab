import React, { useState } from 'react';
import { Mic, FileText, BookOpen, MessageCircle, Timer, Activity, HelpCircle, ChevronDown, ChevronRight, AlertTriangle, Info } from 'lucide-react';

export interface VocalTask {
  id: string;
  name: string;
  description: string;
  icon: any;
  requires: string[];
  avqi_compatible: boolean;
  estimated_duration: string;
  metrics_enabled: string[];
  metrics_disabled: string[];
}

export const VOCAL_TASKS: VocalTask[] = [
  {
    id: 'sustained_a',
    name: 'Vocal sostenida /a/',
    description: 'Vocal sostenida de aproximadamente 3-5 segundos. Permite medir jitter, shimmer, HNR, CPPS y F0.',
    icon: Mic,
    requires: ['audio_vocal'],
    avqi_compatible: false,
    estimated_duration: '3-5 segundos',
    metrics_enabled: ['f0', 'jitter', 'shimmer', 'hnr', 'cpps', 'formants', 'intensity'],
    metrics_disabled: ['avqi'],
  },
  {
    id: 'continuous_speech',
    name: 'Habla continua',
    description: 'Muestra de habla espontánea o lectura de al menos 10 segundos. Requerida para cálculo de AVQI.',
    icon: MessageCircle,
    requires: ['audio_habla'],
    avqi_compatible: true,
    estimated_duration: '≥ 10 segundos',
    metrics_enabled: ['f0', 'jitter', 'shimmer', 'hnr', 'cpps', 'formants', 'intensity', 'avqi'],
    metrics_disabled: [],
  },
  {
    id: 'combined',
    name: 'Muestra combinada para AVQI',
    description: 'Vocal sostenida /a/ + habla continua. Protocolo completo para AVQI v03.01.',
    icon: Activity,
    requires: ['audio_vocal', 'audio_habla'],
    avqi_compatible: true,
    estimated_duration: '3-5s vocal + ≥ 10s habla',
    metrics_enabled: ['f0', 'jitter', 'shimmer', 'hnr', 'cpps', 'formants', 'intensity', 'avqi'],
    metrics_disabled: [],
  },
  {
    id: 'reading',
    name: 'Lectura estandarizada',
    description: 'Lectura de texto estandarizado (ej: "La春`a`" o pasaje similar). Permite análisis de habla con referencia.',
    icon: BookOpen,
    requires: ['audio_vocal'],
    avqi_compatible: true,
    estimated_duration: '15-30 segundos',
    metrics_enabled: ['f0', 'jitter', 'shimmer', 'hnr', 'cpps', 'formants', 'intensity', 'avqi'],
    metrics_disabled: [],
  },
  {
    id: 'conversational',
    name: 'Voz conversacional',
    description: 'Muestra de voz en contexto conversacional. Análisis cualitativo.',
    icon: MessageCircle,
    requires: ['audio_vocal'],
    avqi_compatible: false,
    estimated_duration: 'Variable',
    metrics_enabled: ['f0', 'jitter', 'shimmer', 'hnr', 'formants', 'intensity'],
    metrics_disabled: ['avqi', 'cpps'],
  },
  {
    id: 'maximum_phonation',
    name: 'Máxima fonación',
    description: 'Vocal sostenida /a/ al máximo de tiempo posible. Permite calcular TMF y kapitanov index.',
    icon: Timer,
    requires: ['audio_vocal'],
    avqi_compatible: false,
    estimated_duration: 'Máximo sostenido',
    metrics_enabled: ['f0', 'jitter', 'shimmer', 'hnr', 'cpps', 'formants', 'intensity', 'tmf'],
    metrics_disabled: ['avqi'],
  },
  {
    id: 'diadochokinesis',
    name: 'Diadococinesia',
    description: 'Repetición rápida de sílabas (pa-pa-pa, ta-ta-ta, ka-ka-ka). Evaluación de motricidad velar y labial.',
    icon: Activity,
    requires: ['audio_vocal'],
    avqi_compatible: false,
    estimated_duration: '5-10 segundos por sílaba',
    metrics_enabled: ['f0', 'intensity'],
    metrics_disabled: ['jitter', 'shimmer', 'hnr', 'cpps', 'avqi', 'formants'],
  },
  {
    id: 'other',
    name: 'Otro protocolo',
    description: 'Especificar en observaciones. Métricas básicas disponibles.',
    icon: HelpCircle,
    requires: ['audio_vocal'],
    avqi_compatible: false,
    estimated_duration: 'A definir',
    metrics_enabled: ['f0'],
    metrics_disabled: ['jitter', 'shimmer', 'hnr', 'cpps', 'avqi', 'formants'],
  },
];

interface TaskProtocolSelectorProps {
  selectedTask: string | null;
  onSelect: (taskId: string) => void;
  hasVocal: boolean;
  hasHabla: boolean;
  disabled?: boolean;
}

export default function TaskProtocolSelector({ selectedTask, onSelect, hasVocal, hasHabla, disabled }: TaskProtocolSelectorProps) {
  const [expanded, setExpanded] = useState(true);
  const selected = VOCAL_TASKS.find(t => t.id === selectedTask);

  const canUseTask = (task: VocalTask): { ok: boolean; reason?: string } => {
    if (task.requires.includes('audio_vocal') && !hasVocal) return { ok: false, reason: 'Requiere audio de vocal sostenida' };
    if (task.requires.includes('audio_habla') && !hasHabla) return { ok: false, reason: 'Requiere audio de habla continua' };
    return { ok: true };
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl shadow-xl overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/30 transition-colors">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-sky-400" />
          <span className="text-sm font-bold text-slate-100">Protocolo de Evaluación</span>
        </div>
        <div className="flex items-center gap-2">
          {selected ? (
            <span className="text-[10px] text-emerald-400 font-medium">{selected.name}</span>
          ) : (
            <span className="text-[10px] text-amber-400 font-medium">Sin seleccionar</span>
          )}
          {expanded ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5">
          {!selected && (
            <div className="mb-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-300">
                Seleccione el protocolo de evaluación antes de analizar. Esto determina qué métricas serán calculadas y si el AVQI es aplicable.
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {VOCAL_TASKS.map((task) => {
              const { ok: canUse, reason } = canUseTask(task);
              const isSelected = selectedTask === task.id;
              const Icon = task.icon;
              return (
                <button
                  key={task.id}
                  onClick={() => canUse && !disabled && onSelect(task.id)}
                  disabled={!canUse || disabled}
                  className={`text-left p-3 rounded-xl border-2 transition-all ${
                    isSelected
                      ? 'border-sky-500 bg-sky-500/10 ring-1 ring-sky-500/20'
                      : canUse
                        ? 'border-slate-700/50 bg-slate-800/30 hover:border-slate-600 hover:bg-slate-800/50'
                        : 'border-slate-800/30 bg-slate-900/30 opacity-50 cursor-not-allowed'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`p-1.5 rounded-lg ${isSelected ? 'bg-sky-500/20 text-sky-400' : 'bg-slate-800 text-slate-400'}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-bold ${isSelected ? 'text-sky-300' : 'text-slate-200'}`}>{task.name}</span>
                        {task.avqi_compatible && (
                          <span className="px-1.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-[9px] text-emerald-400 font-medium">
                            AVQI
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-slate-400 mt-0.5 line-clamp-2">{task.description}</p>
                      {!canUse && reason && (
                        <div className="mt-1 text-[9px] text-red-400 flex items-center gap-1">
                          <Info className="w-2.5 h-2.5" /> {reason}
                        </div>
                      )}
                      <div className="mt-1 flex gap-1 flex-wrap">
                        <span className="text-[8px] text-slate-500 bg-slate-800/50 px-1.5 py-0.5 rounded">
                          {task.estimated_duration}
                        </span>
                        {task.metrics_disabled.length > 0 && (
                          <span className="text-[8px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                            Sin {task.metrics_disabled.join(', ')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
