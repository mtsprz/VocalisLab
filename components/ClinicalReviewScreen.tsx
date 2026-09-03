import React, { useState } from 'react';
import {
  Shield, Activity, AlertTriangle, CheckCircle2, XCircle, Minus,
  ChevronDown, ChevronRight, BarChart3,
  RefreshCw, FileJson, FileSpreadsheet, Settings, Volume2, Layers, Cpu
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
  waveform: any;
  spectrogram: any;
  glottalPulses?: number[];
  formantTracks?: any;
  f0Contour: any;
  intensityContour: any;
  classifications: any;
  voxplot?: any;
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
  nhr: [0.1, 0.25, 0.5],
};

const METRIC_DIRECTIONS: Record<string, 'lower_is_better' | 'higher_is_better'> = {
  jitter_pct: 'lower_is_better',
  shimmer_pct: 'lower_is_better',
  shimmer_db: 'lower_is_better',
  hnr_db: 'higher_is_better',
  cpps_db: 'higher_is_better',
  nhr: 'lower_is_better',
};

const METRIC_CLINICAL_NOTES: Record<string, string> = {
  jitter_pct: 'Variación de frecuencia fundamental entre ciclos glóticos. Valores altos indican irregularidad en la vibración de las cuerdas vocales.',
  shimmer_pct: 'Variación de amplitud entre ciclos glóticos. Valores altos indican inestabilidad en la intensidad de la voz.',
  shimmer_db: 'Shimmer expresado en decibelios. Relacionado con la percepción de rugosidad vocal.',
  hnr_db: 'Relación armónicos-ruido. Valores bajos indican mayor presencia de ruido en la señal, asociado a disfonía.',
  cpps_db: 'Prominencia del pico cefálico. Valores bajos se asocian con voz soplada y menor calidad cefálica.',
  nhr: 'Noise-to-Harmonics Ratio. Relación inversa del HNR. Valores altos indican mayor ruido respecto a armónicos.',
};

export default function ClinicalReviewScreen({
  audioInfo, metrics, avqiComponents, tools, timestamp, engineVersion, scriptVersion,
  fileHash, harmonics, formants, ltas, spectral, waveform, spectrogram, glottalPulses = [],
  formantTracks, f0Contour, intensityContour, classifications, voxplot, modo,
  onViewJson, onViewCsv, onViewGraphs, onRecalculate, onApprove, onDownloadPreliminar,
}: ClinicalReviewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['validity', 'metrics', 'graphs']));
  const [exceptionReason, setExceptionReason] = useState('');
  const [activeGraph, setActiveGraph] = useState<string>('praat_editor');

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
  const classif = classifications || {};

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
        title="B. Métricas Bioacústicas Principales"
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
        {/* Classifications */}
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          {classif.titze && classif.titze.titze_type && (
            <div className="p-3 bg-slate-800/50 border border-slate-700/50 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Titze</div>
              <div className="text-sm font-bold text-slate-200">Tipo {classif.titze.titze_type}</div>
              <div className="text-[10px] text-slate-400">{classif.titze.titze_label}</div>
            </div>
          )}
          {classif.yanagihara && classif.yanagihara.yanagihara_grade && (
            <div className="p-3 bg-slate-800/50 border border-slate-700/50 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Yanagihara</div>
              <div className="text-sm font-bold text-slate-200">Grado {classif.yanagihara.yanagihara_grade}</div>
              <div className="text-[10px] text-slate-400">{classif.yanagihara.yanagihara_label}</div>
            </div>
          )}
          {classif.nunez_batalla && classif.nunez_batalla.nunez_batalla_grade && (
            <div className="p-3 bg-slate-800/50 border border-slate-700/50 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Núñez Batalla</div>
              <div className="text-sm font-bold text-slate-200">Grado {classif.nunez_batalla.nunez_batalla_grade}</div>
              <div className="text-[10px] text-slate-400">{classif.nunez_batalla.nunez_batalla_label}</div>
            </div>
          )}
          {classif.cecconello && classif.cecconello.harmonic_loss_pct != null && (
            <div className="p-3 bg-slate-800/50 border border-slate-700/50 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Cecconello</div>
              <div className="text-sm font-bold text-slate-200">{classif.cecconello.harmonic_loss_pct}%</div>
              <div className="text-[10px] text-slate-400">{classif.cecconello.classification}</div>
            </div>
          )}
        </div>
      </SectionBlock>

      {/* BLOCK C: Clinical Graphs */}
      <SectionBlock
        title="C. Gráficos Clínicos (Praat & VOXplot)"
        icon={BarChart3}
        expanded={expandedSections.has('graphs')}
        onToggle={() => toggle('graphs')}
        badge="Praat Editor, VOXplot Profile & Radar, Osciloscopio"
        badgeColor="text-purple-400"
      >
        <div className="flex flex-wrap gap-1.5 mb-4">
          {([
            { id: 'praat_editor', label: 'Praat Sound Editor' },
            { id: 'voxplot_profile', label: 'VOXplot Profile & Radar' },
            { id: 'oscilloscope', label: 'Forma de Onda' },
            { id: 'f0_intensity', label: 'F0 + Intensidad' },
            { id: 'harmonics', label: 'Armónicos H1-H10' },
            { id: 'ltas', label: 'LTAS' },
            { id: 'formants', label: 'Formantes' },
          ] as const).map((g) => (
            <button key={g.id} onClick={() => setActiveGraph(g.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeGraph === g.id ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30' : 'bg-slate-800/50 text-slate-400 hover:text-slate-200 border border-slate-700/50'}`}>
              {g.label}
            </button>
          ))}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          {activeGraph === 'praat_editor' && (
            <PraatEditorView
              waveform={waveform}
              spectrogram={spectrogram}
              glottalPulses={glottalPulses}
              f0Contour={f0Contour}
              intensityContour={intensityContour}
              formantTracks={formantTracks}
            />
          )}
          {activeGraph === 'voxplot_profile' && (
            <VoxplotProfileView
              voxplot={voxplot}
              spectrogram={spectrogram}
              waveform={waveform}
              metrics={metrics}
            />
          )}
          {activeGraph === 'oscilloscope' && (
            <OscilloscopeGraph waveform={waveform} glottalPulses={glottalPulses} />
          )}
          {activeGraph === 'f0_intensity' && (
            <F0IntensityGraph f0Contour={f0Contour} intensityContour={intensityContour} />
          )}
          {activeGraph === 'harmonics' && (
            <HarmonicsGraph harmonics={harmonics} />
          )}
          {activeGraph === 'ltas' && (
            <LtasGraph ltas={ltas} />
          )}
          {activeGraph === 'formants' && (
            <FormantsGraph formants={formants} />
          )}
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

/* ──────── PRAAT SOUND EDITOR EXACT REPLICA ──────── */

function PraatEditorView({ waveform, spectrogram, glottalPulses = [], f0Contour, intensityContour, formantTracks }: any) {
  const wave = waveform?.waveform || [];
  const times = waveform?.time_s || [];
  const dur = waveform?.duration_s || 4.76;
  const specFreqs = spectrogram?.frequencies_hz || [];
  const specTimes = spectrogram?.times_s || [];
  const specPower = spectrogram?.power_db || [];

  const f0Times = f0Contour?.f0_times_s || [];
  const f0Vals = f0Contour?.f0_values_hz || [];

  const intTimes = intensityContour?.intensity_times_s || [];
  const intVals = intensityContour?.intensity_values_db || [];

  const fTimes = formantTracks?.times_s || [];

  const width = 800, waveH = 140, specH = 220, padX = 45;
  const plotW = width - 2 * padX;

  const minV = wave.length > 0 ? Math.min(...wave) : -0.6;
  const maxV = wave.length > 0 ? Math.max(...wave) : 0.6;
  const absMax = Math.max(Math.abs(minV), Math.abs(maxV)) || 0.6;

  // Waveform SVG Path
  const wavePath = wave.map((v: number, i: number) => {
    const x = padX + (i / (wave.length - 1)) * plotW;
    const y = (waveH / 2) - (v / absMax) * (waveH / 2 - 10);
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Pitch Curve SVG Path (Blue)
  const f0Valid = f0Vals.filter((v: any) => v && v > 0);
  const minF0 = f0Valid.length > 0 ? Math.min(...f0Valid) : 50;
  const maxF0 = f0Valid.length > 0 ? Math.max(...f0Valid) : 500;

  const pitchPath = f0Vals.map((v: any, i: number) => {
    if (!v || v <= 0) return null;
    const x = padX + (f0Times[i] / dur) * plotW;
    const y = specH - ((v - 50) / (500 - 50)) * specH;
    return { x, y };
  }).filter(Boolean).map((p: any, i: number) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  // Intensity Curve SVG Path (Yellow)
  const intPath = intVals.map((v: number, i: number) => {
    const x = padX + (intTimes[i] / dur) * plotW;
    const y = specH - ((v - 40) / (100 - 40)) * specH;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Spectrogram cells
  let minDb = Infinity, maxDb = -Infinity;
  for (const row of specPower) { for (const v of row) { if (v < minDb) minDb = v; if (v > maxDb) maxDb = v; } }
  const dbRange = maxDb - minDb || 1;

  const cellW = plotW / (specTimes.length || 1);
  const cellH = specH / (specFreqs.length || 1);

  const cells: JSX.Element[] = [];
  if (specPower.length > 0) {
    for (let fi = 0; fi < specFreqs.length; fi += Math.max(1, Math.floor(specFreqs.length / 80))) {
      for (let ti = 0; ti < specTimes.length; ti += Math.max(1, Math.floor(specTimes.length / 160))) {
        const norm = (specPower[fi][ti] - minDb) / dbRange;
        // Grayscale inverted for Praat style (white = low power, dark gray/black = high power)
        const gray = Math.round(255 * (1 - norm));
        cells.push(
          <rect key={`${fi}-${ti}`}
            x={padX + ti * cellW} y={specH - (fi + 1) * cellH}
            width={cellW + 0.6} height={cellH + 0.6}
            fill={`rgb(${gray},${gray},${gray})`} />
        );
      }
    }
  }

  return (
    <div className="bg-slate-200 border-2 border-slate-400 text-slate-900 rounded-lg p-3 font-sans shadow-2xl">
      {/* Praat Window Header */}
      <div className="bg-slate-300 border-b border-slate-400 px-3 py-1 flex items-center justify-between text-xs font-bold text-slate-800 -mx-3 -mt-3 mb-3 rounded-t-lg">
        <span className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-blue-700" />
          Praat Picture / Sound Editor View — [Sustained Phonation / Continuous Speech]
        </span>
        <span className="text-[10px] text-slate-600 font-mono">Visible part: {dur.toFixed(4)} s</span>
      </div>

      {/* Top Panel: Waveform & Glottal Pulses */}
      <div className="relative bg-white border border-slate-400 mb-2">
        <svg viewBox={`0 0 ${width} ${waveH}`} className="w-full h-36">
          <rect x={padX} y={0} width={plotW} height={waveH} fill="#ffffff" />
          <line x1={padX} y1={waveH / 2} x2={padX + plotW} y2={waveH / 2} stroke="#94a3b8" strokeWidth="0.5" />
          
          {/* Waveform line */}
          {wavePath && <path d={wavePath} fill="none" stroke="#000000" strokeWidth="1.2" />}

          {/* Glottal Pulses (Vertical Blue Lines) */}
          {glottalPulses.map((t, idx) => {
            const x = padX + (t / dur) * plotW;
            return <line key={idx} x1={x} y1={8} x2={x} y2={waveH - 8} stroke="#1d4ed8" strokeWidth="0.7" opacity="0.85" />;
          })}

          {/* Y Axis Labels */}
          <text x={padX - 4} y={12} fill="#000000" fontSize="8" textAnchor="end">{absMax.toFixed(4)}</text>
          <text x={padX - 4} y={waveH / 2 + 3} fill="#000000" fontSize="8" textAnchor="end">0</text>
          <text x={padX - 4} y={waveH - 4} fill="#000000" fontSize="8" textAnchor="end">-{absMax.toFixed(4)}</text>
        </svg>
      </div>

      {/* Bottom Panel: Spectrogram, Pitch (Blue), Intensity (Yellow), Formants (Red dots) */}
      <div className="relative bg-white border border-slate-400">
        <svg viewBox={`0 0 ${width} ${specH}`} className="w-full h-56">
          <rect x={padX} y={0} width={plotW} height={specH} fill="#ffffff" />
          
          {/* Spectrogram Grayscale cells */}
          {cells}

          {/* Intensity Curve (Yellow) */}
          {intPath && <path d={intPath} fill="none" stroke="#eab308" strokeWidth="2.0" strokeDasharray="3,1" />}

          {/* Pitch Curve (Cyan/Blue) */}
          {pitchPath && <path d={pitchPath} fill="none" stroke="#0284c7" strokeWidth="2.5" />}

          {/* Formants Tracking (Red Dots) */}
          {fTimes.map((t: number, ti: number) => {
            const x = padX + (t / dur) * plotW;
            const dots = [];
            for (let fNum = 1; fNum <= 4; fNum++) {
              const val = formantTracks?.[`f${fNum}_hz`]?.[ti];
              if (val && val > 0 && val <= 5000) {
                const y = specH - (val / 5000) * specH;
                dots.push(<circle key={`${ti}-${fNum}`} cx={x} cy={y} r={1.5} fill="#dc2626" />);
              }
            }
            return dots;
          })}

          {/* Y Axes Labels (Spectrogram 0-5000 Hz on Left, Pitch/Intensity on Right) */}
          <text x={padX - 4} y={10} fill="#000000" fontSize="8" textAnchor="end">5000 Hz</text>
          <text x={padX - 4} y={specH - 4} fill="#000000" fontSize="8" textAnchor="end">0 Hz</text>

          <text x={padX + plotW + 4} y={12} fill="#0284c7" fontSize="8" fontWeight="bold">500 Hz</text>
          <text x={padX + plotW + 4} y={specH - 4} fill="#0284c7" fontSize="8">75 Hz</text>

          <text x={padX + plotW + 4} y={26} fill="#ca8a04" fontSize="8" fontWeight="bold">100 dB</text>
          <text x={padX + plotW + 4} y={specH - 16} fill="#ca8a04" fontSize="8">50 dB</text>

          {/* Time axis */}
          <text x={padX} y={specH - 2} fill="#64748b" fontSize="7">0 s</text>
          <text x={padX + plotW} y={specH - 2} fill="#64748b" fontSize="7" textAnchor="end">{dur.toFixed(4)} s</text>
        </svg>
      </div>

      {/* Legend & Controls bar */}
      <div className="mt-2 flex flex-wrap items-center justify-between bg-slate-300 px-3 py-1.5 rounded text-[10px] text-slate-800 font-semibold border border-slate-400">
        <span className="flex items-center gap-1.5"><span className="w-3 h-1 bg-black inline-block" /> Forma de onda</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-1 bg-blue-700 inline-block" /> Pulsos glóticos (vertical)</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-1 bg-sky-600 inline-block" /> Pitch F0 (curva azul)</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-1 bg-yellow-500 inline-block border-dashed" /> Intensidad (amarillo)</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-600 inline-block" /> Formantes F1-F4 (rojo)</span>
      </div>
    </div>
  );
}

/* ──────── EXACT VOXPLOT ACOUSTIC QUALITY PROFILE & RADAR VIEW ──────── */

function VoxplotProfileView({ voxplot, spectrogram, waveform, metrics }: any) {
  const table = voxplot?.table || [];
  const radarAxes = voxplot?.radar_axes || [];
  const avqi = voxplot?.avqi ?? 4.11;
  const abi = voxplot?.abi ?? 5.68;

  // Radar Chart Calculations
  // 6 Axes: AVQI, ABI, Breathiness (GNE, CPPS), Hoarseness (jitter ppq5, HNR)
  const categories = radarAxes.map((r: any) => r.label);
  const N = categories.length || 6;

  const width = 360, height = 360, cx = width / 2, cy = height / 2, radius = 110;

  const angles = Array.from({ length: N }, (_, i) => (i * 2 * Math.PI) / N - Math.PI / 2);

  // Circle normal boundary
  const normPoints = angles.map((a) => {
    const x = cx + radius * Math.cos(a);
    const y = cy + radius * Math.sin(a);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  // Patient Deviation Polygon
  const patientPoints = radarAxes.map((r: any, i: number) => {
    const ratio = Math.min(2.5, Math.max(0.2, r.norm_ratio || 1.0));
    const rScaled = radius * ratio;
    const x = cx + rScaled * Math.cos(angles[i]);
    const y = cy + rScaled * Math.sin(angles[i]);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <div className="bg-white border-2 border-slate-300 text-slate-900 rounded-xl p-6 shadow-2xl font-sans">
      {/* Header */}
      <div className="text-center border-b border-slate-200 pb-4 mb-6">
        <h2 className="text-xl font-bold tracking-tight text-slate-800">VOXplot — Acoustic Voice Quality Profile</h2>
        <p className="text-xs text-slate-500 font-mono mt-0.5">VOXplot Engine v2.0.0 — Clinical Bioacoustics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Spectrogram + Oscillogram */}
        <div className="lg:col-span-6 space-y-4">
          <div className="border border-slate-300 rounded-lg p-2 bg-slate-50 shadow-inner">
            <div className="text-[10px] font-bold text-slate-600 mb-1 uppercase tracking-wider">Espectrograma de Banda Estrecha (0 - 5000 Hz)</div>
            <div className="h-44 bg-slate-900 rounded overflow-hidden relative">
              <SpectrogramGraph spectrogram={spectrogram} />
            </div>
          </div>

          <div className="border border-slate-300 rounded-lg p-2 bg-slate-50 shadow-inner">
            <div className="text-[10px] font-bold text-slate-600 mb-1 uppercase tracking-wider">Forma de Onda (Oscilograma)</div>
            <div className="h-20 bg-slate-900 rounded overflow-hidden relative">
              <OscilloscopeGraph waveform={waveform} />
            </div>
          </div>
        </div>

        {/* Right Side: 16-Metric Table */}
        <div className="lg:col-span-6 border border-slate-200 rounded-lg p-3 bg-slate-50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-slate-800 uppercase">Parámetro Bioacústico</span>
            <span className="text-xs font-bold text-emerald-700 uppercase">Norma</span>
          </div>
          <div className="space-y-1 text-xs">
            {table.map((row: any) => (
              <div key={row.parameter} className={`flex items-center justify-between px-2 py-1 rounded border ${
                row.highlight ? 'bg-amber-100/80 border-amber-300 font-bold' : row.is_normal ? 'bg-white border-slate-200' : 'bg-red-50 border-red-200'
              }`}>
                <span className="text-slate-700">{row.parameter}</span>
                <div className="flex items-center gap-3">
                  <span className={`font-mono font-semibold ${row.is_normal ? 'text-slate-900' : 'text-red-600 font-bold'}`}>
                    {row.value} {row.unit}
                  </span>
                  <span className="text-slate-500 font-mono w-14 text-right">{row.norm}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Section: Exact 6-Axis VOXplot Radar Chart */}
      <div className="mt-8 border-t border-slate-200 pt-6">
        <div className="text-center mb-2">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Perfil de Disfonía y Rugosidad Vocal (Radar Chart)</h3>
          <p className="text-xs text-slate-500">Región verde central = Normalidad. Polígono rojo = Desviación del paciente.</p>
        </div>

        <div className="flex justify-center relative">
          <svg width={width} height={height} className="overflow-visible">
            {/* Concentric rings */}
            {[0.33, 0.66, 1.0, 1.33, 1.66].map((scale, i) => (
              <circle key={i} cx={cx} cy={cy} r={radius * scale} fill="none" stroke="#e2e8f0" strokeWidth={scale === 1.0 ? "1.5" : "0.5"} strokeDasharray={scale === 1.0 ? "none" : "2,2"} />
            ))}

            {/* Central Normal Green Disk */}
            <polygon points={normPoints} fill="#22c55e" fillOpacity="0.25" stroke="#16a34a" strokeWidth="1.5" />

            {/* Axes lines */}
            {angles.map((a, i) => {
              const x2 = cx + radius * 1.8 * Math.cos(a);
              const y2 = cy + radius * 1.8 * Math.sin(a);
              return <line key={i} x1={cx} y1={cy} x2={x2} y2={y2} stroke="#cbd5e1" strokeWidth="1" />;
            })}

            {/* Patient Deviation Red Polygon */}
            {patientPoints && (
              <polygon points={patientPoints} fill="#ef4444" fillOpacity="0.65" stroke="#b91c1c" strokeWidth="2.5" />
            )}

            {/* Axis Labels */}
            {radarAxes.map((r: any, i: number) => {
              const labelRadius = radius * 2.1;
              const lx = cx + labelRadius * Math.cos(angles[i]);
              const ly = cy + labelRadius * Math.sin(angles[i]);
              return (
                <text key={r.axis} x={lx} y={ly} fill="#0f172a" fontSize="10" fontWeight="bold" textAnchor="middle" dominantBaseline="central">
                  {r.label}
                </text>
              );
            })}

            {/* Domain Headers: Hoarseness (Left) vs Breathiness (Right) */}
            <text x={cx - 120} y={cy - 120} fill="#b45309" fontSize="13" fontWeight="bold" textAnchor="middle">Hoarseness</text>
            <text x={cx + 120} y={cy - 120} fill="#1d4ed8" fontSize="13" fontWeight="bold" textAnchor="middle">Breathiness</text>
          </svg>
        </div>

        {/* Cutoff summary */}
        <div className="mt-4 flex justify-center gap-6 text-xs text-slate-600 font-semibold border-t border-slate-100 pt-3">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-emerald-500/40 border border-emerald-600" /> Región Normal</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-red-500/60 border border-red-700" /> Paciente (AVQI: {avqi}, ABI: {abi})</span>
        </div>
      </div>
    </div>
  );
}

/* ──────── OTHER GRAPH COMPONENTS ──────── */

function OscilloscopeGraph({ waveform, glottalPulses = [] }: { waveform: any; glottalPulses?: number[] }) {
  const wave = waveform?.waveform || [];
  const dur = waveform?.duration_s || 0;
  if (wave.length === 0) return <EmptyGraph label="Osciloscopio — Sin datos de forma de onda" />;

  const width = 700, height = 160, padX = 40, padY = 20;
  const plotW = width - 2 * padX, plotH = height - 2 * padY;
  const minV = Math.min(...wave), maxV = Math.max(...wave);
  const range = maxV - minV || 1;

  const pathD = wave.map((v: number, i: number) => {
    const x = padX + (i / (wave.length - 1)) * plotW;
    const y = padY + plotH - ((v - minV) / range) * plotH;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300 mb-2">Osciloscopio — Forma de Onda y Pulsos Glóticos</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40">
        <rect x={padX} y={padY} width={plotW} height={plotH} fill="#0f172a" rx="4" />
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => (
          <line key={frac} x1={padX} y1={padY + plotH * frac} x2={padX + plotW} y2={padY + plotH * frac} stroke="#1e293b" strokeWidth="0.5" />
        ))}
        {glottalPulses.map((t, idx) => {
          const x = padX + (t / (dur || 1)) * plotW;
          return <line key={idx} x1={x} y1={padY} x2={x} y2={padY + plotH} stroke="#3b82f6" strokeWidth="0.6" opacity="0.6" />;
        })}
        <path d={pathD} fill="none" stroke="#38bdf8" strokeWidth="1.5" />
        <text x={padX} y={height - 2} fill="#64748b" fontSize="8">0s</text>
        <text x={padX + plotW} y={height - 2} fill="#64748b" fontSize="8" textAnchor="end">{dur.toFixed(2)}s</text>
        <text x={2} y={padY + 4} fill="#64748b" fontSize="7">{maxV.toFixed(2)}</text>
        <text x={2} y={padY + plotH} fill="#64748b" fontSize="7">{minV.toFixed(2)}</text>
      </svg>
    </div>
  );
}

function SpectrogramGraph({ spectrogram }: { spectrogram: any }) {
  const freqs = spectrogram?.frequencies_hz || [];
  const times = spectrogram?.times_s || [];
  const power = spectrogram?.power_db || [];
  if (freqs.length === 0 || times.length === 0) return <EmptyGraph label="Espectrograma — Sin datos" />;

  const width = 700, height = 220, padX = 40, padY = 20;
  const plotW = width - 2 * padX, plotH = height - 2 * padY;
  const maxFreq = spectrogram?.max_freq_hz || 5000;

  let minDb = Infinity, maxDb = -Infinity;
  for (const row of power) { for (const v of row) { if (v < minDb) minDb = v; if (v > maxDb) maxDb = v; } }
  const dbRange = maxDb - minDb || 1;

  const cellW = plotW / times.length;
  const cellH = plotH / freqs.length;

  const cells: JSX.Element[] = [];
  for (let fi = 0; fi < freqs.length; fi += Math.max(1, Math.floor(freqs.length / 100))) {
    for (let ti = 0; ti < times.length; ti += Math.max(1, Math.floor(times.length / 200))) {
      const norm = (power[fi][ti] - minDb) / dbRange;
      const r = Math.round(255 * Math.min(1, norm * 2));
      const g = Math.round(255 * Math.min(1, Math.max(0, norm * 2 - 1)));
      const b = Math.round(80 + 175 * (1 - norm));
      cells.push(
        <rect key={`${fi}-${ti}`}
          x={padX + ti * cellW} y={padY + plotH - (fi + 1) * cellH}
          width={cellW + 0.5} height={cellH + 0.5}
          fill={`rgb(${r},${g},${b})`} />
      );
    }
  }

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300 mb-2">Espectrograma de Potencia</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ maxHeight: '280px' }}>
        <rect x={padX} y={padY} width={plotW} height={plotH} fill="#000" rx="4" />
        {cells}
        <text x={padX - 2} y={padY + 4} fill="#64748b" fontSize="7" textAnchor="end">{maxFreq}Hz</text>
        <text x={padX - 2} y={padY + plotH} fill="#64748b" fontSize="7" textAnchor="end">0Hz</text>
        <text x={padX} y={height - 2} fill="#64748b" fontSize="7">0s</text>
        <text x={padX + plotW} y={height - 2} fill="#64748b" fontSize="7" textAnchor="end">{times[times.length - 1]?.toFixed(2)}s</text>
      </svg>
    </div>
  );
}

function F0IntensityGraph({ f0Contour, intensityContour }: { f0Contour: any; intensityContour: any }) {
  const f0Times = f0Contour?.f0_times_s || [];
  const f0Values = f0Contour?.f0_values_hz || [];
  const intTimes = intensityContour?.intensity_times_s || [];
  const intValues = intensityContour?.intensity_values_db || [];

  if (f0Values.length === 0 && intValues.length === 0) return <EmptyGraph label="F0 + Intensidad — Sin datos" />;

  const width = 700, height = 200, padX = 50, padY = 20, padY2 = 20;
  const plotW = width - padX - padY2, plotH = height - padY - padY;

  const f0Valid = f0Values.filter((v: number | null) => v !== null && v > 0);
  const f0Min = f0Valid.length > 0 ? Math.min(...f0Valid) : 0;
  const f0Max = f0Valid.length > 0 ? Math.max(...f0Valid) : 300;
  const intMin = intValues.length > 0 ? Math.min(...intValues) : 40;
  const intMax = intValues.length > 0 ? Math.max(...intValues) : 100;

  const totalTime = Math.max(f0Times.length > 0 ? f0Times[f0Times.length - 1] : 0, intTimes.length > 0 ? intTimes[intTimes.length - 1] : 1);

  const f0Path = f0Values.map((v: number | null, i: number) => {
    if (v === null || v <= 0) return null;
    const x = padX + (f0Times[i] / totalTime) * plotW;
    const y = padY + plotH - ((v - f0Min) / (f0Max - f0Min || 1)) * plotH;
    return { x, y };
  }).filter(Boolean).map((p: any, i: number) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  const intPath = intValues.map((v: number, i: number) => {
    const x = padX + (intTimes[i] / totalTime) * plotW;
    const y = padY + plotH - ((v - intMin) / (intMax - intMin || 1)) * plotH;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300 mb-2">Contorno de F0 e Intensidad</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48">
        <rect x={padX} y={padY} width={plotW} height={plotH} fill="#0f172a" rx="4" />
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1={padX} y1={padY + plotH * f} x2={padX + plotW} y2={padY + plotH * f} stroke="#1e293b" strokeWidth="0.5" />
        ))}
        {f0Path && <path d={f0Path} fill="none" stroke="#38bdf8" strokeWidth="2" />}
        {intPath && <path d={intPath} fill="none" stroke="#facc15" strokeWidth="1.5" strokeDasharray="4,2" />}
        <text x={4} y={padY + 4} fill="#38bdf8" fontSize="7">F0 Hz</text>
        <text x={4} y={padY + 14} fill="#facc15" fontSize="7">dB</text>
        <text x={padX - 2} y={padY + 4} fill="#64748b" fontSize="7" textAnchor="end">{f0Max.toFixed(0)}</text>
        <text x={padX - 2} y={padY + plotH} fill="#64748b" fontSize="7" textAnchor="end">{f0Min.toFixed(0)}</text>
        <text x={padX + plotW + 2} y={padY + 4} fill="#64748b" fontSize="7">{intMax.toFixed(0)}</text>
        <text x={padX + plotW + 2} y={padY + plotH} fill="#64748b" fontSize="7">{intMin.toFixed(0)}</text>
      </svg>
    </div>
  );
}

function HarmonicsGraph({ harmonics }: { harmonics: any[] }) {
  if (!harmonics || harmonics.length === 0) return <EmptyGraph label="Espectro Armónico — Sin datos" />;
  const maxAmp = Math.max(...harmonics.map(h => h.amplitude_db), 1);
  const width = 700, height = 180, padX = 40, padY = 20;
  const plotW = width - 2 * padX, plotH = height - 2 * padY;

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300 mb-2">Espectro Armónico — H1 a H{harmonics.length}</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-44">
        <rect x={padX} y={padY} width={plotW} height={plotH} fill="#0f172a" rx="4" />
        {harmonics.map((h, i) => {
          const x = padX + (i / harmonics.length) * plotW + plotW / harmonics.length / 2;
          const barH = (h.amplitude_db / maxAmp) * plotH;
          return (
            <g key={i}>
              <rect x={x - 8} y={padY + plotH - barH} width={16} height={barH} fill="#38bdf8" rx="2" opacity="0.8" />
              <text x={x} y={padY + plotH - barH - 4} fill="#e2e8f0" fontSize="7" textAnchor="middle">{h.amplitude_db.toFixed(0)}</text>
              <text x={x} y={padY + plotH + 10} fill="#64748b" fontSize="7" textAnchor="middle">H{h.number}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function LtasGraph({ ltas }: { ltas: any }) {
  if (!ltas || ltas.ltas_mean_db == null) return <EmptyGraph label="LTAS — Sin datos" />;
  const items = [
    { label: 'Media', val: ltas.ltas_mean_db, color: '#3b82f6' },
    { label: 'Pendiente', val: ltas.ltas_slope_db, color: '#22c55e' },
    { label: 'Pico', val: ltas.ltas_peak_height_db, color: '#f97316' },
    { label: 'Desvío', val: ltas.ltas_stdev_db, color: '#8b5cf6' },
  ];
  const maxAbs = Math.max(...items.map(i => Math.abs(i.val || 0)), 1);
  const width = 700, height = 160, padX = 60, padY = 15;
  const plotW = width - 2 * padX, barH = 24;

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300 mb-2">LTAS — Long-Term Average Spectrum</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40">
        {items.map((item, i) => {
          const y = padY + i * (barH + 12);
          const barW = Math.abs(item.val || 0) / maxAbs * plotW;
          return (
            <g key={item.label}>
              <text x={padX - 4} y={y + barH / 2 + 3} fill="#94a3b8" fontSize="9" textAnchor="end">{item.label}</text>
              <rect x={padX} y={y} width={plotW} height={barH} fill="#1e293b" rx="4" />
              <rect x={padX} y={y} width={barW} height={barH} fill={item.color} rx="4" opacity="0.8" />
              <text x={padX + barW + 4} y={y + barH / 2 + 3} fill="#e2e8f0" fontSize="9">{item.val?.toFixed(1) ?? 'N/D'} dB</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function FormantsGraph({ formants }: { formants: any }) {
  if (!formants || !formants.f1_hz) return <EmptyGraph label="Formantes — Sin datos" />;
  const items = [
    { label: 'F1', val: formants.f1_hz, bw: formants.f1_bandwidth_hz, color: '#ef4444' },
    { label: 'F2', val: formants.f2_hz, bw: formants.f2_bandwidth_hz, color: '#f97316' },
    { label: 'F3', val: formants.f3_hz, color: '#eab308' },
    { label: 'F4', val: formants.f4_hz, color: '#22c55e' },
  ].filter(f => f.val && f.val > 0);
  const maxVal = Math.max(...items.map(f => f.val || 0), 1);
  const width = 700, height = 160, padX = 40, padY = 20;
  const plotW = width - 2 * padX, barW = Math.min(60, plotW / items.length - 10);

  return (
    <div>
      <div className="text-xs font-semibold text-slate-300 mb-2">Formantes F1-F4 (Burg)</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40">
        <rect x={padX} y={padY} width={plotW} height={height - 2 * padY} fill="#0f172a" rx="4" />
        {items.map((f, i) => {
          const x = padX + (i / items.length) * plotW + (plotW / items.length - barW) / 2;
          const barH = (f.val / maxVal) * (height - 2 * padY - 20);
          const y = padY + (height - 2 * padY) - barH;
          return (
            <g key={f.label}>
              <rect x={x} y={y} width={barW} height={barH} fill={f.color} rx="4" opacity="0.85" />
              <text x={x + barW / 2} y={y - 4} fill="#e2e8f0" fontSize="9" textAnchor="middle" fontWeight="bold">{f.val?.toFixed(0)} Hz</text>
              <text x={x + barW / 2} y={padY + height - 2 * padY + 12} fill="#94a3b8" fontSize="9" textAnchor="middle">{f.label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function EmptyGraph({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center h-32 text-slate-500 text-xs">
      <Minus className="w-4 h-4 mr-2" />
      {label}
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
  if (metrics.nhr != null) count++;
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
    hnr_db: 'HNR', cpps_db: 'CPPS', nhr: 'NHR',
  };

  for (const [key, label] of Object.entries(metricMap)) {
    const val = metrics[key];
    if (val != null) {
      cards.push({
        data: {
          metric: label, raw_value: val, display_value: String(val),
          unit: key.includes('db') ? 'dB' : key === 'nhr' ? '' : '%', source: 'Praat / Parselmouth',
          calculation_status: 'valid', validation_status: 'valid',
          reference_source: key === 'hnr_db' ? '> 20 dB' : key === 'cpps_db' ? '> 5.5 dB' : key === 'shimmer_db' ? '< 0.5 dB' : key === 'jitter_pct' ? '< 1.04%' : key === 'nhr' ? '< 0.1' : '< 3.81%',
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
