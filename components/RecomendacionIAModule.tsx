import React, { useState, useEffect } from 'react';
import { Sparkles, Loader2, CheckCircle2, ArrowRight, Shield, Activity, FileText, Send, UserCheck, RefreshCw } from 'lucide-react';
import { useClinical } from './ClinicalContext';
import { calcularEdad } from './clinicalUtils';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
  onTransferToCuadernillo?: (exIds: string[]) => void;
}

export default function RecomendacionIAModule({ pacienteId, onTransferToCuadernillo }: Props) {
  const clinical = useClinical();
  const [loading, setLoading] = useState(false);
  const [pacientes, setPacientes] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string>(pacienteId || '');
  const [recomendacion, setRecomendacion] = useState<any>(null);
  const [transferred, setTransferred] = useState(false);
  const [error, setError] = useState('');

  // Data from clinical context or fallback demo data
  const [pacienteData, setPacienteData] = useState<any>(
    clinical.data.paciente || {
      nombre_completo: 'María Laura González',
      edad: 38,
      sexo: 'Femenino',
      ocupacion: 'Docente de Nivel Primario',
      demanda_vocal_horas: 6
    }
  );
  const [anamnesisData, setAnamnesisData] = useState<any>(
    clinical.data.anamnesis || {
      motivo_consulta: 'Disfonía fluctuante de 6 meses de evolución, fatiga vocal al final de la jornada laboral.',
      diagnostico_orl: 'Esbozo nodular bilateral / Lesión exofítica en tercio medio',
      sintomas: { disfonia: true, fatiga_vocal: true, carraspeo: true, dolor: false }
    }
  );
  const [riesgoVocalData, setRiesgoVocalData] = useState<any>(
    clinical.data.riesgoVocal || {
      puntaje_total: 82,
      grupo: 'Grupo 2 (Tendencia elevada a desarrollar problema vocal)',
      subtotales_dimensiones: {
        "Hábitos Vocales": 38, "Estado Emocional": 12, "Condiciones Biológicas": 14,
        "Condiciones Ambientales": 12, "Hábitos de Vida": 6
      },
      alertas_conductas_3: ["Habla en ambientes ruidosos", "Carraspea en forma habitual", "Usa la voz estando resfriado"]
    }
  );
  const [escalasData, setEscalasData] = useState<any>(
    clinical.data.escalas || {
      grbas: { G: 2, R: 1, B: 1, A: 0, S: 2 },
      rasati: { R: 1, A: 1, S: 1, A2: 0, T: 2, I: 0 },
      vhi10_score: 18, tme_o: 11.5, tme_s: 9.2, indice_so: 0.8
    }
  );
  const [acusticaData, setAcusticaData] = useState<any>(
    clinical.data.acustica || {
      f0_mean: 215.4, jitter_local_pct: 1.42, shimmer_local_pct: 4.85,
      hnr_db: 15.8, cpps_db: 11.2, avqi: 3.85
    }
  );

  useEffect(() => {
    loadPacientes();
  }, []);

  useEffect(() => {
    if (pacienteId) {
      setSelectedId(pacienteId);
      fetchPacienteData(pacienteId);
    }
  }, [pacienteId]);

  // Sync recomendacion back to clinical context
  useEffect(() => {
    if (recomendacion) {
      clinical.setRecomendacion(recomendacion);
      clinical.setAcustica(acusticaData);
      clinical.markStep('recomendacion');
    }
  }, [recomendacion]);

  const loadPacientes = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/pacientes`);
      if (r.ok) setPacientes(await r.json());
    } catch {}
  };

  const fetchPacienteData = async (id: string) => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/pacientes/${id}`);
      if (r.ok) {
        const data = await r.json();
        setPacienteData({
          nombre_completo: data.nombre_completo || 'Paciente',
          edad: calcularEdad(data.fecha_nacimiento) ?? 35,
          sexo: data.sexo || 'Femenino',
          ocupacion: data.ocupacion || 'Profesional de la voz',
          demanda_vocal_horas: data.demanda_vocal_horas || 4
        });
      }
    } catch {}
  };

  const ejecutarRecomendador = async () => {
    setLoading(true);
    setError('');
    setTransferred(false);
    try {
      const fd = new FormData();
      fd.append('paciente_json', JSON.stringify(pacienteData));
      fd.append('anamnesis_json', JSON.stringify(anamnesisData));
      fd.append('riesgo_vocal_json', JSON.stringify(riesgoVocalData));
      fd.append('escalas_json', JSON.stringify(escalasData));
      fd.append('acustica_json', JSON.stringify(acusticaData));

      const r = await fetch(`${BACKEND_URL}/api/recomendar-terapia`, { method: 'POST', body: fd });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      if (data.ok && data.recomendacion) {
        setRecomendacion(data.recomendacion);
      } else {
        setError('No se pudo generar la recomendación.');
      }
    } catch (e: any) {
      setError(e.message || 'Error de conexión con el motor IA');
    }
    setLoading(false);
  };

  const handleTransferToCuadernillo = () => {
    if (!recomendacion?.ejercicios_recomendados) return;
    const ids = recomendacion.ejercicios_recomendados.map((ex: any) => ex.id);
    if (onTransferToCuadernillo) {
      onTransferToCuadernillo(ids);
    }
    setTransferred(true);
  };

  return (
    <div className="max-w-5xl space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 border border-indigo-700/50 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-indigo-400/20 via-transparent to-transparent pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 flex items-center gap-1">
                <Sparkles size={13} className="text-indigo-300" /> Motor IA Fonoaudiológico v2.0
              </span>
            </div>
            <h2 className="text-2xl font-extrabold tracking-tight">Prescripción Terapéutica Vocal Basada en IA</h2>
            <p className="text-sm text-indigo-200 mt-1 max-w-2xl">
              Sintetiza la Ficha de Riesgo Vocal, Anamnesis, Escalas Perceptuales (GRBAS/RASATI) y Acústica de Praat bajo la evidencia metodológica de la Lic. Patricia Farías.
            </p>
          </div>
          <button
            onClick={ejecutarRecomendador}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white rounded-xl font-bold shadow-lg shadow-emerald-900/30 transition-all transform active:scale-95 disabled:opacity-50 flex-shrink-0"
          >
            {loading ? <Loader2 size={20} className="animate-spin" /> : <Sparkles size={20} />}
            {loading ? 'Sintetizando Clínica...' : 'Generar Plan Terapéutico'}
          </button>
        </div>
      </div>

      {/* Patient Selector & Quick Inputs Context */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase text-gray-500 dark:text-gray-400 tracking-wider">Contexto del Paciente</span>
            <UserCheck size={16} className="text-indigo-500" />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Seleccionar Paciente de la Base</label>
            <select
              value={selectedId}
              onChange={e => {
                setSelectedId(e.target.value);
                if (e.target.value) fetchPacienteData(e.target.value);
              }}
              className="w-full px-3 py-2 bg-gray-50 dark:bg-[#0b0f19] border border-gray-200 dark:border-gray-800 rounded-lg text-sm font-medium text-gray-800 dark:text-gray-200"
            >
              <option value="">-- Usar Caso de Demostración --</option>
              {pacientes.map(p => (
                <option key={p.id} value={p.id}>{p.nombre_completo} ({p.dni})</option>
              ))}
            </select>
          </div>
          <div className="text-xs space-y-1 pt-2 border-t border-gray-100 dark:border-gray-800">
            <p className="font-bold text-gray-700 dark:text-gray-300">{pacienteData.nombre_completo}</p>
            <p className="text-gray-500 dark:text-gray-400">{pacienteData.edad} años • {pacienteData.sexo} • {pacienteData.ocupacion}</p>
            <p className="text-gray-500 dark:text-gray-400">Demanda vocal: {pacienteData.demanda_vocal_horas} hs/día</p>
          </div>
        </div>

        {/* Risk & Scales Summary Card */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase text-gray-500 dark:text-gray-400 tracking-wider">Riesgo Vocal y Escalas</span>
            <Shield size={16} className="text-amber-500" />
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-center bg-amber-50 dark:bg-amber-950/30 p-2 rounded-lg border border-amber-200/50 dark:border-amber-900/50">
              <span className="font-bold text-amber-800 dark:text-amber-300">Puntaje Riesgo Vocal:</span>
              <span className="font-extrabold text-amber-700 dark:text-amber-400">{riesgoVocalData.puntaje_total} pts</span>
            </div>
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>GRBAS (G R B A S):</span>
              <span className="font-bold text-gray-800 dark:text-gray-200">G{escalasData.grbas.G} R{escalasData.grbas.R} B{escalasData.grbas.B} A{escalasData.grbas.A} S{escalasData.grbas.S}</span>
            </div>
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>RASATI Tensión (T):</span>
              <span className="font-bold text-gray-800 dark:text-gray-200">T{escalasData.rasati.T}</span>
            </div>
            <div className="flex justify-between text-gray-600 dark:text-gray-400">
              <span>Índice S/O (TME):</span>
              <span className="font-bold text-gray-800 dark:text-gray-200">{escalasData.indice_so}</span>
            </div>
          </div>
        </div>

        {/* Acoustics Metrics Summary Card */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase text-gray-500 dark:text-gray-400 tracking-wider">Biometría Praat</span>
            <Activity size={16} className="text-indigo-500" />
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-gray-50 dark:bg-[#0b0f19] p-2 rounded-lg border border-gray-200 dark:border-gray-800">
              <p className="text-gray-400">F0 Media</p>
              <p className="font-extrabold text-gray-800 dark:text-gray-200">{acusticaData.f0_mean} Hz</p>
            </div>
            <div className="bg-gray-50 dark:bg-[#0b0f19] p-2 rounded-lg border border-gray-200 dark:border-gray-800">
              <p className="text-gray-400">Jitter %</p>
              <p className="font-extrabold text-gray-800 dark:text-gray-200">{acusticaData.jitter_local_pct}%</p>
            </div>
            <div className="bg-gray-50 dark:bg-[#0b0f19] p-2 rounded-lg border border-gray-200 dark:border-gray-800">
              <p className="text-gray-400">CPPS</p>
              <p className="font-extrabold text-gray-800 dark:text-gray-200">{acusticaData.cpps_db} dB</p>
            </div>
            <div className="bg-gray-50 dark:bg-[#0b0f19] p-2 rounded-lg border border-gray-200 dark:border-gray-800">
              <p className="text-gray-400">AVQI v03.01</p>
              <p className="font-extrabold text-gray-800 dark:text-gray-200">{acusticaData.avqi}</p>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 text-red-600 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* RECOMENDACIÓN IA RESULT DISPLAY */}
      {recomendacion && (
        <div className="space-y-6 animate-fadeIn">
          {/* Fisiopatología & Diagnóstico Funcional */}
          <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                <Sparkles size={18} className="text-indigo-500" /> Síntesis Fisiopatológica Fonoaudiológica
              </h3>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                {recomendacion.diagnostico_funcional_fonoaudiologico}
              </span>
            </div>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed font-medium">
              {recomendacion.sintesis_fisiopatologica}
            </p>

            {/* Objetivos Terapéuticos */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">Objetivos Terapéuticos Prioritarios</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {recomendacion.objetivos_terapeuticos?.map((obj: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 p-3 rounded-xl bg-gray-50 dark:bg-[#0b0f19] border border-gray-200 dark:border-gray-800 text-xs font-medium text-gray-800 dark:text-gray-200">
                    <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                    <span>{obj}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Banco de Ejercicios Prescriptos */}
          <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-3">
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <FileText size={18} className="text-indigo-500" /> Prescripción de Ejercicios (Metodología Farías)
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400">Ejercicios seleccionados por el motor según biomecánica cordal y riesgo vocal</p>
              </div>
              <button
                onClick={handleTransferToCuadernillo}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-all"
              >
                {transferred ? <CheckCircle2 size={14} className="text-emerald-300" /> : <Send size={14} />}
                {transferred ? 'Transferido al Cuadernillo' : 'Exportar a Cuadernillo'}
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {recomendacion.ejercicios_recomendados?.map((ex: any, idx: number) => (
                <div key={idx} className="p-4 rounded-xl bg-gray-50 dark:bg-[#0b0f19] border border-gray-200 dark:border-gray-800 space-y-2 relative overflow-hidden">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xs font-extrabold">{idx + 1}</span>
                      {ex.name}
                    </span>
                    <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ${
                      ex.prioridad === 'Alta' ? 'bg-red-100 dark:bg-red-950/60 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800' : 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                    }`}>
                      Prioridad {ex.prioridad}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
                    <strong className="text-gray-800 dark:text-gray-200">Justificación:</strong> {ex.justificacion}
                  </p>
                  <p className="text-xs text-indigo-600 dark:text-indigo-400 font-semibold bg-indigo-50 dark:bg-indigo-950/30 p-2 rounded-lg border border-indigo-100 dark:border-indigo-900/50">
                    Dosificación: {ex.dosificacion}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Pautas de Higiene Vocal */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm space-y-3">
              <h3 className="font-bold text-gray-900 dark:text-white text-sm uppercase tracking-wider text-amber-600 dark:text-amber-400 flex items-center gap-2">
                <Shield size={16} /> Pautas de Higiene y Modificación Conductual
              </h3>
              <ul className="space-y-2 text-xs text-gray-700 dark:text-gray-300">
                {recomendacion.pautas_higiene_prioritarias?.map((pauta: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 bg-amber-50/50 dark:bg-amber-950/20 p-2.5 rounded-lg border border-amber-200/40 dark:border-amber-900/40">
                    <span className="text-amber-500 font-bold">•</span>
                    <span>{pauta}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm space-y-3">
              <h3 className="font-bold text-gray-900 dark:text-white text-sm uppercase tracking-wider text-indigo-600 dark:text-indigo-400 flex items-center gap-2">
                <RefreshCw size={16} /> Plan de Frecuencia y Sesiones
              </h3>
              {recomendacion.plan_sesiones && (
                <div className="space-y-3 text-xs text-gray-700 dark:text-gray-300">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-3 bg-gray-50 dark:bg-[#0b0f19] rounded-xl border border-gray-200 dark:border-gray-800">
                      <p className="text-gray-400">Frecuencia</p>
                      <p className="font-extrabold text-gray-800 dark:text-gray-200">{recomendacion.plan_sesiones.frecuencia}</p>
                    </div>
                    <div className="p-3 bg-gray-50 dark:bg-[#0b0f19] rounded-xl border border-gray-200 dark:border-gray-800">
                      <p className="text-gray-400">Sesiones Sugeridas</p>
                      <p className="font-extrabold text-gray-800 dark:text-gray-200">{recomendacion.plan_sesiones.total_sesiones_sugeridas} sesiones</p>
                    </div>
                  </div>
                  <p className="bg-indigo-50/50 dark:bg-indigo-950/20 p-3 rounded-xl border border-indigo-100 dark:border-indigo-900/50 text-xs leading-relaxed">
                    <strong>Etapas Terapéuticas:</strong> {recomendacion.plan_sesiones.etapas}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
