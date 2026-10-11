import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Mic, Square, Music, Volume2, Save, Activity, CheckCircle2, RefreshCw } from 'lucide-react';
import { useClinical } from './ClinicalContext';
import { useAuth } from './AuthContext';
import { CONVENCION_OCTAVAS, RANGOS_RESPALDO, edadDesde, elegirRangoNormativo, notaDesdeMidi, notaEs, promedioTexto } from './vozNormas';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

// MIDI 36 = Do1 (65.41 Hz), MIDI 84 = Do5 (1046.50 Hz) — convención franco-belga
const MIN_MIDI = 36;
const MAX_MIDI = 84;

function midiToFreq(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function freqToMidi(freq: number): { midi: number; noteName: string; octave: number; cents: number; exactMidi: number } {
  const exactMidi = 69 + 12 * Math.log2(freq / 440);
  const roundedMidi = Math.round(exactMidi);
  const cents = Math.round((exactMidi - roundedMidi) * 100);
  const octave = Math.floor(roundedMidi / 12) - 1;
  const noteName = notaDesdeMidi(roundedMidi);

  return { midi: roundedMidi, noteName, octave, cents, exactMidi };
}

interface KeyInfo {
  midi: number;
  noteName: string;
  isBlack: boolean;
  freq: number;
}

export default function PitchMeterModule() {
  const clinical = useClinical();

  const [active, setActive] = useState(false);
  const [currentFreq, setCurrentFreq] = useState<number | null>(null);
  const [pitchHistory, setHistory] = useState<number[]>([]);
  const [sexo, setSexo] = useState(clinical.data.paciente.sexo || 'Femenino');
  const pacienteRef = useRef(clinical.data.paciente?.id);
  const { user } = useAuth();
  const uid = user?.id || '';
  const [rangos, setRangos] = useState<any[]>(RANGOS_RESPALDO);
  const [companion, setCompanion] = useState<{ fecha: string; mediana: number | null; p5: number | null; p95: number | null }[]>([]);
  const edad = edadDesde(clinical.data.paciente?.fecha_nacimiento);

  // Tabla normativa (la misma que Vocalis Companion y "Voz y sesiones").
  useEffect(() => {
    if (!uid) return;
    fetch(`${BACKEND_URL}/api/companion/referencias?user_id=${uid}`)
      .then(r => r.json()).then(d => { if (d.ok && (d.rangos || []).length) setRangos(d.rangos); })
      .catch(() => {});
  }, [uid]);

  // Últimas sesiones medidas por Vocalis Companion para este paciente.
  useEffect(() => {
    const pid = clinical.data.paciente?.id;
    setCompanion([]);
    if (!pid || !uid) return;
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/companion/sessions?patient_id=${pid}&user_id=${uid}`);
        const d = await r.json();
        const ses = (d.sessions || []).slice(0, 5);
        const filas = await Promise.all(ses.map(async (s: any) => {
          try {
            const rd = await fetch(`${BACKEND_URL}/api/companion/sessions/${s.id}?user_id=${uid}`);
            const dd = await rd.json();
            const a = (dd.acustica || []).find((x: any) => x.task_type === 'conversacion_espontanea') || (dd.acustica || [])[0];
            return { fecha: (s.recorded_at || '').slice(0, 10), mediana: a?.f0_median_hz ?? null, p5: a?.f0_p5_hz ?? null, p95: a?.f0_p95_hz ?? null };
          } catch { return { fecha: (s.recorded_at || '').slice(0, 10), mediana: null, p5: null, p95: null }; }
        }));
        setCompanion(filas);
      } catch {}
    })();
  }, [clinical.data.paciente?.id, uid]);

  // Sincronizar sexo al cambiar de paciente (sin pisar la selección manual)
  useEffect(() => {
    const pid = clinical.data.paciente?.id;
    if (pid !== pacienteRef.current) {
      pacienteRef.current = pid;
      if (clinical.data.paciente?.sexo) setSexo(clinical.data.paciente.sexo);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinical.data.paciente]);

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);
  const historyRef = useRef<number[]>([]);

  // Generate piano key definitions from C2 to C6
  const keys = useMemo<KeyInfo[]>(() => {
    const list: KeyInfo[] = [];
    for (let m = MIN_MIDI; m <= MAX_MIDI; m++) {
      const noteName = notaDesdeMidi(m);
      const isBlack = noteName.includes('#');
      list.push({
        midi: m,
        noteName,
        isBlack,
        freq: midiToFreq(m),
      });
    }
    return list;
  }, []);

  // YIN Pitch Detection
  const yinDetect = (buffer: Float32Array, sampleRate: number): number | null => {
    const threshold = 0.15;
    const minLag = Math.floor(sampleRate / 800); // Up to 800 Hz
    const maxLag = Math.floor(sampleRate / 60);  // Down to 60 Hz
    const size = buffer.length;

    const yinBuffer = new Float32Array(size / 2);
    for (let tau = 0; tau < size / 2; tau++) {
      yinBuffer[tau] = 0;
      for (let j = 0; j < size / 2; j++) {
        const delta = buffer[j] - buffer[j + tau];
        yinBuffer[tau] += delta * delta;
      }
    }

    yinBuffer[0] = 1;
    let runningSum = 0;
    for (let tau = 1; tau < size / 2; tau++) {
      runningSum += yinBuffer[tau];
      yinBuffer[tau] *= tau / runningSum;
    }

    let bestTau = -1;
    for (let tau = minLag; tau < Math.min(maxLag, size / 2); tau++) {
      if (yinBuffer[tau] < threshold) {
        while (tau + 1 < size / 2 && yinBuffer[tau + 1] < yinBuffer[tau]) tau++;
        bestTau = tau;
        break;
      }
    }

    if (bestTau === -1) return null;

    const betterTau = bestTau + 0.5 * (yinBuffer[bestTau - 1] - yinBuffer[bestTau + 1]) /
      (yinBuffer[bestTau - 1] - 2 * yinBuffer[bestTau] + yinBuffer[bestTau + 1] + 0.00001);

    const freq = sampleRate / betterTau;
    return freq >= 60 && freq <= 850 ? freq : null;
  };

  const startMeter = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 4096;
      source.connect(analyser);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      historyRef.current = [];
      setHistory([]);
      setActive(true);

      const process = () => {
        const buf = new Float32Array(analyser.frequencyBinCount);
        analyser.getFloatTimeDomainData(buf);
        const freq = yinDetect(buf, ctx.sampleRate);
        setCurrentFreq(freq);

        if (freq) {
          historyRef.current.push(freq);
          if (historyRef.current.length > 500) historyRef.current.shift();
          setHistory([...historyRef.current]);
        }

        rafRef.current = requestAnimationFrame(process);
      };

      rafRef.current = requestAnimationFrame(process);
    } catch {
      alert('No se pudo acceder al micrófono para la medición de tono.');
    }
  };

  const stopMeter = () => {
    cancelAnimationFrame(rafRef.current);
    audioContextRef.current?.close();
    setActive(false);

    // Auto-save conversational F0 to clinical context when stopping
    saveToClinicalContext();
  };

  // Stats calculation
  const stats = useMemo(() => {
    if (pitchHistory.length === 0) return { mean: null, median: null, p5: null, p95: null, min: null, max: null, count: 0 };
    const sorted = [...pitchHistory].sort((a, b) => a - b);
    const sum = sorted.reduce((a, b) => a + b, 0);
    const mean = sum / sorted.length;
    const n = sorted.length;
    const median = n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
    const pct = (q: number) => sorted[Math.min(n - 1, Math.max(0, Math.round(q * (n - 1))))];
    return {
      mean: Math.round(mean * 10) / 10,
      // Mediana: misma métrica principal que Vocalis Companion (robusta a
      // saltos de octava y a tramos sueltos).
      median: Math.round(median * 10) / 10,
      p5: Math.round(pct(0.05) * 10) / 10,
      p95: Math.round(pct(0.95) * 10) / 10,
      min: Math.round(sorted[0] * 10) / 10,
      max: Math.round(sorted[sorted.length - 1] * 10) / 10,
      count: sorted.length,
    };
  }, [pitchHistory]);

  const saveToClinicalContext = () => {
    if (stats.mean) {
      clinical.setAcustica({
        ...clinical.data.acustica,
        f0_mean: stats.mean,
        f0_median: stats.median,
        f0_min: stats.min || undefined,
        f0_max: stats.max || undefined,
      });
      clinical.markStep('pitch');
    }
  };

  const currentNoteInfo = currentFreq ? freqToMidi(currentFreq) : null;

  // Rango normativo por sexo y edad (tabla compartida; respaldo: rango general adulto)
  const ref = elegirRangoNormativo(rangos, sexo, edad);
  const normRange = ref
    ? { min: ref.f0_min_hz, max: ref.f0_max_hz, typical: promedioTexto(ref),
        label: `${ref.sexo_referencia === 'ninex' ? 'Niñez/adolescencia' : (ref.sexo_referencia === 'masculino' ? 'Masculino' : 'Femenino')}${edad != null ? `, ${edad} años` : ''}: ${ref.f0_min_hz}–${ref.f0_max_hz} Hz`,
        fuente: ref.fuente || '' }
    : null;
  const semaforo = !normRange || stats.median == null ? null
    : stats.median < normRange.min ? { t: 'Por debajo del rango esperado', c: 'text-red-600' }
    : stats.median > normRange.max ? { t: 'Por encima del rango esperado', c: 'text-red-600' }
    : { t: 'Dentro del rango esperado', c: 'text-emerald-600' };

  // Calculate piano layout width percentage
  const whiteKeys = keys.filter(k => !k.isBlack);
  const whiteKeyWidthPct = 100 / whiteKeys.length;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Banner Header */}
      <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
            <Music size={20} />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
              Pitch Meter en Tiempo Real & Teclado Espectral (Do1 - Do5)
              {clinical.data.paciente.nombre_completo && (
                <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 px-2.5 py-0.5 rounded-full border border-indigo-200 dark:border-indigo-800/40">
                  {clinical.data.paciente.nombre_completo}
                </span>
              )}
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Detección YIN de frecuencia fundamental conversacional con volcado directo a Historia Clínica
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={sexo}
            onChange={e => setSexo(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-xl text-xs font-bold focus:ring-2 focus:ring-indigo-500"
          >
            <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100" value="Femenino">Femenino</option>
            <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100" value="Masculino">Masculino</option>
            <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100" value="Otro">Otro</option>
          </select>

          {!active ? (
            <button
              onClick={startMeter}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-600/20 active:scale-95 transition-all"
            >
              <Mic size={16} /> Iniciar Detección Live
            </button>
          ) : (
            <button
              onClick={stopMeter}
              className="flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-red-600/20 active:scale-95 transition-all"
            >
              <Square size={16} /> Detener & Guardar F0
            </button>
          )}
        </div>
      </div>

      {/* 1. MUESTRAS Y ESTADÍSTICAS DEL PITCH */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Frecuencia / Nota Actual */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 shadow-sm text-center">
          <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 block mb-1">
            Frecuencia Fundamental Live
          </span>
          <div className="text-3xl font-black text-indigo-600 dark:text-indigo-400">
            {currentFreq ? `${currentFreq.toFixed(1)}` : '—'} <span className="text-sm font-bold text-gray-500">Hz</span>
          </div>
          {currentNoteInfo && (
            <div className="mt-1 text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center justify-center gap-1">
              <span>{currentNoteInfo.noteName}</span>
              <span className="text-[10px] text-gray-400 font-mono">
                ({currentNoteInfo.cents >= 0 ? `+${currentNoteInfo.cents}` : currentNoteInfo.cents} cents)
              </span>
            </div>
          )}
        </div>

        {/* F0 Media Conversacional */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 shadow-sm text-center">
          <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 block mb-1">
            F0 Conversacional (mediana)
          </span>
          <div className="text-3xl font-black text-gray-900 dark:text-white">
            {stats.median ? `${stats.median}` : '—'} <span className="text-sm font-bold text-gray-500">Hz</span>
          </div>
          {stats.median != null && <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 block">{notaEs(stats.median)}</span>}
          {semaforo && <span className={`text-[11px] font-bold block ${semaforo.c}`}>{semaforo.t}</span>}
          <span className="text-[10px] font-semibold text-gray-400 block mt-1">
            Media {stats.mean ?? '—'} Hz · p5–p95 {stats.p5 ?? '—'}–{stats.p95 ?? '—'} Hz · {stats.count} muestras
          </span>
        </div>

        {/* Rango Observado Min - Max */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 shadow-sm text-center">
          <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 block mb-1">
            Extensión Vocal Observada
          </span>
          <div className="text-xl font-bold text-gray-800 dark:text-gray-200 mt-1">
            {stats.min || '—'} — {stats.max || '—'} <span className="text-xs font-semibold text-gray-500">Hz</span>
          </div>
          <span className="text-[10px] font-semibold text-gray-400 block mt-1">
            Mínima a Máxima
          </span>
        </div>

        {/* Normativa por Sexo */}
        <div className="bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 rounded-2xl p-4 shadow-sm text-center">
          <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 block mb-1">
            Normativa Rango Típico
          </span>
          <div className="text-sm font-bold text-indigo-900 dark:text-indigo-200 mt-1">
            {normRange ? normRange.label : 'Sin rango (faltan sexo o fecha de nacimiento)'}
          </div>
          {normRange?.typical && <span className="text-xs font-extrabold text-indigo-700 dark:text-indigo-300 block mt-1">
            Promedio esperado: {normRange.typical} Hz
          </span>}
          {normRange?.fuente && <span className="text-[10px] text-indigo-500 block mt-1">{normRange.fuente} · orientativo</span>}
        </div>
      </div>

      {/* 2. TECLADO DE PIANO HORIZONTAL DE C2 A C6 CON LÍNEA ESPECTRAL EN VIVO */}
      <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
            <Activity size={16} className="text-emerald-500" />
            Teclado de Piano Espectral en Vivo (Do1 = 65 Hz a Do5 = 1046 Hz · {CONVENCION_OCTAVAS})
          </h3>
          {active && (
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1 animate-pulse">
              <Volume2 size={14} /> Detección activa en tiempo real
            </span>
          )}
        </div>

        {/* Piano Layout Container */}
        <div className="relative w-full h-44 bg-slate-950 rounded-2xl border border-slate-800 p-3 overflow-hidden select-none shadow-inner">
          {/* Piano Keys Wrapper */}
          <div className="relative w-full h-full flex">
            {whiteKeys.map((wk, idx) => {
              const isCurrentKey = currentNoteInfo?.midi === wk.midi;
              return (
                <div
                  key={wk.midi}
                  style={{ width: `${whiteKeyWidthPct}%` }}
                  className={`relative h-full border-r border-slate-300 rounded-b-md transition-colors ${
                    isCurrentKey
                      ? 'bg-emerald-400 shadow-lg shadow-emerald-400/50'
                      : 'bg-slate-100 hover:bg-slate-200'
                  }`}
                >
                  <span className="absolute bottom-1 left-1/2 -translate-x-1/2 text-[9px] font-bold text-slate-700">
                    {wk.noteName.startsWith('Do') && !wk.noteName.includes('#') ? wk.noteName : ''}
                  </span>
                </div>
              );
            })}

            {/* Black Keys Positioned Absolutely */}
            {keys.map((k) => {
              if (!k.isBlack) return null;
              // Calculate offset relative to total MIDI range (36 to 84)
              const positionPct = ((k.midi - MIN_MIDI) / (MAX_MIDI - MIN_MIDI)) * 100;
              const isCurrentKey = currentNoteInfo?.midi === k.midi;

              return (
                <div
                  key={k.midi}
                  style={{
                    left: `${positionPct}%`,
                    width: `${whiteKeyWidthPct * 0.65}%`,
                  }}
                  className={`absolute top-0 h-[60%] -translate-x-1/2 rounded-b-md z-10 transition-colors ${
                    isCurrentKey
                      ? 'bg-emerald-500 ring-2 ring-emerald-300 shadow-lg shadow-emerald-500/50'
                      : 'bg-slate-900 border border-slate-800'
                  }`}
                />
              );
            })}

            {/* Live Pitch Spectral Sweep Line */}
            {currentNoteInfo && currentNoteInfo.exactMidi >= MIN_MIDI && currentNoteInfo.exactMidi <= MAX_MIDI && (
              <div
                style={{
                  left: `${((currentNoteInfo.exactMidi - MIN_MIDI) / (MAX_MIDI - MIN_MIDI)) * 100}%`,
                }}
                className="absolute top-0 bottom-0 w-1 bg-emerald-400 z-20 shadow-[0_0_12px_#34d399] -translate-x-1/2 pointer-events-none transition-all duration-75"
              >
                <div className="absolute -top-1 left-1/2 -translate-x-1/2 bg-emerald-500 text-slate-950 font-black text-[9px] px-1.5 py-0.5 rounded-full shadow-md whitespace-nowrap">
                  {currentFreq?.toFixed(1)} Hz
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Range Indicators Banner */}
        <div className="flex items-center justify-between text-[11px] text-gray-500 dark:text-gray-400 font-mono pt-1">
          <span>Do1 (65.4 Hz)</span>
          <span>Do2 (130.8 Hz)</span>
          <span>Do3 (261.6 Hz)</span>
          <span>Do4 (523.2 Hz)</span>
          <span>Do5 (1046.5 Hz)</span>
        </div>
      </div>

      {/* Vocalis Companion: altura tonal medida en las sesiones grabadas */}
      <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-5 shadow-sm">
        <h3 className="font-bold text-sm text-gray-900 dark:text-white mb-1">Vocalis Companion — altura tonal en las últimas sesiones</h3>
        <p className="text-[11px] text-gray-500 mb-3">Mediana del paciente (voces separadas automáticamente) para comparar con la medición en vivo.</p>
        {companion.length === 0
          ? <p className="text-xs text-gray-400">Sin sesiones del Companion para este paciente.</p>
          : <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {companion.map((c, i) => (
                <div key={i} className="p-2.5 rounded-xl border border-gray-200 dark:border-white/10 text-center">
                  <p className="text-[10px] text-gray-500">{c.fecha}</p>
                  <p className="text-lg font-black">{c.mediana != null ? Math.round(c.mediana) : '—'} <span className="text-xs">Hz</span></p>
                  <p className="text-[11px] font-bold text-indigo-600">{notaEs(c.mediana)}</p>
                  {c.p5 != null && <p className="text-[10px] text-gray-400">{Math.round(c.p5)}–{Math.round(c.p95 ?? 0)} Hz</p>}
                  {stats.median != null && c.mediana != null && (
                    <p className="text-[10px] font-semibold text-gray-500">en vivo {stats.median > c.mediana ? '+' : ''}{(12 * Math.log2(stats.median / c.mediana)).toFixed(1)} st</p>
                  )}
                </div>
              ))}
            </div>}
      </div>

      {/* Button to manually persist to clinical context */}
      <div className="flex justify-end">
        <button
          onClick={saveToClinicalContext}
          className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center gap-2 shadow-md shadow-indigo-600/20"
        >
          <Save size={15} /> Volcar F0 Conversacional a Historia Clínica
        </button>
      </div>
    </div>
  );
}
