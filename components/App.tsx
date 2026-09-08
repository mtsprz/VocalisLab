import React, { useState } from 'react';
import {
  LayoutDashboard, Users, FileText, Mic, BarChart3, Music,
  Stethoscope, Activity, ChevronRight, Menu, X
} from 'lucide-react';
import DashboardModule from './DashboardModule';
import PacientesModule from './PacientesModule';
import AnamnesisModule from './AnamnesisModule';
import EscalasModule from './EscalasModule';
import AnalisisModule from './AnalisisModule';
import CuadernilloModule from './CuadernilloModule';
import PitchMeterModule from './PitchMeterModule';

type ActiveModule = 'dashboard' | 'pacientes' | 'anamnesis' | 'escalas' | 'analisis' | 'cuadernillo' | 'pitch';

const NAV_ITEMS: { id: ActiveModule; label: string; icon: React.ReactNode }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
  { id: 'pacientes', label: 'Pacientes', icon: <Users size={20} /> },
  { id: 'anamnesis', label: 'Anamnesis', icon: <Mic size={20} /> },
  { id: 'escalas', label: 'Escalas Clínicas', icon: <BarChart3 size={20} /> },
  { id: 'analisis', label: 'Análisis Praat', icon: <Activity size={20} /> },
  { id: 'pitch', label: 'Pitch Meter', icon: <Music size={20} /> },
  { id: 'cuadernillo', label: 'Cuadernillo', icon: <FileText size={20} /> },
];

export default function App() {
  const [activeModule, setActiveModule] = useState<ActiveModule>('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedPacienteId, setSelectedPacienteId] = useState<string | null>(null);

  const renderModule = () => {
    switch (activeModule) {
      case 'dashboard':
        return <DashboardModule onNavigate={setActiveModule} onSelectPaciente={setSelectedPacienteId} />;
      case 'pacientes':
        return <PacientesModule onSelectPaciente={(id) => { setSelectedPacienteId(id); setActiveModule('anamnesis'); }} />;
      case 'anamnesis':
        return <AnamnesisModule pacienteId={selectedPacienteId} />;
      case 'escalas':
        return <EscalasModule pacienteId={selectedPacienteId} />;
      case 'analisis':
        return <AnalisisModule pacienteId={selectedPacienteId} />;
      case 'pitch':
        return <PitchMeterModule />;
      case 'cuadernillo':
        return <CuadernilloModule pacienteId={selectedPacienteId} />;
      default:
        return <DashboardModule onNavigate={setActiveModule} onSelectPaciente={setSelectedPacienteId} />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {sidebarOpen && (
        <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shadow-sm flex-shrink-0">
          <div className="p-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
                <Stethoscope size={18} className="text-white" />
              </div>
              <div>
                <h1 className="text-sm font-bold text-gray-900">VocalisLab</h1>
                <p className="text-[10px] text-gray-500">Pro — Fonoaudiología</p>
              </div>
            </div>
          </div>
          <nav className="flex-1 p-2 space-y-1">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveModule(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  activeModule === item.id
                    ? 'bg-indigo-50 text-indigo-700 shadow-sm'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span className={activeModule === item.id ? 'text-indigo-600' : 'text-gray-400'}>
                  {item.icon}
                </span>
                {item.label}
                {activeModule === item.id && <ChevronRight size={16} className="ml-auto text-indigo-400" />}
              </button>
            ))}
          </nav>
          <div className="p-3 border-t border-gray-100">
            <p className="text-[10px] text-gray-400 text-center">v2.0 — Plataforma Clínica</p>
          </div>
        </aside>
      )}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-4 flex-shrink-0">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
          <h2 className="text-lg font-semibold text-gray-800">
            {NAV_ITEMS.find(n => n.id === activeModule)?.label}
          </h2>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          {renderModule()}
        </div>
      </main>
    </div>
  );
}
