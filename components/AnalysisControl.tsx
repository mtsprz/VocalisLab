import React, { useState } from 'react';
import {
  CheckCircle2, AlertTriangle, XCircle, Minus, Eye, FileJson, FileSpreadsheet, Image, RefreshCw, Download, Edit3, CheckSquare, Shield
} from 'lucide-react';

interface ToolStatus {
  name: string;
  status: 'ok' | 'warning' | 'error' | 'not_executed';
  message?: string;
}

interface AnalysisControlProps {
  audioInfo: any;
  metrics: any;
  avqiComponents: any;
  tools: ToolStatus[];
  timestamp: string;
  engineVersion: string;
  scriptVersion: string;
  fileHash: string;
  resultHash?: string;
  rawData?: any;
  jsonExport?: any;
  csvExport?: string;
  onViewRaw?: () => void;
  onViewJson?: () => void;
  onViewCsv?: () => void;
  onViewGraphs?: () => void;
  onRecalculate?: () => void;
  onDownloadPreliminar?: () => void;
  onEdit?: () => void;
  onApprove?: () => void;
  criticalErrors?: string[];
  mandatoryMissing?: string[];
}

const STATUS_CONFIG = {
  ok: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', label: 'Correcto' },
  warning: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', label: 'Advertencia' },
  error: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'Error' },
  not_executed: { icon: Minus, color: 'text-slate-500', bg: 'bg-slate-800/50', border: 'border-slate-700/50', label: 'No ejecutado' },
};

export default function AnalysisControl({
  audioInfo, metrics, avqiComponents, tools, timestamp, engineVersion, scriptVersion,
  fileHash, resultHash, onViewRaw, onViewJson, onViewCsv, onViewGraphs,
  onRecalculate, onDownloadPreliminar, onEdit, onApprove,
  criticalErrors = [], mandatoryMissing = []
}: AnalysisControlProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>('tools');
  const [exceptionReason, setExceptionReason] = useState('');
  const [showExceptionModal, setShowExceptionModal] = useState(false);

  const hasBlockingIssues = criticalErrors.length > 0 || mandatoryMissing.length > 0;
  const canApprove = !hasBlockingIssues || exceptionReason.trim().length > 0;

  const toggle = (s: string) => setExpandedSection(expandedSection === s ? null : s);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-sky-400" />
          <h2 className="text-lg font-bold text-slate-100">Control de Análisis</h2>
        </div>
        <span className="text-[10px] text-slate-500 font-mono">{timestamp}</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
        {[
          { label: 'Motor', value: engineVersion },
          { label: 'Script', value: scriptVersion },
          { label: 'Hash Audio', value: fileHash?.slice(0, 12) + '...' },
          { label: 'Hash Resultados', value: resultHash?.slice(0, 12) || 'Pendiente' + '...' },
        ].map((item) => (
          <div key={item.label} className="bg-slate-900/60 border border-slate-800 rounded-lg p-2">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider">{item.label}</div>
            <div className="text-xs text-slate-300 font-mono mt-0.5">{item.value}</div>
          </div>
        ))}
      </div>

      <button onClick={() => toggle('audio')} className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-900/60 border border-slate-800 rounded-xl hover:border-slate-700 transition-colors">
        <span className="text-sm font-semibold text-slate-200">Estado del Audio</span>
        <span className={`text-xs ${audioInfo?.valid ? 'text-emerald-400' : 'text-red-400'}`}>
          {audioInfo?.valid ? 'Válido' : 'Inválido'}
        </span>
      </button>
      {expandedSection === 'audio' && audioInfo && (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div><span className="text-slate-500">Formato:</span> <span className="text-slate-200">WAV PCM</span></div>
            <div><span className="text-slate-500">Sample Rate:</span> <span className="text-slate-200">{audioInfo.sample_rate_hz} Hz</span></div>
            <div><span className="text-slate-500">Duración:</span> <span className="text-slate-200">{audioInfo.duration_s}s</span></div>
            <div><span className="text-slate-500">Canales:</span> <span className="text-slate-200">{audioInfo.channels}</span></div>
            <div><span className="text-slate-500">RMS:</span> <span className="text-slate-200">{audioInfo.rms}</span></div>
            <div><span className="text-slate-500">Pico:</span> <span className="text-slate-200">{audioInfo.peak}</span></div>
            <div><span className="text-slate-500">Clipping:</span> <span className={audioInfo.clipping_pct > 0 ? 'text-yellow-400' : 'text-emerald-400'}>{audioInfo.clipping_pct}%</span></div>
            <div><span className="text-slate-500">Hash:</span> <span className="text-slate-200 font-mono">{audioInfo.file_hash_sha256}</span></div>
          </div>
          {audioInfo.issues && audioInfo.issues.length > 0 && (
            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
              {audioInfo.issues.map((issue: string, i: number) => (
                <div key={i} className="text-red-300 text-[11px]">• {issue}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <button onClick={() => toggle('tools')} className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-900/60 border border-slate-800 rounded-xl hover:border-slate-700 transition-colors">
        <span className="text-sm font-semibold text-slate-200">Estado de Herramientas</span>
        <span className="text-xs text-slate-400">{tools.filter(t => t.status === 'ok').length}/{tools.length} OK</span>
      </button>
      {expandedSection === 'tools' && (
        <div className="space-y-1.5">
          {tools.map((tool) => {
            const cfg = STATUS_CONFIG[tool.status];
            const Icon = cfg.icon;
            return (
              <div key={tool.name} className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border ${cfg.bg} ${cfg.border}`}>
                <Icon className={`w-4 h-4 ${cfg.color} shrink-0`} />
                <span className="text-sm text-slate-200 flex-1">{tool.name}</span>
                <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                {tool.message && <span className="text-[10px] text-slate-400 max-w-[200px] truncate">{tool.message}</span>}
              </div>
            );
          })}
        </div>
      )}

      <button onClick={() => toggle('avqi')} className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-900/60 border border-slate-800 rounded-xl hover:border-slate-700 transition-colors">
        <span className="text-sm font-semibold text-slate-200">Estado AVQI</span>
        <span className={`text-xs ${avqiComponents?.calculable ? 'text-emerald-400' : 'text-red-400'}`}>
          {avqiComponents?.calculable ? `AVQI = ${avqiComponents.avqi}` : 'No calculable'}
        </span>
      </button>
      {expandedSection === 'avqi' && avqiComponents && (
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 text-xs space-y-1">
          <div className="grid grid-cols-2 gap-1">
            {Object.entries(avqiComponents).filter(([k]) => !['calculable', 'error'].includes(k)).map(([key, val]) => (
              <div key={key}>
                <span className="text-slate-500">{key}:</span>{' '}
                <span className={`font-mono ${val === null ? 'text-red-400' : 'text-slate-200'}`}>
                  {val === null ? 'N/D' : String(val)}
                </span>
              </div>
            ))}
          </div>
          {avqiComponents.error && (
            <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded text-yellow-300">{avqiComponents.error}</div>
          )}
          {avqiComponents.avqi === 0 && avqiComponents.calculable && (
            <div className="mt-2 p-2 bg-orange-500/10 border border-orange-500/30 rounded text-orange-300">
              AVQI = 0.0 es un valor sospechosamente bajo. Verificar calidad del audio y validez del análisis.
            </div>
          )}
        </div>
      )}

      {(criticalErrors.length > 0 || mandatoryMissing.length > 0) && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl space-y-2">
          <div className="flex items-center gap-2 text-red-400 font-semibold text-sm">
            <XCircle className="w-4 h-4" />
            Bloqueos detectados
          </div>
          {criticalErrors.map((e, i) => <div key={`c${i}`} className="text-xs text-red-300">• {e}</div>)}
          {mandatoryMissing.map((m, i) => <div key={`m${i}`} className="text-xs text-red-300">• Campo obligatorio ausente: {m}</div>)}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {[
          { icon: Eye, label: 'Ver datos crudos', onClick: onViewRaw, disabled: false },
          { icon: FileJson, label: 'Ver JSON', onClick: onViewJson, disabled: false },
          { icon: FileSpreadsheet, label: 'Ver CSV', onClick: onViewCsv, disabled: false },
          { icon: Image, label: 'Ver gráficos', onClick: onViewGraphs, disabled: false },
          { icon: RefreshCw, label: 'Recalcular', onClick: onRecalculate, disabled: false },
          { icon: Download, label: 'Informe preliminar', onClick: onDownloadPreliminar, disabled: false },
          { icon: Edit3, label: 'Editar informe', onClick: onEdit, disabled: false },
        ].map((btn) => (
          <button key={btn.label} onClick={btn.onClick} disabled={btn.disabled}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            <btn.icon className="w-3.5 h-3.5" />
            {btn.label}
          </button>
        ))}
      </div>

      {hasBlockingIssues && (
        <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            <span className="text-xs font-semibold text-yellow-300">Excepción requerida para aprobar</span>
          </div>
          <input type="text" value={exceptionReason} onChange={(e) => setExceptionReason(e.target.value)}
            placeholder="Motivo de la excepción (requerido para aprobar con errores)"
            className="w-full px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-yellow-500" />
        </div>
      )}

      <button onClick={onApprove} disabled={!canApprove}
        className={`w-full py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all ${
          canApprove ? 'bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-400 hover:to-green-500 text-white shadow-lg shadow-emerald-500/20' : 'bg-slate-800 text-slate-500 cursor-not-allowed'
        }`}>
        <CheckSquare className="w-4 h-4" />
        {hasBlockingIssues ? 'Aprobar con excepción' : 'Aprobar informe final'}
      </button>
    </div>
  );
}
