import React, { useEffect, useRef, useState } from 'react';
import { dbfs } from '../../utils/pitch';

/** Paleta nocturna de la guía del paciente (una sola apariencia, a propósito). */
export const NOCHE = {
  fondo: '#0a0e16', superficie: '#121a28', linea: '#233047', texto: '#e4e9f2', tenue: '#8d98ad',
  inhala: '#6aa8ff', sonido: '#b39cff', descanso: '#5fd3b4', atencion: '#f1b56a', alerta: '#f2848f',
};

const reducido = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const dormir = (ms: number) => new Promise(r => setTimeout(r, ms));
const coma = (v: number) => v.toFixed(1).replace('.', ',');

// Puntos repartidos sobre una esfera (espiral de Fibonacci).
const PUNTOS = Array.from({ length: 420 }, (_, i) => {
  const y = 1 - (i / 419) * 2, r = Math.sqrt(1 - y * y), th = i * 2.399963;
  return [Math.cos(th) * r, y, Math.sin(th) * r];
});

/**
 * Esfera 3D de puntos que "respira": crece al inhalar, se mueve con la voz
 * (`nivel`, 0..1, leído en cada cuadro sin re-render) y toma el color de la fase.
 */
export function Orbe({ color, escala, nivel }: { color: string; escala: number; nivel?: React.MutableRefObject<number> }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const props = useRef({ color, escala });
  props.current = { color, escala };
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const g = cv.getContext('2d'); if (!g) return;
    let actual = escala, giro = 0, pulso = 0, raf = 0;
    const quieto = reducido();
    const cuadro = () => {
      const w = cv.clientWidth, h = cv.clientHeight, dpr = window.devicePixelRatio || 1;
      if (cv.width !== Math.round(w * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
      g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
      const objetivo = props.current.escala + (nivel?.current || 0) * 0.3;
      actual += (objetivo - actual) * 0.08;
      if (!quieto) { giro += 0.006; pulso += 0.05; }
      const R = Math.min(w, h) * 0.36 * actual * (1 + Math.sin(pulso) * 0.015);
      const c = Math.cos(giro), s = Math.sin(giro), ci = Math.cos(0.45), si = Math.sin(0.45);
      const pts = PUNTOS.map(([x, y, z]) => {
        const X = x * c - z * s; let Z = x * s + z * c;
        const Y = y * ci - Z * si; Z = y * si + Z * ci;
        const p = 2.6 / (2.6 + Z);
        return [w / 2 + X * R * p, h / 2 + Y * R * p, Z];
      }).sort((a, b) => b[2] - a[2]);
      g.fillStyle = props.current.color;
      for (const [x, y, z] of pts) {
        g.globalAlpha = 0.18 + (1 - (z + 1) / 2) * 0.75;
        g.beginPath(); g.arc(x, y, 0.9 + (1 - z) * 0.55, 0, 6.3); g.fill();
      }
      g.globalAlpha = 1;
      raf = requestAnimationFrame(cuadro);
    };
    raf = requestAnimationFrame(cuadro);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <canvas ref={ref} className="absolute inset-0 w-full h-full" aria-hidden="true" />;
}

/** Anillo de cuenta regresiva: se vacía a medida que pasa el tiempo. */
export function AnilloCuenta({ fraccion, color }: { fraccion: number; color: string }) {
  const f = Math.max(0, Math.min(1, fraccion));
  return (
    <svg viewBox="0 0 100 100" className="absolute inset-[4%] w-[92%] h-[92%] -rotate-90" aria-hidden="true">
      <circle cx="50" cy="50" r="45" fill="none" stroke={NOCHE.linea} strokeWidth="5" />
      <circle cx="50" cy="50" r="45" fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
        pathLength={100} strokeDasharray="100" strokeDashoffset={100 - f * 100}
        style={{ transition: reducido() ? 'none' : 'stroke .4s' }} />
    </svg>
  );
}

/** Esfera + anillo + número central: el "escenario" de cada fase. */
export function Escenario({ color, escala, fraccion, centro, nivel, tamano = 'w-32 h-32' }: {
  color: string; escala: number; fraccion: number | null; centro: React.ReactNode;
  nivel?: React.MutableRefObject<number>; tamano?: string;
}) {
  return (
    <div className={`relative shrink-0 ${tamano}`}>
      <Orbe color={color} escala={escala} nivel={nivel} />
      {fraccion != null && <AnilloCuenta fraccion={fraccion} color={color} />}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none" aria-live="polite">
        <span className="text-4xl font-black tabular-nums" style={{ color: NOCHE.texto }}>{centro}</span>
      </div>
    </div>
  );
}

// ─── Índice s/z ─────────────────────────────────────────────────────────

export function lecturaSZ(v: number): { color: string; texto: string } {
  if (v >= 0.8 && v <= 1.2) return { color: NOCHE.descanso, texto: 'Equilibrado' };
  if (v > 1.4) return { color: NOCHE.alerta, texto: 'La /z/ te dura bastante menos que la /s/: lo vemos en la próxima sesión' };
  if (v > 1.2) return { color: NOCHE.atencion, texto: 'La /z/ te dura un poco menos que la /s/' };
  return { color: NOCHE.atencion, texto: 'La /s/ te dura menos que la /z/: revisemos la respiración' };
}

/** Semicírculo de 0,4 a 2,0 con zonas de color y aguja. */
export function MedidorIndice({ valor, compacto = false }: { valor: number | null; compacto?: boolean }) {
  const polar = (v: number) => {
    const t = (Math.min(2, Math.max(0.4, v)) - 0.4) / 1.6, a = Math.PI * (1 - t);
    return [120 + Math.cos(a) * 100, 128 - Math.sin(a) * 100];
  };
  const arco = (a: number, b: number) => { const [x1, y1] = polar(a), [x2, y2] = polar(b); return `M${x1} ${y1} A100 100 0 0 1 ${x2} ${y2}`; };
  const zonas: [number, number, string][] = [[0.4, 0.8, NOCHE.atencion], [0.8, 1.2, NOCHE.descanso], [1.2, 1.4, NOCHE.atencion], [1.4, 2, NOCHE.alerta]];
  const lect = valor != null ? lecturaSZ(valor) : null;
  const [ax, ay] = valor != null ? polar(valor) : [120, 128];
  return (
    <div className="flex flex-col items-center text-center gap-1">
      <svg viewBox="0 0 240 140" className={compacto ? 'w-40' : 'w-full max-w-xs'} role="img"
        aria-label={valor != null ? `Índice s/z ${coma(valor)}` : 'Índice s/z sin datos'}>
        <path d={arco(0.4, 2)} fill="none" stroke="currentColor" strokeOpacity=".15" strokeWidth="14" strokeLinecap="round" />
        {zonas.map(([a, b, c]) => <path key={a} d={arco(a, b)} fill="none" stroke={c} strokeWidth="8" opacity=".85" />)}
        {valor != null && <>
          <line x1="120" y1="128" x2={ax} y2={ay} stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          <circle cx="120" cy="128" r="5" fill="currentColor" />
          <circle cx={ax} cy={ay} r="6" fill={lect!.color} />
        </>}
        <text x="20" y="138" textAnchor="middle" fontSize="11" fill="currentColor" opacity=".6">0,4</text>
        <text x="120" y="13" textAnchor="middle" fontSize="11" fill="currentColor" opacity=".6">1,2</text>
        <text x="220" y="138" textAnchor="middle" fontSize="11" fill="currentColor" opacity=".6">2,0</text>
      </svg>
      {!compacto && <>
        <span className="text-3xl font-black tabular-nums" style={{ color: lect?.color }}>{valor != null ? coma(valor) : '–'}</span>
        <span className="font-semibold text-sm">{lect ? lect.texto : 'Faltan mediciones'}</span>
      </>}
    </div>
  );
}

type Mic = { an: AnalyserNode };
type PropsSZ = {
  simular: boolean;
  abrirMic: () => Promise<Mic>;
  clic: (acento?: boolean) => void;
  decir: (clave: string, texto: string) => Promise<any>;
  onGuardar: (s: number[], z: number[]) => Promise<boolean>;
  onVolver: () => void;
};

/**
 * Medición del índice s/z: tres intentos de /s/ y tres de /z/. Cuenta 3-2-1
 * (mientras toma aire se escucha el ambiente), después el micrófono detecta
 * solo el principio y el final del sonido. El botón «Listo» corta a mano.
 */
export function MedicionSZ({ simular, abrirMic, clic, decir, onGuardar, onVolver }: PropsSZ) {
  const [son, setSon] = useState<'s' | 'z'>('s');
  const [datos, setDatos] = useState<{ s: number[]; z: number[] }>({ s: [], z: [] });
  const [estado, setEstado] = useState<'quieto' | 'cuenta' | 'midiendo' | 'guardando' | 'guardado'>('quieto');
  const [cuenta, setCuenta] = useState(3);
  const [seg, setSeg] = useState(0);
  const [pista, setPista] = useState('Tocá Empezar: cuento 3, 2, 1 y arrancás.');
  const nivel = useRef(0);
  const control = useRef({ cancelado: false, listo: false });

  useEffect(() => () => { control.current.cancelado = true; }, []);

  const intento = async () => {
    control.current = { cancelado: false, listo: false };
    let an: AnalyserNode | null = null;
    if (!simular) {
      try { an = (await abrirMic()).an; } catch { setPista('No se pudo usar el micrófono: revisá el permiso del navegador.'); return; }
    }
    const buf = new Float32Array(2048);
    const ambiente: number[] = [];
    setEstado('cuenta'); setSeg(0);
    await decir(son === 's' ? 'sz_s' : 'sz_z', son === 's' ? 'Tomá aire y hacé sss todo lo que puedas.' : 'Tomá aire y hacé zzz, como una abeja, todo lo que puedas.');
    for (let n = 3; n >= 1; n--) {
      if (control.current.cancelado) return;
      setCuenta(n); setPista('Tomá aire por la nariz, sin levantar los hombros'); clic(n === 1);
      const fin = Date.now() + 1000;
      while (Date.now() < fin) { if (an) { an.getFloatTimeDomainData(buf); ambiente.push(dbfs(buf)); } await dormir(40); }
    }
    if (control.current.cancelado) return;
    setEstado('midiendo'); setPista(`¡Ya! «${son === 's' ? 'sssss' : 'zzzzz'}»… se corta solo cuando terminás`);
    const amb = ambiente.length ? [...ambiente].sort((a, b) => a - b)[Math.floor(ambiente.length / 2)] : -60;
    const umbral = Math.max(-55, amb + 12);
    const t0 = performance.now();
    let ini: number | null = null, ultimo: number | null = null, seguidos = 0, dur = 0;
    const simDur = 12 + Math.random() * 9;
    while (!control.current.cancelado) {
      const ahora = (performance.now() - t0) / 1000;
      let suena: boolean;
      if (an) { an.getFloatTimeDomainData(buf); const db = dbfs(buf); suena = db > umbral; nivel.current = suena ? Math.min(1, (db - umbral) / 25) : 0; }
      else { const tt = ahora * 3; suena = tt > 0.4 && tt < simDur; nivel.current = suena ? 0.5 : 0; } // simulación acelerada
      const tEscala = an ? ahora : ahora * 3;
      if (suena) { seguidos++; if (ini == null && seguidos >= 3) ini = tEscala - 0.08; ultimo = tEscala; } else seguidos = 0;
      if (ini != null) setSeg(Math.max(0, (suena ? tEscala : ultimo!) - ini));
      if (control.current.listo) { dur = ini != null ? (suena ? tEscala : ultimo!) - ini : 0; break; }
      if (ini != null && tEscala - (ultimo || 0) > 0.6) { dur = ultimo! - ini; break; }
      if (ini == null && tEscala > 8) break;   // no se escuchó nada
      if (tEscala > 90) { dur = (ultimo || tEscala) - (ini || 0); break; }
      await dormir(40);
    }
    nivel.current = 0;
    if (control.current.cancelado) return;
    setEstado('quieto');
    if (dur >= 1) {
      const v = Math.round(dur * 10) / 10;
      setSeg(v); setDatos(d => ({ ...d, [son]: [...d[son], v] }));
      setPista(`Guardado: ${coma(v)} s. Descansá unos segundos antes del próximo.`);
      decir('sz_bien', 'Muy bien.');
    } else {
      setSeg(0); setPista('No llegué a escucharte: acercá el celular y probá de nuevo.');
    }
  };

  const n = datos[son].length;
  const otro = son === 's' ? 'z' : 's';
  const completo = datos.s.length >= 3 && datos.z.length >= 3;
  const indice = datos.s.length && datos.z.length ? Math.max(...datos.s) / Math.max(...datos.z) : null;
  const tope = Math.max(25, ...datos.s, ...datos.z);
  const ocupado = estado === 'cuenta' || estado === 'midiendo';
  const color = son === 's' ? NOCHE.inhala : NOCHE.sonido;

  const guardar = async () => {
    setEstado('guardando');
    const ok = await onGuardar(datos.s, datos.z);
    setEstado(ok ? 'guardado' : 'quieto');
    if (!ok) setPista('No se pudo guardar: revisá la conexión y probá de nuevo.');
  };

  return (
    <div className="rounded-3xl border p-5 space-y-4 text-sm" style={{ background: NOCHE.superficie, borderColor: NOCHE.linea }}>
      <div className="flex justify-between items-baseline gap-2">
        <p className="text-lg font-black">Medición s/z</p>
        <span className="text-xs" style={{ color: NOCHE.tenue }}>3 intentos de cada sonido</span>
      </div>
      <p style={{ color: NOCHE.tenue }}>Sostené el sonido todo lo que puedas, sin forzar. Se guarda el mejor intento de cada uno.</p>

      <div className="grid grid-cols-2 gap-2" role="group" aria-label="Sonido a medir">
        {(['s', 'z'] as const).map(k => (
          <button key={k} disabled={ocupado} onClick={() => { setSon(k); setSeg(0); setPista('Tocá Empezar: cuento 3, 2, 1 y arrancás.'); }}
            aria-pressed={son === k}
            className="text-left rounded-2xl border p-3 disabled:opacity-60"
            style={{ borderColor: son === k ? NOCHE.sonido : NOCHE.linea, background: son === k ? '#b39cff14' : 'transparent' }}>
            <b className="text-xl">/{k}/</b> <span className="text-xs" style={{ color: NOCHE.tenue }}>{datos[k].length}/3</span>
            <span className="block text-xs" style={{ color: NOCHE.tenue }}>{k === 's' ? 'como «sssss», sin voz' : 'como una abeja «zzzz», con voz'}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-col items-center gap-2">
        <Escenario tamano="w-44 h-44" color={estado === 'cuenta' ? NOCHE.tenue : color}
          escala={estado === 'cuenta' ? 0.9 : estado === 'midiendo' ? 0.7 : 0.6}
          fraccion={estado === 'cuenta' ? cuenta / 3 : estado === 'midiendo' ? Math.min(1, seg / 25) : null}
          nivel={nivel} centro={estado === 'cuenta' ? cuenta : coma(seg)} />
        <p className="text-center font-semibold min-h-10" aria-live="polite">{pista}</p>
      </div>

      {estado === 'midiendo' ? (
        <button onClick={() => { control.current.listo = true; }} className="w-full py-3.5 rounded-2xl font-bold" style={{ background: NOCHE.alerta, color: '#2a0d12' }}>Listo, se me acabó el aire</button>
      ) : estado === 'cuenta' ? (
        <button onClick={() => { control.current.cancelado = true; setEstado('quieto'); setPista('Cancelado.'); }} className="w-full py-3 rounded-2xl border font-semibold" style={{ borderColor: NOCHE.linea }}>Cancelar</button>
      ) : n < 3 ? (
        <button onClick={intento} className="w-full py-3.5 rounded-2xl font-bold" style={{ background: NOCHE.sonido, color: '#140f26' }}>
          Empezar intento {n + 1} de /{son}/
        </button>
      ) : !completo ? (
        <button onClick={() => { setSon(otro); setSeg(0); }} className="w-full py-3.5 rounded-2xl font-bold" style={{ background: NOCHE.sonido, color: '#140f26' }}>Seguir con /{otro}/</button>
      ) : null}

      {(datos.s.length > 0 || datos.z.length > 0) && (
        <div className="grid grid-cols-[auto_1fr_auto] gap-x-3 gap-y-1.5 items-center">
          {(['s', 'z'] as const).flatMap(k => [0, 1, 2].map(i => {
            const v = datos[k][i], mejor = v != null && v === Math.max(...datos[k]);
            return (
              <React.Fragment key={k + i}>
                <span className="tabular-nums text-xs" style={{ color: NOCHE.tenue }}>/{k}/ {i + 1}</span>
                <div className="h-2.5 rounded-full overflow-hidden" style={{ background: NOCHE.linea }}>
                  <div className="h-full rounded-full" style={{ width: `${v ? (v / tope) * 100 : 0}%`, background: k === 's' ? NOCHE.inhala : NOCHE.sonido }} />
                </div>
                <span className="tabular-nums text-xs">{v != null ? `${coma(v)} s` : '–'}{mejor && <b className="ml-1 text-[10px]" style={{ color: NOCHE.descanso }}>MEJOR</b>}</span>
              </React.Fragment>
            );
          }))}
        </div>
      )}

      <div style={{ color: NOCHE.texto }}><MedidorIndice valor={indice} /></div>
      <p className="text-xs border-t pt-3" style={{ color: NOCHE.tenue, borderColor: NOCHE.linea }}>
        El índice divide tu mejor /s/ por tu mejor /z/. Cerca de 1 es lo esperable. Tu fonoaudiólogo revisa el resultado; no es un diagnóstico.
      </p>

      {estado === 'guardado' ? (
        <p className="text-center font-semibold" style={{ color: NOCHE.descanso }}>✓ Medición guardada</p>
      ) : (datos.s.length > 0 && datos.z.length > 0) && !ocupado && (
        <button onClick={guardar} disabled={estado === 'guardando'} className="w-full py-3 rounded-2xl font-bold disabled:opacity-60" style={{ background: NOCHE.descanso, color: '#062018' }}>
          {estado === 'guardando' ? 'Guardando…' : completo ? 'Guardar medición' : 'Guardar lo medido hasta ahora'}
        </button>
      )}
      <button onClick={() => { control.current.cancelado = true; onVolver(); }} className="w-full text-xs" style={{ color: NOCHE.tenue }}>Volver a la lista</button>
    </div>
  );
}
