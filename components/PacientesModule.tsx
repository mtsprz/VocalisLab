import React, { useState, useEffect } from 'react';
import { UserPlus, Search, Edit2, Trash2, Phone, Mail, Save, X, UserCheck } from 'lucide-react';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Paciente {
  id: string;
  nombre_completo: string;
  dni: string;
  fecha_nacimiento: string;
  sexo: string;
  telefono: string;
  email: string;
  ocupacion: string;
  derivador: string;
  notas_iniciales: string;
  activo: boolean;
}

interface Props {
  onSelectPaciente: (id: string) => void;
}

const EMPTY_FORM = {
  nombre_completo: '', dni: '', fecha_nacimiento: '', sexo: 'Femenino',
  telefono: '', email: '', ocupacion: '', derivador: '', notas_iniciales: '',
};

function FormField({ label, value, onChange, type = 'text', required = false }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; required?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1">{label}{required && ' *'}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
      />
    </div>
  );
}

export default function PacientesModule({ onSelectPaciente }: Props) {
  const clinical = useClinical();
  const [pacientes, setPacientes] = useState<Paciente[]>([]);
  const [buscar, setBuscar] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadPacientes(); }, [buscar]);

  const loadPacientes = async () => {
    setLoading(true);
    try {
      const q = buscar ? `?buscar=${encodeURIComponent(buscar)}` : '';
      const r = await fetch(`${BACKEND_URL}/api/pacientes${q}`);
      if (r.ok) setPacientes(await r.json());
    } catch {}
    setLoading(false);
  };

  const handleSave = async () => {
    if (!form.nombre_completo || !form.dni) return alert('Nombre y DNI son obligatorios');
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    try {
      const url = editId ? `${BACKEND_URL}/api/pacientes/${editId}` : `${BACKEND_URL}/api/pacientes`;
      const method = editId ? 'PUT' : 'POST';
      await fetch(url, { method, body: fd });
      setShowForm(false);
      setEditId(null);
      setForm(EMPTY_FORM);
      loadPacientes();
    } catch (e) {
      alert('Error guardando paciente');
    }
  };

  const handleEdit = (p: Paciente) => {
    setForm({
      nombre_completo: p.nombre_completo,
      dni: p.dni,
      fecha_nacimiento: p.fecha_nacimiento || '',
      sexo: p.sexo || 'Femenino',
      telefono: p.telefono || '',
      email: p.email || '',
      ocupacion: p.ocupacion || '',
      derivador: p.derivador || '',
      notas_iniciales: p.notas_iniciales || '',
    });
    setEditId(p.id);
    setShowForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar este paciente?')) return;
    await fetch(`${BACKEND_URL}/api/pacientes/${id}`, { method: 'DELETE' });
    loadPacientes();
  };

  const set = (field: string) => (v: string) => setForm(prev => ({ ...prev, [field]: v }));

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      {/* Header Search & Actions */}
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
          <input
            value={buscar}
            onChange={e => setBuscar(e.target.value)}
            placeholder="Buscar paciente por nombre o DNI..."
            className="w-full pl-9 pr-4 py-2.5 border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#111827] text-slate-900 dark:text-slate-100 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none shadow-sm"
          />
        </div>
        <button
          onClick={() => { setForm(EMPTY_FORM); setEditId(null); setShowForm(true); }}
          className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-bold shadow-md shadow-indigo-600/20 active:scale-95 transition-all"
        >
          <UserPlus size={16} /> Nuevo Paciente
        </button>
      </div>

      {/* Form Drawer */}
      {showForm && (
        <div className="bg-white dark:bg-[#111827] rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-lg transition-all">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3 mb-4">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <UserCheck size={18} className="text-indigo-500" />
              {editId ? 'Editar Paciente' : 'Registrar Nuevo Paciente'}
            </h3>
            <button
              onClick={() => { setShowForm(false); setEditId(null); }}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X size={18} />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label="Nombre completo" value={form.nombre_completo} onChange={set('nombre_completo')} required />
            <FormField label="DNI / Cédula" value={form.dni} onChange={set('dni')} required />
            <FormField label="Fecha de nacimiento" value={form.fecha_nacimiento} onChange={set('fecha_nacimiento')} type="date" />
            <div>
              <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1">
                Sexo Biológico
              </label>
              <select
                value={form.sexo}
                onChange={e => setForm({ ...form, sexo: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              >
                <option className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100" value="Femenino">Femenino</option>
                <option className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100" value="Masculino">Masculino</option>
                <option className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100" value="Otro">Otro</option>
              </select>
            </div>
            <FormField label="Teléfono / WhatsApp" value={form.telefono} onChange={set('telefono')} />
            <FormField label="Correo electrónico" value={form.email} onChange={set('email')} type="email" />
            <FormField label="Ocupación / Uso vocal" value={form.ocupacion} onChange={set('ocupacion')} />
            <FormField label="Profesional derivador" value={form.derivador} onChange={set('derivador')} />
          </div>

          <div className="mt-4">
            <label className="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1">
              Notas clínicas iniciales
            </label>
            <textarea
              value={form.notas_iniciales}
              onChange={e => setForm({ ...form, notas_iniciales: e.target.value })}
              rows={2}
              placeholder="Antecedentes relevantes, diagnóstico previo..."
              className="w-full px-3 py-2 border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
            />
          </div>

          <div className="mt-5 flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={() => { setShowForm(false); setEditId(null); }}
              className="px-4 py-2 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 rounded-xl text-xs font-bold hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="flex items-center gap-2 px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold shadow-md shadow-indigo-600/20 active:scale-95 transition-all"
            >
              <Save size={15} /> {editId ? 'Actualizar Paciente' : 'Guardar Paciente'}
            </button>
          </div>
        </div>
      )}

      {/* Table List */}
      <div className="bg-white dark:bg-[#111827] rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-3.5 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Nombre Completo</th>
                <th className="px-4 py-3.5 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">DNI</th>
                <th className="px-4 py-3.5 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Sexo</th>
                <th className="px-4 py-3.5 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Teléfono</th>
                <th className="px-4 py-3.5 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Ocupación</th>
                <th className="px-4 py-3.5 text-right text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
              {loading ? (
                <tr><td colSpan={6} className="text-center py-10 text-slate-400 font-medium">Cargando nómina de pacientes...</td></tr>
              ) : pacientes.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-slate-400 font-medium">No se encontraron pacientes registrados</td></tr>
              ) : pacientes.map(p => (
                <tr key={p.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3.5">
                    <button
                      onClick={() => {
                        clinical.setPaciente({
                          id: p.id,
                          nombre_completo: p.nombre_completo,
                          dni: p.dni,
                          fecha_nacimiento: p.fecha_nacimiento,
                          sexo: p.sexo,
                          ocupacion: p.ocupacion,
                          demanda_vocal_horas: 4,
                        });
                        clinical.markStep('pacientes');
                        onSelectPaciente(p.id);
                      }}
                      className="font-bold text-indigo-600 dark:text-indigo-400 hover:underline text-left text-xs block"
                    >
                      {p.nombre_completo}
                    </button>
                  </td>
                  <td className="px-4 py-3.5 font-medium text-slate-700 dark:text-slate-300">{p.dni}</td>
                  <td className="px-4 py-3.5 font-medium text-slate-700 dark:text-slate-300">{p.sexo}</td>
                  <td className="px-4 py-3.5 font-medium text-slate-700 dark:text-slate-300">{p.telefono || '—'}</td>
                  <td className="px-4 py-3.5 font-medium text-slate-700 dark:text-slate-300">{p.ocupacion || '—'}</td>
                  <td className="px-4 py-3.5 text-right space-x-1">
                    <button
                      onClick={() => handleEdit(p)}
                      className="p-1.5 text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                      title="Editar datos"
                    >
                      <Edit2 size={15} />
                    </button>
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="p-1.5 text-slate-400 hover:text-red-600 dark:hover:text-red-400 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                      title="Eliminar registro"
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
