import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Send, Copy, Pause, Play, Eye, AlertTriangle, CheckCircle2 } from 'lucide-react';
import PracticaPaciente from './PracticaPaciente';
import { nombreNota, hzAMidi } from '../../utils/pitch';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const GUIA_TXT: Record<string, string> = { sostenida: 'Nota sostenida', escalera: 'Escalera', rampa: 'Rampa (glissando)', patron: 'Patrón' };
const fecha = (f: any) => (f ? new Date(f).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }) : '—');
const nota = (hz: number) => (hz > 0 ? nombreNota(hzAMidi(hz)) : '—');
const hz1 = (v: number) => Math.round(v);

/** Nota más grave y más aguda que pide un ejercicio con un tono de inicio dado. */
function limites(e: any, base: number): [number, number] {
  const semis = e.guia === 'sostenida' ? [0] : e.guia === 'rampa' ? [0, Number(e.amplitud) || 7] : (e.semitonos || [0]);
  return [base * 2 ** (Math.min(...semis) / 12), base * 2 ** (Math.max(...semis) / 12)];
}

/**
 * Práctica guiada para casa. El tono de inicio y el rango de trabajo salen de
 * los datos clínicos del paciente (con su origen); cada ejercicio muestra sus
 * notas y no se puede enviar si sale del rango. El profesional confirma antes
 * de mandar el enlace. Abajo: registro diario de práctica.
 */
export default function PanelPractica({ pacienteId }: { pacienteId: string }) {
  const [sug, setSug] = useState<any>(null);
  const [base, setBase] = useState<string>('');
  const [rmin, setRmin] = useState<string>('');
  const [rmax, setRmax] = useState<string>('');
  const [guardarRango, setGuardarRango] = useState(false);
  const [confirmado, setConfirmado] = useState(false);
  const [veces, setVeces] = useState(2);
  const [elegidos, setElegidos] = useState<any[]>([]);
  const [indicaciones, setIndicaciones] = useState('Dos veces por día, mañana y tarde.');
  const [lista, setLista] = useState<any>({ practicas: [], sesiones: [] });
  const [nuevo, setNuevo] = useState<any>(null);
  const [error, setError] = useState('');
  const [creando, setCreando] = useState(false);
  const [previa, setPrevia] = useState<any>(null);

  const cargar = () => {
    fetch(`${BACKEND_URL}/api/practicas?paciente_id=${pacienteId}`).then(r => r.json()).then(setLista).catch(() => {});
  };
  useEffect(() => {
    setSug(null); setElegidos([]); setNuevo(null); setError(''); setConfirmado(false);
    fetch(`${BACKEND_URL}/api/practicas/sugerencias?paciente_id=${pacienteId}`)
      .then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || `Error ${r.status}`); return j; })
      .then(j => {
        setSug(j);
        setBase(j.tono_base?.hz ? String(j.tono_base.hz) : '');
        setRmin(j.rango?.min_hz ? String(Math.round(j.rango.min_hz)) : '');
        setRmax(j.rango?.max_hz ? String(Math.round(j.rango.max_hz)) : '');
      }).catch(e => setError(e.message));
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pacienteId]);

  const b = Number(base), lo = Number(rmin), hi = Number(rmax);
  const tonoOk = b >= 60 && b <= 1000;
  const rangoOk = lo >= 50 && hi > lo && 12 * Math.log2(hi / lo) >= 2;
  const baseEnRango = tonoOk && rangoOk && b >= lo * 0.97 && b <= hi * 1.03;

  /** Ejercicios con el tono de inicio actual y si entran en el rango. */
  const revisados = useMemo(() => elegidos.map(e => {
    const [g, a] = tonoOk ? limites(e, b) : [0, 0];
    const fuera = rangoOk && tonoOk && (g < lo * 2 ** (-0.5 / 12) || a > hi * 2 ** (0.5 / 12));
    return { ...e, base_hz: b, _g: g, _a: a, _fuera: fuera };
  }), [elegidos, b, lo, hi, tonoOk, rangoOk]);
  const hayFuera = revisados.some(e => e._fuera);
  const listo = elegidos.length > 0 && tonoOk && rangoOk && baseEnRango && !hayFuera && confirmado;

  const alternar = (e: any) => { setConfirmado(false); setElegidos(v => v.some(x => x.bank_id === e.bank_id)
    ? v.filter(x => x.bank_id !== e.bank_id) : [...v, { ...e, repeticiones: 3, tolerancia_cents: 100 }].slice(0, 8)); };
  const cambiar = (bid: string, k: string, val: any) => { setConfirmado(false); setElegidos(v => v.map(x => x.bank_id === bid ? { ...x, [k]: val } : x)); };

  /** Acota amplitud/escalera al rango de trabajo. */
  const ajustar = (e: any) => {
    if (!tonoOk || !rangoOk) return;
    const tope = Math.floor(12 * Math.log2(hi / b) + 1e-6);
    if (e.guia === 'rampa') cambiar(e.bank_id, 'amplitud', Math.max(1, Math.min(Number(e.amplitud) || 7, tope)));
    else if (e.semitonos) cambiar(e.bank_id, 'semitonos', e.semitonos.filter((s: number) => s <= tope).length >= 2 ? e.semitonos.filter((s: number) => s <= tope) : [0, Math.max(0, Math.min(2, tope)), 0]);
  };

  const crear = async () => {
    setCreando(true); setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/practicas`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paciente_id: pacienteId, indicaciones, veces_por_dia: veces, confirmado,
          rango: { min_hz: lo, max_hz: hi }, guardar_rango_paciente: guardarRango,
          ejercicios: revisados.map(({ _g, _a, _fuera, en_plan, ...e }) => e),
        }),
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
    `Hola ${n.nombre}, te dejo tu práctica de voz para hacer en casa (${veces} vez${veces === 1 ? '' : 'es'} por día): ${n.enlace}\n` +
    `Buscá un lugar tranquilo (mejor con auriculares): primero escuchás cada ejercicio y después lo hacés vos siguiendo la pelotita. Tu voz no se graba. Matías Pérez · Fonoaudiólogo`);
  const tel = (t: string) => (t || '').replace(/\D/g, '');
  const nombreEj = (s: any, i: number) => lista.practicas.find((x: any) => x.id === s.practica_id)?.ejercicios?.[i]?.nombre || `Ejercicio ${i + 1}`;
  const inp = 'px-2 py-1 rounded-lg border border-slate-300 dark:border-white/15 bg-white dark:bg-black/20 text-xs';
  const ad = lista.adherencia;

  return (
    <div className="space-y-3 text-xs">
      {previa && (
        <div className="fixed inset-0 z-50 bg-black/60 overflow-y-auto" onClick={e => { if (e.target === e.currentTarget) setPrevia(null); }}>
          <div className="max-w-md mx-auto my-6 rounded-2xl overflow-hidden text-sm">
            <PracticaPaciente onCerrar={() => setPrevia(null)} vistaPrevia={{
              nombre: previa.nombre || '', estado: 'activa', consentimiento: true, profesional: 'Matías Pérez · Fonoaudiólogo',
              indicaciones: previa.indicaciones || '', veces_por_dia: previa.veces || 2, practicas_hoy: 0,
              ejercicios: previa.ejercicios.map((e: any) => ({ repeticiones: 3, tolerancia_cents: 100, ...e })),
            }} />
          </div>
        </div>
      )}
      {error && <p className="text-red-600 flex gap-1.5"><AlertTriangle size={13} className="shrink-0" />{error}</p>}
      {lista.aviso && <p className="text-amber-600">{lista.aviso}</p>}

      {!sug ? (!error && <p className="text-slate-500 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Buscando datos y ejercicios…</p>) : (
        <>
          {/* 1. Tono y rango (de los datos clínicos) */}
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 space-y-2">
            <p className="font-bold">1. Tono de inicio y rango de trabajo</p>
            <div className="flex flex-wrap gap-3 items-end">
              <label className="flex flex-col">Tono de inicio (Hz)
                <span className="flex items-center gap-1.5"><input type="number" min={60} max={1000} value={base} onChange={e => { setBase(e.target.value); setConfirmado(false); }} className={inp + ' w-20'} />
                  <b>{tonoOk ? nota(b) : '—'}</b></span>
              </label>
              <label className="flex flex-col">Rango de trabajo (Hz)
                <span className="flex items-center gap-1.5">
                  <input type="number" value={rmin} onChange={e => { setRmin(e.target.value); setConfirmado(false); }} className={inp + ' w-16'} /> –
                  <input type="number" value={rmax} onChange={e => { setRmax(e.target.value); setConfirmado(false); }} className={inp + ' w-16'} />
                  <b>{rangoOk ? `${nota(lo)} – ${nota(hi)}` : '—'}</b></span>
              </label>
            </div>
            <p className="text-slate-500">Tono: {sug.tono_base?.origen}</p>
            <p className="text-slate-500">Rango: {sug.rango?.origen}</p>
            {sug.mediciones?.length > 0 && (
              <p className="text-slate-500">Mediciones registradas: {sug.mediciones.map((m: any, i: number) => (
                <button key={i} onClick={() => { setBase(String(m.hz)); setConfirmado(false); }} className="text-indigo-600 mr-2 underline decoration-dotted"
                  title="Usar como tono de inicio">{m.hz} Hz {m.nota} ({m.tipo === 'conversacional' ? 'habla' : 'vocal sostenida'}, {m.fecha})</button>
              ))}</p>
            )}
            {!tonoOk && <p className="text-amber-700 dark:text-amber-300">Cargá el tono de inicio: no hay F0 medida para este paciente.</p>}
            {!rangoOk && <p className="text-amber-700 dark:text-amber-300">Cargá el rango de trabajo (mínimo y máximo).</p>}
            {tonoOk && rangoOk && !baseEnRango && <p className="text-red-600">El tono de inicio está fuera del rango de trabajo.</p>}
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={guardarRango} onChange={e => setGuardarRango(e.target.checked)} />
              Guardar este rango como rango clínico del paciente</label>
          </div>

          {/* 2. Ejercicios */}
          <p className="font-bold">2. Ejercicios (del cuadernillo; los del plan vigente primero)</p>
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

          {revisados.length > 0 && (
            <div className="space-y-2 p-3 rounded-xl bg-slate-50 dark:bg-white/5">
              {revisados.map(e => (
                <div key={e.bank_id} className="space-y-1">
                  <p className="font-bold">{e.nombre}
                    {tonoOk && <span className={`ml-2 font-semibold ${e._fuera ? 'text-red-600' : 'text-emerald-600'}`}>
                      {nota(e._g)}{e._a > e._g * 1.01 ? ` → ${nota(e._a)}` : ''} ({hz1(e._g)}{e._a > e._g * 1.01 ? `–${hz1(e._a)}` : ''} Hz){e._fuera ? ' · fuera del rango' : ' · dentro del rango'}
                    </span>}
                    {e._fuera && <button onClick={() => ajustar(e)} className="ml-2 text-indigo-600 underline">Ajustar al rango</button>}
                  </p>
                  <div className="flex flex-wrap gap-2 items-center">
                    <label>Repeticiones <input type="number" min={1} max={20} value={e.repeticiones} onChange={x => cambiar(e.bank_id, 'repeticiones', Number(x.target.value))} className={inp + ' w-14'} /></label>
                    <label>Margen <select value={e.tolerancia_cents} onChange={x => cambiar(e.bank_id, 'tolerancia_cents', Number(x.target.value))} className={inp}>
                      <option value={50}>estricto (½ tono)</option><option value={100}>normal (1 tono)</option><option value={200}>amplio (2 tonos)</option></select></label>
                    {e.guia === 'rampa' && <label>Amplitud <input type="number" min={1} max={24} value={e.amplitud} onChange={x => cambiar(e.bank_id, 'amplitud', Number(x.target.value))} className={inp + ' w-14'} /> semitonos</label>}
                    {e.guia === 'sostenida' && <label>Duración <input type="number" min={2} max={30} value={e.duracion_s || 6} onChange={x => cambiar(e.bank_id, 'duracion_s', Number(x.target.value))} className={inp + ' w-14'} /> s</label>}
                  </div>
                  <input value={e.consigna || ''} onChange={x => cambiar(e.bank_id, 'consigna', x.target.value)} className={inp + ' w-full'} placeholder="Consigna para el paciente" />
                </div>
              ))}

              {/* 3. Frecuencia y confirmación */}
              <p className="font-bold pt-1">3. Frecuencia y confirmación</p>
              <div className="flex flex-wrap gap-3 items-center">
                <label>Prácticas por día <select value={veces} onChange={e => setVeces(Number(e.target.value))} className={inp}>
                  {[1, 2, 3].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
              </div>
              <textarea value={indicaciones} onChange={e => setIndicaciones(e.target.value)} rows={2} className={inp + ' w-full'} placeholder="Indicación general" />
              <label className="flex items-start gap-1.5 font-semibold">
                <input type="checkbox" className="mt-0.5" checked={confirmado} disabled={!tonoOk || !rangoOk || !baseEnRango || hayFuera} onChange={e => setConfirmado(e.target.checked)} />
                Revisé el tono de inicio ({tonoOk ? `${nota(b)}, ${hz1(b)} Hz` : '—'}) y el rango de trabajo ({rangoOk ? `${nota(lo)}–${nota(hi)}` : '—'}): son los indicados para este paciente.
              </label>
              <div className="flex flex-wrap gap-2">
                <button onClick={() => setPrevia({ ejercicios: revisados, indicaciones, veces })} disabled={!tonoOk}
                  className="px-4 py-2 rounded-xl border border-indigo-300 text-indigo-700 dark:text-indigo-300 font-bold flex items-center gap-1.5 disabled:opacity-40">
                  <Eye size={13} /> Ver y escuchar como el paciente
                </button>
                <button onClick={crear} disabled={creando || !listo}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-40 flex items-center gap-1.5">
                  {creando ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Crear enlace de práctica
                </button>
              </div>
              {hayFuera && <p className="text-red-600">Hay ejercicios fuera del rango: ajustalos antes de enviar.</p>}
            </div>
          )}
        </>
      )}

      {nuevo && (
        <div className="p-3 rounded-xl border border-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 space-y-1.5">
          <p className="font-bold text-emerald-800 dark:text-emerald-200 flex items-center gap-1"><CheckCircle2 size={13} /> Enlace listo para {nuevo.nombre}</p>
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
              <span>{fecha(p.creada_at)} · {p.ejercicios.length} ejercicios · {p.ejercicios[0] ? `inicio ${nota(p.ejercicios[0].base_hz)}` : ''} · {p.consentimiento_at ? 'consentimiento dado' : 'sin abrir todavía'} · {p.activa ? 'activa' : 'pausada'}</span>
              <button onClick={() => pausar(p)} className="text-indigo-600 flex items-center gap-0.5">{p.activa ? <><Pause size={11} /> Pausar</> : <><Play size={11} /> Reactivar</>}</button>
              <button onClick={() => navigator.clipboard?.writeText(p.enlace)} className="text-indigo-600 flex items-center gap-0.5"><Copy size={11} /> Enlace</button>
              <button onClick={() => setPrevia({ ejercicios: p.ejercicios, indicaciones: p.indicaciones, nombre: p.saludo, veces: p.veces_por_dia })} className="text-indigo-600 flex items-center gap-0.5"><Eye size={11} /> Ver</button>
            </div>
          ))}
        </div>
      )}

      {ad && lista.sesiones.length > 0 && (
        <div className="space-y-1">
          <p className="font-bold">Registro de práctica (últimos 14 días): {ad.dias_cumplidos} días completos ({ad.veces_por_dia} por día) · {ad.dias_con_practica} días con alguna práctica</p>
          <div className="flex gap-1">
            {ad.serie.map((d: any) => (
              <div key={d.dia} className="flex-1 text-center" title={`${d.dia}: ${d.practicas} práctica(s)`}>
                <div className={`h-6 rounded ${d.practicas >= ad.veces_por_dia ? 'bg-emerald-500' : d.practicas ? 'bg-amber-400' : 'bg-slate-200 dark:bg-white/10'}`} />
                <span className="text-[9px] text-slate-500">{d.dia.slice(8)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {lista.sesiones.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr className="text-[10px] uppercase text-slate-500 text-left">
              <th className="px-1.5 py-1">Fecha</th><th className="px-1.5">Ejercicio</th><th className="px-1.5">En el camino</th><th className="px-1.5">Octava</th>
              <th className="px-1.5">F0 mediana</th><th className="px-1.5">Rango</th><th className="px-1.5">Estabilidad</th><th className="px-1.5">Afinación inicial</th><th className="px-1.5">Ambiente</th></tr></thead>
            <tbody>
              {lista.sesiones.flatMap((s: any) => (s.resultados || []).map((r: any, i: number) => (
                <tr key={`${s.id}-${i}`} className="border-t border-slate-100 dark:border-white/5">
                  <td className="px-1.5 py-1">{fecha(s.creada_at)}</td>
                  <td className="px-1.5">{nombreEj(s, r.ejercicio)}</td>
                  <td className="px-1.5">{r.dentro_pct != null ? `${r.dentro_pct} %` : '—'}</td>
                  <td className="px-1.5">{r.octava_pct ? `${r.octava_pct} %` : '—'}</td>
                  <td className="px-1.5">{r.f0_mediana_hz != null ? `${r.f0_mediana_hz} Hz (${nota(r.f0_mediana_hz)})` : '—'}</td>
                  <td className="px-1.5">{r.f0_min_hz != null ? `${nota(r.f0_min_hz)}–${nota(r.f0_max_hz)}` : '—'}</td>
                  <td className="px-1.5">{r.desvio_cents != null ? `±${r.desvio_cents} cents` : '—'}</td>
                  <td className="px-1.5">{s.ambiente?.calibracion_hz ? `${s.ambiente.calibracion_hz} Hz (${s.ambiente.calibracion_st > 0 ? '+' : ''}${s.ambiente.calibracion_st} st)` : '—'}</td>
                  <td className="px-1.5">{s.ambiente?.ruido_dbfs != null ? `${s.ambiente.silencioso ? 'tranquilo' : 'ruidoso'} (${s.ambiente.ruido_dbfs} dBFS)` : '—'}</td>
                </tr>
              )))}
            </tbody>
          </table>
          <p className="text-[10px] text-slate-500 mt-1">Medido con el micrófono del celular: orientativo, no reemplaza el análisis acústico en consultorio. «Octava»: tiempo en que cantó la misma nota una octava arriba o abajo.</p>
        </div>
      )}
    </div>
  );
}
