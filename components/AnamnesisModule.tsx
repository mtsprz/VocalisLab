import React, { useState, useRef } from 'react';
import { Mic, Square, Upload, Loader2, FileText, Sparkles } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
}

export default function AnamnesisModule({ pacienteId }: Props) {
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
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="font-semibold text-gray-800 mb-3">{title}</h3>
      {children}
    </div>
  );

  const KVDatum = ({ label, value }: { label: string; value: any }) => (
    <div className="flex justify-between py-1.5 border-b border-gray-50">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-medium text-gray-800">{value ?? '—'}</span>
    </div>
  );

  return (
    <div className="max-w-4xl space-y-4">
      {!pacienteId && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
          Seleccioná un paciente desde la sección Pacientes para asociar esta anamnesis.
        </div>
      )}

      <Section title="Grabación de Anamnesis">
        <p className="text-sm text-gray-500 mb-4">
          Grabá la entrevista clínica. El audio se transcribirá automáticamente con Whisper.
        </p>
        <div className="flex items-center gap-3">
          {!recording ? (
            <button
              onClick={startRecording}
              className="flex items-center gap-2 px-5 py-3 bg-red-500 text-white rounded-lg font-medium hover:bg-red-600 transition-colors"
            >
              <Mic size={18} /> Grabar Anamnesis
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 px-5 py-3 bg-gray-800 text-white rounded-lg font-medium animate-pulse"
            >
              <Square size={18} /> Detener Grabación
            </button>
          )}
          {audioBlob && (
            <>
              <button onClick={downloadAudio} className="text-sm text-indigo-600 hover:underline">
                Descargar audio
              </button>
              <button
                onClick={transcribir}
                disabled={transcribing}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {transcribing ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                Transcribir con Whisper
              </button>
            </>
          )}
        </div>
        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
      </Section>

      {transcripcion && (
        <Section title="Transcripción">
          <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap max-h-60 overflow-y-auto">
            {transcripcion}
          </div>
          <button
            onClick={estructurar}
            disabled={structuring}
            className="mt-3 flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50"
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
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Síntomas</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(estructuracion.sintomas).map(([k, v]) => (
                  <div key={k} className={`text-xs px-2 py-1 rounded-full ${v ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'}`}>
                    {k.replace(/_/g, ' ')}: {v ? 'Sí' : 'No'}
                  </div>
                ))}
              </div>
            </div>
          )}
          {estructuracion.factores_riesgo && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Factores de Riesgo</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(estructuracion.factores_riesgo).map(([k, v]) => (
                  <div key={k} className={`text-xs px-2 py-1 rounded-full ${v ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-500'}`}>
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
          <p className="text-sm text-gray-500 mb-3">Basado en la anamnesis, se recomienda grabar esta secuencia vocal:</p>
          {muestraVocal.orden?.map((p: any) => (
            <div key={p.paso} className="flex items-center gap-3 py-2 border-b border-gray-50">
              <span className="w-7 h-7 bg-indigo-100 text-indigo-700 rounded-full flex items-center justify-center text-sm font-bold">
                {p.paso}
              </span>
              <span className="text-sm text-gray-700">{p.texto}</span>
            </div>
          ))}
          <p className="text-xs text-gray-400 mt-3">
            Duración estimada: {muestraVocal.duracion_estimada_s || 60} segundos
          </p>
        </Section>
      )}
    </div>
  );
}
