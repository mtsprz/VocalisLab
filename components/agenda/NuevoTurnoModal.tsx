import React, { useState, useEffect } from 'react';
import { X, Calendar, Clock, User, Video, Building2, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Paciente {
  id: string;
  nombre_completo: string;
  dni: string;
  email?: string;
  telefono?: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onTurnoCreado: () => void;
  pacientePreseleccionadoId?: string | null;
}

export default function NuevoTurnoModal({
  isOpen,
  onClose,
  onTurnoCreado,
  pacientePreseleccionadoId,
}: Props) {
  const { user } = useAuth();
  const [pacientes, setPacientes] = useState<Paciente[]>([]);
  const [pacienteId, setPacienteId] = useState(pacientePreseleccionadoId || '');
  const [fecha, setFecha] = useState(new Date().toISOString().split('T')[0]);
  const [horaInicio, setHoraInicio] = useState('10:00');
  const [duracionMin, setDuracionMin] = useState(45);
  const [modalidad, setModalidad] = useState<'PRESENCIAL' | 'VIRTUAL'>('PRESENCIAL');
  const [motivo, setMotivo] = useState('Evaluación y Diagnóstico Bioacústico');
  const [tipo, setTipo] = useState('control');
  const [notas, setNotas] = useState('');
  const [syncGoogle, setSyncGoogle] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (isOpen) {
      cargarPacientes();
      if (pacientePreseleccionadoId) setPacienteId(pacientePreseleccionadoId);
    }
  }, [isOpen, pacientePreseleccionadoId]);

  const cargarPacientes = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/pacientes?limit=200`);
      if (r.ok) {
        const data = await r.json();
        setPacientes(data || []);
      }
    } catch {}
  };

  if (!isOpen) return null;

  const pacienteSeleccionado = pacientes.find(p => p.id === pacienteId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pacienteId) {
      setErrorMsg('Seleccioná un paciente para agendar el turno.');
      return;
    }
    setGuardando(true);
    setErrorMsg('');

    try {
      const fechaHoraIso = `${fecha}T${horaInicio}:00`;

      const fd = new FormData();
      fd.append('paciente_id', pacienteId);
      fd.append('fecha_hora', fechaHoraIso);
      fd.append('duracion_min', String(duracionMin));
      fd.append('tipo', tipo);
      fd.append('modalidad', modalidad);
      fd.append('motivo', motivo);
      fd.append('notas', notas);
      if (user?.id) fd.append('user_id', user.id);
      fd.append('sincronizar_google', String(syncGoogle && Boolean(user?.id)));

      const resp = await fetch(`${BACKEND_URL}/api/turnos`, {
        method: 'POST',
        body: fd,
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Error creando turno en el servidor');
      }

      onTurnoCreado();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error al agendar cita.');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white dark:bg-[#111827] rounded-3xl border border-gray-200 dark:border-white/10 w-full max-w-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 dark:border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold">
              <Calendar size={18} />
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900 dark:text-white">
                Agendar Nueva Cita Vocal
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Programá consultas presenciales o virtuales con Google Meet
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-gray-400 hover:text-gray-600 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5 transition-all"
          >
            <X size={18} />
          </button>
        </div>

        {errorMsg && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-600 dark:text-red-400 flex items-center gap-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs">
          {/* Paciente Selector */}
          <div>
            <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">
              Paciente <span className="text-red-500">*</span>
            </label>
            <select
              value={pacienteId}
              onChange={e => setPacienteId(e.target.value)}
              required
              className="w-full px-3 py-2.5 bg-white dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 text-gray-800 dark:text-gray-100 rounded-xl text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="">-- Seleccionar Paciente --</option>
              {pacientes.map(p => (
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" key={p.id} value={p.id}>
                  {p.nombre_completo} {p.dni ? `(DNI: ${p.dni})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Modalidad Switch */}
          <div>
            <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">
              Modalidad de Atención
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setModalidad('PRESENCIAL')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-xl border font-bold transition-all ${
                  modalidad === 'PRESENCIAL'
                    ? 'bg-indigo-500/15 border-indigo-500 text-indigo-700 dark:text-white ring-1 ring-indigo-500'
                    : 'bg-gray-50 dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-500'
                }`}
              >
                <Building2 size={16} />
                <span>Presencial</span>
              </button>
              <button
                type="button"
                onClick={() => setModalidad('VIRTUAL')}
                className={`flex items-center justify-center gap-2 p-2.5 rounded-xl border font-bold transition-all ${
                  modalidad === 'VIRTUAL'
                    ? 'bg-emerald-500/15 border-emerald-500 text-emerald-700 dark:text-white ring-1 ring-emerald-500'
                    : 'bg-gray-50 dark:bg-white/5 border-gray-200 dark:border-white/10 text-gray-500'
                }`}
              >
                <Video size={16} />
                <span>Virtual (Google Meet)</span>
              </button>
            </div>
          </div>

          {/* Fecha y Horario */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">Fecha</label>
              <input
                type="date"
                value={fecha}
                onChange={e => setFecha(e.target.value)}
                required
                className="w-full px-2.5 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">Hora Inicio</label>
              <input
                type="time"
                value={horaInicio}
                onChange={e => setHoraInicio(e.target.value)}
                required
                className="w-full px-2.5 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">Duración</label>
              <select
                value={duracionMin}
                onChange={e => setDuracionMin(Number(e.target.value))}
                className="w-full px-2.5 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
              >
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>60 min</option>
                <option value={90}>90 min</option>
              </select>
            </div>
          </div>

          {/* Motivo & Tipo */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">Motivo</label>
              <select
                value={motivo}
                onChange={e => setMotivo(e.target.value)}
                className="w-full px-2.5 py-2 bg-white dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 text-gray-800 dark:text-gray-100 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              >
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="Evaluación y Diagnóstico Bioacústico">Evaluación Bioacústica</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="Sesión de Terapia Vocal / SOVTE">Terapia Vocal / SOVTE</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="Control Evolutivo / Praat">Control Evolutivo</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="Entrenamiento Profesional de la Voz">Entrenamiento de Voz</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="Entrega de Cuadernillo Terapéutico">Entrega Cuadernillo</option>
              </select>
            </div>
            <div>
              <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">Tipo de Consulta</label>
              <select
                value={tipo}
                onChange={e => setTipo(e.target.value)}
                className="w-full px-2.5 py-2 bg-white dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 text-gray-800 dark:text-gray-100 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              >
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="primera_vez">Primera Vez</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="control">Control</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="terapia">Terapia</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="evaluacion">Evaluación</option>
                <option className="bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100" value="seguimiento">Seguimiento</option>
              </select>
            </div>
          </div>

          {/* Notas */}
          <div>
            <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">Notas Clínicas</label>
            <input
              type="text"
              value={notas}
              onChange={e => setNotas(e.target.value)}
              placeholder="Objetivos de la sesión, pauta de audio requerida, etc."
              className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white"
            />
          </div>

          {/* Sincronización Google Calendar Check */}
          {user && (
            <label className="flex items-center gap-2 p-2.5 rounded-xl bg-indigo-50 dark:bg-white/[0.03] border border-indigo-100 dark:border-white/10 cursor-pointer">
              <input
                type="checkbox"
                checked={syncGoogle}
                onChange={e => setSyncGoogle(e.target.checked)}
                className="rounded text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-[11px] text-gray-700 dark:text-gray-300">
                Sincronizar en <strong>Google Calendar</strong>
                {modalidad === 'VIRTUAL' ? ' y generar enlace de Google Meet automático' : ''}.
              </span>
            </label>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/5 font-semibold"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={guardando}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
            >
              {guardando ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {guardando ? 'Agendando...' : 'Confirmar Cita'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
