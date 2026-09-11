import React, { useState, useEffect } from 'react';
import {
  X, Video, Loader2, AlertCircle, CheckCircle2, ExternalLink,
  Mic, Headphones, Settings, ClipboardList, Save, KeyRound, Link2
} from 'lucide-react';

import ZoomEmbedded from './ZoomEmbedded';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  turno: any;
  pacienteNombre: string;
  onClose: () => void;
  onSalaActualizada: () => void;
}

/**
 * Teleconsulta Zoom con audio profesional.
 * - Crea la sala vía backend (Server-to-Server OAuth) con waiting room.
 * - Guía al paciente para activar "Sonido Original" (sin filtros que destruyen SOVTE/fricativas).
 * - Notas clínicas asociadas al turno.
 * Si Zoom no está configurado en el servidor, muestra la guía de setup sin romper.
 */
export default function ZoomTeleconsulta({ turno, pacienteNombre, onClose, onSalaActualizada }: Props) {
  const [config, setConfig] = useState<{ s2s_configured: boolean; sdk_configured?: boolean; advertencias?: string[] } | null>(null);
  const [creando, setCreando] = useState(false);
  const [guardandoNota, setGuardandoNota] = useState(false);
  const [error, setError] = useState('');
  const [sala, setSala] = useState<any>(
    turno?.zoom_join_url
      ? {
          zoom_meeting_id: turno.zoom_meeting_id || '',
          zoom_password: turno.zoom_password || '',
          zoom_join_url: turno.zoom_join_url,
        }
      : null
  );
  const [mostrarGuia, setMostrarGuia] = useState(false);
  const [notas, setNotas] = useState(turno?.notas || '');
  const [notaGuardada, setNotaGuardada] = useState(false);
  const [modoEmbebido, setModoEmbebido] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/teleconsulta/config`);
        if (r.ok) setConfig(await r.json());
      } catch {}
    })();
  }, []);

  const crearSala = async () => {
    setCreando(true);
    setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/teleconsulta/crear-sala`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          paciente_nombre: pacienteNombre,
          fecha_hora: turno.fecha_hora,
          duracion_min: turno.duracion_min || 45,
          turno_id: turno.id,
          motivo: turno.motivo || 'Teleconsulta fonoaudiológica',
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) {
        throw new Error(data.detail || `Error creando sala (${r.status})`);
      }
      setSala(data);
      onSalaActualizada();
    } catch (e: any) {
      setError(e.message || 'No se pudo crear la sala de Zoom');
    }
    setCreando(false);
  };

  const guardarNotas = async () => {
    setGuardandoNota(true);
    try {
      const fd = new FormData();
      fd.append('notas', notas);
      await fetch(`${BACKEND_URL}/api/turnos/${turno.id}`, { method: 'PUT', body: fd });
      setNotaGuardada(true);
      setTimeout(() => setNotaGuardada(false), 3000);
      onSalaActualizada();
    } catch {}
    setGuardandoNota(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-[#111827] rounded-3xl border border-gray-200 dark:border-white/10 w-full max-w-xl shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-100 dark:border-white/10 flex items-center justify-between sticky top-0 bg-white dark:bg-[#111827]">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
              <Video size={18} />
            </div>
            <div>
              <h3 className="font-bold text-sm text-gray-900 dark:text-white">
                Teleconsulta Zoom — {pacienteNombre}
              </h3>
              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                Audio profesional para terapia vocal (sin filtros destructivos)
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl text-gray-400 hover:text-gray-600 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs">
          {config && !config.s2s_configured && !sala && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-[11px] font-medium flex items-start gap-2">
              <AlertCircle size={15} className="shrink-0 mt-0.5" />
              <span>
                Zoom no está configurado en el servidor (faltan ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID /
                ZOOM_CLIENT_SECRET de una app Server-to-Server OAuth). Creá la app en Zoom App Marketplace
                y agregá las variables en Render para habilitar la creación de salas.
              </span>
            </div>
          )}

          {config?.advertencias && config.advertencias.length > 0 && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-700 dark:text-red-300 text-[11px] font-medium space-y-1">
              {config.advertencias.map((w, i) => (
                <p key={i} className="flex items-start gap-2">
                  <AlertCircle size={15} className="shrink-0 mt-0.5" /> {w}
                </p>
              ))}
            </div>
          )}

          {error && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-[11px] font-semibold flex items-center gap-2">
              <AlertCircle size={15} /> {error}
            </div>
          )}

          {!sala ? (
            <div className="text-center py-4 space-y-3">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Se creará una reunión con sala de espera, video de anfitrión y participante, y audio bidireccional.
              </p>
              <button
                onClick={crearSala}
                disabled={creando || (config != null && !config.s2s_configured)}
                className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs inline-flex items-center gap-2 shadow-lg shadow-blue-600/30 disabled:opacity-50"
              >
                {creando ? <Loader2 size={14} className="animate-spin" /> : <Video size={14} />}
                {creando ? 'Creando sala…' : 'Crear sala de teleconsulta'}
              </button>
            </div>
          ) : (
            <>
              <div className="p-4 rounded-2xl bg-blue-500/5 border border-blue-500/20 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                    <Link2 size={13} className="text-blue-500" /> Enlace de la sala
                  </span>
                  <span className="font-mono text-[11px] text-gray-500 flex items-center gap-1">
                    <KeyRound size={11} /> ID: {sala.zoom_meeting_id || '—'}
                    {sala.zoom_password ? ` · Clave: ${sala.zoom_password}` : ''}
                  </span>
                </div>
                <p className="text-[11px] text-blue-700 dark:text-blue-300 break-all font-mono bg-white dark:bg-black/30 rounded-lg px-2 py-1.5 border border-blue-500/20">
                  {sala.zoom_join_url}
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    onClick={() => setMostrarGuia(true)}
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs flex items-center gap-2 shadow-md shadow-blue-600/25"
                  >
                    <ExternalLink size={13} /> Unirse a la teleconsulta
                  </button>
                  {sala.zoom_meeting_id && (
                    <button
                      onClick={() => setModoEmbebido(v => !v)}
                      className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center gap-2 shadow-md shadow-indigo-600/25"
                      title="Video embebido dentro de la app (Meeting SDK Component View)"
                    >
                      <Video size={13} /> {modoEmbebido ? 'Ocultar video embebido' : 'Atender aquí embebido'}
                    </button>
                  )}
                  <button
                    onClick={() => {
                      const msg = `Hola ${pacienteNombre}, te comparto el enlace de tu teleconsulta fonoaudiológica: ${sala.zoom_join_url}${sala.zoom_password ? ` (clave: ${sala.zoom_password})` : ''}. Entrá unos minutos antes con auriculares.`;
                      window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`, '_blank');
                    }}
                    className="px-4 py-2 rounded-xl bg-[#25D366] hover:bg-[#1fb857] text-white font-bold text-xs"
                  >
                    Enviar enlace por WhatsApp
                  </button>
                </div>
              </div>

              {mostrarGuia && (
                <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 space-y-2">
                  <h4 className="font-bold text-xs text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
                    <Headphones size={14} /> Antes de unirte: audio sin filtros (obligatorio en voz)
                  </h4>
                  <ol className="text-[11px] text-gray-700 dark:text-gray-300 space-y-1.5 list-decimal list-inside">
                    <li>Usá <strong>auriculares</strong> y ubicate en un ambiente silencioso.</li>
                    <li>En Zoom → <strong>Configuración → Audio</strong> → activá <strong>“Sonido original para músicos”</strong>.</li>
                    <li>Desactivá <strong>supresión de ruido</strong> y <strong>cancelación de eco</strong>: esos filtros cortan SOVTE (vibración de labios/lengua), fricativas /s/ /z/ /f/ y screams/falsete.</li>
                    <li>Verificá tu micrófono (placa USB si disponible) con la prueba de audio.</li>
                    <li>Recién entonces abrí el enlace de la sala.</li>
                  </ol>
                  <div className="flex gap-2 pt-1">
                    <a
                      href={sala.zoom_join_url} target="_blank" rel="noopener noreferrer"
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-2"
                    >
                      <Video size={13} /> Abrir sala ahora
                    </a>
                    <button
                      onClick={() => setMostrarGuia(false)}
                      className="px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-700 text-xs font-bold text-gray-600 dark:text-gray-300"
                    >
                      Cerrar guía
                    </button>
                  </div>
                </div>
              )}

              {modoEmbebido && sala.zoom_meeting_id && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                  <div className="lg:col-span-2">
                    <ZoomEmbedded
                      meetingNumber={sala.zoom_meeting_id}
                      password={sala.zoom_password || ''}
                      userName="Fonoaudiólogo/a"
                      role={1}
                      onLeave={() => setModoEmbebido(false)}
                    />
                  </div>
                  <div className="p-3 rounded-2xl bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10">
                    <p className="text-[11px] font-bold text-gray-700 dark:text-gray-300 mb-1">
                      Notas durante la llamada
                    </p>
                    <p className="text-[10px] text-gray-400 mb-2">
                      Anamnesis, F0 observada y respuesta del paciente — se guardan en el turno.
                    </p>
                    <textarea
                      value={notas}
                      onChange={e => setNotas(e.target.value)}
                      rows={10}
                      placeholder="Notas en vivo…"
                      className="w-full px-3 py-2 bg-white dark:bg-black/30 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <button
                      onClick={guardarNotas}
                      disabled={guardandoNota}
                      className="mt-2 w-full px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs disabled:opacity-50"
                    >
                      {guardandoNota ? 'Guardando…' : 'Guardar notas'}
                    </button>
                  </div>
                </div>
              )}

              <div>
                <label className="font-bold text-xs text-gray-700 dark:text-gray-300 flex items-center gap-1.5 mb-1">
                  <ClipboardList size={13} className="text-indigo-500" /> Notas de la teleconsulta
                </label>
                <textarea
                  value={notas}
                  onChange={e => setNotas(e.target.value)}
                  rows={4}
                  placeholder="Anamnesis durante la llamada, F0 observada, ejercicios indicados, respuesta del paciente…"
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <div className="flex items-center justify-end gap-2 mt-2">
                  {notaGuardada && (
                    <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                      <CheckCircle2 size={13} /> Notas guardadas en el turno
                    </span>
                  )}
                  <button
                    onClick={guardarNotas}
                    disabled={guardandoNota}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {guardandoNota ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                    Guardar notas
                  </button>
                </div>
              </div>

              <p className="text-[10px] text-gray-400 flex items-center gap-1">
                <Mic size={11} /> Durante la llamada, pedile al paciente que active “Sonido Original”: así SOVTE, fricativas y agudos llegan sin cortes.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
