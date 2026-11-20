import React, { useEffect, useRef, useState } from 'react';
import { yin, dbfs, nombreNota, hzAMidi, SuavizadorF0 } from '../../utils/pitch';
import {
  Ejercicio, duracion, objetivoSemis, rangoSemis, semisDe, hzDe, Analizador,
  tocarCamino, tocarNota, clic, compararTono, medidaDe, usaTono, objetivoDb, tiemposPulsos, crearTimbre,
} from '../../utils/guiaPractica';
import { Locutor } from '../../utils/locutor';
import { Escenario, MedicionSZ, NOCHE } from './visuales';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const UMBRAL_VOZ_DB = -50;    // por debajo: silencio
const RUIDO_ALTO_DB = -45;    // ambiente ruidoso
const MUY_FUERTE_DB = -8;     // volumen muy alto
const PAUSA_MS = 3000;        // respiro entre repeticiones (con cuenta regresiva)
/** Color y tamaño de la esfera en cada etapa: azul escucha, lavanda tu voz, verde agua respirar. */
const VISUAL: Record<string, { color: string; escala: number; texto: string }> = {
  escucha: { color: NOCHE.inhala, escala: 0.7, texto: 'Escuchá' },
  cuenta: { color: NOCHE.tenue, escala: 0.85, texto: 'Preparate' },
  canto: { color: NOCHE.sonido, escala: 0.62, texto: 'Ahora vos' },
  pausa: { color: NOCHE.descanso, escala: 0.95, texto: 'Respirá' },
};

type Fase = 'lista' | 'preparar' | 'practica' | 'fin' | 'sz';
type Etapa = 'escucha' | 'cuenta' | 'canto' | 'pausa';
const nota = (hz: number) => nombreNota(hzAMidi(hz));
const dormir = (ms: number) => new Promise(r => setTimeout(r, ms));

export const DEMO = {
  nombre: 'León', estado: 'activa', consentimiento: true, profesional: 'Matías Pérez · Fonoaudiólogo',
  indicaciones: 'Dos veces por día, mañana y tarde.', veces_por_dia: 2, practicas_hoy: 1, voz: [],
  ejercicios: [
    { bank_id: 'glissandos', nombre: 'Glissandos ascendentes y descendentes', medida: 'tono', modelo: 'sonoro', guia: 'rampa', base_hz: 118, amplitud: 5, duracion_s: 6, repeticiones: 2, tolerancia_cents: 200, consigna: 'Sirena suave sobre /u/: subí y bajá siguiendo la rampa.' },
    { bank_id: 'tubo_agua', nombre: 'Tubo en agua', medida: 'flujo', modelo: 'sin_modelo', guia: 'sostenida', base_hz: 118, duracion_objetivo_s: 8, margen_db: 6, repeticiones: 2, tolerancia_cents: 100, consigna: 'Tubo en el agua: burbujeo parejo y sonido continuo, sin empujar.' },
    { bank_id: 'messa_di_voce', nombre: 'Messa di voce', medida: 'intensidad', modelo: 'sonoro', guia: 'sostenida', base_hz: 118, duracion_s: 8, patron_intensidad: 'arco', margen_db: 4, repeticiones: 2, tolerancia_cents: 100, consigna: 'Misma nota: empezá suave, crecé y volvé a suave.' },
    { bank_id: 'metodo_acento', nombre: 'Método del acento', medida: 'pulsos', modelo: 'sonoro', guia: 'sostenida', base_hz: 118, pulsos: 6, tempo_bpm: 80, repeticiones: 2, tolerancia_cents: 100, consigna: 'Impulsos rítmicos con apoyo abdominal, siguiendo el pulso.' },
  ],
};

type Props = { token?: string; vistaPrevia?: any; onCerrar?: () => void };

/** Cuadro simulado (vista previa) según lo que mide el ejercicio. */
function simularCuadro(e: Ejercicio, t: number, base: number, ref: number): { db: number; hz: number | null } {
  const ruido = (Math.random() - 0.5);
  switch (medidaDe(e)) {
    case 'flujo': return { db: ref - 2 + ruido * 3 - (t % 3 > 2.85 ? 30 : 0), hz: null };
    case 'intensidad': return { db: ref + objetivoDb(e, t) + ruido * 2, hz: base };
    case 'pulsos': return { db: tiemposPulsos(e).some(tp => t >= tp && t < tp + 0.18) ? ref + 4 : ref - 40, hz: base };
    case 'libre': return { db: ref + Math.sin(t * 3) * 4 + ruido * 2, hz: base * Math.pow(2, (Math.sin(t * 1.7) * 2) / 12) };
    case 'sostenido': return { db: ref + ruido * 2, hz: usaTono(e) ? hzDe(Math.sin(t * 2.3) * 0.3, base) : base * (1 + ruido * 0.01) };
    default: return { db: ref, hz: hzDe(objetivoSemis(e, t) + Math.sin(t * 2.3) * 0.6 + ruido * 0.4, base) };
  }
}

/** Modelo de dinámica (messa di voce): la nota crece y decrece en volumen. */
function tocarDinamica(ctx: AudioContext, e: Ejercicio, hz: number, t0: number) {
  const d = duracion(e), o = ctx.createOscillator(), g = ctx.createGain();
  o.setPeriodicWave(crearTimbre(ctx)); o.frequency.value = hz;
  g.gain.setValueAtTime(0, t0);
  for (let k = 0; k <= 20; k++) g.gain.linearRampToValueAtTime(0.25 * Math.pow(10, (objetivoDb(e, (k / 20) * d) - 6) / 20), t0 + (k / 20) * d);
  g.gain.linearRampToValueAtTime(0, t0 + d + 0.05);
  o.connect(g).connect(ctx.destination); o.start(t0); o.stop(t0 + d + 0.1);
}

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
  const [reloj, setReloj] = useState<{ restante: number; total: number } | null>(null);
  const [cuentaNum, setCuentaNum] = useState(3);
  const nivel = useRef(0);
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
    if (simular) { await dormir(seg * 1000); return { hz: objetivo * Math.pow(2, 0.1 / 12), db: -60, dbVoz: -30 }; }
    const { an } = await abrirMic();
    const ctx = audio();
    const buf = new Float32Array(an.fftSize);
    const suav = new SuavizadorF0();
    const f0: number[] = [], dbs: number[] = [], dbVoz: number[] = [];
    const fin = Date.now() + seg * 1000;
    await new Promise<void>(res => {
      const t = setInterval(() => {
        an.getFloatTimeDomainData(buf);
        const db = dbfs(buf); dbs.push(db); if (db > UMBRAL_VOZ_DB) dbVoz.push(db);
        const hz = suav.agregar(db > UMBRAL_VOZ_DB ? yin(buf, ctx.sampleRate, 55, 1000) : null);
        if (hz) f0.push(hz);
        if (Date.now() > fin) { clearInterval(t); res(); }
      }, 40);
    });
    const ord = [...f0].sort((a, b) => a - b), od = [...dbs].sort((a, b) => a - b);
    const ov = [...dbVoz].sort((a, b) => a - b);
    return { hz: ord.length >= 10 ? ord[Math.floor(ord.length / 2)] : null, db: Math.round(od[Math.floor(od.length / 2)]),
             dbVoz: ov.length >= 10 ? Math.round(ov[Math.floor(ov.length / 2)]) : null };
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
  const hayTono = (info?.ejercicios || []).some((x: Ejercicio) => usaTono(x));
  const afinar = async () => {
    const base = ej!.base_hz;
    if (!hayTono || !base) {
      // Sin altura objetivo: se registra su voz cómoda de hoy, sin dar ninguna nota.
      setPrep(p => ({ ...p, paso: 'instruccion' }));
      await decir('hace_mmm', 'Ahora hacé un mmm cómodo, sin buscar ninguna nota.', 300);
      setPrep(p => ({ ...p, paso: 'cantando' }));
      const r = await medir(3, base || 150);
      const calib = r.hz ? { hz: Math.round(r.hz * 10) / 10, st: null, db: r.dbVoz, ok: true, texto: `Listo: tu voz cómoda de hoy está en ${nota(r.hz)}.` }
        : { hz: null, st: null, db: r.dbVoz, ok: false, texto: 'No te escuchamos bien: acercá el celular y probá de nuevo.' };
      calibRef.current = calib;
      setPrep(p => ({ ...p, paso: 'resultado', calib }));
      return;
    }
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
      calib = { hz: Math.round(r.hz * 10) / 10, st: Math.round(c.st * 10) / 10, db: r.dbVoz, ok: Math.abs(c.st) <= 2 };
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
    const medida = medidaDe(e), conTono = usaTono(e);
    const ctx = audio();
    const m = simular ? null : await abrirMic().catch(() => null);
    if (!simular && !m) { setError('No se pudo usar el micrófono. Revisá el permiso del navegador.'); return; }
    corriendo.current = true;
    const buf = new Float32Array(2048);
    const ambiente = ruidoRef.current?.db ?? -60;
    const referencia = calibRef.current?.db ?? ambiente + 25;      // su nivel cómodo de hoy
    const an = new Analizador(e, ambiente, referencia);
    const suav = new SuavizadorF0();
    const d = duracion(e);
    const base = e.base_hz || calibRef.current?.hz || 150;
    const [lo, hi] = conTono ? rangoSemis(e) : [-24, 18];           // dB respecto de su nivel cómodo
    const minHz = conTono ? Math.max(55, hzDe(lo - 8, base)) : 55, maxHz = conTono ? Math.min(1200, hzDe(hi + 14, base)) : 1000;
    const rastro: { x: number; v: number | null }[] = [];
    const pulsosVistos: number[] = [];
    const notasGuia = conTono ? [...new Set(e.guia === 'rampa' ? [0, e.amplitud || 7] : e.guia === 'sostenida' ? [0] : (e.semitonos || [0]))] : [];
    const IZQ = 52;

    /** Eje vertical: semitonos (altura) o dB respecto de su nivel cómodo (intensidad). */
    const dibujar = (t: number, v: number | null, estado: 'modelo' | 'dentro' | 'fuera' | 'nada' | 'sinAltura') => {
      const c = canvas.current; if (!c) return;
      const g = c.getContext('2d')!; const W = c.width, H = c.height;
      const y = (s: number) => H - 18 - ((s - lo) / (hi - lo)) * (H - 36);
      const xDe = (tt: number) => IZQ + (Math.min(tt, d) / d) * (W - IZQ);
      const oscuro = true; // la guía del paciente es siempre nocturna
      g.clearRect(0, 0, W, H);
      g.font = '18px system-ui'; g.fillStyle = oscuro ? '#9ca3af' : '#6b7280'; g.textBaseline = 'middle';
      if (conTono) notasGuia.forEach(s => g.fillText(nota(hzDe(s, base)), 4, y(s)));
      else { g.fillText('fuerte', 2, y(12)); g.fillText('cómodo', 0, y(0)); g.fillText('suave', 4, y(-14)); }
      // Banda objetivo
      g.fillStyle = oscuro ? 'rgba(29,158,117,0.35)' : 'rgba(93,202,165,0.45)';
      if (medida !== 'libre' && medida !== 'pulsos') {
        const tol = conTono ? e.tolerancia_cents / 100 : (e.margen_db || 6);
        for (let x = IZQ; x < W; x += 3) {
          const tt = ((x - IZQ) / (W - IZQ)) * d;
          const s = conTono ? objetivoSemis(e, tt) : objetivoDb(e, tt);
          g.fillRect(x, y(s + tol), 3, Math.max(4, y(s - tol) - y(s + tol)));
        }
      }
      if (medida === 'pulsos') {
        tiemposPulsos(e).forEach(tp => { g.fillStyle = oscuro ? 'rgba(127,119,221,0.5)' : 'rgba(127,119,221,0.35)'; g.fillRect(xDe(tp) - 3, 0, 6, H); });
        pulsosVistos.forEach(tp => { g.beginPath(); g.arc(xDe(tp), H - 14, 8, 0, Math.PI * 2); g.fillStyle = '#1D9E75'; g.fill(); });
      }
      g.strokeStyle = oscuro ? '#5DCAA5' : '#0F6E56'; g.lineWidth = 2; g.beginPath();
      rastro.forEach((p, k) => { if (p.v == null) return; const yy = y(Math.max(lo, Math.min(hi, p.v))); k && rastro[k - 1].v != null ? g.lineTo(p.x, yy) : g.moveTo(p.x, yy); });
      g.stroke();
      const x = xDe(t);
      g.fillStyle = oscuro ? '#555' : '#ccc'; g.fillRect(x, 0, 1, H);
      if (v != null) {
        g.beginPath(); g.arc(x, y(Math.max(lo, Math.min(hi, v))), 15, 0, Math.PI * 2);
        g.fillStyle = estado === 'modelo' ? '#7F77DD' : estado === 'dentro' ? '#1D9E75' : estado === 'sinAltura' ? '#888780' : '#D85A30'; g.fill();
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

    /** Modelo de cada tipo: altura (sonido), dinámica (sonido con volumen), pulsos (clics) o solo visual. */
    const modelo = async () => {
      if (conTono) { tocarCamino(ctx, e, ctx.currentTime + 0.05); }
      else if (medida === 'intensidad') { tocarDinamica(ctx, e, base, ctx.currentTime + 0.05); }
      else if (medida === 'pulsos') { tiemposPulsos(e).forEach(tp => clic(ctx, ctx.currentTime + 0.05 + tp, true)); }
      await durante(d + 0.1, t => {
        const v = conTono ? objetivoSemis(e, Math.min(t, d)) : medida === 'pulsos'
          ? (tiemposPulsos(e).some(tp => t >= tp && t < tp + 0.18) ? 4 : -14) : objetivoDb(e, Math.min(t, d));
        dibujar(t, v, 'modelo');
      });
      await dormir(250);
    };

    let cantado = 0;
    for (let r = 0; r < e.repeticiones && corriendo.current; r++) {
      setRep(r + 1); an.nuevaRepeticion();
      const conModelo = e.modelo !== 'sin_modelo' && (modeloSiempre || r === 0);
      // 1) Consigna (la primera vez) y modelo.
      if (r === 0 || conModelo) {
        setEtapa('escucha'); rastro.length = 0; pulsosVistos.length = 0; dibujar(0, null, 'nada');
        if (r === 0) { setAviso(e.consigna || ''); await decir(`ej:${e.bank_id || ''}`, e.consigna || '', 300); }
        if (conModelo && corriendo.current) {
          setAviso(conTono || medida === 'intensidad' || medida === 'pulsos' ? 'Escuchá y mirá la pelota' : 'Mirá cómo es');
          await decir('escucha', 'Escuchá.', 150);
          await modelo();
        }
      }
      if (!corriendo.current) break;
      // 2) Cuenta.
      setEtapa('cuenta'); setAviso('Tomá aire…'); setReloj(null); rastro.length = 0; pulsosVistos.length = 0; dibujar(0, null, 'nada');
      await decir('ahora_vos', 'Ahora vos.', 100);
      if (medida !== 'pulsos') {
        // Cuenta regresiva 3·2·1 con un clic por número (el último, agudo).
        for (let n = 3; n >= 1 && corriendo.current; n--) {
          setCuentaNum(n); clic(ctx, ctx.currentTime + 0.02, n === 1); await dormir(550);
        }
      }
      if (!corriendo.current) break;
      // 3) Ahora vos: se mide sin ningún sonido de la app.
      setEtapa('canto'); setAviso(''); suav.reset(); setReloj({ restante: d, total: d });
      const ini = performance.now();
      let sinAltura = 0, conSonido = 0;
      await durante(d, t => {
        let db: number, hzCrudo: number | null;
        if (m) {
          m.an.getFloatTimeDomainData(buf);
          db = dbfs(buf);
          hzCrudo = db > an.umbralSonido() ? yin(buf, ctx.sampleRate, minHz, maxHz) : null;
        } else {
          ({ db, hz: hzCrudo } = simularCuadro(e, t, base, referencia));
        }
        const hz = suav.agregar(hzCrudo);
        const st = an.cuadro(t, hz, db);
        nivel.current = st.suena ? Math.max(0, Math.min(1, ((st.dbRel ?? 0) + 15) / 25)) : 0;
        setReloj({ restante: Math.max(0, d - t), total: d });
        if (st.pulso) pulsosVistos.push(t);
        if (st.suena) { conSonido++; if (!hz) sinAltura++; }
        const sinAlturaMucho = conTono && conSonido > 25 && sinAltura / conSonido > 0.6;
        const v = conTono ? (hz ? semisDe(hz, base) : (st.suena ? objetivoSemis(e, t) : null)) : (st.suena ? st.dbRel : null);
        rastro.push({ x: IZQ + (t / d) * ((canvas.current?.width || 640) - IZQ), v: conTono && !hz ? null : v });
        let aviso = '';
        if (db > MUY_FUERTE_DB) aviso = 'Más suave: no hace falta fuerza';
        else if (!st.suena) aviso = medida === 'pulsos' ? 'Seguí el pulso' : 'Te escucho…';
        else if (conTono && !hz) aviso = sinAlturaMucho ? 'Te escuchamos: con este sonido la altura no se mide, seguí parejo' : '';
        else if (conTono) aviso = st.dentroTono ? 'Muy bien' : st.octava ? `Estás una octava más ${st.cents > 0 ? 'aguda' : 'grave'}` : st.cents > 0 ? 'Un poco más grave' : 'Un poco más agudo';
        else if (medida === 'intensidad') aviso = st.dentroDb ? 'Muy bien' : st.dbRel > objetivoDb(e, t) ? 'Un poco más suave' : 'Un poco más fuerte';
        else if (medida === 'flujo' || medida === 'sostenido') aviso = st.dentroDb ? 'Parejo, muy bien' : st.dbRel > 0 ? 'Más suave, sin empujar' : 'Sostené el sonido';
        else if (medida === 'libre') aviso = hz ? `Tu voz: ${nota(hz)}` : 'Seguí, cómodo';
        setAviso(aviso);
        const estado = !st.suena ? 'nada' : conTono ? (hz ? (st.dentroTono ? 'dentro' : 'fuera') : 'sinAltura')
          : medida === 'libre' || medida === 'pulsos' ? 'dentro' : (st.dentroDb ? 'dentro' : 'fuera');
        dibujar(t, v, estado);
      });
      cantado += Math.min(d, (performance.now() - ini) / 1000);
      nivel.current = 0;
      // 4) Respirá.
      if (r < e.repeticiones - 1 && corriendo.current) {
        setEtapa('pausa'); setAviso('Respirá tranquilo'); dibujar(0, null, 'nada');
        const p0 = performance.now(), totalP = PAUSA_MS / 1000;
        setReloj({ restante: totalP, total: totalP });
        decir('respira', 'Respirá.', 0);
        await durante(totalP, () => setReloj({ restante: Math.max(0, totalP - (performance.now() - p0) / 1000), total: totalP }));
      }
    }
    const completo = corriendo.current;
    corriendo.current = false;
    const res = an.resumen(cantado, e.repeticiones);
    setResumen(res); setFase('fin');
    const bien = res.logro_pct != null && res.logro_pct >= 70;
    decir(bien ? 'fin_bien' : 'fin', bien ? 'Muy bien, terminaste el ejercicio.' : 'Terminaste. Buen trabajo.');
    if (previa) { setHechos(h => [...new Set([...h, i])]); if (!tandaContada.current) { tandaContada.current = true; setHoy(x => x + 1); } return; }
    if (completo || (res.voz_pct || 0) > 0) {
      const amb: any = { tanda: tanda.current };
      if (ruidoRef.current) { amb.ruido_dbfs = ruidoRef.current.db; amb.silencioso = ruidoRef.current.ok; }
      if (calibRef.current?.hz) { amb.calibracion_hz = calibRef.current.hz; amb.calibracion_st = calibRef.current.st; }
      if (calibRef.current?.db != null) amb.calibracion_db = calibRef.current.db;
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

  /** Guarda la medición s/z como un resultado más (no cuenta como práctica del día). */
  const guardarSZ = async (s: number[], z: number[]) => {
    if (previa) return true;
    try {
      const amb: any = { tanda: `sz-${tanda.current}` };
      if (ruidoRef.current) { amb.ruido_dbfs = ruidoRef.current.db; amb.silencioso = ruidoRef.current.ok; }
      const r = await fetch(`${BACKEND_URL}/api/practica/${token}/sesion`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resultados: [{ medida: 'sz', s, z }], ambiente: amb }),
      });
      return r.ok;
    } catch { return false; }
  };

  const caja = 'bg-[#121a28] rounded-3xl border border-[#233047] p-5';
  const boton = 'w-full py-3.5 rounded-2xl bg-[#b39cff] hover:bg-[#c4b2ff] text-[#140f26] font-bold disabled:opacity-50';
  const secundario = 'w-full py-2.5 rounded-2xl border border-[#b39cff]/50 text-[#c9b8ff] font-semibold';

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
              <p className="text-xs text-slate-500 mt-1">{e.repeticiones} repeticiones · {usaTono(e) && e.base_hz ? `empieza en ${nota(e.base_hz)}`
                : ({ flujo: 'sonido parejo y continuo', sostenido: 'sostenido y parejo', intensidad: 'suave–fuerte–suave', pulsos: 'impulsos con el pulso', libre: 'libre, cómodo' } as any)[medidaDe(e)] || ''}</p>
            </button>
          ))}
          <button onClick={() => { audio(); setFase('sz'); }} className={caja + ' w-full text-left hover:border-[#b39cff]'}>
            <p className="font-bold">Medición s/z <span className="text-xs font-semibold text-[#8d98ad]">· opcional, 2 minutos</span></p>
            <p className="text-sm text-slate-300">Sostené «sss» y «zzz» todo lo que puedas, tres veces cada uno. Así vemos cómo cierra tu voz.</p>
          </button>
        </div>
      )}

      {fase === 'sz' && (
        <MedicionSZ simular={simular} abrirMic={abrirMic}
          clic={(acento?: boolean) => { const c = audio(); clic(c, c.currentTime + 0.02, !!acento); }}
          decir={decir} onGuardar={guardarSZ} onVolver={() => setFase('lista')} />
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
            {hayTono && ej.base_hz
              ? <p>2. Ahora afinamos: escuchá tu nota de inicio (<b>{nota(ej.base_hz)}</b>) y hacé «mmm» en esa misma nota.</p>
              : <p>2. Hacé un «mmm» cómodo unos segundos, sin buscar ninguna nota: así registramos tu voz de hoy.</p>}
            <button onClick={afinar} className={boton}>{hayTono && ej.base_hz ? 'Escuchar y afinar' : 'Empezar'}</button>
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
          <div className="flex items-center gap-4">
            <Escenario color={VISUAL[etapa].color} escala={VISUAL[etapa].escala} nivel={nivel}
              fraccion={etapa === 'cuenta' ? cuentaNum / 3 : (etapa === 'canto' || etapa === 'pausa') && reloj ? reloj.restante / reloj.total : null}
              centro={etapa === 'cuenta' ? cuentaNum : (etapa === 'canto' || etapa === 'pausa') && reloj ? Math.ceil(reloj.restante) : '♪'} />
            <div className="min-w-0 space-y-1">
              <p className="text-xl font-black" style={{ color: VISUAL[etapa].color }}>{VISUAL[etapa].texto}</p>
              <p className="font-semibold min-h-6 text-slate-200" aria-live="polite">{aviso}</p>
            </div>
          </div>
          <canvas ref={canvas} width={640} height={300} className="w-full rounded-2xl bg-black/30" />
          <button onClick={() => { corriendo.current = false; loc.current?.callar(); }} className="w-full py-2 rounded-xl border border-slate-300 dark:border-white/20 text-sm">Terminar</button>
        </div>
      )}

      {fase === 'fin' && resumen && (
        <div className={caja + ' space-y-3 text-sm'}>
          <p className="text-lg font-black">¡Bien hecho!</p>
          <p>{mensajeFinal(resumen)}</p>
          <p className="text-xs text-slate-500">Hoy: {Math.min(hoy, veces)} de {veces} práctica{veces === 1 ? '' : 's'}.</p>
          <button onClick={() => setFase('lista')} className={boton}>Volver a la lista</button>
        </div>
      )}
    </Marco>
  );
}

function mensajeFinal(r: any): string {
  if (!r.voz_pct) return 'No llegamos a escuchar tu voz: probá acercar el celular.';
  if ((r.octava_pct || 0) >= 30) return 'Lo hiciste una octava distinta de la nota: la próxima, escuchá el modelo y buscá la misma altura.';
  const l = r.logro_pct ?? 0;
  const extra = r.medida === 'flujo' || r.medida === 'sostenido' ? ` Tu tramo más largo: ${r.tramo_max_s} s${r.cortes ? `, con ${r.cortes} corte${r.cortes === 1 ? '' : 's'}` : ', sin cortes'}.`
    : r.medida === 'pulsos' ? ` Hiciste ${r.pulsos} impulsos.` : '';
  if (r.medida === 'libre') return 'Listo, quedó registrado. ¡Bien hecho!';
  return (l >= 70 ? '¡Muy bien!' : l >= 40 ? 'Vas bien: con práctica te va a salir cada vez más fácil.' : 'Fue un buen comienzo: hacelo despacio y sin esfuerzo.') + extra;
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    // Siempre nocturno: menos brillo para practicar sin molestar la vista.
    <div className="dark min-h-screen bg-[#0a0e16] text-[#e4e9f2] p-4" style={{ colorScheme: 'dark' }}>
      <div className="max-w-md mx-auto space-y-3">
        {children}
        <p className="text-center text-[11px] text-[#8d98ad] pt-2">Matías Pérez · Fonoaudiólogo</p>
      </div>
    </div>
  );
}
