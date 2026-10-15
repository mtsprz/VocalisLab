import React, { useState, useEffect, useRef } from 'react';
import { Mic, Square, Upload, Trash2, Loader2, AlertCircle, WifiOff, FileAudio } from 'lucide-react';
import { useAuth } from './AuthContext';
import { leerPacientesMinimos, idbGuardar, idbListar, idbBorrar } from '../utils/pwa';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export default function GrabadorEmergencia() {
  const { user } = useAuth();
  const uid = user?.id || '';
  const [grabando, setGrabando] = useState(false);
  const [pacSel, setPacSel] = useState('');
  const [consent, setConsent] = useState(false);
  const [pendientes, setPendientes] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const archivoRef = useRef<HTMLInputElement | null>(null);
  const mrRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const wakeRef = useRef<any>(null);
  const grabIdRef = useRef('');
  const inicioRef = useRef(0);
  const online = typeof navigator !== 'undefined' ? navigator.onLine : true;
  const [isOnline, setIsOnline] = useState(online);

  const recargar = async () => {
    try { setPendientes(await idbListar()); } catch { setPendientes([]); }
  };

  useEffect(() => {
    recargar();
    const on = () => { setIsOnline(true); sincronizar(); };
    const off = () => setIsOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    try {
      if (navigator.storage?.persist) navigator.storage.persist();
    } catch {}
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const empezar = async () => {
    if (!pacSel) { setMsg('Elegí un paciente.'); return; }
    if (!consent) { setMsg('Marcá el consentimiento para grabar.'); return; }
    setMsg('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
      });
      streamRef.current = stream;
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mrRef.current = mr;
      grabIdRef.current = `emg-${Date.now()}`;
      inicioRef.current = Date.now();
      mr.ondataavailable = async (ev) => {
        if (ev.data && ev.data.size > 0) {
          await idbGuardar({
            grabacion_id: grabIdRef.current, patient_id: pacSel, consent,
            ts: Date.now(), blob: ev.data,
          });
          recargar();
        }
      };
      mr.start(30000); // bloques de 30 s
      setGrabando(true);
      try {
        // @ts-ignore
        wakeRef.current = await navigator.wakeLock?.request('screen');
      } catch {}
    } catch (e: any) {
      setMsg(`No se pudo acceder al micrófono: ${e.message || e}`);
    }
  };

  const detener = () => {
    try { mrRef.current?.stop(); } catch {}
    try { streamRef.current?.getTracks().forEach(t => t.stop()); } catch {}
    try { wakeRef.current?.release(); } catch {}
    setGrabando(false);
    recargar();
  };

  const borrarGrupo = async (gid: string) => {
    const items = pendientes.filter(p => p.grabacion_id === gid);
    for (const it of items) { try { await idbBorrar(it.id); } catch {} }
    recargar();
  };

  const sincronizar = async () => {
    if (!uid || syncing) return;
    setSyncing(true);
    setMsg('');
    try {
      const items = await idbListar();
      const grupos: Record<string, any[]> = {};
      for (const it of items) { (grupos[it.grabacion_id] = grupos[it.grabacion_id] || []).push(it); }
      let ok = 0, fail = 0;
      for (const [gid, trozos] of Object.entries(grupos)) {
        trozos.sort((a, b) => a.ts - b.ts);
        const blob = new Blob(trozos.map(t => t.blob), { type: 'audio/webm' });
        const fd = new FormData();
        fd.append('user_id', uid);
        fd.append('paciente_id', trozos[0].patient_id);
        fd.append('recorded_at', new Date(trozos[0].ts).toISOString());
        fd.append('audio_duration_sec', String(Math.round((trozos[trozos.length - 1].ts - trozos[0].ts) / 1000) + 30));
        fd.append('consent_recorded', String(!!trozos[0].consent));
        fd.append('audio', blob, `${gid}.webm`);
        try {
          const r = await fetch(`${BACKEND_URL}/api/companion/sesiones-web`, { method: 'POST', body: fd });
          const d = await r.json().catch(() => ({}));
          if (r.ok && d.ok) {
            for (const t of trozos) { try { await idbBorrar(t.id); } catch {} }
            ok++;
          } else { fail++; }
        } catch { fail++; }
      }
      setMsg(`Sincronizado: ${ok} ok${fail ? `, ${fail} pendientes (sin conexión o error)` : ''}. El borrado local ocurre SOLO tras confirmación del servidor.`);
      recargar();
    } finally {
      setSyncing(false);
    }
  };

  // Subir un archivo ya grabado (Grabadora de voz de Windows, celular…):
  // el servidor transcribe, separa las voces y mide la altura tonal (Praat).
  const subirArchivo = async (archivo: File | undefined) => {
    if (!archivo) return;
    if (!pacSel) { setMsg('Elegí un paciente antes de subir el archivo.'); return; }
    if (!consent) { setMsg('Marcá el consentimiento antes de subir el archivo.'); return; }
    if (archivo.size > 45 * 1024 * 1024) { setMsg('El archivo supera 45 MB. Exportalo como m4a/mp3 o usá la app Companion (comprime sola).'); return; }
    setSubiendo(true);
    setMsg(`Subiendo ${archivo.name}…`);
    try {
      const duracion = await new Promise<number>((res) => {
        try {
          const a = new Audio();
          a.preload = 'metadata';
          a.onloadedmetadata = () => { res(isFinite(a.duration) ? a.duration : 0); URL.revokeObjectURL(a.src); };
          a.onerror = () => res(0);
          a.src = URL.createObjectURL(archivo);
        } catch { res(0); }
      });
      const fd = new FormData();
      fd.append('user_id', uid);
      fd.append('paciente_id', pacSel);
      fd.append('recorded_at', new Date(archivo.lastModified || Date.now()).toISOString());
      fd.append('audio_duration_sec', String(Math.round(duracion)));
      fd.append('consent_recorded', 'true');
      fd.append('audio', archivo, archivo.name);
      const r = await fetch(`${BACKEND_URL}/api/companion/sesiones-web`, { method: 'POST', body: fd });
      const d = await r.json().catch(() => ({}));
      if (r.ok && d.ok) {
        setMsg(`✓ ${archivo.name} subido. Se está transcribiendo, separando voces y midiendo la altura tonal: aparece en "Voz y sesiones" del paciente en unos minutos.`);
      } else {
        setMsg(`No se pudo subir: ${d.detail || d.error || r.status}`);
      }
    } catch (e: any) {
      setMsg(`No se pudo subir (¿sin conexión?): ${e.message || e}`);
    } finally {
      setSubiendo(false);
      if (archivoRef.current) archivoRef.current.value = '';
    }
  };

  const grupos: Record<string, any[]> = {};
  for (const p of pendientes) { (grupos[p.grabacion_id] = grupos[p.grabacion_id] || []).push(p); }
  const mins = leerPacientesMinimos();

  return (
    <div className="max-w-3xl mx-auto w-full space-y-4">
      <h2 className="text-xl font-black flex items-center gap-2">
        <Mic size={20} className="text-red-500" /> Grabador de emergencia
        {!isOnline && <span className="text-[10px] px-2 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 font-black flex items-center gap-1"><WifiOff size={11} /> OFFLINE — se guarda local</span>}
      </h2>
      {msg && <p className="text-xs p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 font-semibold">{msg}</p>}
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200 dark:border-white/10 p-4 space-y-3 text-xs">
        <div>
          <label className="font-bold block mb-1">Paciente (lista mínima offline)</label>
          <select value={pacSel} onChange={e => setPacSel(e.target.value)} className="w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-white/10 bg-white dark:bg-white/5" disabled={grabando}>
            <option value="">Elegir…</option>
            {mins.map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
          </select>
          {mins.length === 0 && <p className="text-amber-600 mt-1 flex items-center gap-1"><AlertCircle size={12} /> Sin lista offline: abrí Pacientes con internet una vez.</p>}
        </div>
        <label className="flex items-center gap-2 font-semibold">
          <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} disabled={grabando} className="rounded" />
          Consentimiento verbal registrado para esta grabación
        </label>
        {!grabando
          ? <button onClick={empezar} className="px-5 py-2.5 rounded-xl bg-red-600 text-white font-bold flex items-center gap-2"><Mic size={15} /> Grabar (bloques 30 s)</button>
          : <button onClick={detener} className="px-5 py-2.5 rounded-xl bg-gray-800 text-white font-bold flex items-center gap-2"><Square size={15} /> Detener</button>}
        <p className="text-gray-400">Sin cancelación de eco/ruido ni ganancia automática. La pantalla se mantiene encendida (Wake Lock).</p>
        <div className="pt-3 border-t border-gray-100 dark:border-white/5">
          <label className="font-bold block mb-1">¿Ya grabaste con otro programa?</label>
          <input ref={archivoRef} type="file" accept="audio/*,.m4a,.mp3,.wav,.ogg,.webm,.aac" className="hidden"
            onChange={e => subirArchivo(e.target.files?.[0])} />
          <button onClick={() => archivoRef.current?.click()} disabled={grabando || subiendo || !isOnline}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white font-bold flex items-center gap-2 disabled:opacity-50">
            {subiendo ? <Loader2 size={15} className="animate-spin" /> : <FileAudio size={15} />} Subir archivo de audio
          </button>
          <p className="text-gray-400 mt-1">Grabadora de voz de Windows, celular u otra app (m4a, mp3, wav; máx. 45 MB). La IA transcribe, separa tu voz de la del paciente y mide su altura tonal.</p>
        </div>
      </div>
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-gray-200 dark:border-white/10 p-4 text-xs">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold">Pendientes de sincronizar ({Object.keys(grupos).length})</h3>
          <button onClick={sincronizar} disabled={syncing || !isOnline} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold flex items-center gap-1.5 disabled:opacity-50">
            {syncing ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />} Sincronizar ahora
          </button>
        </div>
        {Object.entries(grupos).map(([gid, t]) => (
          <div key={gid} className="flex items-center gap-2 py-1.5 border-t border-gray-100 dark:border-white/5">
            <span className="font-mono">{gid.replace('emg-', '')}</span>
            <span className="text-gray-400">{t.length} bloque(s) · {(t.reduce((a: number, x: any) => a + (x.blob?.size || 0), 0) / 1048576).toFixed(1)} MB</span>
            <button onClick={() => borrarGrupo(gid)} className="ml-auto text-red-500 font-bold flex items-center gap-1"><Trash2 size={13} /> Descartar local</button>
          </div>
        ))}
        {Object.keys(grupos).length === 0 && <p className="text-gray-400">Nada pendiente.</p>}
      </div>
    </div>
  );
}
