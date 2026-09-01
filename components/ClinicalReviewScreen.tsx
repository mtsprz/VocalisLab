import React, { useState } from 'react';
import {
  Shield, Activity, Mic, FileText, AlertTriangle, CheckCircle2, XCircle, Minus,
  ChevronDown, ChevronRight, Clock, Hash, Cpu, BarChart3, Eye, Download,
  RefreshCw, FileJson, FileSpreadsheet, Image, Settings, Volume2
} from 'lucide-react';
import MetricSeverityCard, { MetricData } from './MetricSeverityCard';

interface AudioInfo {
  valid: boolean;
  sample_rate_hz: number;
  duration_s: number;
  channels: number;
  rms: number;
  peak: number;
  clipping_pct: number;
  file_hash_sha256: string;
  issues: string[];
}

interface ToolStatus {
  name: string;
  status: 'ok' | 'warning' | 'error' | 'not_executed';
  message?: string;
}

interface ClinicalReviewProps {
  audioInfo: AudioInfo;
  metrics: any;
  avqiComponents: any;
  tools: ToolStatus[];
  timestamp: string;
  engineVersion: string;
  scriptVersion: string;
  fileHash: string;
  harmonics: any[];
  formants: any;
  ltas: any;
  spectral: any;
  modo: string;
  onViewJson?: () => void;
  onViewCsv?: () => void;
  onViewGraphs?: () => void;
  onRecalculate?: () => void;
  onApprove?: () => void;
  onDownloadPreliminar?: () => void;
}

const METRIC_THRESHOLDS: Record<string, [number, number, number]> = {
  jitter_pct: [1.04, 2.0, 3.0],
  shimmer_pct: [3.81, 5.0, 7.0],
  shimmer_db: [0.5, 1.0, 2.0],
  hnr_db: [20, 15, 10],
  cpps_db: [5.5, 3.0, 1.0],
};

const METRIC_DIRECTIONS: Record<string, 'lower_is_better' | 'higher_is_better'> = {
  jitter_pct: 'lower_is_better',
  shimmer_pct: 'lower_is_better',
  shimmer_db: 'lower_is_better',
  hnr_db: 'higher_is_better',
  cpps_db: 'higher_is_better',
};

const METRIC_CLINICAL_NOTES: Record<string, string> = {
  jitter_pct: 'Variación de frecuencia fundamental entre ciclos glóticos. Valores altos indican irregularidad en la vibración de las cuerdas vocales.',
  shimmer_pct: 'Variación de amplitud entre ciclos glóticos. Valores altos indican inestabilidad en la intensidad de la voz.',
  shimmer_db: 'Shimmer expresado en decibelios. Relacionado con la percepción de rugosidad vocal.',
  hnr_db: 'Relación armónicos-ruido. Valores bajos indican mayor presencia de ruido en la señal, asociado a disfonía.',
  cpps_db: 'Prominencia del pico cefálico. Valores bajos se asocian con voz soplada y menor calidad cefálica.',
};

export default function ClinicalReviewScreen({
  audioInfo, metrics, avqiComponents, tools, timestamp, engineVersion, scriptVersion,
  fileHash, harmonics, formants, ltas, spectral, modo,
  onViewJson, onViewCsv, onViewGraphs, onRecalculate, onApprove, onDownloadPreliminar,
}: ClinicalReviewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['validity', 'metrics']));
  const [exceptionReason, setExceptionReason] = useState('');

  const toggle = (s: string) => {
    const next = new Set(expandedSections);
    next.has(s) ? next.delete(s) : next.add(s);
    setExpandedSections(next);
  };

  const audioValid = audioInfo.valid;
  const hasIssues = audioInfo.issues.length > 0;
  const hasBlocking = !audioValid || tools.some(t => t.status === 'error');
  const canApprove = !hasBlocking || exceptionReason.trim().length > 0;

  const audioStatus = audioValid
    ? (hasIssues ? { label: 'Apto con advertencias', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', icon: AlertTriangle }
                  : { label: 'Apto para análisis', color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', icon: CheckCircle2 })
    : { label: 'No apto', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: XCircle };

  const AudioStatusIcon = audioStatus.icon;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-sky-400" />
          <h2 className="text-lg font-bold text-slate-100">Control Clínico</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${audioStatus.bg} ${audioStatus.color}`}>
            <AudioStatusIcon className="w-3 h-3 inline mr-1" />
            {audioStatus.label}
          </span>
          <span className="text-[10px] text-slate-500 font-mono">{timestamp}</span>
        </div>
      </div>

      {/* BLOCK A: Audio Validity */}
      <SectionBlock
        title="A. Validez del Audio"
        icon={Volume2}
        expanded={expandedSections.has('validity')}
        onToggle={() => toggle('validity')}
        badge={`${audioValid ? 'Válido' : 'Inválido'} — ${tools.filter(t => t.status === 'ok').length}/${tools.length} herramientas`}
        badgeColor={audioValid ? 'text-emerald-400' : 'text-red-400'}
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <InfoBox label="Estado" value={audioValid ? 'Válido' : 'Inválido'} ok={audioValid} />
          <InfoBox label="Sample Rate" value={`${audioInfo.sample_rate_hz} Hz`} ok={audioInfo.sample_rate_hz >= 44100} />
          <InfoBox label="Duración" value={`${audioInfo.duration_s}s`} ok={audioInfo.duration_s >= 1.0} />
          <InfoBox label="Canales" value={audioInfo.channels === 1 ? 'Mono' : `${audioInfo.channels}ch`} ok={audioInfo.channels === 1} />
          <InfoBox label="RMS" value={String(audioInfo.rms)} ok={audioInfo.rms >= 0.01} />
          <InfoBox label="Pico" value={String(audioInfo.peak)} ok={audioInfo.peak >= 0.01} />
          <InfoBox label="Clipping" value={`${audioInfo.clipping_pct}%`} ok={audioInfo.clipping_pct < 1} warning={audioInfo.clipping_pct >= 0.5} />
          <InfoBox label="Hash" value={`${fileHash.slice(0, 12)}...`} ok={true} mono />
        </div>
        {hasIssues && (
          <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-xl">
            <div className="text-xs font-semibold text-red-400 mb-1">Problemas detectados:</div>
            {audioInfo.issues.map((issue, i) => (
              <div key={i} className="text-[11px] text-red-300 flex items-start gap-1.5">
                <span className="text-red-500 mt-0.5">•</span>
                {issue}
              </div>
            ))}
          </div>
        )}
      </SectionBlock>

      {/* BLOCK B: Main Metrics */}
      <SectionBlock
        title="B. Métricas Principales"
        icon={Activity}
        expanded={expandedSections.has('metrics')}
        onToggle={() => toggle('metrics')}
        badge={`${countValidMetrics(metrics)} métricas calculadas`}
        badgeColor="text-sky-400"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {buildMetricCards(metrics, avqiComponents).map((card, i) => (
            <MetricSeverityCard key={i} data={card.data} thresholds={card.thresholds} showDetail />
          ))}
        </div>
        {avqiComponents && (
          <div className="mt-4 p-4 bg-slate-800/50 border border-slate-700/50 rounded-xl">
            <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">AVQI v03.01 — Componentes</div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
              {[
                { label: 'CPPs', val: avqiComponents.cpps_db, unit: 'dB' },
                { label: 'HNR', val: avqiComponents.hnr_db, unit: 'dB' },
                { label: 'Shimmer local', val: avqiComponents.shimmer_local_pct, unit: '%' },
                { label: 'Shimmer dB', val: avqiComponents.shimmer_local_db, unit: 'dB' },
                { label: 'Spectral Slope', val: avqiComponents.spectral_slope, unit: 'dB/oct' },
                { label: 'Spectral Tilt', val: avqiComponents.spectral_tilt, unit: 'dB' },
              ].map((c) => (
                <div key={c.label} className="flex justify-between px-2 py-1.5 bg-slate-900/50 rounded-lg">
                  <span className="text-slate-400">{c.label}</span>
                  <span className={`font-mono font-bold ${c.val === null ? 'text-red-400' : 'text-slate-200'}`}>
                    {c.val === null ? 'N/D' : `${c.val} ${c.unit}`}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs">
              {avqiComponents.calculable ? (
                <span className="text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  AVQI = {avqiComponents.avqi}
                </span>
              ) : (
                <span className="text-red-400 flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" />
                  AVQI no calculable
                </span>
              )}
              {avqiComponents.error && (
                <span className="text-amber-400 text-[10px]">— {avqiComponents.error}</span>
              )}
            </div>
          </div>
        )}
      </SectionBlock>

      {/* BLOCK C: Graphs */}
      <SectionBlock
        title="C. Gráficos"
        icon={BarChart3}
        expanded={expandedSections.has('graphs')}
        onToggle={() => toggle('graphs')}
        badge={`${harmonics.length > 0 ? 'Armónicos, ' : ''}${ltas?.ltas_mean_db != null ? 'LTAS, ' : ''}Espectrograma`}
        badgeColor="text-purple-400"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {harmonics.length > 0 && (
            <GraphCard title="Espectro Armónico" subtitle="H1-H10">
              <MiniHarmonicsChart harmonics={harmonics} />
            </GraphCard>
          )}
          {ltas?.ltas_mean_db != null && (
            <GraphCard title="LTAS" subtitle="Long-Term Average Spectrum">
              <MiniLtasChart ltas={ltas} />
            </GraphCard>
          )}
          <GraphCard title="Resumen" subtitle="Métricas normalizadas">
            <MiniMetricsBar metrics={metrics} />
          </GraphCard>
          {formants?.f1_hz && (
            <GraphCard title="Formantes" subtitle="F1-F4">
              <MiniFormantsChart formants={formants} />
            </GraphCard>
          )}
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={onViewGraphs} className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors">
            <Image className="w-3.5 h-3.5" /> Ver gráficos completos
          </button>
        </div>
      </SectionBlock>

      {/* BLOCK D: Audit */}
      <SectionBlock
        title="D. Auditoría"
        icon={Settings}
        expanded={expandedSections.has('audit')}
        onToggle={() => toggle('audit')}
        badge={`${tools.filter(t => t.status === 'ok').length}/${tools.length} OK`}
        badgeColor="text-emerald-400"
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center mb-3">
          {[
            { label: 'Motor', value: engineVersion },
            { label: 'Script', value: scriptVersion },
            { label: 'Hash Audio', value: fileHash?.slice(0, 12) + '...' },
            { label: 'Fecha', value: timestamp?.slice(0, 19) },
          ].map((item) => (
            <div key={item.label} className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-2">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider">{item.label}</div>
              <div className="text-xs text-slate-300 font-mono mt-0.5 truncate">{item.value}</div>
            </div>
          ))}
        </div>
        <div className="space-y-1.5">
          {tools.map((tool) => {
            const cfg = {
              ok: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30', label: 'Correcto' },
              warning: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30', label: 'Advertencia' },
              error: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', label: 'Error' },
              not_executed: { icon: Minus, color: 'text-slate-500', bg: 'bg-slate-800/50 border-slate-700/50', label: 'No ejecutado' },
            }[tool.status];
            const Icon = cfg.icon;
            return (
              <div key={tool.name} className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${cfg.bg}`}>
                <Icon className={`w-4 h-4 ${cfg.color} shrink-0`} />
                <span className="text-xs text-slate-200 flex-1">{tool.name}</span>
                <span className={`text-[10px] font-medium ${cfg.color}`}>{cfg.label}</span>
                {tool.message && <span className="text-[10px] text-slate-400 max-w-[200px] truncate">{tool.message}</span>}
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={onViewJson} className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors">
            <FileJson className="w-3.5 h-3.5" /> Ver JSON
          </button>
          <button onClick={onViewCsv} className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors">
            <FileSpreadsheet className="w-3.5 h-3.5" /> Descargar CSV
          </button>
          <button onClick={onRecalculate} className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> Recalcular
          </button>
        </div>
      </SectionBlock>

      {/* Blocking issues */}
      {hasBlocking && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl space-y-2">
          <div className="flex items-center gap-2 text-red-400 font-semibold text-sm">
            <XCircle className="w-4 h-4" />
            Bloqueos — No se puede generar informe
          </div>
          {!audioValid && <div className="text-xs text-red-300">• El audio no es válido para análisis clínico</div>}
          {tools.filter(t => t.status === 'error').map((t, i) => (
            <div key={i} className="text-xs text-red-300">• {t.name}: {t.message}</div>
          ))}
          <div className="mt-2">
            <input type="text" value={exceptionReason} onChange={(e) => setExceptionReason(e.target.value)}
              placeholder="Motivo de la excepción (requerido para aprobar con errores)"
              className="w-full px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-yellow-500" />
          </div>
        </div>
      )}

      {/* Approve */}
      <button onClick={onApprove} disabled={!canApprove}
        className={`w-full py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all ${
          canApprove ? 'bg-gradient-to-r from-emerald-500 to-green-600 hover:from-emerald-400 hover:to-green-500 text-white shadow-lg shadow-emerald-500/20' : 'bg-slate-800 text-slate-500 cursor-not-allowed'
        }`}>
        <CheckCircle2 className="w-4 h-4" />
        {hasBlocking ? 'Aprobar con excepción' : 'Aprobar y generar informe'}
      </button>
    </div>
  );
}

function SectionBlock({ title, icon: Icon, expanded, onToggle, badge, badgeColor, children }: {
  title: string; icon: any; expanded: boolean; onToggle: () => void; badge: string; badgeColor: string; children: React.ReactNode;
}) {
  return (
    <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl shadow-xl overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/30 transition-colors">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-sky-400" />
          <span className="text-sm font-bold text-slate-100">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-medium ${badgeColor}`}>{badge}</span>
          {expanded ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
        </div>
      </button>
      {expanded && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}

function InfoBox({ label, value, ok, warning, mono }: { label: string; value: string; ok: boolean; warning?: boolean; mono?: boolean }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-2.5">
      <div className="text-[10px] text-slate-500 uppercase tracking-wider">{label}</div>
      <div className={`text-xs font-bold mt-0.5 ${ok ? 'text-emerald-300' : warning ? 'text-amber-300' : 'text-red-300'} ${mono ? 'font-mono' : ''}`}>
        {value}
      </div>
    </div>
  );
}

function GraphCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3">
      <div className="text-xs font-semibold text-slate-300 mb-1">{title}</div>
      <div className="text-[10px] text-slate-500 mb-2">{subtitle}</div>
      {children}
    </div>
  );
}

function MiniHarmonicsChart({ harmonics }: { harmonics: any[] }) {
  const maxAmp = Math.max(...harmonics.map(h => h.amplitude_db), 1);
  return (
    <div className="flex items-end gap-1 h-24">
      {harmonics.slice(0, 8).map((h, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
          <div className="text-[8px] text-slate-400">{h.amplitude_db.toFixed(0)}</div>
          <div className="w-full bg-sky-400 rounded-t" style={{ height: `${(h.amplitude_db / maxAmp) * 70}px` }} />
          <div className="text-[8px] text-slate-500">H{h.number}</div>
        </div>
      ))}
    </div>
  );
}

function MiniLtasChart({ ltas }: { ltas: any }) {
  const items = [
    { label: 'Media', val: ltas.ltas_mean_db, color: '#3b82f6' },
    { label: 'Pendiente', val: ltas.ltas_slope_db, color: '#22c55e' },
    { label: 'Pico', val: ltas.ltas_peak_height_db, color: '#f97316' },
    { label: 'Desvío', val: ltas.ltas_stdev_db, color: '#8b5cf6' },
  ];
  return (
    <div className="space-y-1.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <span className="text-[10px] text-slate-400 w-14">{item.label}</span>
          <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${Math.min(Math.abs(item.val || 0) / 50 * 100, 100)}%`, backgroundColor: item.color }} />
          </div>
          <span className="text-[10px] text-slate-300 w-10 text-right font-mono">{item.val?.toFixed(1) ?? 'N/D'}</span>
        </div>
      ))}
    </div>
  );
}

function MiniMetricsBar({ metrics }: { metrics: any }) {
  const items = [
    { label: 'F0', val: metrics.f0_mean || 0, norm: 300, color: '#3b82f6' },
    { label: 'Jitter', val: metrics.jitter_pct || 0, norm: 5, color: '#ef4444' },
    { label: 'Shimmer', val: metrics.shimmer_pct || 0, norm: 10, color: '#f97316' },
    { label: 'HNR', val: metrics.hnr_db || 0, norm: 30, color: '#22c55e' },
    { label: 'CPPS', val: metrics.cpps_db || 0, norm: 15, color: '#8b5cf6' },
  ];
  return (
    <div className="space-y-1.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <span className="text-[10px] text-slate-400 w-14">{item.label}</span>
          <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${Math.min((item.val / item.norm) * 100, 100)}%`, backgroundColor: item.color }} />
          </div>
          <span className="text-[10px] text-slate-300 w-10 text-right font-mono">{item.val.toFixed(1)}</span>
        </div>
      ))}
    </div>
  );
}

function MiniFormantsChart({ formants }: { formants: any }) {
  const items = [
    { label: 'F1', val: formants.f1_hz, color: '#ef4444' },
    { label: 'F2', val: formants.f2_hz, color: '#f97316' },
    { label: 'F3', val: formants.f3_hz, color: '#eab308' },
    { label: 'F4', val: formants.f4_hz, color: '#22c55e' },
  ].filter(f => f.val && f.val > 0);
  return (
    <div className="flex items-end gap-2 h-20">
      {items.map((f) => (
        <div key={f.label} className="flex-1 flex flex-col items-center gap-0.5">
          <div className="text-[8px] text-slate-400">{f.val?.toFixed(0)}</div>
          <div className="w-full rounded-t" style={{ height: `${Math.min((f.val || 0) / 4000 * 60, 60)}px`, backgroundColor: f.color }} />
          <div className="text-[8px] text-slate-500">{f.label}</div>
        </div>
      ))}
    </div>
  );
}

function countValidMetrics(metrics: any): number {
  let count = 0;
  if (metrics.f0_mean) count++;
  if (metrics.jitter_pct != null) count++;
  if (metrics.shimmer_pct != null) count++;
  if (metrics.hnr_db != null) count++;
  if (metrics.cpps_db != null) count++;
  return count;
}

function buildMetricCards(metrics: any, avqi: any): { data: MetricData; thresholds: [number, number, number] }[] {
  const cards: { data: MetricData; thresholds: [number, number, number] }[] = [];

  if (metrics.f0_mean != null) {
    cards.push({
      data: {
        metric: 'F0 media', raw_value: metrics.f0_mean, display_value: String(metrics.f0_mean),
        unit: 'Hz', source: 'Praat / Parselmouth',
        calculation_status: 'valid', validation_status: 'valid',
        reference_source: 'Variable (edad, sexo)', severity_rule_version: '1.0',
        direction: 'lower_is_better', severity: null,
        clinical_note: 'Frecuencia fundamental media. Los valores de referencia dependen de edad, sexo y protocolo.',
      },
      thresholds: [0, 0, 0],
    });
  }

  const metricMap: Record<string, string> = {
    jitter_pct: 'Jitter local', shimmer_pct: 'Shimmer local', shimmer_db: 'Shimmer dB',
    hnr_db: 'HNR', cpps_db: 'CPPS',
  };

  for (const [key, label] of Object.entries(metricMap)) {
    const val = metrics[key];
    if (val != null) {
      cards.push({
        data: {
          metric: label, raw_value: val, display_value: String(val),
          unit: key.includes('db') ? 'dB' : '%', source: 'Praat / Parselmouth',
          calculation_status: 'valid', validation_status: 'valid',
          reference_source: key === 'hnr_db' ? '> 20 dB' : key === 'cpps_db' ? '> 5.5 dB' : key === 'shimmer_db' ? '< 0.5 dB' : key === 'jitter_pct' ? '< 1.04%' : '< 3.81%',
          severity_rule_version: '1.0',
          direction: METRIC_DIRECTIONS[key] || 'lower_is_better',
          clinical_note: METRIC_CLINICAL_NOTES[key],
        },
        thresholds: METRIC_THRESHOLDS[key] || [0, 0, 0],
      });
    }
  }

  return cards;
}
