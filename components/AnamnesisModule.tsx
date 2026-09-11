import React, { useState, useRef, useEffect } from 'react';
import {
  Mic, MicOff, Square, Play, Pause, Download, Loader2, FileText, Sparkles,
  AlertCircle, CheckCircle2, Stethoscope, User, Activity, Volume2, Save
} from 'lucide-react';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
}

export default function AnamnesisModule({ pacienteId }: Props) {
  const clinical = useClinical();

  // Audio Recording & AudioContext state
  const [recording, setRecording] = useState(false);
  const [paused, setPaused] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [transcribing, setTranscribing] = useState(false);
  const [structuring, setStructuring] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [transcripcion, setTranscripcion] = useState('');
  const [error, setError] = useState('');

  // Guided Clinical Fields
  const [motivoConsulta, setMotivoConsulta] = useState(clinical.data.anamnesis.motivo_consulta || '');
  const [diagnosticoOrl, setDiagnosticoOrl] = useState(clinical.data.anamnesis.diagnostico_orl || '');
  const [metodoExploracion, setMetodoExploracion] = useState(clinical.data.anamnesis.metodo_exploracion || 'Nasal');
  const [demandaVocalHoras, setDemandaVocalHoras] = useState<number>(clinical.data.paciente.demanda_vocal_horas || 4);
  const [antecedentesSalud, setAntecedentesSalud] = useState('');
  const [resumenClinico, setResumenClinico] = useState(clinical.data.anamnesis.resumen_clinico || '');

  // Symptoms & Risk Factors toggles
  const [sintomas, setSintomas] = useState<Record<string, boolean>>({
    carraspeo_frecuente: false,
    fatiga_vocal: false,
    dolor_al_hablar: false,
    sensacion_cuerpo_extrano: false,
    sequedad_laringea: false,
    perdida_de_agudos: false,
    disfonia_intermitente: false,
  });

  const [factoresRiesgo, setFactoresRiesgo] = useState<Record<string, boolean>>({
    tabaquismo: false,
    reflujo_laringofaringeo: false,
    consumo_alto_cafe_mate: false,
    ambiente_ruidoso_polvo: false,
    reposo_insuficiente: false,
    falta_hidratacion: false,
  });

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number>(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Sync state if clinical context changes externally
  useEffect(() => {
    if (clinical.data.anamnesis.motivo_consulta) setMotivoConsulta(clinical.data.anamnesis.motivo_consulta);
    if (clinical.data.anamnesis.diagnostico_orl) setDiagnosticoOrl(clinical.data.anamnesis.diagnostico_orl);
    if (clinical.data.anamnesis.resumen_clinico) setResumenClinico(clinical.data.anamnesis.resumen_clinico);
    if (clinical.data.anamnesis.sintomas) setSintomas(prev => ({ ...prev, ...clinical.data.anamnesis.sintomas }));
    if (clinical.data.anamnesis.factores_riesgo) setFactoresRiesgo(prev => ({ ...prev, ...clinical.data.anamnesis.factores_riesgo }));
  }, [clinical.data.anamnesis]);

  // Audio recording timer
  useEffect(() => {
    if (recording && !paused) {
      timerRef.current = setInterval(() => {
        setSeconds(s => s + 1);
      }, 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [recording, paused]);

  // Passive visualizer draw loop
  const drawVisualizer = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (recording && analyserRef.current) {
      const bufferLength = analyserRef.current.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      analyserRef.current.getByteFrequencyData(dataArray);

      const barWidth = (w / 32);
      let x = 0;
      for (let i = 0; i < 32; i++) {
        const barHeight = (dataArray[i * 4] / 255) * h * 0.85;
        const gradient = ctx.createLinearGradient(0, h, 0, 0);
        gradient.addColorStop(0, '#6366f1');
        gradient.addColorStop(1, '#10b981');
        ctx.fillStyle = gradient;
        ctx.fillRect(x, h - barHeight, barWidth - 2, barHeight);
        x += barWidth;
      }
    } else {
      // Idle wave
      ctx.strokeStyle = '#334155';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      for (let x = 0; x < w; x += 5) {
        const y = h / 2 + Math.sin(x * 0.05 + Date.now() * 0.003) * 3;
        ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    animFrameRef.current = requestAnimationFrame(drawVisualizer);
  };

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(drawVisualizer);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [recording]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // AudioContext setup for visualizer
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);
      audioCtxRef.current = audioCtx;
      analyserRef.current = analyser;

      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        stream.getTracks().forEach(t => t.stop());
        audioCtxRef.current?.close();
      };

      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
      setPaused(false);
      setSeconds(0);
      setError('');
    } catch (e) {
      setError('No se pudo acceder al micrófono para la sesión de audio.');
    }
  };

  const pauseRecording = () => {
    if (!mediaRecorderRef.current) return;
    if (paused) {
      mediaRecorderRef.current.resume();
      setPaused(false);
    } else {
      mediaRecorderRef.current.pause();
      setPaused(true);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
    setPaused(false);
  };

  const formatTime = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const transcribirAudio = async () => {
    if (!audioBlob) return;
    setTranscribing(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('audio', audioBlob, 'anamnesis_sesion.webm');
      const r = await fetch(`${BACKEND_URL}/api/anamnesis/transcribir`, { method: 'POST', body: fd });
      const data = await r.json();
      if (data.error) { setError(data.error); return; }
      setTranscripcion(data.transcripcion || '');
    } catch {
      setError('Error conectando con el servidor de transcripción Whisper.');
    }
    setTranscribing(false);
  };

  const estructurarConIA = async () => {
    if (!transcripcion) return;
    setStructuring(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('transcripcion', transcripcion);
      const r = await fetch(`${BACKEND_URL}/api/anamnesis/estructurar`, { method: 'POST', body: fd });
      const data = await r.json();
      if (data.error) { setError(data.error); return; }

      if (data.motivo_consulta) setMotivoConsulta(data.motivo_consulta);
      if (data.diagnostico_orl) setDiagnosticoOrl(data.diagnostico_orl);
      if (data.metodo_exploracion) setMetodoExploracion(data.metodo_exploracion);
      if (data.resumen_clinico) setResumenClinico(data.resumen_clinico);

      if (data.sintomas) {
        setSintomas(prev => ({ ...prev, ...data.sintomas }));
      }
      if (data.factores_riesgo) {
        setFactoresRiesgo(prev => ({ ...prev, ...data.factores_riesgo }));
      }

      guardarContextoClinico(data);
    } catch {
      setError('Error al procesar la anamnesis con IA.');
    }
    setStructuring(false);
  };

  const guardarContextoClinico = (overrideData?: any) => {
    const anamnesisObj = {
      motivo_consulta: overrideData?.motivo_consulta || motivoConsulta,
      diagnostico_orl: overrideData?.diagnostico_orl || diagnosticoOrl,
      metodo_exploracion: overrideData?.metodo_exploracion || metodoExploracion,
      sintomas: overrideData?.sintomas || sintomas,
      factores_riesgo: overrideData?.factores_riesgo || factoresRiesgo,
      resumen_clinico: overrideData?.resumen_clinico || resumenClinico,
      transcripcion: transcripcion,
    };

    clinical.setAnamnesis(anamnesisObj);
    clinical.setPaciente({
      ...clinical.data.paciente,
      demanda_vocal_horas: demandaVocalHoras,
    });
    clinical.markStep('anamnesis');

    // Persistir en backend (fire-and-forget: no bloquea la UI)
    if (pacienteId) {
      try {
        const fd = new FormData();
        fd.append('paciente_id', pacienteId);
        fd.append('motivo_consulta', anamnesisObj.motivo_consulta || '');
        fd.append('diagnostico_orl', anamnesisObj.diagnostico_orl || '');
        fd.append('metodo_exploracion', anamnesisObj.metodo_exploracion || '');
        fd.append('sintomas', JSON.stringify(anamnesisObj.sintomas || {}));
        fd.append('factores_riesgo', JSON.stringify(anamnesisObj.factores_riesgo || {}));
        fd.append('resumen_clinico', anamnesisObj.resumen_clinico || '');
        fd.append('transcripcion_audio', anamnesisObj.transcripcion || '');
        fd.append('demanda_vocal_horas', String(demandaVocalHoras || ''));
        fetch(`${BACKEND_URL}/api/anamnesis`, { method: 'POST', body: fd }).catch(() => {});
      } catch {}
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* 1. BARRA SUPERIOR DE SESIÓN CLÍNICA (Discreta y Profesional) */}
      <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 shadow-sm flex flex-wrap items-center justify-between gap-4 transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
            <Stethoscope size={18} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
              Entrevista Clínica Fonoaudiológica
              {clinical.data.paciente.nombre_completo && (
                <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 px-2 py-0.5 rounded-full border border-indigo-200 dark:border-indigo-800/40">
                  {clinical.data.paciente.nombre_completo}
                </span>
              )}
            </h2>
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              Captura discreta de audio + campos clínicos guiados
            </p>
          </div>
        </div>

        {/* Discreet Pill Audio Control Bar */}
        <div className="flex items-center gap-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 p-1.5 rounded-full">
          {!recording ? (
            <button
              onClick={startRecording}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-sm active:scale-95"
            >
              <Mic size={14} />
              <span>Sesión de Audio</span>
            </button>
          ) : (
            <div className="flex items-center gap-1.5 px-2">
              {/* LED Pulsante Verde */}
              <span className="relative flex h-2.5 w-2.5">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${paused ? 'bg-amber-400' : 'bg-emerald-400'} opacity-75`} />
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${paused ? 'bg-amber-500' : 'bg-emerald-500'}`} />
              </span>
              <span className="font-mono text-xs font-bold text-gray-800 dark:text-white px-1">
                {formatTime(seconds)}
              </span>
              <button
                onClick={pauseRecording}
                className="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-white/10 text-gray-700 dark:text-gray-300"
                title={paused ? 'Reanudar' : 'Pausar'}
              >
                {paused ? <Play size={13} /> : <Pause size={13} />}
              </button>
              <button
                onClick={stopRecording}
                className="p-1 rounded-full bg-red-500/20 text-red-600 dark:text-red-400 hover:bg-red-500/30 ml-1"
                title="Detener"
              >
                <Square size={13} />
              </button>
            </div>
          )}

          {audioBlob && !recording && (
            <div className="flex items-center gap-2 pl-2 border-l border-gray-200 dark:border-white/10">
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                <CheckCircle2 size={12} /> Audio Listo
              </span>
              <button
                onClick={transcribirAudio}
                disabled={transcribing}
                className="px-2.5 py-1 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-bold flex items-center gap-1 disabled:opacity-50"
              >
                {transcribing ? <Loader2 size={12} className="animate-spin" /> : <FileText size={12} />}
                Transcribir
              </button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 2. CAMPOS CLÍNICOS GUIADOS PRINCIPALES */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Columna Izquierda & Centro: Formulario Anamnesis */}
        <div className="lg:col-span-2 space-y-5">
          {/* Motivo de Consulta & ORL */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm space-y-4">
            <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2 border-b border-gray-100 dark:border-white/5 pb-2">
              <Activity size={16} className="text-indigo-500" />
              Sintomatología Motivo de Consulta & Diagnóstico ORL
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                  Motivo de Consulta Principal
                </label>
                <textarea
                  value={motivoConsulta}
                  onChange={e => setMotivoConsulta(e.target.value)}
                  onBlur={() => guardarContextoClinico()}
                  rows={3}
                  placeholder="Ej: Ronquera progresiva hace 3 meses, fatiga al final de la jornada docente..."
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                  Informe Laringoscópico / Diagnóstico ORL
                </label>
                <textarea
                  value={diagnosticoOrl}
                  onChange={e => setDiagnosticoOrl(e.target.value)}
                  onBlur={() => guardarContextoClinico()}
                  rows={3}
                  placeholder="Ej: Esbozo nodular bilateral en tercio anterior e medio cordal, hiato longitudinal..."
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                  Método de Exploración ORL
                </label>
                <select
                  value={metodoExploracion}
                  onChange={e => { setMetodoExploracion(e.target.value); guardarContextoClinico(); }}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                >
                  <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100">Nasoangiofibroscopía Rígida/Flexible</option>
                  <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100">Laringostroboscopía de Alta Resolución</option>
                  <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100">Telelaringoscopía Rígida (70°)</option>
                  <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100">Sin informe ORL previo</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                  Demanda Vocal Estimada (Horas/Día)
                </label>
                <input
                  type="number"
                  min={1}
                  max={16}
                  value={demandaVocalHoras}
                  onChange={e => { setDemandaVocalHoras(Number(e.target.value)); guardarContextoClinico(); }}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Síntomas Vocales Específicos */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm space-y-3">
            <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2 border-b border-gray-100 dark:border-white/5 pb-2">
              <Volume2 size={16} className="text-amber-500" />
              Síntomas Vocales y Sensaciones Laringofaríngeas
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {[
                { id: 'carraspeo_frecuente', label: 'Carraspeo frecuente' },
                { id: 'fatiga_vocal', label: 'Fatiga vocal vespertina' },
                { id: 'dolor_al_hablar', label: 'Dolor / Tensión cervical' },
                { id: 'sensacion_cuerpo_extrano', label: 'Sensación de cuerpo extraño' },
                { id: 'sequedad_laringea', label: 'Sequedad de mucosas' },
                { id: 'perdida_de_agudos', label: 'Pérdida de rango agudo' },
                { id: 'disfonia_intermitente', label: 'Disfonía intermitente' },
              ].map(item => (
                <label
                  key={item.id}
                  className={`flex items-center gap-2 p-2 rounded-xl border text-xs font-semibold cursor-pointer transition-all ${
                    sintomas[item.id]
                      ? 'bg-amber-500/10 border-amber-500/40 text-amber-700 dark:text-amber-300'
                      : 'bg-gray-50 dark:bg-white/5 border-gray-200 dark:border-white/5 text-gray-600 dark:text-gray-400'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={Boolean(sintomas[item.id])}
                    onChange={e => {
                      const next = { ...sintomas, [item.id]: e.target.checked };
                      setSintomas(next);
                      guardarContextoClinico({ sintomas: next });
                    }}
                    className="rounded text-amber-600 focus:ring-amber-500 shrink-0"
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Factores de Riesgo */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm space-y-3">
            <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2 border-b border-gray-100 dark:border-white/5 pb-2">
              <AlertCircle size={16} className="text-purple-500" />
              Factores de Riesgo e Higiene Vocal
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {[
                { id: 'tabaquismo', label: 'Tabaquismo activo/pasivo' },
                { id: 'reflujo_laringofaringeo', label: 'Reflujo Laringofaríngeo (RLF)' },
                { id: 'consumo_alto_cafe_mate', label: 'Alto consumo café/mate' },
                { id: 'ambiente_ruidoso_polvo', label: 'Ambiente ruidoso o polvo' },
                { id: 'reposo_insuficiente', label: 'Reposo nocturno < 6h' },
                { id: 'falta_hidratacion', label: 'Hidratación < 1.5L/día' },
              ].map(item => (
                <label
                  key={item.id}
                  className={`flex items-center gap-2 p-2 rounded-xl border text-xs font-semibold cursor-pointer transition-all ${
                    factoresRiesgo[item.id]
                      ? 'bg-purple-500/10 border-purple-500/40 text-purple-700 dark:text-purple-300'
                      : 'bg-gray-50 dark:bg-white/5 border-gray-200 dark:border-white/5 text-gray-600 dark:text-gray-400'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={Boolean(factoresRiesgo[item.id])}
                    onChange={e => {
                      const next = { ...factoresRiesgo, [item.id]: e.target.checked };
                      setFactoresRiesgo(next);
                      guardarContextoClinico({ factores_riesgo: next });
                    }}
                    className="rounded text-purple-600 focus:ring-purple-500 shrink-0"
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Columna Derecha: Transcripción, Estructuración IA & Visor Pasivo de Audio */}
        <div className="space-y-5">
          {/* Visor de Audio Pasivo Discreto */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                <Activity size={14} className="text-emerald-500" />
                Monitor de Señal de Audio
              </span>
              <span className="text-[10px] text-gray-400 font-mono">
                {recording ? (paused ? 'Pausado' : 'Grabando') : audioBlob ? 'Audio Cargado' : 'En Espera'}
              </span>
            </div>

            {/* Canvas Visualizador Discreto */}
            <div className="bg-slate-900 rounded-xl p-2 border border-slate-800 h-20 flex items-center justify-center overflow-hidden">
              <canvas ref={canvasRef} width={300} height={60} className="w-full h-full" />
            </div>

            {audioBlob && (
              <div className="mt-3 pt-2 border-t border-gray-100 dark:border-white/5 flex items-center justify-between text-xs">
                <audio
                  src={URL.createObjectURL(audioBlob)}
                  controls
                  className="w-full h-8 rounded-lg text-xs"
                />
              </div>
            )}
          </div>

          {/* Transcripción Whisper */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-gray-800 dark:text-white flex items-center gap-1.5">
                <FileText size={14} className="text-indigo-500" />
                Transcripción de Voz
              </span>
              {transcripcion && (
                <button
                  onClick={estructurarConIA}
                  disabled={structuring}
                  className="px-3 py-1 rounded-full bg-purple-600 hover:bg-purple-500 text-white text-[11px] font-bold flex items-center gap-1 shadow-sm disabled:opacity-50"
                >
                  {structuring ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  Sintetizar IA
                </button>
              )}
            </div>

            <textarea
              value={transcripcion}
              onChange={e => setTranscripcion(e.target.value)}
              onBlur={() => guardarContextoClinico()}
              rows={6}
              placeholder="La transcripción del audio de la consulta se generará aquí..."
              className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-200 dark:border-gray-800 rounded-xl text-xs text-gray-800 dark:text-gray-200 focus:outline-none"
            />
          </div>

          {/* Resumen Sintético */}
          <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-4 shadow-sm space-y-2">
            <span className="text-xs font-bold text-gray-800 dark:text-white block">
              Sintesis Clínica de Anamnesis
            </span>
            <textarea
              value={resumenClinico}
              onChange={e => setResumenClinico(e.target.value)}
              onBlur={() => guardarContextoClinico()}
              rows={4}
              placeholder="Resumen del cuadro para incluir en el reporte final..."
              className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-200 dark:border-gray-800 rounded-xl text-xs text-gray-800 dark:text-gray-200 focus:outline-none"
            />
            <button
              onClick={() => guardarContextoClinico()}
              className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-md shadow-indigo-600/20"
            >
              <Save size={14} /> Guardar Anamnesis en Historia Clínica
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
