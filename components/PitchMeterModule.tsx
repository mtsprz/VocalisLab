import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Mic, Square, Music, Volume2, Save, Activity, CheckCircle2, RefreshCw } from 'lucide-react';
import { useClinical } from './ClinicalContext';

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

// MIDI 36 = C2 (65.41 Hz), MIDI 84 = C6 (1046.50 Hz)
const MIN_MIDI = 36;
const MAX_MIDI = 84;

function midiToFreq(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function freqToMidi(freq: number): { midi: number; noteName: string; octave: number; cents: number; exactMidi: number } {
  const exactMidi = 69 + 12 * Math.log2(freq / 440);
  const roundedMidi = Math.round(exactMidi);
  const cents = Math.round((exactMidi - roundedMidi) * 100);
  const noteIdx = ((roundedMidi % 12) + 12) % 12;
  const octave = Math.floor(roundedMidi / 12) - 1;
  const noteName = `${NOTE_NAMES[noteIdx]}${octave}`;

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

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);
  const historyRef = useRef<number[]>([]);

  // Generate piano key definitions from C2 to C6
  const keys = useMemo<KeyInfo[]>(() => {
    const list: KeyInfo[] = [];
    for (let m = MIN_MIDI; m <= MAX_MIDI; m++) {
      const noteIdx = ((m % 12) + 12) % 12;
      const name = NOTE_NAMES[noteIdx];
      const isBlack = name.includes('#');
      const octave = Math.floor(m / 12) - 1;
      list.push({
        midi: m,
        noteName: `${name}${octave}`,
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
    if (pitchHistory.length === 0) return { mean: null, min: null, max: null, count: 0 };
    const sorted = [...pitchHistory].sort((a, b) => a - b);
    const sum = sorted.reduce((a, b) => a + b, 0);
    const mean = sum / sorted.length;
    return {
      mean: Math.round(mean * 10) / 10,
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
        f0_min: stats.min || undefined,
        f0_max: stats.max || undefined,
      });
      clinical.markStep('pitch');
    }
  };

  const currentNoteInfo = currentFreq ? freqToMidi(currentFreq) : null;

  // Expected normative range by sex
  const normRange = sexo === 'Masculino'
    ? { min: 85, max: 180, typical: 120, label: 'Masculino (85-180 Hz)' }
    : { min: 165, max: 300, typical: 210, label: 'Femenino (165-300 Hz)' };

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
              Pitch Meter en Tiempo Real & Teclado Espectral (C2 - C6)
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
            F0 Conversacional Media
          </span>
          <div className="text-3xl font-black text-gray-900 dark:text-white">
            {stats.mean ? `${stats.mean}` : '—'} <span className="text-sm font-bold text-gray-500">Hz</span>
          </div>
          <span className="text-[10px] font-semibold text-gray-400 block mt-1">
            Muestras capturadas: {stats.count}
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
            {normRange.label}
          </div>
          <span className="text-xs font-extrabold text-indigo-700 dark:text-indigo-300 block mt-1">
            F0 Típica: {normRange.typical} Hz
          </span>
        </div>
      </div>

      {/* 2. TECLADO DE PIANO HORIZONTAL DE C2 A C6 CON LÍNEA ESPECTRAL EN VIVO */}
      <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
            <Activity size={16} className="text-emerald-500" />
            Teclado de Piano Espectral en Vivo (C2 = 65 Hz a C6 = 1046 Hz)
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
                    {wk.noteName.includes('C') ? wk.noteName : ''}
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
          <span>C2 (65.4 Hz)</span>
          <span>C3 (130.8 Hz)</span>
          <span>C4 (261.6 Hz)</span>
          <span>C5 (523.2 Hz)</span>
          <span>C6 (1046.5 Hz)</span>
        </div>
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
