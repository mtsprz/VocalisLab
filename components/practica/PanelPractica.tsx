import React, { useEffect, useState } from 'react';
import { Loader2, Send, Copy, Pause, Play, Eye } from 'lucide-react';
import PracticaPaciente from './PracticaPaciente';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const GUIA_TXT: Record<string, string> = { sostenida: 'Nota sostenida', escalera: 'Escalera', rampa: 'Rampa (glissando)', patron: 'Patrón' };
const fecha = (f: any) => (f ? new Date(f).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : '—');

/**
 * Práctica guiada para casa: se eligen ejercicios del cuadernillo con guía
 * visual (ya filtrados por contraindicaciones), se ajusta el tono y se manda
 * el enlace por WhatsApp. Abajo, lo que el paciente practicó.
 */
export default function PanelPractica({ pacienteId }: { pacienteId: string }) {
  const [sug, setSug] = useState<any>(null);
  const [elegidos, setElegidos] = useState<any[]>([]);
  const [indicaciones, setIndicaciones] = useState('');
  const [lista, setLista] = useState<any>({ practicas: [], sesiones: [] });
  const [nuevo, setNuevo] = useState<any>(null);
  const [error, setError] = useState('');
  const [creando, setCreando] = useState(false);
  const [previa, setPrevia] = useState<any>(null);

  const cargar = () => {
    fetch(`${BACKEND_URL}/api/practicas?paciente_id=${pacienteId}`).then(r => r.json()).then(setLista).catch(() => {});
  };
  useEffect(() => {
    setSug(null); setElegidos([]); setNuevo(null); setError('');
    fetch(`${BACKEND_URL}/api/practicas/sugerencias?paciente_id=${pacienteId}`)
      .then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || `Error ${r.status}`); return j; })
      .then(setSug).catch(e => setError(e.message));
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pacienteId]);

  const alternar = (e: any) => setElegidos(v => v.some(x => x.bank_id === e.bank_id)
    ? v.filter(x => x.bank_id !== e.bank_id) : [...v, { ...e, repeticiones: 3, tolerancia_cents: 100 }].slice(0, 8));
  const cambiar = (bid: string, k: string, val: any) => setElegidos(v => v.map(x => x.bank_id === bid ? { ...x, [k]: val } : x));

  const crear = async () => {
    setCreando(true); setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/practicas`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paciente_id: pacienteId, ejercicios: elegidos, indicaciones }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || `Error ${r.status}`);
      setNuevo(j); cargar();
    } catch (e: any) { setError(e?.message || 'No se pudo crear'); }
    setCreando(false);
  };

  const pausar = async (p: any) => {
    await fetch(`${BACKEND_URL}/api/practicas/${p.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ activa: !p.activa }) });
    cargar();
  };

  const mensaje = (n: any) => encodeURIComponent(
    `Hola ${n.nombre}, te dejo tu práctica de voz para hacer en casa: ${n.enlace}\n` +
    `Buscá un lugar tranquilo y seguí la pelotita con tu voz. Tu voz no se graba. Matías Pérez · Fonoaudiólogo`);
  const tel = (t: string) => (t || '').replace(/\D/g, '');

  const nombreEj = (s: any, i: number) => {
    const p = lista.practicas.find((x: any) => x.id === s.practica_id);
    return p?.ejercicios?.[i]?.nombre || `Ejercicio ${i + 1}`;
  };
  const dias = new Set(lista.sesiones.map((s: any) => String(s.creada_at).slice(0, 10))).size;
  const inp = 'px-2 py-1 rounded-lg border border-slate-300 dark:border-white/15 bg-white dark:bg-black/20 text-xs';

  return (
    <div className="space-y-3 text-xs">
      {previa && (
        <div className="fixed inset-0 z-50 bg-black/60 overflow-y-auto" onClick={e => { if (e.target === e.currentTarget) setPrevia(null); }}>
          <div className="max-w-md mx-auto my-6 rounded-2xl overflow-hidden text-sm">
            <PracticaPaciente onCerrar={() => setPrevia(null)} vistaPrevia={{
              nombre: previa.nombre || '', estado: 'activa', consentimiento: true, profesional: 'Matías Pérez · Fonoaudiólogo',
              indicaciones: previa.indicaciones || '',
              ejercicios: previa.ejercicios.map((e: any) => ({ repeticiones: 3, tolerancia_cents: 100, ...e })),
            }} />
          </div>
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}
      {lista.aviso && <p className="text-amber-600">{lista.aviso}</p>}
      {!sug ? (!error && <p className="text-slate-500 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Buscando ejercicios…</p>) : (
        <>
          <p className="text-slate-500">
            Tono de inicio: <b>{sug.tono_base.hz} Hz</b> ({sug.tono_base.origen}). Los ejercicios salen del cuadernillo; los del plan vigente aparecen primero.
          </p>
          <div className="grid sm:grid-cols-2 gap-1.5">
            {sug.ejercicios.map((e: any) => (
              <label key={e.bank_id} className={`flex gap-2 p-2 rounded-lg border cursor-pointer ${elegidos.some(x => x.bank_id === e.bank_id) ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10' : 'border-slate-200 dark:border-white/10'}`}>
                <input type="checkbox" checked={elegidos.some(x => x.bank_id === e.bank_id)} onChange={() => alternar(e)} />
                <span><b>{e.nombre}</b> · {GUIA_TXT[e.guia]}{e.en_plan && <span className="ml-1 text-emerald-600 font-bold">en el plan</span>}</span>
              </label>
            ))}
          </div>
          {sug.excluidos?.length > 0 && (
            <p className="text-amber-700 dark:text-amber-300">No se ofrecen por el diagnóstico: {sug.excluidos.map((x: any) => x.name).join(', ')}.</p>
          )}
          {elegidos.length > 0 && (
            <div className="space-y-2 p-3 rounded-xl bg-slate-50 dark:bg-white/5">
              {elegidos.map(e => (
                <div key={e.bank_id} className="space-y-1">
                  <p className="font-bold">{e.nombre}</p>
                  <div className="flex flex-wrap gap-2 items-center">
                    <label>Tono Hz <input type="number" min={60} max={1000} value={e.base_hz} onChange={x => cambiar(e.bank_id, 'base_hz', Number(x.target.value))} className={inp + ' w-20'} /></label>
                    <label>Repeticiones <input type="number" min={1} max={20} value={e.repeticiones} onChange={x => cambiar(e.bank_id, 'repeticiones', Number(x.target.value))} className={inp + ' w-14'} /></label>
                    <label>Margen <select value={e.tolerancia_cents} onChange={x => cambiar(e.bank_id, 'tolerancia_cents', Number(x.target.value))} className={inp}>
                      <option value={50}>estricto (½ tono)</option><option value={100}>normal (1 tono)</option><option value={200}>amplio (2 tonos)</option></select></label>
                    {e.guia === 'rampa' && <label>Amplitud <input type="number" min={1} max={24} value={e.amplitud} onChange={x => cambiar(e.bank_id, 'amplitud', Number(x.target.value))} className={inp + ' w-14'} /> semitonos</label>}
                    {e.guia === 'sostenida' && <label>Duración <input type="number" min={2} max={30} value={e.duracion_s} onChange={x => cambiar(e.bank_id, 'duracion_s', Number(x.target.value))} className={inp + ' w-14'} /> s</label>}
                  </div>
                  <input value={e.consigna || ''} onChange={x => cambiar(e.bank_id, 'consigna', x.target.value)} className={inp + ' w-full'} placeholder="Consigna para el paciente" />
                </div>
              ))}
              <textarea value={indicaciones} onChange={e => setIndicaciones(e.target.value)} rows={2} className={inp + ' w-full'}
                placeholder="Indicación general (por ejemplo: 2 veces por día, mañana y tarde)" />
              <button onClick={crear} disabled={creando} className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-50 flex items-center gap-1.5">
                {creando ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Crear enlace de práctica
              </button>
              <button onClick={() => setPrevia({ ejercicios: elegidos, indicaciones })}
                className="px-4 py-2 rounded-xl border border-indigo-300 text-indigo-700 dark:text-indigo-300 font-bold flex items-center gap-1.5">
                <Eye size={13} /> Ver como el paciente
              </button>
            </div>
          )}
        </>
      )}

      {nuevo && (
        <div className="p-3 rounded-xl border border-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 space-y-1.5">
          <p className="font-bold text-emerald-800 dark:text-emerald-200">Enlace listo para {nuevo.nombre}</p>
          <p className="break-all">{nuevo.enlace}</p>
          <div className="flex gap-2">
            <a href={`https://wa.me/${tel(nuevo.telefono)}?text=${mensaje(nuevo)}`} target="_blank" rel="noreferrer"
              className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold flex items-center gap-1"><Send size={12} /> Enviar por WhatsApp</a>
            <button onClick={() => navigator.clipboard?.writeText(nuevo.enlace)} className="px-3 py-1.5 rounded-lg border flex items-center gap-1"><Copy size={12} /> Copiar</button>
          </div>
        </div>
      )}

      {lista.practicas.length > 0 && (
        <div className="space-y-1">
          <p className="font-bold">Rutinas enviadas</p>
          {lista.practicas.map((p: any) => (
            <div key={p.id} className="flex flex-wrap items-center gap-2 text-slate-600 dark:text-slate-300">
              <span>{fecha(p.creada_at)} · {p.ejercicios.length} ejercicios · {p.consentimiento_at ? 'consentimiento dado' : 'sin abrir todavía'} · {p.activa ? 'activa' : 'pausada'}</span>
              <button onClick={() => pausar(p)} className="text-indigo-600 flex items-center gap-0.5">{p.activa ? <><Pause size={11} /> Pausar</> : <><Play size={11} /> Reactivar</>}</button>
              <button onClick={() => navigator.clipboard?.writeText(p.enlace)} className="text-indigo-600 flex items-center gap-0.5"><Copy size={11} /> Enlace</button>
              <button onClick={() => setPrevia({ ejercicios: p.ejercicios, indicaciones: p.indicaciones, nombre: p.saludo })} className="text-indigo-600 flex items-center gap-0.5"><Eye size={11} /> Ver</button>
            </div>
          ))}
        </div>
      )}

      {lista.sesiones.length > 0 && (
        <div className="overflow-x-auto">
          <p className="font-bold mb-1">Práctica en casa: {dias} día{dias === 1 ? '' : 's'} con práctica</p>
          <table className="w-full">
            <thead><tr className="text-[10px] uppercase text-slate-500 text-left">
              <th className="px-1.5 py-1">Fecha</th><th className="px-1.5">Ejercicio</th><th className="px-1.5">En el camino</th>
              <th className="px-1.5">F0 mediana</th><th className="px-1.5">Rango</th><th className="px-1.5">Estabilidad</th><th className="px-1.5">Ambiente</th></tr></thead>
            <tbody>
              {lista.sesiones.flatMap((s: any) => (s.resultados || []).map((r: any, i: number) => (
                <tr key={`${s.id}-${i}`} className="border-t border-slate-100 dark:border-white/5">
                  <td className="px-1.5 py-1">{fecha(s.creada_at)}</td>
                  <td className="px-1.5">{nombreEj(s, r.ejercicio)}</td>
                  <td className="px-1.5">{r.dentro_pct != null ? `${r.dentro_pct} %` : '—'}</td>
                  <td className="px-1.5">{r.f0_mediana_hz != null ? `${r.f0_mediana_hz} Hz` : '—'}</td>
                  <td className="px-1.5">{r.f0_min_hz != null ? `${r.f0_min_hz}–${r.f0_max_hz} Hz` : '—'}</td>
                  <td className="px-1.5">{r.desvio_cents != null ? `±${r.desvio_cents} cents` : '—'}</td>
                  <td className="px-1.5">{s.ambiente?.ruido_dbfs != null ? `${s.ambiente.silencioso ? 'tranquilo' : 'ruidoso'} (${s.ambiente.ruido_dbfs} dBFS)` : '—'}</td>
                </tr>
              )))}
            </tbody>
          </table>
          <p className="text-[10px] text-slate-500 mt-1">Medido con el micrófono del celular: orientativo, no reemplaza el análisis acústico en consultorio.</p>
        </div>
      )}
    </div>
  );
}
