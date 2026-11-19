import React, { useEffect, useState } from 'react';
import { Loader2, Sparkles, AlertTriangle, Save, Printer } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const ETAPAS: Record<string, string> = {
  '': 'Detectar de los registros',
  postquirurgica: 'Postquirúrgica',
  prequirurgica: 'Prequirúrgica (cirugía indicada o programada)',
  a_definir: 'Lesión a definir con el ORL',
  no_quirurgica: 'Sin indicación quirúrgica',
};
const cuando = (f: any) => (f ? new Date(f).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : '');

/**
 * Orientación clínica integral: cruza todos los datos del paciente, tiene en
 * cuenta la situación quirúrgica y se guarda (editable por el profesional).
 */
export default function OrientacionClinica({ pacienteId, situacion, paciente }: { pacienteId: string; situacion: any; paciente: any }) {
  const [etapa, setEtapa] = useState('');
  const [pregunta, setPregunta] = useState('');
  const [actual, setActual] = useState<any>(null);
  const [texto, setTexto] = useState('');
  const [historial, setHistorial] = useState<any[]>([]);
  const [aviso, setAviso] = useState('');
  const [estado, setEstado] = useState<{ cargando?: boolean; guardando?: boolean; error?: string; ok?: string }>({});

  const cargar = async (mostrarUltima = false) => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/ficha/${pacienteId}/orientaciones`);
      const j = await r.json();
      setHistorial(j.orientaciones || []);
      setAviso(j.aviso || '');
      if (mostrarUltima && j.orientaciones?.[0]) { setActual(j.orientaciones[0]); setTexto(j.orientaciones[0].texto); }
    } catch {}
  };
  useEffect(() => { setActual(null); setTexto(''); setEstado({}); cargar(true); /* eslint-disable-next-line */ }, [pacienteId]);

  const generar = async () => {
    setEstado({ cargando: true });
    try {
      const r = await fetch(`${BACKEND_URL}/api/ficha/${pacienteId}/orientacion`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ etapa: etapa || undefined, pregunta: pregunta || undefined }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || `Error ${r.status}`);
      setActual(j); setTexto(j.texto); setAviso(j.aviso || '');
      setEstado({ ok: j.id ? 'Orientación generada y guardada.' : '' });
      cargar();
    } catch (e: any) {
      setEstado({ error: e?.message || 'No se pudo generar' });
    }
  };

  const guardarEdicion = async () => {
    if (!actual?.id) return;
    setEstado({ guardando: true });
    try {
      const r = await fetch(`${BACKEND_URL}/api/orientaciones/${actual.id}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Error ${r.status}`);
      setActual({ ...actual, texto, editado: true });
      setEstado({ ok: 'Cambios guardados.' });
      cargar();
    } catch (e: any) { setEstado({ error: e?.message || 'No se pudo guardar' }); }
  };

  const imprimir = () => {
    const w = window.open('', '_blank');
    if (!w) return;
    const esc = (s: string) => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]!));
    w.document.write(`<html><head><title>Orientación clínica</title><style>body{font-family:system-ui,sans-serif;max-width:760px;margin:32px auto;line-height:1.5;font-size:13px}pre{white-space:pre-wrap;font-family:inherit}</style></head><body>
      <h2>Orientación clínica — ${esc(paciente?.nombre_completo || '')}</h2><p>${cuando(actual?.creada_at) || new Date().toLocaleDateString('es-AR')}</p>
      <pre>${esc(texto)}</pre><p>Matías Pérez · Fonoaudiólogo</p></body></html>`);
    w.document.close(); w.print();
  };

  const sit = actual?.situacion || situacion;
  const cambiado = actual && texto !== actual.texto;

  return (
    <div className="space-y-3 text-xs">
      {sit && (
        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10">
          <p><b>Situación quirúrgica:</b> {sit.etiqueta} <span className="text-slate-500">({sit.origen})</span></p>
          {sit.evidencia?.slice(0, 3).map((e: any, i: number) => (
            <p key={i} className="text-slate-500 italic">{e.fuente}{e.fecha ? ` ${e.fecha}` : ''}: {e.texto}</p>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2 items-end">
        <label className="flex flex-col gap-0.5">Situación quirúrgica
          <select value={etapa} onChange={e => setEtapa(e.target.value)}
            className="px-2 py-1.5 rounded-lg border border-slate-300 dark:border-white/15 bg-white dark:bg-black/20">
            {Object.entries(ETAPAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 flex-1 min-w-[200px]">Pregunta puntual (opcional)
          <input value={pregunta} onChange={e => setPregunta(e.target.value)} placeholder="¿Conviene reevaluar antes de la cirugía?"
            className="px-2 py-1.5 rounded-lg border border-slate-300 dark:border-white/15 bg-white dark:bg-black/20" />
        </label>
        <button onClick={generar} disabled={estado.cargando}
          className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold flex items-center gap-1.5 disabled:opacity-50">
          {estado.cargando ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          {estado.cargando ? 'Cruzando todos los datos…' : 'Generar orientación clínica'}
        </button>
      </div>
      {aviso && <p className="text-amber-700 dark:text-amber-300">{aviso}</p>}
      {estado.error && <p className="text-red-600 flex gap-1.5"><AlertTriangle size={13} />{estado.error}</p>}
      {estado.ok && <p className="text-emerald-600">{estado.ok}</p>}

      {actual && (
        <div className="space-y-2">
          {historial.length > 1 && (
            <label className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">Guardadas:
              <select value={actual.id || ''} onChange={e => { const h = historial.find(x => x.id === e.target.value); if (h) { setActual(h); setTexto(h.texto); setEstado({}); } }}
                className="px-2 py-1 rounded-lg border border-slate-300 dark:border-white/15 bg-white dark:bg-black/20">
                {historial.map(h => <option key={h.id} value={h.id}>{cuando(h.creada_at)}{h.editado ? ' (editada)' : ''}</option>)}
              </select>
            </label>
          )}
          {actual.completo === false && <p className="text-amber-700 dark:text-amber-300">El texto pudo quedar incompleto: generalo de nuevo.</p>}
          {actual.valores_a_revisar?.length > 0 && (
            <p className="text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} className="shrink-0" />
              Revisá estos valores: no coinciden con los datos cargados: {actual.valores_a_revisar.join(', ')}.</p>
          )}
          <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={Math.min(40, Math.max(12, texto.split('\n').length + 2))}
            className="w-full p-3 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-black/20 text-slate-800 dark:text-slate-100 leading-relaxed" />
          <div className="flex gap-2">
            <button onClick={guardarEdicion} disabled={!cambiado || !actual.id || estado.guardando}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold flex items-center gap-1 disabled:opacity-40">
              <Save size={12} /> Guardar cambios
            </button>
            <button onClick={imprimir} className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-white/15 flex items-center gap-1">
              <Printer size={12} /> Imprimir / PDF
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
