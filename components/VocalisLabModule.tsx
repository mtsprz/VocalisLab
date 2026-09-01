import React, { useState, useEffect, useRef } from 'react';
import { Mic, Square, Play, RefreshCw, FileText, Download, CheckCircle2, AlertCircle, Volume2, User } from 'lucide-react';

export const VocalisLabModule: React.FC = () => {
  // Device selection state
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');

  // Patient metadata state
  const [patientName, setPatientName] = useState<string>('');
  const [patientAge, setPatientAge] = useState<number>(30);
  const [patientGender, setPatientGender] = useState<string>('Femenino');
  const [tmf, setTmf] = useState<number>(15);

  // Clinical scales state
  const [grbas, setGrbas] = useState({ G: 0, R: 0, B: 0, A: 0, S: 0 });
  const [rasati, setRasati] = useState({ R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 });

  // Recording state
  const [recordingType, setRecordingType] = useState<'sustained_a' | 'reading' | null>(null);
  const [sustainedBlob, setSustainedBlob] = useState<Blob | null>(null);
  const [readingBlob, setReadingBlob] = useState<Blob | null>(null);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [timer, setTimer] = useState<number>(0);

  // Analysis result state
  const [loading, setLoading] = useState<boolean>(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<any>(null);

  useEffect(() => {
    // Load audio input devices (external audio cards, mics)
    navigator.mediaDevices.enumerateDevices().then((allDevices) => {
      const audioInputs = allDevices.filter(d => d.kind === 'audioinput');
      setDevices(audioInputs);
      if (audioInputs.length > 0) {
        setSelectedDeviceId(audioInputs[0].deviceId);
      }
    }).catch(err => console.error("Error enumerating audio devices:", err));
  }, []);

  const startRecording = async (type: 'sustained_a' | 'reading') => {
    try {
      setErrorMsg('');
      audioChunksRef.current = [];
      const constraints = {
        audio: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : true
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        if (type === 'sustained_a') {
          setSustainedBlob(audioBlob);
        } else {
          setReadingBlob(audioBlob);
        }
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingType(type);
      setTimer(0);

      timerRef.current = setInterval(() => {
        setTimer(prev => prev + 1);
      }, 1000);

      // Auto stop for sustained /a/ after 4 seconds
      if (type === 'sustained_a') {
        setTimeout(() => {
          stopRecording();
        }, 4000);
      }
    } catch (err) {
      console.error("Error starting recording:", err);
      setErrorMsg("No se pudo acceder al micrófono seleccionado. Verifique permisos.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setRecordingType(null);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleAnalyze = async () => {
    if (!sustainedBlob || !readingBlob) {
      setErrorMsg("Debe grabar tanto la /a/ sostenida como la lectura continua.");
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      const formData = new FormData();
      formData.append("audio_vocal", sustainedBlob, "sustained_a.wav");
      formData.append("audio_habla", readingBlob, "reading.wav");
      formData.append("nombre", patientName || "Paciente Anónimo");
      formData.append("edad", patientAge.toString());
      formData.append("sexo", "No especificado");
      formData.append("dni", "00000000");
      formData.append("motivo", "Evaluación vocal bioacústica");
      formData.append("derivador", "Profesional fonoaudiólogo");
      formData.append("tmf", tmf.toString());

      // Vercel serverless relative endpoint
      const response = await fetch("/api/analizar-y-reportar", {
        method: "POST",
        body: formData
      });

      if (response.ok) {
        const blobPdf = await response.blob();
        const url = window.URL.createObjectURL(blobPdf);
        const a = document.createElement('a');
        a.href = url;
        a.download = `VocalisLab_Informe_${patientName || 'Paciente'}.pdf`;
        a.click();
        
        setAnalysisResult({
          success: true,
          avqi: "Analizado",
          metrics: { f0_mean: "Calculado", jitter_local: "OK", shimmer_local: "OK", hnr: "OK", cpps: "OK" },
          synthesis: "Informe generado y descargado exitosamente en PDF."
        });
      } else {
        setErrorMsg("Error en el procesamiento bioacústico en el servidor Vercel.");
      }
    } catch (err) {
      console.error("Connection error to serverless API:", err);
      setErrorMsg("No se pudo conectar con la función serverless de Vercel (/api/analizar-y-reportar).");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8 bg-slate-50 min-h-screen">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Volume2 className="text-indigo-600 w-7 h-7" />
            VocalisLab <span className="text-xs bg-indigo-100 text-indigo-700 px-2.5 py-1 rounded-full font-semibold">Bioacústica Avanzada & AVQI v03.01</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1">Plataforma fonoaudiológica de análisis vocal con Praat, VOXplot, VoxMetria y Síntesis IA Rioplatense.</p>
        </div>
        
        {/* Hardware Mic Selector */}
        <div className="w-full md:w-auto">
          <label className="block text-xs font-semibold text-slate-600 mb-1">Selector de Placa / Micrófono Externo:</label>
          <select 
            value={selectedDeviceId} 
            onChange={(e) => setSelectedDeviceId(e.target.value)}
            className="w-full md:w-72 bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500"
          >
            {devices.map(d => (
              <option key={d.deviceId} value={d.deviceId}>{d.label || `Micrófono (${d.deviceId.slice(0,5)}...)`}</option>
            ))}
            {devices.length === 0 && <option value="">Micrófono predeterminado del sistema</option>}
          </select>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg flex items-center gap-3 text-red-700">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <p className="text-sm">{errorMsg}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Col: Patient Form & Clinical Scales */}
        <div className="space-y-6 lg:col-span-1">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
            <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <User className="w-5 h-5 text-indigo-600" /> Datos del Paciente
            </h2>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Nombre Completo:</label>
              <input 
                type="text" 
                value={patientName} 
                onChange={(e) => setPatientName(e.target.value)} 
                placeholder="Ej. María Gómez"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Edad:</label>
                <input 
                  type="number" 
                  value={patientAge} 
                  onChange={(e) => setPatientAge(Number(e.target.value))} 
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">TMF (seg):</label>
                <input 
                  type="number" 
                  value={tmf} 
                  onChange={(e) => setTmf(Number(e.target.value))} 
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>

          {/* GRBAS & RASATI Scales */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
            <h2 className="text-lg font-bold text-slate-800">Escalas Perceptuales</h2>
            
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">GRBAS (0-3)</label>
              <div className="grid grid-cols-5 gap-2 text-center text-xs">
                {Object.keys(grbas).map(key => (
                  <div key={key} className="bg-slate-50 p-2 rounded border">
                    <span className="font-bold block text-slate-600">{key}</span>
                    <select 
                      value={(grbas as any)[key]} 
                      onChange={(e) => setGrbas({...grbas, [key]: Number(e.target.value)})}
                      className="mt-1 w-full text-xs border rounded bg-white"
                    >
                      <option value={0}>0</option>
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                      <option value={3}>3</option>
                    </select>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">RASATI (0-3)</label>
              <div className="grid grid-cols-6 gap-1 text-center text-xs">
                {['R', 'A', 'S', 'A2', 'T', 'I'].map((key, idx) => {
                  const stateKey = idx === 3 ? 'A2' : key;
                  return (
                    <div key={key} className="bg-slate-50 p-1.5 rounded border">
                      <span className="font-bold block text-slate-600">{key}</span>
                      <select 
                        value={(rasati as any)[stateKey]} 
                        onChange={(e) => setRasati({...rasati, [stateKey]: Number(e.target.value)})}
                        className="mt-1 w-full text-xs border rounded bg-white"
                      >
                        <option value={0}>0</option>
                        <option value={1}>1</option>
                        <option value={2}>2</option>
                        <option value={3}>3</option>
                      </select>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Right Col: Recorders & Results */}
        <div className="space-y-6 lg:col-span-2">
          
          {/* Recorders Box */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-6">
            <h2 className="text-lg font-bold text-slate-800">Grabación de Muestras VocalisLab (44.1 kHz)</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              
              {/* Sample 1: /a/ sustained */}
              <div className="border border-slate-200 p-5 rounded-xl bg-slate-50 flex flex-col justify-between space-y-4">
                <div>
                  <h3 className="font-semibold text-slate-800 text-sm">1. Vocal /a/ Sostenida (4 seg)</h3>
                  <p className="text-xs text-slate-500 mt-1">Emisión continua a tono y sonoridad habituales.</p>
                </div>
                
                <div className="flex items-center justify-between">
                  {isRecording && recordingType === 'sustained_a' ? (
                    <div className="flex items-center gap-2 text-red-600 font-bold animate-pulse">
                      <span className="w-3 h-3 bg-red-600 rounded-full"></span> Grabando ({timer}s / 4s)
                    </div>
                  ) : sustainedBlob ? (
                    <span className="text-emerald-600 text-xs font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" /> Muestra lista ({Math.round(sustainedBlob.size / 1024)} KB)
                    </span>
                  ) : (
                    <span className="text-slate-400 text-xs">Sin grabar</span>
                  )}

                  <div className="flex gap-2">
                    <button 
                      onClick={() => startRecording('sustained_a')}
                      disabled={isRecording}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-1 disabled:opacity-50"
                    >
                      <Mic className="w-4 h-4" /> Grabar
                    </button>
                    {isRecording && recordingType === 'sustained_a' && (
                      <button 
                        onClick={stopRecording}
                        className="bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded-lg text-xs"
                      >
                        <Square className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Sample 2: Continuous Reading */}
              <div className="border border-slate-200 p-5 rounded-xl bg-slate-50 flex flex-col justify-between space-y-4">
                <div>
                  <h3 className="font-semibold text-slate-800 text-sm">2. Lectura Continua / Habla</h3>
                  <p className="text-xs text-slate-500 mt-1">Texto estandarizado o conversación espontánea (5-10s).</p>
                </div>
                
                <div className="flex items-center justify-between">
                  {isRecording && recordingType === 'reading' ? (
                    <div className="flex items-center gap-2 text-red-600 font-bold animate-pulse">
                      <span className="w-3 h-3 bg-red-600 rounded-full"></span> Grabando ({timer}s)
                    </div>
                  ) : readingBlob ? (
                    <span className="text-emerald-600 text-xs font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-4 h-4" /> Muestra lista ({Math.round(readingBlob.size / 1024)} KB)
                    </span>
                  ) : (
                    <span className="text-slate-400 text-xs">Sin grabar</span>
                  )}

                  <div className="flex gap-2">
                    <button 
                      onClick={() => startRecording('reading')}
                      disabled={isRecording}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-medium flex items-center gap-1 disabled:opacity-50"
                    >
                      <Mic className="w-4 h-4" /> Grabar
                    </button>
                    {isRecording && recordingType === 'reading' && (
                      <button 
                        onClick={stopRecording}
                        className="bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded-lg text-xs"
                      >
                        <Square className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>

            </div>

            <button 
              onClick={handleAnalyze}
              disabled={loading || !sustainedBlob || !readingBlob}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-3 rounded-xl font-bold text-sm shadow-md transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <FileText className="w-5 h-5" />}
              {loading ? 'Procesando Bioacústica (Praat + AVQI + Groq IA)...' : 'Analizar y Generar Reporte Fonoaudiológico'}
            </button>
          </div>

          {/* Results Display */}
          {analysisResult && (
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-6">
              <div className="flex justify-between items-center border-b pb-4">
                <h3 className="text-lg font-bold text-slate-800">Resultados del Análisis VocalisLab</h3>
                <a 
                  href={`http://localhost:7860${analysisResult.pdf_url}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2"
                >
                  <Download className="w-4 h-4" /> Descargar PDF ReportLab
                </a>
              </div>

              {/* AVQI Score Card */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gradient-to-br from-indigo-50 to-blue-50 p-5 rounded-xl border border-indigo-100 flex flex-col justify-center items-center text-center">
                  <span className="text-xs font-bold uppercase tracking-wider text-indigo-600">Índice de Calidad Acústica Vocal</span>
                  <span className="text-4xl font-extrabold text-indigo-900 mt-2">{analysisResult.avqi}</span>
                  <span className="text-xs text-slate-500 mt-1">AVQI v03.01 (Umbral normalidad &lt; 2.9)</span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-50 p-3 rounded-xl border">
                    <span className="text-xs text-slate-500 block">F0 Media</span>
                    <span className="text-base font-bold text-slate-800">{analysisResult.metrics.f0_mean} Hz</span>
                    <span className="text-[10px] text-slate-400">Praat</span>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-xl border">
                    <span className="text-xs text-slate-500 block">CPPS</span>
                    <span className="text-base font-bold text-slate-800">{analysisResult.metrics.cpps} dB</span>
                    <span className="text-[10px] text-slate-400">VoxMetria</span>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-xl border">
                    <span className="text-xs text-slate-500 block">Jitter Local</span>
                    <span className="text-base font-bold text-slate-800">{analysisResult.metrics.jitter_local}%</span>
                    <span className="text-[10px] text-slate-400">Praat</span>
                  </div>
                  <div className="bg-slate-50 p-3 rounded-xl border">
                    <span className="text-xs text-slate-500 block">HNR</span>
                    <span className="text-base font-bold text-slate-800">{analysisResult.metrics.hnr} dB</span>
                    <span className="text-[10px] text-slate-400">Praat</span>
                  </div>
                </div>
              </div>

              {/* AI Rioplatense Synthesis */}
              <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">Síntesis Diagnóstica (Groq Llama-3.3 - Rioplatense)</h4>
                <p className="text-sm text-slate-700 whitespace-pre-line leading-relaxed">{analysisResult.synthesis}</p>
              </div>

            </div>
          )}

        </div>

      </div>
    </div>
  );
};
export default VocalisLabModule;
