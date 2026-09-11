import React, { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle, PhoneOff } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  meetingNumber: string;
  password: string;
  userName: string;
  /** 1 = terapeuta (host), 0 = paciente */
  role?: number;
  onLeave?: () => void;
  onJoin?: () => void;
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
export function ZoomEmbedded({ meetingNumber, password, userName, role = 1, onLeave, onJoin }: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<any>(null);
  const [status, setStatus] = useState<'cargando' | 'en_llamada' | 'error'>('cargando');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    let cancelled = false;

    // El SDK puede rechazar el join fuera del await (evento interno).
    // Convertir el error 3712 en mensaje accionable en vez de spam en consola.
    const onUnhandled = (ev: PromiseRejectionEvent) => {
      const r: any = ev.reason;
      if (r && (r.errorCode === 3712 || /signature is invalid/i.test(String(r.reason || r.message || '')))) {
        ev.preventDefault();
        if (!cancelled) {
          setErrorMsg(
            'Firma Zoom inválida (error 3712): las credenciales no corresponden a una app con Meeting SDK habilitado. ' +
            'En Render, ZOOM_SDK_KEY y ZOOM_SDK_SECRET deben ser el Client ID y Client Secret de una app “General App” ' +
            '(Marketplace → Build App → General App → Features → Embed → Meeting SDK ON), NO las de la app Server-to-Server.'
          );
          setStatus('error');
        }
      }
    };
    window.addEventListener('unhandledrejection', onUnhandled);

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

        if (cancelled) return;
        const client = ZoomMtgEmbedded.createClient();
        clientRef.current = client;

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
          setStatus('en_llamada');
          onJoin?.();
        }
      } catch (e: any) {
        if (!cancelled) {
          setErrorMsg(e.message || 'No se pudo unir a la sala embebida');
          setStatus('error');
        }
      }
    })();

    return () => {
      cancelled = true;
      window.removeEventListener('unhandledrejection', onUnhandled);
      try {
        clientRef.current?.leave?.();
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meetingNumber]);

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
          <div className="absolute inset-0 rounded-2xl bg-slate-950/95 flex flex-col items-center justify-center gap-3 p-6 text-center pointer-events-none">
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
                <p className="text-[11px] text-slate-500">
                  Podés unirte igual con el enlace directo de Zoom o la app de escritorio.
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
