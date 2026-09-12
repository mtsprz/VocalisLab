import React, { useState, useEffect } from 'react';
import { FileText, Download, Loader2, CheckCircle2, Settings, Sparkles, AlertCircle, Shield, Music, Activity, Wind, MessageCircle, Mail, X, Send } from 'lucide-react';
import { useClinical } from './ClinicalContext';
import { firmaProfesional } from './clinicalUtils';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
  initialExerciseIds?: string[];
}

interface Exercise {
  id: string;
  name: string;
  description: string;
  steps: string[];
  duration_min?: number;
  phrases?: string[];
}

interface Section {
  id: string;
  name: string;
  description: string;
  exercises: Exercise[];
}

interface Preset {
  id: string;
  name: string;
  description: string;
  exercise_ids: string[];
  sesiones_recomendadas: number;
  frecuencia: string;
}

const DEFAULT_PRESETS: Preset[] = [
  {
    id: "dmt_1",
    name: "DMT Tipo I — Hiperfunción Isométrica",
    description: "Isometría laríngea con laringe elevada y tensión. Foco en Le Huche, descontracturación cervical y descenso laríngeo.",
    exercise_ids: ["le_huche", "shiatsu_cabeza", "rotacion_hombros", "masaje_laringeo", "descenso_laringeo", "respiracion_abdominal", "tubo_agua", "calentamiento"],
    sesiones_recomendadas: 10,
    frecuencia: "2 veces por semana"
  },
  {
    id: "dmt_2",
    name: "DMT Tipo II — Contracción Supraglótica",
    description: "Aproximación excesiva de bandas ventriculares. Foco en ensanchamiento faríngeo, SOVTE en tubo de agua y soplo aspirado.",
    exercise_ids: ["le_huche", "descenso_laringeo", "tubo_agua", "soplo_escalonado", "humming_m", "vibracion_labial", "enfriamiento"],
    sesiones_recomendadas: 12,
    frecuencia: "2 a 3 veces por semana"
  },
  {
    id: "nodo_cordial",
    name: "Nódulos Cordales / Lesiones Exofíticas",
    description: "Edema en punto nodular por microtrauma. Foco en reeducación respiratoria, ataque suave, SOVTE y descontracturación.",
    exercise_ids: ["le_huche", "masaje_laringeo", "respiracion_abdominal", "soplo_escalonado", "tubo_agua", "humming_m", "frases_balanceadas", "calentamiento", "enfriamiento"],
    sesiones_recomendadas: 14,
    frecuencia: "2 a 3 veces por semana"
  },
  {
    id: "paralisis_cordal",
    name: "Parálisis Cordal / Incompetencia Glótica",
    description: "Déficit de cierre cordal. Foco en apoyo costodiafragmático, consonantes fricativas sonoras y resonancia anterior.",
    exercise_ids: ["respiracion_abdominal", "expansion_costo_lateral", "consonantes_fricativas", "popote_aire", "escalas_vocalicas", "humming_m"],
    sesiones_recomendadas: 16,
    frecuencia: "2 a 3 veces por semana"
  },
  {
    id: "presbifonia",
    name: "Presbifonía / Atrofia Cordal",
    description: "Atrofia cordal senil con arqueamiento. Foco en incremento de tonicidad con popote estrecho y proyección vocal.",
    exercise_ids: ["expansion_costo_lateral", "popote_aire", "vibracion_labial", "consonantes_fricativas", "escalas_vocalicas", "frases_balanceadas", "calentamiento"],
    sesiones_recomendadas: 12,
    frecuencia: "2 veces por semana"
  },
  {
    id: "fonastenia",
    name: "Fonastenia / Fatiga Vocal Ocupacional",
    description: "Cansancio vocal en docentes y profesionales. Foco en economía vocal (SOVTE), resonancia y pausas vocales.",
    exercise_ids: ["rotacion_hombros", "respiracion_abdominal", "tubo_agua", "popote_aire", "humming_m", "frases_balanceadas", "calentamiento", "enfriamiento"],
    sesiones_recomendadas: 8,
    frecuencia: "2 veces por semana"
  },
  {
    id: "rlf",
    name: "Reflujo Laringofaríngeo (RLF)",
    description: "Irritación interaritenoidea con carraspeo crónico. Foco en higiene digestiva estricta, hidratación y vibración suave.",
    exercise_ids: ["pautas_rlf", "descenso_laringeo", "tubo_agua", "vibracion_labial", "humming_m", "enfriamiento"],
    sesiones_recomendadas: 8,
    frecuencia: "1 a 2 veces por semana"
  },
  {
    id: "edema_reinke",
    name: "Edema de Reinke / Degeneración Polipoidea",
    description: "Aumento de masa y laxitud en espacio de Reinke. Foco en disminución de impacto, resonancia y SOVTE.",
    exercise_ids: ["le_huche", "masaje_laringeo", "tubo_agua", "soplo_escalonado", "humming_m", "calentamiento", "enfriamiento"],
    sesiones_recomendadas: 12,
    frecuencia: "2 veces por semana"
  },
  {
    id: "preparacion_vocal",
    name: "Acondicionamiento y Mantenimiento Vocal",
    description: "Rutina completa de preparación y cuidado para profesionales de la voz hablada y cantada.",
    exercise_ids: ["rotacion_hombros", "le_huche", "respiracion_abdominal", "tubo_agua", "vibracion_labial", "humming_m", "frases_balanceadas", "calentamiento", "enfriamiento"],
    sesiones_recomendadas: 6,
    frecuencia: "diario o pre-jornada"
  }
];

const DEFAULT_SECTIONS: Section[] = [
  {
    id: "corporal",
    name: "Trabajo Corporal y Miofascial",
    description: "Relajación muscular, técnica de Le Huche, digitopresión y liberación miofascial cervicofacial",
    exercises: [
      {
        id: "le_huche",
        name: "Técnica de Relajación Diferencial (Le Huche)",
        description: "Secuencia respiratoria: inspiración nasal, espiración en /f/ y /sh/, apnea y descenso tensional.",
        steps: ["Inspire nasal abdominal 3s", "Espire en /f/ 4s", "Espire en /sh/ prolongado 6s", "Pausa apneica 2-3s relajando hombros", "Repita 8 a 10 ciclos"],
        duration_min: 5
      },
      {
        id: "shiatsu_cabeza",
        name: "Digitopresión Descontracturante Craneofacial y ATM",
        description: "Puntos de presión en vértex, sienes, ATM, maseteros y músculos suprahioideos.",
        steps: ["Vértex 30s circular", "Sienes 30s bilateral", "ATM con apertura mandibular 30s", "Maseteros 40s descendente", "Zona submandibular hacia hioides"],
        duration_min: 5
      },
      {
        id: "rotacion_hombros",
        name: "Movilización Articular Cervicoescapular",
        description: "Desbloqueo de cintura escapular y cuello para reducir el anclaje laríngeo superior.",
        steps: ["Círculos de hombros hacia atrás 10x", "Círculos hacia adelante 10x", "Inclinación lateral 15s por lado", "Rotación suave 10s por lado"],
        duration_min: 4
      }
    ]
  },
  {
    id: "laringeo",
    name: "Flexibilización y Descenso Laríngeo",
    description: "Masaje circumlaríngeo de Aronson, descenso laríngeo activo y liberación del espacio tirohioideo",
    exercises: [
      {
        id: "masaje_laringeo",
        name: "Masaje Circumlaríngeo Manual (Aronson/Farías)",
        description: "Masaje circular en espacio tirohioideo y láminas tiroideas para descender la laringe elevada.",
        steps: ["Palpe espacio tirohioideo bilateral", "Movimientos circulares suaves de anterior a posterior", "Desplace la laringe lateralmente", "Fonación simultánea en /u/ grave y relajada"],
        duration_min: 4
      },
      {
        id: "descenso_laringeo",
        name: "Bostezo-Suspiro Activo con Emisión Grave",
        description: "Facilita la apertura faríngea y el descenso fisiológico del hioides y laringe.",
        steps: ["Bostezo amplio sintiendo descenso laríngeo", "Suspiro sonoro en /u/ o /o/ sin ataque duro", "8 repeticiones pausadas"],
        duration_min: 3
      },
      {
        id: "oclusion_succion",
        name: "Técnica de Succión con Popote / Cucharita",
        description: "Estimula la ampliación faríngea y el descenso pasivo del complejo hio-laríngeo.",
        steps: ["Selle labios en popote estrecho", "Succiones suaves de 5-10s", "Emisión sostenida en tono cómodo", "6 ciclos con descanso"],
        duration_min: 3
      }
    ]
  },
  {
    id: "respiratorio",
    name: "Dinámica Respiratoria y Apoyo Costodiafragmático",
    description: "Coordinación fonorrespiratoria, expansión costolateral y dosificación del flujo subglótico",
    exercises: [
      {
        id: "respiracion_abdominal",
        name: "Respiración Costodiafragmática con Dosificación en /s/",
        description: "Reeducación ventilatoria baja para optimizar la presión subglótica sin tensión escapular.",
        steps: ["Inspire diafragmático", "Espire dosificando en fricativa /s/ constante", "Buscar >15s sin temblor", "6 series con pausa"],
        duration_min: 5
      },
      {
        id: "expansion_costo_lateral",
        name: "Expansión Costolateral y Apertura Torácica Baja",
        description: "Apertura de costillas flotantes para incrementar capacidad vital útil.",
        steps: ["Manos en costillas laterales", "Inspire empujando manos hacia afuera", "Conteo 1 al 10 manteniendo costillas abiertas"],
        duration_min: 4
      },
      {
        id: "soplo_escalonado",
        name: "Soplo Escalonado y Ataques Suaves",
        description: "Transición de flujo áfono en /h/ a sonoridad suave para erradicar el golpe de glotis.",
        steps: ["Inicio con soplo en /h/", "Introducir sonoridad progresiva /ha, he, hi, ho, hu/", "Verificar ausencia de golpe glótico"],
        duration_min: 4
      }
    ]
  },
  {
    id: "sovte",
    name: "Tracto Vocal Semiocluido (SOVTE)",
    description: "Tubo de resonancia sumergido en agua (Lax Vox), vibración labial/lingual y popotes delgados",
    exercises: [
      {
        id: "tubo_agua",
        name: "Lax Vox / Tubo Sumergido en Agua",
        description: "Fonación en tubo de silicona sumergido 1.5 cm en agua. Masaje glótico por contrapresión acústica.",
        steps: ["Tubo a 1.5 cm en agua", "Selle labios emitiendo /u/ sostenido con burbujeo parejo", "Glissandos ascendentes y descendentes suaves", "Series de 1 min hasta 5 min"],
        duration_min: 5
      },
      {
        id: "vibracion_labial",
        name: "Vibración de Labios y Lengua (Trill)",
        description: "Oscilación labial /brrr/ o lingual /rrr/ para equilibrar la impedancia acústica.",
        steps: ["Sostenga comisuras suavemente", "Vibración labial /brrr/ sostenida", "Sirenas tonales de grave a agudo"],
        duration_min: 4
      },
      {
        id: "popote_aire",
        name: "Fonación en Popote Delgado al Aire (Titze)",
        description: "Fonación en sorbete estrecho para elevar reactancia acústica y economía vocal.",
        steps: ["Popote estrecho entre labios", "Tonos sostenidos e intensidades variables", "Glissandos cubriendo tesitura modal"],
        duration_min: 4
      },
      {
        id: "consonantes_fricativas",
        name: "Consonantes Sonoras Sostenidas /v/, /z/, /j/",
        description: "Fricativas anteriores para potenciar vibración ósea y colocación en máscara.",
        steps: ["Emisión de /v/ labiodental sostenida", "Transición a vocal /vvv-aaaa/ sin corte", "Repetir con /z/ y /j/"],
        duration_min: 4
      }
    ]
  },
  {
    id: "resonancia",
    name: "Enfoque Resonancial y Proyección Vocal",
    description: "Humming nasal /m/, bostezo-vocal y lectura con frases balanceadas",
    exercises: [
      {
        id: "humming_m",
        name: "Resonancia Anterior con /m/ (Humming de Lessac)",
        description: "Colocación de la voz en máscara facial mediante oclusión bilabial relajada.",
        steps: ["Labios juntos sin apretar", "Emita /m/ conversacional sintiendo vibración labionasal", "Masticación sonora /mmmm-num-num/", "Palabras con nasal inicial"],
        duration_min: 4
      },
      {
        id: "escalas_vocalicas",
        name: "Escalas Vocálicas y Glissandos Controlados",
        description: "Flexibilidad cordal y balance cricotiroideo/tiroaritenoideo.",
        steps: ["Sirena de 5 notas ascendente y descendente", "Volumen moderado sin forzar", "Alternar vocales cerradas y abiertas"],
        duration_min: 5
      },
      {
        id: "frases_balanceadas",
        name: "Frases Fonéticamente Balanceadas para Transferencia",
        description: "Lectura proyectada para transferir los patrones funcionales al habla conversacional.",
        steps: ["Articulación clara y apertura bucal", "Pausas respiratorias adecuadas", "Proyección a 3 metros sin esfuerzo"],
        phrases: [
          "La mañana luminosa renueva la energía de las personas.",
          "Muchos músicos tocan melodías suaves junto al mar.",
          "El río transparente corre tranquilo entre las piedras.",
          "Un vaso de agua fresca alivia la sensación de fatiga."
        ],
        duration_min: 6
      }
    ]
  },
  {
    id: "higiene",
    name: "Higiene y Pautas Preventivas",
    description: "Calentamiento, enfriamiento, hidratación y prevención del reflujo laringofaríngeo",
    exercises: [
      {
        id: "calentamiento",
        name: "Protocolo de Calentamiento Vocal Integral",
        description: "Rutina pre-exigencia de 6 minutos para preparar la viscosidad de la mucosa vocal.",
        steps: ["Respiración y relajación cervical 1 min", "Masaje laríngeo y bostezos 1 min", "Vibración labial /brrr/ con glissandos 2 min", "Humming /m/ y frases 2 min"],
        duration_min: 6
      },
      {
        id: "enfriamiento",
        name: "Protocolo de Enfriamiento y Reposo",
        description: "Desaceleración funcional post-exigencia para evitar edema reactivo.",
        steps: ["Respiración diafragmática lenta con /sh/ 2 min", "Bostezos y suspiros graves /u/ 1 min", "Masaje facial y cervical 1 min", "Hidratación y reposo vocal"],
        duration_min: 5
      },
      {
        id: "pautas_rlf",
        name: "Pautas Antirreflujo Laringofaríngeo (RLF)",
        description: "Higiene digestiva para controlar la irritación ácida/pepsínica de la comisura posterior.",
        steps: ["No acostarse antes de 2.5h post-cena", "Elevar cabecera de la cama 10-15 cm", "Disminuir café, mate caliente, alcohol y picantes", "Hidratación fraccionada en pequeños sorbos"],
        duration_min: 3
      }
    ]
  }
];

export default function CuadernilloModule({ pacienteId, initialExerciseIds }: Props) {
  const clinical = useClinical();
  const [sections, setSections] = useState<Section[]>(DEFAULT_SECTIONS);
  const [presets, setPresets] = useState<Preset[]>(DEFAULT_PRESETS);
  const [selectedPreset, setSelectedPreset] = useState('');
  const [selectedExercises, setSelectedExercises] = useState<string[]>(initialExerciseIds || []);
  const [titulo, setTitulo] = useState('Cuadernillo Terapéutico Vocal');
  const [sesiones, setSesiones] = useState(8);
  const [notas, setNotas] = useState('');
  const [generating, setGenerating] = useState(false);
  const [pdfUrl, setPdfUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [emailBody, setEmailBody] = useState('');
  const [showMembrete, setShowMembrete] = useState(false);
  const [sugerencias, setSugerencias] = useState<any[]>([]);
  const [expandiendo, setExpandiendo] = useState(false);
  const [seccionExpandir, setSeccionExpandir] = useState('sovte');
  const [expandMsg, setExpandMsg] = useState('');
  const [profesional, setProfesional] = useState<Record<string, string>>(() => {
    try {
      const raw = localStorage.getItem('vocalislab_profesional');
      if (raw) return JSON.parse(raw);
    } catch {}
    return {
      profesional_nombre: 'Lic. Matias Perez',
      profesional_titulo: 'Fonoaudiólogo',
      profesional_matricula: '',
      profesional_telefono: '',
      profesional_email: '',
      profesional_instagram: '',
      profesional_direccion: 'Consultorio',
      profesional_logo_url: '',
    };
  });

  const setProf = (k: string, v: string) => {
    setProfesional(prev => {
      const next = { ...prev, [k]: v };
      try {
        localStorage.setItem('vocalislab_profesional', JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const pacienteNombre = clinical.data.paciente?.nombre_completo || '';
  const pacienteTelefono = (clinical.data.paciente?.telefono || '').replace(/\D/g, '');
  const pacienteEmail = clinical.data.paciente?.email || '';

  useEffect(() => {
    if (initialExerciseIds && initialExerciseIds.length > 0) {
      setSelectedExercises(initialExerciseIds);
      setTitulo('Cuadernillo — Prescripción IA Fonoaudiológica');
    }
  }, [initialExerciseIds]);

  useEffect(() => {
    loadBank();
  }, []);

  const loadBank = async () => {
    try {
      const r = await fetch(`${BACKEND_URL}/api/ejercicios`);
      if (r.ok) {
        const data = await r.json();
        if (data.sections && data.sections.length > 0) setSections(data.sections);
        if (data.presets && data.presets.length > 0) setPresets(data.presets);
      }
    } catch {
      // DEFAULT_PRESETS and DEFAULT_SECTIONS are already present as fallbacks
    }
    try {
      const r2 = await fetch(`${BACKEND_URL}/api/ejercicios/ia?estado=pendiente`);
      if (r2.ok) setSugerencias(await r2.json());
    } catch {}
  };

  const expandirBanco = async () => {
    setExpandiendo(true);
    setExpandMsg('');
    try {
      const r = await fetch(`${BACKEND_URL}/api/ejercicios/expandir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seccion_id: seccionExpandir, cantidad: 3 }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) throw new Error(data.detail || `Error ${r.status}`);
      setExpandMsg(`${(data.creados || []).length} ejercicios sugeridos. Revisalos abajo.`);
      const r2 = await fetch(`${BACKEND_URL}/api/ejercicios/ia?estado=pendiente`);
      if (r2.ok) setSugerencias(await r2.json());
    } catch (e: any) {
      setExpandMsg(e.message || 'La IA no pudo generar ejercicios');
    }
    setExpandiendo(false);
  };

  const moderarSugerencia = async (id: string, estado: 'aprobado' | 'descartado') => {
    try {
      const fd = new FormData();
      fd.append('estado', estado);
      await fetch(`${BACKEND_URL}/api/ejercicios/ia/${id}`, { method: 'PUT', body: fd });
      setSugerencias(prev => prev.filter(s => s.id !== id));
      if (estado === 'aprobado') loadBank();
    } catch {}
  };

  const applyPreset = (presetId: string) => {
    setSelectedPreset(presetId);
    const preset = presets.find(p => p.id === presetId);
    if (preset) {
      setSelectedExercises(preset.exercise_ids);
      setSesiones(preset.sesiones_recomendadas);
      setTitulo(`Cuadernillo — ${preset.name}`);
    }
  };

  const toggleExercise = (id: string) => {
    setSelectedExercises(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
    setSelectedPreset('');
  };

  const getAllExercises = (): Exercise[] => {
    const all: Exercise[] = [];
    sections.forEach(s => s.exercises.forEach(e => all.push({ ...e, seccion_id: s.id } as Exercise)));
    return all;
  };

  const getSelectedDetails = (): Exercise[] => {
    return getAllExercises().filter(e => selectedExercises.includes(e.id));
  };

  const handleGenerate = async () => {
    if (!selectedExercises.length) {
      alert('Seleccioná al menos un ejercicio terapéutico.');
      return;
    }
    setGenerating(true);
    try {
      const selected = getSelectedDetails();
      const presetData = presets.find(p => p.id === selectedPreset);
      const contrato = {
        frecuencia: presetData?.frecuencia || '2 veces por semana',
        duracion_sesion: '30 minutos',
        pautas_ausencias: 'Avisar con 24h de anticipación.',
      };
      const fd = new FormData();
      fd.append('paciente_id', pacienteId || '');
      fd.append('titulo', titulo);
      fd.append('sesiones', String(sesiones));
      fd.append('ejercicios_json', JSON.stringify(selected));
      fd.append('contrato_json', JSON.stringify(contrato));
      fd.append('notas', notas);
      fd.append('profesional_json', JSON.stringify(profesional));

      const r = await fetch(`${BACKEND_URL}/api/cuadernillo/generar`, { method: 'POST', body: fd });
      const data = await r.json();
      if (data.ok && data.pdf_base64) {
        const bin = atob(data.pdf_base64);
        const arr = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        const blob = new Blob([arr], { type: 'application/pdf' });
        setPdfUrl(URL.createObjectURL(blob));
      } else {
        alert(data.error || 'Error generando el PDF del cuadernillo');
      }
    } catch (e) {
      alert('Error de conexión generando cuadernillo.');
    }
    setGenerating(false);
  };

  const downloadPdf = () => {
    if (!pdfUrl) return;
    const a = document.createElement('a');
    a.href = pdfUrl;
    a.download = `${titulo.replace(/\s+/g, '_')}.pdf`;
    a.click();
  };

  const mensajeClinico = () => {
    const nombre = pacienteNombre || 'paciente';
    return `Hola ${nombre}, te comparto tu ${titulo} (${sesiones} sesiones).\n\n${notas ? `Indicaciones: ${notas}\n\n` : ''}Descargá el PDF adjunto en este chat/correo y realizá los ejercicios según la dosificación indicada. Ante cualquier duda o molestia, escribime.\n\n${firmaProfesional()}`;
  };

  const compartirWhatsApp = () => {
    const base = pacienteTelefono
      ? `https://wa.me/${pacienteTelefono}?text=`
      : `https://api.whatsapp.com/send?text=`;
    window.open(base + encodeURIComponent(mensajeClinico()), '_blank');
  };

  const abrirEmailModal = () => {
    setEmailBody(mensajeClinico());
    setShowEmailModal(true);
  };

  return (
    <div className="max-w-6xl mx-auto w-full space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-indigo-900/60 via-purple-900/40 to-slate-900/80 backdrop-blur-xl border border-indigo-500/20 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="text-[10px] font-bold tracking-widest uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2.5 py-1 rounded-full">
            Terapéutica Vocal Basada en Evidencia
          </span>
          <h2 className="text-2xl font-black text-white mt-2 flex items-center gap-2">
            <FileText className="text-indigo-400" /> Prescripción de Cuadernillo Terapéutico
          </h2>
          <p className="text-xs text-gray-300 max-w-2xl mt-1">
            Presets clínicos por patología cordal y biomecánica laríngea (DMT, Nódulos, Parálisis, Presbifonía, RLF, SOVTE) adaptados según Farías (2012, 2016) y Le Huche.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerate}
            disabled={generating || selectedExercises.length === 0}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {generating ? 'Generando PDF...' : `Generar Cuadernillo (${selectedExercises.length})`}
          </button>
          {pdfUrl && (
            <>
              <button
                onClick={downloadPdf}
                className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/30 transition-all"
              >
                <Download size={16} /> Descargar PDF
              </button>
              <button
                onClick={compartirWhatsApp}
                className="px-4 py-2.5 rounded-xl bg-[#25D366] hover:bg-[#1fb857] text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-green-600/30 transition-all"
                title={pacienteTelefono ? `Enviar a ${pacienteTelefono}` : 'Compartir por WhatsApp'}
              >
                <MessageCircle size={16} /> WhatsApp
              </button>
              <button
                onClick={abrirEmailModal}
                className="px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-sky-600/30 transition-all"
                title={pacienteEmail ? `Enviar a ${pacienteEmail}` : 'Enviar por correo'}
              >
                <Mail size={16} /> Email
              </button>
            </>
          )}
        </div>
      </div>

      {/* Presets por Patología (Clinical Quick Pick) */}
      <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-gray-900 dark:text-white flex items-center gap-2 text-sm">
            <Settings size={16} className="text-indigo-500" /> Presets Clínicos por Patología Cordal ({presets.length})
          </h3>
          <span className="text-[11px] text-gray-500 dark:text-gray-400">
            Haz clic en un preset para cargar los ejercicios y dosificación recomendada
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {presets.map(p => {
            const isSelected = selectedPreset === p.id;
            return (
              <button
                key={p.id}
                onClick={() => applyPreset(p.id)}
                className={`text-left p-3.5 rounded-xl border text-xs transition-all duration-200 flex flex-col justify-between ${
                  isSelected
                    ? 'bg-indigo-600/15 border-indigo-500 text-indigo-950 dark:text-white ring-2 ring-indigo-500/30 shadow-md'
                    : 'bg-gray-50/70 dark:bg-white/[0.03] border-gray-200 dark:border-white/10 hover:border-indigo-400/50 hover:bg-indigo-50/50 dark:hover:bg-white/[0.06] text-gray-700 dark:text-gray-300'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1">
                    <p className="font-bold text-gray-900 dark:text-white text-xs">{p.name}</p>
                    {isSelected && <CheckCircle2 size={14} className="text-indigo-500 shrink-0" />}
                  </div>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 leading-snug">{p.description}</p>
                </div>
                <div className="mt-3 pt-2 border-t border-gray-200 dark:border-white/5 flex items-center justify-between text-[10px] text-gray-400">
                  <span className="font-semibold text-indigo-600 dark:text-indigo-400">{p.exercise_ids.length} ejercicios</span>
                  <span>{p.sesiones_recomendadas} ses. • {p.frecuencia}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Expansión IA del banco (Farías/Le Huche/Titze) + moderación */}
      <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-bold text-gray-900 dark:text-white text-sm flex items-center gap-2 mr-auto">
            <Sparkles size={16} className="text-purple-500" /> Expandir banco con IA
          </h3>
          <select
            value={seccionExpandir}
            onChange={e => setSeccionExpandir(e.target.value)}
            className="px-3 py-2 bg-white dark:bg-[#0b0f19] border border-gray-300 dark:border-gray-700 text-gray-800 dark:text-gray-100 rounded-xl text-xs"
          >
            {sections.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <button
            onClick={expandirBanco}
            disabled={expandiendo}
            className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-2 disabled:opacity-50"
          >
            {expandiendo ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {expandiendo ? 'Generando…' : 'Sugerir ejercicios'}
          </button>
        </div>
        <p className="text-[11px] text-gray-500 dark:text-gray-400">
          La IA propone ejercicios nuevos con fundamento Farías/Le Huche/Titze. Nada entra al
          catálogo sin tu aprobación.
        </p>
        {expandMsg && <p className="text-xs font-semibold text-purple-700 dark:text-purple-300">{expandMsg}</p>}
        {sugerencias.length > 0 && (
          <div className="space-y-2 pt-1">
            {sugerencias.map(s => (
              <div key={s.id} className="p-3 rounded-xl bg-purple-500/5 border border-purple-500/25 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-bold text-gray-900 dark:text-white">{s.name}</p>
                  <span className="text-[10px] text-purple-600 dark:text-purple-300 font-mono">{s.seccion_id}</span>
                </div>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">{s.description}</p>
                {s.fundamento && (
                  <p className="text-[10px] text-gray-400 italic">Fundamento: {s.fundamento}</p>
                )}
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => moderarSugerencia(s.id, 'aprobado')}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold"
                  >
                    Aprobar al catálogo
                  </button>
                  <button
                    onClick={() => moderarSugerencia(s.id, 'descartado')}
                    className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-300 text-[11px] font-bold"
                  >
                    Descartar
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Exercise Catalogue by Section */}
      <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm space-y-6">
        <div className="flex items-center justify-between border-b border-gray-200 dark:border-white/10 pb-3">
          <div>
            <h3 className="font-bold text-gray-900 dark:text-white text-sm">
              Catálogo de Técnicas & Ejercicios
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Personalizá la selección marcando o desmarcando los ejercicios para el paciente
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800/60">
            <span>{selectedExercises.length} seleccionados</span>
          </div>
        </div>

        {sections.map(section => (
          <div key={section.id} className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
              <p className="text-xs font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300">
                {section.name}
              </p>
              <span className="text-[10px] text-gray-400">({section.exercises.length})</span>
            </div>
            <p className="text-[11px] text-gray-500 dark:text-gray-400 -mt-1 mb-2 ml-4">
              {section.description}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 ml-1">
              {section.exercises.map(ex => {
                const checked = selectedExercises.includes(ex.id);
                return (
                  <label
                    key={ex.id}
                    className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer border transition-all ${
                      checked
                        ? 'bg-indigo-500/10 border-indigo-500/50 text-gray-900 dark:text-white'
                        : 'bg-gray-50/50 dark:bg-white/[0.02] border-gray-200 dark:border-white/5 hover:border-gray-300 dark:hover:border-white/15'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleExercise(ex.id)}
                      className="mt-1 rounded text-indigo-600 focus:ring-indigo-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-bold text-gray-900 dark:text-white truncate">{ex.name}</p>
                        {ex.duration_min && (
                          <span className="text-[10px] font-medium text-gray-400 shrink-0">{ex.duration_min} min</span>
                        )}
                      </div>
                      <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{ex.description}</p>
                      {ex.steps && ex.steps.length > 0 && (
                        <div className="mt-2 space-y-0.5 pt-1.5 border-t border-gray-100 dark:border-white/5">
                          {ex.steps.slice(0, 3).map((st, i) => (
                            <p key={i} className="text-[10px] text-gray-400 truncate">• {st}</p>
                          ))}
                          {ex.steps.length > 3 && (
                            <p className="text-[9px] text-indigo-400 font-medium">+ {ex.steps.length - 3} pasos más</p>
                          )}
                        </div>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Settings & Professional Contract Form */}
      <div className="bg-white/80 dark:bg-white/5 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-white/10 p-5 shadow-sm space-y-4">
        <h3 className="font-bold text-gray-900 dark:text-white text-sm flex items-center gap-2">
          <FileText size={16} className="text-indigo-500" /> Parámetros de Prescripción & Contrato Terapéutico
        </h3>

        {/* Membrete profesional (marca blanca del PDF) */}
        <div className="rounded-xl border border-indigo-200 dark:border-indigo-900/60 overflow-hidden">
          <button
            onClick={() => setShowMembrete(v => !v)}
            className="w-full flex items-center justify-between px-4 py-2.5 bg-indigo-50/60 dark:bg-indigo-950/30 text-xs font-bold text-indigo-800 dark:text-indigo-200"
          >
            <span>Membrete profesional del PDF (marca blanca — sin logos de plataforma)</span>
            <span className="text-indigo-500">{showMembrete ? '▲' : '▼'}</span>
          </button>
          {showMembrete && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
              {[
                { k: 'profesional_nombre', label: 'Nombre y apellido', ph: 'Lic. María García' },
                { k: 'profesional_titulo', label: 'Título profesional', ph: 'Lic. en Fonoaudiología' },
                { k: 'profesional_matricula', label: 'Matrícula (M.P.)', ph: '12345' },
                { k: 'profesional_telefono', label: 'Teléfono / WhatsApp', ph: '+54 9 ...' },
                { k: 'profesional_email', label: 'Email', ph: 'contacto@consultorio.com' },
                { k: 'profesional_instagram', label: 'Instagram / Red', ph: '@consultorio' },
                { k: 'profesional_direccion', label: 'Dirección / Consultorio', ph: 'Av. ...' },
                { k: 'profesional_logo_url', label: 'Logo (URL de imagen)', ph: 'https://...' },
              ].map(f => (
                <div key={f.k}>
                  <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">{f.label}</label>
                  <input
                    value={profesional[f.k] || ''}
                    onChange={e => setProf(f.k, e.target.value)}
                    placeholder={f.ph}
                    className="mt-1 w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              ))}
              <p className="md:col-span-2 text-[10px] text-gray-400">
                Estos datos aparecen en portada, encabezados y pie del PDF. Se guardan en este dispositivo.
              </p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">Título del Cuadernillo</label>
            <input
              value={titulo}
              onChange={e => setTitulo(e.target.value)}
              className="mt-1 w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">Número de Sesiones Planificadas</label>
            <input
              type="number"
              value={sesiones}
              onChange={e => setSesiones(parseInt(e.target.value) || 8)}
              min={1}
              max={30}
              className="mt-1 w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">Pautas Particulares y Observaciones Clínicas</label>
          <textarea
            value={notas}
            onChange={e => setNotas(e.target.value)}
            rows={3}
            placeholder="Indicaciones específicas para el paciente (p. ej., realizar la rutina SOVTE en agua 2 veces al día, suspender carraspeo, mantener hidratación de 2L/día)..."
            className="mt-1 w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700 rounded-xl text-xs font-medium text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={handleGenerate}
            disabled={generating || selectedExercises.length === 0}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50"
          >
            {generating ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {generating ? 'Compilando Cuadernillo PDF...' : 'Generar y Descargar Cuadernillo Clínico'}
          </button>
        </div>
      </div>

      {/* Modal envío por Email */}
      {showEmailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-[#111827] rounded-3xl border border-gray-200 dark:border-white/10 w-full max-w-lg shadow-2xl overflow-hidden max-h-[92dvh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-100 dark:border-white/10 flex items-center justify-between">
              <h3 className="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
                <Mail size={16} className="text-sky-500" /> Enviar cuadernillo por correo
              </h3>
              <button onClick={() => setShowEmailModal(false)} className="p-2 rounded-xl text-gray-400 hover:text-gray-600 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-white/5">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-3 text-xs">
              <div>
                <label className="font-semibold text-gray-700 dark:text-gray-300 block mb-1">
                  Destinatario{pacienteEmail ? ` (${pacienteEmail})` : ' (sin correo registrado)'}
                </label>
                <textarea
                  value={emailBody}
                  onChange={e => setEmailBody(e.target.value)}
                  rows={8}
                  className="w-full px-3 py-2 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
              <p className="text-[11px] text-amber-600 dark:text-amber-400 font-medium">
                Recordá adjuntar el PDF descargado al correo antes de enviarlo.
              </p>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => {
                    const su = encodeURIComponent(`Cuadernillo Terapéutico Vocal — ${pacienteNombre || ''}`.trim());
                    window.open(`https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(pacienteEmail)}&su=${su}&body=${encodeURIComponent(emailBody)}`, '_blank');
                  }}
                  className="px-4 py-2 rounded-xl bg-red-500 hover:bg-red-400 text-white font-bold text-xs flex items-center gap-2"
                >
                  <Send size={14} /> Abrir Gmail
                </button>
                <button
                  onClick={() => {
                    const su = encodeURIComponent(`Cuadernillo Terapéutico Vocal — ${pacienteNombre || ''}`.trim());
                    window.location.href = `mailto:${encodeURIComponent(pacienteEmail)}?subject=${su}&body=${encodeURIComponent(emailBody)}`;
                  }}
                  className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs flex items-center gap-2"
                >
                  <Mail size={14} /> App de correo
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
