import React, { useEffect, useRef, useState } from 'react';
import { yin, dbfs } from '../../utils/pitch';
import { Ejercicio, duracion, objetivoSemis, rangoSemis, semisDe, hzDe, Medidor } from '../../utils/guiaPractica';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const PAUSA_S = 2.5;          // respiro entre repeticiones
const UMBRAL_VOZ_DB = -50;    // por debajo: silencio
const RUIDO_ALTO_DB = -45;    // ambiente ruidoso
const MUY_FUERTE_DB = -8;     // volumen muy alto

type Fase = 'lista' | 'ambiente' | 'practica' | 'fin';

/**
 * Práctica guiada del paciente (?practica=<token>): sin login. La voz se
 * analiza en el celular; al servidor solo viajan números del resultado.
 */
export const DEMO = {
  nombre: 'León', estado: 'activa', consentimiento: true, profesional: 'Matías Pérez · Fonoaudiólogo',
  indicaciones: 'Dos veces por día, mañana y tarde.',
  ejercicios: [
    { nombre: 'Glissandos ascendentes y descendentes', guia: 'rampa', base_hz: 110, amplitud: 7, duracion_s: 6, repeticiones: 3, tolerancia_cents: 100, consigna: 'Sirena suave sobre /u/: subí y bajá siguiendo la rampa.' },
    { nombre: 'Escala de cinco notas', guia: 'escalera', base_hz: 110, semitonos: [0, 2, 4, 5, 7, 5, 4, 2, 0], nota_s: 1.2, repeticiones: 2, tolerancia_cents: 100, consigna: 'Subí y bajá los escalones, cómodo.' },
    { nombre: '/m/ sostenida', guia: 'sostenida', base_hz: 110, duracion_s: 6, repeticiones: 3, tolerancia_cents: 100, consigna: '/m/ en tu tono cómodo, pareja y sin esfuerzo.' },
  ],
};

type Props = { token?: string; vistaPrevia?: any; onCerrar?: () => void };

export default function PracticaPaciente({ token = '', vistaPrevia, onCerrar }: Props) {
  // Vista previa (desde la ficha) o demo (?practica=demo): no guarda nada.
  const previa = vistaPrevia || (token === 'demo' ? DEMO : null);
  const [simular, setSimular] = useState(!!previa);
  const [info, setInfo] = useState<any>(previa);
  const [error, setError] = useState('');
  const [acepto, setAcepto] = useState(false);
  const [fase, setFase] = useState<Fase>('lista');
  const [idx, setIdx] = useState(0);
  const [ambiente, setAmbiente] = useState<{ db: number; ok: boolean } | null>(null);
  const [aviso, setAviso] = useState('');
  const [rep, setRep] = useState(0);
  const [resumen, setResumen] = useState<any>(null);
  const [hechos, setHechos] = useState<number[]>([]);
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const audio = useRef<{ ctx: AudioContext; stream: MediaStream; an: AnalyserNode } | null>(null);
  const corriendo = useRef(false);

  useEffect(() => {
    if (previa) return () => detenerAudio();
    fetch(`${BACKEND_URL}/api/practica/${token}`)
      .then(async r => { const j = await r.json(); if (!r.ok) throw new Error(j.detail || 'No se pudo abrir'); return j; })
      .then(setInfo).catch(e => setError(e.message));
    return () => detenerAudio();
  }, [token]);

  const ej: Ejercicio | null = info?.ejercicios?.[idx] || null;

  const abrirMicrofono = async () => {
    if (audio.current) return audio.current;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    const ctx = new AudioContext();
    const an = ctx.createAnalyser();
    an.fftSize = 2048;
    ctx.createMediaStreamSource(stream).connect(an);
    audio.current = { ctx, stream, an };
    return audio.current;
  };

  function detenerAudio() {
    corriendo.current = false;
    audio.current?.stream.getTracks().forEach(t => t.stop());
    audio.current?.ctx.close().catch(() => {});
    audio.current = null;
  }

  const aceptar = async () => {
    const r = await fetch(`${BACKEND_URL}/api/practica/${token}/consentimiento`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ acepta: true }),
    });
    if (r.ok) setInfo((i: any) => ({ ...i, consentimiento: true }));
    else setError('No se pudo registrar. Probá de nuevo.');
  };

  /** Nota de referencia: 1,2 s de tono suave en el tono de inicio. */
  const escucharNota = (hz: number) => {
    const ctx = new AudioContext();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'sine'; o.frequency.value = hz;
    g.gain.setValueAtTime(0, ctx.currentTime);
    g.gain.linearRampToValueAtTime(0.25, ctx.currentTime + 0.05);
    g.gain.linearRampToValueAtTime(0, ctx.currentTime + 1.2);
    o.connect(g).connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime + 1.25);
    setTimeout(() => ctx.close(), 1500);
  };

  /** 3 segundos en silencio para medir el ruido del ambiente. */
  const medirAmbiente = async () => {
    setFase('ambiente'); setAviso('');
    if (simular) { setAmbiente({ db: -60, ok: true }); return; }
    try {
      const { an } = await abrirMicrofono();
      const buf = new Float32Array(an.fftSize);
      const muestras: number[] = [];
      const fin = Date.now() + 3000;
      await new Promise<void>(res => {
        const t = setInterval(() => {
          an.getFloatTimeDomainData(buf); muestras.push(dbfs(buf));
          if (Date.now() > fin) { clearInterval(t); res(); }
        }, 100);
      });
      const ord = muestras.sort((a, b) => a - b);
      const db = Math.round(ord[Math.floor(ord.length / 2)]);
      setAmbiente({ db, ok: db < RUIDO_ALTO_DB });
    } catch {
      setError('No se pudo usar el micrófono. Revisá el permiso del navegador y volvé a intentar.');
      setFase('lista');
    }
  };

  const practicar = async () => {
    if (!ej) return;
    const mic = simular ? null : await abrirMicrofono().catch(() => null);
    if (!simular && !mic) { setError('No se pudo usar el micrófono. Revisá el permiso del navegador.'); return; }
    const sr = mic ? mic.ctx.sampleRate : 48000;
    setFase('practica'); setResumen(null);
    corriendo.current = true;
    const buf = new Float32Array(2048);
    const med = new Medidor();
    const d = duracion(ej), ciclo = d + PAUSA_S, total = ciclo * ej.repeticiones;
    const [lo, hi] = rangoSemis(ej);
    const minHz = Math.max(60, hzDe(lo - 6, ej.base_hz)), maxHz = Math.min(1200, hzDe(hi + 6, ej.base_hz));
    const inicio = performance.now();
    const rastro: { x: number; s: number | null }[] = [];

    const dibujar = (t: number, semis: number | null, dentro: boolean) => {
      const c = canvas.current; if (!c) return;
      const g = c.getContext('2d')!; const W = c.width, H = c.height;
      const y = (s: number) => H - 16 - ((s - lo) / (hi - lo)) * (H - 32);
      const oscuro = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
      g.clearRect(0, 0, W, H);
      const tol = ej.tolerancia_cents / 100;
      g.fillStyle = oscuro ? 'rgba(29,158,117,0.35)' : 'rgba(93,202,165,0.45)';
      for (let x = 0; x < W; x += 3) {
        const s = objetivoSemis(ej, (x / W) * d);
        g.fillRect(x, y(s + tol), 3, Math.max(4, y(s - tol) - y(s + tol)));
      }
      g.strokeStyle = oscuro ? '#5DCAA5' : '#0F6E56'; g.lineWidth = 1.5; g.beginPath();
      rastro.forEach((p, i) => { if (p.s == null) return; const yy = y(p.s); i && rastro[i - 1].s != null ? g.lineTo(p.x, yy) : g.moveTo(p.x, yy); });
      g.stroke();
      const x = (t / d) * W;
      g.fillStyle = oscuro ? '#888' : '#bbb'; g.fillRect(x, 0, 1, H);
      if (semis != null) {
        g.beginPath(); g.arc(x, y(Math.max(lo, Math.min(hi, semis))), 13, 0, Math.PI * 2);
        g.fillStyle = dentro ? '#1D9E75' : '#D85A30'; g.fill();
      }
    };

    await new Promise<void>(res => {
      const tick = () => {
        if (!corriendo.current) return res();
        const ahora = (performance.now() - inicio) / 1000;
        if (ahora >= total) return res();
        const r = Math.floor(ahora / ciclo), t = ahora - r * ciclo;
        setRep(r + 1);
        let db: number, hz: number | null;
        if (mic) {
          mic.an.getFloatTimeDomainData(buf);
          db = dbfs(buf);
          hz = db > UMBRAL_VOZ_DB ? yin(buf, sr, minHz, maxHz) : null;
        } else {                           // voz simulada (vista previa)
          db = -25;
          const tt = Math.min(t, d);
          hz = t > d ? null : hzDe(objetivoSemis(ej, tt) + Math.sin(ahora * 2.3) * 0.6 + (Math.random() - 0.5) * 0.4, ej.base_hz);
        }
        if (t > d) {                       // pausa para respirar
          setAviso('Respirá…'); rastro.length = 0; dibujar(d, null, false);
        } else {
          const objetivo = hzDe(objetivoSemis(ej, t), ej.base_hz);
          med.agregar(hz, objetivo, ej.tolerancia_cents);
          const semis = hz ? semisDe(hz, ej.base_hz) : null;
          const dentro = hz != null && Math.abs(1200 * Math.log2(hz / objetivo)) <= ej.tolerancia_cents;
          rastro.push({ x: (t / d) * (canvas.current?.width || 600), s: semis });
          setAviso(db > MUY_FUERTE_DB ? 'Más suave: no hace falta fuerza' : hz == null ? '' : dentro ? 'Muy bien' : semis! > objetivoSemis(ej, t) ? 'Un poco más grave' : 'Un poco más agudo');
          dibujar(t, semis, dentro);
        }
        setTimeout(tick, 50);
      };
      tick();
    });
    const fueCompleto = corriendo.current;
    corriendo.current = false;
    const res = med.resumen(Math.min(total, (performance.now() - inicio) / 1000), ej.repeticiones);
    setResumen(res); setFase('fin');
    if (previa) { setHechos(h => [...new Set([...h, idx])]); return; }
    if (fueCompleto || (res.voz_pct || 0) > 0) {
      fetch(`${BACKEND_URL}/api/practica/${token}/sesion`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resultados: [{ ejercicio: idx, ...res }], ambiente: ambiente ? { ruido_dbfs: ambiente.db, silencioso: ambiente.ok } : {} }),
      }).then(r => { if (r.ok) setHechos(h => [...new Set([...h, idx])]); }).catch(() => {});
    }
  };

  const caja = 'bg-white dark:bg-white/5 rounded-2xl border border-slate-200 dark:border-white/10 p-5';
  const boton = 'w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-50';

  if (error) return <Marco><div className={caja}><p className="text-red-600">{error}</p></div></Marco>;
  if (!info) return <Marco><p className="text-slate-500">Cargando…</p></Marco>;
  if (info.estado !== 'activa') return <Marco><div className={caja}><p>Esta práctica está {info.estado}. Pedile una nueva a tu fonoaudiólogo.</p></div></Marco>;

  if (!info.consentimiento) return (
    <Marco>
      <div className={caja + ' space-y-3 text-sm'}>
        <h1 className="text-lg font-black">Hola{info.nombre ? ` ${info.nombre}` : ''}</h1>
        <p>Esta es tu práctica de voz indicada por {info.profesional}. Mientras practicás, una pelotita sigue tu voz para guiarte.</p>
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

  return (
    <Marco>
      {previa && (
        <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-300 text-xs space-y-1.5">
          <p className="font-bold text-amber-800 dark:text-amber-200">Vista previa: así lo ve el paciente (no se guarda nada)</p>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={simular} onChange={e => { detenerAudio(); setSimular(e.target.checked); }} />
            Simular la voz (sin micrófono). Desmarcalo para probar con tu voz.</label>
          {onCerrar && <button onClick={() => { detenerAudio(); onCerrar(); }} className="text-indigo-600 font-semibold">Cerrar vista previa</button>}
        </div>
      )}
      {fase === 'lista' && (
        <div className="space-y-3">
          <div className={caja}>
            <h1 className="text-lg font-black">Hola{info.nombre ? ` ${info.nombre}` : ''}, tu práctica de hoy</h1>
            {info.indicaciones && <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{info.indicaciones}</p>}
            <p className="text-xs text-slate-500 mt-2">Buscá un lugar tranquilo. Si sentís molestia o esfuerzo, pará y descansá.</p>
          </div>
          {info.ejercicios.map((e: Ejercicio, i: number) => (
            <button key={i} onClick={() => { setIdx(i); medirAmbiente(); }}
              className={caja + ' w-full text-left hover:border-indigo-400'}>
              <p className="font-bold">{i + 1}. {e.nombre} {hechos.includes(i) && <span className="text-emerald-600 text-sm">✓ hecho</span>}</p>
              {e.consigna && <p className="text-sm text-slate-600 dark:text-slate-300">{e.consigna}</p>}
              <p className="text-xs text-slate-500 mt-1">{e.repeticiones} repeticiones</p>
            </button>
          ))}
        </div>
      )}

      {fase === 'ambiente' && ej && (
        <div className={caja + ' space-y-3 text-sm'}>
          <p className="font-bold">{ej.nombre}</p>
          {!ambiente ? <p>Quedate en silencio 3 segundos: estamos escuchando el ambiente…</p> : (
            <>
              <p className={ambiente.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}>
                {ambiente.ok ? 'El lugar está tranquilo.' : 'Hay bastante ruido: si podés, buscá un lugar más silencioso (igual podés seguir).'}
              </p>
              {ej.consigna && <p>{ej.consigna}</p>}
              <button onClick={() => escucharNota(ej.base_hz)} className="w-full py-2.5 rounded-xl border border-indigo-300 text-indigo-700 dark:text-indigo-300 font-semibold">
                Escuchar la nota de inicio
              </button>
              <button onClick={practicar} className={boton}>Empezar ejercicio</button>
              <button onClick={() => { setAmbiente(null); setFase('lista'); }} className="w-full text-slate-500 text-xs">Volver</button>
            </>
          )}
        </div>
      )}

      {fase === 'practica' && ej && (
        <div className={caja + ' space-y-2'}>
          <div className="flex justify-between text-sm"><b>{ej.nombre}</b><span className="text-slate-500">Repetición {rep} de {ej.repeticiones}</span></div>
          <canvas ref={canvas} width={640} height={300} className="w-full rounded-xl bg-slate-50 dark:bg-black/30" />
          <p className="text-center font-semibold h-6">{aviso}</p>
          <button onClick={() => { corriendo.current = false; }} className="w-full py-2 rounded-xl border border-slate-300 dark:border-white/20 text-sm">Terminar</button>
        </div>
      )}

      {fase === 'fin' && resumen && (
        <div className={caja + ' space-y-3 text-sm'}>
          <p className="text-lg font-black">¡Bien hecho!</p>
          <p>{resumen.dentro_pct == null ? 'No llegamos a escuchar tu voz: probá acercar el celular.'
            : resumen.dentro_pct >= 70 ? 'Seguiste muy bien el camino.'
            : resumen.dentro_pct >= 40 ? 'Vas bien: con práctica te va a salir cada vez más fácil.'
            : 'Fue un buen comienzo. Hacelo despacio y sin esfuerzo.'}</p>
          <button onClick={() => { setAmbiente(null); setFase('lista'); }} className={boton}>Volver a la lista</button>
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
