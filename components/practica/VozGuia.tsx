import React, { useEffect, useRef, useState } from 'react';
import { Mic, Square, Play, Trash2, Loader2, CheckCircle2 } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const MAX_SEG = 25;

/** Convierte la grabación en WAV mono 24 kHz: sin silencios al principio y al
 *  final y con volumen parejo (se escucha bien en cualquier celular). */
async function aWav(blob: Blob): Promise<{ b64: string; seg: number }> {
  const ctx = new AudioContext();
  const orig = await ctx.decodeAudioData(await blob.arrayBuffer());
  ctx.close();
  const SR = 24000;
  const off = new OfflineAudioContext(1, Math.ceil(orig.duration * SR), SR);
  const s = off.createBufferSource(); s.buffer = orig; s.connect(off.destination); s.start();
  const x = (await off.startRendering()).getChannelData(0);
  // Recorte de silencios (ventanas de 20 ms por debajo del 4 % del pico).
  let pico = 0; for (const v of x) pico = Math.max(pico, Math.abs(v));
  const win = Math.round(SR * 0.02), umbral = pico * 0.04;
  const activo = (i: number) => { let m = 0; for (let k = i; k < Math.min(x.length, i + win); k++) m = Math.max(m, Math.abs(x[k])); return m > umbral; };
  let ini = 0; while (ini < x.length && !activo(ini)) ini += win;
  let fin = x.length; while (fin > ini && !activo(fin - win)) fin -= win;
  ini = Math.max(0, ini - Math.round(SR * 0.12)); fin = Math.min(x.length, fin + Math.round(SR * 0.2));
  const y = x.slice(ini, fin);
  const g = pico > 0 ? 0.89 / pico : 1;
  const buf = new ArrayBuffer(44 + y.length * 2), dv = new DataView(buf);
  const str = (o: number, t: string) => [...t].forEach((c, i) => dv.setUint8(o + i, c.charCodeAt(0)));
  str(0, 'RIFF'); dv.setUint32(4, 36 + y.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
  dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, SR, true);
  dv.setUint32(28, SR * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); str(36, 'data'); dv.setUint32(40, y.length * 2, true);
  y.forEach((v, i) => dv.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v * g)) * 0x7fff, true));
  let bin = ''; const u8 = new Uint8Array(buf);
  for (let i = 0; i < u8.length; i += 0x8000) bin += String.fromCharCode(...u8.subarray(i, i + 0x8000));
  return { b64: btoa(bin), seg: Math.round((y.length / SR) * 10) / 10 };
}

/**
 * Tu voz guía: grabás las indicaciones de la práctica (y la consigna de cada
 * ejercicio) con tu voz; el paciente las escucha en lugar de la voz del celular.
 */
export default function VozGuia({ onCambio }: { onCambio?: (claves: string[]) => void }) {
  const [datos, setDatos] = useState<any>(null);
  const [grabando, setGrabando] = useState<string | null>(null);
  const [guardando, setGuardando] = useState<string | null>(null);
  const [seg, setSeg] = useState(0);
  const [error, setError] = useState('');
  const rec = useRef<{ mr: MediaRecorder; stream: MediaStream; partes: Blob[]; t: any } | null>(null);

  const cargar = async () => {
    try {
      const j = await (await fetch(`${BACKEND_URL}/api/voz-guia`)).json();
      setDatos(j);
      onCambio?.([...(j.frases || []), ...(j.ejercicios || [])].filter((f: any) => f.grabada).map((f: any) => f.clave));
    } catch { setError('No se pudo cargar la voz guía.'); }
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line */ }, []);

  const empezar = async (clave: string) => {
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      const mr = new MediaRecorder(stream);
      const partes: Blob[] = [];
      mr.ondataavailable = e => e.data.size && partes.push(e.data);
      mr.onstop = () => terminar(clave, partes, mr.mimeType);
      mr.start();
      setSeg(0);
      const t = setInterval(() => setSeg(s => { if (s + 1 >= MAX_SEG) parar(); return s + 1; }), 1000);
      rec.current = { mr, stream, partes, t };
      setGrabando(clave);
    } catch { setError('No se pudo usar el micrófono para grabar.'); }
  };
  const parar = () => {
    const r = rec.current; if (!r) return;
    clearInterval(r.t);
    if (r.mr.state !== 'inactive') r.mr.stop();
    r.stream.getTracks().forEach(t => t.stop());
    rec.current = null;
    setGrabando(null);
  };
  const terminar = async (clave: string, partes: Blob[], mime: string) => {
    setGuardando(clave);
    try {
      const { b64, seg: dur } = await aWav(new Blob(partes, { type: mime }));
      if (dur < 0.3) throw new Error('No se escuchó la grabación: probá de nuevo más cerca del micrófono.');
      const r = await fetch(`${BACKEND_URL}/api/voz-guia/${encodeURIComponent(clave)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_b64: b64, mime: 'audio/wav', duracion_s: dur }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Error ${r.status}`);
      await cargar();
    } catch (e: any) { setError(e?.message || 'No se pudo guardar la grabación.'); }
    setGuardando(null);
  };
  const escuchar = async (clave: string) => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/voz-guia/${encodeURIComponent(clave)}/audio`);
      if (!r.ok) throw new Error();
      const ctx = new AudioContext();
      const b = await ctx.decodeAudioData(await r.arrayBuffer());
      const s = ctx.createBufferSource(); s.buffer = b; s.connect(ctx.destination); s.onended = () => ctx.close(); s.start();
    } catch { setError('No se pudo reproducir.'); }
  };
  const borrar = async (clave: string) => {
    if (!confirm('¿Borrar esta grabación? Se va a usar la voz del celular.')) return;
    await fetch(`${BACKEND_URL}/api/voz-guia/${encodeURIComponent(clave)}`, { method: 'DELETE' });
    cargar();
  };

  if (!datos) return <p className="text-slate-500 text-xs">{error || 'Cargando…'}</p>;
  const fila = (f: any, titulo?: string) => (
    <div key={f.clave} className="flex items-center gap-2 py-1.5 border-t border-slate-100 dark:border-white/5">
      <div className="flex-1 min-w-0">
        {titulo && <p className="font-bold">{titulo}</p>}
        <p className="text-slate-700 dark:text-slate-200">«{f.texto}»</p>
      </div>
      {f.grabada && <span className="text-emerald-600 flex items-center gap-0.5 shrink-0"><CheckCircle2 size={12} /> {f.duracion_s ? `${f.duracion_s} s` : 'grabada'}</span>}
      {grabando === f.clave ? (
        <button onClick={parar} className="px-2.5 py-1.5 rounded-lg bg-red-600 text-white font-bold flex items-center gap-1 shrink-0"><Square size={11} /> Parar ({seg} s)</button>
      ) : guardando === f.clave ? (
        <Loader2 size={14} className="animate-spin shrink-0" />
      ) : (
        <button onClick={() => empezar(f.clave)} disabled={!!grabando} className="px-2.5 py-1.5 rounded-lg border border-red-300 text-red-700 dark:text-red-300 flex items-center gap-1 shrink-0 disabled:opacity-40">
          <Mic size={11} /> {f.grabada ? 'Regrabar' : 'Grabar'}</button>
      )}
      {f.grabada && <button onClick={() => escuchar(f.clave)} className="text-indigo-600 shrink-0" title="Escuchar"><Play size={14} /></button>}
      {f.grabada && <button onClick={() => borrar(f.clave)} className="text-slate-400 hover:text-red-600 shrink-0" title="Borrar"><Trash2 size={13} /></button>}
    </div>
  );
  const nf = datos.frases.filter((f: any) => f.grabada).length, ne = datos.ejercicios.filter((f: any) => f.grabada).length;

  return (
    <div className="text-xs space-y-2">
      <p className="text-slate-600 dark:text-slate-300">
        Grabá las indicaciones con tu voz: el paciente las escucha durante la práctica. Lo que no grabes lo dice la voz del celular.
        Podés decirlas con tus palabras (tranquilo, cerca del micrófono). {nf}/{datos.frases.length} indicaciones · {ne}/{datos.ejercicios.length} consignas grabadas.
      </p>
      {datos.aviso && <p className="text-amber-600">{datos.aviso}</p>}
      {error && <p className="text-red-600">{error}</p>}
      <div>{datos.frases.map((f: any) => fila(f))}</div>
      <p className="font-bold pt-2">Consigna de cada ejercicio (suena antes de la primera repetición)</p>
      <div>{datos.ejercicios.map((f: any) => fila(f, f.nombre))}</div>
    </div>
  );
}
