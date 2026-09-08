import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard, Users, FileText, Mic, BarChart3, Music,
  Stethoscope, Activity, ChevronRight, Menu, X, Sun, Moon, Sparkles
} from 'lucide-react';
import DashboardModule from './DashboardModule';
import PacientesModule from './PacientesModule';
import AnamnesisModule from './AnamnesisModule';
import EscalasModule from './EscalasModule';
import AnalisisModule from './AnalisisModule';
import CuadernilloModule from './CuadernilloModule';
import PitchMeterModule from './PitchMeterModule';
import RecomendacionIAModule from './RecomendacionIAModule';

type ActiveModule = 'dashboard' | 'pacientes' | 'anamnesis' | 'escalas' | 'analisis' | 'recomendacion' | 'pitch' | 'cuadernillo';

const NAV_ITEMS: { id: ActiveModule; label: string; icon: React.ReactNode }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} /> },
  { id: 'pacientes', label: 'Pacientes', icon: <Users size={20} /> },
  { id: 'anamnesis', label: 'Anamnesis', icon: <Mic size={20} /> },
  { id: 'escalas', label: 'Escalas & Riesgo FonoAr', icon: <BarChart3 size={20} /> },
  { id: 'analisis', label: 'Análisis Praat', icon: <Activity size={20} /> },
  { id: 'recomendacion', label: 'Motor IA Terapéutico', icon: <Sparkles size={20} /> },
  { id: 'pitch', label: 'Pitch Meter', icon: <Music size={20} /> },
  { id: 'cuadernillo', label: 'Cuadernillo', icon: <FileText size={20} /> },
];

export default function App() {
  const [activeModule, setActiveModule] = useState<ActiveModule>('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedPacienteId, setSelectedPacienteId] = useState<string | null>(null);
  const [initialExerciseIds, setInitialExerciseIds] = useState<string[]>([]);
  
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return 'dark'; // Default premium clinical dark style
  });

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

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
      case 'recomendacion':
        return (
          <RecomendacionIAModule
            pacienteId={selectedPacienteId}
            onTransferToCuadernillo={(exIds) => {
              setInitialExerciseIds(exIds);
              setActiveModule('cuadernillo');
            }}
          />
        );
      case 'pitch':
        return <PitchMeterModule />;
      case 'cuadernillo':
        return <CuadernilloModule pacienteId={selectedPacienteId} initialExerciseIds={initialExerciseIds} />;
      default:
        return <DashboardModule onNavigate={setActiveModule} onSelectPaciente={setSelectedPacienteId} />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#0b0f19] text-slate-800 dark:text-slate-100 overflow-hidden transition-colors duration-200">
      {sidebarOpen && (
        <aside className="w-64 bg-white dark:bg-[#111827] border-r border-gray-200 dark:border-gray-800 flex flex-col shadow-sm flex-shrink-0 z-20 transition-colors duration-200">
          <div className="p-4 border-b border-gray-100 dark:border-gray-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-600 dark:bg-indigo-500 rounded-lg flex items-center justify-center shadow-md shadow-indigo-500/20">
                <Stethoscope size={18} className="text-white" />
              </div>
              <div>
                <h1 className="text-sm font-bold text-gray-900 dark:text-white">VocalisLab</h1>
                <p className="text-[10px] text-gray-500 dark:text-gray-400 font-semibold tracking-wider uppercase">Pro — Fonoaudiología</p>
              </div>
            </div>
          </div>
          <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveModule(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  activeModule === item.id
                    ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <span className={activeModule === item.id ? 'text-indigo-600 dark:text-indigo-400' : 'text-gray-400 dark:text-gray-500'}>
                  {item.icon}
                </span>
                {item.label}
                {activeModule === item.id && <ChevronRight size={16} className="ml-auto text-indigo-400 dark:text-indigo-400" />}
              </button>
            ))}
          </nav>
          <div className="p-3 border-t border-gray-100 dark:border-gray-800">
            <p className="text-[10px] text-gray-400 dark:text-gray-500 text-center font-medium">v2.0 — Plataforma Clínica</p>
          </div>
        </aside>
      )}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white dark:bg-[#111827] border-b border-gray-200 dark:border-gray-800 px-4 py-3 flex items-center justify-between flex-shrink-0 transition-colors duration-200">
          <div className="flex items-center gap-4">
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400">
              {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-white">
              {NAV_ITEMS.find(n => n.id === activeModule)?.label}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700/80 text-gray-700 dark:text-gray-300 transition-all"
              title={theme === 'light' ? 'Activar modo oscuro' : 'Activar modo claro'}
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
          </div>
        </header>
        <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-slate-50 dark:bg-[#0b0f19] transition-colors duration-200">
          {renderModule()}
        </div>
      </main>
    </div>
  );
}
