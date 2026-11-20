import React, { useEffect, useRef, useState } from 'react';
import type { Paso } from '../../utils/guiaPractica';
import { NOCHE } from './visuales';

/**
 * Animaciones de la práctica con tiempo: una escena por tipo de trabajo
 * (boca, respiración, cuello y hombros, puntos de masaje, laringe, vibración).
 *
 * El movimiento lo marca el reloj del paso: la apertura / inspiración avanza
 * mientras corre la cuenta y el cierre / exhalación es LENTO y con curva suave
 * (nunca de golpe), para que el modelo visual sea de relajación. Mientras se
 * escucha la indicación, la figura queda quieta en la posición de partida.
 */

type Escena = 'boca' | 'respira' | 'cuello' | 'puntos' | 'laringe' | 'vibra';

const n = (t: string) => (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const suave = (u: number) => 0.5 - Math.cos(Math.PI * Math.max(0, Math.min(1, u))) / 2;   // ease-in-out
const reducido = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

const BOCA = ['apertura_fondo_boca', 'moldeado_vertical'];
const RESPIRA = ['respiracion_abdominal', 'expansion_costo_lateral', 'soplo_escalonado', 'respiracion_dinamica', 'le_huche'];

/** Qué escena corresponde a este paso (por el ejercicio y por lo que dice la indicación). */
export function escenaDe(bankId: string | null | undefined, paso: Paso, anterior?: Escena): Escena {
  const t = n(paso.texto), id = bankId || '';
  if (/bostez|abri la boca|apertura|o . a . o|hola, como|suspiro/.test(t)) return 'boca';
  if (/laringe|traga/.test(t) || id === 'masaje_laringeo') return 'laringe';
  if (/coronilla|vertex|sien|entrecejo|mandibula|masetero|labios|cuello, a los costados/.test(t) || id === 'shiatsu_cabeza') return 'puntos';
  if (/hombro|cabeza|menton|oreja|cuello y hombros/.test(t) || id === 'rotacion_hombros') return 'cuello';
  if (/brrr|trino|mmm|bbb|vibracion|sirena|contra la mano/.test(t) || id === 'b_prolongada' || id === 'mano_boca') return 'vibra';
  if (paso.tipo === 'descanso' && anterior) return anterior;   // descansar = soltar lo que se venía haciendo
  if (BOCA.includes(id) || /cerra suave|sin apretar/.test(t)) return 'boca';
  if (id === 'masaje_laringeo' || id === 'descenso_laringeo') return 'laringe';
  if (['inhala', 'exhala', 'retiene'].includes(paso.tipo) || RESPIRA.includes(id) || /respir|aire|inspira/.test(t)) return 'respira';
  return paso.tipo === 'descanso' && anterior ? anterior : 'respira';
}

/** Apertura (0 cerrado … 1 abierto) en el segundo `s` del paso. */
function apertura(tipo: Paso['tipo'], s: number, seg: number, desde: number) {
  if (tipo === 'exhala' || tipo === 'descanso') {
    const dur = Math.min(Math.max(2, seg * 0.9), tipo === 'exhala' ? seg : 6);   // cierre lento
    return desde * (1 - suave(s / dur));
  }
  const dur = tipo === 'inhala' ? Math.max(1.5, seg * 0.95) : tipo === 'retiene' ? 0.6 : Math.min(3, Math.max(1.2, seg * 0.5));
  return desde + (1 - desde) * suave(s / dur);
}

export function AnimacionPaso({ bankId, paso, clave, corriendo, color }: {
  bankId?: string | null; paso: Paso; clave: string; corriendo: boolean; color: string;
}) {
  const [, setCuadro] = useState(0);
  const est = useRef({ clave: '', desde: 0, valor: 0, inicio: 0, escena: undefined as Escena | undefined, corria: false });
  const e = est.current;
  if (e.clave !== clave) {
    e.clave = clave; e.desde = e.valor; e.inicio = 0; e.corria = false;
    e.escena = escenaDe(bankId, paso, e.escena);
  }
  if (corriendo && !e.corria) { e.corria = true; e.inicio = performance.now(); }

  useEffect(() => {
    let raf = 0;
    const loop = () => { setCuadro(c => (c + 1) % 1e6); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  const ahora = performance.now() / 1000;
  const s = e.corria ? (performance.now() - e.inicio) / 1000 : 0;
  const o = e.corria ? apertura(paso.tipo, s, paso.segundos, e.desde) : e.desde;
  e.valor = o;
  const quieto = reducido();
  const vivo = quieto ? 0 : 1;                     // micro-movimientos (respiración de fondo, ondas)
  const mov = e.corria && paso.tipo !== 'descanso' ? 1 : 0;   // movimientos rítmicos solo con el reloj corriendo
  const props = { o, t: ahora, s, vivo, mov, color, texto: n(paso.texto), tipo: paso.tipo, bankId: bankId || '' };

  return (
    <svg viewBox="0 0 200 200" className="w-full h-full" role="img" aria-label={paso.texto}>
      <defs>
        <radialGradient id="anim-piel" cx="38%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#3a4c74" /><stop offset="55%" stopColor="#1d2840" /><stop offset="100%" stopColor="#0d1320" />
        </radialGradient>
        <radialGradient id="anim-boca" cx="50%" cy="40%" r="65%">
          <stop offset="0%" stopColor="#3b1220" /><stop offset="100%" stopColor="#12060b" />
        </radialGradient>
        <radialGradient id="anim-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" /><stop offset="100%" stopColor={color} stopOpacity="0" />
        </radialGradient>
        <filter id="anim-brillo" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.2" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>
      <circle cx="100" cy="100" r="96" fill="url(#anim-halo)" />
      <ellipse cx="100" cy="192" rx="62" ry="5" fill="#000" opacity="0.35" />
      {e.escena === 'boca' && <Boca {...props} />}
      {e.escena === 'respira' && <Respira {...props} />}
      {e.escena === 'cuello' && <Cuello {...props} />}
      {e.escena === 'puntos' && <Puntos {...props} />}
      {e.escena === 'laringe' && <Laringe {...props} />}
      {e.escena === 'vibra' && <Vibra {...props} />}
    </svg>
  );
}

type P = { o: number; t: number; s: number; vivo: number; mov: number; color: string; texto: string; tipo: Paso['tipo']; bankId: string };

/** Cabeza de frente con relieve (luz arriba a la izquierda). */
function Cabeza({ cx = 100, cy = 88, alarga = 0, color, ojos = true, rot = 0, giro = 0 }: {
  cx?: number; cy?: number; alarga?: number; color: string; ojos?: boolean; rot?: number; giro?: number;
}) {
  const rx = 50 * (1 - Math.abs(giro) * 0.12);
  return (
    <g transform={`rotate(${rot} ${cx} ${cy + 60})`}>
      <ellipse cx={cx} cy={cy + alarga / 2} rx={rx} ry={60 + alarga / 2} fill="url(#anim-piel)" stroke={color} strokeOpacity="0.55" strokeWidth="1.5" />
      <ellipse cx={cx - rx - 2} cy={cy + 6} rx="6" ry="11" fill="#1a2438" stroke={color} strokeOpacity="0.35" opacity={1 - Math.max(0, giro) * 0.9} />
      <ellipse cx={cx + rx + 2} cy={cy + 6} rx="6" ry="11" fill="#1a2438" stroke={color} strokeOpacity="0.35" opacity={1 + Math.min(0, giro) * 0.9} />
      {ojos && <g stroke={NOCHE.texto} strokeOpacity="0.75" strokeWidth="2" fill="none" strokeLinecap="round" transform={`translate(${giro * 14} 0)`}>
        <path d={`M${cx - 26} ${cy - 4} q9 6 18 0`} /><path d={`M${cx + 8} ${cy - 4} q9 6 18 0`} />
        <path d={`M${cx} ${cy + 4} q-3 12 2 16`} strokeOpacity="0.35" />
      </g>}
    </g>
  );
}

/** Apertura de la boca y del fondo: mandíbula que baja, lengua plana y paladar blando que sube. */
function Boca({ o, t, s, vivo, mov, color, tipo, texto }: P) {
  let a = o;
  if (tipo === 'sonido' && /o . a|hola/.test(texto)) a = o * (0.72 + 0.28 * Math.sin(s * 2.6) * mov);   // vocales encadenadas
  const baja = a * 16;
  const my = 124 + baja * 0.7, ry = 2.5 + a * 19, rx = 17 - a * 3;
  const flecha = mov && tipo !== 'descanso' ? 0.6 : tipo === 'descanso' ? 0.45 : 0;
  return (
    <g>
      <Cabeza alarga={baja} color={color} />
      <ellipse cx="100" cy={my} rx={rx + 3} ry={ry + 3} fill="none" stroke="#c98b9a" strokeOpacity="0.55" strokeWidth="3" />
      <ellipse cx="100" cy={my} rx={rx} ry={ry} fill="url(#anim-boca)" />
      {a > 0.25 && <g opacity={Math.min(1, (a - 0.25) * 2)}>
        {/* paladar blando y úvula: suben con la apertura del fondo */}
        <path d={`M${100 - rx + 3} ${my - ry + 4} Q100 ${my - ry - 2 - a * 4} ${100 + rx - 3} ${my - ry + 4}`} fill="none" stroke="#e7a3b4" strokeOpacity="0.7" strokeWidth="2" />
        <ellipse cx="100" cy={my - ry + 7 - a * 2} rx="2.4" ry={3.5 - a} fill="#e7a3b4" opacity="0.9" />
        {/* lengua plana */}
        <ellipse cx="100" cy={my + ry - 5} rx={rx - 3} ry={3 + (1 - a) * 2} fill="#c46a7f" />
      </g>}
      {flecha > 0 && <g stroke={color} strokeWidth="2" fill="none" strokeLinecap="round" opacity={flecha * (0.6 + 0.4 * Math.sin(t * 3) * vivo)} filter="url(#anim-brillo)">
        {tipo === 'descanso'
          ? <><path d={`M70 ${my + 22} v-10 m-4 4 l4 -4 l4 4`} /><path d={`M130 ${my + 22} v-10 m-4 4 l4 -4 l4 4`} /></>
          : <><path d={`M70 ${my + 8} v10 m-4 -4 l4 4 l4 -4`} /><path d={`M130 ${my + 8} v10 m-4 -4 l4 4 l4 -4`} /></>}
      </g>}
    </g>
  );
}

/** Torso que se expande: abdominal (hacia adelante) o costal (hacia los costados), con aire que entra o sale. */
function Respira({ o, t, vivo, color, texto, tipo, bankId }: P) {
  const costal = /costilla|costal|espalda/.test(texto) || bankId === 'expansion_costo_lateral';
  const leHuche = bankId === 'le_huche' && /hombros y brazos/.test(texto);
  const fondo = 1 + Math.sin(t * 1.3) * 0.01 * vivo;
  const panza = costal ? 0.25 : 1, cost = costal ? 1 : 0.3;
  const hombro = leHuche ? 6 * o : 0;
  const entra = tipo === 'inhala', sale = tipo === 'exhala';
  return (
    <g>
      <rect x="90" y="48" width="20" height="22" rx="7" fill="#18223a" />
      <circle cx="100" cy="36" r="22" fill="url(#anim-piel)" stroke={color} strokeOpacity="0.5" />
      {/* tronco: hombros redondeados, costados que se abren (costal) y abdomen que avanza */}
      <path d={`M90 ${66 - hombro} C70 ${66 - hombro} ${46 - cost * o * 4} ${68 - hombro} ${40 - cost * o * 6} ${86 - hombro}
               C${38 - cost * o * 10} 110 ${44 - cost * o * 14} 150 ${54 - cost * o * 8} 186
               Q100 ${194 + panza * o * 6} ${146 + cost * o * 8} 186
               C${156 + cost * o * 14} 150 ${162 + cost * o * 10} 110 ${160 + cost * o * 6} ${86 - hombro}
               C${154 + cost * o * 4} ${68 - hombro} 130 ${66 - hombro} 110 ${66 - hombro} Z`}
        fill="url(#anim-piel)" stroke={color} strokeOpacity="0.5" strokeWidth="1.5" transform={`scale(${fondo}) translate(${(1 - fondo) * 100} 0)`} />
      {/* costillas */}
      <g stroke={color} strokeOpacity={0.25 + cost * o * 0.5} fill="none" strokeWidth="1.6">
        {[96, 108, 120].map((y, i) => <path key={y} d={`M${62 - cost * o * (10 - i * 2)} ${y} Q100 ${y - 10} ${138 + cost * o * (10 - i * 2)} ${y}`} />)}
      </g>
      {/* abdomen */}
      <ellipse cx="100" cy="158" rx={30 + panza * o * 12} ry={18 + panza * o * 9} fill={color} fillOpacity={0.12 + panza * o * 0.3}
        stroke={color} strokeOpacity="0.6" filter="url(#anim-brillo)" />
      {/* aire */}
      {(entra || sale) && vivo > 0 && [0, 1, 2, 3].map(k => {
        const f = ((t * 0.8 + k / 4) % 1);
        const y = entra ? 2 + f * 28 : 50 + f * 26, x = entra ? 100 : 100 + (k - 1.5) * f * 10;
        return <circle key={k} cx={x} cy={y} r={2.2 - f} fill={color} opacity={(1 - f) * 0.8} />;
      })}
    </g>
  );
}

/** Cuello y hombros: rotación de hombros (juntos o alternados), cabeza por delante, mentón u oreja a cada hombro. */
function Cuello({ o, t, s, mov, color, texto, tipo }: P) {
  const w = (2 * Math.PI) / 6;                  // una vuelta cada 6 s: lento
  const fase = s * w * mov;
  const act = tipo === 'descanso' ? o : mov;
  let rot = 0, giro = 0, dx = 0, dy = 0, hI = [0, 0], hD = [0, 0];
  if (/hombro/.test(texto) && /rota|alternad/.test(texto)) {
    const alt = /alternad|uno y otro/.test(texto) ? Math.PI : 0;
    hI = [Math.cos(fase) * 6 * act, Math.sin(fase) * 6 * act];
    hD = [-Math.cos(fase + alt) * 6 * act, Math.sin(fase + alt) * 6 * act];
  } else if (/oreja/.test(texto)) rot = Math.sin(fase) * 20 * act;
  else if (/menton/.test(texto)) giro = Math.sin(fase) * act;
  else if (/cabeza/.test(texto)) { dx = Math.sin(fase) * 12 * act; dy = Math.abs(Math.cos(fase)) * 6 * act; rot = Math.sin(fase) * 10 * act; }
  return (
    <g>
      <path d={`M${40 + hI[0]} ${170 + hI[1]} Q${52 + hI[0]} ${148 + hI[1]} 84 146 L116 146 Q${148 + hD[0]} ${148 + hD[1]} ${160 + hD[0]} ${170 + hD[1]} L168 198 L32 198 Z`}
        fill="url(#anim-piel)" stroke={color} strokeOpacity="0.5" strokeWidth="1.5" />
      <rect x="86" y="118" width="28" height="34" rx="10" fill="#18223a" />
      <g transform={`translate(${dx} ${dy}) scale(0.78) translate(28 8)`}>
        <Cabeza cy={86} color={color} rot={rot} giro={giro} />
      </g>
      {mov > 0 && <g fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" opacity="0.55" filter="url(#anim-brillo)">
        <path d="M24 150 a14 14 0 1 1 6 12" /><path d="M176 150 a14 14 0 1 0 -6 12" />
      </g>}
    </g>
  );
}

/** Masaje por puntos: el punto se ilumina y un círculo pequeño marca el movimiento circular. */
const PUNTOS: [RegExp, [number, number][]][] = [
  [/coronilla|vertex/, [[100, 30]]], [/sien/, [[56, 72], [144, 72]]], [/entrecejo/, [[100, 72]]],
  [/mandibula/, [[54, 104], [146, 104]]], [/masetero/, [[64, 120], [136, 120]]], [/labios/, [[86, 128], [114, 128]]],
  [/cuello/, [[74, 168], [126, 168]]],
];
function Puntos({ o, t, s, mov, color, texto }: P) {
  const lugar = PUNTOS.find(([r]) => r.test(texto))?.[1] || [];
  const ang = s * 2.2 * mov;
  return (
    <g>
      <rect x="80" y="140" width="40" height="40" rx="12" fill="#18223a" />
      <Cabeza cy={84} color={color} />
      <path d="M92 126 q8 4 16 0" stroke="#c98b9a" strokeOpacity="0.6" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {lugar.map(([x, y], i) => (
        <g key={i} filter="url(#anim-brillo)">
          <circle cx={x} cy={y} r={7 + Math.sin(t * 2.4) * 1.5} fill={color} opacity={0.35 + o * 0.25} />
          <circle cx={x + Math.cos(ang) * 6} cy={y + Math.sin(ang) * 6} r="3.2" fill={NOCHE.texto} opacity={mov ? 0.9 : 0} />
        </g>
      ))}
    </g>
  );
}

/** Laringe de frente: los dedos bajan por los costados y la laringe desciende, sin tensión. */
function Laringe({ o, s, mov, color, texto, tipo }: P) {
  const baja = /baja|descen|masaje/.test(texto) ? o * 10 : 0;
  const traga = /traga/.test(texto) && mov === 0 && tipo === 'descanso' ? Math.max(0, Math.sin(s * 1.6)) * -6 : 0;
  const f = (s / 2.5) % 1;                       // un recorrido de los dedos cada 2,5 s
  const dedo = mov ? 96 + f * 50 : 96;
  return (
    <g>
      <path d="M68 70 Q66 150 50 198 L150 198 Q134 150 132 70 Z" fill="url(#anim-piel)" stroke={color} strokeOpacity="0.5" strokeWidth="1.5" />
      <ellipse cx="100" cy="46" rx="44" ry="34" fill="url(#anim-piel)" stroke={color} strokeOpacity="0.4" />
      <g transform={`translate(0 ${baja + traga})`}>
        <path d="M86 104 L114 104 L108 128 Q100 134 92 128 Z" fill={color} fillOpacity="0.28" stroke={color} strokeOpacity="0.8" strokeWidth="1.5" filter="url(#anim-brillo)" />
        <path d="M100 104 l0 -6" stroke={color} strokeOpacity="0.8" strokeWidth="2" />
      </g>
      {mov > 0 && /masaj/.test(texto) && [80, 120].map(x => (
        <g key={x} opacity={Math.sin(f * Math.PI)}>
          <ellipse cx={x} cy={dedo} rx="6" ry="9" fill={NOCHE.texto} opacity="0.85" />
          <path d={`M${x} ${dedo - 30} v18`} stroke={NOCHE.texto} strokeOpacity="0.25" strokeWidth="3" strokeLinecap="round" />
        </g>
      ))}
      {baja > 2 && <path d="M150 100 v22 m-5 -5 l5 5 l5 -5" stroke={color} strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.6" />}
    </g>
  );
}

/** Sonido con vibración (labios, «mmm», «bbb», mano contra la boca): ondas que salen de los labios. */
function Vibra({ o, t, mov, vivo, color, texto, bankId }: P) {
  const mejillas = bankId === 'b_prolongada' || /bbb/.test(texto) ? o * 8 : 0;
  const temblor = mov * vivo * (/brrr|trino/.test(texto) ? Math.sin(t * 60) * 0.8 : 0);
  const mano = bankId === 'mano_boca' || /contra la mano/.test(texto);
  return (
    <g>
      <Cabeza cy={84} color={color} />
      <ellipse cx="66" cy="120" rx={10 + mejillas} ry={8 + mejillas * 0.7} fill={color} fillOpacity={0.08 + mejillas * 0.02} />
      <ellipse cx="134" cy="120" rx={10 + mejillas} ry={8 + mejillas * 0.7} fill={color} fillOpacity={0.08 + mejillas * 0.02} />
      <path d={`M86 ${126 + temblor} q14 ${5 - temblor} 28 0`} stroke="#c98b9a" strokeWidth="3.5" fill="none" strokeLinecap="round" />
      {mano && <path d="M78 116 q22 -8 44 0 l2 22 q-24 8 -48 0 Z" fill="#26324d" stroke={color} strokeOpacity="0.5" />}
      {mov > 0 && vivo > 0 && [0, 1, 2].map(k => {
        const f = (t * 0.9 + k / 3) % 1;
        return <ellipse key={k} cx="100" cy="128" rx={18 + f * 70} ry={8 + f * 40} fill="none" stroke={color} strokeWidth="2" opacity={(1 - f) * 0.6 * o + 0.05} />;
      })}
    </g>
  );
}
