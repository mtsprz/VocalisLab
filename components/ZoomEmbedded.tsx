import React, { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle, PhoneOff, RotateCcw, ExternalLink } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
/** Tiempo máximo esperando init/join antes de mostrar error accionable. */
const JOIN_TIMEOUT_MS = 60000;

interface Props {
  meetingNumber: string;
  password: string;
  userName: string;
  /** 1 = terapeuta (host), 0 = paciente */
  role?: number;
  /** Enlace directo a la sala (fallback cuando el embebido falla). */
  joinUrl?: string;
  onLeave?: () => void;
  onJoin?: () => void;
}

/**
 * Traduce rechazos del SDK (vienen como objetos {errorCode, reason}, no Error)
 * a mensajes accionables en español. Devuelve null si no es del SDK Zoom.
 */
function zoomRejectionMessage(r: any): string | null {
  if (r == null) return null;
  const code = typeof r === 'object' ? r.errorCode ?? r.code : null;
  const raw = typeof r === 'string'
    ? r
    : String(r.reason ?? r.message ?? r.error ?? '');
  const low = raw.toLowerCase();
  const isZoom = typeof code === 'number'
    || /zoom|meeting|signature|hardware acceleration|video encoding|media/i.test(raw);
  if (!isZoom) return null;
  if (code === 3712 || /signature is invalid/i.test(raw)) {
    return 'Firma Zoom inválida (error 3712): las credenciales no corresponden a una app con Meeting SDK habilitado. '
      + 'En Render, ZOOM_SDK_KEY y ZOOM_SDK_SECRET deben ser el Client ID y Client Secret de una app “General App” '
      + '(Marketplace → Build App → General App → Features → Embed → Meeting SDK ON), NO las de la app Server-to-Server.';
  }
  if (/hardware acceleration|video encoding/i.test(raw)) {
    return 'Zoom bloqueó la aceleración de video por restricción de la cuenta (sin HD/720p habilitado). '
      + 'El embebido puede quedar en negro: unite con la app de escritorio de Zoom o pedí habilitar HD en tu plan. '
      + `Detalle técnico: ${raw.slice(0, 200)}`;
  }
  if (/network|timeout|connection|reconnect/i.test(low)) {
    return `Se perdió la conexión con la sala de Zoom (${raw.slice(0, 160)}). Revisá tu internet y reintentá.`;
  }
  if (/sharedarraybuffer|noise suppression/i.test(low)) {
    return 'Supresión de ruido no disponible en este navegador (requiere escritorio con crossed-isolated). El audio sigue funcionando sin ese filtro.';
  }
  return `Zoom devolvió un error${typeof code === 'number' ? ` (${code})` : ''}: ${raw.slice(0, 220) || 'fallo desconocido del SDK'}. Probá reintentar o unirte con el enlace directo.`;
}

/**
 * Teleconsulta embebida con Zoom Meeting SDK (Component View, patrón oficial
 * zoom/meetingsdk-web-sample → Components/).
 *
 * - La firma se genera en el backend (/api/teleconsulta/zoom-signature).
 * - El SDK se importa dinámicamente: si el paquete no está instalado o la
 *   firma falla, muestra fallback con enlace directo (no rompe la app).
 * - Sonido Original: el SDK web no permite forzarlo por código (a diferencia
 *   del Video SDK); el paciente debe activarlo en el panel de audio de Zoom.
 *   Ver guía en ZoomTeleconsulta.
 */
export function ZoomEmbedded({ meetingNumber, password, userName, role = 1, joinUrl, onLeave, onJoin }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<any>(null);
  const joinedRef = useRef(false);
  const [status, setStatus] = useState<'cargando' | 'en_llamada' | 'error'>('cargando');
  const [errorMsg, setErrorMsg] = useState('');
  // Reintentos: cambiar la key vuelve a montar el efecto (reinit limpio del SDK).
  const [attempt, setAttempt] = useState(0);

  const fail = (msg: string) => {
    setErrorMsg(msg);
    setStatus('error');
  };

  useEffect(() => {
    let cancelled = false;
    joinedRef.current = false;
    setStatus('cargando');
    setErrorMsg('');

    // El SDK rechaza promesas fuera del await (fallas de media/red/hardware).
    // Mapearlas a mensajes accionables y evitar el "Uncaught (in promise)".
    const onUnhandled = (ev: PromiseRejectionEvent) => {
      const msg = zoomRejectionMessage(ev.reason);
      if (msg) {
        ev.preventDefault();
        if (!cancelled) fail(msg);
      }
    };
    window.addEventListener('unhandledrejection', onUnhandled);

    // Timeout: si init/join cuelga, no dejar loader infinito.
    const timeoutId = window.setTimeout(() => {
      if (!cancelled && !joinedRef.current) {
        fail('Zoom tardó demasiado en conectar (60 s). Puede ser red, cuenta sin permisos de video, o sala llena. Reintentá o unite con el enlace directo.');
      }
    }, JOIN_TIMEOUT_MS);

    (async () => {
      try {
        // 1. Firma desde el backend
        const rs = await fetch(`${BACKEND_URL}/api/teleconsulta/zoom-signature`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ meeting_number: meetingNumber, role }),
        });
        const sig = await rs.json().catch(() => ({}));
        if (!rs.ok || !sig.signature) {
          throw new Error(sig.detail || `Firma Zoom no disponible (${rs.status}). Verificá ZOOM_SDK_KEY/SECRET en Render.`);
        }

        // 2. SDK (import dinámico con fallback amable)
        let ZoomMtgEmbedded: any;
        try {
          const mod = await import('@zoom/meetingsdk/embedded');
          ZoomMtgEmbedded = mod.default ?? mod;
        } catch {
          throw new Error('Paquete @zoom/meetingsdk no instalado. Corré `npm install` y redeployá.');
        }
        try {
          await import('@zoom/meetingsdk/dist/css/bootstrap.css');
          await import('@zoom/meetingsdk/dist/css/react-select.css');
        } catch {}
        // El reboot de Bootstrap pisa el fondo del body en blanco y "rompe"
        // el modo noche de la app. Reafirmar nuestros fondos DESPUÉS de que
        // cargue su CSS (gana por orden de cascada). Singleton por sesión.
        try {
          if (!document.getElementById('zoom-bootstrap-compensation')) {
            const st = document.createElement('style');
            st.id = 'zoom-bootstrap-compensation';
            st.textContent = [
              'html body{background-color:#f3f4f6 !important;color:#0f172a !important;}',
              'html.dark body{background-color:#020617 !important;color:#e2e8f0 !important;}',
              'html.dark{color-scheme:dark;}',
            ].join('\n');
            document.head.appendChild(st);
          }
        } catch {}

        if (cancelled) return;
        const client = ZoomMtgEmbedded.createClient();
        clientRef.current = client;

        // Si la conexión cae DESPUÉS del join (video/red), mostrar error con
        // reintento en vez de dejar el área en negro/blanco.
        try {
          if (typeof client.on === 'function') {
            client.on('connection-change', (payload: any) => {
              const state = String(payload?.state ?? payload ?? '').toLowerCase();
              if (cancelled) return;
              if ((state === 'closed' || state === 'failed') && joinedRef.current) {
                joinedRef.current = false;
                fail('Se cortó la conexión con la sala de Zoom. Reintentá o unite con el enlace directo.');
              }
            });
          }
        } catch {}

        // NOTA: no pasar `videoElement` (deprecado en el SDK: usar attachVideo/
        // renderVideo si se maneja video propio; el Component View lo gestiona solo).
        await client.init({
          zoomAppRoot: rootRef.current,
          language: 'es-ES',
        });

        await client.join({
          signature: sig.signature,
          sdkKey: sig.sdkKey,
          meetingNumber,
          password,
          userName: userName || 'Fonoaudiólogo/a',
        });

        if (!cancelled) {
          joinedRef.current = true;
          setStatus('en_llamada');
          onJoin?.();
        }
      } catch (e: any) {
        if (!cancelled) {
          const mapped = zoomRejectionMessage(e);
          fail(mapped ?? (e.message || 'No se pudo unir a la sala embebida'));
        }
      } finally {
        window.clearTimeout(timeoutId);
      }
    })();

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      window.removeEventListener('unhandledrejection', onUnhandled);
      try {
        clientRef.current?.leave?.();
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meetingNumber, attempt]);

  const colgar = async () => {
    try {
      await clientRef.current?.leave?.();
    } catch {}
    onLeave?.();
  };

  // El root del SDK queda SIEMPRE vacío para React: el SDK muta ese DOM
  // directamente (lo vacía al hacer init). Los estados se renderizan como
  // overlays HERMANOS para que React nunca intente remover nodos del SDK
  // (evita NotFoundError: removeChild en la reconciliación).
  return (
    <div className="space-y-2">
      <div className="relative">
        <div
          ref={rootRef}
          id="meetingSDKElement"
          className="w-full min-h-[320px] sm:min-h-[480px] bg-slate-950 rounded-2xl border border-slate-800 overflow-hidden"
        />
        {status !== 'en_llamada' && (
          <div className="absolute inset-0 rounded-2xl bg-slate-950/95 flex flex-col items-center justify-center gap-3 p-6 text-center">
            {status === 'cargando' ? (
              <>
                <Loader2 size={28} className="animate-spin text-blue-500" />
                <p className="text-xs font-semibold text-slate-400">Conectando sala embebida…</p>
              </>
            ) : (
              <>
                <AlertCircle size={28} className="text-amber-500" />
                <p className="text-xs font-bold text-slate-200">No se pudo embeber el video</p>
                <p className="text-[11px] text-slate-400 max-w-sm">{errorMsg}</p>
                <div className="flex flex-wrap justify-center gap-2 pt-1">
                  <button
                    onClick={() => setAttempt(a => a + 1)}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center gap-1.5"
                  >
                    <RotateCcw size={13} /> Reintentar embebido
                  </button>
                  {joinUrl && (
                    <a
                      href={joinUrl} target="_blank" rel="noopener noreferrer"
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5"
                    >
                      <ExternalLink size={13} /> Abrir en Zoom
                    </a>
                  )}
                </div>
                <p className="text-[11px] text-slate-500">
                  También podés unirte con la app de escritorio de Zoom.
                </p>
              </>
            )}
          </div>
        )}
      </div>
      {status === 'en_llamada' && (
        <div className="flex justify-end">
          <button
            onClick={colgar}
            className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white font-bold text-xs flex items-center gap-2"
          >
            <PhoneOff size={14} /> Colgar
          </button>
        </div>
      )}
    </div>
  );
}

export default React.memo(ZoomEmbedded);
