import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Video, Copy, MessageCircle, Wifi, WifiOff, Volume2, Save, X, Send, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useClinical } from '../ClinicalContext';
import { tokenSesion } from '../../utils/authFetch';
import CurvaTono, { Muestra } from './CurvaTono';
import { cents, hzAMidi, midiAHz, nombreNota, notasObjetivo, urlWs } from '../../utils/pitch';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const MODOS: Record<string, string> = {
  habla: 'Habla (F0 conversacional)', nota: 'Nota sostenida / afinación',
  canto: 'Canto (rango amplio)', tmf: 'Tiempo máximo de fonación',
};

/**
 * Sala virtual: ver en vivo la voz del paciente o alumno durante Meet/Zoom.
 * El paciente abre un enlace sin cuenta; su equipo mide la voz con el
 * micrófono sin filtros y la manda acá. Se puede fijar una nota objetivo,
 * hacerla sonar, enviar consignas y guardar la medición en la historia.
 */
export default function SalaVirtualModule() {
  const clinical = useClinical();
  const paciente = clinical.data.paciente;
  const [modo, setModo] = useState('habla');
  const [sala, setSala] = useState<any | null>(null);
  const [error, setError] = useState('');
  const [conectado, setConectado] = useState(false);
  const [muestras, setMuestras] = useState<Muestra[]>([]);
  const [objetivoMidi, setObjetivoMidi] = useState<number | ''>('');
  const [tolerancia, setTolerancia] = useState(50);
  const [consigna, setConsigna] = useState('');
  const [copiado, setCopiado] = useState(false);
  const [guardado, setGuardado] = useState<{ ok: boolean; t: string } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const inicioRef = useRef<number>(0);
  const [abiertas, setAbiertas] = useState<any[]>([]);
  const [notas, setNotas] = useState('');

  // Salas abiertas (también las que se crean desde el asistente de Telegram).
  const cargarAbiertas = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/salas`);
      if (r.ok) setAbiertas((await r.json()).salas || []);
    } catch { /* sin conexión: no se listan */ }
  };
  useEffect(() => { if (!sala) cargarAbiertas(); }, [sala]);
  const retomar = (s: any) => {
    setError(''); setGuardado(null); setMuestras([]);
    setModo(s.modo); setSala(s); inicioRef.current = s.creada * 1000;
  };
  // El paciente de la sala manda; si no tiene, el elegido en «Pacientes».
  const pacienteId = sala?.paciente_id || paciente?.id || '';
  const pacienteNombre = sala?.nombre && sala?.paciente_id ? sala.nombre : (paciente?.nombre_completo || '');

  const crear = async () => {
    setError(''); setGuardado(null);
    try {
      const r = await fetch(`${BACKEND_URL}/api/salas`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paciente_id: paciente?.id || null, nombre: paciente?.nombre_completo || '', modo }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setSala(d); setMuestras([]); inicioRef.current = Date.now();
    } catch (e: any) {
      setError(e?.message || 'No se pudo crear la sala');
    }
  };

  // Conexión en vivo (con reconexión) mientras la sala esté abierta.
  useEffect(() => {
    if (!sala) return;
    let cerrado = false;
    let espera = 1000;
    const conectar = () => {
      const ws = new WebSocket(urlWs(BACKEND_URL, `/ws/sala/${sala.token}/profesional?sesion=${encodeURIComponent(tokenSesion())}`));
      wsRef.current = ws;
      ws.onopen = () => { espera = 1000; };
      ws.onmessage = ev => {
        const m = JSON.parse(ev.data);
        if (m.tipo === 'estado') {
          setConectado(Boolean(m.paciente_conectado));
          if (m.historial?.length) setMuestras(prev => (prev.length ? prev : m.historial));
        }
        if (m.tipo === 'muestras') setMuestras(prev => [...prev, ...m.datos].slice(-6000));
        if (m.tipo === 'error') { setError(m.texto); cerrado = true; }
      };
      ws.onclose = () => { if (!cerrado) { setTimeout(conectar, espera); espera = Math.min(espera * 2, 10000); } };
    };
    conectar();
    return () => { cerrado = true; wsRef.current?.close(); };
  }, [sala]);

  const enviar = (msg: any) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  };

  const fijarObjetivo = (midi: number | '', tol = tolerancia) => {
    setObjetivoMidi(midi);
    enviar({ tipo: 'objetivo', objetivo: midi === '' ? null
      : { hz: Math.round(midiAHz(midi) * 10) / 10, nota: nombreNota(midi), tolerancia_cents: tol } });
  };

  const tocarNota = () => {
    if (objetivoMidi === '') return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.value = midiAHz(objetivoMidi);
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.05);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 2);
    osc.connect(g).connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + 2.05);
    setTimeout(() => ctx.close(), 2300);
  };

  const conVoz = useMemo(() => muestras.filter(m => m.f0) as { t: number; f0: number }[], [muestras]);
  const ultima = muestras.length ? muestras[muestras.length - 1] : null;
  const actual = ultima && Date.now() - ultima.t < 3000 ? ultima.f0 : null;
  const objHz = objetivoMidi === '' ? null : midiAHz(objetivoMidi);

  const stats = useMemo(() => {
    if (!conVoz.length) return null;
    const v = conVoz.map(m => m.f0).sort((a, b) => a - b);
    const q = (p: number) => v[Math.min(v.length - 1, Math.round(p * (v.length - 1)))];
    const enObj = objHz ? conVoz.filter(m => Math.abs(cents(m.f0, objHz)) <= tolerancia).length / conVoz.length : null;
    // TMF: tramo más largo con voz continua (cortes < 300 ms).
    let mejor = 0, inicio = 0, previo = 0;
    for (const m of muestras) {
      if (m.f0) { if (!inicio || m.t - previo > 300) inicio = m.t; previo = m.t; mejor = Math.max(mejor, m.t - inicio); }
    }
    return { mediana: q(0.5), p5: q(0.05), p95: q(0.95), min: v[0], max: v[v.length - 1], enObj, tmf: mejor / 1000, n: v.length };
  }, [conVoz, muestras, objHz, tolerancia]);

  const guardar = async () => {
    if (!stats || !pacienteId || !sala) return;
    setGuardado(null);
    const st = conVoz.map(m => 12 * Math.log2(m.f0 / stats.mediana));
    const media = st.reduce((a, b) => a + b, 0) / st.length;
    const sd = Math.sqrt(st.reduce((a, b) => a + (b - media) ** 2, 0) / st.length);
    const paso = Math.max(1, Math.ceil(conVoz.length / 600));
    const modoSala = sala.modo || modo;
    try {
      const r = await fetch(`${BACKEND_URL}/api/sala-sesiones`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paciente_id: pacienteId, modo: modoSala, consigna, notas,
          duracion_s: (Date.now() - inicioRef.current) / 1000,
          objetivo: objHz ? { hz: Math.round(objHz * 10) / 10, nota: nombreNota(Number(objetivoMidi)), tolerancia_cents: tolerancia } : null,
          media_hz: conVoz.reduce((a, m) => a + m.f0, 0) / conVoz.length,
          resultados: { mediana_hz: stats.mediana, p5_hz: stats.p5, p95_hz: stats.p95, min_hz: stats.min, max_hz: stats.max,
                        sd_st: Math.round(sd * 100) / 100, n: stats.n, tmf_s: Math.round(stats.tmf * 10) / 10,
                        en_objetivo_pct: stats.enObj != null ? Math.round(stats.enObj * 100) : null },
          contorno: conVoz.filter((_, i) => i % paso === 0).map(m => m.f0),
        }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      const que = modoSala === 'habla' ? `F0 mediana ${stats.mediana.toFixed(0)} Hz (suma a la evolución de F0 conversacional)`
        : modoSala === 'tmf' ? `TMF ${stats.tmf.toFixed(1)} s` : `mediana ${stats.mediana.toFixed(0)} Hz${stats.enObj != null ? ` · ${Math.round(stats.enObj * 100)} % en objetivo` : ''}`;
      setGuardado({ ok: !d.aviso, t: d.aviso || `Guardado en la ficha integral (Sala virtual): ${que}.` });
    } catch (e: any) {
      setGuardado({ ok: false, t: e?.message || 'No se pudo guardar' });
    }
  };

  const cerrar = () => {
    enviar({ tipo: 'cerrar' });
    setSala(null); setConectado(false);
  };

  const copiar = async () => {
    if (!sala) return;
    await navigator.clipboard.writeText(sala.enlace);
    setCopiado(true); setTimeout(() => setCopiado(false), 2000);
  };

  const telefono = (paciente?.telefono || '').replace(/\D/g, '');
  const textoWa = sala ? encodeURIComponent(
    `Hola${sala.nombre ? ` ${sala.nombre}` : ''}, para la sesión de hoy abrí este enlace, tocá «Activar micrófono» y dejalo abierto mientras hablamos por videollamada: ${sala.enlace}`) : '';
  const desvio = actual && objHz ? cents(actual, objHz) : null;
  const campo = 'px-3 py-2 border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 rounded-xl text-xs';

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-slate-200 dark:border-white/10 p-5">
        <h2 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Video size={18} className="text-indigo-500" /> Sala virtual {pacienteNombre ? `· ${pacienteNombre}` : ''}
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Usala junto a Meet o Zoom: el paciente abre un enlace, su equipo mide la voz con el micrófono sin filtros y
          acá la ves en vivo. Elegí antes el paciente en «Pacientes» para poder guardar la medición en su historia.
        </p>
        {!sala && abiertas.length > 0 && (
          <div className="mt-4 space-y-1.5">
            <p className="text-xs font-bold text-slate-700 dark:text-slate-200">Salas abiertas</p>
            {abiertas.map(a => (
              <div key={a.token} className="flex flex-wrap items-center gap-2 text-xs rounded-xl border border-slate-200 dark:border-white/10 px-3 py-2">
                <span className="font-semibold">{a.nombre || 'Sin paciente'}</span>
                <span className="text-slate-500">{MODOS[a.modo]?.split(' (')[0]} · abierta {new Date(a.creada * 1000).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}</span>
                <span className={a.paciente_conectado ? 'text-emerald-600 font-bold' : 'text-amber-600'}>{a.paciente_conectado ? 'paciente conectado' : 'esperando'}</span>
                <button onClick={() => retomar(a)} className="ml-auto px-3 py-1 rounded-lg bg-indigo-600 text-white font-bold">Retomar</button>
              </div>
            ))}
          </div>
        )}
        {!sala ? (
          <div className="flex flex-wrap items-center gap-2 mt-4">
            <select value={modo} onChange={e => setModo(e.target.value)} className={campo}>
              {Object.entries(MODOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <button onClick={crear} className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold">
              Crear sala y enlace
            </button>
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            <p className="text-xs font-mono bg-slate-100 dark:bg-white/5 rounded-lg px-3 py-2 break-all">{sala.enlace}</p>
            <div className="flex flex-wrap gap-2">
              <button onClick={copiar} className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-white/10 text-xs font-bold flex items-center gap-1.5">
                <Copy size={13} /> {copiado ? 'Copiado' : 'Copiar enlace'}
              </button>
              <a href={telefono ? `https://wa.me/${telefono}?text=${textoWa}` : `https://wa.me/?text=${textoWa}`} target="_blank" rel="noreferrer"
                className="px-3 py-1.5 rounded-lg border border-emerald-300 text-emerald-700 dark:text-emerald-300 text-xs font-bold flex items-center gap-1.5">
                <MessageCircle size={13} /> Enviar por WhatsApp
              </a>
              <span className={`text-xs font-bold flex items-center gap-1 ${conectado ? 'text-emerald-600' : 'text-amber-600'}`}>
                {conectado ? <><Wifi size={13} /> Paciente conectado</> : <><WifiOff size={13} /> Esperando al paciente…</>}
              </span>
              <button onClick={cerrar} className="ml-auto px-3 py-1.5 rounded-lg text-xs font-bold text-red-600 flex items-center gap-1"><X size={13} /> Cerrar sala</button>
            </div>
          </div>
        )}
        {error && <p className="mt-2 text-xs text-red-600 flex gap-1.5"><AlertTriangle size={13} />{error}</p>}
      </div>

      {sala && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            <CurvaTono muestras={muestras} objetivoHz={objHz} toleranciaCents={tolerancia} alto={300} />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              {[
                ['Ahora', actual ? `${nombreNota(hzAMidi(actual))} · ${actual.toFixed(0)} Hz` : '—'],
                ['Mediana', stats ? `${stats.mediana.toFixed(0)} Hz (${nombreNota(hzAMidi(stats.mediana))})` : '—'],
                ['Rango p5–p95', stats ? `${stats.p5.toFixed(0)}–${stats.p95.toFixed(0)} Hz` : '—'],
                [sala.modo === 'tmf' ? 'TMF (mejor)' : 'En objetivo', sala.modo === 'tmf'
                  ? (stats ? `${stats.tmf.toFixed(1)} s` : '—')
                  : (stats?.enObj != null ? `${Math.round(stats.enObj * 100)} %` : '—')],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-white/80 dark:bg-white/5 border border-slate-200 dark:border-white/10 p-3">
                  <p className="text-[10px] uppercase font-bold text-slate-500">{k}</p>
                  <p className="text-sm font-black text-slate-900 dark:text-white">{v}</p>
                </div>
              ))}
            </div>
            {desvio != null && (
              <p className={`text-sm font-bold text-center ${Math.abs(desvio) <= tolerancia ? 'text-emerald-600' : 'text-amber-600'}`}>
                {Math.abs(desvio) <= tolerancia ? 'Afinado' : desvio > 0 ? `Alto (+${desvio.toFixed(0)} cents)` : `Bajo (${desvio.toFixed(0)} cents)`}
              </p>
            )}
          </div>

          <div className="space-y-3">
            <div className="rounded-2xl bg-white/80 dark:bg-white/5 border border-slate-200 dark:border-white/10 p-4 space-y-2">
              <p className="text-xs font-bold text-slate-700 dark:text-slate-200">Nota objetivo (la ve el paciente)</p>
              <select value={objetivoMidi} onChange={e => fijarObjetivo(e.target.value === '' ? '' : Number(e.target.value))} className={`${campo} w-full`}>
                <option value="">Sin objetivo</option>
                {notasObjetivo().map(n => <option key={n.midi} value={n.midi}>{n.nombre} · {n.hz} Hz</option>)}
              </select>
              <div className="flex items-center gap-2">
                <label className="text-[11px] text-slate-500">Tolerancia</label>
                <select value={tolerancia} onChange={e => { const t = Number(e.target.value); setTolerancia(t); if (objetivoMidi !== '') fijarObjetivo(objetivoMidi, t); }} className={campo}>
                  {[25, 50, 100].map(t => <option key={t} value={t}>±{t} cents</option>)}
                </select>
                <button onClick={tocarNota} disabled={objetivoMidi === ''} className="ml-auto px-3 py-1.5 rounded-lg border border-slate-300 dark:border-white/10 text-xs font-bold flex items-center gap-1 disabled:opacity-40">
                  <Volume2 size={13} /> Escuchar
                </button>
              </div>
              <p className="text-[10px] text-slate-400">«Escuchar» suena en tu equipo: si compartís el audio en la videollamada, el paciente también la oye.</p>
            </div>

            <div className="rounded-2xl bg-white/80 dark:bg-white/5 border border-slate-200 dark:border-white/10 p-4 space-y-2">
              <p className="text-xs font-bold text-slate-700 dark:text-slate-200">Modo y consigna</p>
              <select value={sala.modo} onChange={e => { setSala({ ...sala, modo: e.target.value }); setModo(e.target.value); enviar({ tipo: 'modo', modo: e.target.value }); }} className={`${campo} w-full`}>
                {Object.entries(MODOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <div className="flex gap-2">
                <input value={consigna} onChange={e => setConsigna(e.target.value)} placeholder="Ej.: sostené una /u/ cómoda" className={`${campo} flex-1`}
                  onKeyDown={e => { if (e.key === 'Enter') enviar({ tipo: 'consigna', texto: consigna }); }} />
                <button onClick={() => enviar({ tipo: 'consigna', texto: consigna })} className="px-3 rounded-lg bg-indigo-600 text-white"><Send size={13} /></button>
              </div>
            </div>

            <div className="rounded-2xl bg-white/80 dark:bg-white/5 border border-slate-200 dark:border-white/10 p-4 space-y-2">
              <textarea value={notas} onChange={e => setNotas(e.target.value)} rows={2} placeholder="Observaciones de la sesión (opcional)"
                className={`${campo} w-full`} />
              <button onClick={guardar} disabled={!stats || !pacienteId}
                className="w-full px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 disabled:opacity-40">
                <Save size={13} /> Guardar en la ficha {pacienteNombre ? `de ${pacienteNombre}` : ''}
              </button>
              {!pacienteId && <p className="text-[11px] text-slate-500">Elegí el paciente en «Pacientes» para poder guardar.</p>}
              <p className="text-[10px] text-slate-500">Queda en la Ficha integral → «Sala virtual». Solo el modo Habla suma a la F0 conversacional.</p>
              <button onClick={() => { setMuestras([]); setGuardado(null); inicioRef.current = Date.now(); }} className="w-full text-[11px] text-slate-500 underline">Empezar medición de nuevo</button>
              {guardado && (
                <p className={`text-xs flex gap-1.5 ${guardado.ok ? 'text-emerald-600' : 'text-red-600'}`}>
                  {guardado.ok ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />} {guardado.t}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
