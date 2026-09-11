import React, { useState, useEffect, useMemo } from 'react';
import {
  Calendar as CalendarIcon, Clock, Plus, Video, Building2, ChevronLeft, ChevronRight,
  RefreshCw, Users, CheckCircle2, AlertCircle, ExternalLink, Filter, CalendarDays, ListFilter
} from 'lucide-react';
import FiltroModalidad, { ModalidadFiltro } from './FiltroModalidad';
import TargetPacienteCard from './TargetPacienteCard';
import NuevoTurnoModal from './NuevoTurnoModal';
import ZoomTeleconsulta from '../ZoomTeleconsulta';
import { useAuth } from '../AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

type VistaFormato = 'mes' | 'semana' | 'dia' | 'lista';

interface Props {
  onNavigate: (modulo: string, pacienteId?: string) => void;
  onSelectPaciente: (pacienteId: string) => void;
}

export default function AgendaView({ onNavigate, onSelectPaciente }: Props) {
  const { user } = useAuth();
  const [turnos, setTurnos] = useState<any[]>([]);
  const [googleEvents, setGoogleEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalNuevoAbierto, setModalNuevoAbierto] = useState(false);
  const [turnoEditar, setTurnoEditar] = useState<any | null>(null);
  const [turnoZoom, setTurnoZoom] = useState<any | null>(null);
  const [formato, setFormato] = useState<VistaFormato>('semana');
  const [filtroModalidad, setFiltroModalidad] = useState<ModalidadFiltro>('TODAS');
  const [fechaActual, setFechaActual] = useState(new Date());

  useEffect(() => {
    cargarAgenda();
  }, [fechaActual]);

  const cargarAgenda = async () => {
    setLoading(true);
    // Cargar turnos de VocalisLab
    try {
      const r = await fetch(`${BACKEND_URL}/api/turnos?limit=300`);
      if (r.ok) {
        const data = await r.json();
        setTurnos(Array.isArray(data) ? data : []);
      }
    } catch {
      setTurnos([]);
    }

    // Cargar Google Calendar si el usuario está autenticado
    if (user?.id) {
      try {
        const r2 = await fetch(`${BACKEND_URL}/api/calendar/events?user_id=${user.id}&max_results=100`);
        if (r2.ok) {
          const gData = await r2.json();
          setGoogleEvents(gData.events || []);
        }
      } catch {}
    }
    setLoading(false);
  };

  const handleActualizarEstado = async (turnoId: string, nuevoEstado: string) => {
    try {
      const fd = new FormData();
      fd.append('estado', nuevoEstado);
      await fetch(`${BACKEND_URL}/api/turnos/${turnoId}`, { method: 'PUT', body: fd });
      cargarAgenda();
    } catch {}
  };

  const handleEliminarTurno = async (turnoId: string) => {
    if (!window.confirm('¿Seguro que deseas eliminar esta cita?')) return;
    try {
      await fetch(`${BACKEND_URL}/api/turnos/${turnoId}`, { method: 'DELETE' });
      cargarAgenda();
    } catch {}
  };

  // Filtrado según modalidad (Presencial / Virtual)
  const turnosFiltrados = useMemo(() => {
    let list = [...turnos];
    if (filtroModalidad === 'PRESENCIAL') {
      list = list.filter(t => (t.modalidad || '').toUpperCase() !== 'VIRTUAL' && !t.meet_link);
    } else if (filtroModalidad === 'VIRTUAL') {
      list = list.filter(t => (t.modalidad || '').toUpperCase() === 'VIRTUAL' || Boolean(t.meet_link));
    }
    return list.sort((a, b) => new Date(a.fecha_hora).getTime() - new Date(b.fecha_hora).getTime());
  }, [turnos, filtroModalidad]);

  // Conteo para los badges del filtro
  const conteoModalidad = useMemo(() => {
    const virtuales = turnos.filter(t => (t.modalidad || '').toUpperCase() === 'VIRTUAL' || Boolean(t.meet_link)).length;
    return {
      todas: turnos.length,
      presenciales: turnos.length - virtuales,
      virtuales,
    };
  }, [turnos]);

  // Citas agrupadas por día
  const turnosPorDia = useMemo(() => {
    const map = new Map<string, any[]>();
    turnosFiltrados.forEach(t => {
      const diaKey = new Date(t.fecha_hora).toISOString().split('T')[0];
      if (!map.has(diaKey)) map.set(diaKey, []);
      map.get(diaKey)!.push(t);
    });
    return map;
  }, [turnosFiltrados]);

  // Navegación temporal
  const navegarFecha = (direccion: number) => {
    const d = new Date(fechaActual);
    if (formato === 'mes') {
      d.setMonth(d.getMonth() + direccion);
    } else if (formato === 'semana') {
      d.setDate(d.getDate() + direccion * 7);
    } else {
      d.setDate(d.getDate() + direccion);
    }
    setFechaActual(d);
  };

  const irAHoy = () => setFechaActual(new Date());

  const tituloRangoFecha = useMemo(() => {
    const opciones: Intl.DateTimeFormatOptions = { month: 'long', year: 'numeric' };
    if (formato === 'mes') {
      return fechaActual.toLocaleDateString('es-AR', opciones);
    } else if (formato === 'dia') {
      return fechaActual.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    } else {
      // Semana
      const inicioSemana = new Date(fechaActual);
      inicioSemana.setDate(fechaActual.getDate() - fechaActual.getDay() + 1);
      const finSemana = new Date(inicioSemana);
      finSemana.setDate(inicioSemana.getDate() + 6);
      return `${inicioSemana.getDate()} de ${inicioSemana.toLocaleDateString('es-AR', { month: 'short' })} - ${finSemana.getDate()} de ${finSemana.toLocaleDateString('es-AR', { month: 'short', year: 'numeric' })}`;
    }
  }, [fechaActual, formato]);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Top Banner Agenda */}
      <div className="bg-gradient-to-r from-indigo-900/60 via-purple-900/40 to-slate-900/80 backdrop-blur-xl border border-indigo-500/20 rounded-3xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold tracking-widest uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2.5 py-1 rounded-full">
              Gestión de Citas Clínicas & Google Calendar
            </span>
            {user && (
              <span className="text-[10px] font-semibold text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                <CheckCircle2 size={10} /> Google Calendar Conectado
              </span>
            )}
          </div>
          <h2 className="text-2xl font-black text-white mt-2 flex items-center gap-2">
            <CalendarIcon className="text-indigo-400" /> Agenda de Pacientes & Teleconsulta
          </h2>
          <p className="text-xs text-gray-300 max-w-2xl mt-1">
            Gestione consultas presenciales y videoconsultas por Google Meet con sincronización bidireccional y acceso directo al historial clínico.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => cargarAgenda()}
            className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 transition-all"
            title="Recargar citas"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setModalNuevoAbierto(true)}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all active:scale-95"
          >
            <Plus size={16} /> Nueva Cita
          </button>
        </div>
      </div>

      {/* Control Bar: Selector Formato + Navegación + Filtro Modalidad */}
      <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Navegación Fecha */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => navegarFecha(-1)}
            className="p-2 rounded-xl bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-700 dark:text-gray-300 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={irAHoy}
            className="px-3 py-1.5 rounded-xl bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-xs font-bold text-gray-700 dark:text-gray-300 transition-colors"
          >
            Hoy
          </button>
          <button
            onClick={() => navegarFecha(1)}
            className="p-2 rounded-xl bg-gray-100 dark:bg-white/5 hover:bg-gray-200 dark:hover:bg-white/10 text-gray-700 dark:text-gray-300 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
          <span className="text-sm font-bold text-gray-900 dark:text-white capitalize ml-2">
            {tituloRangoFecha}
          </span>
        </div>

        {/* Filtro Presencial / Virtual & Selector de Formato */}
        <div className="flex flex-wrap items-center gap-3">
          <FiltroModalidad
            valor={filtroModalidad}
            onChange={setFiltroModalidad}
            conteo={conteoModalidad}
          />

          {/* Formato de Vista */}
          <div className="inline-flex p-1 rounded-xl bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-xs font-medium">
            {(['semana', 'mes', 'dia', 'lista'] as VistaFormato[]).map(v => (
              <button
                key={v}
                onClick={() => setFormato(v)}
                className={`px-3 py-1.5 rounded-lg capitalize transition-all ${
                  formato === v
                    ? 'bg-white dark:bg-indigo-600 text-gray-900 dark:text-white shadow-sm font-bold'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Agenda Grid / List */}
      {turnosFiltrados.length === 0 && googleEvents.length === 0 ? (
        <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-12 text-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 text-indigo-500 mx-auto flex items-center justify-center mb-3">
            <CalendarIcon size={32} />
          </div>
          <h3 className="font-bold text-gray-900 dark:text-white text-base">
            No hay citas programadas con estos filtros
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 max-w-sm mx-auto mt-1 mb-4">
            Podés agendar una nueva consulta vocal presencial o virtual con generación automática de Google Meet.
          </p>
          <button
            onClick={() => setModalNuevoAbierto(true)}
            className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs inline-flex items-center gap-2 shadow-lg shadow-indigo-600/30"
          >
            <Plus size={16} /> Agendar Cita
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Turnos Clínicos de VocalisLab */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {turnosFiltrados.map(turno => (
              <TargetPacienteCard
                key={turno.id}
                turno={turno}
                onNavigate={onNavigate}
                onSelectPaciente={onSelectPaciente}
                onActualizarEstado={handleActualizarEstado}
                onEliminarTurno={handleEliminarTurno}
                onEditarTurno={(t) => { setTurnoEditar(t); setModalNuevoAbierto(true); }}
                onZoom={(t) => setTurnoZoom(t)}
              />
            ))}
          </div>

          {/* Google Calendar Direct Synchronized Events */}
          {googleEvents.length > 0 && (
            <div className="mt-8 pt-6 border-t border-gray-200 dark:border-white/10">
              <h3 className="text-xs font-bold uppercase tracking-widest text-gray-500 dark:text-gray-400 flex items-center gap-2 mb-3">
                <CalendarDays size={14} className="text-indigo-500" />
                Eventos Externos Importados de Google Calendar ({googleEvents.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {googleEvents.slice(0, 9).map(ev => {
                  const evDate = new Date(ev.start_datetime);
                  return (
                    <div
                      key={ev.id}
                      className="bg-blue-50/40 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl p-3 text-xs"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-bold text-gray-900 dark:text-white truncate">
                          {ev.summary || 'Sin título'}
                        </div>
                        {ev.meet_link && (
                          <a
                            href={ev.meet_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1 rounded bg-emerald-600 text-white hover:bg-emerald-500 flex items-center gap-1 text-[10px] font-bold"
                            title="Unirse con Google Meet"
                          >
                            <Video size={10} /> Meet
                          </a>
                        )}
                      </div>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1 flex items-center gap-1">
                        <Clock size={11} />
                        {evDate.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' })} — {evDate.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })} hs
                      </p>
                      {ev.description && (
                        <p className="text-[10px] text-gray-400 mt-1 truncate">{ev.description}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal Nuevo / Editar Turno */}
      <NuevoTurnoModal
        isOpen={modalNuevoAbierto}
        onClose={() => { setModalNuevoAbierto(false); setTurnoEditar(null); }}
        onTurnoCreado={() => { cargarAgenda(); setTurnoEditar(null); }}
        turnoEditar={turnoEditar}
      />

      {/* Modal Teleconsulta Zoom */}
      {turnoZoom && (
        <ZoomTeleconsulta
          turno={turnoZoom}
          pacienteNombre={turnoZoom.pacientes?.nombre_completo || 'Paciente'}
          onClose={() => setTurnoZoom(null)}
          onSalaActualizada={() => cargarAgenda()}
        />
      )}
    </div>
  );
}
