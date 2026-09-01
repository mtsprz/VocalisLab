import React, { useState } from 'react';
import { AlertCircle, Info, ChevronDown, ChevronRight, CheckCircle2, AlertTriangle, XCircle, Minus } from 'lucide-react';

export type SeverityLevel = 0 | 1 | 2 | 3 | null;
export type SeverityDirection = 'lower_is_better' | 'higher_is_better';
export type CalculationStatus = 'valid' | 'warning' | 'failed' | 'not_calculated' | 'suspicious';

export interface MetricData {
  metric: string;
  raw_value: number | null;
  display_value: string;
  unit: string;
  source: string;
  calculation_status: CalculationStatus;
  validation_status: 'valid' | 'warning' | 'invalid';
  reference_source: string;
  severity_rule_version: string;
  error_message?: string;
  severity?: SeverityLevel;
  severity_label?: string;
  direction: SeverityDirection;
  clinical_note?: string;
}

const SEVERITY_CONFIG = {
  0: {
    bg: 'bg-emerald-50', border: 'border-emerald-300', indicator: 'bg-emerald-500',
    badge: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    bar: 'bg-emerald-400', text: 'text-emerald-900', label: 'Normal',
    icon: CheckCircle2, ring: 'ring-emerald-200',
  },
  1: {
    bg: 'bg-amber-50', border: 'border-amber-300', indicator: 'bg-amber-500',
    badge: 'bg-amber-100 text-amber-800 border-amber-200',
    bar: 'bg-amber-400', text: 'text-amber-900', label: 'Vigilancia',
    icon: AlertTriangle, ring: 'ring-amber-200',
  },
  2: {
    bg: 'bg-orange-50', border: 'border-orange-300', indicator: 'bg-orange-500',
    badge: 'bg-orange-100 text-orange-800 border-orange-200',
    bar: 'bg-orange-400', text: 'text-orange-900', label: 'Moderado',
    icon: AlertTriangle, ring: 'ring-orange-200',
  },
  3: {
    bg: 'bg-red-50', border: 'border-red-300', indicator: 'bg-red-500',
    badge: 'bg-red-100 text-red-800 border-red-200',
    bar: 'bg-red-400', text: 'text-red-900', label: 'Marcado',
    icon: XCircle, ring: 'ring-red-200',
  },
};

const STATUS_CONFIG = {
  valid: { icon: CheckCircle2, color: 'text-emerald-400', label: 'Validado' },
  warning: { icon: AlertTriangle, color: 'text-amber-400', label: 'Advertencia' },
  failed: { icon: XCircle, color: 'text-red-400', label: 'Error' },
  not_calculated: { icon: Minus, color: 'text-slate-400', label: 'No calculado' },
  suspicious: { icon: AlertCircle, color: 'text-orange-400', label: 'Sospechoso' },
};

function getSeverityFromValue(
  value: number | null,
  thresholds: [number, number, number],
  direction: SeverityDirection
): SeverityLevel {
  if (value === null || value === undefined || isNaN(value)) return null;
  if (direction === 'lower_is_better') {
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

function getBarPosition(level: SeverityLevel, value: number | null, thresholds: [number, number, number]): number {
  if (level === null || value === null) return 0;
  const min = 0;
  const max = thresholds[2] * 1.5;
  return Math.min(Math.max((value / max) * 100, 2), 98);
}

interface MetricSeverityCardProps {
  data: MetricData;
  thresholds: [number, number, number];
  compact?: boolean;
  showDetail?: boolean;
  onDetailClick?: () => void;
  className?: string;
}

export default function MetricSeverityCard({
  data,
  thresholds,
  compact = false,
  showDetail = false,
  onDetailClick,
  className = '',
}: MetricSeverityCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const level = data.severity ?? getSeverityFromValue(data.raw_value, thresholds, data.direction);
  const config = level !== null ? SEVERITY_CONFIG[level] : null;
  const statusConfig = STATUS_CONFIG[data.calculation_status];
  const StatusIcon = statusConfig.icon;
  const SeverityIcon = config?.icon ?? Minus;
  const barPos = getBarPosition(level, data.raw_value, thresholds);

  const isUnavailable = data.raw_value === null || data.calculation_status === 'not_calculated' || data.calculation_status === 'failed';

  if (compact) {
    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${
        isUnavailable ? 'bg-slate-50 border-slate-200' : `${config?.bg} ${config?.border}`
      } ${className}`}>
        <div className={`w-1 h-8 rounded-full ${isUnavailable ? 'bg-slate-300' : config?.indicator}`} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-slate-600 truncate">{data.metric}</div>
          <div className={`text-sm font-bold ${isUnavailable ? 'text-slate-400' : config?.text}`}>
            {data.display_value}
            {data.unit && <span className="text-xs font-normal ml-0.5">{data.unit}</span>}
          </div>
        </div>
        {level !== null && (
          <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold border ${config?.badge}`}>
            <SeverityIcon className="w-3 h-3" />
            {level}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={`relative rounded-xl border-2 transition-all duration-300 ${
        isUnavailable
          ? 'bg-slate-50 border-slate-200'
          : `${config?.bg} ${config?.border} ring-1 ${config?.ring}`
      } hover:shadow-md ${className}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* Severity indicator bar */}
      <div className={`absolute top-0 left-0 w-1.5 h-full rounded-l-xl ${isUnavailable ? 'bg-slate-300' : config?.indicator}`} />

      <div className="pl-5 pr-4 py-4">
        {/* Header row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-0.5">
              {data.metric}
            </div>
            <div className={`text-2xl font-bold tracking-tight ${isUnavailable ? 'text-slate-400' : config?.text}`}>
              {isUnavailable ? (
                <span className="text-base">No disponible</span>
              ) : (
                <>
                  {data.display_value}
                  {data.unit && <span className="text-sm font-normal ml-1 text-slate-500">{data.unit}</span>}
                </>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end gap-1">
            {level !== null && (
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border ${config?.badge}`}>
                <SeverityIcon className="w-3.5 h-3.5" />
                <span>{level}</span>
                <span className="font-normal opacity-75">— {config?.label}</span>
              </div>
            )}
            <div className={`flex items-center gap-1 text-[10px] ${statusConfig.color}`}>
              <StatusIcon className="w-3 h-3" />
              <span>{statusConfig.label}</span>
            </div>
          </div>
        </div>

        {/* Progress bar */}
        {!isUnavailable && (
          <div className="mb-2">
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${config?.bar}`}
                style={{ width: `${barPos}%` }}
              />
            </div>
            <div className="flex justify-between mt-0.5">
              <span className="text-[9px] text-slate-400">0</span>
              <span className="text-[9px] text-slate-400">{thresholds[2]}</span>
            </div>
          </div>
        )}

        {/* Reference and source */}
        <div className="flex items-center justify-between text-[10px] text-slate-500">
          <span className="flex items-center gap-1">
            <Info className="w-3 h-3" />
            Ref: {data.reference_source}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            {data.source}
          </span>
        </div>

        {/* Error message */}
        {data.error_message && (
          <div className="mt-2 px-2 py-1 bg-red-50 border border-red-200 rounded text-[10px] text-red-700">
            {data.error_message}
          </div>
        )}

        {/* Clinical note */}
        {data.clinical_note && (
          <div className="mt-2 px-2 py-1 bg-blue-50 border border-blue-200 rounded text-[10px] text-blue-700 italic">
            {data.clinical_note}
          </div>
        )}

        {/* Expandable detail */}
        {showDetail && (
          <button
            onClick={() => { setExpanded(!expanded); onDetailClick?.(); }}
            className="mt-2 flex items-center gap-1 text-[10px] text-sky-600 hover:text-sky-800 font-medium"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            Ver detalle
          </button>
        )}

        {expanded && (
          <div className="mt-2 p-2 bg-white/60 rounded-lg border border-slate-100 text-[10px] space-y-1">
            <div><span className="font-medium text-slate-600">Valor crudo:</span> {String(data.raw_value)}</div>
            <div><span className="font-medium text-slate-600">Estado cálculo:</span> {data.calculation_status}</div>
            <div><span className="font-medium text-slate-600">Estado validación:</span> {data.validation_status}</div>
            <div><span className="font-medium text-slate-600">Regla severidad:</span> v{data.severity_rule_version}</div>
            <div><span className="font-medium text-slate-600">Dirección:</span> {data.direction === 'lower_is_better' ? 'Menor es mejor' : 'Mayor es mejor'}</div>
          </div>
        )}
      </div>

      {/* Tooltip */}
      {showTooltip && data.clinical_note && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-900 text-white text-xs rounded-lg shadow-lg max-w-xs pointer-events-none">
          {data.clinical_note}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 w-2 h-2 bg-slate-900 rotate-45" />
        </div>
      )}
    </div>
  );
}

export { getSeverityFromValue, SEVERITY_CONFIG, STATUS_CONFIG };
