import React, { useEffect, useRef } from 'react';
import { hzAMidi, nombreNota } from '../../utils/pitch';

export interface Muestra {
  t: number;            // ms (Date.now())
  f0: number | null;    // Hz (null = sin voz)
  db?: number;
}

interface Props {
  muestras: Muestra[];
  objetivoHz?: number | null;
  toleranciaCents?: number;
  ventanaS?: number;
  alto?: number;
}

/**
 * Curva de altura tonal de los últimos segundos, en semitonos (escala
 * musical), con la franja de la nota objetivo si hay una.
 */
export default function CurvaTono({ muestras, objetivoHz, toleranciaCents = 50, ventanaS = 15, alto = 220 }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const ancho = canvas.clientWidth;
    canvas.width = ancho * dpr;
    canvas.height = alto * dpr;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    const oscuro = document.documentElement.classList.contains('dark');
    ctx.fillStyle = oscuro ? '#0b0f19' : '#f8fafc';
    ctx.fillRect(0, 0, ancho, alto);

    const ahora = muestras.length ? muestras[muestras.length - 1].t : Date.now();
    const desde = ahora - ventanaS * 1000;
    const visibles = muestras.filter(m => m.t >= desde);
    const midis = visibles.filter(m => m.f0).map(m => hzAMidi(m.f0 as number));
    const objMidi = objetivoHz ? hzAMidi(objetivoHz) : null;
    if (objMidi != null) midis.push(objMidi);
    let lo = midis.length ? Math.min(...midis) - 3 : 45;
    let hi = midis.length ? Math.max(...midis) + 3 : 69;
    if (hi - lo < 12) { const c = (hi + lo) / 2; lo = c - 6; hi = c + 6; }
    const y = (m: number) => alto - ((m - lo) / (hi - lo)) * alto;
    const x = (t: number) => ((t - desde) / (ventanaS * 1000)) * ancho;

    // Grilla por semitono con nombre en los Do y en la nota objetivo.
    ctx.font = '10px system-ui';
    for (let m = Math.ceil(lo); m <= hi; m++) {
      const esDo = ((m % 12) + 12) % 12 === 0;
      ctx.strokeStyle = esDo ? (oscuro ? '#334155' : '#cbd5e1') : (oscuro ? '#1e293b' : '#eef2f7');
      ctx.beginPath(); ctx.moveTo(0, y(m)); ctx.lineTo(ancho, y(m)); ctx.stroke();
      if (esDo) { ctx.fillStyle = oscuro ? '#64748b' : '#94a3b8'; ctx.fillText(nombreNota(m), 4, y(m) - 2); }
    }
    if (objMidi != null) {
      const banda = toleranciaCents / 100;
      ctx.fillStyle = 'rgba(16,185,129,0.18)';
      ctx.fillRect(0, y(objMidi + banda), ancho, y(objMidi - banda) - y(objMidi + banda));
      ctx.strokeStyle = '#10b981'; ctx.setLineDash([6, 4]);
      ctx.beginPath(); ctx.moveTo(0, y(objMidi)); ctx.lineTo(ancho, y(objMidi)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#059669'; ctx.fillText(`Objetivo ${nombreNota(objMidi)}`, ancho - 90, y(objMidi) - 4);
    }
    // Curva (se corta donde no hay voz).
    ctx.strokeStyle = '#6366f1'; ctx.lineWidth = 2.5;
    ctx.beginPath();
    let abierto = false;
    for (const m of visibles) {
      if (!m.f0) { abierto = false; continue; }
      const px = x(m.t), py = y(hzAMidi(m.f0));
      if (abierto) ctx.lineTo(px, py); else { ctx.moveTo(px, py); abierto = true; }
    }
    ctx.stroke();
    ctx.lineWidth = 1;
  }, [muestras, objetivoHz, toleranciaCents, ventanaS, alto]);

  return <canvas ref={ref} style={{ width: '100%', height: alto }} className="rounded-xl border border-slate-200 dark:border-white/10" />;
}
