import React, { useState, useEffect } from 'react';
import { Users, Calendar, FileText, Activity, Clock, AlertCircle, Sparkles, ExternalLink } from 'lucide-react';
import { useAuth } from './AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface DashboardProps {
  onNavigate: (m: any) => void;
  onSelectPaciente: (id: string) => void;
}

export default function DashboardModule({ onNavigate, onSelectPaciente }: DashboardProps) {
  const { user } = useAuth();
  const [stats, setStats] = useState({ total_pacientes: 0, turnos_hoy: 0, evaluaciones_mes: 0, analisis_mes: 0 });
  const [turnos, setTurnos] = useState<any[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
    loadCalendarEvents();
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

  const loadCalendarEvents = async () => {
    if (!user?.id) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/calendar/events?user_id=${user.id}`);
      if (r.ok) {
        const data = await r.json();
        setCalendarEvents(data.events || []);
      }
    } catch {}
  };

  const statCards = [
    { label: 'Pacientes Activos', value: stats.total_pacientes, icon: <Users size={22} />, color: 'bg-blue-500/10 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400', action: () => onNavigate('pacientes') },
    { label: 'Turnos Hoy', value: stats.turnos_hoy, icon: <Calendar size={22} />, color: 'bg-green-500/10 text-green-600 dark:bg-green-500/20 dark:text-green-400', action: () => {} },
    { label: 'Evaluaciones (Mes)', value: stats.evaluaciones_mes, icon: <FileText size={22} />, color: 'bg-purple-500/10 text-purple-600 dark:bg-purple-500/20 dark:text-purple-400', action: () => onNavigate('escalas') },
    { label: 'Análisis (Mes)', value: stats.analisis_mes, icon: <Activity size={22} />, color: 'bg-orange-500/10 text-orange-600 dark:bg-orange-500/20 dark:text-orange-400', action: () => onNavigate('analisis') },
  ];

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <button
            key={card.label}
            onClick={card.action}
            className="bg-white/70 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-white/20 dark:border-white/10 p-5 text-left hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-indigo-500/10 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
          >
            <div className={`w-10 h-10 rounded-xl ${card.color} flex items-center justify-center mb-3 backdrop-blur-sm`}>
              {card.icon}
            </div>
            <p className="text-2xl font-extrabold text-gray-900 dark:text-white tracking-tight">{card.value}</p>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mt-1 uppercase tracking-wider">{card.label}</p>
          </button>
        ))}
      </div>

      <div className="bg-white/70 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-white/20 dark:border-white/10 p-5 shadow-sm transition-all duration-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white flex items-center gap-2">
            <Calendar size={18} className="text-indigo-600 dark:text-indigo-400" /> Agenda de Hoy
          </h3>
          <button
            onClick={() => onNavigate('agenda')}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors"
          >
            Ver agenda completa
          </button>
        </div>
        {turnos.length === 0 && calendarEvents.length === 0 ? (
          <div className="text-center py-8 text-gray-400 dark:text-gray-500">
            <Clock size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No hay turnos ni eventos programados para hoy</p>
          </div>
        ) : (
          <div className="space-y-2">
            {turnos.map((t: any) => (
              <div key={t.id} className="flex items-center gap-4 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/40 border border-gray-100 dark:border-gray-800/80">
                <div className="text-sm font-mono text-gray-600 dark:text-gray-400 w-16">
                  {new Date(t.fecha_hora).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-800 dark:text-white">
                    {t.pacientes?.nombre_completo || 'Sin paciente'}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{t.tipo} — {t.duracion_min} min</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  t.estado === 'completado' ? 'bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400' :
                  t.estado === 'cancelado' ? 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400' :
                  'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400'
                }`}>
                  {t.estado}
                </span>
              </div>
            ))}
            {calendarEvents.length > 0 && (
              <>
                <div className="flex items-center gap-2 py-2">
                  <div className="h-px flex-1 bg-gray-200 dark:bg-gray-800" />
                  <span className="text-[10px] text-gray-400 dark:text-gray-500 font-semibold uppercase tracking-wider">Google Calendar</span>
                  <div className="h-px flex-1 bg-gray-200 dark:bg-gray-800" />
                </div>
                {calendarEvents.slice(0, 5).map((ev: any) => (
                  <div key={ev.id} className="flex items-center gap-4 p-3 rounded-lg bg-blue-50/50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40">
                    <div className="text-sm font-mono text-blue-600 dark:text-blue-400 w-16">
                      {ev.start_datetime ? new Date(ev.start_datetime).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-800 dark:text-white">{ev.summary}</p>
                      {ev.description && <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{ev.description}</p>}
                    </div>
                    {ev.html_link && (
                      <a href={ev.html_link} target="_blank" rel="noopener" className="text-blue-400 hover:text-blue-300">
                        <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <button
          onClick={() => onNavigate('anamnesis')}
          className="bg-gradient-to-br from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 rounded-2xl p-5 text-white text-left hover:shadow-xl dark:hover:shadow-indigo-500/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
        >
          <p className="text-lg font-bold mb-1 flex items-center gap-2">Nueva Anamnesis <Activity size={18} /></p>
          <p className="text-sm text-indigo-100/90 font-medium">Grabar entrevista, transcribir con Whisper y estructurar con IA</p>
        </button>
        <button
          onClick={() => onNavigate('recomendacion')}
          className="bg-gradient-to-br from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 rounded-2xl p-5 text-white text-left hover:shadow-xl dark:hover:shadow-amber-500/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
        >
          <p className="text-lg font-bold mb-1 flex items-center gap-2">Motor IA Terapéutico <Sparkles size={18} /></p>
          <p className="text-sm text-amber-100/90 font-medium">Sintetizar caso clínico y generar prescripción de ejercicios Farías</p>
        </button>
        <button
          onClick={() => onNavigate('cuadernillo')}
          className="bg-gradient-to-br from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 rounded-2xl p-5 text-white text-left hover:shadow-xl dark:hover:shadow-emerald-500/20 transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
        >
          <p className="text-lg font-bold mb-1 flex items-center gap-2">Crear Cuadernillo <FileText size={18} /></p>
          <p className="text-sm text-emerald-100/90 font-medium">Generar PDF de ejercicios terapéuticos personalizados</p>
        </button>
      </div>
    </div>
  );
}
