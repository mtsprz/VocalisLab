import React, { useState, useEffect } from 'react';
import { UserPlus, Search, Edit2, Trash2, Phone, Mail, Save, X } from 'lucide-react';

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

export default function PacientesModule({ onSelectPaciente }: Props) {
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
      sexo: p.sexo || '',
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

  const FormField = ({ label, field, type = 'text', required = false }: any) => (
    <div>
      <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">{label}{required && ' *'}</label>
      <input
        type={type}
        value={(form as any)[field]}
        onChange={e => setForm({ ...form, [field]: e.target.value })}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
      />
    </div>
  );

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
          <input
            value={buscar}
            onChange={e => setBuscar(e.target.value)}
            placeholder="Buscar por nombre o DNI..."
            className="w-full pl-9 pr-4 py-2.5 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#111827] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>
        <button
          onClick={() => { setForm(EMPTY_FORM); setEditId(null); setShowForm(true); }}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 shadow-md shadow-indigo-600/10 active:scale-95 transition-all"
        >
          <UserPlus size={16} /> Nuevo Paciente
        </button>
      </div>

      {showForm && (
        <div className="bg-white dark:bg-[#111827] rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm transition-all duration-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800 dark:text-white">{editId ? 'Editar Paciente' : 'Nuevo Paciente'}</h3>
            <button onClick={() => { setShowForm(false); setEditId(null); }} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-white">
              <X size={18} />
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <FormField label="Nombre completo" field="nombre_completo" required />
            <FormField label="DNI" field="dni" required />
            <FormField label="Fecha de nacimiento" field="fecha_nacimiento" type="date" />
            <div>
              <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">Sexo</label>
              <select
                value={form.sexo}
                onChange={e => setForm({ ...form, sexo: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option>Femenino</option>
                <option>Masculino</option>
                <option>Otro</option>
              </select>
            </div>
            <FormField label="Teléfono" field="telefono" />
            <FormField label="Email" field="email" type="email" />
            <FormField label="Ocupación" field="ocupacion" />
            <FormField label="Derivador" field="derivador" />
          </div>
          <div className="mt-3">
            <label className="block text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">Notas iniciales</label>
            <textarea
              value={form.notas_iniciales}
              onChange={e => setForm({ ...form, notas_iniciales: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div className="mt-4 flex gap-2">
            <button onClick={handleSave} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 shadow-md shadow-indigo-600/10 active:scale-95 transition-all">
              <Save size={16} /> {editId ? 'Actualizar' : 'Crear Paciente'}
            </button>
            <button onClick={() => { setShowForm(false); setEditId(null); }} className="px-4 py-2 border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 rounded-lg text-sm font-semibold hover:bg-gray-50 dark:hover:bg-gray-800">
              Cancelar
            </button>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-[#111827] rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-800">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Nombre</th>
                <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">DNI</th>
                <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Sexo</th>
                <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Teléfono</th>
                <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Ocupación</th>
                <th className="px-4 py-3 text-right text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="text-center py-8 text-gray-400 dark:text-gray-500 text-sm">Cargando...</td></tr>
              ) : pacientes.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-8 text-gray-400 dark:text-gray-500 text-sm">No se encontraron pacientes</td></tr>
              ) : pacientes.map(p => (
                <tr key={p.id} className="border-b border-gray-100 dark:border-gray-800 last:border-b-0 hover:bg-gray-50/50 dark:hover:bg-gray-800/40">
                  <td className="px-4 py-3">
                    <button onClick={() => onSelectPaciente(p.id)} className="text-sm font-bold text-indigo-600 dark:text-indigo-400 hover:underline text-left">
                      {p.nombre_completo}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300 font-medium">{p.dni}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300 font-medium">{p.sexo}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300 font-medium">{p.telefono || '—'}</td>
                  <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300 font-medium">{p.ocupacion || '—'}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => handleEdit(p)} className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-indigo-600 dark:hover:text-indigo-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
                      <Edit2 size={15} />
                    </button>
                    <button onClick={() => handleDelete(p.id)} className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800">
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
