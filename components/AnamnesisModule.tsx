import React, { useState, useRef } from 'react';
import { Mic, Square, Upload, Loader2, FileText, Sparkles, AlertCircle } from 'lucide-react';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
}

export default function AnamnesisModule({ pacienteId }: Props) {
  const clinical = useClinical();
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [structuring, setStructuring] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [transcripcion, setTranscripcion] = useState('');
  const [estructuracion, setEstructuracion] = useState<any>(null);
  const [muestraVocal, setMuestraVocal] = useState<any>(null);
  const [error, setError] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
      setError('');
    } catch (e) {
      setError('No se pudo acceder al micrófono');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  const transcribir = async () => {
    if (!audioBlob) return;
    setTranscribing(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('audio', audioBlob, 'anamnesis.webm');
      const r = await fetch(`${BACKEND_URL}/api/anamnesis/transcribir`, { method: 'POST', body: fd });
      const data = await r.json();
      if (data.error) { setError(data.error); return; }
      setTranscripcion(data.transcripcion || '');
    } catch (e) {
      setError('Error conectando con el servidor');
    }
    setTranscribing(false);
  };

  const estructurar = async () => {
    if (!transcripcion) return;
    setStructuring(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('transcripcion', transcripcion);
      const r = await fetch(`${BACKEND_URL}/api/anamnesis/estructurar`, { method: 'POST', body: fd });
      const data = await r.json();
      if (data.error) { setError(data.error); return; }
      setEstructuracion(data);

      // Sync anamnesis to clinical context
      clinical.setAnamnesis({
        motivo_consulta: data.motivo_consulta,
        diagnostico_orl: data.diagnostico_orl,
        metodo_exploracion: data.metodo_exploracion,
        sintomas: data.sintomas,
        factores_riesgo: data.factores_riesgo,
        resumen_clinico: data.resumen_clinico,
        transcripcion: transcripcion,
      });
      clinical.markStep('anamnesis');

      const r2 = await fetch(`${BACKEND_URL}/api/anamnesis/completa`, {
        method: 'POST',
        body: (() => { const f = new FormData(); f.append('audio', audioBlob!, 'anamnesis.webm'); f.append('paciente_id', pacienteId || ''); return f; })(),
      });
      const data2 = await r2.json();
      setMuestraVocal(data2.muestra_vocal || null);
    } catch (e) {
      setError('Error estructurando anamnesis');
    }
    setStructuring(false);
  };

  const downloadAudio = () => {
    if (!audioBlob) return;
    const url = URL.createObjectURL(audioBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `anamnesis_${new Date().toISOString().slice(0,10)}.webm`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="bg-white dark:bg-[#111827] rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm transition-all duration-200">
      <h3 className="font-bold text-gray-800 dark:text-white mb-3 text-base">{title}</h3>
      {children}
    </div>
  );

  const KVDatum = ({ label, value }: { label: string; value: any }) => (
    <div className="flex justify-between py-2 border-b border-gray-50 dark:border-gray-800 last:border-b-0">
      <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">{label}</span>
      <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">{value ?? '—'}</span>
    </div>
  );

  return (
    <div className="max-w-4xl space-y-4">
      {!pacienteId && (
        <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 text-amber-700 dark:text-amber-400 rounded-lg p-3 text-sm font-medium flex items-center gap-2">
          <AlertCircle size={16} />
          Seleccioná un paciente desde la sección Pacientes para asociar esta anamnesis.
        </div>
      )}

      <Section title="Grabación de Anamnesis">
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4 font-medium">
          Grabá la entrevista clínica. El audio se transcribirá automáticamente con Whisper.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          {!recording ? (
            <button
              onClick={startRecording}
              className="flex items-center gap-2 px-5 py-3 bg-red-500 text-white rounded-lg font-semibold hover:bg-red-600 shadow-md shadow-red-500/10 active:scale-95 transition-all"
            >
              <Mic size={18} /> Grabar Anamnesis
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 px-5 py-3 bg-gray-800 text-white rounded-lg font-semibold animate-pulse active:scale-95 transition-all"
            >
              <Square size={18} /> Detener Grabación
            </button>
          )}
          {audioBlob && (
            <>
              <button onClick={downloadAudio} className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline font-semibold">
                Descargar audio
              </button>
              <button
                onClick={transcribir}
                disabled={transcribing}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition-all shadow-md shadow-indigo-600/10"
              >
                {transcribing ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                Transcribir con Whisper
              </button>
            </>
          )}
        </div>
        {error && <p className="text-sm text-red-600 dark:text-red-400 mt-3 font-medium flex items-center gap-1"><AlertCircle size={14} /> {error}</p>}
      </Section>

      {transcripcion && (
        <Section title="Transcripción">
          <div className="bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-800 rounded-lg p-4 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap max-h-60 overflow-y-auto font-medium">
            {transcripcion}
          </div>
          <button
            onClick={estructurar}
            disabled={structuring}
            className="mt-3 flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-semibold disabled:opacity-50 transition-all shadow-md shadow-purple-600/10"
          >
            {structuring ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Estructurar con IA
          </button>
        </Section>
      )}

      {estructuracion && (
        <Section title="Anamnesis Estructurada">
          <div className="space-y-1">
            <KVDatum label="Motivo de consulta" value={estructuracion.motivo_consulta} />
            <KVDatum label="Diagnóstico ORL" value={estructuracion.diagnostico_orl} />
            <KVDatum label="Método de exploración" value={estructuracion.metodo_exploracion} />
            <KVDatum label="Resumen clínico" value={estructuracion.resumen_clinico} />
          </div>
          {estructuracion.sintomas && (
            <div className="mt-4 border-t border-gray-100 dark:border-gray-800 pt-3">
              <p className="text-xs font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Síntomas Detectados</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(estructuracion.sintomas).map(([k, v]) => (
                  <div key={k} className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                    v ? 'bg-red-50 text-red-700 border-red-100 dark:bg-red-950/20 dark:text-red-400 dark:border-red-900/40' : 'bg-gray-50 text-gray-400 border-gray-100 dark:bg-gray-800 dark:text-gray-500 dark:border-gray-700/40'
                  }`}>
                    {k.replace(/_/g, ' ')}: {v ? 'Sí' : 'No'}
                  </div>
                ))}
              </div>
            </div>
          )}
          {estructuracion.factores_riesgo && (
            <div className="mt-4 border-t border-gray-100 dark:border-gray-800 pt-3">
              <p className="text-xs font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Factores de Riesgo</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(estructuracion.factores_riesgo).map(([k, v]) => (
                  <div key={k} className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                    v ? 'bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-950/20 dark:text-amber-400 dark:border-amber-900/40' : 'bg-gray-50 text-gray-400 border-gray-100 dark:bg-gray-800 dark:text-gray-500 dark:border-gray-700/40'
                  }`}>
                    {k.replace(/_/g, ' ')}: {v ? 'Sí' : 'No'}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>
      )}

      {muestraVocal && (
        <Section title="Muestra Vocal Recomendada">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 font-medium">Basado en la anamnesis, se recomienda grabar esta secuencia vocal:</p>
          <div className="space-y-2">
            {muestraVocal.orden?.map((p: any) => (
              <div key={p.paso} className="flex items-center gap-3 py-2 border-b border-gray-50 dark:border-gray-800 last:border-b-0">
                <span className="w-7 h-7 bg-indigo-50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-400 rounded-full flex items-center justify-center text-xs font-bold border border-indigo-100 dark:border-indigo-900">
                  {p.paso}
                </span>
                <span className="text-sm text-gray-700 dark:text-gray-300 font-medium">{p.texto}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 font-semibold">
            Duración estimada: {muestraVocal.duracion_estimada_s || 60} segundos
          </p>
        </Section>
      )}
    </div>
  );
}
