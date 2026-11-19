import React, { useEffect, useState } from 'react';
import { Send, Copy, MessageCircle, Loader2, CheckCircle2, Clock, Download, AlertTriangle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const FRONTEND = typeof window !== 'undefined' ? window.location.origin : 'https://vocalis-lab.vercel.app';

interface Props {
  pacienteId: string | null;
  pacienteNombre?: string;
  telefono?: string;
  /** Carga las respuestas del paciente en el formulario de la evaluación. */
  onCargar: (a: { VHI10?: Record<string, number>; RiesgoVocal?: Record<string, number>; autopercepcion?: number | null }) => void;
}

const NOMBRES: Record<string, string> = { autopercepcion: 'Autopercepción', vhi10: 'VHI-10', riesgo: 'Riesgo vocal' };

/**
 * Autoevaluación por enlace: el paciente completa autopercepción, VHI-10 y
 * riesgo vocal desde su celular (sin entrar a la app) y acá se ven sus
 * resultados, listos para cargar en la evaluación.
 */
export default function PanelAutoevaluacion({ pacienteId, pacienteNombre, telefono, onCargar }: Props) {
  const [lista, setLista] = useState<any[]>([]);
  const [aviso, setAviso] = useState('');
  const [instrumentos, setInstrumentos] = useState<string[]>(['autopercepcion', 'vhi10', 'riesgo']);
  const [nuevo, setNuevo] = useState<any | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');
  const [copiado, setCopiado] = useState('');
  const [cargadoId, setCargadoId] = useState('');

  const listar = async () => {
    if (!pacienteId) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/autoevaluaciones?paciente_id=${pacienteId}`);
      const d = await r.json();
      setLista(d.autoevaluaciones || []);
      setAviso(d.aviso || '');
    } catch {}
  };
  useEffect(() => { setNuevo(null); setLista([]); listar(); /* eslint-disable-next-line */ }, [pacienteId]);

  const crear = async () => {
    setCargando(true); setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/autoevaluaciones`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paciente_id: pacienteId, instrumentos }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setNuevo(d);
      await listar();
    } catch (e: any) {
      setError(e?.message || 'No se pudo crear el enlace');
    }
    setCargando(false);
  };

  const enlaceDe = (token: string) => `${FRONTEND}/?autoeval=${token}`;
  const copiar = async (texto: string, id: string) => {
    await navigator.clipboard.writeText(texto);
    setCopiado(id); setTimeout(() => setCopiado(''), 2000);
  };
  const tel = (telefono || nuevo?.telefono || '').replace(/\D/g, '');
  const mensajeWa = (enlace: string) => encodeURIComponent(
    `Hola${nuevo?.nombre ? ` ${nuevo.nombre}` : ''}, te comparto un cuestionario breve sobre tu voz para la próxima sesión. ` +
    `Lo completás desde el celular en unos 10 minutos: ${enlace}`);

  if (!pacienteId) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-white/10 bg-white/80 dark:bg-white/5 p-4 text-xs text-slate-500">
        Elegí un paciente en «Pacientes» para enviarle la autoevaluación.
      </div>
    );
  }

  const completadas = lista.filter(a => a.estado === 'completada');
  const pendientes = lista.filter(a => a.estado !== 'completada');

  return (
    <div className="rounded-2xl border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50/60 dark:bg-indigo-500/5 p-4 space-y-3">
      <div>
        <p className="text-sm font-bold text-slate-900 dark:text-white">Autoevaluación del paciente {pacienteNombre ? `· ${pacienteNombre}` : ''}</p>
        <p className="text-xs text-slate-600 dark:text-slate-300">
          El paciente completa desde su celular, sin entrar a la app, solo lo de autovaloración. Sus respuestas aparecen acá
          y las cargás en la evaluación con un toque.
        </p>
      </div>
      {aviso && <p className="text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} />{aviso}</p>}

      <div className="flex flex-wrap items-center gap-3">
        {Object.entries(NOMBRES).map(([k, v]) => (
          <label key={k} className="text-xs flex items-center gap-1 text-slate-700 dark:text-slate-200">
            <input type="checkbox" checked={instrumentos.includes(k)}
              onChange={e => setInstrumentos(prev => e.target.checked ? [...prev, k] : prev.filter(x => x !== k))} /> {v}
          </label>
        ))}
        <button onClick={crear} disabled={cargando || !instrumentos.length}
          className="ml-auto px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50">
          {cargando ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Generar enlace para el paciente
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}

      {nuevo && (
        <div className="rounded-xl bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 p-3 space-y-2">
          <p className="text-[11px] font-mono break-all">{nuevo.enlace}</p>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => copiar(nuevo.enlace, 'nuevo')} className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-white/10 text-xs font-bold flex items-center gap-1">
              <Copy size={13} /> {copiado === 'nuevo' ? 'Copiado' : 'Copiar enlace'}
            </button>
            <a href={`https://wa.me/${tel}?text=${mensajeWa(nuevo.enlace)}`} target="_blank" rel="noreferrer"
              className="px-3 py-1.5 rounded-lg border border-emerald-300 text-emerald-700 dark:text-emerald-300 text-xs font-bold flex items-center gap-1">
              <MessageCircle size={13} /> Enviar por WhatsApp
            </a>
            <span className="text-[11px] text-slate-500 self-center">Vence en 14 días.</span>
          </div>
        </div>
      )}

      {completadas.map(a => (
        <div key={a.id} className="rounded-xl bg-white dark:bg-white/5 border border-emerald-200 dark:border-emerald-500/30 p-3 text-xs space-y-1">
          <p className="font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
            <CheckCircle2 size={14} /> Completada por el paciente el {new Date(a.completada_at).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })}
          </p>
          <p className="text-slate-700 dark:text-slate-200">
            {a.autopercepcion != null && <>Autopercepción <b>{a.autopercepcion}/10</b> · </>}
            {a.vhi10_score != null && <>VHI-10 <b>{a.vhi10_score}/40</b> · </>}
            {a.riesgo_vocal_score != null && <>Riesgo vocal <b>{a.riesgo_vocal_score}/207</b></>}
          </p>
          {a.comentario && <p className="text-slate-600 dark:text-slate-300 italic">«{a.comentario}»</p>}
          <button onClick={() => { onCargar({ ...(a.respuestas || {}), autopercepcion: a.autopercepcion }); setCargadoId(a.id); }}
            className="mt-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold flex items-center gap-1.5">
            <Download size={13} /> {cargadoId === a.id ? 'Cargado en la evaluación: revisá y guardá' : 'Cargar en la evaluación'}
          </button>
        </div>
      ))}

      {pendientes.slice(0, 3).map(a => (
        <div key={a.id} className="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <Clock size={13} className="text-amber-500" />
          Enviada el {new Date(a.creada_at).toLocaleDateString('es-AR')} · esperando respuesta
          {a.token && (
            <button onClick={() => copiar(enlaceDe(a.token), a.id)} className="underline">
              {copiado === a.id ? 'Copiado' : 'copiar enlace'}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
