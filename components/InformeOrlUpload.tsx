import React, { useState, useEffect } from 'react';
import {
  Upload, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp,
  Stethoscope, Save, FileText, Eye, Trash2
} from 'lucide-react';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
  onVolcado?: (d: { diagnostico: string; metodo: string; texto: string }) => void;
}

interface InformeRow {
  id: string;
  titulo: string;
  tipo_informe: string;
  archivo_nombre: string;
  texto_extraido: string;
  texto_corregido?: string | null;
  diagnostico_principal?: string | null;
  metodo_exploracion?: string | null;
  profesional_orl?: string | null;
  fecha_informe?: string | null;
  confianza: string;
  estado: string;
  fecha: string;
}

export default function InformeOrlUpload({ pacienteId, onVolcado }: Props) {
  const clinical = useClinical();
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  // Resultado del OCR (editable antes de guardar)
  const [texto, setTexto] = useState('');
  const [diagnostico, setDiagnostico] = useState('');
  const [metodo, setMetodo] = useState('');
  const [estructurales, setEstructurales] = useState('');
  const [funcionales, setFuncionales] = useState('');
  const [confianza, setConfianza] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [archivoNombre, setArchivoNombre] = useState('');
  const [archivoMime, setArchivoMime] = useState('');

  // Historial del paciente (banco de datos)
  const [historial, setHistorial] = useState<InformeRow[]>([]);
  const [verId, setVerId] = useState<string | null>(null);

  const cargarHistorial = async () => {
    if (!pacienteId) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/informes-orl?paciente_id=${pacienteId}`);
      if (r.ok) setHistorial(await r.json());
    } catch { /* sin historial disponible */ }
  };

  useEffect(() => { cargarHistorial(); }, [pacienteId]);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError('');
    setSaved(false);
    try {
      const fd = new FormData();
      fd.append('archivo', file, file.name);
      const r = await fetch(`${BACKEND_URL}/api/informes-orl/ocr`, { method: 'POST', body: fd });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) {
        throw new Error(data.error || data.detail || `Error del servidor (${r.status})`);
      }
      setTexto(data.texto_transcrito_crudo || data.texto_extraido || '');
      setDiagnostico(data.diagnostico_principal || '');
      setMetodo(data.metodo_exploracion || '');
      setEstructurales(data.hallazgos_estructurales || '');
      setFuncionales(data.hallazgos_funcionales || '');
      setConfianza(data.confianza_extraccion || data.confianza || '');
      setObservaciones(data.observaciones || '');
      setArchivoNombre(file.name);
      setArchivoMime(file.type);
    } catch (err: any) {
      setError(err.message || 'No se pudo procesar el archivo');
      setTexto('');
    }
    setUploading(false);
    e.target.value = '';
  };

  const guardarHistoria = async () => {
    if (!texto.trim()) return;
    if (!pacienteId) {
      setError('Seleccioná un paciente primero para guardar el informe en su historia.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('paciente_id', pacienteId);
      fd.append('titulo', `Informe ORL — ${new Date().toLocaleDateString()}`);
      fd.append('tipo_informe', 'ORL');
      fd.append('archivo_nombre', archivoNombre);
      fd.append('mime', archivoMime);
      fd.append('texto_extraido', texto);
      fd.append('texto_transcrito_crudo', texto);
      fd.append('hallazgos_estructurales', estructurales);
      fd.append('hallazgos_funcionales', funcionales);
      fd.append('datos_estructurados', JSON.stringify({
        texto_transcrito_crudo: texto,
        hallazgos_estructurales: estructurales,
        hallazgos_funcionales: funcionales,
      }));
      fd.append('diagnostico_principal', diagnostico);
      fd.append('metodo_exploracion', metodo);
      fd.append('confianza', confianza || 'media');
      fd.append('observaciones_ia', observaciones);
      fd.append('volcar_anamnesis', 'true');
      const r = await fetch(`${BACKEND_URL}/api/informes-orl`, { method: 'POST', body: fd });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) {
        throw new Error(data.detail || `Error guardando (${r.status})`);
      }
      // Actualizar contexto clínico global (la IA lo lee desde anamnesis)
      const prevResumen = clinical.data.anamnesis.resumen_clinico || '';
      const bloque = `[Informe ORL]\n${texto}`.trim();
      clinical.setAnamnesis({
        ...clinical.data.anamnesis,
        diagnostico_orl: diagnostico || clinical.data.anamnesis.diagnostico_orl,
        metodo_exploracion: metodo || clinical.data.anamnesis.metodo_exploracion,
        resumen_clinico: prevResumen ? `${prevResumen}\n\n${bloque}` : bloque,
      });
      clinical.markStep('anamnesis');
      onVolcado?.({ diagnostico, metodo, texto });
      await cargarHistorial();
      setTexto(''); setDiagnostico(''); setMetodo('');
      setEstructurales(''); setFuncionales('');
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (err: any) {
      setError(err.message || 'No se pudo guardar en la historia clínica');
    }
    setSaving(false);
  };

  const cambiarEstado = async (id: string, estado: string) => {
    try {
      const fd = new FormData();
      fd.append('estado', estado);
      await fetch(`${BACKEND_URL}/api/informes-orl/${id}`, { method: 'PUT', body: fd });
      await cargarHistorial();
    } catch { /* noop */ }
  };

  const eliminar = async (id: string) => {
    if (!confirm('¿Eliminar este informe del historial?')) return;
    try {
      await fetch(`${BACKEND_URL}/api/informes-orl/${id}`, { method: 'DELETE' });
      await cargarHistorial();
    } catch { /* noop */ }
  };

  const estadoBadge = (estado: string) => {
    if (estado === 'validado') return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300';
    if (estado === 'descartado') return 'bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400';
    return 'bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300';
  };

  return (
    <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl shadow-sm overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between p-5 text-left">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-500/10 text-teal-600 dark:text-teal-400 flex items-center justify-center">
            <Stethoscope size={20} />
          </div>
          <div>
            <h3 className="font-bold text-sm text-gray-900 dark:text-white">
              Informe ORL (análisis del otorrino)
            </h3>
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              Subí foto o PDF del informe — la IA extrae el texto y lo vuelca a la historia. Queda como banco de datos del paciente.
            </p>
          </div>
        </div>
        {open ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-100 dark:border-white/5 pt-4">
          <label className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700 hover:border-teal-400 dark:hover:border-teal-500 cursor-pointer text-xs font-bold text-gray-600 dark:text-gray-300 transition-all">
            {uploading
              ? <><Loader2 size={16} className="animate-spin" /> Leyendo informe con IA…</>
              : <><Upload size={16} /> Subir informe ORL (imagen PNG/JPG o PDF)</>}
            <input type="file" accept="image/*,.pdf" className="hidden" onChange={handleFile} disabled={uploading} />
          </label>

          {error && (
            <p className="text-xs text-red-600 dark:text-red-400 font-semibold flex items-center gap-1">
              <AlertCircle size={14} /> {error}
            </p>
          )}

          {texto && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="px-2 py-0.5 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-700 dark:text-teal-300 font-bold">
                  <FileText size={11} className="inline mr-1" />{archivoNombre || 'informe'}
                </span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 font-bold">
                  Confianza: {confianza || '—'}
                </span>
              </div>
              {observaciones && (
                <p className="text-[11px] text-gray-500 dark:text-gray-400 italic">{observaciones}</p>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 dark:text-gray-400 mb-1">
                    Diagnóstico principal (editable)
                  </label>
                  <input
                    value={diagnostico}
                    onChange={e => setDiagnostico(e.target.value)}
                    placeholder="Ej: Nódulo bilateral / Pólipo…"
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-gray-500 dark:text-gray-400 mb-1">
                    Método de exploración (editable)
                  </label>
                  <input
                    value={metodo}
                    onChange={e => setMetodo(e.target.value)}
                    placeholder="Ej: Nasofibroscopía flexible…"
                    className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div className="p-2.5 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
                  <label className="block text-[10px] font-bold text-indigo-700 dark:text-indigo-300 mb-1">
                    Hallazgos estructurales (anatómicos — editable)
                  </label>
                  <textarea
                    value={estructurales}
                    onChange={e => setEstructurales(e.target.value)}
                    rows={3}
                    placeholder="Ej: pliegues vocales, bordes, mucosa, subglotis…"
                    className="w-full bg-transparent text-xs text-gray-800 dark:text-gray-100 focus:outline-none resize-y"
                  />
                </div>
                <div className="p-2.5 rounded-xl bg-violet-500/5 border border-violet-500/20">
                  <label className="block text-[10px] font-bold text-violet-700 dark:text-violet-300 mb-1">
                    Hallazgos funcionales (movilidad — editable)
                  </label>
                  <textarea
                    value={funcionales}
                    onChange={e => setFuncionales(e.target.value)}
                    rows={3}
                    placeholder="Ej: hiperfunción, constricción, hiato, movilidad cordal…"
                    className="w-full bg-transparent text-xs text-gray-800 dark:text-gray-100 focus:outline-none resize-y"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-gray-500 dark:text-gray-400 mb-1">
                  Transcripción cruda (revisá y corregí antes de guardar)
                </label>
                <textarea
                  value={texto}
                  onChange={e => setTexto(e.target.value)}
                  rows={6}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 rounded-xl text-xs text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-teal-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={guardarHistoria}
                  disabled={saving}
                  className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-teal-500 to-emerald-500 hover:from-teal-400 hover:to-emerald-400 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-teal-500/20 active:scale-95 transition-all disabled:opacity-50"
                >
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {saving ? 'Guardando…' : 'Guardar en historia clínica'}
                </button>
                {saved && (
                  <span className="text-xs text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                    <CheckCircle2 size={14} /> Guardado
                  </span>
                )}
              </div>
            </>
          )}

          {/* Historial / banco de datos */}
          {historial.length > 0 && (
            <div className="pt-2">
              <h4 className="text-xs font-bold text-gray-600 dark:text-gray-300 mb-2">
                Informes guardados ({historial.length})
              </h4>
              <div className="space-y-2">
                {historial.map(inf => (
                  <div key={inf.id} className="border border-gray-200 dark:border-white/10 rounded-xl p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-gray-800 dark:text-gray-100 truncate">
                          {inf.diagnostico_principal || inf.titulo}
                        </p>
                        <p className="text-[10px] text-gray-500 dark:text-gray-400">
                          {inf.archivo_nombre || ''} · {inf.fecha ? new Date(inf.fecha).toLocaleDateString() : ''}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <span className={`px-1.5 py-0.5 text-[9px] font-bold border rounded-full ${estadoBadge(inf.estado)}`}>
                          {inf.estado === 'validado' ? 'VALIDADO' : inf.estado === 'descartado' ? 'DESCARTADO' : 'PENDIENTE'}
                        </span>
                        <button onClick={() => setVerId(verId === inf.id ? null : inf.id)} title="Ver texto"
                          className="p-1 rounded hover:bg-gray-100 dark:hover:bg-white/10 text-gray-500">
                          <Eye size={13} />
                        </button>
                        {inf.estado === 'pendiente_revision' && (
                          <button onClick={() => cambiarEstado(inf.id, 'validado')} title="Validar"
                            className="p-1 rounded hover:bg-emerald-500/10 text-emerald-600">
                            <CheckCircle2 size={13} />
                          </button>
                        )}
                        <button onClick={() => eliminar(inf.id)} title="Eliminar"
                          className="p-1 rounded hover:bg-red-500/10 text-red-500">
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                    {verId === inf.id && (
                      <pre className="mt-2 p-2 bg-gray-50 dark:bg-white/5 rounded-lg text-[11px] whitespace-pre-wrap text-gray-700 dark:text-gray-300 max-h-40 overflow-auto">
                        {inf.texto_corregido || inf.texto_extraido}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
