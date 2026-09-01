import React, { useState, useEffect, useRef } from 'react';
import {
  Activity, Mic, Square, FileText, CheckCircle2,
  Sparkles, Sliders, Volume2, User, Stethoscope, AlertCircle,
  Shield, Edit3, ArrowRight, ChevronDown, ChevronRight, Layers, Upload
} from 'lucide-react';
import { supabase } from '../utils/supabase';
import ClinicalReviewScreen from './ClinicalReviewScreen';
import TaskProtocolSelector from './TaskProtocolSelector';
import ReportEditor from './ReportEditor';
import VoxPlotImport from './VoxPlotImport';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface AnalysisResult {
  audio: any;
  metrics: any;
  avqiComponents: any;
  tools: any[];
  jsonExport: any;
  csvExport: string;
  harmonics: any[];
  formants: any;
  ltas: any;
  spectral: any;
  timestamp: string;
  engineVersion: string;
  scriptVersion: string;
  fileHash: string;
  modo: string;
}

type FlowStep = 'protocol' | 'capture' | 'analyzing' | 'review' | 'editor';

const ANALYSIS_STAGES = [
  'Validando señal de audio...',
  'Ejecutando Praat / Parselmouth...',
  'Calculando F0 y frecuencia fundamental...',
  'Midiendo Jitter (5 métodos)...',
  'Midiendo Shimmer (6 métodos)...',
  'Calculando HNR (Harmonics-to-Noise Ratio)...',
  'Calculando CPPS (Cepstral Peak Prominence)...',
  'Extrayendo formantes (Burg)...',
  'Calculando componentes AVQI v03.01...',
  'Generando espectrograma...',
  'Generando gráficos clínicos...',
  'Informe listo para revisión.',
];

export default function VocalisLabModule() {
  const [dispositivos, setDispositivos] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [nombre, setNombre] = useState('');
  const [dni, setDni] = useState('');
  const [edad, setEdad] = useState('');
  const [sexo, setSexo] = useState('Femenino');
  const [motivo, setMotivo] = useState('');
  const [derivador, setDerivador] = useState('');
  const [tmf, setTmf] = useState('15');
  const [grbas, setGrbas] = useState({ G: 0, R: 0, B: 0, A: 0, S: 0 });
  const [rasati, setRasati] = useState({ R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 });

  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [grabandoVocal, setGrabandoVocal] = useState(false);
  const [grabandoHabla, setGrabandoHabla] = useState(false);
  const [blobVocal, setBlobVocal] = useState<Blob | null>(null);
  const [blobHabla, setBlobHabla] = useState<Blob | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [analysisStage, setAnalysisStage] = useState(0);
  const [mensajeExito, setMensajeExito] = useState('');
  const [errorBackend, setErrorBackend] = useState('');

  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [flowStep, setFlowStep] = useState<FlowStep>('protocol');
  const [showRawData, setShowRawData] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [approved, setApproved] = useState(false);
  const [showVoxplot, setShowVoxplot] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const mediaRecorderRef = useRef<any>(null);
  const analysisIntervalRef = useRef<any>(null);

  useEffect(() => {
    async function cargarDispositivos() {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        const devs = await navigator.mediaDevices.enumerateDevices();
        const mics = devs.filter((d) => d.kind === 'audioinput');
        setDispositivos(mics);
        if (mics.length > 0) setSelectedDeviceId(mics[0].deviceId);
      } catch (err) {
        console.error('Error accediendo a dispositivos de audio:', err);
      }
    }
    cargarDispositivos();
  }, []);

  useEffect(() => {
    return () => {
      if (analysisIntervalRef.current) clearInterval(analysisIntervalRef.current);
    };
  }, []);

  const iniciarVisualizador = (stream: MediaStream) => {
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    const source = audioCtx.createMediaStreamSource(stream);
    source.connect(analyser);
    audioContextRef.current = audioCtx;
    analyserRef.current = analyser;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const draw = () => {
      animationFrameRef.current = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(dataArray);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = '#38bdf8';
      ctx.beginPath();
      const sliceWidth = (canvas.width * 1.0) / bufferLength;
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        x += sliceWidth;
      }
      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    };
    draw();
  };

  const detenerVisualizador = () => {
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    if (audioContextRef.current) audioContextRef.current.close();
  };

  const encodeWav = (samples: Float32Array, sampleRate: number): Blob => {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const writeString = (offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };
    writeString(0, 'RIFF');
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
  };

  const grabarMuestra = async (tipo: 'vocal' | 'habla') => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
          echoCancellation: false, noiseSuppression: false, autoGainControl: false, sampleRate: 44100,
        },
      });
      iniciarVisualizador(stream);
      const audioCtx = new AudioContext({ sampleRate: 44100 });
      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      const recordedSamples: Float32Array[] = [];
      processor.onaudioprocess = (e) => { recordedSamples.push(new Float32Array(e.inputBuffer.getChannelData(0))); };
      source.connect(processor);
      processor.connect(audioCtx.destination);
      const stopRecording = () => {
        processor.disconnect();
        source.disconnect();
        audioCtx.close();
        detenerVisualizador();
        stream.getTracks().forEach((t) => t.stop());
        const totalLength = recordedSamples.reduce((acc, s) => acc + s.length, 0);
        const merged = new Float32Array(totalLength);
        let offset = 0;
        recordedSamples.forEach((s) => { merged.set(s, offset); offset += s.length; });
        const wavBlob = encodeWav(merged, 44100);
        if (tipo === 'vocal') setBlobVocal(wavBlob); else setBlobHabla(wavBlob);
      };
      mediaRecorderRef.current = { stop: stopRecording };
      if (tipo === 'vocal') {
        setGrabandoVocal(true);
        setTimeout(() => { stopRecording(); setGrabandoVocal(false); }, 4000);
      } else {
        setGrabandoHabla(true);
      }
    } catch (err) {
      alert('Error al acceder al micrófono.');
    }
  };

  const detenerHabla = () => {
    if (mediaRecorderRef.current?.stop) { mediaRecorderRef.current.stop(); setGrabandoHabla(false); }
  };

  const ejecutarAnalisis = async () => {
    if (!blobVocal) { alert('Debes grabar la muestra de audio.'); return; }
    if (!BACKEND_URL) { alert('ERROR: Configure VITE_BACKEND_URL en Vercel.'); return; }

    setProcesando(true);
    setFlowStep('analyzing');
    setAnalysisStage(0);
    setErrorBackend('');
    setMensajeExito('');
    setAnalysisResult(null);

    let stage = 0;
    analysisIntervalRef.current = setInterval(() => {
      stage++;
      if (stage < ANALYSIS_STAGES.length) setAnalysisStage(stage);
    }, 800);

    try {
      const formData = new FormData();
      formData.append('audio_vocal', blobVocal, 'vocal_a.wav');
      if (blobHabla) formData.append('audio_habla', blobHabla, 'habla_continua.wav');
      formData.append('nombre', nombre || 'Paciente Sin Nombre');
      formData.append('dni', dni || 'S/D');
      formData.append('edad', edad || '0');
      formData.append('sexo', sexo);
      formData.append('motivo', motivo || 'Evaluación de control');
      formData.append('derivador', derivador || 'Consulta directa');
      formData.append('tmf', tmf);
      formData.append('rasati', JSON.stringify(rasati));

      const resJson = await fetch(`${BACKEND_URL}/api/analizar`, { method: 'POST', body: formData });
      if (!resJson.ok) { const errText = await resJson.text(); throw new Error(`Error ${resJson.status}: ${errText}`); }
      const data = await resJson.json();
      setAnalysisResult(data);
      setFlowStep('review');
    } catch (err: any) {
      setErrorBackend(err.message || 'Error al procesar el análisis.');
      setFlowStep('capture');
    } finally {
      if (analysisIntervalRef.current) clearInterval(analysisIntervalRef.current);
      setProcesando(false);
    }
  };

  const descargarPdf = async () => {
    if (!blobVocal || !BACKEND_URL) return;
    setProcesando(true);
    try {
      const formData = new FormData();
      formData.append('audio_vocal', blobVocal, 'vocal_a.wav');
      if (blobHabla) formData.append('audio_habla', blobHabla, 'habla_continua.wav');
      formData.append('nombre', nombre || 'Paciente Sin Nombre');
      formData.append('dni', dni || 'S/D');
      formData.append('edad', edad || '0');
      formData.append('sexo', sexo);
      formData.append('motivo', motivo || 'Evaluación de control');
      formData.append('derivador', derivador || 'Consulta directa');
      formData.append('tmf', tmf);
      formData.append('rasati', JSON.stringify(rasati));
      const res = await fetch(`${BACKEND_URL}/api/analizar-y-reportar`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const blobPdf = await res.blob();
      const url = window.URL.createObjectURL(blobPdf);
      const a = document.createElement('a');
      a.href = url;
      a.download = `VocalisLab_Informe_${dni || 'Clinico'}.pdf`;
      a.click();
      try {
        const grbasStr = `G${grbas.G} R${grbas.R} B${grbas.B} A${grbas.A} S${grbas.S}`;
        const rasatiStr = `R${rasati.R} A${rasati.A} S${rasati.S} A2${rasati.A2} T${rasati.T} I${rasati.I}`;
        await supabase.from('evaluaciones_vocales').insert({
          nombre_paciente: nombre || 'Paciente Sin Nombre', dni: dni || 'S/D',
          edad: parseInt(edad) || 0, sexo, motivo: motivo || 'Evaluación de control',
          derivador: derivador || 'Consulta directa', grbas: grbasStr, rasati: rasatiStr, tmf: parseFloat(tmf) || 0,
        });
      } catch (e) { console.warn('Error guardando en Supabase:', e); }
      setMensajeExito('Informe generado y descargado.');
      setTimeout(() => setMensajeExito(''), 5000);
    } catch (err: any) {
      setErrorBackend(err.message || 'Error al generar el PDF.');
    } finally {
      setProcesando(false);
    }
  };

  const r = analysisResult;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto mb-6 flex flex-col md:flex-row items-start md:items-center justify-between border-b border-slate-800 pb-6 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-sky-500/10 border border-sky-500/30 rounded-xl text-sky-400">
            <Activity className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-sky-400 bg-clip-text text-transparent">
              VocalisLab Pro
            </h1>
            <p className="text-sm text-slate-400">Bioacústica Fonoaudiológica — Praat/Parselmouth — VoiceLab v2.0</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 px-4 py-2 rounded-xl">
            <Volume2 className="w-4 h-4 text-sky-400" />
            <select value={selectedDeviceId} onChange={(e) => setSelectedDeviceId(e.target.value)}
              className="bg-transparent text-xs text-slate-200 outline-none cursor-pointer max-w-[220px] truncate">
              {dispositivos.map((d) => (
                <option key={d.deviceId} value={d.deviceId} className="bg-slate-900 text-white">
                  {d.label || `Mic ${d.deviceId.slice(0, 5)}`}
                </option>
              ))}
            </select>
          </div>
          <button onClick={() => setShowVoxplot(!showVoxplot)}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-900/90 border border-slate-800 rounded-xl text-xs text-slate-400 hover:text-slate-200 transition-colors">
            <Layers className="w-3.5 h-3.5" /> VOXplot
          </button>
        </div>
      </div>

      {/* Flow progress indicator */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex items-center gap-1 bg-slate-900/60 border border-slate-800 rounded-xl p-1">
          {([
            { id: 'protocol' as const, label: '1. Protocolo', icon: FileText },
            { id: 'capture' as const, label: '2. Captura', icon: Mic },
            { id: 'analyzing' as const, label: '3. Análisis', icon: Sparkles },
            { id: 'review' as const, label: '4. Revisión', icon: Shield, disabled: !r },
            { id: 'editor' as const, label: '5. Informe', icon: Edit3, disabled: !r },
          ]).map((step) => {
            const stepIdx = ['protocol', 'capture', 'analyzing', 'review', 'editor'].indexOf(step.id);
            const currentIdx = ['protocol', 'capture', 'analyzing', 'review', 'editor'].indexOf(flowStep);
            const isActive = step.id === flowStep;
            const isDone = stepIdx < currentIdx;
            const isDisabled = step.disabled || (stepIdx > currentIdx && !isDone);
            return (
              <button key={step.id} onClick={() => !isDisabled && setFlowStep(step.id as FlowStep)}
                disabled={isDisabled}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
                  isActive ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                  : isDone ? 'text-emerald-400 hover:text-emerald-300'
                  : 'text-slate-500 hover:text-slate-300 disabled:opacity-30'
                }`}>
                <step.icon className="w-3.5 h-3.5" />
                {step.label}
                {isDone && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
              </button>
            );
          })}
        </div>
      </div>

      {!BACKEND_URL && (
        <div className="max-w-7xl mx-auto mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          <p className="text-sm text-red-300">
            <strong>Backend no configurado.</strong> Configure <code className="bg-red-500/20 px-1 rounded">VITE_BACKEND_URL</code> en Vercel.
          </p>
        </div>
      )}
      {errorBackend && (
        <div className="max-w-7xl mx-auto mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          <p className="text-sm text-red-300">{errorBackend}</p>
        </div>
      )}
      {mensajeExito && (
        <div className="max-w-7xl mx-auto mb-4 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <p className="text-sm text-emerald-300">{mensajeExito}</p>
        </div>
      )}

      <div className="max-w-7xl mx-auto">
        {/* STEP 1: Protocol */}
        {flowStep === 'protocol' && (
          <div className="space-y-6">
            <TaskProtocolSelector selectedTask={selectedTask} onSelect={(id) => { setSelectedTask(id); setFlowStep('capture'); }}
              hasVocal={!!blobVocal} hasHabla={!!blobHabla} />
          </div>
        )}

        {/* STEP 2: Capture */}
        {flowStep === 'capture' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 space-y-6">
              <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl">
                <div className="flex items-center gap-2 mb-4 text-sky-400 font-semibold text-sm">
                  <User className="w-4 h-4" />
                  <span>Datos del Paciente</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                  <div>
                    <label className="text-xs text-slate-400 font-medium">Nombre Completo</label>
                    <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Ej. Martín García" className="w-full mt-1 px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-medium">DNI / Documento</label>
                    <input type="text" value={dni} onChange={(e) => setDni(e.target.value)} placeholder="Número de identificación" className="w-full mt-1 px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors" />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-slate-400 font-medium">Edad</label>
                      <input type="number" value={edad} onChange={(e) => setEdad(e.target.value)} placeholder="Años" className="w-full mt-1 px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-sky-500" />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 font-medium">Sexo</label>
                      <select value={sexo} onChange={(e) => setSexo(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-sky-500">
                        <option>Femenino</option>
                        <option>Masculino</option>
                        <option>Otro</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 font-medium">TMF (segundos)</label>
                    <input type="number" value={tmf} onChange={(e) => setTmf(e.target.value)} className="w-full mt-1 px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-sky-500" />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-xs text-slate-400 font-medium">Motivo / Médico Derivador</label>
                    <input type="text" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej. Disfonía funcional — Deriva Dr. López (ORL)" className="w-full mt-1 px-3 py-2 bg-slate-950/70 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors" />
                  </div>
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl space-y-4">
                <div className="flex items-center gap-2 text-sky-400 font-semibold text-sm">
                  <Sliders className="w-4 h-4" />
                  <span>Evaluación Perceptivo-Auditiva (0: Normal, 3: Severo)</span>
                </div>
                <div>
                  <span className="text-xs font-semibold text-slate-300 block mb-2">Escala GRBAS</span>
                  <div className="grid grid-cols-5 gap-2">
                    {(['G', 'R', 'B', 'A', 'S'] as const).map((param) => (
                      <div key={param} className="bg-slate-950/80 p-2 rounded-xl border border-slate-800 text-center">
                        <span className="text-[11px] font-bold text-slate-400 block mb-1">{param}</span>
                        <div className="flex justify-center gap-1">
                          {[0, 1, 2, 3].map((val) => (
                            <button key={val} type="button" onClick={() => setGrbas((prev) => ({ ...prev, [param]: val }))}
                              className={`w-5 h-6 rounded text-xs font-semibold transition-all ${grbas[param] === val ? 'bg-sky-500 text-white shadow-md shadow-sky-500/30' : 'text-slate-500 hover:text-slate-300'}`}>
                              {val}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs font-semibold text-slate-300 block mb-2">Escala RASATI</span>
                  <div className="grid grid-cols-6 gap-2">
                    {(['R', 'A', 'S', 'A2', 'T', 'I'] as const).map((param) => (
                      <div key={param} className="bg-slate-950/80 p-2 rounded-xl border border-slate-800 text-center">
                        <span className="text-[11px] font-bold text-slate-400 block mb-1">{param === 'A2' ? 'Aste.' : param}</span>
                        <div className="flex justify-center gap-1">
                          {[0, 1, 2, 3].map((val) => (
                            <button key={val} type="button" onClick={() => setRasati((prev) => ({ ...prev, [param]: val }))}
                              className={`w-5 h-6 rounded text-xs font-semibold transition-all ${rasati[param] === val ? 'bg-sky-500 text-white shadow-md shadow-sky-500/30' : 'text-slate-500 hover:text-slate-300'}`}>
                              {val}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-5 space-y-6">
              <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl flex flex-col items-center">
                <div className="w-full flex items-center justify-between mb-3 text-xs text-slate-400">
                  <span className="flex items-center gap-1.5 font-medium">
                    <Stethoscope className="w-4 h-4 text-sky-400" />
                    Señal en Vivo (Osciloscopio)
                  </span>
                  {(grabandoVocal || grabandoHabla) && (
                    <span className="flex items-center gap-1 text-red-400 animate-pulse font-bold">● GRABANDO 44.1 kHz</span>
                  )}
                </div>
                <div className="w-full h-28 bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-inner relative flex items-center justify-center">
                  <canvas ref={canvasRef} width={400} height={112} className="w-full h-full" />
                  {!grabandoVocal && !grabandoHabla && (
                    <span className="absolute text-xs text-slate-600 font-medium">Presiona grabar para capturar la señal</span>
                  )}
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl space-y-4">
                <div className="flex items-center gap-2 text-sky-400 font-semibold text-sm">
                  <Mic className="w-4 h-4" />
                  <span>Captura de Muestras</span>
                </div>
                <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-200">1. Vocal /a/ sostenida</p>
                    <p className="text-xs text-slate-400">Emisión a tono cómodo (4 segundos)</p>
                  </div>
                  <button type="button" onClick={() => grabarMuestra('vocal')} disabled={grabandoVocal || grabandoHabla}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${grabandoVocal ? 'bg-red-500 text-white animate-pulse' : blobVocal ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-sky-500 hover:bg-sky-400 text-white shadow-lg shadow-sky-500/25'}`}>
                    {grabandoVocal ? <><Square className="w-3.5 h-3.5 fill-current" /> Grabando...</> : blobVocal ? <><CheckCircle2 className="w-3.5 h-3.5" /> Lista</> : <><Mic className="w-3.5 h-3.5" /> Grabar</>}
                  </button>
                </div>
                <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-200">2. Habla continua</p>
                    <p className="text-xs text-slate-400">Lectura del texto estándar</p>
                  </div>
                  {grabandoHabla ? (
                    <button type="button" onClick={detenerHabla} className="px-4 py-2 bg-red-500 text-white rounded-xl text-xs font-semibold flex items-center gap-2 animate-pulse">
                      <Square className="w-3.5 h-3.5 fill-current" /> Detener
                    </button>
                  ) : (
                    <button type="button" onClick={() => grabarMuestra('habla')} disabled={grabandoVocal}
                      className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all ${blobHabla ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-slate-800 hover:bg-slate-700 text-slate-200'}`}>
                      {blobHabla ? <><CheckCircle2 className="w-3.5 h-3.5" /> Lista</> : <><Mic className="w-3.5 h-3.5" /> Grabar</>}
                    </button>
                  )}
                </div>
                <button type="button" onClick={ejecutarAnalisis} disabled={procesando || !blobVocal}
                  className={`w-full py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-xl transition-all ${procesando || !blobVocal ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white shadow-sky-500/20 active:scale-[0.98]'}`}>
                  <><FileText className="w-4 h-4" /> Analizar con Praat</>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Analyzing */}
        {flowStep === 'analyzing' && (
          <div className="max-w-2xl mx-auto">
            <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-8 rounded-2xl shadow-xl text-center">
              <div className="mb-6">
                <div className="w-16 h-16 mx-auto bg-sky-500/10 border border-sky-500/30 rounded-2xl flex items-center justify-center">
                  <Sparkles className="w-8 h-8 text-sky-400 animate-spin" />
                </div>
              </div>
              <h2 className="text-lg font-bold text-slate-100 mb-2">Analizando con Praat/Parselmouth</h2>
              <p className="text-sm text-slate-400 mb-6">Procesando audio y calculando métricas bioacústicas...</p>
              <div className="space-y-2">
                {ANALYSIS_STAGES.slice(0, analysisStage + 1).map((stage, i) => (
                  <div key={i} className={`flex items-center gap-2 text-xs px-4 py-2 rounded-lg transition-all ${
                    i === analysisStage ? 'bg-sky-500/10 text-sky-300 border border-sky-500/30' : 'text-emerald-400'
                  }`}>
                    {i < analysisStage ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : i === analysisStage ? (
                      <div className="w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <div className="w-3.5 h-3.5" />
                    )}
                    {stage}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: Clinical Review */}
        {flowStep === 'review' && r && (
          <ClinicalReviewScreen
            audioInfo={r.audio}
            metrics={r.metrics}
            avqiComponents={r.avqiComponents}
            tools={r.tools || []}
            timestamp={r.timestamp || new Date().toISOString()}
            engineVersion={r.engineVersion || 'N/D'}
            scriptVersion={r.scriptVersion || 'N/D'}
            fileHash={r.fileHash || r.audio?.file_hash_sha256 || 'N/D'}
            harmonics={r.harmonics || r.metrics?.harmonics || []}
            formants={r.formants || r.metrics?.formants || {}}
            ltas={r.ltas || r.metrics?.ltas || {}}
            spectral={r.spectral || r.metrics?.spectral || {}}
            modo={r.modo || 'clinico'}
            onViewJson={() => setShowJson(true)}
            onViewCsv={() => {
              if (r.csvExport) {
                const blob = new Blob([r.csvExport], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url; a.download = 'VocalisLab_Datos.csv'; a.click();
              }
            }}
            onViewGraphs={() => {}}
            onRecalculate={() => { setFlowStep('capture'); ejecutarAnalisis(); }}
            onDownloadPreliminar={descargarPdf}
            onApprove={() => { setApproved(true); setFlowStep('editor'); }}
          />
        )}

        {/* STEP 5: Report Editor */}
        {flowStep === 'editor' && r && (
          <div className="space-y-4">
            <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl">
              <ReportEditor
                patientData={{ nombre, dni, edad, sexo, motivo, derivador }}
                metrics={r.metrics}
                aiText={r.jsonExport?.sintesis_ia || ''}
                onSave={(fields, author) => console.log('Guardado:', { fields, author })}
                onExport={(fields) => { descargarPdf(); }}
              />
            </div>
            <div className="flex gap-3">
              <button onClick={() => setFlowStep('review')}
                className="px-6 py-3 rounded-xl font-bold text-sm flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition-all">
                ← Volver a Revisión
              </button>
              <button onClick={descargarPdf} disabled={procesando}
                className="flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white shadow-lg shadow-sky-500/20 transition-all disabled:opacity-40">
                <FileText className="w-4 h-4" /> Generar y Descargar PDF
              </button>
            </div>
          </div>
        )}

        {/* VOXplot optional panel */}
        {showVoxplot && (
          <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setShowVoxplot(false)}>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 max-w-2xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-amber-400" />
                  VOXplot — Importación Avanzada (Opcional)
                </h3>
                <button onClick={() => setShowVoxplot(false)} className="text-slate-400 hover:text-white text-lg">✕</button>
              </div>
              <p className="text-xs text-slate-400 mb-4">
                Importación opcional de datos exportados desde VOXplot. No es requerida para el análisis clínico.
              </p>
              <VoxPlotImport onImport={(data) => console.log('VOXplot importado:', data)} />
            </div>
          </div>
        )}

        {/* Raw data modal */}
        {showRawData && r && (
          <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setShowRawData(false)}>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 max-w-2xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-slate-100">Datos Crudos</h3>
                <button onClick={() => setShowRawData(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>
              <pre className="text-[10px] text-slate-300 font-mono whitespace-pre-wrap">{JSON.stringify(r, null, 2)}</pre>
            </div>
          </div>
        )}

        {/* JSON modal */}
        {showJson && r && (
          <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setShowJson(false)}>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 max-w-2xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-slate-100">JSON de Resultados</h3>
                <button onClick={() => setShowJson(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>
              <pre className="text-[10px] text-slate-300 font-mono whitespace-pre-wrap">{JSON.stringify(r.jsonExport, null, 2)}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
