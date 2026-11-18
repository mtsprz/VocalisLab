import React, { useState } from 'react';
import { X, Loader2, Music, CheckCircle2, AlertTriangle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onImportado: () => void;
}

const ACCION: Record<string, string> = { nuevo: 'Nuevo', actualizado: 'Se actualiza', existente: 'Ya cargado' };

/**
 * Pegado manual de la planilla "ALUMNOS DE CANTO" (pestaña MATIAS). El
 * script de Google la importa sola cada mañana; esto sirve para actualizar
 * en el momento. Crea/actualiza alumnos, sus clases de las próximas 4
 * semanas (con reemplazos puntuales) y el estado de pago por mes.
 */
export default function ImportarPlanillaCanto({ isOpen, onClose, onImportado }: Props) {
  const [contenido, setContenido] = useState('');
  const [vista, setVista] = useState<any | null>(null);
  const [hecho, setHecho] = useState<any | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const enviar = async (simular: boolean) => {
    setCargando(true); setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/canto/importar-planilla`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contenido, simular }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.ok) throw new Error(d.detail || d.error || `Error ${r.status}`);
      if (simular) setVista(d); else { setHecho(d); setVista(null); onImportado(); }
    } catch (e: any) {
      setError(e?.message || 'No se pudo leer la planilla');
    }
    setCargando(false);
  };

  const cerrar = () => { setContenido(''); setVista(null); setHecho(null); setError(''); onClose(); };
  const liq = (vista || hecho)?.liquidacion;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 w-full max-w-3xl max-h-[90vh] overflow-y-auto p-5 shadow-2xl">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Music size={18} className="text-pink-500" /> Planilla de alumnos de canto
          </h3>
          <button onClick={cerrar} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10"><X size={16} /></button>
        </div>

        {hecho ? (
          <div className="space-y-2">
            <p className="text-sm text-emerald-700 dark:text-emerald-300 font-semibold flex items-center gap-2">
              <CheckCircle2 size={16} /> {hecho.alumnos_nuevos} alumnos nuevos, {hecho.alumnos_actualizados} actualizados,
              {' '}{hecho.clases_nuevas} clases agregadas a la agenda.
            </p>
            {(hecho.avisos || []).map((a: string) => (
              <p key={a} className="text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} />{a}</p>
            ))}
            <button onClick={cerrar} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold">Listo</button>
          </div>
        ) : (
          <>
            <p className="text-xs text-gray-600 dark:text-gray-300 mb-2">
              El script de Google la importa sola cada mañana. Para actualizarla ahora: en la planilla, pestaña
              <b> MATIAS</b>, seleccioná desde «DÍA» hasta la última fila (incluí la liquidación si querés), copiá y pegá acá.
            </p>
            <textarea value={contenido} onChange={e => { setContenido(e.target.value); setVista(null); }} rows={7}
              placeholder={'DÍA\tHORA\tALUMNOS\tEDAD\tDNI\tCELULAR\tEMAIL\tNOVIEMBRE…'}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-900 dark:text-gray-100 rounded-xl text-xs font-mono" />
            <div className="flex justify-end mt-2">
              <button onClick={() => enviar(true)} disabled={!contenido.trim() || cargando}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold disabled:opacity-50 flex items-center gap-1.5">
                {cargando && <Loader2 size={13} className="animate-spin" />} Ver vista previa
              </button>
            </div>
            {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

            {vista && (
              <div className="mt-4 space-y-3">
                {(vista.detalle || []).map((d: any) => (
                  <div key={d.alumno} className="rounded-xl border border-gray-200 dark:border-white/10 p-3 text-xs text-gray-800 dark:text-gray-200">
                    <p className="font-bold">{d.alumno} <span className="font-normal text-gray-500">· {d.horario} · {ACCION[d.accion] || d.accion}</span></p>
                    <p className="mt-1 text-gray-600 dark:text-gray-300">Próximas clases: {(d.clases || []).join(' · ') || '—'}</p>
                    {Object.entries(d.pagos || {}).map(([mes, txt]) => (
                      <p key={mes} className="text-gray-500">{mes}: {String(txt)}</p>
                    ))}
                  </div>
                ))}
                {(vista.avisos || []).map((a: string) => (
                  <p key={a} className="text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} />{a}</p>
                ))}
                <div className="flex justify-end">
                  <button onClick={() => enviar(false)} disabled={cargando}
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50 flex items-center gap-1.5">
                    {cargando && <Loader2 size={13} className="animate-spin" />} Importar
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {liq?.items?.length > 0 && (
          <div className="mt-4 rounded-xl bg-pink-50 dark:bg-pink-500/10 border border-pink-200 dark:border-pink-500/30 p-3 text-xs">
            <p className="font-bold text-pink-800 dark:text-pink-300">Liquidación {liq.mes}</p>
            {liq.items.map((i: any, n: number) => (
              <p key={n} className="text-gray-700 dark:text-gray-200">
                {i.actividad === 'Total' ? <b>Total: {i.pago} · tu parte: {i.docente}</b> : `${i.alumno}: ${i.pago} → ${i.docente}`}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
