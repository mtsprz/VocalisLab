import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { RIESGO_VOCAL_2026, VHI10 } from '../instrumentosVoz';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

// Escalas en palabras simples (mismos valores que los instrumentos).
const OPC_VHI = ['Nunca', 'Casi nunca', 'A veces', 'Casi siempre', 'Siempre'];
const OPC_RIESGO = ['Nada / nunca', 'Poco / a veces', 'Bastante / a menudo', 'Mucho / siempre'];

// Aclaraciones para las preguntas más técnicas (no cambian la pregunta).
const AYUDA: Record<string, string> = {
  A4: 'Hablar con la voz muy grave y raspada, como gruñendo.',
  A6: 'Hablar con la boca poco abierta, casi sin mover la mandíbula.',
  A10: 'Al hablar, respirar levantando los hombros y el pecho en lugar de inflar la panza.',
  A18: 'Reírse tomando aire hacia adentro.',
  A25: 'Hablar mientras te agachás, girás o hacés fuerza con el cuerpo.',
  A29: 'Usar mucho la voz apenas te levantás.',
  C2: 'Respirar por la boca la mayor parte del tiempo.',
  C6: 'Reflujo, acidez o ardor de estómago.',
};

type Paso = { id: string; titulo: string; tipo: 'auto' | 'vhi' | 'riesgo' | 'comentario'; seccion?: number };

/**
 * Formulario de autoevaluación del paciente (enlace ?autoeval=<token>, sin
 * cuenta ni acceso a la app). Solo lo que se autovalora: autopercepción,
 * VHI-10 y cuestionario de riesgo vocal. Las respuestas llegan a la ficha.
 */
export default function AutoevaluacionPaciente({ token }: { token: string }) {
  const clave = `vocalislab_autoeval_${token}`;
  const [info, setInfo] = useState<any | null>(null);
  const [error, setError] = useState('');
  const [paso, setPaso] = useState(0);
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const [resp, setResp] = useState<{ auto: number | null; vhi: Record<string, number>; riesgo: Record<string, number>; comentario: string }>(() => {
    try {
      const guardado = localStorage.getItem(clave);
      if (guardado) return JSON.parse(guardado);
    } catch {}
    return { auto: null, vhi: {}, riesgo: {}, comentario: '' };
  });

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/autoevaluacion/${token}`)
      .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.detail); return d; })
      .then(setInfo)
      .catch(e => setError(e?.message || 'No se pudo abrir el cuestionario.'));
  }, [token]);

  // El avance queda guardado en el teléfono hasta enviarlo.
  useEffect(() => {
    try { localStorage.setItem(clave, JSON.stringify(resp)); } catch {}
  }, [resp, clave]);

  const pasos: Paso[] = useMemo(() => {
    const ins: string[] = info?.instrumentos || [];
    const out: Paso[] = [];
    if (ins.includes('autopercepcion')) out.push({ id: 'auto', titulo: 'Tu voz hoy', tipo: 'auto' });
    if (ins.includes('vhi10')) out.push({ id: 'vhi', titulo: 'Cómo te afecta tu voz (VHI-10)', tipo: 'vhi' });
    if (ins.includes('riesgo')) {
      RIESGO_VOCAL_2026.dimensions.forEach((d, i) =>
        out.push({ id: `riesgo${i}`, titulo: d.categoria.replace(/^Sección \d+ — /, '').replace(/\s*\(\d+ ítems\)/, ''), tipo: 'riesgo', seccion: i }));
    }
    out.push({ id: 'comentario', titulo: 'Algo más que quieras contar', tipo: 'comentario' });
    return out;
  }, [info]);

  const actual = pasos[paso];
  const completo = (p: Paso) => {
    if (p.tipo === 'auto') return resp.auto != null;
    if (p.tipo === 'vhi') return VHI10.items.every(it => resp.vhi[it.key] != null);
    if (p.tipo === 'riesgo') return RIESGO_VOCAL_2026.dimensions[p.seccion!].items.every(it => resp.riesgo[it.key] != null);
    return true;
  };
  const faltanEnPaso = actual ? !completo(actual) : false;

  const enviar = async () => {
    setEnviando(true); setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/autoevaluacion/${token}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autopercepcion: resp.auto, vhi10: resp.vhi, riesgo: resp.riesgo, comentario: resp.comentario }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setEnviado(true);
      try { localStorage.removeItem(clave); } catch {}
    } catch (e: any) {
      setError(e?.message || 'No se pudo enviar. Revisá tu conexión y probá de nuevo.');
    }
    setEnviando(false);
  };

  const Opciones = ({ opciones, valor, onElegir }: { opciones: string[]; valor: number | undefined; onElegir: (v: number) => void }) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 mt-2">
      {opciones.map((o, v) => (
        <button key={v} onClick={() => onElegir(v)}
          className={`text-left px-3 py-2.5 rounded-xl border text-sm transition-all ${valor === v
            ? 'bg-indigo-600 text-white border-indigo-600 font-semibold'
            : 'bg-white dark:bg-white/5 border-slate-200 dark:border-white/10 text-slate-700 dark:text-slate-200'}`}>
          {o}
        </button>
      ))}
    </div>
  );

  const contenido = () => {
    if (!actual) return null;
    if (actual.tipo === 'auto') return (
      <div>
        <p className="text-base font-semibold">Del 0 al 10, ¿qué puntaje le darías a la calidad de tu voz hoy?</p>
        <p className="text-xs text-slate-500 mt-1">0 = muy mala · 10 = excelente</p>
        <div className="grid grid-cols-6 sm:grid-cols-11 gap-1.5 mt-3">
          {Array.from({ length: 11 }, (_, v) => (
            <button key={v} onClick={() => setResp(r => ({ ...r, auto: v }))}
              className={`py-3 rounded-xl border text-base font-bold ${resp.auto === v ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white dark:bg-white/5 border-slate-200 dark:border-white/10'}`}>
              {v}
            </button>
          ))}
        </div>
      </div>
    );
    if (actual.tipo === 'vhi') return (
      <div className="space-y-5">
        <p className="text-xs text-slate-500">Marcá con qué frecuencia te pasa cada situación.</p>
        {VHI10.items.map(it => (
          <div key={it.key}>
            <p className="text-sm font-semibold">{it.label}</p>
            <Opciones opciones={OPC_VHI} valor={resp.vhi[it.key]} onElegir={v => setResp(r => ({ ...r, vhi: { ...r.vhi, [it.key]: v } }))} />
          </div>
        ))}
      </div>
    );
    if (actual.tipo === 'riesgo') return (
      <div className="space-y-5">
        <p className="text-xs text-slate-500">Respondé pensando en tu día a día.</p>
        {RIESGO_VOCAL_2026.dimensions[actual.seccion!].items.map(it => (
          <div key={it.key}>
            <p className="text-sm font-semibold">{it.label}</p>
            {AYUDA[it.key] && <p className="text-xs text-slate-500 mt-0.5">{AYUDA[it.key]}</p>}
            <Opciones opciones={OPC_RIESGO} valor={resp.riesgo[it.key]} onElegir={v => setResp(r => ({ ...r, riesgo: { ...r.riesgo, [it.key]: v } }))} />
          </div>
        ))}
      </div>
    );
    return (
      <div>
        <p className="text-sm font-semibold">¿Hay algo más sobre tu voz que quieras contarle a tu fonoaudiólogo? (opcional)</p>
        <textarea value={resp.comentario} onChange={e => setResp(r => ({ ...r, comentario: e.target.value }))} rows={4}
          className="w-full mt-2 px-3 py-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 text-sm" />
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0b0f19] text-slate-900 dark:text-white p-4">
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="text-center pt-3">
          <h1 className="text-xl font-extrabold">Consultorio de Voz</h1>
          <p className="text-xs text-slate-500">{info?.profesional || 'Matías Pérez · Fonoaudiólogo'}</p>
        </div>

        {enviado ? (
          <div className="p-6 rounded-2xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 text-center">
            <CheckCircle2 size={40} className="mx-auto text-emerald-600" />
            <p className="text-lg font-bold mt-2">¡Listo, gracias{info?.nombre ? `, ${info.nombre}` : ''}!</p>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Tus respuestas ya le llegaron a tu fonoaudiólogo. Podés cerrar esta página.</p>
          </div>
        ) : !info ? (
          error ? <p className="p-4 rounded-2xl bg-amber-100 text-amber-800 text-sm text-center">{error}</p>
            : <p className="text-center text-sm text-slate-500"><Loader2 className="inline animate-spin" size={16} /> Abriendo el cuestionario…</p>
        ) : info.estado === 'completada' ? (
          <p className="p-4 rounded-2xl bg-emerald-50 text-emerald-800 text-sm text-center">Este cuestionario ya fue enviado. ¡Gracias!</p>
        ) : info.estado === 'vencida' ? (
          <p className="p-4 rounded-2xl bg-amber-100 text-amber-800 text-sm text-center">El enlace venció. Pedile uno nuevo a tu fonoaudiólogo.</p>
        ) : (
          <>
            {paso === 0 && (
              <div className="p-4 rounded-2xl bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 text-sm">
                <p className="font-bold">{info.nombre ? `Hola ${info.nombre}` : 'Hola'} 👋</p>
                <p className="text-slate-600 dark:text-slate-300 mt-1">
                  Son unas preguntas sobre tu voz y tus hábitos. Lleva unos 10 minutos. Si cerrás la página, lo que
                  respondiste queda guardado en este teléfono para seguir después.
                </p>
              </div>
            )}
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>Paso {paso + 1} de {pasos.length}</span><span>{actual?.titulo}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-200 dark:bg-white/10 overflow-hidden">
                <div className="h-full bg-indigo-600 transition-all" style={{ width: `${((paso + 1) / pasos.length) * 100}%` }} />
              </div>
            </div>
            <div className="p-4 rounded-2xl bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10">
              <h2 className="font-bold mb-3">{actual?.titulo}</h2>
              {contenido()}
            </div>
            {error && <p className="text-sm text-red-600 text-center">{error}</p>}
            <div className="flex gap-2">
              <button onClick={() => { setPaso(p => Math.max(0, p - 1)); window.scrollTo(0, 0); }} disabled={paso === 0}
                className="px-4 py-3 rounded-xl border border-slate-300 dark:border-white/10 text-sm font-bold disabled:opacity-30 flex items-center gap-1">
                <ChevronLeft size={16} /> Atrás
              </button>
              {paso < pasos.length - 1 ? (
                <button onClick={() => { setPaso(p => p + 1); window.scrollTo(0, 0); }} disabled={faltanEnPaso}
                  className="flex-1 py-3 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-40 flex items-center justify-center gap-1">
                  {faltanEnPaso ? 'Respondé todas las preguntas' : <>Siguiente <ChevronRight size={16} /></>}
                </button>
              ) : (
                <button onClick={enviar} disabled={enviando || pasos.some(p => !completo(p))}
                  className="flex-1 py-3 rounded-xl bg-emerald-600 text-white text-sm font-bold disabled:opacity-40 flex items-center justify-center gap-1">
                  {enviando ? <><Loader2 size={16} className="animate-spin" /> Enviando…</> : 'Enviar respuestas'}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
