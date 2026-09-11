import React, { useState, useEffect, useRef } from 'react';
import { Save, AlertCircle, CheckCircle2, ChevronDown, ChevronUp, BarChart2, Shield } from 'lucide-react';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props { pacienteId: string | null; }

const RIESGO_VOCAL_FONOAR = {
  name: 'Ficha de Evaluación de Riesgo Vocal',
  dimensions: [
    {
      categoria: "Hábitos Vocales",
      items: [
        { key: "R1", label: "1. ¿Habla fuerte?" },
        { key: "R2", label: "2. ¿Es muy conversador?" },
        { key: "R3", label: "3. ¿Hace uso prolongado de la voz?" },
        { key: "R4", label: "4. ¿Habla en registro gruñidor?" },
        { key: "R5", label: "5. ¿Habla susurrando?" },
        { key: "R6", label: "6. ¿Utiliza una articulación cerrada?" },
        { key: "R7", label: "7. ¿Hace esfuerzo al hablar?" },
        { key: "R8", label: "8. ¿Habla con poco aire?" },
        { key: "R9", label: "9. ¿Hace aspiraciones ruidosas al hablar?" },
        { key: "R10", label: "10. ¿Utiliza el tipo respiratorio costal superior durante la fonación?" },
        { key: "R11", label: "11. ¿Llega sin aire al final de la frase?" },
        { key: "R12", label: "12. ¿Habla rápido, con pocas pausas?" },
        { key: "R13", label: "13. ¿Habla al mismo tiempo que los demás?" },
        { key: "R14", label: "14. ¿Habla mucho por teléfono?" },
        { key: "R15", label: "15. ¿Habla mucho al aire libre?" },
        { key: "R16", label: "16. ¿Habla mucho en ambientes ruidosos (vehículos, gimnasios, pub...)" },
        { key: "R17", label: "17. ¿Carraspea en forma habitual?" },
        { key: "R18", label: "18. ¿Ríe en reversión de la fonación?" },
        { key: "R19", label: "19. ¿Grita con frecuencia?" },
        { key: "R20", label: "20. ¿Grita en forma repentina y violenta?" },
        { key: "R21", label: "21. ¿Imita voces?" },
        { key: "R22", label: "22. ¿Canta?" },
        { key: "R23", label: "23. ¿Canta mientras ejecuta instrumentos musicales?" },
        { key: "R24", label: "24. ¿Imita ruidos o sonidos?" },
        { key: "R25", label: "25. ¿Hábito mientras su cuerpo adopta múltiples posturas?" },
        { key: "R26", label: "26. ¿Usa la voz en forma habitual a pesar de estar cursando procesos respiratorios patológicos?" },
        { key: "R27", label: "27. ¿Usa la voz luego de una ingesta abundante?" },
        { key: "R28", label: "28. ¿Usa la voz después de exposiciones solares?" },
        { key: "R29", label: "29. ¿Hace uso intenso de la voz matinal?" },
        { key: "R30", label: "30. ¿Utiliza la voz estando su interlocutor a distancia?" },
        { key: "R31", label: "31. ¿Practica deporte en los cuales utilice la voz?" },
        { key: "R32", label: "32. ¿Integra grupos religiosos que exigen gran uso de la voz?" }
      ]
    },
    {
      categoria: "Estado Emocional",
      items: [
        { key: "R33", label: "1. ¿Tiene preocupaciones económicas?" },
        { key: "R34", label: "2. ¿Tiene conflictos afectivos de orden personal o familiar?" },
        { key: "R35", label: "3. ¿Trabaja en situaciones conflictivas?" },
        { key: "R36", label: "4. ¿Es emocionalmente hiperreactivo?" },
        { key: "R37", label: "5. ¿Es emocionalmente reprimido?" },
        { key: "R38", label: "6. ¿Tiene un temperamento dominante y agresivo?" },
        { key: "R39", label: "7. ¿Se siente afectado por los problemas de los otros?" }
      ]
    },
    {
      categoria: "Condiciones Biológicas Desfavorables",
      items: [
        { key: "R40", label: "1. ¿Padece de alguna afección que disminuya su capacidad respiratoria?" },
        { key: "R41", label: "2. ¿Es respirador bucal?" },
        { key: "R42", label: "3. ¿Sufre procesos infecciosos o alérgicos en las vías aéreas?" },
        { key: "R43", label: "4. ¿Tiene tos?" },
        { key: "R44", label: "5. ¿Tiene problemas auditivos?" },
        { key: "R45", label: "6. ¿Tiene RGE o acidez gástrica?" },
        { key: "R46", label: "7. ¿Es estreñido?" },
        { key: "R47", label: "8. ¿Tiene problemas posturales?" },
        { key: "R48", label: "9. ¿Siempre tuvo una voz poco clara?" },
        { key: "R49", label: "10. ¿Se pone ronco con facilidad después de esfuerzo vocal: campamentos, fiestas, etc.?" },
        { key: "R50", label: "11. ¿Tiene antecedentes de ronquera en familiares?" },
        { key: "R51", label: "12. ¿Tiene rigidez corporal, falta de flexibilidad?" }
      ]
    },
    {
      categoria: "Condiciones Ambientales Desfavorables",
      items: [
        { key: "R52", label: "1. ¿Permanece en ambientes con aire acondicionado o calefacción?" },
        { key: "R53", label: "2. ¿Permanece en ambientes con polvo, humedad o poca ventilación?" },
        { key: "R54", label: "3. ¿Comparte lugares con fumadores?" },
        { key: "R55", label: "4. ¿Vive en un ambiente familiar ruidoso?" },
        { key: "R56", label: "5. ¿Trabaja en ambiente ruidoso?" },
        { key: "R57", label: "6. ¿Está expuesto a ruidos intensos?" },
        { key: "R58", label: "7. ¿Convive o trabaja con personas con problemas auditivos?" }
      ]
    },
    {
      categoria: "Hábitos de Vida",
      items: [
        { key: "R59", label: "1. ¿Se expone a cambios bruscos de temperatura?" },
        { key: "R60", label: "2. ¿Duerme poco?" },
        { key: "R61", label: "3. La cantidad de líquido necesaria para un profesional de la voz es de 3 litros. ¿Ud. bebe poco?" },
        { key: "R62", label: "4. ¿Ingiere alimentos picantes?" },
        { key: "R63", label: "5. ¿Bebe café o té en exceso?" },
        { key: "R64", label: "6. ¿Ingiere bebidas heladas o muy calientes?" },
        { key: "R65", label: "7. ¿Consume drogas?" },
        { key: "R66", label: "8. ¿Ingiere alcohol?" },
        { key: "R67", label: "9. ¿Fuma tabaco?" },
        { key: "R68", label: "10. ¿Usa ropa ajustada?" },
        { key: "R69", label: "11. ¿Practica deportes violentos?" }
      ]
    }
  ]
};

const SCALES = {
  GRBAS: {
    name: 'GRBAS',
    items: [
      { key: 'G', label: 'Grado de disfonía', desc: '0=Normal, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'R', label: 'Rugosidad', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'B', label: 'Aspiración/Breathiness', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'A', label: 'Asthenia (debilidad)', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'S', label: 'Esfuerzo', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    ]
  },
  RASATI: {
    name: 'RASATI',
    items: [
      { key: 'R', label: 'Rugosidad', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'A', label: 'Aspiración', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'S', label: 'Soplo/Airiness', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'A2', label: 'Aspereza', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'T', label: 'Tensión', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
      { key: 'I', label: 'Inestabilidad', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    ]
  },
  VHI10: {
    name: 'VHI-10 (Índice Handicap Vocal)',
    items: [
      { key: 'V1', label: 'Mi voz me dificulta hacerme entender', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V2', label: 'Siento que tengo que esforzarme para hablar', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V3', label: 'La gente no me entiende cuando hablo', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V4', label: 'Mi voz me limita vida personal y social', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V5', label: 'Me siento cohibido cuando hablo', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V6', label: 'Pierdo el control de mi voz', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V7', label: 'Tengo dificultades para proyectar mi voz', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V8', label: 'Mi voz suena débil', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V9', label: 'La gente me pide repetir lo que digo', desc: '0=Nunca ... 4=Siempre' },
      { key: 'V10', label: 'Mi voz se cansa al hablar', desc: '0=Nunca ... 4=Siempre' },
    ]
  },
  TME: {
    name: 'Tiempo Máximo de Energía (TME)',
    items: [
      { key: 'TME_O', label: 'TME sostenido (segundos)', desc: '' },
      { key: 'TME_S', label: 'TME suave (segundos)', desc: '' },
    ]
  },
};

export default function EscalasModule({ pacienteId }: Props) {
  const clinical = useClinical();
  const [activeScale, setActiveScale] = useState<string>('GRBAS');
  const [activeDimensionIndex, setActiveDimensionIndex] = useState<number>(0);
  
  const [scores, setScores] = useState<Record<string, Record<string, number>>>(() => {
    // Initialize risk keys R1 to R69 with 0
    const initialRisk: Record<string, number> = {};
    for (let i = 1; i <= 69; i++) {
      initialRisk[`R${i}`] = 0;
    }
    return {
      GRBAS: { G: 0, R: 0, B: 0, A: 0, S: 0 },
      RASATI: { R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 },
      VHI10: { V1: 0, V2: 0, V3: 0, V4: 0, V5: 0, V6: 0, V7: 0, V8: 0, V9: 0, V10: 0 },
      RiesgoVocal: initialRisk,
      TME: { TME_O: 0, TME_S: 0 },
    };
  });

  const [observaciones, setObservaciones] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [evolucion, setEvolucion] = useState<any[]>([]);

  const blankScores = () => {
    const initialRisk: Record<string, number> = {};
    for (let i = 1; i <= 69; i++) {
      initialRisk[`R${i}`] = 0;
    }
    return {
      GRBAS: { G: 0, R: 0, B: 0, A: 0, S: 0 },
      RASATI: { R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 },
      VHI10: { V1: 0, V2: 0, V3: 0, V4: 0, V5: 0, V6: 0, V7: 0, V8: 0, V9: 0, V10: 0 },
      RiesgoVocal: initialRisk,
      TME: { TME_O: 0, TME_S: 0 },
    };
  };

  const aplicadaRef = useRef(-1);

  // Reset total al cambiar de paciente
  useEffect(() => {
    setScores(blankScores());
    setObservaciones('');
    setSaveError('');
    setSaved(false);
    aplicadaRef.current = -1;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pacienteId]);

  // Hidrata una vez por hidratación del contexto (última evaluación del backend)
  useEffect(() => {
    if (clinical.cargaToken === aplicadaRef.current) return;
    if (pacienteId && clinical.data.paciente?.id !== pacienteId) return;
    aplicadaRef.current = clinical.cargaToken;
    const esc = clinical.data.escalas || {};
    const rv = clinical.data.riesgoVocal || {};
    setScores(prev => ({
      ...blankScores(),
      GRBAS: { ...prev.GRBAS, ...(esc.grbas || {}) },
      RASATI: { ...prev.RASATI, ...(esc.rasati || {}) },
      VHI10: { ...prev.VHI10, ...(esc.vhi10_detalle || {}) },
      RiesgoVocal: { ...prev.RiesgoVocal, ...(rv.detalle || {}) },
      TME: {
        TME_O: esc.tme_o ?? esc.tme ?? 0,
        TME_S: esc.tme_s ?? esc.tme_segundos ?? 0,
      },
    }));
    if (esc.observaciones) setObservaciones(esc.observaciones);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clinical.cargaToken]);

  // Historial de evaluaciones para comparar basal vs. reevaluación (sesión 8)
  useEffect(() => {
    if (!pacienteId) { setEvolucion([]); return; }
    (async () => {
      try {
        const r = await fetch(`${BACKEND_URL}/api/evaluaciones?paciente_id=${pacienteId}&limit=50`);
        if (r.ok) {
          const arr = await r.json();
          if (Array.isArray(arr)) {
            setEvolucion([...arr].sort((a, b) =>
              new Date(a.fecha).getTime() - new Date(b.fecha).getTime()));
          }
        }
      } catch {}
    })();
  }, [pacienteId, saved]);

  // Sync escalas data to global clinical context
  useEffect(() => {
    const riesgoTotal = getTotal('RiesgoVocal');
    const subtotales: Record<string, number> = {};
    RIESGO_VOCAL_FONOAR.dimensions.forEach(dim => {
      subtotales[dim.categoria] = dim.items.reduce((acc, it) => acc + (scores.RiesgoVocal[it.key] || 0), 0);
    });
    const alertas3 = RIESGO_VOCAL_FONOAR.dimensions.flatMap(d => d.items)
      .filter(it => (scores.RiesgoVocal[it.key] || 0) === 3)
      .map(it => it.label);

    clinical.setEscalas({
      grbas: scores.GRBAS,
      rasati: scores.RASATI,
      vhi10_score: getTotal('VHI10'),
      vhi10_detalle: scores.VHI10,
      tme_o: scores.TME.TME_O,
      tme_s: scores.TME.TME_S,
      indice_so: scores.TME.TME_O > 0 ? (scores.TME.TME_S / scores.TME.TME_O).toFixed(2) : null,
    });
    clinical.setRiesgoVocal({
      puntaje_total: riesgoTotal,
      grupo: riesgoTotal <= 60 ? 'Grupo 1 (Mínimo)' : riesgoTotal <= 90 ? 'Grupo 2 (Elevado)' : 'Grupo 3 (Muy Elevado)',
      subtotales_dimensiones: subtotales,
      alertas_conductas_3: alertas3,
      detalle: scores.RiesgoVocal,
    });
    if (riesgoTotal > 0) {
      clinical.markStep('escalas');
    }
  }, [scores]);

  const updateScore = (key: string, val: number) => {
    setScores(prev => ({
      ...prev,
      [activeScale]: { ...prev[activeScale], [key]: val },
    }));
  };

  const getTotal = (scale: string) => {
    const s = scores[scale];
    if (!s) return 0;
    return Object.values(s).reduce((a, b) => a + b, 0);
  };

  const getRiesgoVocalInterpretation = (total: number) => {
    if (total <= 60) {
      return {
        label: 'Grupo 1 (Mínimo)',
        color: 'text-green-700 bg-green-50 border-green-200 dark:bg-green-950/30 dark:text-green-400 dark:border-green-900',
        diagnostico: "Riesgo vocal mínimo. Conoce y respeta los límites de su sistema fonatorio. Si presenta alteración, probablemente sea de origen orgánico e independiente del uso vocal."
      };
    } else if (total <= 90) {
      return {
        label: 'Grupo 2 (Elevado)',
        color: 'text-amber-700 bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900',
        diagnostico: "Tendencia a desarrollar problema de voz elevada. Probable presencia de síntomas o cuadro funcional instalado. Revisar ítems con alto puntaje (3) y controlar semanalmente."
      };
    } else {
      return {
        label: 'Grupo 3 (Muy Elevado)',
        color: 'text-red-700 bg-red-50 border-red-200 dark:bg-red-950/30 dark:text-red-400 dark:border-red-900',
        diagnostico: "Riesgo vocal muy elevado. Probable problema funcional crónico. Necesidad imperiosa de modificar conductas con puntaje elevado. Control diario de descenso de puntaje."
      };
    }
  };

  const getSeverity = (total: number, max: number) => {
    const pct = max > 0 ? (total / max) * 100 : 0;
    if (pct === 0) return { label: 'Normal', color: 'text-green-600 bg-green-50 dark:bg-green-950/30 dark:text-green-400' };
    if (pct <= 25) return { label: 'Leve', color: 'text-yellow-600 bg-yellow-50 dark:bg-yellow-950/30 dark:text-yellow-400' };
    if (pct <= 50) return { label: 'Moderado', color: 'text-orange-600 bg-orange-50 dark:bg-orange-950/30 dark:text-orange-400' };
    return { label: 'Severo', color: 'text-red-600 bg-red-50 dark:bg-red-950/30 dark:text-red-400' };
  };

  const handleSave = async () => {
    if (!pacienteId) { alert('Seleccioná un paciente primero'); return; }
    setSaving(true);
    setSaveError('');
    try {
      const fd = new FormData();
      fd.append('paciente_id', pacienteId);
      fd.append('grbas', JSON.stringify(scores.GRBAS));
      fd.append('rasati', JSON.stringify(scores.RASATI));
      fd.append('vhi10_score', String(getTotal('VHI10')));
      fd.append('vhi10_detalle', JSON.stringify(scores.VHI10));
      fd.append('riesgo_vocal_score', String(getTotal('RiesgoVocal')));
      fd.append('riesgo_vocal_detalle', JSON.stringify(scores.RiesgoVocal));
      fd.append('tme_o', String(scores.TME.TME_O || ''));
      fd.append('tme_s', String(scores.TME.TME_S || ''));
      fd.append('observaciones', observaciones);
      const f0conv = clinical.data.acustica?.f0_mean;
      fd.append('f0_conversacional_hz', f0conv != null ? String(f0conv) : '');
      const autoVoz = clinical.data.anamnesis?.autopercepcion_voz;
      fd.append('autopercepcion_vocal', autoVoz != null ? String(autoVoz) : '');
      const r = await fetch(`${BACKEND_URL}/api/evaluaciones`, { method: 'POST', body: fd });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || `Error del servidor (${r.status})`);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setSaveError(e.message || 'No se pudo guardar la evaluación');
    }
    setSaving(false);
  };

  // Progress for RiesgoVocal
  const getRiesgoProgress = () => {
    const s = scores.RiesgoVocal || {};
    const answered = Object.values(s).filter(v => v !== undefined).length;
    return {
      answered,
      total: 69,
      pct: Math.round((answered / 69) * 100)
    };
  };

  const renderEvolucion = () => {
    if (evolucion.length === 0) return null;
    const basal = evolucion[0];
    const actual = evolucion[evolucion.length - 1];
    const esReevaluacion = evolucion.length >= 2;
    const num = (v: any) => (v == null || v === '' || isNaN(Number(v)) ? null : Number(v));
    const rows = [
      {
        metrica: 'Autopercepción voz (0-10)',
        b: num(basal.autopercepcion_vocal), a: num(actual.autopercepcion_vocal),
        mejorSiSube: true,
      },
      {
        metrica: 'VHI-10 (0-40)',
        b: num(basal.vhi10_score), a: num(actual.vhi10_score),
        mejorSiSube: false,
      },
      {
        metrica: 'Riesgo vocal (/207)',
        b: num(basal.riesgo_vocal_score), a: num(actual.riesgo_vocal_score),
        mejorSiSube: false,
      },
      {
        metrica: 'F0 conversacional (Hz)',
        b: num(basal.f0_conversacional_hz), a: num(actual.f0_conversacional_hz),
        mejorSiSube: null,
      },
    ];
    const conDatos = rows.filter(r => r.b != null || r.a != null);
    if (conDatos.length === 0) return null;

    // Pronóstico: autopercepción manda, VHI acompaña
    const dAuto = (rows[0].a != null && rows[0].b != null) ? rows[0].a! - rows[0].b! : null;
    const dVhi = (rows[1].a != null && rows[1].b != null) ? rows[1].b! - rows[1].a! : null;
    let pronostico = null;
    if (esReevaluacion) {
      if ((dAuto != null && dAuto >= 2) || (dVhi != null && dVhi >= 6)) {
        pronostico = {
          label: 'Buen pronóstico: respuesta terapéutica favorable',
          cls: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300',
        };
      } else if ((dAuto != null && dAuto <= -2) || (dVhi != null && dVhi <= -6)) {
        pronostico = {
          label: 'Revisar plan terapéutico: sin mejoría o empeoramiento',
          cls: 'bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-300',
        };
      } else {
        pronostico = {
          label: 'Cuadro estable: sostener plan y reevaluar',
          cls: 'bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300',
        };
      }
    }

    const fmtDelta = (r: any) => {
      if (r.a == null || r.b == null) return '—';
      const d = Math.round((r.a - r.b) * 10) / 10;
      if (d === 0) return '±0';
      const signo = d > 0 ? '+' : '';
      const bueno = r.mejorSiSube == null ? null : (r.mejorSiSube ? d > 0 : d < 0);
      const color = bueno == null ? 'text-gray-500' : bueno ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400';
      return <span className={`font-bold ${color}`}>{signo}{d}</span>;
    };

    return (
      <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900 bg-indigo-50/50 dark:bg-indigo-950/20 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-bold text-indigo-800 dark:text-indigo-200">
            Evolución terapéutica: basal vs. actual ({evolucion.length} evaluación{evolucion.length > 1 ? 'es' : ''})
          </span>
          {!esReevaluacion && (
            <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-100 dark:bg-indigo-900/40 px-2 py-0.5 rounded-full">
              Basal registrado — reevaluar en sesión 8
            </span>
          )}
        </div>
        <div className="hidden sm:grid grid-cols-4 gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 pb-1">
          <span>Métrica</span><span className="text-right">Basal</span>
          <span className="text-right">Actual</span><span className="text-right">Δ</span>
        </div>
        {conDatos.map(r => (
          <div key={r.metrica} className="grid grid-cols-3 sm:grid-cols-4 gap-x-2 gap-y-0.5 text-xs py-1.5 border-t border-indigo-100 dark:border-indigo-900/50">
            <span className="col-span-3 sm:col-span-1 font-medium text-gray-700 dark:text-gray-300">{r.metrica}</span>
            <span className="text-left sm:text-right font-mono text-gray-600 dark:text-gray-400"><span className="sm:hidden text-gray-400">Basal: </span>{r.b ?? '—'}</span>
            <span className="text-left sm:text-right font-mono font-bold text-gray-900 dark:text-white"><span className="sm:hidden text-gray-400 font-medium">Actual: </span>{r.a ?? '—'}</span>
            <span className="text-right font-mono">{fmtDelta(r)}</span>
          </div>
        ))}
        {pronostico && (
          <div className={`mt-2 p-2.5 rounded-lg border text-xs font-bold ${pronostico.cls}`}>
            {pronostico.label}
          </div>
        )}
      </div>
    );
  };

  const renderRiesgoVocal = () => {
    const total = getTotal('RiesgoVocal');
    const interpretation = getRiesgoVocalInterpretation(total);
    const progress = getRiesgoProgress();

    return (
      <div className="space-y-6">
        {/* Header Clinical Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#111827] shadow-sm flex flex-col justify-center">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1">Puntaje Total Riesgo Vocal</span>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-extrabold text-indigo-600 dark:text-indigo-400">{total}</span>
              <span className="text-sm font-medium text-gray-400">/ 207 pts</span>
            </div>
          </div>
          <div className={`p-4 rounded-xl border ${interpretation.color} shadow-sm md:col-span-2 flex flex-col justify-center`}>
            <div className="flex items-center gap-2 mb-1.5">
              <Shield size={18} className="text-indigo-500 dark:text-indigo-400" />
              <span className="text-sm font-bold uppercase tracking-wide">Clasificación: {interpretation.label}</span>
            </div>
            <p className="text-xs leading-relaxed font-medium">{interpretation.diagnostico}</p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#111827] shadow-sm">
          <div className="flex justify-between items-center mb-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400">
            <span>Progreso de la ficha</span>
            <span>{progress.answered} de {progress.total} ítems completados ({progress.pct}%)</span>
          </div>
          <div className="w-full bg-gray-100 dark:bg-gray-800 h-2 rounded-full overflow-hidden">
            <div className="bg-indigo-600 dark:bg-indigo-500 h-full transition-all duration-300" style={{ width: `${progress.pct}%` }} />
          </div>
        </div>

        {/* Navigation Category Tabs */}
        <div className="flex flex-wrap gap-1.5 border-b border-gray-100 dark:border-gray-800 pb-2">
          {RIESGO_VOCAL_FONOAR.dimensions.map((dim, idx) => {
            // Count items in this dimension
            const dimItems = dim.items;
            const dimScore = dimItems.reduce((acc, it) => acc + (scores.RiesgoVocal[it.key] || 0), 0);
            return (
              <button
                key={dim.categoria}
                onClick={() => setActiveDimensionIndex(idx)}
                className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                  activeDimensionIndex === idx
                    ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/10'
                    : 'bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/80'
                }`}
              >
                {dim.categoria}
                <span className={`ml-2 px-1.5 py-0.5 rounded text-[10px] ${
                  activeDimensionIndex === idx ? 'bg-indigo-700 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
                }`}>
                  {dimScore} pts
                </span>
              </button>
            );
          })}
        </div>

        {/* Items Listing for current Dimension */}
        <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <h4 className="font-bold text-gray-800 dark:text-white">{RIESGO_VOCAL_FONOAR.dimensions[activeDimensionIndex].categoria}</h4>
            <span className="text-xs font-semibold text-gray-400">Total Dimensión: {
              RIESGO_VOCAL_FONOAR.dimensions[activeDimensionIndex].items.reduce((acc, it) => acc + (scores.RiesgoVocal[it.key] || 0), 0)
            } pts</span>
          </div>

          <div className="grid grid-cols-1 gap-4 max-h-[500px] overflow-y-auto pr-2">
            {RIESGO_VOCAL_FONOAR.dimensions[activeDimensionIndex].items.map((item, index) => {
              const currentVal = scores.RiesgoVocal[item.key] || 0;
              return (
                <div key={item.key} className="flex flex-col md:flex-row md:items-center justify-between py-3 border-b border-gray-100 dark:border-gray-800 last:border-b-0 gap-3">
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">{item.label}</p>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {[
                      { val: 0, lbl: "0", desc: "Nada, nunca" },
                      { val: 1, lbl: "1", desc: "Poco, a veces" },
                      { val: 2, lbl: "2", desc: "Bastante, a menudo" },
                      { val: 3, lbl: "3", desc: "Mucho, siempre" }
                    ].map(opt => (
                      <button
                        key={opt.val}
                        onClick={() => updateScore(item.key, opt.val)}
                        title={opt.desc}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          currentVal === opt.val
                            ? opt.val === 0 ? 'bg-green-500 text-white' :
                              opt.val === 1 ? 'bg-yellow-400 dark:bg-yellow-500 text-white' :
                              opt.val === 2 ? 'bg-orange-500 text-white' :
                              'bg-red-500 text-white'
                            : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400'
                        }`}
                      >
                        {opt.lbl}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Dimension Pagination Buttons */}
          <div className="flex justify-between pt-4 border-t border-gray-100 dark:border-gray-800">
            <button
              disabled={activeDimensionIndex === 0}
              onClick={() => setActiveDimensionIndex(p => p - 1)}
              className="px-4 py-2 text-xs font-bold border border-gray-200 dark:border-gray-800 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
            >
              Anterior Dimensión
            </button>
            <button
              disabled={activeDimensionIndex === RIESGO_VOCAL_FONOAR.dimensions.length - 1}
              onClick={() => setActiveDimensionIndex(p => p + 1)}
              className="px-4 py-2 text-xs font-bold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              Siguiente Dimensión
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto w-full space-y-4">
      {/* Scale Switcher Tabs */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(SCALES).map(([key, scale]) => (
          <button
            key={key}
            onClick={() => setActiveScale(key)}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeScale === key
                ? 'bg-indigo-600 text-white'
                : 'bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/80'
            }`}
          >
            {scale.name}
          </button>
        ))}
        {/* Replaced RiesgoVocal Option tab */}
        <button
          onClick={() => setActiveScale('RiesgoVocal')}
          className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeScale === 'RiesgoVocal'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white dark:bg-[#111827] border border-gray-200 dark:border-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/80'
          }`}
        >
          Riesgo Vocal
        </button>
      </div>

      {/* Evolución terapéutica basal vs. actual (todas las pestañas) */}
      {renderEvolucion()}

      {activeScale === 'RiesgoVocal' ? (
        renderRiesgoVocal()
      ) : (
        <div className="bg-white dark:bg-[#111827] rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm transition-all duration-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800 dark:text-white">{(SCALES as any)[activeScale].name}</h3>
            {activeScale !== 'TME' && (
              <span className={`text-sm font-medium px-3 py-1 rounded-full ${
                getSeverity(getTotal(activeScale), ((SCALES as any)[activeScale].items.length) * (activeScale === 'VHI10' ? 4 : 3)).color
              }`}>
                {getSeverity(getTotal(activeScale), ((SCALES as any)[activeScale].items.length) * (activeScale === 'VHI10' ? 4 : 3)).label}
                ({getTotal(activeScale)}/{((SCALES as any)[activeScale].items.length) * (activeScale === 'VHI10' ? 4 : 3)})
              </span>
            )}
          </div>

          <div className="space-y-4">
            {(SCALES as any)[activeScale].items.map((item: any) => (
              <div key={item.key} className="border-b border-gray-50 dark:border-gray-800/50 pb-3 last:border-0 last:pb-0">
                <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">{item.label}</p>
                {item.desc && <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">{item.desc}</p>}
                {activeScale === 'TME' ? (
                  <input
                    type="number"
                    value={scores[activeScale]?.[item.key] || ''}
                    onChange={e => updateScore(item.key, parseFloat(e.target.value) || 0)}
                    className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="0"
                  />
                ) : (
                  <div className="flex gap-1">
                    {[0, 1, 2, 3, ...(activeScale === 'VHI10' ? [4] : [])].map(v => (
                      <button
                        key={v}
                        onClick={() => updateScore(item.key, v)}
                        className={`w-10 h-10 rounded-lg text-sm font-bold transition-colors ${
                          scores[activeScale]?.[item.key] === v
                            ? v === 0 ? 'bg-green-500 text-white' :
                              v === 1 ? 'bg-yellow-400 text-white' :
                              v === 2 ? 'bg-orange-500 text-white' :
                              v === 3 ? 'bg-red-500 text-white' :
                              'bg-purple-600 text-white'
                            : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                        }`}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {activeScale === 'TME' && scores.TME.TME_O > 0 && scores.TME.TME_S > 0 && (
            <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900 rounded-lg text-sm">
              <span className="font-medium text-blue-700 dark:text-blue-400">Índice S/O: </span>
              <span className="text-blue-800 dark:text-blue-300">{(scores.TME.TME_S / scores.TME.TME_O).toFixed(2)}</span>
              <span className="text-blue-500 dark:text-blue-500 ml-2">(TME suave / TME sostenido)</span>
            </div>
          )}
        </div>
      )}

      {/* Observations Box */}
      <div className="bg-white dark:bg-[#111827] rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm transition-all duration-200">
        <label className="block text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Observaciones Clínicas Generales</label>
        <textarea
          value={observaciones}
          onChange={e => setObservaciones(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#0b0f19] text-gray-800 dark:text-gray-100 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          placeholder="Escriba aquí cualquier observación pertinente..."
        />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !pacienteId}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-all shadow-md shadow-indigo-600/10 active:scale-95"
          >
            <Save size={16} /> Guardar Evaluación
          </button>
          {saved && <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1 font-medium"><CheckCircle2 size={16} /> Guardado correctamente</span>}
          {saveError && <span className="text-sm text-red-600 dark:text-red-400 flex items-center gap-1 font-medium"><AlertCircle size={16} /> {saveError}</span>}
          {!pacienteId && <span className="text-sm text-amber-600 dark:text-amber-400 flex items-center gap-1 font-medium"><AlertCircle size={16} /> Seleccione un paciente en la barra lateral para guardar</span>}
        </div>
      </div>
    </div>
  );
}