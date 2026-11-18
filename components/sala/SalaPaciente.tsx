import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Wifi, WifiOff } from 'lucide-react';
import CurvaTono, { Muestra } from './CurvaTono';
import { cents, dbfs, hzAMidi, nombreNota, urlWs, yin } from '../../utils/pitch';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

/**
 * Página del paciente o alumno en la sala virtual (enlace ?sala=<token>,
 * sin cuenta). Mide la voz en SU equipo con el micrófono sin filtros (sin
 * cancelación de ruido, de eco ni control de volumen) y la manda en vivo al
 * fonoaudiólogo. No se graba audio.
 */
export default function SalaPaciente({ token }: { token: string }) {
  const [info, setInfo] = useState<any | null>(null);
  const [error, setError] = useState('');
  const [activo, setActivo] = useState(false);
  const [conectado, setConectado] = useState(false);
  const [muestras, setMuestras] = useState<Muestra[]>([]);
  const [actual, setActual] = useState<number | null>(null);
  const [objetivo, setObjetivo] = useState<any | null>(null);
  const [consigna, setConsigna] = useState('');
  const [modo, setModo] = useState('habla');
  const wsRef = useRef<WebSocket | null>(null);
  const pendientes = useRef<Muestra[]>([]);
  const audioRef = useRef<{ ctx: AudioContext; stream: MediaStream } | null>(null);
  const modoRef = useRef('habla');

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/sala/${token}/info`)
      .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.detail); return d; })
      .then(d => { setInfo(d); setObjetivo(d.objetivo); setConsigna(d.consigna || ''); setModo(d.modo); modoRef.current = d.modo; })
      .catch(e => setError(e?.message || 'No se pudo abrir la sala.'));
  }, [token]);

  // Conexión en vivo con reconexión automática.
  useEffect(() => {
    if (!activo) return;
    let cerrado = false;
    let espera = 1000;
    const conectar = () => {
      const ws = new WebSocket(urlWs(BACKEND_URL, `/ws/sala/${token}/paciente`));
      wsRef.current = ws;
      ws.onopen = () => { setConectado(true); espera = 1000; };
      ws.onmessage = ev => {
        const m = JSON.parse(ev.data);
        if (m.tipo === 'objetivo') setObjetivo(m.objetivo);
        if (m.tipo === 'consigna') setConsigna(m.texto);
        if (m.tipo === 'modo') { setModo(m.modo); modoRef.current = m.modo; }
        if (m.tipo === 'config') { setObjetivo(m.objetivo); setConsigna(m.consigna || ''); setModo(m.modo); modoRef.current = m.modo; }
        if (m.tipo === 'cerrada') { setError('El fonoaudiólogo cerró la sala. ¡Gracias!'); cerrado = true; ws.close(); }
        if (m.tipo === 'error') { setError(m.texto); cerrado = true; }
      };
      ws.onclose = () => {
        setConectado(false);
        if (!cerrado) { setTimeout(conectar, espera); espera = Math.min(espera * 2, 10000); }
      };
    };
    conectar();
    const envio = setInterval(() => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN && pendientes.current.length) {
        ws.send(JSON.stringify({ tipo: 'muestras', datos: pendientes.current.splice(0, 50) }));
      }
    }, 300);
    return () => { cerrado = true; clearInterval(envio); wsRef.current?.close(); };
  }, [activo, token]);

  const activar = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 4096;
      ctx.createMediaStreamSource(stream).connect(analyser);
      audioRef.current = { ctx, stream };
      const buf = new Float32Array(analyser.fftSize);
      setActivo(true);
      const tick = () => {
        if (!audioRef.current) return;
        analyser.getFloatTimeDomainData(buf);
        const db = dbfs(buf);
        const maxHz = modoRef.current === 'canto' ? 1200 : 700;
        const f0 = db > -50 ? yin(buf, ctx.sampleRate, 60, maxHz) : null;
        const m: Muestra = { t: Date.now(), f0: f0 ? Math.round(f0 * 10) / 10 : null, db: Math.round(db) };
        pendientes.current.push(m);
        setActual(m.f0);
        setMuestras(prev => [...prev.slice(-400), m]);
        setTimeout(tick, 100);
      };
      tick();
    } catch {
      setError('No se pudo usar el micrófono. Revisá el permiso del navegador y volvé a intentar.');
    }
  };

  const detener = () => {
    audioRef.current?.stream.getTracks().forEach(t => t.stop());
    audioRef.current?.ctx.close();
    audioRef.current = null;
    setActivo(false);
  };

  const desvio = actual && objetivo?.hz ? cents(actual, objetivo.hz) : null;
  const enObjetivo = desvio != null && Math.abs(desvio) <= (objetivo?.tolerancia_cents || 50);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0b0f19] text-slate-900 dark:text-white p-4">
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="text-center pt-4">
          <h1 className="text-xl font-extrabold">Consultorio de Voz</h1>
          <p className="text-xs text-slate-500">{info?.profesional || 'Matías Pérez · Fonoaudiólogo'}</p>
        </div>

        {error ? (
          <p className="p-4 rounded-2xl bg-amber-100 dark:bg-amber-500/10 text-amber-800 dark:text-amber-300 text-sm text-center">{error}</p>
        ) : !info ? (
          <p className="text-center text-sm text-slate-500">Abriendo la sala…</p>
        ) : (
          <>
            <div className="p-4 rounded-2xl bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 text-sm">
              <p className="font-bold">{info.nombre ? `Hola ${info.nombre}` : 'Hola'} 👋</p>
              <p className="text-slate-600 dark:text-slate-300 mt-1">
                Esta página mide tu voz con el micrófono de este equipo y se la muestra a tu fonoaudiólogo en vivo.
                No se graba ningún audio. Seguí con la videollamada abierta como siempre.
              </p>
            </div>

            {!activo ? (
              <button onClick={activar}
                className="w-full py-4 rounded-2xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold flex items-center justify-center gap-2 text-base">
                <Mic size={20} /> Activar micrófono
              </button>
            ) : (
              <>
                {consigna && (
                  <p className="p-4 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 text-base font-semibold text-center">
                    {consigna}
                  </p>
                )}
                <div className={`p-5 rounded-2xl text-center border ${enObjetivo ? 'bg-emerald-50 dark:bg-emerald-500/10 border-emerald-300' : 'bg-white dark:bg-white/5 border-slate-200 dark:border-white/10'}`}>
                  <p className="text-5xl font-black">{actual ? nombreNota(hzAMidi(actual)) : '—'}</p>
                  <p className="text-sm text-slate-500 mt-1">{actual ? `${actual.toFixed(0)} Hz` : 'Hablá o cantá para ver tu voz'}</p>
                  {objetivo?.hz && (
                    <p className={`mt-2 text-sm font-bold ${enObjetivo ? 'text-emerald-600' : 'text-slate-600 dark:text-slate-300'}`}>
                      Objetivo: {objetivo.nota || `${objetivo.hz} Hz`}
                      {desvio != null && (enObjetivo ? ' · ¡justo!' : desvio > 0 ? ' · bajá un poco' : ' · subí un poco')}
                    </p>
                  )}
                </div>
                <CurvaTono muestras={muestras} objetivoHz={objetivo?.hz} toleranciaCents={objetivo?.tolerancia_cents} />
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="flex items-center gap-1">{conectado ? <><Wifi size={13} className="text-emerald-500" /> Conectado con tu fonoaudiólogo</> : <><WifiOff size={13} className="text-amber-500" /> Reconectando…</>}</span>
                  <button onClick={detener} className="flex items-center gap-1 underline"><MicOff size={13} /> Apagar micrófono</button>
                </div>
              </>
            )}
            <p className="text-[11px] text-slate-400 text-center">
              Consejo: usá auriculares y, en la videollamada, desactivá la cancelación de ruido. Modo: {info.modo_texto}.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
