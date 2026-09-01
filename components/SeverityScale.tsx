import React from 'react';

export type SeverityLevel = 0 | 1 | 2 | 3;

interface SeverityScaleProps {
  value: number | string | null | undefined;
  level: SeverityLevel;
  label: string;
  reference: string;
  unit?: string;
  direction?: 'lower_better' | 'higher_better';
  compact?: boolean;
}

const LEVEL_CONFIG: Record<SeverityLevel, { bg: string; border: string; text: string; badge: string; bar: string; ariaLabel: string }> = {
  0: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-400', badge: 'bg-emerald-500/20 text-emerald-300', bar: 'bg-emerald-500', ariaLabel: 'Normal' },
  1: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/40', text: 'text-yellow-400', badge: 'bg-yellow-500/20 text-yellow-300', bar: 'bg-yellow-500', ariaLabel: 'Leve' },
  2: { bg: 'bg-orange-500/10', border: 'border-orange-500/40', text: 'text-orange-400', badge: 'bg-orange-500/20 text-orange-300', bar: 'bg-orange-500', ariaLabel: 'Moderado' },
  3: { bg: 'bg-red-500/10', border: 'border-red-500/40', text: 'text-red-400', badge: 'bg-red-500/20 text-red-300', bar: 'bg-red-500', ariaLabel: 'Marcado' },
};

const LEVEL_LABELS: Record<SeverityLevel, string> = {
  0: 'Normal',
  1: 'Leve',
  2: 'Moderado',
  3: 'Marcado',
};

function getBarPercent(level: SeverityLevel): number {
  return ((level + 1) / 4) * 100;
}

export default function SeverityScale({ value, level, label, reference, unit = '', compact = false }: SeverityScaleProps) {
  const config = LEVEL_CONFIG[level];
  const levelLabel = LEVEL_LABELS[level];
  const isNA = value === null || value === undefined || value === 'N/D' || value === 'N/A' || value === 'NO CALCULABLE';

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border ${config.bg} ${config.border} transition-all duration-300`} role="status" aria-label={`${label}: ${isNA ? 'No disponible' : `${value}${unit} - ${config.ariaLabel}`}`}>
        <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-[10px] font-bold ${config.badge}`}>
          {isNA ? '—' : level}
        </span>
        <span className="text-xs text-slate-300 font-medium">{label}</span>
        {!isNA && <span className={`text-xs font-semibold ${config.text}`}>{value}{unit}</span>}
      </div>
    );
  }

  return (
    <div className={`rounded-xl border p-3.5 ${config.bg} ${config.border} transition-all duration-500 ease-out`} role="group" aria-label={`Parámetro: ${label}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold ${config.badge} shadow-sm`}>
            {isNA ? '—' : level}
          </span>
          <span className="text-sm font-semibold text-slate-200">{label}</span>
        </div>
        <span className={`text-lg font-bold tabular-nums ${isNA ? 'text-slate-500' : config.text}`}>
          {isNA ? 'N/D' : value}
          {!isNA && <span className="text-xs font-normal ml-0.5">{unit}</span>}
        </span>
      </div>

      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full ${config.bar} transition-all duration-700 ease-out`}
          style={{ width: `${isNA ? 0 : getBarPercent(level)}%` }}
        />
      </div>

      <div className="flex items-center justify-between">
        <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded ${config.badge}`}>
          {isNA ? 'No disponible' : `${levelLabel}`}
        </span>
        <span className="text-[10px] text-slate-500">
          Ref: {reference}
        </span>
      </div>
    </div>
  );
}

export function getSeverityLevel(
  value: number | null | undefined,
  thresholds: [number, number, number],
  direction: 'lower_better' | 'higher_better' = 'lower_better'
): SeverityLevel {
  if (value === null || value === undefined || isNaN(value)) return 0;
  if (direction === 'lower_better') {
    if (value <= thresholds[0]) return 0;
    if (value <= thresholds[1]) return 1;
    if (value <= thresholds[2]) return 2;
    return 3;
  } else {
    if (value >= thresholds[0]) return 0;
    if (value >= thresholds[1]) return 1;
    if (value >= thresholds[2]) return 2;
    return 3;
  }
}

export function getSeverityFromBackend(backendLevel: string): SeverityLevel {
  switch (backendLevel?.toLowerCase()) {
    case 'normal': return 0;
    case 'leve': return 1;
    case 'moderado': return 2;
    case 'marcado': return 3;
    default: return 0;
  }
}
