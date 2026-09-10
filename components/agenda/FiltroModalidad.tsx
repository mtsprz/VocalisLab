import React from 'react';
import { Video, Building2, Layers } from 'lucide-react';

export type ModalidadFiltro = 'TODAS' | 'PRESENCIAL' | 'VIRTUAL';

interface Props {
  valor: ModalidadFiltro;
  onChange: (val: ModalidadFiltro) => void;
  conteo?: { todas: number; presenciales: number; virtuales: number };
}

export default function FiltroModalidad({ valor, onChange, conteo }: Props) {
  const opciones: { id: ModalidadFiltro; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: 'TODAS', label: 'Todas las Citas', icon: <Layers size={14} />, badge: conteo?.todas },
    { id: 'PRESENCIAL', label: 'Presenciales', icon: <Building2 size={14} />, badge: conteo?.presenciales },
    { id: 'VIRTUAL', label: 'Virtuales (Meet)', icon: <Video size={14} />, badge: conteo?.virtuales },
  ];

  return (
    <div className="inline-flex items-center p-1 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-xs font-medium">
      {opciones.map(op => {
        const activa = valor === op.id;
        return (
          <button
            key={op.id}
            onClick={() => onChange(op.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
              activa
                ? 'bg-white dark:bg-indigo-600 text-gray-900 dark:text-white shadow-sm font-semibold'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <span className={activa ? 'text-indigo-600 dark:text-white' : 'text-gray-400'}>
              {op.icon}
            </span>
            <span>{op.label}</span>
            {op.badge !== undefined && (
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full ml-0.5 ${
                activa
                  ? 'bg-indigo-100 dark:bg-white/20 text-indigo-700 dark:text-white'
                  : 'bg-gray-200 dark:bg-white/10 text-gray-500 dark:text-gray-400'
              }`}>
                {op.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
