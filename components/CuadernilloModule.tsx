import React, { useState, useEffect } from 'react';
import { FileText, Download, Loader2, CheckCircle2, Settings } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props { pacienteId: string | null; }

interface Exercise {
  id: string; name: string; description: string; steps: string[];
  duration_min?: number; phrases?: string[];
}

interface Section {
  id: string; name: string; description: string; exercises: Exercise[];
}

interface Preset {
  id: string; name: string; description: string; exercise_ids: string[];
  sesiones_recomendadas: number; frecuencia: string;
}

export default function CuadernilloModule({ pacienteId }: Props) {
  const [sections, setSections] = useState<Section[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState('');
  const [selectedExercises, setSelectedExercises] = useState<string[]>([]);
  const [titulo, setTitulo] = useState('Cuadernillo Terapéutico Vocal');
  const [sesiones, setSesiones] = useState(8);
  const [notas, setNotas] = useState('');
  const [generating, setGenerating] = useState(false);
  const [pdfUrl, setPdfUrl] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadBank(); }, []);

  const loadBank = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/ejercicios`);
      if (r.ok) {
        const data = await r.json();
        setSections(data.sections || []);
        setPresets(data.presets || []);
      }
    } catch {}
    setLoading(false);
  };

  const applyPreset = (presetId: string) => {
    setSelectedPreset(presetId);
    const preset = presets.find(p => p.id === presetId);
    if (preset) {
      setSelectedExercises(preset.exercise_ids);
      setSesiones(preset.sesiones_recomendadas);
      setTitulo(`Cuadernillo — ${preset.name}`);
    }
  };

  const toggleExercise = (id: string) => {
    setSelectedExercises(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
    setSelectedPreset('');
  };

  const getAllExercises = (): Exercise[] => {
    const all: Exercise[] = [];
    sections.forEach(s => s.exercises.forEach(e => all.push({ ...e })));
    return all;
  };

  const getSelectedDetails = (): Exercise[] => {
    return getAllExercises().filter(e => selectedExercises.includes(e.id));
  };

  const handleGenerate = async () => {
    if (!selectedExercises.length) { alert('Seleccioná al menos un ejercicio'); return; }
    setGenerating(true);
    try {
      const selected = getSelectedDetails();
      const presetData = presets.find(p => p.id === selectedPreset);
      const contrato = {
        frecuencia: presetData?.frecuencia || '2 veces por semana',
        duracion_sesion: '30 minutos',
        pautas_ausencias: 'Avisar con 24h de anticipación.',
      };
      const fd = new FormData();
      fd.append('paciente_id', pacienteId || '');
      fd.append('titulo', titulo);
      fd.append('sesiones', String(sesiones));
      fd.append('ejercicios_json', JSON.stringify(selected));
      fd.append('contrato_json', JSON.stringify(contrato));
      fd.append('notas', notas);

      const r = await fetch(`${BACKEND_URL}/api/cuadernillo/generar`, { method: 'POST', body: fd });
      const data = await r.json();
      if (data.ok && data.pdf_base64) {
        const bin = atob(data.pdf_base64);
        const arr = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        const blob = new Blob([arr], { type: 'application/pdf' });
        setPdfUrl(URL.createObjectURL(blob));
      }
    } catch (e) {
      alert('Error generando cuadernillo');
    }
    setGenerating(false);
  };

  const downloadPdf = () => {
    if (!pdfUrl) return;
    const a = document.createElement('a');
    a.href = pdfUrl;
    a.download = `${titulo.replace(/\s+/g, '_')}.pdf`;
    a.click();
  };

  if (loading) {
    return <div className="text-center py-16 text-gray-400"><Loader2 size={24} className="animate-spin mx-auto" /></div>;
  }

  return (
    <div className="max-w-5xl space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Settings size={18} /> Presets por Patología
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {presets.map(p => (
            <button
              key={p.id}
              onClick={() => applyPreset(p.id)}
              className={`text-left p-3 rounded-lg border text-sm transition-colors ${
                selectedPreset === p.id
                  ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                  : 'border-gray-200 hover:bg-gray-50 text-gray-700'
              }`}
            >
              <p className="font-medium">{p.name}</p>
              <p className="text-xs text-gray-500 mt-1">{p.description}</p>
              <p className="text-xs text-gray-400 mt-1">{p.sesiones_recomendadas} sesiones — {p.frecuencia}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-800 mb-3">Ejercicios Seleccionados ({selectedExercises.length})</h3>
        {sections.map(section => (
          <div key={section.id} className="mb-4">
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{section.name}</p>
            <div className="space-y-1">
              {section.exercises.map(ex => (
                <label
                  key={ex.id}
                  className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer ${
                    selectedExercises.includes(ex.id) ? 'bg-indigo-50' : 'hover:bg-gray-50'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedExercises.includes(ex.id)}
                    onChange={() => toggleExercise(ex.id)}
                    className="mt-1 rounded text-indigo-600"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-700">{ex.name}</p>
                    <p className="text-xs text-gray-500">{ex.description}</p>
                    {ex.duration_min && <p className="text-xs text-gray-400">{ex.duration_min} min</p>}
                  </div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold text-gray-800 mb-3">Configuración del Cuadernillo</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500">Título</label>
            <input value={titulo} onChange={e => setTitulo(e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
          <div>
            <label className="text-xs text-gray-500">Sesiones</label>
            <input type="number" value={sesiones} onChange={e => setSesiones(parseInt(e.target.value) || 8)} className="w-full px-3 py-2 border rounded-lg text-sm" />
          </div>
        </div>
        <div className="mt-3">
          <label className="text-xs text-gray-500">Notas del profesional</label>
          <textarea value={notas} onChange={e => setNotas(e.target.value)} rows={2} className="w-full px-3 py-2 border rounded-lg text-sm" />
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleGenerate}
            disabled={generating || !selectedExercises.length}
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
          >
            {generating ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
            Generar PDF
          </button>
          {pdfUrl && (
            <button onClick={downloadPdf} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
              <Download size={16} /> Descargar PDF
            </button>
          )}
        </div>
      </div>

      {pdfUrl && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <CheckCircle2 size={18} className="text-green-500" /> Cuadernillo Generado
          </h3>
          <iframe src={pdfUrl} className="w-full h-[600px] rounded-lg border" title="Cuadernillo" />
        </div>
      )}
    </div>
  );
}
