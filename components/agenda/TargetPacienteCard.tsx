import React from 'react';
import { User, Mic, BarChart3, Activity, FileText, Phone, Mail, ExternalLink, Calendar, Video, Clock } from 'lucide-react';

interface PacienteData {
  id?: string;
  nombre_completo: string;
  dni?: string;
  telefono?: string;
  email?: string;
}

interface TurnoData {
  id: string;
  paciente_id?: string;
  pacientes?: PacienteData;
  fecha_hora: string;
  duracion_min: number;
  tipo: string;
  modalidad?: string;
  motivo?: string;
  notas?: string;
  meet_link?: string;
  google_event_id?: string;
  zoom_meeting_id?: string;
  zoom_password?: string;
  zoom_join_url?: string;
  estado?: string;
}

interface Props {
  turno: TurnoData;
  onNavigate: (modulo: string, pacienteId?: string) => void;
  onSelectPaciente: (pacienteId: string) => void;
  onActualizarEstado?: (turnoId: string, nuevoEstado: string) => void;
  onEliminarTurno?: (turnoId: string) => void;
  onEditarTurno?: (turno: TurnoData) => void;
  onZoom?: (turno: TurnoData) => void;
  onIngresarVideoconferencia?: (turno: TurnoData) => void;
}

export default function TargetPacienteCard({
  turno,
  onNavigate,
  onSelectPaciente,
  onActualizarEstado,
  onEliminarTurno,
  onEditarTurno,
  onZoom,
  onIngresarVideoconferencia,
}: Props) {
  const paciente = turno.pacientes;
  const pId = turno.paciente_id || paciente?.id;
  const esVirtual = turno.modalidad?.toUpperCase() === 'VIRTUAL' || Boolean(turno.meet_link);

  const fechaObj = new Date(turno.fecha_hora);
  const horaStr = fechaObj.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
  const fechaStr = fechaObj.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' });

  const handleAction = (modulo: string) => {
    if (pId) {
      onSelectPaciente(pId);
      onNavigate(modulo, pId);
    }
  };

  return (
    <div className="bg-white/80 dark:bg-white/[0.04] backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-4 shadow-sm hover:shadow-md transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-100 dark:border-white/5 pb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-black text-sm">
            {paciente?.nombre_completo ? paciente.nombre_completo.substring(0, 2).toUpperCase() : 'PA'}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-bold text-sm text-gray-900 dark:text-white">
                {paciente?.nombre_completo || 'Paciente sin registrar'}
              </h4>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                esVirtual
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                  : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-800'
              }`}>
                {esVirtual ? 'Virtual' : 'Presencial'}
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-2 mt-0.5">
              <span>{turno.motivo || turno.tipo || 'Consulta Vocal'}</span>
              {paciente?.dni && <span>• DNI {paciente.dni}</span>}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-right">
          <div className="text-xs">
            <span className="font-bold text-gray-900 dark:text-white block">{horaStr} hs</span>
            <span className="text-[11px] text-gray-500 dark:text-gray-400 capitalize">{fechaStr} ({turno.duracion_min}m)</span>
          </div>
        </div>
      </div>

      {/* Meet Link Button (si es virtual con Google Meet) */}
      {esVirtual && turno.meet_link && (
        <div className="mt-3 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Video size={16} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="text-xs font-semibold text-emerald-800 dark:text-emerald-300 truncate">
              Google Meet Generado
            </span>
          </div>
          <a
            href={turno.meet_link}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold flex items-center gap-1 shadow-sm shrink-0"
          >
            <span>Unirse</span>
            <ExternalLink size={12} />
          </a>
        </div>
      )}

      {/* Zoom Teleconsulta (audio profesional) */}
      <div className="mt-3 flex items-center gap-2">
        {turno.zoom_join_url ? (
          <a
            href={turno.zoom_join_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 px-3 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-sm"
          >
            <Video size={14} /> Unirse por Zoom
          </a>
        ) : (
          onZoom && (
            <button
              onClick={() => onZoom(turno)}
              className="flex-1 px-3 py-2 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center gap-2 transition-all"
              title="Crear sala Zoom con audio profesional (sin filtros)"
            >
              <Video size={14} /> Crear sala Zoom
            </button>
          )
        )}
        {onZoom && turno.zoom_join_url && (
          <button
            onClick={() => onZoom(turno)}
            className="px-3 py-2 rounded-xl border border-blue-500/30 text-blue-700 dark:text-blue-300 text-xs font-bold hover:bg-blue-500/10 transition-all"
            title="Abrir panel de teleconsulta (guía de audio, notas)"
          >
            Panel
          </button>
        )}
      </div>

      {/* Ingresar a videoconferencia integrada */}
      {onIngresarVideoconferencia && (
        <button
          onClick={() => onIngresarVideoconferencia(turno)}
          className="mt-2 w-full px-3 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-bold flex items-center justify-center gap-2 shadow-md shadow-indigo-600/25 transition-all"
        >
          <Video size={14} /> Ingresar a videoconferencia
        </button>
      )}

      {/* Patient info contact */}
      {(paciente?.telefono || paciente?.email) && (
        <div className="mt-2.5 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
          {paciente.telefono && (
            <span className="flex items-center gap-1">
              <Phone size={12} /> {paciente.telefono}
            </span>
          )}
          {paciente.email && (
            <span className="flex items-center gap-1">
              <Mail size={12} /> {paciente.email}
            </span>
          )}
        </div>
      )}

      {turno.notas && (
        <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 italic bg-gray-50 dark:bg-white/[0.02] p-2 rounded-lg">
          "{turno.notas}"
        </p>
      )}

      {/* Clinical Action Buttons: Anamnesis, Escalas, Praat, Cuadernillo */}
      <div className="mt-3 pt-3 border-t border-gray-100 dark:border-white/5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <button
            onClick={() => handleAction('anamnesis')}
            className="px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 hover:bg-indigo-100 text-indigo-700 dark:text-indigo-300 text-xs font-semibold flex items-center gap-1 border border-indigo-200 dark:border-indigo-800/40 transition-colors"
            title="Abrir Anamnesis Inteligente"
          >
            <Mic size={12} /> Anamnesis
          </button>
          <button
            onClick={() => handleAction('escalas')}
            className="px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/40 hover:bg-purple-100 text-purple-700 dark:text-purple-300 text-xs font-semibold flex items-center gap-1 border border-purple-200 dark:border-purple-800/40 transition-colors"
            title="Abrir Escalas y Riesgo Vocal"
          >
            <BarChart3 size={12} /> Escalas
          </button>
          <button
            onClick={() => handleAction('analisis')}
            className="px-2.5 py-1 rounded-lg bg-cyan-50 dark:bg-cyan-950/40 hover:bg-cyan-100 text-cyan-700 dark:text-cyan-300 text-xs font-semibold flex items-center gap-1 border border-cyan-200 dark:border-cyan-800/40 transition-colors"
            title="Abrir Análisis Bioacústico Praat"
          >
            <Activity size={12} /> Praat
          </button>
          <button
            onClick={() => handleAction('cuadernillo')}
            className="px-2.5 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 text-emerald-700 dark:text-emerald-300 text-xs font-semibold flex items-center gap-1 border border-emerald-200 dark:border-emerald-800/40 transition-colors"
            title="Abrir Cuadernillo Terapéutico"
          >
            <FileText size={12} /> Cuadernillo
          </button>
        </div>

        {/* State select & delete */}
        <div className="flex items-center gap-2">
          {onEditarTurno && (
            <button
              onClick={() => onEditarTurno(turno)}
              className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 px-2 py-1 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 rounded-lg transition-colors"
              title="Editar cita (fecha, hora, modalidad) y sincronizar con Google"
            >
              Editar
            </button>
          )}
          {onActualizarEstado && (
            <select
              value={turno.estado || 'programado'}
              onChange={e => onActualizarEstado(turno.id, e.target.value)}
              className="text-[11px] font-semibold bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 text-gray-700 dark:text-gray-300 focus:outline-none"
            >
              <option value="programado">Programado</option>
              <option value="confirmado">Confirmado</option>
              <option value="completado">Completado</option>
              <option value="cancelado">Cancelado</option>
              <option value="no_asistio">No Asistió</option>
            </select>
          )}
          {onEliminarTurno && (
            <button
              onClick={() => onEliminarTurno(turno.id)}
              className="text-xs text-red-500 hover:text-red-700 px-2 py-1 hover:bg-red-50 dark:hover:bg-red-950/30 rounded-lg transition-colors"
              title="Eliminar cita"
            >
              ×
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
