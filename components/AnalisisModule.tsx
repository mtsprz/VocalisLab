import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Upload, Loader2, Activity, AlertCircle, CheckCircle2 } from 'lucide-react';
import ClinicalReviewScreen from './ClinicalReviewScreen';
import ReportEditor from './ReportEditor';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props { pacienteId: string | null; }

interface AnalysisResult {
  audio: any; metrics: any; tools: any[]; charts: any;
  harmonics: any[]; formants: any; ltas: any; spectral: any;
  waveform: any; spectrogram: any; voxplot: any;
  avqiStatus: string; crossCheck: any;
}

export default function AnalisisModule({ pacienteId }: Props) {
  const [step, setStep] = useState<'capture' | 'analyzing' | 'review' | 'editor'>('capture');
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const [grbas, setGrbas] = useState({ G: 0, R: 0, B: 0, A: 0, S: 0 });
  const [rasati, setRasati] = useState({ R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 });
  const [edad, setEdad] = useState('');
  const [sexo, setSexo] = useState('Femenino');
  const [profNombre, setProfNombre] = useState('');
  const [profTitulo, setProfTitulo] = useState('Lic. en Fonoaudiología');
  const [profMatricula, setProfMatricula] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const STAGES = [
    'Validando señal...', 'Ejecutando Praat...', 'Calculando F0...',
    'Midiendo Jitter...', 'Midiendo Shimmer...', 'Calculando HNR...',
    'Calculando CPPS...', 'Extrayendo formantes...', 'Componentes AVQI...',
    'Generando espectrograma...', 'Generando gráficos...', 'Informe listo.',
  ];

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        setAudioBlob(new Blob(chunksRef.current, { type: 'audio/webm' }));
        stream.getTracks().forEach(t => t.stop());
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
    } catch { setError('No se pudo acceder al micrófono'); }
  };

  const stopRecording = () => { mediaRecorderRef.current?.stop(); setRecording(false); };

  const analyze = async () => {
    if (!audioBlob) return;
    setStep('analyzing');
    setProgress(0);
    setError('');
    const iv = setInterval(() => setProgress(p => Math.min(p + 8, 90)), 300);

    try {
      const fd = new FormData();
      fd.append('audio', audioBlob, 'vocal_sample.webm');
      fd.append('grbas', JSON.stringify(grbas));
      fd.append('rasati', JSON.stringify(rasati));
      fd.append('edad', edad);
      fd.append('sexo', sexo);
      fd.append('prof_nombre', profNombre);
      fd.append('prof_titulo', profTitulo);
      fd.append('prof_matricula', profMatricula);
      fd.append('modo', 'clinico');

      const r = await fetch(`${BACKEND_URL}/api/analizar-y-reportar`, { method: 'POST', body: fd });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setResult(data);
      setProgress(100);
      setStep('review');
    } catch (e: any) {
      setError(e.message || 'Error en análisis');
      setStep('capture');
    }
    clearInterval(iv);
  };

  const ScaleButtons = ({ value, onChange }: { value: number; onChange: (v: number) => void }) => (
    <div className="flex gap-1">
      {[0, 1, 2, 3].map(v => (
        <button key={v} onClick={() => onChange(v)}
          className={`w-8 h-8 rounded text-xs font-bold ${
            value === v ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}>{v}</button>
      ))}
    </div>
  );

  if (step === 'capture') {
    return (
      <div className="max-w-3xl space-y-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-800 mb-3">Datos del Paciente</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="text-xs text-gray-500">Edad</label>
              <input value={edad} onChange={e => setEdad(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" placeholder="45" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Sexo</label>
              <select value={sexo} onChange={e => setSexo(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm">
                <option>Femenino</option><option>Masculino</option><option>Otro</option>
              </select>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-800 mb-3">Evaluación Perceptual (GRBAS)</h3>
          <div className="grid grid-cols-5 gap-3">
            {(['G', 'R', 'B', 'A', 'S'] as const).map(k => (
              <div key={k} className="text-center">
                <p className="text-xs font-bold text-gray-600 mb-1">{k}</p>
                <ScaleButtons value={grbas[k]} onChange={v => setGrbas({ ...grbas, [k]: v })} />
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-800 mb-3">Grabar Muestra Vocal (5s sostenido)</h3>
          <div className="flex items-center gap-3">
            {!recording ? (
              <button onClick={startRecording} className="flex items-center gap-2 px-5 py-3 bg-red-500 text-white rounded-lg font-medium hover:bg-red-600">
                <Mic size={18} /> Grabar
              </button>
            ) : (
              <button onClick={() => { stopRecording(); }} className="flex items-center gap-2 px-5 py-3 bg-gray-800 text-white rounded-lg font-medium animate-pulse">
                <Square size={18} /> Detener
              </button>
            )}
            {audioBlob && (
              <button onClick={analyze} className="flex items-center gap-2 px-5 py-3 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700">
                <Activity size={18} /> Analizar
              </button>
            )}
          </div>
          {error && <p className="text-sm text-red-600 mt-3 flex items-center gap-1"><AlertCircle size={14} /> {error}</p>}
        </div>
      </div>
    );
  }

  if (step === 'analyzing') {
    return (
      <div className="max-w-2xl mx-auto text-center py-16">
        <Loader2 size={48} className="animate-spin text-indigo-600 mx-auto mb-4" />
        <p className="text-lg font-semibold text-gray-800">Analizando...</p>
        <div className="mt-4 bg-gray-200 rounded-full h-2 overflow-hidden">
          <div className="bg-indigo-600 h-full rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
        <p className="text-sm text-gray-500 mt-2">{STAGES[Math.min(Math.floor(progress / 8), STAGES.length - 1)]}</p>
      </div>
    );
  }

  if (step === 'review' && result) {
    return (
      <div className="space-y-4">
        <ClinicalReviewScreen result={result} grbas={grbas} rasati={rasati} />
        <div className="flex gap-2">
          <button onClick={() => { setResult(null); setStep('capture'); }} className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
            Nuevo Análisis
          </button>
          <button onClick={() => setStep('editor')} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
            Editar Informe
          </button>
        </div>
      </div>
    );
  }

  if (step === 'editor' && result) {
    return (
      <div>
        <button onClick={() => setStep('review')} className="mb-3 text-sm text-indigo-600 hover:underline">
          ← Volver a revisión
        </button>
        <ReportEditor result={result} grbas={grbas} rasati={rasati} profNombre={profNombre} profTitulo={profTitulo} profMatricula={profMatricula} />
      </div>
    );
  }

  return null;
}
