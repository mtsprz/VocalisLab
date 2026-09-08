import React, { useState } from 'react';
import { Save } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props { pacienteId: string | null; }

const SCALES = {
  GRBAS: { name: 'GRBAS', items: [
    { key: 'G', label: 'Grado de disfonía', desc: '0=Normal, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'R', label: 'Rugosidad', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'B', label: 'Aspiración/Breathiness', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'A', label: 'Asthenia (debilidad)', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'S', label: 'Esfuerzo', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
  ]},
  RASATI: { name: 'RASATI', items: [
    { key: 'R', label: 'Rugosidad', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'A', label: 'Aspiración', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'S', label: 'Soplo/Airiness', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'A2', label: 'Aspereza', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'T', label: 'Tensión', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
    { key: 'I', label: 'Inestabilidad', desc: '0=Ausente, 1=Discreta, 2=Moderada, 3=Muy intensa' },
  ]},
  VHI10: { name: 'VHI-10 (Índice Handicap Vocal)', items: [
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
  ]},
  RiesgoVocal: { name: 'Evaluación de Riesgo Vocal', items: [
    { key: 'R1', label: 'Horas de uso vocal al día (0=<2h, 1=2-4h, 2=4-8h, 3=>8h)', desc: '' },
    { key: 'R2', label: 'Exposición a ruido ambiental (0=bajo, 1=moderado, 2=alto, 3=muy alto)', desc: '' },
    { key: 'R3', label: 'Humedad ambiental (0=buena, 1=moderada, 2=seca, 3=muy seca)', desc: '' },
    { key: 'R4', label: 'Ingesta de líquidos (0=mucha, 1=moderada, 1=poca, 3=muy poca)', desc: '' },
    { key: 'R5', label: 'Reflujo gastroesofágico (0=nunca, 1=a veces, 2=frecuente, 3=diario)', desc: '' },
    { key: 'R6', label: 'Tabaquismo (0=no, 1=ex-fumador, 2=fumador ocasional, 3=fumador habitual)', desc: '' },
    { key: 'R7', label: 'Tensión cervical/mandibular (0=ninguna, 1=leve, 2=moderada, 3=intensa)', desc: '' },
    { key: 'R8', label: 'Antecedentes de cirugía laríngea (0=no, 3=sí)', desc: '' },
  ]},
  TME: { name: 'Tiempo Máximo de Energía (TME)', items: [
    { key: 'TME_O', label: 'TME sostenido (segundos)', desc: '' },
    { key: 'TME_S', label: 'TME suave (segundos)', desc: '' },
  ]},
};

export default function EscalasModule({ pacienteId }: Props) {
  const [activeScale, setActiveScale] = useState<string>('GRBAS');
  const [scores, setScores] = useState<Record<string, Record<string, number>>>({
    GRBAS: { G: 0, R: 0, B: 0, A: 0, S: 0 },
    RASATI: { R: 0, A: 0, S: 0, A2: 0, T: 0, I: 0 },
    VHI10: { V1: 0, V2: 0, V3: 0, V4: 0, V5: 0, V6: 0, V7: 0, V8: 0, V9: 0, V10: 0 },
    RiesgoVocal: { R1: 0, R2: 0, R3: 0, R4: 0, R5: 0, R6: 0, R7: 0, R8: 0 },
    TME: { TME_O: 0, TME_S: 0 },
  });
  const [observaciones, setObservaciones] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const current = SCALES[activeScale as keyof typeof SCALES];

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

  const getSeverity = (total: number, max: number) => {
    const pct = max > 0 ? (total / max) * 100 : 0;
    if (pct === 0) return { label: 'Normal', color: 'text-green-600 bg-green-50' };
    if (pct <= 25) return { label: 'Leve', color: 'text-yellow-600 bg-yellow-50' };
    if (pct <= 50) return { label: 'Moderado', color: 'text-orange-600 bg-orange-50' };
    return { label: 'Severo', color: 'text-red-600 bg-red-50' };
  };

  const handleSave = async () => {
    if (!pacienteId) { alert('Seleccioná un paciente primero'); return; }
    setSaving(true);
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
      await fetch(`${BACKEND_URL}/api/evaluaciones`, { method: 'POST', body: fd });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {}
    setSaving(false);
  };

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex flex-wrap gap-2">
        {Object.entries(SCALES).map(([key, scale]) => (
          <button
            key={key}
            onClick={() => setActiveScale(key)}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeScale === key
                ? 'bg-indigo-600 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {scale.name}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800">{current.name}</h3>
          {activeScale !== 'TME' && (
            <span className={`text-sm font-medium px-3 py-1 rounded-full ${
              getSeverity(getTotal(activeScale), (current.items.length) * (activeScale === 'VHI10' || activeScale === 'RiesgoVocal' ? 4 : 3)).color
            }`}>
              {getSeverity(getTotal(activeScale), (current.items.length) * (activeScale === 'VHI10' || activeScale === 'RiesgoVocal' ? 4 : 3)).label}
              ({getTotal(activeScale)}/{(current.items.length) * (activeScale === 'VHI10' || activeScale === 'RiesgoVocal' ? 4 : 3)})
            </span>
          )}
        </div>

        <div className="space-y-4">
          {current.items.map(item => (
            <div key={item.key} className="border-b border-gray-50 pb-3">
              <p className="text-sm font-medium text-gray-700 mb-1">{item.label}</p>
              {item.desc && <p className="text-xs text-gray-400 mb-2">{item.desc}</p>}
              {activeScale === 'TME' ? (
                <input
                  type="number"
                  value={scores[activeScale]?.[item.key] || ''}
                  onChange={e => updateScore(item.key, parseFloat(e.target.value) || 0)}
                  className="w-32 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  placeholder="0"
                />
              ) : (
                <div className="flex gap-1">
                  {[0, 1, 2, 3].map(v => (
                    <button
                      key={v}
                      onClick={() => updateScore(item.key, v)}
                      className={`w-10 h-10 rounded-lg text-sm font-bold transition-colors ${
                        scores[activeScale]?.[item.key] === v
                          ? v === 0 ? 'bg-green-500 text-white' :
                            v === 1 ? 'bg-yellow-400 text-white' :
                            v === 2 ? 'bg-orange-500 text-white' :
                            'bg-red-500 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
          <div className="mt-3 p-3 bg-blue-50 rounded-lg text-sm">
            <span className="font-medium text-blue-700">Índice S/O: </span>
            <span className="text-blue-800">{(scores.TME.TME_S / scores.TME.TME_O).toFixed(2)}</span>
            <span className="text-blue-500 ml-2">(TME suave / TME sostenido)</span>
          </div>
        )}

        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 mb-1">Observaciones</label>
          <textarea
            value={observaciones}
            onChange={e => setObservaciones(e.target.value)}
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !pacienteId}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            <Save size={16} /> Guardar Evaluación
          </button>
          {saved && <span className="text-sm text-green-600">Guardado correctamente</span>}
        </div>
      </div>
    </div>
  );
}
