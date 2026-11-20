import React, { useEffect, useMemo, useState } from 'react';
import { ClipboardList, Loader2, Image as ImageIcon, Film, Columns2, Eye, EyeOff, Sparkles, AlertTriangle, ExternalLink } from 'lucide-react';
import { nombreCentro } from '../centros';
import PanelPractica from '../practica/PanelPractica';
import OrientacionClinica from './OrientacionClinica';
import { fechaCorta, fechaHora, edad as edadDe } from '../../utils/fechas';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props { pacienteId: string | null }

const fmt = (v: any, dec = 1) => (v == null || v === '' ? '—' : typeof v === 'number' ? String(Math.round(v * 10 ** dec) / 10 ** dec) : String(v));
const fecha = (f: any) => fechaCorta(f);
const esVisual = (a: any) => /^(image|video)\//.test(a.mime || '') || ['foto', 'video'].includes(a.tipo);
const vistaDrive = (a: any) => `https://drive.google.com/file/d/${a.drive_file_id}/preview`;

/** Dato clínico más cercano (en días) a una fecha. */
function masCercano(lista: any[], f: string, campo = 'fecha') {
  if (!lista?.length || !f) return null;
  const t = new Date(f).getTime();
  return [...lista].sort((a, b) => Math.abs(new Date(a[campo]).getTime() - t) - Math.abs(new Date(b[campo]).getTime() - t))[0];
}

function Tarjeta({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-slate-200 dark:border-white/10 p-4">
      <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">{titulo}</h3>
      {children}
    </div>
  );
}

/** Curva mínima para ver la tendencia de un valor en el tiempo. */
function Tendencia({ valores }: { valores: number[] }) {
  if (valores.length < 2) return null;
  const min = Math.min(...valores), max = Math.max(...valores), r = max - min || 1;
  const pts = valores.map((v, i) => `${(i / (valores.length - 1)) * 100},${28 - ((v - min) / r) * 24}`).join(' ');
  return <svg viewBox="0 0 100 30" className="w-24 h-6"><polyline points={pts} fill="none" stroke="#6366f1" strokeWidth="2" /></svg>;
}

/**
 * Ficha integral: todos los datos del paciente en una hoja (clínica,
 * informes ORL, evolución de escalas y acústica, F0, autoevaluaciones, plan)
 * y la galería de estudios por imagen, con comparación de dos fechas y un
 * análisis automático orientativo.
 */
export default function FichaIntegralModule({ pacienteId }: Props) {
  const [d, setD] = useState<any | null>(null);
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(false);
  const [abiertos, setAbiertos] = useState<string[]>([]);
  const [comparar, setComparar] = useState<string[]>([]);
  const [analisis, setAnalisis] = useState<{ texto?: string; cargando?: boolean; error?: string }>({});

  useEffect(() => {
    if (!pacienteId) return;
    setCargando(true); setError(''); setD(null); setComparar([]); setAnalisis({});
    fetch(`${BACKEND_URL}/api/ficha/${pacienteId}`)
      .then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || `Error ${r.status}`); return j; })
      .then(setD).catch(e => setError(e.message)).finally(() => setCargando(false));
  }, [pacienteId]);

  const visuales = useMemo(() => (d?.archivos || []).filter(esVisual), [d]);
  const seleccion = visuales.filter((a: any) => comparar.includes(a.id)).sort((a: any, b: any) => String(a.fecha).localeCompare(String(b.fecha)));

  const analizar = async () => {
    setAnalisis({ cargando: true });
    try {
      const r = await fetch(`${BACKEND_URL}/api/ficha/${pacienteId}/analisis-imagenes`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archivo_ids: seleccion.map((a: any) => a.id) }),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || `Error ${r.status}`);
      setAnalisis({ texto: j.texto });
    } catch (e: any) {
      setAnalisis({ error: e?.message || 'No se pudo analizar' });
    }
  };

  if (!pacienteId) return <p className="text-sm text-slate-500 max-w-5xl mx-auto">Elegí un paciente en «Pacientes» para ver su ficha integral.</p>;
  if (cargando) return <p className="text-sm text-slate-500 max-w-5xl mx-auto flex items-center gap-2"><Loader2 size={16} className="animate-spin" /> Juntando todos los datos…</p>;
  if (error) return <p className="text-sm text-red-600 max-w-5xl mx-auto">{error}</p>;
  if (!d) return null;

  const p = d.paciente, an = d.anamnesis || {};
  const evals = d.evaluaciones || [], acus = d.analisis_acusticos || [];
  const edad = edadDe(p.fecha_nacimiento);
  const th = 'px-2 py-1.5 text-left text-[10px] uppercase font-bold text-slate-500';
  const td = 'px-2 py-1.5 text-xs text-slate-800 dark:text-slate-200';

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* Encabezado */}
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-slate-200 dark:border-white/10 p-5">
        <h2 className="text-lg font-black text-slate-900 dark:text-white flex items-center gap-2">
          <ClipboardList size={20} className="text-indigo-500" /> {p.nombre_completo || p.nombre}
        </h2>
        <p className="text-xs text-slate-600 dark:text-slate-300 mt-1">
          {[edad != null && `${edad} años`, p.sexo, p.ocupacion, p.demanda_vocal_horas && `${p.demanda_vocal_horas} h/día de voz`,
            nombreCentro(p.centro), p.obra_social, p.tipo_atencion === 'canto' && 'Alumno/a de canto'].filter(Boolean).join(' · ')}
        </p>
        <p className="text-[11px] text-slate-500 mt-1">
          {d.turnos.total} turnos ({d.turnos.realizados} realizados){d.turnos.primero ? ` · desde ${fecha(d.turnos.primero)}` : ''}
          {' · '}{evals.length} evaluaciones · {acus.length} análisis acústicos · {visuales.length} imágenes/videos
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Tarjeta titulo="Cuadro clínico">
          <dl className="text-xs space-y-1.5">
            <div><dt className="font-semibold text-slate-500 inline">Motivo: </dt><dd className="inline text-slate-800 dark:text-slate-200">{an.motivo_consulta || '—'}</dd></div>
            <div><dt className="font-semibold text-slate-500 inline">Diagnóstico ORL: </dt><dd className="inline font-bold text-slate-800 dark:text-slate-200">{an.diagnostico_orl || '—'}</dd></div>
            <div><dt className="font-semibold text-slate-500 inline">Exploración: </dt><dd className="inline">{an.metodo_exploracion || '—'}</dd></div>
            {an.antecedentes_salud && <div><dt className="font-semibold text-slate-500 inline">Antecedentes: </dt><dd className="inline">{an.antecedentes_salud}</dd></div>}
            {an.resumen_clinico && <p className="text-slate-600 dark:text-slate-300 pt-1 border-t border-slate-100 dark:border-white/5">{an.resumen_clinico}</p>}
          </dl>
        </Tarjeta>

        <Tarjeta titulo={`Informes del ORL (${d.informes_orl.length})`}>
          {d.informes_orl.length === 0 ? <p className="text-xs text-slate-500">Sin informes cargados.</p> : (
            <ul className="text-xs space-y-1.5">
              {d.informes_orl.map((i: any) => (
                <li key={i.id}>
                  <b>{i.fecha_informe || fecha(i.fecha)}</b> · {i.diagnostico_principal || 'sin diagnóstico'}
                  <span className="text-slate-500">{i.metodo_exploracion ? ` · ${i.metodo_exploracion}` : ''}{i.profesional_orl ? ` · ${i.profesional_orl}` : ''}</span>
                  {i.archivo_url && <a href={i.archivo_url} target="_blank" rel="noreferrer" className="ml-1 text-indigo-600 inline-flex"><ExternalLink size={11} /></a>}
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>

      {/* Evolución */}
      <Tarjeta titulo="Evolución de escalas y autovaloración">
        {evals.length === 0 ? <p className="text-xs text-slate-500">Sin evaluaciones guardadas.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr><th className={th}>Fecha</th><th className={th}>GRBAS</th><th className={th}>VHI-10</th><th className={th}>Riesgo</th><th className={th}>TME /a/ · /s/</th><th className={th}>S/Z</th><th className={th}>Autoperc.</th></tr></thead>
              <tbody>
                {evals.map((e: any) => (
                  <tr key={e.id} className="border-t border-slate-100 dark:border-white/5">
                    <td className={td}>{fecha(e.fecha)}</td>
                    <td className={td}>{e.grbas ? `G${e.grbas.G ?? '–'} R${e.grbas.R ?? '–'} B${e.grbas.B ?? '–'} A${e.grbas.A ?? '–'} S${e.grbas.S ?? '–'}` : '—'}</td>
                    <td className={td}>{fmt(e.vhi10_score, 0)}/40</td>
                    <td className={td}>{fmt(e.riesgo_vocal_score, 0)}</td>
                    <td className={td}>{fmt(e.tme_o)} · {fmt(e.tme_s)} s</td>
                    <td className={td}>{fmt(e.indice_so, 2)}</td>
                    <td className={td}>{fmt(e.autopercepcion_vocal, 0)}/10</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex gap-6 mt-2 text-[11px] text-slate-500 items-center">
              <span className="flex items-center gap-1">VHI-10 <Tendencia valores={evals.map((e: any) => e.vhi10_score).filter((v: any) => v != null)} /></span>
              <span className="flex items-center gap-1">Riesgo <Tendencia valores={evals.map((e: any) => e.riesgo_vocal_score).filter((v: any) => v != null)} /></span>
            </div>
          </div>
        )}
      </Tarjeta>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Tarjeta titulo="Análisis acústicos (propios y externos)">
          {acus.length === 0 ? <p className="text-xs text-slate-500">Sin análisis acústicos.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead><tr><th className={th}>Fecha</th><th className={th}>F0</th><th className={th}>Jitter</th><th className={th}>Shimmer</th><th className={th}>HNR</th><th className={th}>CPPS</th><th className={th}>AVQI</th></tr></thead>
                <tbody>
                  {acus.map((a: any) => (
                    <tr key={a.id} className="border-t border-slate-100 dark:border-white/5">
                      <td className={td}>{fecha(a.fecha)}</td><td className={td}>{fmt(a.f0_mean, 0)}</td>
                      <td className={td}>{fmt(a.jitter_local_pct, 2)}%</td><td className={td}>{fmt(a.shimmer_local_pct, 2)}%</td>
                      <td className={td}>{fmt(a.hnr_db)}</td><td className={td}>{fmt(a.cpps_db)}</td><td className={td}>{fmt(a.avqi, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Tarjeta>
        <Tarjeta titulo="F0 conversacional y autoevaluaciones">
          {d.f0_conversacional.length > 0 ? (
            <p className="text-xs flex items-center gap-2">
              {d.f0_conversacional.length} mediciones · última {fmt(d.f0_conversacional.at(-1).f0_mediana_hz, 0)} Hz ({fecha(d.f0_conversacional.at(-1).fecha)})
              <Tendencia valores={d.f0_conversacional.map((x: any) => x.f0_mediana_hz)} />
            </p>
          ) : <p className="text-xs text-slate-500">Sin mediciones de F0.</p>}
          <ul className="text-xs mt-2 space-y-1">
            {d.autoevaluaciones.map((a: any) => (
              <li key={a.id}>Autoevaluación {fecha(a.completada_at)}: autopercepción {fmt(a.autopercepcion, 0)}/10 · VHI-10 {fmt(a.vhi10_score, 0)} · riesgo {fmt(a.riesgo_vocal_score, 0)}
                {a.comentario && <span className="text-slate-500 italic"> — «{a.comentario}»</span>}</li>
            ))}
          </ul>
          {d.plan_vigente?.recomendacion && (
            <p className="text-xs mt-2 pt-2 border-t border-slate-100 dark:border-white/5">
              <b>Plan vigente ({fecha(d.plan_vigente.creada_at)}):</b> {d.plan_vigente.recomendacion.diagnostico_funcional_fonoaudiologico}
            </p>
          )}
        </Tarjeta>
      </div>

      {/* Galería y comparación */}
      <Tarjeta titulo={`Estudios por imagen (${visuales.length})`}>
        {visuales.length === 0 ? (
          <p className="text-xs text-slate-500">Todavía no hay imágenes ni videos. Subilos desde Pacientes → carpeta del paciente (las imágenes de los PDF se separan solas).</p>
        ) : (
          <>
            <p className="text-[11px] text-slate-500 mb-2">Marcá «Comparar» en dos estudios (por ejemplo, 2023 y 2026) para verlos lado a lado.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {visuales.map((a: any) => (
                <div key={a.id} className={`rounded-xl border p-2 text-xs ${comparar.includes(a.id) ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10' : 'border-slate-200 dark:border-white/10'}`}>
                  <p className="font-semibold flex items-center gap-1.5">
                    {a.tipo === 'video' || /^video\//.test(a.mime || '') ? <Film size={13} className="text-purple-500" /> : <ImageIcon size={13} className="text-sky-500" />}
                    {fecha(a.fecha)} · {a.titulo}
                  </p>
                  {a.notas && <p className="text-[11px] text-slate-500 truncate">{a.notas}</p>}
                  <div className="flex gap-3 mt-1">
                    <button onClick={() => setAbiertos(v => v.includes(a.id) ? v.filter(x => x !== a.id) : [...v, a.id])} className="flex items-center gap-1 text-indigo-600">
                      {abiertos.includes(a.id) ? <><EyeOff size={12} /> Ocultar</> : <><Eye size={12} /> Ver</>}
                    </button>
                    <label className="flex items-center gap-1">
                      <input type="checkbox" checked={comparar.includes(a.id)}
                        onChange={e => { setAnalisis({}); setComparar(v => e.target.checked ? [...v, a.id].slice(-2) : v.filter(x => x !== a.id)); }} />
                      Comparar
                    </label>
                  </div>
                  {abiertos.includes(a.id) && <iframe src={vistaDrive(a)} className="w-full aspect-video mt-2 rounded-lg" allow="autoplay" />}
                </div>
              ))}
            </div>
          </>
        )}
      </Tarjeta>

      {seleccion.length > 0 && (
        <Tarjeta titulo={seleccion.length === 2 ? `Comparación ${fecha(seleccion[0].fecha)} → ${fecha(seleccion[1].fecha)}` : `Estudio ${fecha(seleccion[0].fecha)}`}>
          <div className={`grid gap-3 ${seleccion.length === 2 ? 'md:grid-cols-2' : ''}`}>
            {seleccion.map((a: any) => {
              const ev = masCercano(evals, a.fecha), ac = masCercano(acus, a.fecha);
              const inf = masCercano(d.informes_orl, a.fecha);
              return (
                <div key={a.id} className="space-y-2">
                  <iframe src={vistaDrive(a)} className="w-full aspect-video rounded-lg border border-slate-200 dark:border-white/10" allow="autoplay" />
                  <div className="text-[11px] text-slate-700 dark:text-slate-200 space-y-0.5">
                    <p><b>{a.titulo}</b> · {fecha(a.fecha)}</p>
                    {inf && <p>ORL más cercano ({inf.fecha_informe || fecha(inf.fecha)}): {inf.diagnostico_principal || '—'}</p>}
                    {ev && <p>Evaluación más cercana ({fecha(ev.fecha)}): VHI-10 {fmt(ev.vhi10_score, 0)} · riesgo {fmt(ev.riesgo_vocal_score, 0)} · {ev.grbas ? `G${ev.grbas.G ?? '–'}` : ''}</p>}
                    {ac && <p>Acústica más cercana ({fecha(ac.fecha)}): F0 {fmt(ac.f0_mean, 0)} Hz · HNR {fmt(ac.hnr_db)} · CPPS {fmt(ac.cpps_db)} · AVQI {fmt(ac.avqi, 2)}</p>}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 dark:border-white/5">
            <button onClick={analizar} disabled={analisis.cargando}
              className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50">
              {analisis.cargando ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {seleccion.length === 2 ? 'Análisis automático de la evolución (orientativo)' : 'Análisis automático del estudio (orientativo)'}
            </button>
            {analisis.error && <p className="mt-2 text-xs text-red-600 flex gap-1.5"><AlertTriangle size={13} />{analisis.error}</p>}
            {analisis.texto && (
              <div className="mt-3 p-3 rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-xs text-slate-800 dark:text-slate-200 whitespace-pre-wrap">
                {analisis.texto}
              </div>
            )}
          </div>
        </Tarjeta>
      )}

      <Tarjeta titulo={`Sala virtual: sesiones en vivo (${(d.sala_virtual || []).length})`}>
        {(d.sala_virtual || []).length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-[10px] uppercase text-slate-500 text-left">
                <th className={th}>Fecha</th><th className={th}>Modo</th><th className={th}>Objetivo</th><th className={th}>F0 mediana</th>
                <th className={th}>Rango p5–p95</th><th className={th}>En objetivo</th><th className={th}>TMF</th><th className={th}>Consigna / notas</th></tr></thead>
              <tbody>
                {d.sala_virtual.map((x: any) => {
                  const r = x.resultados || {};
                  return (
                    <tr key={x.id} className="border-t border-slate-100 dark:border-white/5 align-top">
                      <td className={td}>{fechaHora(x.creada_at)}</td>
                      <td className={td}>{({ habla: 'Habla', nota: 'Nota sostenida', canto: 'Canto', tmf: 'TMF' } as any)[x.modo] || x.modo}</td>
                      <td className={td}>{x.objetivo?.hz ? `${x.objetivo.nota || ''} ${fmt(x.objetivo.hz, 0)} Hz ±${fmt(x.objetivo.tolerancia_cents, 0)}¢` : '—'}</td>
                      <td className={td}>{r.mediana_hz != null ? `${fmt(r.mediana_hz, 0)} Hz` : '—'}</td>
                      <td className={td}>{r.p5_hz != null ? `${fmt(r.p5_hz, 0)}–${fmt(r.p95_hz, 0)} Hz` : '—'}</td>
                      <td className={td}>{r.en_objetivo_pct != null ? `${r.en_objetivo_pct} %` : '—'}</td>
                      <td className={td}>{x.modo === 'tmf' && r.tmf_s != null ? `${fmt(r.tmf_s)} s` : '—'}</td>
                      <td className={td}>{[x.consigna, x.notas].filter(Boolean).join(' · ') || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="text-[10px] text-slate-500 mt-1">Medido en el equipo del paciente durante la videollamada. Solo las sesiones de Habla suman a la F0 conversacional.</p>
          </div>
        ) : <p className="text-xs text-slate-500">Sin sesiones guardadas desde la sala virtual.</p>}
      </Tarjeta>

      {(d.notas_turnos || []).length > 0 && (
        <Tarjeta titulo="Notas de las sesiones">
          <ul className="text-xs space-y-1.5">
            {d.notas_turnos.map((t: any, i: number) => (
              <li key={i}><b>{fechaHora(t.fecha_hora)}</b> <span className="text-slate-500">({t.tipo || 'turno'}{t.estado ? `, ${t.estado}` : ''})</span>
                <span className="block whitespace-pre-line text-slate-700 dark:text-slate-300">{t.notas}</span></li>
            ))}
          </ul>
        </Tarjeta>
      )}

      <Tarjeta titulo="Práctica guiada en casa">
        <PanelPractica pacienteId={pacienteId} />
      </Tarjeta>

      {d.lectura && <LecturaClinica l={d.lectura} aps={d.autopercepciones || []} />}

      <Tarjeta titulo="Orientación clínica integral">
        <OrientacionClinica pacienteId={pacienteId} situacion={d.situacion_quirurgica} paciente={p} />
      </Tarjeta>
    </div>
  );
}

const NIVEL: Record<string, string> = {
  normal: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300',
  leve: 'bg-lime-100 text-lime-800 dark:bg-lime-500/15 dark:text-lime-300',
  moderado: 'bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300',
  alterado: 'bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300',
  sin_dato: 'bg-slate-100 text-slate-700 dark:bg-white/10 dark:text-slate-300',
};
const NIVEL_TXT: Record<string, string> = { normal: 'Normal', leve: 'Leve', moderado: 'Moderado', alterado: 'Alterado', sin_dato: 'Sin referencia' };

/** Lectura por reglas clínicas fijas + indicación general redactada (verificada). */
function LecturaClinica({ l, aps }: { l: any; aps: any[] }) {
  const [refs, setRefs] = useState(false);
  return (
    <Tarjeta titulo="Lectura clínica integrada">
      <p className="text-[11px] text-slate-500 mb-2">
        Cada valor se muestra tal como está guardado, con su fecha y su origen; la lectura sale de criterios de referencia fijos.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full">
          <tbody>
            {l.hallazgos.map((h: any, i: number) => (
              <tr key={i} className="border-t border-slate-100 dark:border-white/5 align-top">
                <td className="px-2 py-1.5 text-[10px] uppercase font-bold text-slate-500 whitespace-nowrap">{h.area}</td>
                <td className="px-2 py-1.5 text-xs font-semibold text-slate-800 dark:text-slate-100">{h.parametro}</td>
                <td className="px-2 py-1.5 text-xs text-slate-800 dark:text-slate-200">{h.lectura}
                  <span className="block text-[10px] text-slate-500">{h.fuente}{h.fecha ? ` · ${fecha(h.fecha)}` : ''}</span></td>
                <td className="px-2 py-1.5"><span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${NIVEL[h.nivel] || NIVEL.sin_dato}`}>{NIVEL_TXT[h.nivel] || h.nivel}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {aps.length > 1 && (
        <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-2">
          <b>Autopercepción registrada:</b> {aps.map((a: any) => `${a.valor}/10 (${a.fuente}, ${fecha(a.fecha)})`).join(' · ')}
        </p>
      )}
      {l.alertas.map((a: string, i: number) => (
        <p key={i} className="mt-2 text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} className="shrink-0 mt-0.5" />{a}</p>
      ))}
      {l.patrones.length > 0 && (
        <div className="mt-3 space-y-2">
          {l.patrones.map((p: any, i: number) => (
            <div key={i} className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/20 text-xs">
              <p className="font-bold text-indigo-900 dark:text-indigo-200">{p.patron}</p>
              <p className="text-indigo-800 dark:text-indigo-300">Datos: {p.evidencia.join(' · ')}</p>
              <p className="text-slate-600 dark:text-slate-300">{p.sugerencia}</p>
            </div>
          ))}
        </div>
      )}
      {l.faltan.length > 0 && <p className="mt-2 text-xs text-slate-500">Sin datos de: {l.faltan.join(', ')}.</p>}
      <button onClick={() => setRefs(v => !v)} className="mt-2 text-[11px] text-indigo-600">{refs ? 'Ocultar' : 'Ver'} valores de referencia usados</button>
      {refs && (
        <ul className="mt-1 text-[11px] text-slate-500 list-disc pl-4">
          {Object.values(l.referencias).map((r: any, i: number) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </Tarjeta>
  );
}
