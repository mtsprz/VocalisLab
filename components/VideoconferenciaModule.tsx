import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Video, Mic, Save, Clock, User, FileText, Music, BookOpen,
  Presentation, CheckCircle2, AlertCircle, Loader2, X, Send,
  MessageCircle, Mail, ChevronDown, ChevronUp, Activity, Headphones,
  Flag, ArrowLeft, Stethoscope
} from 'lucide-react';
import ZoomEmbedded from './ZoomEmbedded';
import { useClinical } from './ClinicalContext';
import { useAuth } from './AuthContext';
import { firmaProfesional } from './clinicalUtils';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  turno: any;
  onNavigate: (modulo: string, pacienteId?: string) => void;
  onVolver: () => void;
  onEnviarCuadernillo?: (exerciseIds: string[]) => void;
}

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

function freqToNote(freq: number) {
  const exact = 69 + 12 * Math.log2(freq / 440);
  const rounded = Math.round(exact);
  const cents = Math.round((exact - rounded) * 100);
  const idx = ((rounded % 12) + 12) % 12;
  return { name: `${NOTE_NAMES[idx]}${Math.floor(rounded / 12) - 1}`, cents };
}

function yinDetect(buffer: Float32Array, sampleRate: number): number | null {
  const threshold = 0.15;
  const minLag = Math.floor(sampleRate / 500);
  const maxLag = Math.floor(sampleRate / 60);
  const half = Math.floor(buffer.length / 2);
  const yb = new Float32Array(half);
  for (let tau = 0; tau < half; tau++) {
    let s = 0;
    for (let j = 0; j < half; j++) {
      const d = buffer[j] - buffer[j + tau];
      s += d * d;
    }
    yb[tau] = s;
  }
  yb[0] = 1;
  let run = 0;
  for (let tau = 1; tau < half; tau++) {
    run += yb[tau];
    yb[tau] *= tau / run;
  }
  let best = -1;
  for (let tau = minLag; tau < Math.min(maxLag, half); tau++) {
    if (yb[tau] < threshold) {
      while (tau + 1 < half && yb[tau + 1] < yb[tau]) tau++;
      best = tau;
      break;
    }
  }
  if (best <= 0) return null;
  const f = sampleRate / best;
  return f >= 60 && f <= 800 ? f : null;
}

/** Pitch compacto para feedback en vivo. NO diagnostica ni sustituye a Praat.
 *  Solo guarda valores si el profesional lo confirma. */
function PitchMini({ onConfirmF0 }: { onConfirmF0: (f0: number) => void }) {
  const [active, setActive] = useState(false);
  const [freq, setFreq] = useState<number | null>(null);
  const [confiable, setConfiable] = useState(true);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState('');
  const [noConsent, setNoConsent] = useState(true);
  const ctxRef = useRef<AudioContext | null>(null);
  const anRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef(0);
  const histRef = useRef<number[]>([]);
  const [media, setMedia] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const ds = await navigator.mediaDevices.enumerateDevices();
        setDevices(ds.filter(d => d.kind === 'audioinput'));
      } catch {}
    })();
    return () => {
      cancelAnimationFrame(rafRef.current);
      ctxRef.current?.close().catch(() => {});
    };
  }, []);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: deviceId ? { exact: deviceId } : undefined,
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        } as MediaTrackConstraints,
      });
      const ctx = new AudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const an = ctx.createAnalyser();
      an.fftSize = 4096;
      src.connect(an);
      ctxRef.current = ctx;
      anRef.current = an;
      histRef.current = [];
      setActive(true);
      const loop = () => {
        const buf = new Float32Array(an.frequencyBinCount);
        an.getFloatTimeDomainData(buf);
        // Energía para indicador de confiabilidad
        let e = 0;
        for (let i = 0; i < buf.length; i += 4) e += buf[i] * buf[i];
        e = Math.sqrt(e / (buf.length / 4));
        const f = yinDetect(buf, ctx.sampleRate);
        setFreq(f);
        setConfiable(e > 0.008);
        if (f) {
          histRef.current.push(f);
          if (histRef.current.length > 300) histRef.current.shift();
          setMedia(histRef.current.reduce((a, b) => a + b, 0) / histRef.current.length);
        }
        rafRef.current = requestAnimationFrame(loop);
      };
      rafRef.current = requestAnimationFrame(loop);
    } catch {
      alert('No se pudo acceder al micrófono');
    }
  };

  const stop = () => {
    cancelAnimationFrame(rafRef.current);
    ctxRef.current?.close().catch(() => {});
    setActive(false);
  };

  const note = freq ? freqToNote(freq) : null;
  const usb = devices.find(d => d.deviceId === deviceId);
  const esUSB = usb ? /usb/i.test(usb.label || '') : false;

  return (
    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
          <Music size={13} className="text-emerald-400" /> Pitch en vivo (orientativo)
        </span>
        {!active ? (
          <button onClick={start} className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold flex items-center gap-1">
            <Mic size={12} /> Activar
          </button>
        ) : (
          <button onClick={stop} className="px-2.5 py-1 rounded-lg bg-red-600 hover:bg-red-500 text-white text-[11px] font-bold">
            Detener
          </button>
        )}
      </div>

      <select
        value={deviceId}
        onChange={e => setDeviceId(e.target.value)}
        className="w-full px-2 py-1.5 bg-slate-900 border border-slate-700 text-slate-200 rounded-lg text-[11px]"
      >
        <option value="">Micrófono del sistema</option>
        {devices.map(d => (
          <option key={d.deviceId} value={d.deviceId}>{d.label || 'Dispositivo de audio'}</option>
        ))}
      </select>
      {deviceId && (
        <p className="text-[10px] text-slate-400">
          {esUSB ? 'Interfaz USB detectada.' : 'Verificá que sea tu placa USB.'} No se garantiza audio sin filtros en el navegador.
        </p>
      )}

      <div className="flex items-end justify-between">
        <div>
          <div className="text-2xl font-black text-emerald-400 font-mono">
            {freq ? freq.toFixed(1) : '—'} <span className="text-xs">Hz</span>
          </div>
          {note && (
            <div className="text-[11px] text-slate-300 font-bold">
              {note.name} <span className="text-slate-500 font-mono">({note.cents >= 0 ? `+${note.cents}` : note.cents}¢)</span>
            </div>
          )}
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${!active ? 'bg-slate-800 text-slate-500' : confiable ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'}`}>
          {!active ? 'Inactivo' : confiable ? 'Señal confiable' : 'Señal débil'}
        </span>
      </div>

      {/* Mini teclado C2-C6 con indicador */}
      <MiniKeys freq={freq} />

      <p className="text-[9px] text-slate-500 leading-snug">
        Feedback en tiempo real. No diagnostica ni sustituye el análisis de Praat. La calidad depende del
        micrófono, navegador, red y filtros de Zoom. No se almacena audio.
      </p>

      {media > 0 && (
        <button
          onClick={() => onConfirmF0(Math.round(media * 10) / 10)}
          className="w-full py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-bold"
        >
          Confirmar y guardar F0 media ({media.toFixed(1)} Hz) en la sesión
        </button>
      )}
    </div>
  );
}

function MiniKeys({ freq }: { freq: number | null }) {
  const whites = [0, 2, 4, 5, 7, 9, 11];
  const midi = freq ? Math.round(69 + 12 * Math.log2(freq / 440)) : -1;
  const keys = [];
  for (let m = 36; m <= 84; m++) {
    const pc = ((m % 12) + 12) % 12;
    keys.push({ m, black: !whites.includes(pc) });
  }
  return (
    <div className="relative h-10 flex rounded overflow-hidden border border-slate-700">
      {keys.filter(k => !k.black).map(k => (
        <div
          key={k.m}
          className={`flex-1 border-r border-slate-700 last:border-r-0 ${k.m === midi ? 'bg-emerald-400' : 'bg-slate-200'}`}
        />
      ))}
      {keys.filter(k => k.black).map(k => {
        const wi = keys.filter(x => !x.black && x.m < k.m).length;
        const totalW = keys.filter(x => !x.black).length;
        return (
          <div
            key={k.m}
            style={{ left: `${(wi / totalW) * 100}%`, width: `${(0.6 / totalW) * 100}%` }}
            className={`absolute top-0 h-[60%] -translate-x-1/2 rounded-b ${k.m === midi ? 'bg-emerald-500' : 'bg-slate-900 border border-slate-700'}`}
          />
        );
      })}
    </div>
  );
}

export default function VideoconferenciaModule({ turno: turnoInicial, onNavigate, onVolver, onEnviarCuadernillo }: Props) {
  const clinical = useClinical();
  const { user } = useAuth();
  const [turno, setTurno] = useState<any>(turnoInicial);
  const [paciente, setPaciente] = useState<any>(turnoInicial?.pacientes || {});
  const [inicio, setInicio] = useState<number | null>(null);
  const [ahora, setAhora] = useState(Date.now());
  const [enLlamada, setEnLlamada] = useState(false);

  const [notas, setNotas] = useState(turnoInicial?.notas || '');
  const [objetivos, setObjetivos] = useState('');
  const [incidencias, setIncidencias] = useState('');
  const [resumen, setResumen] = useState('');
  const [bank, setBank] = useState<any[]>([]);
  const [ejercicioId, setEjercicioId] = useState('');
  const [ejDuracion, setEjDuracion] = useState(5);
  const [ejObs, setEjObs] = useState('');
  const [realizados, setRealizados] = useState<any[]>([]);
  const [presentar, setPresentar] = useState<any | null>(null);
  const [f0Sesion, setF0Sesion] = useState<number | null>(null);
  const [finalizando, setFinalizando] = useState(false);
  const [showResumen, setShowResumen] = useState(false);
  const [finalizado, setFinalizado] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  const pId = turno?.paciente_id || paciente?.id;

  // Refrescar agregado (sin start_url salvo host: este módulo es del profesional)
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/teleconsulta/${turnoInicial.id}?role=host`);
        if (r.ok) {
          const d = await r.json();
          if (d.turno) setTurno(d.turno);
          if (d.paciente?.id) setPaciente(d.paciente);
        }
      } catch {}
      try {
        const rb = await fetch(`${BACKEND_URL}/api/ejercicios`);
        if (rb.ok) {
          const b = await rb.json();
          const flat: any[] = [];
          (b.sections || []).forEach((s: any) =>
            (s.exercises || []).forEach((e: any) => flat.push({ ...e, seccion: s.name })));
          setBank(flat);
        }
      } catch {}
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cronómetro de sesión
  useEffect(() => {
    if (!enLlamada || inicio == null) return;
    const iv = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(iv);
  }, [enLlamada, inicio]);

  const duracionMin = inicio ? Math.max(1, Math.round((ahora - inicio) / 60000)) : (turno?.duracion_min || 45);
  const mmss = (ms: number) => {
    const s = Math.floor(ms / 1000);
    return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  };

  const ejercicioActual = bank.find(e => e.id === ejercicioId);

  const guardarNotas = async (silencioso = false) => {
    if (!user?.id) {
      if (!silencioso) setError('Iniciá sesión con Google para guardar en el servidor');
      return false;
    }
    try {
      const r = await fetch(`${BACKEND_URL}/api/teleconsulta/${turno.id}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          notas,
          ejercicios: realizados,
          duracion_min: duracionMin,
          incidencias,
        }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.ok) throw new Error(d.detail || `Error ${r.status}`);
      return true;
    } catch (e: any) {
      if (!silencioso) setError(e.message || 'No se pudieron guardar las notas');
      return false;
    }
  };

  const marcarRealizado = () => {
    if (!ejercicioActual) return;
    setRealizados(prev => [...prev, {
      ejercicio_id: ejercicioActual.id,
      nombre: ejercicioActual.name,
      duracion_s: ejDuracion * 60,
      observaciones: ejObs,
      f0_sesion_hz: f0Sesion,
      ts: new Date().toISOString(),
    }]);
    setEjObs('');
  };

  const finalizarSesion = async () => {
    if (!user?.id) {
      setError('Iniciá sesión con Google para finalizar en el servidor');
      return;
    }
    setFinalizando(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/teleconsulta/${turno.id}/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          notas, resumen,
          ejercicios: realizados,
          duracion_min: duracionMin,
          incidencias,
        }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.ok) throw new Error(d.detail || `Error ${r.status}`);
      if (f0Sesion) {
        clinical.setAcustica({ ...clinical.data.acustica, f0_mean: f0Sesion });
      }
      setFinalizado(true);
    } catch (e: any) {
      setError(e.message || 'No se pudo finalizar la sesión');
    }
    setFinalizando(false);
  };

  const compartirWhatsApp = (confirmar: boolean) => {
    const tel = (paciente.telefono || '').replace(/\D/g, '');
    const msg = `Hola ${paciente.nombre_completo || 'paciente'}, te comparto el resumen de tu teleconsulta fonoaudiológica (${duracionMin} min):\n\n${resumen || notas || 'Sesión completada.'}\n\n${firmaProfesional()}`;
    const hacer = () => window.open(
      tel ? `https://wa.me/${tel}?text=${encodeURIComponent(msg)}`
          : `https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`, '_blank');
    if (confirmar) {
      if (window.confirm('¿Enviar resumen por WhatsApp al paciente?')) hacer();
    } else hacer();
  };

  const compartirEmail = () => {
    if (!window.confirm('¿Abrir correo con el resumen para enviar al paciente?')) return;
    const su = encodeURIComponent(`Resumen de teleconsulta — ${paciente.nombre_completo || ''}`.trim());
    const body = encodeURIComponent(`${resumen || notas || ''}\n\nDuración: ${duracionMin} min\n\n${firmaProfesional()}`);
    if (paciente.email) {
      window.open(`https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(paciente.email)}&su=${su}&body=${body}`, '_blank');
    } else {
      window.location.href = `mailto:?subject=${su}&body=${body}`;
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      {/* Header: paciente +计时 + volver */}
      <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button onClick={onVolver} className="p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-white/5 text-gray-500" title="Volver a la agenda">
            <ArrowLeft size={18} />
          </button>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 border border-blue-500/30 flex items-center justify-center font-black text-blue-600 dark:text-blue-400">
            {(paciente.nombre_completo || 'PA').substring(0, 2).toUpperCase()}
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
              Videoconferencia — {paciente.nombre_completo || 'Paciente'}
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${enLlamada ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' : 'bg-gray-100 dark:bg-white/5 text-gray-500'}`}>
                {enLlamada ? `En sesión · ${mmss(ahora - (inicio || ahora))}` : 'Pre-sesión'}
              </span>
            </h2>
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              {turno?.motivo || turno?.tipo || 'Teleconsulta'} · {turno?.duracion_min || 45} min planificados
            </p>
          </div>
        </div>
        {!finalizado ? (
          <button
            onClick={() => setShowResumen(true)}
            disabled={!enLlamada && realizados.length === 0}
            className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-2 disabled:opacity-40"
          >
            <Flag size={14} /> Finalizar sesión
          </button>
        ) : (
          <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
            <CheckCircle2 size={14} /> Sesión finalizada y guardada
          </span>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400 font-semibold flex items-center gap-1">
          <AlertCircle size={14} /> {error}
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Panel central: video */}
        <div className="lg:col-span-2 space-y-4">
          {turno?.zoom_meeting_id ? (
            <ZoomEmbedded
              meetingNumber={turno.zoom_meeting_id}
              password={turno.zoom_password || ''}
              userName="Fonoaudiólogo/a"
              role={1}
              onJoin={() => { setEnLlamada(true); setInicio(Date.now()); }}
              onLeave={() => setEnLlamada(false)}
            />
          ) : (
            <div className="p-8 text-center rounded-2xl bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 text-xs text-gray-500">
              Este turno aún no tiene sala Zoom. Creala desde la tarjeta del turno en la Agenda.
            </div>
          )}

          {/* Material terapéutico en sesión */}
          <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 space-y-3">
            <h3 className="font-bold text-xs text-gray-900 dark:text-white flex items-center gap-2">
              <BookOpen size={14} className="text-indigo-500" /> Material terapéutico en sesión
            </h3>
            <div className="flex flex-wrap gap-2">
              <select
                value={ejercicioId}
                onChange={e => setEjercicioId(e.target.value)}
                className="flex-1 min-w-[200px] px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
              >
                <option value="">Seleccionar ejercicio actual…</option>
                {bank.map(e => (
                  <option key={e.id} value={e.id}>{e.name} ({e.seccion})</option>
                ))}
              </select>
              <input
                type="number" min={1} max={60} value={ejDuracion}
                onChange={e => setEjDuracion(Number(e.target.value) || 5)}
                title="Duración en minutos"
                className="w-20 px-2 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
              />
              <button
                onClick={() => ejercicioActual && setPresentar(ejercicioActual)}
                disabled={!ejercicioActual}
                className="px-3 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold flex items-center gap-1 disabled:opacity-40"
              >
                <Presentation size={13} /> Presentar consigna
              </button>
              <button
                onClick={marcarRealizado}
                disabled={!ejercicioActual}
                className="px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1 disabled:opacity-40"
              >
                <CheckCircle2 size={13} /> Marcar realizado
              </button>
            </div>
            {ejercicioActual && (
              <div className="text-[11px] text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-white/5 rounded-xl p-2.5">
                <p className="font-bold">{ejercicioActual.name}</p>
                <p className="mt-0.5">{ejercicioActual.description}</p>
              </div>
            )}
            <input
              type="text" value={ejObs} onChange={e => setEjObs(e.target.value)}
              placeholder="Observaciones del ejercicio (respuesta, compensaciones, dosificación real)…"
              className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
            />
            {realizados.length > 0 && (
              <div className="space-y-1">
                {realizados.map((r, i) => (
                  <div key={i} className="flex items-center justify-between text-[11px] bg-emerald-500/5 border border-emerald-500/20 rounded-lg px-2.5 py-1.5">
                    <span className="font-semibold text-gray-800 dark:text-gray-200">{r.nombre}</span>
                    <span className="text-gray-500 font-mono">{Math.round(r.duracion_s / 60)} min</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Panel lateral clínico */}
        <div className="space-y-4">
          <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 space-y-2">
            <h3 className="font-bold text-xs text-gray-900 dark:text-white flex items-center gap-2">
              <User size={14} className="text-indigo-500" /> Ficha resumida
            </h3>
            <p className="text-xs text-gray-700 dark:text-gray-300"><strong>Motivo:</strong> {clinical.data.anamnesis?.motivo_consulta || turno?.motivo || '—'}</p>
            <div className="flex flex-wrap gap-1">
              <button onClick={() => onNavigate('anamnesis', pId)} className="px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 text-[11px] font-bold">Anamnesis</button>
              <button onClick={() => onNavigate('escalas', pId)} className="px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 text-[11px] font-bold">Escalas</button>
              <button onClick={() => onNavigate('analisis', pId)} className="px-2.5 py-1 rounded-lg bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-300 text-[11px] font-bold">Praat</button>
            </div>
          </div>

          <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl p-4 space-y-2">
            <label className="font-bold text-xs text-gray-900 dark:text-white block">Objetivos de la sesión</label>
            <textarea value={objetivos} onChange={e => setObjetivos(e.target.value)} rows={2}
              placeholder="Ej: reducir hiperfunción en lectura, SOVTE 5 min…"
              className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white" />
            <label className="font-bold text-xs text-gray-900 dark:text-white block">Notas clínicas</label>
            <textarea value={notas} onChange={e => setNotas(e.target.value)} rows={4}
              placeholder="Evolución observada, F0, compensaciones…"
              className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white" />
            <button onClick={() => guardarNotas()} className="w-full py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center justify-center gap-1.5">
              <Save size={13} /> Guardar notas
            </button>
          </div>

          <PitchMini onConfirmF0={(f0) => {
            setF0Sesion(f0);
            clinical.setAcustica({ ...clinical.data.acustica, f0_mean: f0 });
          }} />
          {f0Sesion && (
            <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold">
              F0 de sesión confirmada: {f0Sesion} Hz (se incluye al finalizar)
            </p>
          )}
        </div>
      </div>

      {/* Overlay presentar consigna (para compartir pantalla) */}
      {presentar && (
        <div className="fixed inset-0 z-[60] bg-slate-950 flex flex-col items-center justify-center p-4 sm:p-8 text-center overflow-y-auto">
          <p className="text-sm text-slate-400 font-bold uppercase tracking-widest mb-4">Consigna para el paciente — compartí esta pantalla</p>
          <h2 className="text-3xl md:text-5xl font-black text-white max-w-4xl">{presentar.name}</h2>
          <div className="mt-6 space-y-3 max-w-2xl">
            {(presentar.steps || []).slice(0, 5).map((s: string, i: number) => (
              <p key={i} className="text-lg md:text-2xl text-slate-200">{i + 1}. {s}</p>
            ))}
          </div>
          <button
            onClick={() => setPresentar(null)}
            className="mt-8 px-6 py-3 rounded-2xl bg-white/10 hover:bg-white/20 text-white font-bold text-sm flex items-center gap-2"
          >
            <X size={16} /> Cerrar presentación
          </button>
        </div>
      )}

      {/* Modal finalización */}
      {showResumen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-[#111827] rounded-3xl border border-gray-200 dark:border-white/10 w-full max-w-lg shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-100 dark:border-white/10">
              <h3 className="font-bold text-sm text-gray-900 dark:text-white">Finalizar teleconsulta</h3>
              <p className="text-[11px] text-gray-500">Duración: {duracionMin} min · {realizados.length} ejercicios · {f0Sesion ? `F0 ${f0Sesion} Hz` : 'sin F0 confirmada'}</p>
            </div>
            <div className="p-6 space-y-3 text-xs">
              <div>
                <label className="font-bold text-gray-700 dark:text-gray-300 block mb-1">Resumen clínico (editable)</label>
                <textarea value={resumen} onChange={e => setResumen(e.target.value)} rows={5}
                  placeholder="Síntesis de la sesión, respuesta del paciente, plan…"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white" />
              </div>
              <div className="flex flex-wrap gap-2 justify-end">
                <button onClick={() => setShowResumen(false)} className="px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-700 text-xs font-bold text-gray-600 dark:text-gray-300">
                  Seguir en sesión
                </button>
                <button onClick={finalizarSesion} disabled={finalizando}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold disabled:opacity-50">
                  {finalizando ? 'Guardando…' : 'Guardar y finalizar'}
                </button>
              </div>
              {finalizado && (
                <div className="pt-2 border-t border-gray-100 dark:border-white/10 space-y-2">
                  <p className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 size={13} /> Sesión guardada y turno completado
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => onEnviarCuadernillo
                        ? onEnviarCuadernillo(realizados.map(r => r.ejercicio_id).filter(Boolean))
                        : onNavigate('cuadernillo', pId)}
                      className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-bold flex items-center gap-1">
                      <FileText size={12} /> Generar cuadernillo
                    </button>
                    <button
                      onClick={() => {
                        if (!window.confirm('¿Compartir resumen por WhatsApp con el paciente?')) return;
                        const tel = (paciente.telefono || '').replace(/\D/g, '');
                        const msg = `Hola ${paciente.nombre_completo || 'paciente'}, resumen de tu teleconsulta (${duracionMin} min):\n\n${resumen || notas}\n\n${firmaProfesional()}`;
                        window.open(tel ? `https://wa.me/${tel}?text=${encodeURIComponent(msg)}` : `https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`, '_blank');
                      }}
                      className="px-3 py-2 rounded-xl bg-[#25D366] hover:bg-[#1fb857] text-white text-[11px] font-bold flex items-center gap-1">
                      <MessageCircle size={12} /> WhatsApp
                    </button>
                    <button
                      onClick={() => {
                        if (!window.confirm('¿Abrir correo con el resumen para enviar al paciente?')) return;
                        const su = encodeURIComponent(`Resumen de teleconsulta — ${paciente.nombre_completo || ''}`.trim());
                        const body = encodeURIComponent(`${resumen || notas}\n\nDuración: ${duracionMin} min\n\n${firmaProfesional()}`);
                        if (paciente.email) window.open(`https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(paciente.email)}&su=${su}&body=${body}`, '_blank');
                        else window.location.href = `mailto:?subject=${su}&body=${body}`;
                      }}
                      className="px-3 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-[11px] font-bold flex items-center gap-1">
                      <Mail size={12} /> Email
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
