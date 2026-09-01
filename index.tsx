import React, { useState, useEffect, useMemo, useCallback } from "react";
import { createRoot } from "react-dom/client";
import { 
  Users, Calendar, Settings, Mic, Save, Bot, MicOff, Home, FileBarChart, PenTool, Loader2, Sparkles, ShieldCheck, TrendingUp, Zap, BookOpen, BarChart3, Shield, Menu, X, Sun, Moon, Monitor, Building2, MessageSquare, BookMarked, Mail, Clock
} from "lucide-react";

import DashboardSection from "./components/DashboardSection";
import PatientsSection from "./components/PatientsSection";
import ConsultoriosSection from "./components/ConsultoriosSection";
import TelegramInbox from "./components/TelegramInbox";
import ReportsSection from "./components/ReportsSection";
import SettingsSection from "./components/SettingsSection";
import PatientSelectorModal from "./components/PatientSelectorModal";
import GlobalAssistant from "./components/GlobalAssistant";
import ClinicalMascot from "./components/ClinicalMascot";
import { TREATMENT_PLAN_TEMPLATE } from "./types/reports";

import { supabase } from "./utils/supabaseClient";

import Editor from "./components/Editor";
import HomeGuideEditor from "./components/HomeGuideEditor";
import HomeGuidePreview from "./components/HomeGuidePreview";
import { ConsultorioConfigPanel } from "./components/ConsultorioConfigPanel";
import DashboardAnalytics from "./components/DashboardAnalytics";
import FollowUpWorklist from "./components/FollowUpWorklist";
import SuggestionEffectivenessDashboard from "./components/SuggestionEffectivenessDashboard";

import { ToastProvider, useToast } from "./context/ToastContext";
import { useRealtimeSync } from "./hooks/useRealtimeSync";
import { ThemeProvider } from "./context/ThemeContext";
import { SettingsProvider } from "./context/SettingsContext";
import { ClinicalAlertBusProvider } from "./context/ClinicalAlertBus";
import { useAlertBridge } from "./hooks/useAlertBridge";
import { QueryProvider } from "./providers/QueryProvider";
import { ViewType, Patient } from "./types";
import { useAuth } from "./hooks/useAuth";
import { useMaterials } from "./hooks/useMaterials";
import { usePatientsQuery, useAppointmentsQuery, usePatientMutations, useAppointmentMutations } from "./hooks/useSupabaseQueries";
import { useHomeGuideWorkflow } from "./hooks/useHomeGuideWorkflow";
import { useShellUI } from "./hooks/useShellUI";
import { useClinicalIntelligence } from "./hooks/useClinicalIntelligence";
import { useAppStore } from "./store/appStore";
import { clinicalContextManager } from "./services/ClinicalContextManager";

import { LoginPage } from "./components/LoginPage";
import QuickModePanel from "./components/QuickModePanel";
import { TemplateManager } from "./components/TemplateManager";
import PublicGuideView from "./components/PublicGuideView";
import PublicBookingPortal from "./components/PublicBookingPortal";

import AdminPanel from "./components/AdminPanel";
import VisualLibraryScreen from "./components/VisualLibraryScreen";
import SourcesSection from "./components/SourcesSection";
import NotebookLMSection from "./components/NotebookLMSection";
import ComunicacionSection from "./components/ComunicacionSection";
import DiarioTrabajoSection from "./components/DiarioTrabajoSection";
import { ErrorBoundary } from "./components/ErrorBoundary";

import MultimediaCreator from "./components/MultimediaCreator";
import AgendaSincronizada from "./components/AgendaSincronizada";
import { ReportBuilderPro } from "./components/ReportBuilderPro";
import NBADashboard from "./components/NBADashboard";
import { ThemeToggle } from "./components/ThemeToggle";
import VocalisLabModule from "./components/VocalisLabModule";


// --- Main App Component ---

const App = () => {
  const { addToast } = useToast();
  // Check for public share route
  const pathParts = window.location.pathname.split('/');
  const isPublicShareRoute = pathParts[1] === 'share' && pathParts[2] === 'guide';
  const isBookingRoute = pathParts[1] === 'agendar' || pathParts[1] === 'booking';
  const shareToken = isPublicShareRoute ? pathParts[3] : null;

  const auth = useAuth();
  useRealtimeSync();
  const { session, userProfile, dbProfile, isAuthLoading, isGoogleConnected, signOut } = auth;

  // React Query — single source of truth for server data
  const { data: patients = [] } = usePatientsQuery();
  const { data: appointments = [] } = useAppointmentsQuery();

  // Zustand — UI state only
  const selectedPatientId = useAppStore(s => s.selectedPatientId);
  const setSelectedPatientId = useAppStore(s => s.setSelectedPatientId);

  // Derived: selectedPatient from React Query data
  const selectedPatient = useMemo(
    () => patients.find(p => p.id === selectedPatientId) || null,
    [patients, selectedPatientId]
  );

  // Mutations
  const { handleCreatePatient, handleDeletePatient, handleFormalizeQuickPatient, handleDiscardQuickPatient, handleSessionComplete, updatePatientField } = usePatientMutations(session?.user?.id);
  const { handleUpdateStatus } = useAppointmentMutations();

  // Compatibility bridge: old setPatients(prev => ...) → React Query updatePatientField
  const setPatientsCompat = useCallback(( updater: React.SetStateAction<Patient[]> ) => {
    if (typeof updater === 'function') {
      const updated = updater(patients);
      // Diff: find patients that changed and persist each field change
      for (const newP of updated) {
        const oldP = patients.find(p => p.id === newP.id);
        if (!oldP) continue;
        for (const key of Object.keys(newP) as (keyof Patient)[]) {
          if (JSON.stringify(newP[key]) !== JSON.stringify(oldP[key])) {
            updatePatientField({ patientId: newP.id, field: key as string, value: newP[key] });
          }
        }
      }
    }
  }, [patients, updatePatientField]);

  const { materials, materialsError, isLoadingMaterials, fetchMaterials } = useMaterials();

  const { showHomeGuideEditor, showHomeGuidePreview, currentHomeGuideDraft, handleGenerateHomeGuideDraft, handleSaveHomeGuide, handleShowHomeGuidePreview, closeHomeGuideEditor, closeHomeGuidePreview } = useHomeGuideWorkflow({ addToast });

  const { proactiveSuggestions, redFlags, dismissRedFlag } = useClinicalIntelligence(patients);

  useAlertBridge(proactiveSuggestions, redFlags, patients);

  const {
    currentView, setCurrentView,
    selectedConsultorio, setSelectedConsultorio,
    consultorioConfigVersion, setConsultorioConfigVersion,
    pendingPatientId, setPendingPatientId,
    isAssistantOpen, setIsAssistantOpen,
    showNewPatientModal, setShowNewPatientModal,
    showPatientSelector, setShowPatientSelector,
    showConsultorioConfig, setShowConsultorioConfig,
    showTemplateManager, setShowTemplateManager,
    showQuickMode, setShowQuickMode,
    editingMaterialId, setEditingMaterialId,
    isEditingPlan, setIsEditingPlan,
    editedPlan, setEditedPlan,
    showReportEditor, setShowReportEditor,
    reportGuideId, setReportGuideId,
    newReportContent, setNewReportContent,
    newReportType, setNewReportType,
    handleStartReport, handleSaveReport,
  } = useShellUI({ addToast });

  // Derived: pendingPatient from React Query data
  const pendingPatient = useMemo(
    () => pendingPatientId ? patients.find(p => p.id === pendingPatientId) || null : null,
    [patients, pendingPatientId]
  );

  // Sync clinicalContextManager when selectedPatient changes
  useEffect(() => {
    if (selectedPatient) {
      clinicalContextManager.setPatient(selectedPatient.id);
      clinicalContextManager.setPatientSummary({
        name: selectedPatient.name,
        age: selectedPatient.age,
        diagnosis: selectedPatient.diagnosis,
        alerts: selectedPatient.alerts || [],
        interests: selectedPatient.interests || [],
      });
    } else {
      clinicalContextManager.setPatient(null);
    }
  }, [selectedPatient]);

  const [showMobileSidebar, setShowMobileSidebar] = useState(false);

  const navigate = useCallback((view: ViewType) => {
    setCurrentView(view);
    setShowMobileSidebar(false);
  }, [setCurrentView]);

  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(null, '', window.location.pathname);
    }
  }, []);

  const activePatients = patients.filter(p => p.quick_status !== 'active_quick').length;
  const pendingReports = patients.filter(p => p.quick_status !== 'active_quick' && (!p.reports || p.reports.length === 0)).length;
  const todayAppointments = appointments.filter(a => a.date === new Date().toISOString().split('T')[0]).length;
  const totalSessions = patients.filter(p => p.quick_status !== 'active_quick').reduce((sum, p) => sum + (p.history?.length || 0), 0);
  const patientsWithPlan = patients.filter(p => p.quick_status !== 'active_quick' && p.treatmentPlan?.strategies && p.treatmentPlan.strategies.length > 0).length;
  const recentSessions = patients.filter(p => p.quick_status !== 'active_quick').reduce((sum, p) => {
    const recent = (p.history || []).filter(s => {
      const d = new Date(s.date);
      const weekAgo = new Date();
      weekAgo.setDate(weekAgo.getDate() - 7);
      return d >= weekAgo;
    });
    return sum + recent.length;
  }, 0);

  if (isBookingRoute) {
    return <PublicBookingPortal />;
  }

  if (isPublicShareRoute && shareToken) {
    return <PublicGuideView token={shareToken} materials={materials} />;
  }

  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="animate-spin text-blue-600 dark:text-blue-400" size={32} />
          <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Cargando FonoAudio-Pro...</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return <LoginPage onSkip={() => {
      const devId = '00000000-0000-0000-0000-000000000001';
      auth.setSession({ user: { id: devId, email: 'dev@fonoaudio.local', user_metadata: { full_name: 'Desarrollador Local' } } } as any);
      auth.setUserProfile({ id: devId, email: 'dev@fonoaudio.local', name: 'Desarrollador Local', avatarUrl: '' });
    }} />;
  }

  return (
    <div className="flex h-screen bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-200 font-sans overflow-hidden">
      <aside className={`w-64 bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 flex flex-col z-20 shadow-sm shrink-0 max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:transition-transform max-md:duration-200 ${showMobileSidebar ? 'max-md:translate-x-0' : 'max-md:-translate-x-full'}`}>
        <div className="p-6 border-b border-slate-100 dark:border-slate-700 flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white"><Bot size={20} /></div>
          <span className="font-bold text-xl text-slate-900 dark:text-white tracking-tight">Fono-Pro</span>
        </div>
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
           <button onClick={() => navigate("dashboard")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "dashboard" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Home size={20} /> Dashboard</button>
           <button onClick={() => { setSelectedPatientId(null); setSelectedConsultorio(null); navigate("consultorios"); }} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "consultorios" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Building2 size={20} /> Consultorios</button>
           <button onClick={() => { setSelectedPatientId(null); navigate("patients"); }} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "patients" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Users size={20} /> Pacientes</button>
            <button onClick={() => navigate("agenda")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "agenda" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Calendar size={20} /> Agenda</button>
            <button onClick={() => navigate("telegram")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "telegram" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><MessageSquare size={20} /> Canal Clínico</button>
            <button onClick={() => navigate("followup")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "followup" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><ShieldCheck size={20} /> Seguimiento</button>
            <button onClick={() => navigate("metrics")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "metrics" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><TrendingUp size={20} /> Métricas IA</button>
            <button onClick={() => navigate("analytics")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "analytics" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><BarChart3 size={20} /> Analytics</button>
            <button onClick={() => navigate("reports")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "reports" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><FileBarChart size={20} /> Informes</button>

          <button onClick={() => setShowTemplateManager(true)} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${showTemplateManager ? "bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><PenTool size={20} /> Plantillas IA</button>

          <button onClick={() => navigate("library")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "library" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><BookOpen size={20} /> Biblioteca</button>

          <button onClick={() => navigate("sources")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "sources" ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><BookMarked size={20} /> Fuentes Clínicas</button>

          <button onClick={() => navigate("notebooklm")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "notebooklm" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><BookOpen size={20} /> NotebookLM</button>

          <button onClick={() => navigate("comunicacion")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "comunicacion" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Mail size={20} /> Comunicación</button>

          <button onClick={() => navigate("diario")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "diario" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Clock size={20} /> Diario de Trabajo</button>

          <button onClick={() => navigate("multimedia")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "multimedia" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}>
            <Sparkles size={20} /> Multimedia
          </button>

          <button onClick={() => navigate("vocalislab")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "vocalislab" ? "bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}>
            <Mic size={20} /> VocalisLab
          </button>

          {(dbProfile?.role === 'admin' || session?.user?.id === '00000000-0000-0000-0000-000000000001') && (
            <button onClick={() => navigate("admin")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "admin" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Shield size={20} /> Administración</button>
          )}

          <button onClick={() => navigate("settings")} className={`flex items-center gap-3 w-full p-3 rounded-lg transition-all ${currentView === "settings" ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium" : "text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700"}`}><Settings size={20} /> Configuración</button>
          
          <div className="pt-2 border-t border-slate-100 dark:border-slate-700 mt-2">
            <button onClick={() => setShowQuickMode(true)} className="flex items-center gap-3 w-full p-3 rounded-lg transition-all bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/30 font-medium border border-amber-200 dark:border-amber-800">
              <Zap size={20} /> Modo Rápido
            </button>
          </div>
        </nav>
        {userProfile && (
          <div className="px-4 py-3 border-t border-slate-100 dark:border-slate-700">
            <div className="flex items-center gap-3 mb-3">
              {userProfile.avatarUrl ? (
                <img src={userProfile.avatarUrl} alt="" className="w-8 h-8 rounded-full object-cover" />
              ) : (
                <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center text-sm font-bold">
                  {userProfile.name.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-slate-800 dark:text-white truncate">{userProfile.name}</p>
                <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate">{userProfile.email}</p>
                <span className={`inline-block mt-1 px-1.5 py-0.5 text-[9px] font-bold rounded-full ${
                  dbProfile?.role === 'admin' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400' :
                  dbProfile?.role === 'supervisor' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400' :
                  dbProfile?.role === 'secretaria' ? 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-400' :
                  session?.user?.id === '00000000-0000-0000-0000-000000000001'
                    ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400'
                    : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                }`}>
                  {dbProfile?.role === 'admin' || session?.user?.id === '00000000-0000-0000-0000-000000000001'
                    ? 'Admin'
                    : dbProfile?.role === 'supervisor' ? 'Supervisor'
                    : dbProfile?.role === 'secretaria' ? 'Secretaria'
                    : 'Profesional'}
                </span>
              </div>
            </div>
            <div className="flex gap-2">
              {isGoogleConnected && (
                <span className="flex items-center gap-1 text-[10px] font-bold text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-2 py-1 rounded-lg">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span> Google
                </span>
              )}
              <button
                onClick={signOut}
                className="text-[10px] font-bold text-slate-400 hover:text-red-500 px-2 py-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors ml-auto"
              >
                Salir
              </button>
            </div>
          </div>
        )}
        <div className="p-4 border-t border-slate-100 dark:border-slate-700 space-y-2">
          <ThemeToggle />
          <button onClick={() => setIsAssistantOpen(!isAssistantOpen)} className={`w-full flex items-center justify-center gap-2 p-3 rounded-xl font-medium transition-all shadow-sm ${isAssistantOpen ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800' : 'bg-slate-900 dark:bg-slate-700 text-white hover:bg-slate-800 dark:hover:bg-slate-600'}`}>
            {isAssistantOpen ? <><MicOff size={18} /> Cerrar IA</> : <><Mic size={18} /> Asistente IA</>}
          </button>
        </div>
      </aside>

      {showMobileSidebar && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setShowMobileSidebar(false)} />
      )}

      <main className="flex-1 flex flex-col relative overflow-y-auto">
        <div className="md:hidden p-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex items-center gap-3">
          <button onClick={() => setShowMobileSidebar(true)} className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700">
            <Menu size={20} className="text-slate-600 dark:text-slate-400" />
          </button>
          <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center text-white"><Bot size={14} /></div>
          <span className="font-bold text-sm text-slate-800 dark:text-white">Fono-Pro</span>
        </div>
        {currentView === "dashboard" && (
          <ErrorBoundary moduleName="Dashboard">
          <DashboardSection
            patients={patients}
            appointments={appointments}
            proactiveSuggestions={proactiveSuggestions}
            redFlags={redFlags}
            activePatients={activePatients}
            pendingReports={pendingReports}
            todayAppointments={todayAppointments}
            totalSessions={totalSessions}
            patientsWithPlan={patientsWithPlan}
            recentSessions={recentSessions}
            onSelectPatient={(p) => { setSelectedPatientId(p?.id ?? null); setCurrentView("patients"); }}
            onNavigate={(v) => setCurrentView(v as ViewType)}
            onDismissRedFlag={dismissRedFlag}
            fetchMaterials={fetchMaterials}
            isGoogleConnected={isGoogleConnected}
            onNavigateToSettings={() => setCurrentView("settings")}
            userId={session?.user?.id}
          />
          </ErrorBoundary>
        )}

        {currentView === "consultorios" && (
          <ErrorBoundary moduleName="Consultorios">
          <ConsultoriosSection
            patients={patients}
            onSelectConsultorio={(id) => {
              setSelectedConsultorio(id);
              setSelectedPatientId(null);
              setCurrentView("patients");
            }}
            onShowConfig={() => setShowConsultorioConfig(true)}
          />
          </ErrorBoundary>
        )}
 
          {currentView === "patients" && (
            <ErrorBoundary moduleName="Pacientes">
            <PatientsSection
              patients={patients}
              selectedPatient={selectedPatient}
              selectedConsultorio={selectedConsultorio}
              materials={materials}
              onSelectPatient={(p) => { setSelectedPatientId(p?.id ?? null); setCurrentView("patients"); }}
              onSelectConsultorio={setSelectedConsultorio}
              onCreatePatient={() => setShowNewPatientModal(true)}
              onDeletePatient={handleDeletePatient}
              onFormalizeQuick={handleFormalizeQuickPatient}
              onDiscardQuick={handleDiscardQuickPatient}
              onSessionComplete={handleSessionComplete}
              onStartReport={handleStartReport}
              onShowConsultorioConfig={() => setShowConsultorioConfig(true)}
              onGenerateHomeGuideDraft={handleGenerateHomeGuideDraft}
              onSaveHomeGuide={handleSaveHomeGuide}
              onScheduleAppointment={(patient) => {
                setSelectedPatientId(patient.id);
                setPendingPatientId(patient.id);
                setCurrentView("agenda");
              }}
              consultorioConfigVersion={consultorioConfigVersion}
              setShowNewPatientModal={setShowNewPatientModal}
              setPatients={setPatientsCompat}
            />
            </ErrorBoundary>
          )}
 
 
 
          {currentView === "agenda" && (
            <ErrorBoundary moduleName="Agenda">
              <React.Suspense fallback={<div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-blue-500" size={24} /></div>}>
                <AgendaSincronizada
                  patients={patients}
                  proactiveSuggestions={proactiveSuggestions}
                  pendingPatient={pendingPatient}
                  onPendingPatientHandled={() => setPendingPatientId(null)}
                />
              </React.Suspense>
            </ErrorBoundary>
          )}

          {currentView === "telegram" && (
            <ErrorBoundary moduleName="Canal Clínico">
              <div className="h-full">
                <TelegramInbox
                  onNavigateToSettings={() => setCurrentView("settings")}
                  onNavigate={(v) => setCurrentView(v as ViewType)}
                  userId={session?.user?.id}
                  patients={patients}
              onSelectPatient={(p) => { setSelectedPatientId(p?.id ?? null); if (p) setCurrentView("patients"); }}
                />
              </div>
            </ErrorBoundary>
          )}
 
          {currentView === "followup" && (
            <ErrorBoundary moduleName="Seguimiento">
              <FollowUpWorklist onPatientSelect={(id) => {
                if (!id) { setCurrentView("patients"); return; }
                const p = patients.find(pat => pat.id === id);
                if (p) {
                  setSelectedPatientId(p.id);
                  setCurrentView("patients");
                }
              }} />
            </ErrorBoundary>
          )}
 
          {currentView === "metrics" && (
            <ErrorBoundary moduleName="Métricas">
              <div className="p-4 sm:p-6 lg:p-8 space-y-8">
                <SuggestionEffectivenessDashboard />
                <React.Suspense fallback={<div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-blue-500" size={24} /></div>}>
                  <NBADashboard />
                </React.Suspense>
              </div>
            </ErrorBoundary>
          )}

          {currentView === "analytics" && (
            <ErrorBoundary moduleName="Analítica">
              <DashboardAnalytics consultorioId={selectedConsultorio || undefined} />
            </ErrorBoundary>
          )}

          {currentView === "sources" && (
            <ErrorBoundary moduleName="Fuentes Clínicas">
              <SourcesSection onNavigate={setCurrentView} />
            </ErrorBoundary>
          )}

          {currentView === "notebooklm" && (
            <ErrorBoundary moduleName="NotebookLM">
              <NotebookLMSection onNavigate={setCurrentView} />
            </ErrorBoundary>
          )}

          {currentView === "comunicacion" && (
            <ErrorBoundary moduleName="Comunicación">
              <ComunicacionSection
                userId={session?.user?.id}
                patients={patients}
                onSelectPatient={(p) => { setSelectedPatientId(p?.id ?? null); setCurrentView("patients"); }}
              />
            </ErrorBoundary>
          )}

          {currentView === "diario" && (
            <ErrorBoundary moduleName="Diario de Trabajo">
              <DiarioTrabajoSection
                userId={session?.user?.id}
                patients={patients}
                onSelectPatient={(p) => { setSelectedPatientId(p?.id ?? null); setCurrentView("patients"); }}
              />
            </ErrorBoundary>
          )}

          {currentView === "multimedia" && session?.user?.id && (
            <ErrorBoundary moduleName="Multimedia">
              <div className="flex-1 overflow-y-auto">
                <React.Suspense fallback={<div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-blue-500" size={24} /></div>}>
                  <MultimediaCreator
                    userId={session.user.id}
                    consultorioId={selectedConsultorio || undefined}
                    patientId={selectedPatient?.id}
                    onMaterialCreated={async (id) => {
                      await fetchMaterials();
                      setEditingMaterialId(null);
                      setCurrentView("library");
                    }}
                    editMaterialId={editingMaterialId}
                  />
                </React.Suspense>
              </div>
            </ErrorBoundary>
          )}

          {currentView === "vocalislab" && (
            <ErrorBoundary moduleName="VocalisLab">
              <VocalisLabModule />
            </ErrorBoundary>
          )}
 
           {currentView === "reports" && (
            <ErrorBoundary moduleName="Informes">
              <ReportsSection onStartReport={handleStartReport} />
            </ErrorBoundary>
          )}
 
          {currentView === "admin" && (
            <ErrorBoundary moduleName="Administración">
              <AdminPanel onAccessDenied={() => setCurrentView("dashboard")} />
            </ErrorBoundary>
          )}

          {currentView === "settings" && (
            <ErrorBoundary moduleName="Configuración">
              <SettingsSection isGoogleConnected={isGoogleConnected} />
            </ErrorBoundary>
          )}

          {currentView === "library" && (
            <ErrorBoundary moduleName="Biblioteca">
              <div className="flex flex-col h-full overflow-y-auto">
                <VisualLibraryScreen
                  materials={materials}
                  isLoading={isLoadingMaterials}
                  error={materialsError ? "Error cargando materiales" : null}
                  onUpload={async () => {
                    await fetchMaterials();
                  }}
                  onEditMaterial={(m) => {
                    setEditingMaterialId(m.id);
                    setCurrentView("multimedia");
                  }}
                />
              </div>
            </ErrorBoundary>
          )}

       </main>

       {showTemplateManager && (
         <div className="fixed inset-0 bg-black/50 z-[70] flex items-center justify-center p-4 backdrop-blur-sm">
           <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700">
             <TemplateManager onClose={() => setShowTemplateManager(false)} />
           </div>
         </div>
       )}

        <ErrorBoundary moduleName="Asistente IA">
          <GlobalAssistant
            isOpen={isAssistantOpen}
            setIsOpen={setIsAssistantOpen}
            professionalName={userProfile?.name}
            professionalRole={dbProfile?.role}
            professionalId={session?.user?.id}
          />
        </ErrorBoundary>

        {/* Mascota virtual de FonoAudio-Pro — da vida al asistente dentro de la app */}
        <ClinicalMascot
          redFlags={redFlags}
          isAssistantOpen={isAssistantOpen}
          setIsAssistantOpen={setIsAssistantOpen}
          proactiveSuggestions={proactiveSuggestions}
        />


          {showNewPatientModal && (
 
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-900 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-200 dark:border-slate-700">
              <h3 className="font-bold text-lg mb-4 text-slate-800 dark:text-white">Nuevo Paciente</h3>
              <form onSubmit={(e) => {
                e.preventDefault(); const fd = new FormData(e.currentTarget);
                const diagnosisVal = fd.get("diagnosis") as string;
                const consultationType = fd.get("consultationType") as string;
                handleCreatePatient({ id: crypto.randomUUID(), name: fd.get("name") as string, age: Number(fd.get("age")), diagnosis: consultationType === 'consulta' ? `Consulta: ${fd.get("notes") || 'Sin especificar'}` : consultationType === 'evaluacion' ? 'En evaluación' : consultationType === 'seguimiento' ? 'En seguimiento' : consultationType === 'tratamiento' ? 'En tratamiento' : diagnosisVal || '', phone: fd.get("phone") as string, document: "", email: "", notes: fd.get("notes") as string || "", treatmentPlan: { general: "", specific: [], strategies: TREATMENT_PLAN_TEMPLATE }, history: [], evaluations: [], documents: [], reports: [], consultorio: selectedConsultorio || undefined });
                setShowNewPatientModal(false);
              }} className="space-y-4">
                <input name="name" placeholder="Nombre" required className="w-full p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500" />
                <input name="age" placeholder="Edad" type="number" required className="w-full p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500" />
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 dark:text-slate-400">Tipo de Consulta</label>
                  <select name="consultationType" className="w-full p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-white">
                    <option value="consulta">Consulta</option>
                    <option value="evaluacion">Evaluación</option>
                    <option value="seguimiento">Seguimiento</option>
                    <option value="tratamiento">Tratamiento</option>
                    <option value="diagnostico">Diagnóstico específico</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-slate-500 dark:text-slate-400">Diagnóstico (opcional)</label>
                  <input name="diagnosis" placeholder="Ej: Disfagia orofaríngea, Trastorno del lenguaje..." className="w-full p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500" />
                </div>
                <input name="phone" placeholder="Teléfono" className="w-full p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500" />
                <input name="notes" placeholder="Notas adicionales (opcional)" className="w-full p-2.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-700 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500" />
                <div className="flex gap-2 mt-4"><button type="button" onClick={() => setShowNewPatientModal(false)} className="flex-1 p-2.5 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">Cancelar</button><button type="submit" className="flex-1 p-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors">Guardar</button></div>
              </form>
            </div>
          </div>
        )}
 
       <PatientSelectorModal isOpen={showPatientSelector} onClose={() => setShowPatientSelector(false)} patients={patients} onSelect={(p) => { setShowPatientSelector(false); setSelectedPatientId(p.id); setShowReportEditor(true); }} />
 
       {isEditingPlan && selectedPatient && (
         <div className="fixed inset-0 bg-black/50 z-[60] flex items-center justify-center p-4 backdrop-blur-sm">
           <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700">
             <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-800">
               <h3 className="font-bold text-slate-800 dark:text-white">Editar Plan de Tratamiento</h3>
               <div className="flex gap-2">
                 <button onClick={() => setIsEditingPlan(false)} className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg text-sm font-medium transition-colors">Cancelar</button>
                  <button onClick={() => {
                    const updatedP = { ...selectedPatient, treatmentPlan: { ...selectedPatient.treatmentPlan, strategies: editedPlan } };
                    updatePatientField({ patientId: selectedPatient.id, field: 'treatmentPlan', value: updatedP.treatmentPlan });
                    setIsEditingPlan(false);
                  }} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm font-medium transition-colors"><Save size={18} /> Guardar</button>
               </div>
             </div>
             <div className="flex-1 p-4 overflow-hidden bg-slate-100 dark:bg-slate-800">
               <Editor content={editedPlan} onChange={setEditedPlan} />
             </div>
           </div>
         </div>
       )}
 
        {showReportEditor && selectedPatient && (
          <ErrorBoundary moduleName="Constructor de Informes">
            <React.Suspense fallback={<div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-blue-500" size={24} /></div>}>
              <ReportBuilderPro
                patient={selectedPatient}
                onClose={() => setShowReportEditor(false)}
                onSave={handleSaveReport}
                initialGuideId={reportGuideId}
              />
            </React.Suspense>
          </ErrorBoundary>
        )}
 
       {showHomeGuideEditor && currentHomeGuideDraft && selectedPatient && (
         <HomeGuideEditor
           guide={currentHomeGuideDraft}
           patient={selectedPatient}
           onSave={handleSaveHomeGuide}
           onCancel={closeHomeGuideEditor}
           onPreview={() => handleShowHomeGuidePreview(currentHomeGuideDraft)}
           materials={materials}
           materialsError={materialsError}
         />
       )}

        {showHomeGuidePreview && currentHomeGuideDraft && (
          <HomeGuidePreview
            guide={currentHomeGuideDraft}
            materials={materials}
            patientName={selectedPatient?.name || 'Paciente'}
            onClose={closeHomeGuidePreview}
          />
        )}

        <ConsultorioConfigPanel
          isOpen={showConsultorioConfig}
          onClose={() => setShowConsultorioConfig(false)}
          onSave={() => setConsultorioConfigVersion(v => v + 1)}
        />

        <QuickModePanel
          isOpen={showQuickMode}
          onClose={() => setShowQuickMode(false)}
          onSavePatient={async (patient) => {
            await handleCreatePatient(patient);
            addToast({ message: 'Paciente guardado en la base de datos', type: 'success' });
          }}
        />
      </div>
   );
 };
 
  const rootElement = document.getElementById("root");
  
  if (rootElement) {
    const root = createRoot(rootElement);
    root.render(
      <ErrorBoundary moduleName="FonoAudio Pro">
        <QueryProvider>
          <ToastProvider>
            <ThemeProvider>
              <SettingsProvider>
                <ClinicalAlertBusProvider>
                  <App />
                </ClinicalAlertBusProvider>
              </SettingsProvider>
            </ThemeProvider>
          </ToastProvider>
        </QueryProvider>
      </ErrorBoundary>
    );
  }
