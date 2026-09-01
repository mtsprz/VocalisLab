import React, { useState, useEffect, useRef } from 'react';
import {
  Activity, Mic, Square, FileText, CheckCircle2,
  Sparkles, Layers, Sliders, Volume2, User, Stethoscope, Save, AlertCircle,
  ChevronDown, ChevronRight, Shield, Edit3
} from 'lucide-react';
import { supabase } from '../utils/supabase';
import SeverityScale, { getSeverityLevel } from './SeverityScale';
import AnalysisControl from './AnalysisControl';
import VoxPlotImport from './VoxPlotImport';
import ReportEditor from './ReportEditor';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface AnalysisResult {
  audio: any;
  metrics: any;
  avqiComponents: any;
  tools: any[];
  jsonExport: any;
  csvExport: string;
}

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

  const [grabandoVocal, setGrabandoVocal] = useState(false);
  const [grabandoHabla, setGrabandoHabla] = useState(false);
  const [blobVocal, setBlobVocal] = useState<Blob | null>(null);
  const [blobHabla, setBlobHabla] = useState<Blob | null>(null);
  const [procesando, setProcesando] = useState(false);
  const [mensajeExito, setMensajeExito] = useState('');
  const [errorBackend, setErrorBackend] = useState('');

  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [activeTab, setActiveTab] = useState<'capture' | 'control' | 'editor' | 'voxplot'>('capture');
  const [showRawData, setShowRawData] = useState(false);
  const [showJson, setShowJson] = useState(false);
  const [approved, setApproved] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const mediaRecorderRef = useRef<any>(null);

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
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
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
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 44100,
        },
      });
      iniciarVisualizador(stream);
      const audioCtx = new AudioContext({ sampleRate: 44100 });
      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      const recordedSamples: Float32Array[] = [];
      processor.onaudioprocess = (e) => {
        recordedSamples.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      };
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
        if (tipo === 'vocal') setBlobVocal(wavBlob);
        else setBlobHabla(wavBlob);
      };

      mediaRecorderRef.current = { stop: stopRecording };
      if (tipo === 'vocal') {
        setGrabandoVocal(true);
        setTimeout(() => { stopRecording(); setGrabandoVocal(false); }, 4000);
      } else {
        setGrabandoHabla(true);
      }
    } catch (err) {
      alert('Error al acceder al micrófono o placa de audio.');
    }
  };

  const detenerHabla = () => {
    if (mediaRecorderRef.current?.stop) {
      mediaRecorderRef.current.stop();
      setGrabandoHabla(false);
    }
  };

  const ejecutarAnalisis = async () => {
    if (!blobVocal) { alert('Debes grabar la muestra de la vocal /a/ sostenida.'); return; }
    if (!BACKEND_URL) { alert('ERROR CRÍTICO: Configure VITE_BACKEND_URL en Vercel.'); return; }

    setProcesando(true);
    setErrorBackend('');
    setMensajeExito('');
    setAnalysisResult(null);

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

      if (!resJson.ok) {
        const errText = await resJson.text();
        throw new Error(`Error ${resJson.status}: ${errText}`);
      }

      const data = await resJson.json();
      setAnalysisResult(data);
      setActiveTab('control');
    } catch (err: any) {
      setErrorBackend(err.message || 'Error al procesar el análisis.');
    } finally {
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

  const handleVoxPlotImport = (data: any) => {
    console.log('VOXplot importado:', data);
  };

  const r = analysisResult;
  const m = r?.metrics;
  const avqi = r?.avqiComponents;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto mb-6 flex flex-col md:flex-row items-start md:items-center justify-between border-b border-slate-800 pb-6 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-sky-500/10 border border-sky-500/30 rounded-xl text-sky-400">
            <Activity className="w-7 h-7 animate-pulse" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-sky-400 bg-clip-text text-transparent">
              VocalisLab Pro
            </h1>
            <p className="text-sm text-slate-400">Bioacústica Fonoaudiológica — AVQI v03.01 — Praat/Parselmouth</p>
          </div>
        </div>
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

      <div className="max-w-7xl mx-auto mb-4 flex gap-1 bg-slate-900/60 border border-slate-800 rounded-xl p-1">
        {[
          { id: 'capture' as const, label: 'Captura', icon: Mic },
          { id: 'control' as const, label: 'Control', icon: Shield, disabled: !r },
          { id: 'editor' as const, label: 'Editor', icon: Edit3, disabled: !r },
          { id: 'voxplot' as const, label: 'VOXplot', icon: Layers },
        ].map((tab) => (
          <button key={tab.id} onClick={() => !tab.disabled && setActiveTab(tab.id)}
            disabled={tab.disabled}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeTab === tab.id ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30' : 'text-slate-500 hover:text-slate-300 disabled:opacity-30'
            }`}>
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="max-w-7xl mx-auto">
        {activeTab === 'capture' && (
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
                  <Layers className="w-4 h-4" />
                  <span>Captura de Muestras Estandarizadas</span>
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
                  {procesando ? (
                    <><Sparkles className="w-4 h-4 animate-spin text-sky-200" /> Procesando con Praat...</>
                  ) : (
                    <><FileText className="w-4 h-4" /> Analizar con Praat</>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'control' && r && (
          <div className="space-y-6">
            <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl">
              <AnalysisControl
                audioInfo={r.audio}
                metrics={m}
                avqiComponents={avqi}
                tools={r.tools || []}
                timestamp={r.jsonExport?.timestamp || new Date().toISOString()}
                engineVersion={m?.parselmouth_version || 'N/D'}
                scriptVersion={m?.praat_script || 'N/D'}
                fileHash={r.audio?.file_hash_sha256 || 'N/D'}
                onViewRaw={() => setShowRawData(true)}
                onViewJson={() => setShowJson(true)}
                onViewGraphs={() => {}}
                onRecalculate={ejecutarAnalisis}
                onDownloadPreliminar={descargarPdf}
                onEdit={() => setActiveTab('editor')}
                onApprove={() => { setApproved(true); setActiveTab('editor'); }}
                criticalErrors={r.audio?.valid === false ? r.audio.issues : []}
              />
            </div>

            {m && (
              <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl space-y-4">
                <div className="flex items-center gap-2 text-sky-400 font-semibold text-sm">
                  <Activity className="w-4 h-4" />
                  <span>Resultados Bioacústicos</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  <SeverityScale value={m.f0_mean} level={getSeverityLevel(m.f0_mean, [0, 0, 0])} label="F0 media" reference="Variable (edad, sexo)" unit=" Hz" />
                  <SeverityScale value={m.jitter_pct} level={getSeverityLevel(m.jitter_pct, [1.04, 2.0, 3.0])} label="Jitter local" reference="< 1.04%" unit="%" />
                  <SeverityScale value={m.shimmer_pct} level={getSeverityLevel(m.shimmer_pct, [3.81, 5.0, 7.0])} label="Shimmer local" reference="< 3.81%" unit="%" />
                  <SeverityScale value={m.shimmer_db} level={getSeverityLevel(m.shimmer_db, [0.5, 1.0, 2.0])} label="Shimmer dB" reference="< 0.5 dB" unit=" dB" />
                  <SeverityScale value={m.hnr_db} level={getSeverityLevel(m.hnr_db, [20, 15, 10], 'higher_better')} label="HNR" reference="> 20 dB" unit=" dB" />
                  <SeverityScale value={m.cpps_db} level={getSeverityLevel(m.cpps_db, [5.5, 3.0, 1.0], 'higher_better')} label="CPPS" reference="> 5.5 dB" unit=" dB" />
                </div>

                {avqi && (
                  <div className="mt-4 p-4 bg-slate-950/50 border border-slate-800 rounded-xl">
                    <div className="text-xs text-slate-400 uppercase tracking-wider mb-3">AVQI v03.01 — Componentes</div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                      {[
                        { label: 'CPPs', val: avqi.cpps_db, unit: 'dB' },
                        { label: 'HNR', val: avqi.hnr_db, unit: 'dB' },
                        { label: 'Shimmer local', val: avqi.shimmer_local_pct, unit: '%' },
                        { label: 'Shimmer dB', val: avqi.shimmer_local_db, unit: 'dB' },
                        { label: 'Spectral Slope', val: avqi.spectral_slope, unit: 'dB/oct' },
                        { label: 'Spectral Tilt', val: avqi.spectral_tilt, unit: 'dB' },
                      ].map((c) => (
                        <div key={c.label} className="flex justify-between px-2 py-1 bg-slate-900/50 rounded">
                          <span className="text-slate-400">{c.label}</span>
                          <span className={`font-mono ${c.val === null ? 'text-red-400' : 'text-slate-200'}`}>{c.val !== null ? `${c.val}${c.unit}` : 'N/D'}</span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-xs text-slate-500">AVQI v03.01:</span>
                      {avqi.calculable ? (
                        <SeverityScale value={avqi.avqi} level={getSeverityLevel(avqi.avqi, [2.0, 2.9, 3.5])} label="" reference="corte ≤ 2.9" compact />
                      ) : (
                        <span className="text-xs text-red-400 font-semibold">NO CALCULABLE — {avqi.error || 'Faltan componentes obligatorios'}</span>
                      )}
                    </div>
                  </div>
                )}

                {m.harmonics && m.harmonics.length > 0 && (
                  <div className="mt-4 p-4 bg-slate-950/50 border border-slate-800 rounded-xl">
                    <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Armónicos detectados</div>
                    <div className="flex flex-wrap gap-1.5">
                      {m.harmonics.map((h: any) => (
                        <span key={h.number} className="px-2 py-0.5 bg-sky-500/10 border border-sky-500/30 rounded text-[10px] text-sky-300 font-mono">
                          H{h.number}: {h.frequency_hz} Hz ({h.amplitude_db} dB)
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {m.formants && Object.keys(m.formants).length > 0 && (
                  <div className="mt-2 p-3 bg-slate-950/50 border border-slate-800 rounded-xl text-xs">
                    <span className="text-slate-400">Formantes:</span>
                    {m.formants.f1_hz && <span className="ml-2 text-slate-200">F1={m.formants.f1_hz} Hz</span>}
                    {m.formants.f2_hz && <span className="ml-2 text-slate-200">F2={m.formants.f2_hz} Hz</span>}
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <button onClick={descargarPdf} disabled={procesando}
                className="flex-1 py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white shadow-lg shadow-sky-500/20 transition-all disabled:opacity-40">
                <FileText className="w-4 h-4" /> Descargar Informe PDF
              </button>
              <button onClick={() => setActiveTab('editor')}
                className="px-6 py-3 rounded-xl font-bold text-sm flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition-all">
                <Edit3 className="w-4 h-4" /> Editar Informe
              </button>
            </div>
          </div>
        )}

        {activeTab === 'editor' && r && (
          <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl">
            <ReportEditor
              patientData={{ nombre, dni, edad, sexo, motivo, derivador }}
              metrics={m}
              aiText={r.jsonExport?.sintesis_ia || ''}
              onSave={(fields, author) => console.log('Guardado:', { fields, author })}
              onExport={(fields) => { console.log('Exportar:', fields); descargarPdf(); }}
            />
          </div>
        )}

        {activeTab === 'voxplot' && (
          <div className="space-y-4">
            <VoxPlotImport onImport={handleVoxPlotImport} />
          </div>
        )}

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
