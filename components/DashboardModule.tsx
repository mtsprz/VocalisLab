import React, { useState, useEffect } from 'react';
import { Users, Calendar, FileText, Activity, Clock, AlertCircle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface DashboardProps {
  onNavigate: (m: any) => void;
  onSelectPaciente: (id: string) => void;
}

export default function DashboardModule({ onNavigate, onSelectPaciente }: DashboardProps) {
  const [stats, setStats] = useState({ total_pacientes: 0, turnos_hoy: 0, evaluaciones_mes: 0, analisis_mes: 0 });
  const [turnos, setTurnos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/dashboard`);
      if (r.ok) setStats(await r.json());
    } catch {}
    try {
      const hoy = new Date().toISOString().split('T')[0];
      const r = await fetch(`${BACKEND_URL}/api/turnos?fecha_desde=${hoy}T00:00:00&fecha_hasta=${hoy}T23:59:59`);
      if (r.ok) setTurnos(await r.json());
    } catch {}
    setLoading(false);
  };

  const statCards = [
    { label: 'Pacientes Activos', value: stats.total_pacientes, icon: <Users size={22} />, color: 'bg-blue-50 text-blue-600', action: () => onNavigate('pacientes') },
    { label: 'Turnos Hoy', value: stats.turnos_hoy, icon: <Calendar size={22} />, color: 'bg-green-50 text-green-600', action: () => {} },
    { label: 'Evaluaciones (Mes)', value: stats.evaluaciones_mes, icon: <FileText size={22} />, color: 'bg-purple-50 text-purple-600', action: () => onNavigate('escalas') },
    { label: 'Análisis (Mes)', value: stats.analisis_mes, icon: <Activity size={22} />, color: 'bg-orange-50 text-orange-600', action: () => onNavigate('analisis') },
  ];

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <button
            key={card.label}
            onClick={card.action}
            className="bg-white rounded-xl border border-gray-200 p-5 text-left hover:shadow-md transition-shadow"
          >
            <div className={`w-10 h-10 rounded-lg ${card.color} flex items-center justify-center mb-3`}>
              {card.icon}
            </div>
            <p className="text-2xl font-bold text-gray-900">{card.value}</p>
            <p className="text-sm text-gray-500 mt-1">{card.label}</p>
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Calendar size={18} /> Agenda de Hoy
        </h3>
        {turnos.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <Clock size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No hay turnos programados para hoy</p>
          </div>
        ) : (
          <div className="space-y-2">
            {turnos.map((t: any) => (
              <div key={t.id} className="flex items-center gap-4 p-3 rounded-lg bg-gray-50 border border-gray-100">
                <div className="text-sm font-mono text-gray-600 w-16">
                  {new Date(t.fecha_hora).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800">
                    {t.pacientes?.nombre_completo || 'Sin paciente'}
                  </p>
                  <p className="text-xs text-gray-500">{t.tipo} — {t.duracion_min} min</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  t.estado === 'completado' ? 'bg-green-100 text-green-700' :
                  t.estado === 'cancelado' ? 'bg-red-100 text-red-700' :
                  'bg-blue-100 text-blue-700'
                }`}>
                  {t.estado}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <button
          onClick={() => onNavigate('anamnesis')}
          className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl p-5 text-white text-left hover:shadow-lg transition-shadow"
        >
          <p className="text-lg font-semibold mb-1">Nueva Anamnesis</p>
          <p className="text-sm text-indigo-100">Grabar entrevista, transcribir con Whisper y estructurar con IA</p>
        </button>
        <button
          onClick={() => onNavigate('cuadernillo')}
          className="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl p-5 text-white text-left hover:shadow-lg transition-shadow"
        >
          <p className="text-lg font-semibold mb-1">Crear Cuadernillo</p>
          <p className="text-sm text-emerald-100">Generar PDF de ejercicios terapéuticos personalizados</p>
        </button>
      </div>
    </div>
  );
}
