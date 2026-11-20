import React, { useEffect, useState } from 'react';
import { Bot, Loader2, Send, ExternalLink, CheckCircle2, AlertTriangle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

/**
 * Asistente personal por Telegram: estado, activación (conecta el bot con
 * el servidor y da el enlace para vincular tu chat) y mensaje de prueba.
 */
export default function AsistenteCard() {
  const [estado, setEstado] = useState<any | null>(null);
  const [enlace, setEnlace] = useState('');
  const [cargando, setCargando] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);

  const cargar = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/asistente/estado`);
      if (r.ok) setEstado(await r.json());
    } catch {}
  };
  useEffect(() => { cargar(); }, []);

  const activar = async () => {
    setCargando(true); setMsg(null);
    try {
      const r = await fetch(`${BACKEND_URL}/api/asistente/activar`, { method: 'POST' });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setEnlace(d.enlace);
      await cargar();
    } catch (e: any) {
      setMsg({ ok: false, t: e?.message || 'No se pudo activar' });
    }
    setCargando(false);
  };

  const probar = async () => {
    setCargando(true); setMsg(null);
    try {
      const r = await fetch(`${BACKEND_URL}/api/asistente/probar`, { method: 'POST' });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setMsg({ ok: true, t: 'Mensaje enviado: revisá Telegram.' });
    } catch (e: any) {
      setMsg({ ok: false, t: e?.message || 'No se pudo enviar' });
    }
    setCargando(false);
  };

  return (
    <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-bold text-gray-900 dark:text-white flex items-center gap-2 text-sm">
            <Bot size={17} className="text-indigo-500" /> Asistente del Consultorio (Telegram)
            {estado?.vinculado && <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold">activo</span>}
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-xl">
            Te avisa cuando llega la agenda de Fonoar, te manda el repaso del día a las 7:30 y entiende
            texto y notas de voz: consulta agenda, pacientes, práctica en casa y autoevaluaciones, y
            agenda, reprograma o cancela turnos, anota, envía la autoevaluación o abre una sala, siempre
            con tu confirmación. Comandos: /hoy /manana /semana /pendientes /repaso.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={activar} disabled={cargando}
            className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50">
            {cargando ? <Loader2 size={13} className="animate-spin" /> : <Bot size={13} />}
            {estado?.vinculado ? 'Revincular' : 'Activar asistente'}
          </button>
          {estado?.vinculado && (
            <button onClick={probar} disabled={cargando}
              className="px-4 py-2 rounded-xl border border-gray-300 dark:border-white/10 text-gray-700 dark:text-gray-200 text-xs font-bold flex items-center gap-1.5">
              <Send size={13} /> Probar
            </button>
          )}
        </div>
      </div>

      {estado && !estado.bot_configurado && (
        <p className="mt-3 text-xs text-amber-700 dark:text-amber-300 flex gap-1.5">
          <AlertTriangle size={13} className="shrink-0 mt-0.5" />
          Falta el bot: en Telegram abrí @BotFather → /newbot, copiá el token y cargalo en Render →
          Environment como TELEGRAM_BOT_TOKEN. Después tocá «Activar asistente».
        </p>
      )}
      {enlace && (
        <p className="mt-3 text-xs text-gray-700 dark:text-gray-200">
          Último paso: abrí este enlace en el celular y tocá «Iniciar» en Telegram (vence en 30 minutos):{' '}
          <a href={enlace} target="_blank" rel="noreferrer" className="text-indigo-600 underline inline-flex items-center gap-1">
            {enlace} <ExternalLink size={11} />
          </a>
        </p>
      )}
      {msg && (
        <p className={`mt-3 text-xs flex gap-1.5 ${msg.ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-600'}`}>
          {msg.ok ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />} {msg.t}
        </p>
      )}
    </div>
  );
}
