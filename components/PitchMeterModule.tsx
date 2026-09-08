import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, Square, Music, Volume2 } from 'lucide-react';

const FREQ_RANGES = {
  Femenino: { min: 165, typical: 210, max: 300, label: 'Rango típico femenino (165-300 Hz)' },
  Masculino: { min: 85, typical: 120, max: 180, label: 'Rango típico masculino (85-180 Hz)' },
};

export default function PitchMeterModule() {
  const [active, setActive] = useState(false);
  const [currentFreq, setCurrentFreq] = useState<number | null>(null);
  const [minFreq, setMinFreq] = useState<number | Infinity>(Infinity);
  const [maxFreq, setMaxFreq] = useState<number>(0);
  const [histogram, setHistogram] = useState<number[]>(new Array(50).fill(0));
  const [sexo, setSexo] = useState('Femenino');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyRef = useRef<number[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number>(0);

  const range = FREQ_RANGES[sexo as keyof typeof FREQ_RANGES];

  const yinDetect = (buffer: Float32Array, sampleRate: number): number | null => {
    const threshold = 0.15;
    const minLag = Math.floor(sampleRate / 500);
    const maxLag = Math.floor(sampleRate / 60);
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
    return freq > 50 && freq < 600 ? freq : null;
  };

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, w, h);

    const hist = histogram;
    const maxH = Math.max(...hist, 1);

    ctx.fillStyle = 'rgba(99, 102, 241, 0.35)';
    const barW = w / hist.length;
    hist.forEach((v, i) => {
      const barH = (v / maxH) * h * 0.8;
      ctx.fillRect(i * barW, h - barH, barW - 1, barH);
    });

    if (currentFreq) {
      const x = ((currentFreq - 50) / 550) * w;
      ctx.strokeStyle = '#22c55e';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();

      ctx.fillStyle = '#22c55e';
      ctx.font = 'bold 14px monospace';
      ctx.fillText(`${currentFreq.toFixed(1)} Hz`, x + 5, 20);
    }

    const freqLabels = [100, 200, 300, 400, 500];
    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';
    freqLabels.forEach(f => {
      const x = ((f - 50) / 550) * w;
      ctx.fillText(`${f}`, x, h - 4);
    });
  }, [currentFreq, histogram]);

  useEffect(() => {
    drawCanvas();
    if (active) rafRef.current = requestAnimationFrame(drawCanvas);
    return () => cancelAnimationFrame(rafRef.current);
  }, [active, drawCanvas]);

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
      setMinFreq(Infinity);
      setMaxFreq(0);
      setHistogram(new Array(50).fill(0));
      setActive(true);

      const process = () => {
        const buf = new Float32Array(analyser.frequencyBinCount);
        analyser.getFloatTimeDomainData(buf);
        const freq = yinDetect(buf, ctx.sampleRate);
        setCurrentFreq(freq);
        if (freq) {
          historyRef.current.push(freq);
          if (historyRef.current.length > 200) historyRef.current.shift();
          setMinFreq(p => Math.min(p, freq));
          setMaxFreq(p => Math.max(p, freq));
          setHistogram(prev => {
            const bin = Math.min(49, Math.max(0, Math.floor(((freq - 50) / 550) * 50)));
            const next = [...prev];
            next[bin]++;
            return next;
          });
        }
        rafRef.current = requestAnimationFrame(process);
      };
      rafRef.current = requestAnimationFrame(process);
    } catch {
      alert('No se pudo acceder al micrófono');
    }
  };

  const stopMeter = () => {
    cancelAnimationFrame(rafRef.current);
    audioContextRef.current?.close();
    setActive(false);
  };

  const inRange = currentFreq && currentFreq >= range.min && currentFreq <= range.max;

  return (
    <div className="max-w-4xl space-y-4">
      <div className="bg-white dark:bg-[#111827] rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm transition-all duration-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-gray-800 dark:text-white flex items-center gap-2 text-base">
            <Music size={18} className="text-indigo-600 dark:text-indigo-400" /> Pitch Meter en Vivo
          </h3>
          <div className="flex items-center gap-3">
            <select
              value={sexo}
              onChange={e => setSexo(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option>Femenino</option>
              <option>Masculino</option>
            </select>
            {!active ? (
              <button
                onClick={startMeter}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold transition-all shadow-md shadow-indigo-600/10 active:scale-95"
              >
                <Mic size={16} /> Iniciar
              </button>
            ) : (
              <button
                onClick={stopMeter}
                className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm font-semibold transition-all shadow-md shadow-red-500/10 active:scale-95"
              >
                <Square size={16} /> Detener
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className={`rounded-xl p-4 text-center border transition-all duration-200 ${
            inRange
              ? 'bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-900/60'
              : 'bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-900/60'
          }`}>
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">Frecuencia Actual</p>
            <p className={`text-3xl font-extrabold ${inRange ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
              {currentFreq ? `${currentFreq.toFixed(1)}` : '—'} <span className="text-lg">Hz</span>
            </p>
          </div>
          <div className="bg-gray-50 dark:bg-gray-800/40 rounded-xl p-4 text-center border border-gray-200 dark:border-gray-800">
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">Rango Observado</p>
            <p className="text-xl font-bold text-gray-700 dark:text-gray-200">
              {minFreq === Infinity ? '—' : Math.round(minFreq)} — {maxFreq === 0 ? '—' : Math.round(maxFreq)} Hz
            </p>
          </div>
          <div className="bg-blue-50 dark:bg-blue-950/20 rounded-xl p-4 text-center border border-blue-200 dark:border-blue-900/60">
            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">{range.label}</p>
            <p className="text-sm font-bold text-blue-700 dark:text-blue-400 mt-1">
              Típico: {range.typical} Hz
            </p>
          </div>
        </div>

        <div className="bg-[#0f172a] rounded-xl overflow-hidden shadow-inner border border-gray-800">
          <canvas ref={canvasRef} width={800} height={200} className="w-full h-[220px]" />
        </div>

        {active && (
          <div className="mt-3 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400 font-semibold">
            <Volume2 size={14} className="text-green-500 animate-pulse" />
            Escuchando señal de audio en tiempo real...
          </div>
        )}
      </div>
    </div>
  );
}
