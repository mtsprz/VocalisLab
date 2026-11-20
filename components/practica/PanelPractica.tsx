import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Send, Copy, Pause, Play, Eye, AlertTriangle, CheckCircle2 } from 'lucide-react';
import PracticaPaciente from './PracticaPaciente';
import VozGuia from './VozGuia';
import { MedidorIndice, lecturaSZ } from './visuales';
import { nombreLimpio } from '../../utils/guiaPractica';
import { nombreNota, hzAMidi } from '../../utils/pitch';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const GUIA_TXT: Record<string, string> = { sostenida: 'Nota sostenida', escalera: 'Escalera', rampa: 'Rampa (glissando)', patron: 'Patrón' };
const MEDIDAS: Record<string, string> = {
  tono: 'Altura (camino de notas)',
  sostenido: 'Sostenido: duración y estabilidad',
  flujo: 'Flujo / SOVT con ruido (tubo, burbujeo, fricativas)',
  intensidad: 'Intensidad (pareja o messa di voce)',
  pulsos: 'Pulsos / ataques rítmicos',
  libre: 'Libre: búsqueda o habla, sin objetivo tonal',
};
const OIDO: Record<string, { cents: number; texto: string }> = {
  sin_experiencia: { cents: 200, texto: 'Sin experiencia musical' },
  algo: { cents: 100, texto: 'Algo de experiencia' },
  entrenado: { cents: 50, texto: 'Oído entrenado / canto' },
};
const usaTonoE = (e: any) => (e.medida || 'tono') === 'tono' || (e.medida === 'sostenido' && !!e.con_tono);
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
  const [oido, setOido] = useState('sin_experiencia');
  const [elegidos, setElegidos] = useState<any[]>([]);
  const [indicaciones, setIndicaciones] = useState('Dos veces por día, mañana y tarde.');
  const [lista, setLista] = useState<any>({ practicas: [], sesiones: [] });
  const [nuevo, setNuevo] = useState<any>(null);
  const [error, setError] = useState('');
  const [creando, setCreando] = useState(false);
  const [previa, setPrevia] = useState<any>(null);
  const [vozClaves, setVozClaves] = useState<string[]>([]);
  const [verVoz, setVerVoz] = useState(false);
  // De dónde salen los ejercicios: 'auto' = según el centro y si tiene cuadernillo.
  const [origen, setOrigen] = useState('auto');

  const cargar = () => {
    fetch(`${BACKEND_URL}/api/practicas?paciente_id=${pacienteId}`).then(r => r.json()).then(setLista).catch(() => {});
  };
  useEffect(() => { setOrigen('auto'); }, [pacienteId]);
  useEffect(() => {
    setSug(null); setElegidos([]); setNuevo(null); setError(''); setConfirmado(false);
    fetch(`${BACKEND_URL}/api/practicas/sugerencias?paciente_id=${pacienteId}&origen=${origen}`)
      .then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || `Error ${r.status}`); return j; })
      .then(j => {
        setSug(j);
        setBase(j.tono_base?.hz ? String(j.tono_base.hz) : '');
        setRmin(j.rango?.min_hz ? String(Math.round(j.rango.min_hz)) : '');
        setRmax(j.rango?.max_hz ? String(Math.round(j.rango.max_hz)) : '');
      }).catch(e => setError(e.message));
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pacienteId, origen]);

  const b = Number(base), lo = Number(rmin), hi = Number(rmax);
  const tonoOk = b >= 60 && b <= 1000;
  const rangoOk = lo >= 50 && hi > lo && 12 * Math.log2(hi / lo) >= 2;
  const baseEnRango = tonoOk && rangoOk && b >= lo * 0.97 && b <= hi * 1.03;

  /** Ejercicios con el tono de inicio actual y si entran en el rango. */
  const revisados = useMemo(() => elegidos.map(e => {
    const conTono = usaTonoE(e);
    const [g, a] = tonoOk && conTono ? limites(e, b) : [0, 0];
    const fuera = conTono && rangoOk && tonoOk && (g < lo * 2 ** (-0.5 / 12) || a > hi * 2 ** (0.5 / 12));
    return { ...e, base_hz: tonoOk ? b : undefined, _g: g, _a: a, _fuera: fuera, _tono: conTono };
  }), [elegidos, b, lo, hi, tonoOk, rangoOk]);
  const hayFuera = revisados.some(e => e._fuera);
  const necesitaTono = revisados.some(e => e._tono);
  const listo = elegidos.length > 0 && (!necesitaTono || (tonoOk && baseEnRango)) && rangoOk && !hayFuera && confirmado;
  /** Margen tonal según el oído del paciente y su cuadro (el más amplio de los dos). */
  const margenSugerido = Math.max(OIDO[oido].cents, sug?.tolerancia_sugerida?.cents || 100);
  const aplicarOido = (o: string) => {
    setOido(o); setConfirmado(false);
    const c = Math.max(OIDO[o].cents, sug?.tolerancia_sugerida?.cents || 100);
    setElegidos(v => v.map(x => (usaTonoE(x) ? { ...x, tolerancia_cents: c, modelo: o === 'sin_experiencia' ? 'sonoro' : x.modelo } : x)));
  };

  const alternar = (e: any) => { setConfirmado(false); setElegidos(v => v.some(x => x.bank_id === e.bank_id)
    ? v.filter(x => x.bank_id !== e.bank_id) : [...v, { ...e, repeticiones: 3, tolerancia_cents: usaTonoE(e) ? Math.max(e.tolerancia_cents || 0, margenSugerido) : (e.tolerancia_cents || 100) }].slice(0, 8)); };
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
          ejercicios: revisados.map(({ _g, _a, _fuera, _tono, en_plan, ...e }) => e),
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
  const nombreEj = (s: any, i: number) => lista.practicas.find((x: any) => x.id === s.practica_id)?.ejercicios?.[i]?.nombre ? nombreLimpio(lista.practicas.find((x: any) => x.id === s.practica_id).ejercicios[i].nombre) : `Ejercicio ${i + 1}`;
  const inp = 'px-2 py-1 rounded-lg border border-slate-300 dark:border-white/15 bg-white dark:bg-black/20 text-xs';
  const ad = lista.adherencia;
  // Mediciones s/z (la más reciente primero).
  const medicionesSZ = (lista.sesiones || []).flatMap((s: any) =>
    (s.resultados || []).filter((r: any) => r.medida === 'sz').map((r: any) => ({ s, r })));

  return (
    <div className="space-y-3 text-xs">
      {previa && (
        <div className="fixed inset-0 z-50 bg-black/60 overflow-y-auto" onClick={e => { if (e.target === e.currentTarget) setPrevia(null); }}>
          <div className="max-w-md mx-auto my-6 rounded-2xl overflow-hidden text-sm">
            <PracticaPaciente onCerrar={() => setPrevia(null)} vistaPrevia={{
              nombre: previa.nombre || '', estado: 'activa', consentimiento: true, profesional: 'Matías Pérez · Fonoaudiólogo',
              indicaciones: previa.indicaciones || '', veces_por_dia: previa.veces || 2, practicas_hoy: 0, voz: vozClaves,
              fuenteVoz: async (c: string) => { const r = await fetch(`${BACKEND_URL}/api/voz-guia/${encodeURIComponent(c)}/audio`); return r.ok ? r.arrayBuffer() : null; },
              ejercicios: previa.ejercicios.map((e: any) => ({ repeticiones: 3, tolerancia_cents: 100, ...e })),
            }} />
          </div>
        </div>
      )}
      {error && <p className="text-red-600 flex gap-1.5"><AlertTriangle size={13} className="shrink-0" />{error}</p>}
      <div className="p-3 rounded-xl border border-slate-200 dark:border-white/10">
        <button onClick={() => setVerVoz(v => !v)} className="font-bold text-indigo-700 dark:text-indigo-300">
          {verVoz ? '▾' : '▸'} Tu voz guía ({vozClaves.length} grabaciones) — las indicaciones con tu voz
        </button>
        <div className={verVoz ? 'mt-2' : 'hidden'}><VozGuia onCambio={setVozClaves} /></div>
      </div>
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

          <div className="flex flex-wrap items-center gap-3">
            <label className="font-bold">Oído musical del paciente
              <select value={oido} onChange={e => aplicarOido(e.target.value)} className={inp + ' ml-1.5 font-normal'}>
                {Object.entries(OIDO).map(([k, v]) => <option key={k} value={k}>{v.texto}</option>)}
              </select></label>
            <span className="text-slate-500">Margen tonal sugerido: ±{margenSugerido} cents
              {sug.tolerancia_sugerida?.cents > OIDO[oido].cents ? ` (${sug.tolerancia_sugerida.motivo})` : ` (${OIDO[oido].texto.toLowerCase()})`}</span>
          </div>

          {/* 2. Ejercicios: coherentes con el cuadernillo que tiene el paciente */}
          <div className="p-3 rounded-xl border border-slate-200 dark:border-white/10 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-bold">2. Ejercicios de</p>
              <select value={origen} onChange={e => setOrigen(e.target.value)} className={inp}>
                <option value="auto">Automático: {sug.origenes?.[sug.origen_auto] || '—'}</option>
                {Object.entries(sug.origenes || {}).map(([k, v]: any) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            {sug.origen === 'cuadernillo' && sug.cuadernillo && (
              <p className="text-slate-600 dark:text-slate-300">«{sug.cuadernillo.titulo}» del {sug.cuadernillo.fecha}: {sug.cuadernillo.con_guia} de {sug.cuadernillo.total} ejercicios
                tienen práctica guiada. Se muestran en el orden del cuadernillo, con su número.</p>
            )}
            {sug.origen === 'fonoar' && sug.fonoar && (
              <p className="text-slate-600 dark:text-slate-300">Cuadernillo de Fonoar: {sug.fonoar.con_guia} de {sug.fonoar.total} ejercicios
                tienen práctica guiada, con el número que el paciente ve en su cuadernillo.</p>
            )}
            {sug.sin_guia?.length > 0 && (
              <p className="text-slate-500">Del cuadernillo, sin práctica guiada todavía: {sug.sin_guia.map((x: any) => `${x.orden}. ${x.nombre}`).join(' · ')}.</p>
            )}
            {sug.origen === 'sueltos' && <p className="text-slate-500">Práctica fuera del cuadernillo: todos los ejercicios con guía (los del plan vigente primero).</p>}
            {sug.aviso_origen && <p className="text-amber-700 dark:text-amber-300">{sug.aviso_origen}</p>}
          </div>
          <div className="grid sm:grid-cols-2 gap-1.5">
            {sug.ejercicios.map((e: any) => (
              <label key={e.bank_id} className={`flex gap-2 p-2 rounded-lg border cursor-pointer ${elegidos.some(x => x.bank_id === e.bank_id) ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10' : 'border-slate-200 dark:border-white/10'}`}>
                <input type="checkbox" checked={elegidos.some(x => x.bank_id === e.bank_id)} onChange={() => alternar(e)} />
                <span>{e.ref_cuadernillo && <span className="block text-[10px] font-bold text-indigo-600 dark:text-indigo-300">{e.ref_cuadernillo}</span>}<b>{nombreLimpio(e.nombre)}</b> · {MEDIDAS[e.medida || 'tono']?.split(' (')[0].split(':')[0]}{e.medida === 'tono' || !e.medida ? ` (${GUIA_TXT[e.guia]})` : ''}{e.en_plan && <span className="ml-1 text-emerald-600 font-bold">en el plan</span>}</span>
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
                  <p className="font-bold">{nombreLimpio(e.nombre)}
                    {!e._tono && <span className="ml-2 font-normal text-slate-500">sin altura objetivo: no se evalúa la afinación</span>}
                    {tonoOk && e._tono && <span className={`ml-2 font-semibold ${e._fuera ? 'text-red-600' : 'text-emerald-600'}`}>
                      {nota(e._g)}{e._a > e._g * 1.01 ? ` → ${nota(e._a)}` : ''} ({hz1(e._g)}{e._a > e._g * 1.01 ? `–${hz1(e._a)}` : ''} Hz){e._fuera ? ' · fuera del rango' : ' · dentro del rango'}
                    </span>}
                    {e._fuera && <button onClick={() => ajustar(e)} className="ml-2 text-indigo-600 underline">Ajustar al rango</button>}
                  </p>
                  <div className="flex flex-wrap gap-2 items-center">
                    <label>Qué se mide <select value={e.medida || 'tono'} onChange={x => cambiar(e.bank_id, 'medida', x.target.value)} className={inp}>
                      {Object.entries(MEDIDAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                    <label>Ejemplo <select value={e.modelo || 'sonoro'} onChange={x => cambiar(e.bank_id, 'modelo', x.target.value)} className={inp}>
                      <option value="sonoro">con ejemplo sonoro</option><option value="sin_modelo">sin ejemplo (no condicionar la búsqueda)</option></select></label>
                    {e.medida === 'sostenido' && <label className="flex items-center gap-1"><input type="checkbox" checked={!!e.con_tono} onChange={x => cambiar(e.bank_id, 'con_tono', x.target.checked)} /> con nota objetivo</label>}
                    {['sostenido', 'flujo', 'libre'].includes(e.medida) && <label>Duración objetivo <input type="number" min={2} max={60} value={e.duracion_objetivo_s || 8} onChange={x => cambiar(e.bank_id, 'duracion_objetivo_s', Number(x.target.value))} className={inp + ' w-14'} /> s</label>}
                    {['sostenido', 'flujo', 'intensidad'].includes(e.medida) && <label>Margen de intensidad ±<input type="number" min={2} max={15} value={e.margen_db || 6} onChange={x => cambiar(e.bank_id, 'margen_db', Number(x.target.value))} className={inp + ' w-12'} /> dB</label>}
                    {e.medida === 'intensidad' && <label>Patrón <select value={e.patron_intensidad || 'pareja'} onChange={x => cambiar(e.bank_id, 'patron_intensidad', x.target.value)} className={inp}>
                      <option value="pareja">pareja</option><option value="arco">suave–fuerte–suave</option></select></label>}
                    {e.medida === 'pulsos' && <><label>Impulsos <input type="number" min={2} max={30} value={e.pulsos || 6} onChange={x => cambiar(e.bank_id, 'pulsos', Number(x.target.value))} className={inp + ' w-12'} /></label>
                      <label>Tempo <input type="number" min={30} max={200} value={e.tempo_bpm || 80} onChange={x => cambiar(e.bank_id, 'tempo_bpm', Number(x.target.value))} className={inp + ' w-14'} /> por min</label></>}
                    <label>Repeticiones <input type="number" min={1} max={20} value={e.repeticiones} onChange={x => cambiar(e.bank_id, 'repeticiones', Number(x.target.value))} className={inp + ' w-14'} /></label>
                    {e._tono && <label>Margen tonal <select value={e.tolerancia_cents} onChange={x => cambiar(e.bank_id, 'tolerancia_cents', Number(x.target.value))} className={inp}>
                      <option value={50}>estricto (±½ semitono)</option><option value={100}>normal (±1 semitono)</option><option value={200}>amplio (±2 semitonos)</option><option value={300}>muy amplio (±3 semitonos)</option></select></label>}
                    {e._tono && e.guia === 'rampa' && <label>Amplitud <input type="number" min={1} max={24} value={e.amplitud} onChange={x => cambiar(e.bank_id, 'amplitud', Number(x.target.value))} className={inp + ' w-14'} /> semitonos</label>}
                    {e._tono && e.medida !== 'sostenido' && e.guia === 'sostenida' && <label>Duración <input type="number" min={2} max={30} value={e.duracion_s || 6} onChange={x => cambiar(e.bank_id, 'duracion_s', Number(x.target.value))} className={inp + ' w-14'} /> s</label>}
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
                <input type="checkbox" className="mt-0.5" checked={confirmado} disabled={(necesitaTono && (!tonoOk || !baseEnRango)) || !rangoOk || hayFuera} onChange={e => setConfirmado(e.target.checked)} />
                Revisé el tono de inicio ({tonoOk ? `${nota(b)}, ${hz1(b)} Hz` : '—'}) y el rango de trabajo ({rangoOk ? `${nota(lo)}–${nota(hi)}` : '—'}): son los indicados para este paciente.
              </label>
              <div className="flex flex-wrap gap-2">
                <button onClick={() => setPrevia({ ejercicios: revisados, indicaciones, veces })} disabled={necesitaTono && !tonoOk}
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

      {medicionesSZ.length > 0 && (
        <div className="space-y-2">
          <p className="font-bold">Índice s/z medido en casa</p>
          <div className="flex flex-wrap items-center gap-4">
            <div className="text-slate-700 dark:text-slate-200"><MedidorIndice valor={medicionesSZ[0].r.indice_sz} compacto /></div>
            <table className="text-xs">
              <thead><tr className="text-[10px] uppercase text-slate-500 text-left">
                <th className="pr-3">Fecha</th><th className="pr-3">/s/ mejor</th><th className="pr-3">/z/ mejor</th><th className="pr-3">Índice</th><th>Intentos</th></tr></thead>
              <tbody>
                {medicionesSZ.map(({ s, r }: any) => (
                  <tr key={s.id} className="border-t border-slate-100 dark:border-white/5">
                    <td className="pr-3 py-0.5 whitespace-nowrap">{fecha(s.creada_at)}</td>
                    <td className="pr-3">{r.s_max_s ?? '—'} s</td>
                    <td className="pr-3">{r.z_max_s ?? '—'} s</td>
                    <td className="pr-3 font-bold" style={{ color: r.indice_sz != null ? lecturaSZ(r.indice_sz).color : undefined }}>{r.indice_sz ?? '—'}</td>
                    <td className="text-slate-500">s: {(r.s_intentos || []).join(' · ') || '—'} | z: {(r.z_intentos || []).join(' · ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-slate-500">Mejor /s/ dividido mejor /z/, con el micrófono del celular (detecta inicio y fin del sonido). Orientativo: confirmalo en consultorio.</p>
        </div>
      )}

      {lista.sesiones.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr className="text-[10px] uppercase text-slate-500 text-left">
              <th className="px-1.5 py-1">Fecha</th><th className="px-1.5">Ejercicio</th><th className="px-1.5">Logro</th>
              <th className="px-1.5">Altura</th><th className="px-1.5">F0</th><th className="px-1.5">Intensidad</th>
              <th className="px-1.5">Continuidad</th><th className="px-1.5">Pulsos</th><th className="px-1.5">Periodicidad</th>
              <th className="px-1.5">Afinación inicial</th><th className="px-1.5">Ambiente</th></tr></thead>
            <tbody>
              {lista.sesiones.flatMap((s: any) => (s.resultados || []).filter((r: any) => r.medida !== 'sz').map((r: any, i: number) => (
                <tr key={`${s.id}-${i}`} className="border-t border-slate-100 dark:border-white/5 align-top">
                  <td className="px-1.5 py-1 whitespace-nowrap">{fecha(s.creada_at)}</td>
                  <td className="px-1.5">{nombreEj(s, r.ejercicio)}<span className="block text-[10px] text-slate-500">{(MEDIDAS[r.medida || 'tono'] || '').split(' (')[0].split(':')[0]}</span></td>
                  <td className="px-1.5 font-bold">{r.logro_pct != null ? `${r.logro_pct} %` : r.dentro_pct != null ? `${r.dentro_pct} %` : '—'}</td>
                  <td className="px-1.5">{r.altura_no_medible ? 'no medible (sonido sin altura)' : r.dentro_pct != null ? `${r.dentro_pct} % en el camino${r.octava_pct ? ` · ${r.octava_pct} % en otra octava` : ''}${r.desvio_cents != null ? ` · ±${r.desvio_cents} cents` : ''}` : '—'}</td>
                  <td className="px-1.5">{r.f0_mediana_hz != null ? `${r.f0_mediana_hz} Hz (${nota(r.f0_mediana_hz)})${r.f0_min_hz != null ? ` · ${nota(r.f0_min_hz)}–${nota(r.f0_max_hz)}` : ''}` : '—'}</td>
                  <td className="px-1.5">{r.intensidad_media_db != null ? `${r.intensidad_media_db} dB sobre el ambiente · rango ${r.intensidad_rango_db ?? '—'} dB · estabilidad ±${r.intensidad_sd_db ?? '—'} dB${r.intensidad_dentro_pct != null ? ` · ${r.intensidad_dentro_pct} % en el margen` : ''}` : '—'}</td>
                  <td className="px-1.5">{r.tramo_max_s != null ? `tramo máx. ${r.tramo_max_s} s · ${r.cortes ?? 0} cortes · ${r.sonido_s ?? '—'} s de sonido` : '—'}</td>
                  <td className="px-1.5">{r.medida === 'pulsos' ? `${r.pulsos} · regularidad ${r.pulsos_regularidad_pct ?? '—'} %` : '—'}</td>
                  <td className="px-1.5">{r.periodicidad_pct != null ? `${r.periodicidad_pct} %` : '—'}</td>
                  <td className="px-1.5">{s.ambiente?.calibracion_hz ? `${s.ambiente.calibracion_hz} Hz${s.ambiente.calibracion_st != null ? ` (${s.ambiente.calibracion_st > 0 ? '+' : ''}${s.ambiente.calibracion_st} st)` : ''}` : '—'}</td>
                  <td className="px-1.5">{s.ambiente?.ruido_dbfs != null ? `${s.ambiente.silencioso ? 'tranquilo' : 'ruidoso'} (${s.ambiente.ruido_dbfs} dBFS)` : '—'}</td>
                </tr>
              )))}
            </tbody>
          </table>
          <p className="text-[10px] text-slate-500 mt-1">Medido con el micrófono del celular: orientativo, no reemplaza el análisis acústico en consultorio. Intensidad en dB relativos (sobre el ruido del lugar; el micrófono del celular no está calibrado en dB SPL). Periodicidad: parte del sonido con altura medible (baja en tubo en agua o fricativas: es esperable).</p>
        </div>
      )}
    </div>
  );
}
