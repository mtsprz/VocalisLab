import React, { useState, useEffect } from 'react';
import { Mic, Play, Activity, GitBranch, Scale, FileText, CheckCircle2, XCircle,
  Download, Smartphone, Trash2, Loader2, AlertCircle, HardDrive,
  ChevronDown, ChevronUp, RefreshCw, KeyRound } from 'lucide-react';
import { useClinical } from './ClinicalContext';
import { useAuth } from './AuthContext';
import { elegirRangoNormativo, notaEs } from './vozNormas';

/** Nota entre paréntesis para la mediana (solo presentación). */
const notaMusical = (hz?: number | null) => (notaEs(hz) ? `(${notaEs(hz)})` : '');

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
}

const TASK_LABEL: Record<string, string> = {
  vocal_sostenida_a: 'Vocal sostenida /a/',
  conteo: 'Conteo',
  lectura: 'Lectura',
  conversacion_espontanea: 'Conversación espontánea',
};

const fmtDb = (v: any) => (v === null || v === undefined ? '—' : Number(v).toFixed(1));
const fmtHz = (v: any) => (v === null || v === undefined ? '—' : Number(v).toFixed(0));

function edadDe(fechaNac: string): number | null {
  try {
    if (!fechaNac) return null;
    const d = new Date(fechaNac.slice(0, 10));
    const h = new Date();
    let e = h.getFullYear() - d.getFullYear();
    if (h.getMonth() < d.getMonth() || (h.getMonth() === d.getMonth() && h.getDate() < d.getDate())) e--;
    return e;
  } catch { return null; }
}

function LineChart({ puntos, refMin, refMax, unidad, color }: any) {
  const W = 560, H = 190, P = 34;
  const vals = puntos.map((p: any) => p.y).filter((v: any) => v !== null && v !== undefined);
  if (!vals.length) return <p className="text-xs text-gray-400">Sin datos.</p>;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (refMin != null) lo = Math.min(lo, refMin);
  if (refMax != null) hi = Math.max(hi, refMax);
  if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const X = (i: number) => P + (i * (W - 2 * P)) / Math.max(puntos.length - 1, 1);
  const Y = (v: number) => H - P - ((v - lo) / (hi - lo)) * (H - 2 * P);
  const base = vals[0];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-44 bg-white dark:bg-white/5 rounded-xl border border-gray-200 dark:border-white/10">
      {refMin != null && refMax != null && (
        <rect x={P} y={Y(refMax)} width={W - 2 * P} height={Math.max(Y(refMin) - Y(refMax), 2)} fill="#E0F2FE" opacity={0.8} />
      )}
      <line x1={P} y1={Y(base)} x2={W - P} y2={Y(base)} stroke="#0F172A" strokeDasharray="5 3" strokeWidth={1} />
      <polyline
        points={puntos.map((p: any, i: number) => (p.y == null ? '' : `${X(i)},${Y(p.y)}`)).filter(Boolean).join(' ')}
        fill="none" stroke={color} strokeWidth={2.2}
      />
      {puntos.map((p: any, i: number) => p.y == null ? null : (
        <g key={i}>
          <circle cx={X(i)} cy={Y(p.y)} r={3.5} fill={color} />
          <text x={X(i)} y={H - 8} fontSize={9} textAnchor="middle" fill="#64748B">S{p.x}</text>
        </g>
      ))}
      <text x={6} y={Y(hi) + 3} fontSize={9} fill="#64748B">{Number(hi).toFixed(1)}</text>
      <text x={6} y={Y(lo) + 3} fontSize={9} fill="#64748B">{Number(lo).toFixed(1)}</text>
      <text x={W - P} y={16} fontSize={9} fill="#64748B">{unidad}</text>
    </svg>
  );
}

function Histograma({ hist, refMin, refMax }: any) {
  const bins = hist?.bins || {};
  const ref = Number(hist?.ref_hz) || 0;
  const keys = Object.keys(bins).map(Number).sort((a, b) => a - b);
  if (!keys.length || !ref) return <p className="text-xs text-gray-400">Sin histograma.</p>;
  const max = Math.max(...keys.map(k => bins[String(k)]));
  const W = 560, H = 150, P = 30;
  const bw = (W - 2 * P) / keys.length;
  const hzOf = (st: number) => ref * Math.pow(2, st / 12);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36 bg-white dark:bg-white/5 rounded-xl border border-gray-200 dark:border-white/10">
      {keys.map(k => {
        const lo = hzOf(k - 0.5), hi = hzOf(k + 0.5);
        const dentro = refMin != null && refMax != null && hi >= refMin && lo <= refMax;
        const h = (bins[String(k)] / max) * (H - 2 * P - 14);
        return (
          <rect key={k} x={P + keys.indexOf(k) * bw + 1} y={H - P - h} width={Math.max(bw - 2, 1)}
            height={h} fill={dentro ? '#0284C7' : '#CBD5E1'} rx={1} />
        );
      })}
      <text x={P} y={H - 8} fontSize={9} fill="#64748B">{fmtHz(hzOf(keys[0] - 0.5))} Hz</text>
      <text x={W - P} y={H - 8} fontSize={9} textAnchor="end" fill="#64748B">{fmtHz(hzOf(keys[keys.length - 1] + 0.5))} Hz</text>
      <text x={W - P} y={16} fontSize={9} fill="#64748B">azul = dentro de referencia</text>
    </svg>
  );
}

export default function SesionesVozModule({ pacienteId }: Props) {
  const clinical = useClinical();
  const { user } = useAuth();
  const uid = user?.id || '';
  const [sesiones, setSesiones] = useState<any[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<any>(null);
  const [cargando, setCargando] = useState(false);
  const [audioUrl, setAudioUrl] = useState('');
  const [rango, setRango] = useState<any>(null);
  const [progreso, setProgreso] = useState<any[]>([]);
  const [draftEdit, setDraftEdit] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [expandTr, setExpandTr] = useState(false);
  const [cmpA, setCmpA] = useState<string>('');
  const [cmpB, setCmpB] = useState<string>('');
  const [cmpDatos, setCmpDatos] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [pairCode, setPairCode] = useState('');
  const [alm, setAlm] = useState<any>(null);
  const [refEdit, setRefEdit] = useState({ sexo_referencia: '', f0_ref_min_hz: '', f0_ref_max_hz: '' });

  const paciente = clinical.data.paciente || {};
  const edad = edadDe(paciente.fecha_nacimiento || '');

  const cargarSesiones = async () => {
    if (!pacienteId || !uid) return;
    setCargando(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/companion/sessions?patient_id=${pacienteId}&user_id=${uid}`);
      const d = await r.json();
      if (d.ok) {
        setSesiones(d.sessions || []);
        if (!selId && d.sessions?.length) setSelId(d.sessions[0].id);
      }
    } catch {}
    setCargando(false);
  };

  const cargarAux = async () => {
    if (!pacienteId || !uid) return;
    try {
      const rr = await fetch(`${BACKEND_URL}/api/companion/referencias?user_id=${uid}`);
      const dr = await rr.json();
      if (dr.ok) {
        setRango(elegirRangoNormativo(dr.rangos || [], paciente.sexo_referencia || paciente.sexo || '', edad));
      }
    } catch {}
    try {
      const rp = await fetch(`${BACKEND_URL}/api/companion/progreso?patient_id=${pacienteId}&user_id=${uid}`);
      const dp = await rp.json();
      if (dp.ok) setProgreso(dp.serie || []);
    } catch {}
    try {
      const ra = await fetch(`${BACKEND_URL}/api/companion/almacenamiento?user_id=${uid}`);
      setAlm(await ra.json());
    } catch {}
    try {
      const rd = await fetch(`${BACKEND_URL}/api/companion/devices?user_id=${uid}`);
      const dd = await rd.json();
      if (dd.ok) setDevices(dd.devices || []);
    } catch {}
  };

  useEffect(() => { cargarSesiones(); cargarAux(); }, [pacienteId, uid]);
  useEffect(() => {
    if (!selId || !uid) return;
    (async () => {
      const r = await fetch(`${BACKEND_URL}/api/companion/sessions/${selId}?user_id=${uid}`);
      const d = await r.json();
      if (d.ok) {
        setDetalle(d);
        setDraftEdit(d.borrador ? { ...d.borrador } : null);
        setAudioUrl('');
      }
    })();
  }, [selId]);

  useEffect(() => {
    if (!cmpA || !cmpB || !uid) return;
    (async () => {
      const out = [];
      for (const id of [cmpA, cmpB]) {
        const r = await fetch(`${BACKEND_URL}/api/companion/sessions/${id}?user_id=${uid}`);
        out.push(await r.json());
      }
      setCmpDatos(out);
    })();
  }, [cmpA, cmpB]);

  const pedirAudio = async (clipId?: string) => {
    if (!selId) return;
    const q = `?user_id=${uid}` + (clipId ? `&clip=${clipId}` : '');
    const r = await fetch(`${BACKEND_URL}/api/companion/sessions/${selId}/audio-url${q}`);
    const d = await r.json();
    if (d.ok) setAudioUrl(d.url);
    else setMsg(`Audio no disponible: ${d.detail || d.error || r.status}`);
  };

  const guardarBorrador = async (aprobar: boolean) => {
    if (!selId || !draftEdit) return;
    const base = `${BACKEND_URL}/api/companion/anamnesis-drafts/${selId}`;
    if (aprobar) {
      if (!confirm('¿Volcar el borrador a la ficha de anamnesis vigente?')) return;
      const r = await fetch(`${base}/aprobar`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: uid }) });
      const d = await r.json();
      setMsg(d.ok ? 'Borrador aprobado y volcado a la ficha ✓' : `Error: ${d.detail || d.error}`);
    } else {
      const r = await fetch(base, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: uid, ...draftEdit }) });
      const d = await r.json();
      setMsg(d.ok ? 'Borrador guardado ✓' : `Error: ${d.detail || d.error}`);
    }
    const rd = await fetch(`${BACKEND_URL}/api/companion/sessions/${selId}?user_id=${uid}`);
    const dd = await rd.json();
    if (dd.ok) { setDetalle(dd); setDraftEdit(dd.borrador ? { ...dd.borrador } : null); }
  };

  const descartarBorrador = async () => {
    if (!selId || !confirm('¿Descartar el borrador?')) return;
    await fetch(`${BACKEND_URL}/api/companion/anamnesis-drafts/${selId}/descartar`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: uid }) });
    setDraftEdit(null);
    setMsg('Borrador descartado');
  };

  const descargarPDF = async (tipo: 'sesion' | 'evolucion') => {
    const url = `${BACKEND_URL}/api/companion/informes/${tipo}`;
    const body: any = tipo === 'sesion' ? { user_id: uid, session_id: selId } : { user_id: uid, patient_id: pacienteId };
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) { setMsg('Error generando PDF'); return; }
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = tipo === 'sesion' ? `informe_sesion_${selId?.slice(0, 8)}.pdf` : `evolucion_voz.pdf`;
    a.click();
  };

  const generarCodigo = async () => {
    const r = await fetch(`${BACKEND_URL}/api/companion/pairing-code?user_id=${uid}`, { method: 'POST' });
    const d = await r.json();
    if (d.ok) setPairCode(d.code);
    else setMsg(d.detail || 'Error');
  };

  const revocar = async (id: string) => {
    if (!confirm('¿Revocar este dispositivo?')) return;
    await fetch(`${BACKEND_URL}/api/companion/devices/${id}?user_id=${uid}`, { method: 'DELETE' });
    cargarAux();
  };

  const guardarReferencia = async () => {
    if (!pacienteId) return;
    const r = await fetch(`${BACKEND_URL}/api/pacientes/${pacienteId}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sexo_referencia: refEdit.sexo_referencia || undefined,
        f0_ref_min_hz: refEdit.f0_ref_min_hz ? Number(refEdit.f0_ref_min_hz) : undefined,
        f0_ref_max_hz: refEdit.f0_ref_max_hz ? Number(refEdit.f0_ref_max_hz) : undefined,
      }),
    });
    if (r.ok) { setMsg('Referencia actualizada ✓'); clinical.cargarPaciente(pacienteId); }
    else setMsg('No se pudo guardar (¿migración aplicada?)');
  };

  // Semáforo F0 conversacional
  const conv = (detalle?.acustica || []).find((a: any) => a.task_type === 'conversacion_espontanea');
  const f0c = conv?.f0_median_hz;
  const rMin = paciente.f0_ref_min_hz || rango?.f0_min_hz;
  const rMax = paciente.f0_ref_max_hz || rango?.f0_max_hz;
  const semaforo = f0c == null || rMin == null || rMax == null
    ? { c: 'gray', t: 'Sin referencia' }
    : f0c < rMin ? { c: 'red', t: `Por debajo (${fmtHz(f0c)} < ${rMin})` }
    : f0c > rMax ? { c: 'red', t: `Por encima (${fmtHz(f0c)} > ${rMax})` }
    : { c: 'green', t: `Dentro de rango (${fmtHz(f0c)} Hz)` };
  const semaColor: any = { green: 'bg-emerald-500/10 border-emerald-500/40 text-emerald-700 dark:text-emerald-300', red: 'bg-red-500/10 border-red-500/40 text-red-700 dark:text-red-300', gray: 'bg-gray-500/10 border-gray-400/40 text-gray-500' };

  const serieConv = progreso.filter((p: any) => p.task_type === 'conversacion_espontanea');

  if (!pacienteId) return <p className="text-sm text-gray-500">Seleccioná un paciente.</p>;

  return (
    <div className="max-w-6xl mx-auto w-full space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-xl font-black text-gray-900 dark:text-white flex items-center gap-2">
          <Mic size={20} className="text-indigo-500" /> Voz y sesiones
        </h2>
        <div className="flex items-center gap-2 text-xs">
          {alm?.ok && (
            <span className="px-2.5 py-1.5 rounded-lg bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 flex items-center gap-1.5" title="Uso de almacenamiento Companion">
              <HardDrive size={13} /> {(alm.used_bytes / 1048576).toFixed(0)} / {(alm.quota_bytes / 1073741824).toFixed(1)} GB · {alm.sessions_count} sesiones
            </span>
          )}
          <button onClick={() => { cargarSesiones(); cargarAux(); }} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 font-bold flex items-center gap-1.5 hover:bg-gray-100 dark:hover:bg-white/5">
            <RefreshCw size={13} /> Actualizar
          </button>
          <button onClick={() => descargarPDF('evolucion')} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold flex items-center gap-1.5">
            <Download size={13} /> PDF evolución
          </button>
        </div>
      </div>
      {msg && <p className="text-xs p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 font-semibold">{msg}</p>}

      {/* Referencia aplicable */}
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200 dark:border-white/10 p-4">
        <h3 className="font-bold text-sm flex items-center gap-2 mb-2"><Scale size={15} className="text-indigo-500" /> Referencia de F0 ({paciente.sexo_referencia || paciente.sexo || '—'}{edad != null ? `, ${edad} años` : ''})</h3>
        <div className={`p-3 rounded-xl border text-xs font-bold ${semaColor[semaforo.c]}`}>
          Semáforo conversacional: {semaforo.t}
          <span className="block font-normal mt-1">Valores orientativos — requieren criterio clínico. {rMin && rMax ? `Rango: ${rMin}–${rMax} Hz.` : 'Sin rango aplicable (faltan sexo o fecha de nacimiento).'}
            {rango?.f0_promedio_min_hz != null && !paciente.f0_ref_min_hz && <> Promedio esperado: {rango.f0_promedio_min_hz === rango.f0_promedio_max_hz ? rango.f0_promedio_min_hz : `${rango.f0_promedio_min_hz}–${rango.f0_promedio_max_hz}`} Hz.</>}
            {rango?.fuente && !paciente.f0_ref_min_hz && <> Fuente: {rango.fuente}.</>}</span>
        </div>
        <div className="flex items-end gap-2 mt-3 flex-wrap text-xs">
          <div>
            <label className="font-semibold block mb-1">Sexo de referencia</label>
            <select value={refEdit.sexo_referencia} onChange={e => setRefEdit({ ...refEdit, sexo_referencia: e.target.value })} className="px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-white/5">
              <option value="">(igual que sexo)</option>
              <option value="masculino">Masculino</option>
              <option value="femenino">Femenino</option>
              <option value="ninex">Niñez</option>
            </select>
          </div>
          <div>
            <label className="font-semibold block mb-1">Override mín (Hz)</label>
            <input value={refEdit.f0_ref_min_hz} onChange={e => setRefEdit({ ...refEdit, f0_ref_min_hz: e.target.value })} placeholder={String(rMin || '')} className="w-24 px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-white/5" />
          </div>
          <div>
            <label className="font-semibold block mb-1">Override máx (Hz)</label>
            <input value={refEdit.f0_ref_max_hz} onChange={e => setRefEdit({ ...refEdit, f0_ref_max_hz: e.target.value })} placeholder={String(rMax || '')} className="w-24 px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-white/5" />
          </div>
          <button onClick={guardarReferencia} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold">Guardar</button>
        </div>
      </div>

      {/* Evolución */}
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200 dark:border-white/10 p-4">
        <h3 className="font-bold text-sm flex items-center gap-2 mb-3"><Activity size={15} className="text-indigo-500" /> Evolución sesión a sesión (línea punteada = sesión 1, banda = referencia)</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-bold mb-1">F0 mediana conversacional (Hz)</p>
            <LineChart puntos={serieConv.map((p: any) => ({ x: p.session_number, y: p.f0_median_hz }))} refMin={rMin} refMax={rMax} unidad="Hz" color="#0284C7" />
          </div>
          <div>
            <p className="text-xs font-bold mb-1">Variabilidad de F0 (SD en semitonos)</p>
            <LineChart puntos={serieConv.map((p: any) => ({ x: p.session_number, y: p.f0_sd_semitones }))} unidad="st" color="#7C3AED" />
          </div>
        </div>
        {/* Comparador */}
        <div className="mt-4 pt-3 border-t border-gray-200 dark:border-white/10">
          <p className="text-xs font-bold mb-2 flex items-center gap-1.5"><GitBranch size={13} /> Comparador lado a lado</p>
          <div className="flex gap-2 mb-2 text-xs">
            {[['A', cmpA, setCmpA], ['B', cmpB, setCmpB]].map(([l, v, set]: any) => (
              <select key={l} value={v} onChange={e => set(e.target.value)} className="px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-white/5">
                <option value="">Sesión {l}…</option>
                {sesiones.map(s => <option key={s.id} value={s.id}>{(s.recorded_at || '').slice(0, 10)} · {s.status}</option>)}
              </select>
            ))}
          </div>
          {cmpDatos.length === 2 && cmpDatos[0].ok && cmpDatos[1].ok && (
            <div className="grid grid-cols-2 gap-3 text-xs">
              {cmpDatos.map((d: any, i: number) => (
                <div key={i} className="p-3 rounded-xl border border-gray-200 dark:border-white/10">
                  <p className="font-bold mb-1">Sesión {i === 0 ? 'A' : 'B'} · {(d.sesion.recorded_at || '').slice(0, 10)}</p>
                  {(d.acustica || []).map((a: any) => (
                    <p key={a.task_type} className="mt-1">
                      <span className="font-semibold">{TASK_LABEL[a.task_type] || a.task_type}:</span> F0 {fmtHz(a.f0_median_hz)} Hz {notaMusical(a.f0_median_hz)} · rango {fmtHz(a.f0_p5_hz)}–{fmtHz(a.f0_p95_hz)} Hz · SD {fmtDb(a.f0_sd_semitones)} st
                      {!a.validada && <span className="text-amber-600 font-bold"> (no validada)</span>}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Sesiones */}
      <div className="space-y-3">
        {cargando && <p className="text-xs text-gray-400 flex items-center gap-2"><Loader2 size={13} className="animate-spin" /> Cargando…</p>}
        {!cargando && sesiones.length === 0 && <p className="text-xs text-gray-400">Sin sesiones sincronizadas para este paciente.</p>}
        {sesiones.map(s => {
          const abierta = selId === s.id;
          return (
            <div key={s.id} className="bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200 dark:border-white/10 overflow-hidden">
              <button onClick={() => setSelId(abierta ? null : s.id)} className="w-full px-4 py-3 flex items-center gap-3 text-left">
                <span className="px-2 py-1 rounded-lg text-[10px] font-black bg-teal-500/10 text-teal-700 dark:text-teal-300 border border-teal-500/30">Grabada offline / sincronizada</span>
                <span className="text-xs font-bold">{(s.recorded_at || '').slice(0, 16).replace('T', ' ')}</span>
                <span className="text-[11px] text-gray-500">{s.audio_duration_sec ? `${Math.round(s.audio_duration_sec / 60)} min · ` : ''}{s.audio_codec || ''} {s.audio_bitrate_kbps ? `${s.audio_bitrate_kbps} kbps` : ''}</span>
                <span className={`px-2 py-0.5 rounded-lg text-[10px] font-black border ${s.status === 'processed' ? 'bg-emerald-500/10 text-emerald-700 border-emerald-500/30' : s.status === 'error' ? 'bg-red-500/10 text-red-600 border-red-500/30' : 'bg-amber-500/10 text-amber-700 border-amber-500/30'}`}>{s.status}</span>
                {!s.consent_recorded
                  ? <span className="px-2 py-0.5 rounded-lg text-[10px] font-black bg-red-500/10 text-red-600 border border-red-500/30 flex items-center gap-1"><AlertCircle size={11} /> Sin consentimiento</span>
                  : <span className="px-2 py-0.5 rounded-lg text-[10px] font-black bg-emerald-500/10 text-emerald-700 border border-emerald-500/30 flex items-center gap-1"><CheckCircle2 size={11} /> Consentido</span>}
                <span className="ml-auto text-gray-400">{abierta ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</span>
              </button>
              {abierta && detalle && detalle.sesion?.id === s.id && (
                <div className="px-4 pb-4 space-y-3 text-xs border-t border-gray-100 dark:border-white/5 pt-3">
                  {s.error_detail && <p className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-300 font-semibold">{s.error_detail}</p>}
                  <div className="flex items-center gap-2 flex-wrap">
                    <button onClick={() => pedirAudio()} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold flex items-center gap-1.5"><Play size={13} /> Reproducir audio</button>
                    <button onClick={() => descargarPDF('sesion')} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 font-bold flex items-center gap-1.5"><Download size={13} /> PDF sesión</button>
                  </div>
                  {audioUrl && <audio src={audioUrl} controls className="w-full" />}
                  {/* Métricas por tarea */}
                  {(detalle.acustica || []).map((a: any) => (
                    <div key={a.task_type} className="p-3 rounded-xl border border-gray-200 dark:border-white/10">
                      <p className="font-bold mb-1">{TASK_LABEL[a.task_type] || a.task_type}
                        {!a.validada && <span className="ml-2 text-amber-600">no validada</span>}</p>
                      <p className="text-base font-black">{fmtHz(a.f0_median_hz)} Hz <span className="text-indigo-600 dark:text-indigo-400">{notaMusical(a.f0_median_hz)}</span> <span className="text-xs font-normal text-gray-500">altura tonal del paciente (mediana)</span></p>
                      <p>Rango p5–p95 {fmtHz(a.f0_p5_hz)}–{fmtHz(a.f0_p95_hz)} Hz · media {fmtHz(a.f0_mean_hz)} Hz · SD {fmtDb(a.f0_sd_semitones)} st · voz {a.voiced_fraction != null ? `${Math.round(a.voiced_fraction * 100)}%` : '—'}</p>
                      <div className="mt-2">
                        <p className="font-semibold mb-1">Histograma F0 (estilo SpeechPitch)</p>
                        <Histograma hist={a.f0_histogram} refMin={rMin} refMax={rMax} />
                      </div>
                    </div>
                  ))}
                  {/* Transcripción */}
                  <div>
                    <button onClick={() => setExpandTr(v => !v)} className="font-bold flex items-center gap-1.5">
                      <FileText size={13} /> Transcripción ({(detalle.transcripciones || []).length}) {expandTr ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>
                    {expandTr && (
                      <div className="mt-2 space-y-1.5 max-h-64 overflow-y-auto">
                        {(detalle.transcripciones || []).map((t: any, i: number) => (
                          <p key={i} className="p-2 rounded-lg bg-gray-50 dark:bg-white/5">
                            <span className={`font-black ${t.speaker === 'fonoaudiologo' ? 'text-indigo-600 dark:text-indigo-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                              {t.speaker === 'fonoaudiologo' ? 'Fonoaudiólogo' : 'Paciente'}
                            </span>
                            <span className="text-gray-400"> [{Math.round(t.start_sec)}s]</span> {t.text}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                  {/* Borrador anamnesis */}
                  {detalle.borrador ? (
                    <div className="p-3 rounded-xl border border-amber-500/30 bg-amber-500/5">
                      <p className="font-bold mb-2">Borrador de anamnesis <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 dark:bg-white/10">{detalle.borrador.status}</span></p>
                      {draftEdit && (['motivo_consulta', 'sintomatologia_vocal', 'habitos_vocales', 'observaciones_clinicas', 'plan_sugerido'] as any).map((k: string) => (
                        <div key={k} className="mb-2">
                          <label className="font-semibold block mb-0.5 capitalize">{k.replace(/_/g, ' ')}</label>
                          <textarea value={draftEdit[k] || ''} onChange={e => setDraftEdit({ ...draftEdit, [k]: e.target.value })} rows={2} className="w-full px-2 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 bg-white dark:bg-white/5" />
                        </div>
                      ))}
                      <div className="flex gap-2">
                        <button onClick={() => guardarBorrador(false)} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-white/10 font-bold">Guardar edición</button>
                        <button onClick={() => guardarBorrador(true)} className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold flex items-center gap-1.5"><CheckCircle2 size={13} /> Aprobar → ficha</button>
                        <button onClick={descartarBorrador} className="px-3 py-1.5 rounded-lg border border-red-300 text-red-600 font-bold flex items-center gap-1.5"><XCircle size={13} /> Descartar</button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-gray-400">Sin borrador de anamnesis para esta sesión.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Dispositivos */}
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200 dark:border-white/10 p-4 text-xs">
        <h3 className="font-bold text-sm flex items-center gap-2 mb-2"><Smartphone size={15} className="text-indigo-500" /> Dispositivos Companion</h3>
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <button onClick={generarCodigo} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold flex items-center gap-1.5"><KeyRound size={13} /> Generar código (10 min)</button>
          {pairCode && <span className="px-3 py-1.5 rounded-lg bg-gray-900 text-white font-mono font-black tracking-widest">Ingresar en la app: {pairCode}</span>}
        </div>
        {(devices || []).map((d: any) => (
          <div key={d.id} className="flex items-center gap-2 py-1.5 border-t border-gray-100 dark:border-white/5">
            <span className="font-bold">{d.device_name || 'Companion'}</span>
            <span className="text-gray-400">{(d.created_at || '').slice(0, 10)}{d.last_seen_at ? ` · visto ${(d.last_seen_at || '').slice(0, 10)}` : ''}</span>
            {d.revoked
              ? <span className="text-red-500 font-bold">revocado</span>
              : <button onClick={() => revocar(d.id)} className="ml-auto text-red-500 font-bold flex items-center gap-1"><Trash2 size={13} /> Revocar</button>}
          </div>
        ))}
      </div>
    </div>
  );
}
