import React, { useEffect, useRef, useState } from 'react';
import { yin, dbfs, nombreNota, hzAMidi, SuavizadorF0 } from '../../utils/pitch';
import {
  Ejercicio, duracion, objetivoSemis, rangoSemis, semisDe, hzDe, Medidor,
  tocarCamino, tocarNota, clic, compararTono,
} from '../../utils/guiaPractica';
import { Locutor } from '../../utils/locutor';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const UMBRAL_VOZ_DB = -50;    // por debajo: silencio
const RUIDO_ALTO_DB = -45;    // ambiente ruidoso
const MUY_FUERTE_DB = -8;     // volumen muy alto
const PAUSA_MS = 2500;        // respiro entre repeticiones

type Fase = 'lista' | 'preparar' | 'practica' | 'fin';
type Etapa = 'escucha' | 'cuenta' | 'canto' | 'pausa';
const nota = (hz: number) => nombreNota(hzAMidi(hz));
const dormir = (ms: number) => new Promise(r => setTimeout(r, ms));

export const DEMO = {
  nombre: 'León', estado: 'activa', consentimiento: true, profesional: 'Matías Pérez · Fonoaudiólogo',
  indicaciones: 'Dos veces por día, mañana y tarde.', veces_por_dia: 2, practicas_hoy: 1, voz: [],
  ejercicios: [
    { bank_id: 'glissandos', nombre: 'Glissandos ascendentes y descendentes', guia: 'rampa', base_hz: 118, amplitud: 5, duracion_s: 6, repeticiones: 3, tolerancia_cents: 100, consigna: 'Sirena suave sobre /u/: subí y bajá siguiendo la rampa.', rango_min_hz: 98, rango_max_hz: 175 },
    { bank_id: 'popote_aire', nombre: 'Escala de cinco notas', guia: 'escalera', base_hz: 118, semitonos: [0, 2, 4, 5, 7, 5, 4, 2, 0], nota_s: 1.2, repeticiones: 2, tolerancia_cents: 100, consigna: 'Subí y bajá los escalones, cómodo.', rango_min_hz: 98, rango_max_hz: 175 },
    { bank_id: 'oclusion_nasal', nombre: '/m/ sostenida', guia: 'sostenida', base_hz: 118, duracion_s: 6, repeticiones: 3, tolerancia_cents: 100, consigna: '/m/ en tu tono cómodo, pareja y sin esfuerzo.', rango_min_hz: 98, rango_max_hz: 175 },
  ],
};

type Props = { token?: string; vistaPrevia?: any; onCerrar?: () => void };

/**
 * Práctica guiada del paciente (?practica=<token>): sin login. Cada
 * repetición: ESCUCHÁ el modelo (sonido + pelota) → AHORA VOS (se mide sin
 * ningún sonido: el micrófono solo escucha al paciente) → RESPIRÁ. Las
 * indicaciones suenan con la voz grabada del fonoaudiólogo (o la del
 * celular). La voz se analiza en el celular; al servidor solo viajan números.
 */
export default function PracticaPaciente({ token = '', vistaPrevia, onCerrar }: Props) {
  const previa = vistaPrevia || (token === 'demo' ? DEMO : null);
  const [simular, setSimular] = useState(!!previa);
  const [hablar, setHablar] = useState(true);
  const [modeloSiempre, setModeloSiempre] = useState(true);
  const [info, setInfo] = useState<any>(previa);
  const [error, setError] = useState('');
  const [acepto, setAcepto] = useState(false);
  const [fase, setFase] = useState<Fase>('lista');
  const [idx, setIdx] = useState(0);
  const [prep, setPrep] = useState<{ paso: string; ruido?: { db: number; ok: boolean }; calib?: any }>({ paso: 'inicio' });
  const [etapa, setEtapa] = useState<Etapa>('escucha');
  const [aviso, setAviso] = useState('');
  const [rep, setRep] = useState(0);
  const [resumen, setResumen] = useState<any>(null);
  const [hechos, setHechos] = useState<number[]>([]);
  const [hoy, setHoy] = useState<number>(previa?.practicas_hoy || 0);
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const mic = useRef<{ stream: MediaStream; an: AnalyserNode } | null>(null);
  const loc = useRef<Locutor | null>(null);
  const corriendo = useRef(false);
  const tanda = useRef(`${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`);
  const preparado = useRef(false);
  const calibRef = useRef<any>(null);
  const ruidoRef = useRef<any>(null);
  const tandaContada = useRef(false);

  useEffect(() => {
    if (previa) return () => detener();
    fetch(`${BACKEND_URL}/api/practica/${token}`)
      .then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || 'No se pudo abrir'); return j; })
      .then(j => { setInfo(j); setHoy(j.practicas_hoy || 0); }).catch(e => setError(e.message));
    return () => detener();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const ej: Ejercicio | null = info?.ejercicios?.[idx] || null;

  const audio = () => {
    if (!ctxRef.current || ctxRef.current.state === 'closed') ctxRef.current = new AudioContext();
    ctxRef.current.resume().catch(() => {});
    return ctxRef.current;
  };
  /** Locutor con la voz grabada del profesional (se crea y precarga una vez). */
  const locutor = async () => {
    if (!loc.current) {
      const claves: string[] = info?.voz || [];
      const fuente = previa
        ? (vistaPrevia?.fuenteVoz || null)
        : async (c: string) => { const r = await fetch(`${BACKEND_URL}/api/practica/${token}/voz/${encodeURIComponent(c)}`); return r.ok ? r.arrayBuffer() : null; };
      loc.current = new Locutor(audio, fuente, claves);
      await loc.current.precargar();
    }
    loc.current.activo = hablar;
    return loc.current;
  };
  const decir = async (clave: string, texto: string, margen = 250) => (await locutor()).decir(clave, texto, margen);

  const abrirMic = async () => {
    if (mic.current) return mic.current;
    const ctx = audio();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    const an = ctx.createAnalyser();
    an.fftSize = 2048;
    ctx.createMediaStreamSource(stream).connect(an);
    mic.current = { stream, an };
    return mic.current;
  };
  function detener() {
    corriendo.current = false;
    loc.current?.callar();
    mic.current?.stream.getTracks().forEach(t => t.stop());
    mic.current = null;
    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;
    loc.current = null;
  }

  /** F0 mediana durante `seg` segundos, sin el ataque y sin saltos aislados. */
  const medir = async (seg: number, objetivo: number) => {
    if (simular) { await dormir(seg * 1000); return { hz: objetivo * Math.pow(2, 0.1 / 12), db: -60 }; }
    const { an } = await abrirMic();
    const ctx = audio();
    const buf = new Float32Array(an.fftSize);
    const suav = new SuavizadorF0();
    const f0: number[] = [], dbs: number[] = [];
    const fin = Date.now() + seg * 1000;
    await new Promise<void>(res => {
      const t = setInterval(() => {
        an.getFloatTimeDomainData(buf);
        const db = dbfs(buf); dbs.push(db);
        const hz = suav.agregar(db > UMBRAL_VOZ_DB ? yin(buf, ctx.sampleRate, 55, 1000) : null);
        if (hz) f0.push(hz);
        if (Date.now() > fin) { clearInterval(t); res(); }
      }, 40);
    });
    const ord = [...f0].sort((a, b) => a - b), od = [...dbs].sort((a, b) => a - b);
    return { hz: ord.length >= 10 ? ord[Math.floor(ord.length / 2)] : null, db: Math.round(od[Math.floor(od.length / 2)]) };
  };

  const aceptar = async () => {
    const r = await fetch(`${BACKEND_URL}/api/practica/${token}/consentimiento`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ acepta: true }),
    });
    if (r.ok) setInfo((i: any) => ({ ...i, consentimiento: true }));
    else setError('No se pudo registrar. Probá de nuevo.');
  };

  const elegir = (i: number) => {
    setIdx(i); setResumen(null); audio();
    if (preparado.current) { setFase('practica'); setTimeout(() => practicar(i), 50); }
    else { setPrep({ paso: 'inicio' }); setFase('preparar'); }
  };

  /** Preparación (una vez por práctica): silencio del lugar + afinación con la nota de inicio. */
  const prepararSilencio = async () => {
    try {
      if (!simular) await abrirMic();
      setPrep({ paso: 'hablando' });
      await decir('bienvenida', 'Hola, vamos a hacer tu práctica de voz.');
      await decir('silencio', 'Quedate en silencio unos segundos.', 400);
      setPrep({ paso: 'silencio' });
      const r = await medir(3, ej!.base_hz);
      ruidoRef.current = { db: r.db, ok: r.db < RUIDO_ALTO_DB };
      setPrep({ paso: 'nota', ruido: ruidoRef.current });
    } catch {
      setError('No se pudo usar el micrófono. Revisá el permiso del navegador y volvé a intentar.');
    }
  };
  const afinar = async () => {
    const base = ej!.base_hz;
    setPrep(p => ({ ...p, paso: 'escuchando' }));
    await decir('escucha_nota', 'Escuchá tu nota.');
    tocarNota(audio(), base, 2.2);
    await dormir(2500);
    setPrep(p => ({ ...p, paso: 'instruccion' }));
    await decir('hace_mmm', 'Ahora hacé mmm en esa misma nota.', 300);   // se mide recién cuando terminó de hablar
    setPrep(p => ({ ...p, paso: 'cantando' }));
    const r = await medir(3, base);
    let calib: any = { hz: r.hz, st: null, texto: 'No te escuchamos: acercá el celular y probá de nuevo.', ok: false };
    if (r.hz) {
      const c = compararTono(r.hz, base);
      calib = { hz: Math.round(r.hz * 10) / 10, st: Math.round(c.st * 10) / 10, ok: Math.abs(c.st) <= 2 };
      calib.texto = calib.ok
        ? (Math.abs(c.st) <= 0.5 ? `¡Muy bien! Estás en tu nota (${nota(base)}).`
          : `¡Muy bien! Estás cerca de tu nota (${nota(base)}), apenas un poco más ${c.st > 0 ? 'agudo' : 'grave'}.`)
        : c.octava ? `Estás una octava más ${c.octava === 'arriba' ? 'aguda' : 'grave'} (${nota(r.hz)}). Probá más ${c.octava === 'arriba' ? 'grave' : 'agudo'}, como la nota que escuchaste.`
        : `Estás ${Math.abs(Math.round(c.st))} semitonos más ${c.st > 0 ? 'agudo' : 'grave'} que la nota (${nota(r.hz)} en vez de ${nota(base)}). Escuchala de nuevo y probá.`;
    }
    calibRef.current = calib;
    setPrep(p => ({ ...p, paso: 'resultado', calib }));
    await decir(calib.ok ? 'afinado' : 'de_nuevo', calib.ok ? 'Muy bien, estás en tu nota.' : 'Probemos de nuevo.');
  };
  const empezar = () => { preparado.current = true; setFase('practica'); setTimeout(() => practicar(idx), 50); };

  const practicar = async (i: number) => {
    const e: Ejercicio = info.ejercicios[i];
    const ctx = audio();
    const m = simular ? null : await abrirMic().catch(() => null);
    if (!simular && !m) { setError('No se pudo usar el micrófono. Revisá el permiso del navegador.'); return; }
    corriendo.current = true;
    const buf = new Float32Array(2048);
    const med = new Medidor();
    const suav = new SuavizadorF0();
    const d = duracion(e);
    const [lo, hi] = rangoSemis(e);
    const minHz = Math.max(55, hzDe(lo - 8, e.base_hz)), maxHz = Math.min(1200, hzDe(hi + 14, e.base_hz));
    const rastro: { x: number; s: number | null }[] = [];
    const notasGuia = [...new Set(e.guia === 'rampa' ? [0, e.amplitud || 7] : e.guia === 'sostenida' ? [0] : (e.semitonos || [0]))];

    const dibujar = (t: number, semis: number | null, estado: 'modelo' | 'dentro' | 'fuera' | 'nada') => {
      const c = canvas.current; if (!c) return;
      const g = c.getContext('2d')!; const W = c.width, H = c.height, IZQ = 52;
      const y = (s: number) => H - 18 - ((s - lo) / (hi - lo)) * (H - 36);
      const oscuro = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
      g.clearRect(0, 0, W, H);
      g.font = '20px system-ui'; g.fillStyle = oscuro ? '#9ca3af' : '#6b7280'; g.textBaseline = 'middle';
      notasGuia.forEach(s => { g.fillText(nota(hzDe(s, e.base_hz)), 4, y(s)); });
      const tol = e.tolerancia_cents / 100;
      g.fillStyle = oscuro ? 'rgba(29,158,117,0.35)' : 'rgba(93,202,165,0.45)';
      for (let x = IZQ; x < W; x += 3) {
        const s = objetivoSemis(e, ((x - IZQ) / (W - IZQ)) * d);
        g.fillRect(x, y(s + tol), 3, Math.max(4, y(s - tol) - y(s + tol)));
      }
      g.strokeStyle = oscuro ? '#5DCAA5' : '#0F6E56'; g.lineWidth = 2; g.beginPath();
      rastro.forEach((p, k) => { if (p.s == null) return; const yy = y(p.s); k && rastro[k - 1].s != null ? g.lineTo(p.x, yy) : g.moveTo(p.x, yy); });
      g.stroke();
      const x = IZQ + (Math.min(t, d) / d) * (W - IZQ);
      g.fillStyle = oscuro ? '#555' : '#ccc'; g.fillRect(x, 0, 1, H);
      if (semis != null) {
        g.beginPath(); g.arc(x, y(Math.max(lo, Math.min(hi, semis))), 15, 0, Math.PI * 2);
        g.fillStyle = estado === 'modelo' ? '#7F77DD' : estado === 'dentro' ? '#1D9E75' : '#D85A30'; g.fill();
      }
    };

    /** Corre `seg` segundos llamando a `cuadro(t)` cada 40 ms. */
    const durante = (seg: number, cuadro: (t: number) => void) => new Promise<void>(res => {
      const ini = performance.now();
      const tick = () => {
        if (!corriendo.current) return res();
        const t = (performance.now() - ini) / 1000;
        if (t >= seg) return res();
        cuadro(t);
        setTimeout(tick, 40);
      };
      tick();
    });

    let cantado = 0;
    for (let r = 0; r < e.repeticiones && corriendo.current; r++) {
      setRep(r + 1);
      // 1) ESCUCHÁ: consigna (la primera vez) + modelo sonando con la pelota.
      if (modeloSiempre || r === 0) {
        setEtapa('escucha'); rastro.length = 0; dibujar(0, null, 'nada');
        if (r === 0) { setAviso(e.consigna || ''); await decir(`ej:${e.bank_id || ''}`, e.consigna || '', 300); }
        if (!corriendo.current) break;
        setAviso('Escuchá y mirá la pelota');
        await decir('escucha', 'Escuchá.', 150);
        tocarCamino(ctx, e, ctx.currentTime + 0.05);
        await durante(d + 0.1, t => dibujar(t, objetivoSemis(e, Math.min(t, d)), 'modelo'));
        await dormir(250);   // que termine de sonar
      }
      if (!corriendo.current) break;
      // 2) CUENTA: "Ahora vos" (se espera que termine) + dos clics.
      setEtapa('cuenta'); setAviso('Preparate…'); rastro.length = 0; dibujar(0, null, 'nada');
      await decir('ahora_vos', 'Ahora vos.', 100);
      clic(ctx, ctx.currentTime + 0.05); clic(ctx, ctx.currentTime + 0.5, true);
      await dormir(800);
      if (!corriendo.current) break;
      // 3) AHORA VOS: se mide sin ningún sonido de la app.
      setEtapa('canto'); setAviso(''); suav.reset();
      const ini = performance.now();
      await durante(d, t => {
        let db: number, hzCrudo: number | null;
        if (m) {
          m.an.getFloatTimeDomainData(buf);
          db = dbfs(buf);
          hzCrudo = db > UMBRAL_VOZ_DB ? yin(buf, ctx.sampleRate, minHz, maxHz) : null;
        } else {
          db = -25;
          hzCrudo = hzDe(objetivoSemis(e, t) + Math.sin(t * 2.3) * 0.6 + (Math.random() - 0.5) * 0.4, e.base_hz);
        }
        const hz = suav.agregar(hzCrudo);
        const objetivo = hzDe(objetivoSemis(e, t), e.base_hz);
        if (hzCrudo == null || hz != null) med.agregar(hz, objetivo, e.tolerancia_cents);  // el ataque no se cuenta
        const semis = hz ? semisDe(hz, e.base_hz) : null;
        const cents = hz ? 1200 * Math.log2(hz / objetivo) : 0;
        const dentro = hz != null && Math.abs(cents) <= e.tolerancia_cents;
        const octava = hz != null && !dentro && Math.abs(Math.abs(cents) - 1200) <= e.tolerancia_cents;
        rastro.push({ x: 52 + (t / d) * ((canvas.current?.width || 640) - 52), s: semis });
        setAviso(db > MUY_FUERTE_DB ? 'Más suave: no hace falta fuerza'
          : hzCrudo == null ? 'Te escucho…'
          : hz == null ? ''
          : dentro ? 'Muy bien'
          : octava ? `Estás una octava más ${cents > 0 ? 'aguda' : 'grave'}`
          : cents > 0 ? 'Un poco más grave' : 'Un poco más agudo');
        dibujar(t, semis, hz == null ? 'nada' : dentro ? 'dentro' : 'fuera');
      });
      cantado += Math.min(d, (performance.now() - ini) / 1000);
      // 4) RESPIRÁ.
      if (r < e.repeticiones - 1 && corriendo.current) {
        setEtapa('pausa'); setAviso('Respirá tranquilo'); dibujar(0, null, 'nada');
        const p0 = performance.now();
        await decir('respira', 'Respirá.', 0);
        await dormir(Math.max(0, PAUSA_MS - (performance.now() - p0)));
      }
    }
    const completo = corriendo.current;
    corriendo.current = false;
    const res = med.resumen(cantado, e.repeticiones);
    setResumen(res); setFase('fin');
    const bien = res.dentro_pct != null && res.dentro_pct >= 70;
    decir(bien ? 'fin_bien' : 'fin', bien ? 'Muy bien, terminaste el ejercicio.' : 'Terminaste. Buen trabajo.');
    if (previa) { setHechos(h => [...new Set([...h, i])]); if (!tandaContada.current) { tandaContada.current = true; setHoy(x => x + 1); } return; }
    if (completo || (res.voz_pct || 0) > 0) {
      const amb: any = { tanda: tanda.current };
      if (ruidoRef.current) { amb.ruido_dbfs = ruidoRef.current.db; amb.silencioso = ruidoRef.current.ok; }
      if (calibRef.current?.hz) { amb.calibracion_hz = calibRef.current.hz; amb.calibracion_st = calibRef.current.st; }
      fetch(`${BACKEND_URL}/api/practica/${token}/sesion`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resultados: [{ ejercicio: i, ...res }], ambiente: amb }),
      }).then(r => {
        if (r.ok) {
          setHechos(h => [...new Set([...h, i])]);
          if (!tandaContada.current) { tandaContada.current = true; setHoy(x => x + 1); }
        }
      }).catch(() => {});
    }
  };

  const caja = 'bg-white dark:bg-white/5 rounded-2xl border border-slate-200 dark:border-white/10 p-5';
  const boton = 'w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-50';
  const secundario = 'w-full py-2.5 rounded-xl border border-indigo-300 text-indigo-700 dark:text-indigo-300 font-semibold';

  if (error) return <Marco><div className={caja}><p className="text-red-600">{error}</p></div></Marco>;
  if (!info) return <Marco><p className="text-slate-500">Cargando…</p></Marco>;
  if (info.estado !== 'activa') return <Marco><div className={caja}><p>Esta práctica está {info.estado}. Pedile una nueva a tu fonoaudiólogo.</p></div></Marco>;

  if (!info.consentimiento) return (
    <Marco>
      <div className={caja + ' space-y-3 text-sm'}>
        <h1 className="text-lg font-black">Hola{info.nombre ? ` ${info.nombre}` : ''}</h1>
        <p>Esta es tu práctica de voz indicada por {info.profesional}. Primero escuchás cada ejercicio y después lo hacés vos: una pelotita sigue tu voz para guiarte.</p>
        <ul className="list-disc pl-5 space-y-1 text-slate-700 dark:text-slate-300">
          <li>Se usa el micrófono de tu celular solo mientras practicás.</li>
          <li><b>No se graba tu voz:</b> el tono se calcula en tu teléfono.</li>
          <li>Solo se guardan números de la práctica (por ejemplo, cuánto tiempo seguiste el camino) y los ve únicamente tu fonoaudiólogo.</li>
          <li>Podés dejar de usarla cuando quieras.</li>
        </ul>
        <label className="flex gap-2 items-start"><input type="checkbox" className="mt-1" checked={acepto} onChange={e => setAcepto(e.target.checked)} />
          <span>Entiendo y acepto que se midan estos datos de mi práctica.</span></label>
        <button disabled={!acepto} onClick={aceptar} className={boton}>Empezar</button>
      </div>
    </Marco>
  );

  const veces = info.veces_por_dia || 2;

  return (
    <Marco>
      {previa && (
        <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-300 text-xs space-y-1.5">
          <p className="font-bold text-amber-800 dark:text-amber-200">Vista previa: así lo ve el paciente (no se guarda nada)</p>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={simular} onChange={e => { detener(); setSimular(e.target.checked); }} />
            Simular la voz (sin micrófono). Desmarcalo para probar con tu voz.</label>
          {onCerrar && <button onClick={() => { detener(); onCerrar(); }} className="text-indigo-600 font-semibold">Cerrar vista previa</button>}
        </div>
      )}

      {fase === 'lista' && (
        <div className="space-y-3">
          <div className={caja}>
            <h1 className="text-lg font-black">Hola{info.nombre ? ` ${info.nombre}` : ''}, tu práctica de hoy</h1>
            <p className="mt-1 text-sm font-semibold text-indigo-700 dark:text-indigo-300">
              Hoy: {Math.min(hoy, veces)} de {veces} práctica{veces === 1 ? '' : 's'} {hoy >= veces ? '✓' : ''}
            </p>
            {info.semana && (
              <div className="flex gap-1 mt-2" title="Últimos 7 días">
                {info.semana.map((d: any) => (
                  <span key={d.dia} className={`h-2.5 flex-1 rounded-full ${d.practicas >= veces ? 'bg-emerald-500' : d.practicas ? 'bg-amber-400' : 'bg-slate-200 dark:bg-white/10'}`} />
                ))}
              </div>
            )}
            {info.indicaciones && <p className="text-sm text-slate-600 dark:text-slate-300 mt-2">{info.indicaciones}</p>}
            <p className="text-xs text-slate-500 mt-2">Buscá un lugar tranquilo; con auriculares se escucha mejor. Si sentís molestia o esfuerzo, pará y descansá.</p>
            <div className="mt-2 space-y-1 text-xs text-slate-600 dark:text-slate-300">
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={hablar} onChange={e => setHablar(e.target.checked)} /> Indicaciones habladas</label>
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={modeloSiempre} onChange={e => setModeloSiempre(e.target.checked)} /> Escuchar el modelo antes de cada repetición</label>
            </div>
          </div>
          {info.ejercicios.map((e: Ejercicio, i: number) => (
            <button key={i} onClick={() => elegir(i)} className={caja + ' w-full text-left hover:border-indigo-400'}>
              <p className="font-bold">{i + 1}. {e.nombre} {hechos.includes(i) && <span className="text-emerald-600 text-sm">✓ hecho</span>}</p>
              {e.consigna && <p className="text-sm text-slate-600 dark:text-slate-300">{e.consigna}</p>}
              <p className="text-xs text-slate-500 mt-1">{e.repeticiones} repeticiones · empieza en {nota(e.base_hz)}</p>
            </button>
          ))}
        </div>
      )}

      {fase === 'preparar' && ej && (
        <div className={caja + ' space-y-3 text-sm'}>
          <p className="font-bold">Antes de empezar</p>
          {prep.paso === 'inicio' && (<>
            <p>1. Vamos a escuchar el lugar unos segundos: quedate en silencio.</p>
            <button onClick={prepararSilencio} className={boton}>Empezar</button>
          </>)}
          {prep.paso === 'hablando' && <p className="text-center py-4">Escuchá la indicación… 🔊</p>}
          {prep.paso === 'silencio' && <p className="text-center py-4">Silencio… 🤫</p>}
          {['nota', 'escuchando', 'instruccion', 'cantando', 'resultado'].includes(prep.paso) && prep.ruido && (
            <p className={prep.ruido.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}>
              {prep.ruido.ok ? 'El lugar está tranquilo.' : 'Hay bastante ruido: si podés, buscá un lugar más silencioso.'}
            </p>
          )}
          {prep.paso === 'nota' && (<>
            <p>2. Ahora afinamos: escuchá tu nota de inicio (<b>{nota(ej.base_hz)}</b>) y hacé «mmm» en esa misma nota.</p>
            <button onClick={afinar} className={boton}>Escuchar y afinar</button>
          </>)}
          {prep.paso === 'escuchando' && <p className="text-center py-4">Escuchá la nota… 🎵</p>}
          {prep.paso === 'instruccion' && <p className="text-center py-4">Escuchá la indicación… 🔊</p>}
          {prep.paso === 'cantando' && <p className="text-center py-4 font-bold text-emerald-600">Ahora vos: «mmm»… 🎙️</p>}
          {prep.paso === 'resultado' && prep.calib && (<>
            <p className={prep.calib.ok ? 'text-emerald-700 dark:text-emerald-300 font-semibold' : 'text-amber-700 dark:text-amber-300 font-semibold'}>{prep.calib.texto}</p>
            {!prep.calib.ok && <button onClick={afinar} className={secundario}>Probar de nuevo</button>}
            <button onClick={empezar} className={boton}>{prep.calib.ok ? 'Empezar ejercicio' : 'Empezar igual'}</button>
          </>)}
          <button onClick={() => { setFase('lista'); }} className="w-full text-slate-500 text-xs">Volver</button>
        </div>
      )}

      {fase === 'practica' && ej && (
        <div className={caja + ' space-y-2'}>
          <div className="flex justify-between text-sm"><b>{ej.nombre}</b><span className="text-slate-500">Repetición {rep} de {ej.repeticiones}</span></div>
          <p className={`text-center text-lg font-black ${etapa === 'escucha' ? 'text-indigo-600' : etapa === 'canto' ? 'text-emerald-600' : 'text-slate-500'}`}>
            {etapa === 'escucha' ? '🎧 Escuchá' : etapa === 'cuenta' ? 'Preparate…' : etapa === 'canto' ? '🎙️ Ahora vos' : '🌬️ Respirá'}
          </p>
          <canvas ref={canvas} width={640} height={300} className="w-full rounded-xl bg-slate-50 dark:bg-black/30" />
          <p className="text-center font-semibold min-h-6">{aviso}</p>
          <button onClick={() => { corriendo.current = false; loc.current?.callar(); }} className="w-full py-2 rounded-xl border border-slate-300 dark:border-white/20 text-sm">Terminar</button>
        </div>
      )}

      {fase === 'fin' && resumen && (
        <div className={caja + ' space-y-3 text-sm'}>
          <p className="text-lg font-black">¡Bien hecho!</p>
          <p>{resumen.dentro_pct == null ? 'No llegamos a escuchar tu voz: probá acercar el celular.'
            : (resumen.octava_pct || 0) >= 30 ? 'Lo hiciste una octava distinta de la nota: la próxima, escuchá el modelo y buscá la misma altura.'
            : resumen.dentro_pct >= 70 ? 'Seguiste muy bien el camino.'
            : resumen.dentro_pct >= 40 ? 'Vas bien: con práctica te va a salir cada vez más fácil.'
            : 'Fue un buen comienzo. Escuchá bien el modelo y hacelo despacio, sin esfuerzo.'}</p>
          <p className="text-xs text-slate-500">Hoy: {Math.min(hoy, veces)} de {veces} práctica{veces === 1 ? '' : 's'}.</p>
          <button onClick={() => setFase('lista')} className={boton}>Volver a la lista</button>
        </div>
      )}
    </Marco>
  );
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0b0f19] text-slate-900 dark:text-white p-4">
      <div className="max-w-md mx-auto space-y-3">
        {children}
        <p className="text-center text-[11px] text-slate-400 pt-2">Matías Pérez · Fonoaudiólogo</p>
      </div>
    </div>
  );
}
