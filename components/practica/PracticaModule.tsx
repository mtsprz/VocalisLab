import React from 'react';
import { Dumbbell } from 'lucide-react';
import { useClinical } from '../ClinicalContext';
import { centroPorId } from '../centros';
import PanelPractica from './PanelPractica';

/**
 * Sección «Práctica en casa»: armar y seguir la rutina guiada del paciente.
 * El origen de los ejercicios se propone solo (cuadernillo de Fonoar si el
 * paciente es de Fonoar; si no, su cuadernillo de la app) y se puede cambiar.
 */
export default function PracticaModule({ pacienteId, origenInicial }: { pacienteId: string; origenInicial?: string }) {
  const clinical = useClinical();
  const p = clinical.data.paciente;
  if (!pacienteId) {
    return <p className="text-sm text-slate-500 max-w-5xl mx-auto">Elegí un paciente en «Pacientes» para armar su práctica en casa.</p>;
  }
  const centro = centroPorId(p?.centro);
  return (
    <div className="max-w-5xl mx-auto space-y-3">
      <div className="bg-white/80 dark:bg-white/5 rounded-2xl border border-slate-200 dark:border-white/10 p-5">
        <h2 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Dumbbell size={18} className="text-indigo-500" /> Práctica en casa {p?.nombre_completo ? `· ${p.nombre_completo}` : ''}
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          {centro?.cuadernilloPropio
            ? `Paciente de ${centro.nombre}: la rutina se arma con su cuadernillo, con los mismos números que tiene en papel.`
            : 'La rutina se arma con el cuadernillo que le entregaste en la app; también podés usar ejercicios sueltos o el apartado de tracto vocal semiocluido.'}
        </p>
        <div className="mt-4 text-xs">
          <PanelPractica key={`${pacienteId}-${origenInicial || 'auto'}`} pacienteId={pacienteId} origenInicial={origenInicial} />
        </div>
      </div>
    </div>
  );
}
