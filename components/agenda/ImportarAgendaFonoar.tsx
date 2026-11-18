import React, { useState } from 'react';
import { X, Loader2, ClipboardPaste, CheckCircle2, AlertTriangle, KeyRound } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onImportado: () => void;
}

const TIPO: Record<string, string> = {
  terapia: 'Tratamiento', evaluacion: 'Evaluación', control: 'Control', primera_vez: 'Primera vez',
};
const ACCION: Record<string, string> = { nuevo: 'Nuevo', actualizado: 'Se completan datos', existente: 'Ya cargado' };

/**
 * Importa el mail "Fonoar: Turnos del DD/MM/AAAA" (llega los martes a la
 * cuenta del consultorio). Se copia la tabla desde Gmail, se pega acá, se ve
 * la vista previa y se confirma: crea/actualiza pacientes (centro Fonoar La
 * Plata, obra social, teléfono) y crea los turnos sin duplicar.
 */
export default function ImportarAgendaFonoar({ isOpen, onClose, onImportado }: Props) {
  const [contenido, setContenido] = useState('');
  const [fecha, setFecha] = useState('');
  const [vista, setVista] = useState<any | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');
  const [hecho, setHecho] = useState<any | null>(null);
  const [clave, setClave] = useState('');

  if (!isOpen) return null;

  const enviar = async (simular: boolean) => {
    setCargando(true);
    setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/agenda/importar-fonoar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contenido, fecha: fecha || undefined, simular }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.ok) throw new Error(d.detail || d.error || `Error ${r.status}`);
      if (simular) {
        setVista(d);
        if (!fecha && d.fecha) setFecha(d.fecha);
      } else {
        setHecho(d);
        setVista(null);
        onImportado();
      }
    } catch (e: any) {
      setError(e?.message || 'No se pudo leer la agenda');
    }
    setCargando(false);
  };

  /** Copia el script de Google (con la clave ya incluida) al portapapeles. */
  const copiarScript = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/agenda/script-gmail`);
      if (!r.ok) throw new Error(`Error ${r.status}`);
      await navigator.clipboard.writeText(await r.text());
      setClave('copiado');
    } catch (e: any) {
      setError(`No se pudo copiar el script: ${e?.message || 'error'}`);
    }
  };

  const cerrar = () => {
    setContenido(''); setFecha(''); setVista(null); setHecho(null); setError(''); setClave('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 w-full max-w-3xl max-h-[90vh] overflow-y-auto p-5 shadow-2xl">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <ClipboardPaste size={18} className="text-indigo-500" /> Importar agenda de Fonoar
          </h3>
          <button onClick={cerrar} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-white/10"><X size={16} /></button>
        </div>

        {hecho ? (
          <div className="space-y-3">
            <p className="text-sm text-emerald-700 dark:text-emerald-300 font-semibold flex items-center gap-2">
              <CheckCircle2 size={16} /> Agenda del {hecho.fecha} importada:
              {' '}{hecho.turnos_nuevos} turnos nuevos, {hecho.pacientes_nuevos} pacientes nuevos
              {hecho.turnos_existentes ? `, ${hecho.turnos_existentes} turnos ya estaban cargados` : ''}.
            </p>
            {(hecho.avisos || []).map((a: string) => (
              <p key={a} className="text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} />{a}</p>
            ))}
            <button onClick={cerrar} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold">Listo</button>
          </div>
        ) : (
          <>
            <ol className="text-xs text-gray-600 dark:text-gray-300 list-decimal pl-5 space-y-0.5 mb-3">
              <li>Abrí en Gmail el mail <b>«Fonoar: Turnos del …»</b>.</li>
              <li>Seleccioná desde «Turnos del …» hasta la última fila de la tabla y copiá (Ctrl+C).</li>
              <li>Pegalo abajo (Ctrl+V) y tocá «Ver vista previa».</li>
            </ol>
            <textarea
              value={contenido}
              onChange={e => { setContenido(e.target.value); setVista(null); }}
              rows={7}
              placeholder={'Turnos del 18/11/2026 Mat: 7276\nHora\tPaciente\tO.Social\tTelefono\n09:30\tALVAREZ YESICA TTO\tIOMA\t…'}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-900 dark:text-gray-100 rounded-xl text-xs font-mono"
            />
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <label className="text-xs text-gray-600 dark:text-gray-300">Fecha de los turnos</label>
              <input type="date" value={fecha} onChange={e => { setFecha(e.target.value); setVista(null); }}
                className="px-2 py-1 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-900 dark:text-gray-100 rounded-lg text-xs" />
              <span className="text-[11px] text-gray-500">(se detecta sola del texto «Turnos del …»)</span>
              <button onClick={() => enviar(true)} disabled={!contenido.trim() || cargando}
                className="ml-auto px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold disabled:opacity-50 flex items-center gap-1.5">
                {cargando && <Loader2 size={13} className="animate-spin" />} Ver vista previa
              </button>
            </div>
            {error && <p className="mt-2 text-xs text-red-600">{error}</p>}

            {vista && (
              <div className="mt-4 space-y-2">
                <p className="text-xs font-bold text-gray-800 dark:text-gray-200">
                  Turnos del {vista.fecha} · Fonoar La Plata · {vista.turnos_nuevos} nuevos
                  {vista.turnos_existentes ? ` · ${vista.turnos_existentes} ya cargados` : ''}
                </p>
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-gray-500 border-b border-gray-200 dark:border-white/10">
                    <th className="py-1">Hora</th><th>Paciente</th><th>Tipo</th><th>O. social</th><th>Paciente en la app</th><th>Turno</th>
                  </tr></thead>
                  <tbody>
                    {(vista.detalle || []).map((d: any) => (
                      <tr key={`${d.hora}-${d.paciente}`} className="border-b border-gray-100 dark:border-white/5 text-gray-800 dark:text-gray-200">
                        <td className="py-1 font-mono">{d.hora}</td><td>{d.paciente}</td><td>{TIPO[d.tipo] || d.tipo}</td>
                        <td>{d.obra_social || '—'}</td><td>{ACCION[d.accion_paciente] || d.accion_paciente}</td>
                        <td>{ACCION[d.accion_turno] || d.accion_turno}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(vista.avisos || []).map((a: string) => (
                  <p key={a} className="text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} />{a}</p>
                ))}
                <div className="flex justify-end">
                  <button onClick={() => enviar(false)} disabled={cargando || !(vista.detalle || []).length}
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold disabled:opacity-50 flex items-center gap-1.5">
                    {cargando && <Loader2 size={13} className="animate-spin" />} Importar a la agenda
                  </button>
                </div>
              </div>
            )}

            <details className="mt-5 text-xs text-gray-600 dark:text-gray-300">
              <summary className="cursor-pointer font-semibold flex items-center gap-1.5"><KeyRound size={13} /> Importación automática desde Gmail</summary>
              <p className="mt-2">
                Un script de Google en la cuenta que recibe estos mails los importa solo, cada hora, sin duplicar.
                Instalación única:
              </p>
              <ol className="list-decimal pl-5 mt-1 space-y-0.5">
                <li>Tocá «Copiar script» (ya incluye tu clave: no lo compartas).</li>
                <li>Entrá a <a href="https://script.google.com" target="_blank" rel="noreferrer" className="text-indigo-600 underline">script.google.com</a> con
                  la cuenta que recibe los mails de Fonoar → «Nuevo proyecto».</li>
                <li>Borrá lo que aparece, pegá el script y guardá (Ctrl+S).</li>
                <li>Arriba elegí la función <b>instalar</b> → «Ejecutar» y aceptá los permisos
                  (si dice «Google no verificó esta app»: Configuración avanzada → Ir al proyecto).</li>
              </ol>
              <button onClick={copiarScript} className="mt-2 px-3 py-1 rounded-lg border border-gray-300 dark:border-gray-700">
                {clave === 'copiado' ? '✓ Script copiado' : 'Copiar script'}
              </button>
            </details>
          </>
        )}
      </div>
    </div>
  );
}
