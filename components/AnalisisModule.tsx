import React, { useState, useRef, useEffect } from 'react';
import {
  Mic, Square, Upload, Loader2, Activity, AlertCircle, CheckCircle2,
  ChevronDown, ChevronUp, Shield, FileText, User, Sparkles, BarChart3
} from 'lucide-react';
import ClinicalReviewScreen from './ClinicalReviewScreen';
import ReportEditor from './ReportEditor';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
}

export default function AnalisisModule({ pacienteId }: Props) {
  const clinical = useClinical();

  const [step, setStep] = useState<'capture' | 'analyzing' | 'review' | 'editor'>('capture');
  const [recordingVocal, setRecordingVocal] = useState(false);
  const [recordingHabla, setRecordingHabla] = useState(false);
  const [audioBlobVocal, setAudioBlobVocal] = useState<Blob | null>(null);
  const [audioBlobHabla, setAudioBlobHabla] = useState<Blob | null>(null);

  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);

  // Auto-inherit GRBAS, RASATI, Sexo, Edad from ClinicalContext (End of redundancy!)
  const [grbas, setGrbas] = useState(clinical.data.escalas.grbas || { G: 0, R: 0, B: 0, A: 0, S: 0 });
  const [rasati, setRasati] = useState(clinical.data.escalas.rasati || { R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 });
  const [vhi10, setVhi10] = useState(clinical.data.escalas.vhi10_total || 0);
  const [tmeSec, setTmeSec] = useState(clinical.data.escalas.tme_segundos || 0);

  const [edad, setEdad] = useState(
    clinical.data.paciente.fecha_nacimiento
      ? String(new Date().getFullYear() - new Date(clinical.data.paciente.fecha_nacimiento).getFullYear())
      : '40'
  );
  const [sexo, setSexo] = useState(clinical.data.paciente.sexo || 'Femenino');
  const [profNombre, setProfNombre] = useState('Lic. Fonoaudiólogo/a');
  const [profTitulo, setProfTitulo] = useState('Especialista en Voz Bioacústica');
  const [profMatricula, setProfMatricula] = useState('M.N. 12345');

  const [showPerceptualCard, setShowPerceptualCard] = useState(true);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Update inherited scales when clinical context changes
  useEffect(() => {
    if (clinical.data.escalas.grbas) setGrbas(clinical.data.escalas.grbas);
    if (clinical.data.escalas.rasati) setRasati(clinical.data.escalas.rasati);
    if (clinical.data.escalas.vhi10_total) setVhi10(clinical.data.escalas.vhi10_total);
    if (clinical.data.escalas.tme_segundos) setTmeSec(clinical.data.escalas.tme_segundos);
    if (clinical.data.paciente.sexo) setSexo(clinical.data.paciente.sexo);
  }, [clinical.data.escalas, clinical.data.paciente]);

  const STAGES = [
    'Validando señal de audio...', 'Iniciando servidor de análisis Praat...',
    'Extrayendo F0 y tono fundamental...', 'Midiendo Jitter local y RAP...',
    'Midiendo Shimmer local y APQ...', 'Calculando HNR y CPPS cepstral...',
    'Midiendo formantes F1-F4...', 'Calculando componentes AVQI...',
    'Generando espectrograma de banda estrecha...', 'Renderizando gráficos clínicos...',
    'Sintetizando cross-check bioacústico...', 'Análisis completado.',
  ];

  const startRecording = async (type: 'vocal' | 'habla') => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        if (type === 'vocal') setAudioBlobVocal(blob);
        else setAudioBlobHabla(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      mr.start();
      mediaRecorderRef.current = mr;
      if (type === 'vocal') setRecordingVocal(true);
      else setRecordingHabla(true);
      setError('');
    } catch {
      setError('No se pudo acceder al micrófono para la grabación.');
    }
  };

  const stopRecording = (type: 'vocal' | 'habla') => {
    mediaRecorderRef.current?.stop();
    if (type === 'vocal') setRecordingVocal(false);
    else setRecordingHabla(false);
  };

  const analyze = async () => {
    if (!audioBlobVocal) {
      setError('Se requiere al menos la muestra vocal sostenida (/a/)');
      return;
    }

    setStep('analyzing');
    setProgress(0);
    setError('');

    const interval = setInterval(() => {
      setProgress(p => Math.min(p + 7, 92));
    }, 280);

    try {
      const fd = new FormData();
      fd.append('audio_vocal', audioBlobVocal, 'vocal_a.webm');
      if (audioBlobHabla) {
        fd.append('audio_habla', audioBlobHabla, 'habla_continua.webm');
      }
      fd.append('grbas', JSON.stringify(grbas));
      fd.append('rasati', JSON.stringify(rasati));
      fd.append('edad', edad);
      fd.append('sexo', sexo);
      fd.append('prof_nombre', profNombre);
      fd.append('prof_titulo', profTitulo);
      fd.append('prof_matricula', profMatricula);
      fd.append('modo', 'clinico');

      const r = await fetch(`${BACKEND_URL}/api/analizar`, { method: 'POST', body: fd });
      if (!r.ok) {
        const errData = await r.json().catch(() => ({}));
        throw new Error(errData.detail || `Error del servidor HTTP ${r.status}`);
      }

      const data = await r.json();
      setResult(data);
      setProgress(100);
      setStep('review');

      // Sync metrics to global clinical context
      if (data.metrics) {
        clinical.setAcustica({
          f0_mean: data.metrics.f0_mean,
          f0_min: data.metrics.f0_min,
          f0_max: data.metrics.f0_max,
          f0_sd: data.metrics.f0_sd,
          jitter_local_pct: data.metrics.jitter_pct,
          shimmer_local_pct: data.metrics.shimmer_pct,
          hnr_db: data.metrics.hnr_db,
          cpps_db: data.metrics.cpps_db,
          nhr: data.metrics.nhr,
          avqi: data.avqiComponents?.avqi,
          f1_hz: data.metrics.f1_hz,
          f2_hz: data.metrics.f2_hz,
          formants: data.metrics.formants,
          spectral: data.metrics.spectral,
        });
        clinical.markStep('analisis');

        // Persistir análisis en backend (fire-and-forget, mapeando claves al schema)
        if (pacienteId) {
          try {
            const m = data.metrics;
            const flat = {
              f0_mean: m.f0_mean, f0_min: m.f0_min, f0_max: m.f0_max,
              f0_sd: m.f0_sd, f0_range: m.f0_range,
              jitter_local_pct: m.jitter_pct ?? m.jitter_local_pct,
              jitter_rap_pct: m.jitter_rap_pct,
              jitter_ppq5_pct: m.jitter_ppq5_pct,
              shimmer_local_pct: m.shimmer_pct ?? m.shimmer_local_pct,
              shimmer_apq3_pct: m.shimmer_apq3_pct,
              shimmer_apq5_pct: m.shimmer_apq5_pct,
              hnr_db: m.hnr_db, cpps_db: m.cpps_db,
              nhr: m.nhr, nne_db: m.nne_db,
              avqi: data.avqiComponents?.avqi,
              f1_hz: m.f1_hz, f2_hz: m.f2_hz, f3_hz: m.f3_hz, f4_hz: m.f4_hz,
              intensity_mean_db: m.intensity_mean_db,
            };
            const fd = new FormData();
            fd.append('paciente_id', pacienteId);
            fd.append('metrics_json', JSON.stringify(flat));
            fd.append('cross_check_json', JSON.stringify(data.crossCheck || {}));
            fd.append('charts_json', '{}');
            fd.append('modo', 'clinico');
            fetch(`${BACKEND_URL}/api/analisis_acusticos`, { method: 'POST', body: fd }).catch(() => {});
          } catch {}
        }
      }
    } catch (e: any) {
      setError(e.message || 'Error durante el análisis bioacústico.');
      setStep('capture');
    } finally {
      clearInterval(interval);
    }
  };

  if (step === 'capture') {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header Banner */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 flex items-center justify-center font-bold">
              <Activity size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                Análisis Bioacústico Instrumental Praat
                {clinical.data.paciente.nombre_completo && (
                  <span className="text-xs font-semibold text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-950/50 px-2.5 py-0.5 rounded-full border border-cyan-200 dark:border-cyan-800/40">
                    {clinical.data.paciente.nombre_completo}
                  </span>
                )}
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Lámina acústica objetiva: Perturbación (Jitter/Shimmer), Ruido (HNR/CPPS/AVQI) y Espectrografía
              </p>
            </div>
          </div>
        </div>

        {/* 1. TARJETA DE REFERENCIA PERCEPTUAL HEREDADA (SIN REDUNDANCIA) */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-5 shadow-sm space-y-3">
          <div
            onClick={() => setShowPerceptualCard(!showPerceptualCard)}
            className="flex items-center justify-between cursor-pointer select-none"
          >
            <div className="flex items-center gap-2">
              <Shield size={16} className="text-indigo-500" />
              <h3 className="font-bold text-sm text-gray-900 dark:text-white">
                Evaluación Perceptual e Historia Clínica Heredada
              </h3>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold">
                Auto-Sincronizado
              </span>
            </div>
            <button className="text-gray-400 hover:text-gray-600 dark:hover:text-white">
              {showPerceptualCard ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
          </div>

          {showPerceptualCard && (
            <div className="pt-3 border-t border-gray-100 dark:border-white/5 grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              {/* Resumen GRBAS */}
              <div className="bg-gray-50 dark:bg-white/5 p-3 rounded-xl border border-gray-100 dark:border-white/5 space-y-1">
                <span className="font-bold text-gray-700 dark:text-gray-300 block mb-1">Escala GRBAS</span>
                <div className="flex items-center gap-2 font-mono text-sm font-black text-indigo-600 dark:text-indigo-400">
                  <span>G{grbas.G}</span>
                  <span>R{grbas.R}</span>
                  <span>B{grbas.B}</span>
                  <span>A{grbas.A}</span>
                  <span>S{grbas.S}</span>
                </div>
                <p className="text-[10px] text-gray-400">Grado disfonía, Aspereza, Soplo, Astenia, Tensión</p>
              </div>

              {/* Resumen RASATI */}
              <div className="bg-gray-50 dark:bg-white/5 p-3 rounded-xl border border-gray-100 dark:border-white/5 space-y-1">
                <span className="font-bold text-gray-700 dark:text-gray-300 block mb-1">Escala RASATI</span>
                <div className="flex items-center gap-2 font-mono text-sm font-black text-purple-600 dark:text-purple-400">
                  <span>R{rasati.R}</span>
                  <span>A{rasati.A}</span>
                  <span>S{rasati.S}</span>
                  <span>A2{rasati.A2}</span>
                  <span>T{rasati.T}</span>
                  <span>I{rasati.I}</span>
                </div>
                <p className="text-[10px] text-gray-400">Ronquera, Aspereza, Soplo, Astenia, Tensión, Inestabilidad</p>
              </div>

              {/* Autopercepción Paciente VHI-10 & TME */}
              <div className="bg-gray-50 dark:bg-white/5 p-3 rounded-xl border border-gray-100 dark:border-white/5 space-y-1">
                <span className="font-bold text-gray-700 dark:text-gray-300 block mb-1">Autopercepción & TME</span>
                <div className="flex items-center justify-between text-xs font-bold text-gray-800 dark:text-gray-200">
                  <span>VHI-10 Total: <strong className="text-amber-600 dark:text-amber-400">{vhi10}/40</strong></span>
                  <span>TME: <strong className="text-cyan-600 dark:text-cyan-400">{tmeSec}s</strong></span>
                </div>
                <p className="text-[10px] text-gray-400">Índice de Incapacidad Vocal y Tiempo Máximo Fonación</p>
              </div>
            </div>
          )}
        </div>

        {/* 2. DATOS BIOGRÁFICOS DEL PACIENTE */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-5 shadow-sm space-y-3">
          <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2 border-b border-gray-100 dark:border-white/5 pb-2">
            <User size={16} className="text-indigo-500" />
            Ajuste de Parámetros Normativos por Edad y Sexo
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                Edad del Paciente
              </label>
              <input
                type="number"
                value={edad}
                onChange={e => setEdad(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 text-gray-800 dark:text-gray-100 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                Sexo Biológico
              </label>
              <select
                value={sexo}
                onChange={e => setSexo(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500"
              >
                <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100" value="Femenino">Femenino</option>
                <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100" value="Masculino">Masculino</option>
                <option className="bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100" value="Otro">Otro</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-600 dark:text-gray-300 mb-1">
                Profesional Responsable
              </label>
              <input
                type="text"
                value={profNombre}
                onChange={e => setProfNombre(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 text-gray-800 dark:text-gray-100 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        </div>

        {/* 3. CAPTURA DE MUESTRAS VOCALES Y ANÁLISIS */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2 border-b border-gray-100 dark:border-white/5 pb-2">
            <Mic size={16} className="text-red-500" />
            Grabación de Muestra Vocal Sustentada /a/ y Habla Continua
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Muestra Vocal Sustentada /a/ */}
            <div className="p-4 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-800 dark:text-white">
                  Muestra 1: Vocal Sustentada /a/ <span className="text-red-500">*</span>
                </span>
                {audioBlobVocal && (
                  <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <CheckCircle2 size={10} /> Lista
                  </span>
                )}
              </div>
              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                Emisión sostenida de /a/ en tono e intensidad cómodos durante 3-5 segundos.
              </p>

              <div className="flex items-center gap-2 pt-1">
                {!recordingVocal ? (
                  <button
                    onClick={() => startRecording('vocal')}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-bold text-xs rounded-xl transition-all active:scale-95 shadow-md shadow-red-600/20"
                  >
                    <Mic size={14} /> Grabar Vocal /a/
                  </button>
                ) : (
                  <button
                    onClick={() => stopRecording('vocal')}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white font-bold text-xs rounded-xl animate-pulse active:scale-95"
                  >
                    <Square size={14} /> Detener
                  </button>
                )}
              </div>
            </div>

            {/* Habla Continua (Opcional para AVQI) */}
            <div className="p-4 rounded-xl bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-800 dark:text-white">
                  Muestra 2: Habla Continua (AVQI completo)
                </span>
                {audioBlobHabla && (
                  <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <CheckCircle2 size={10} /> Lista
                  </span>
                )}
              </div>
              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                Lectura de frase estandarizada (ej: "El viento del norte y el sol...").
              </p>

              <div className="flex items-center gap-2 pt-1">
                {!recordingHabla ? (
                  <button
                    onClick={() => startRecording('habla')}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs rounded-xl transition-all active:scale-95 shadow-md shadow-indigo-600/20"
                  >
                    <Mic size={14} /> Grabar Habla
                  </button>
                ) : (
                  <button
                    onClick={() => stopRecording('habla')}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white font-bold text-xs rounded-xl animate-pulse active:scale-95"
                  >
                    <Square size={14} /> Detener
                  </button>
                )}
              </div>
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
              <AlertCircle size={15} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Action Analyze Button */}
          <div className="flex justify-end pt-2">
            <button
              onClick={analyze}
              disabled={!audioBlobVocal}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-40 active:scale-95"
            >
              <Activity size={16} /> Ejecutar Análisis Bioacústico Praat
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (step === 'analyzing') {
    return (
      <div className="max-w-xl mx-auto text-center py-20 space-y-4">
        <Loader2 size={48} className="animate-spin text-indigo-600 mx-auto" />
        <h3 className="text-lg font-bold text-gray-900 dark:text-white">
          Procesando Muestra Bioacústica con Praat
        </h3>
        <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-2.5 overflow-hidden">
          <div
            className="bg-gradient-to-r from-indigo-600 to-emerald-500 h-full rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400">
          {STAGES[Math.min(Math.floor(progress / 8), STAGES.length - 1)]}
        </p>
      </div>
    );
  }

  if (step === 'review' && result) {
    return (
      <div className="space-y-4">
        <ClinicalReviewScreen
          grbas={grbas}
          rasati={rasati}
          vhi10={vhi10}
          tme={tmeSec}
          audioInfo={result.audio}
          metrics={result.metrics}
          avqiComponents={result.avqiComponents}
          tools={result.tools || []}
          timestamp={result.timestamp || new Date().toISOString()}
          engineVersion={result.engineVersion || '2.0'}
          scriptVersion={result.scriptVersion || 'VoiceLab/2.0'}
          fileHash={result.fileHash || ''}
          harmonics={result.metrics?.harmonics || []}
          formants={result.metrics?.formants || {}}
          ltas={result.metrics?.ltas || {}}
          spectral={result.metrics?.spectral || {}}
          waveform={result.waveform || {}}
          spectrogram={result.spectrogram || {}}
          glottalPulses={result.glottalPulses || []}
          formantTracks={result.formantTracks || {}}
          f0Contour={result.f0Contour || {}}
          intensityContour={result.intensityContour || {}}
          classifications={result.classifications || {}}
          voxplot={result.voxplot || {}}
          charts={result.charts || {}}
          avqiStatus={result.avqi_status || 'ok'}
          crossCheck={result.crossCheck || {}}
          modo="clinico"
        />

        <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-white/10">
          <button
            onClick={() => { setResult(null); setStep('capture'); }}
            className="px-4 py-2.5 rounded-xl border border-gray-300 dark:border-gray-700 text-xs font-bold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-white/5 transition-all"
          >
            ← Capturar Nueva Muestra
          </button>

          <button
            onClick={() => setStep('editor')}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/20 active:scale-95 transition-all"
          >
            <FileText size={16} /> Editar y Generar Reporte Clínico PDF
          </button>
        </div>
      </div>
    );
  }

  if (step === 'editor' && result) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => setStep('review')}
          className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 mb-2"
        >
          ← Volver al Panel de Control de Auditoría
        </button>
        <ReportEditor
          result={result}
          grbas={grbas}
          rasati={rasati}
          profNombre={profNombre}
          profTitulo={profTitulo}
          profMatricula={profMatricula}
        />
      </div>
    );
  }

  return null;
}
