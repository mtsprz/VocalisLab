import React, { useState, useEffect } from 'react';
import { Edit3, Save, Undo2, Redo2, Eye, Lock, Unlock, User, Clock, FileText } from 'lucide-react';

interface ReportField {
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'readonly';
  source: 'patient' | 'praat' | 'voxplot' | 'manual' | 'ai' | 'system';
  value: string;
}

interface ReportVersion {
  id: string;
  timestamp: string;
  author: string;
  fields: ReportField[];
  locked: boolean;
}

interface ReportEditorProps {
  patientData: any;
  metrics: any;
  aiText: string;
  voxPlotData?: any;
  onSave: (fields: ReportField[], author: string) => void;
  onExport: (fields: ReportField[]) => void;
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  patient: { label: 'Paciente', color: 'bg-sky-500/20 text-sky-300' },
  praat: { label: 'Praat', color: 'bg-purple-500/20 text-purple-300' },
  voxplot: { label: 'VOXplot', color: 'bg-amber-500/20 text-amber-300' },
  manual: { label: 'Manual', color: 'bg-slate-700 text-slate-300' },
  ai: { label: 'IA', color: 'bg-cyan-500/20 text-cyan-300' },
  system: { label: 'Sistema', color: 'bg-emerald-500/20 text-emerald-300' },
};

function buildFields(patientData: any, metrics: any, aiText: string, voxPlotData?: any): ReportField[] {
  const fields: ReportField[] = [
    { key: 'nombre', label: 'Nombre del paciente', type: 'text', source: 'patient', value: patientData?.nombre || '' },
    { key: 'dni', label: 'DNI / Documento', type: 'text', source: 'patient', value: patientData?.dni || '' },
    { key: 'edad', label: 'Edad', type: 'text', source: 'patient', value: patientData?.edad || '' },
    { key: 'sexo', label: 'Sexo', type: 'text', source: 'patient', value: patientData?.sexo || '' },
    { key: 'motivo', label: 'Motivo de consulta', type: 'textarea', source: 'patient', value: patientData?.motivo || '' },
    { key: 'derivador', label: 'Derivador', type: 'text', source: 'patient', value: patientData?.derivador || '' },
    { key: 'f0_mean', label: 'F0 media (Hz)', type: 'readonly', source: 'praat', value: String(metrics?.f0_mean ?? 'N/D') },
    { key: 'f0_min', label: 'F0 mínima (Hz)', type: 'readonly', source: 'praat', value: String(metrics?.f0_min ?? 'N/D') },
    { key: 'f0_max', label: 'F0 máxima (Hz)', type: 'readonly', source: 'praat', value: String(metrics?.f0_max ?? 'N/D') },
    { key: 'jitter_pct', label: 'Jitter local (%)', type: 'readonly', source: 'praat', value: String(metrics?.jitter_pct ?? 'N/D') },
    { key: 'shimmer_pct', label: 'Shimmer local (%)', type: 'readonly', source: 'praat', value: String(metrics?.shimmer_pct ?? 'N/D') },
    { key: 'shimmer_db', label: 'Shimmer (dB)', type: 'readonly', source: 'praat', value: String(metrics?.shimmer_db ?? 'N/D') },
    { key: 'hnr_db', label: 'HNR (dB)', type: 'readonly', source: 'praat', value: String(metrics?.hnr_db ?? 'N/D') },
    { key: 'cpps_db', label: 'CPPS (dB)', type: 'readonly', source: 'praat', value: String(metrics?.cpps_db ?? 'N/D') },
    { key: 'avqi', label: 'AVQI v03.01', type: 'readonly', source: 'praat', value: String(metrics?.avqi ?? 'N/D') },
    { key: 'descripcion_tarea', label: 'Descripción de la tarea vocal', type: 'textarea', source: 'manual', value: '' },
    { key: 'anamnesis', label: 'Anamnesis resumida', type: 'textarea', source: 'manual', value: '' },
    { key: 'interpretacion', label: 'Interpretación clínica', type: 'textarea', source: 'manual', value: '' },
    { key: 'calidad_audio', label: 'Observaciones sobre calidad de audio', type: 'textarea', source: 'manual', value: '' },
    { key: 'conclusion', label: 'Conclusión', type: 'textarea', source: 'manual', value: '' },
    { key: 'recomendaciones', label: 'Recomendaciones', type: 'textarea', source: 'manual', value: '' },
    { key: 'advertencias', label: 'Advertencias', type: 'textarea', source: 'manual', value: '' },
    { key: 'sintesis_ia', label: 'Texto generado por IA', type: 'textarea', source: 'ai', value: aiText || '' },
  ];
  return fields;
}

export default function ReportEditor({ patientData, metrics, aiText, voxPlotData, onSave, onExport }: ReportEditorProps) {
  const [fields, setFields] = useState<ReportField[]>(() => buildFields(patientData, metrics, aiText, voxPlotData));
  const [history, setHistory] = useState<ReportField[][]>([fields]);
  const [historyIdx, setHistoryIdx] = useState(0);
  const [author, setAuthor] = useState('');
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [showDiff, setShowDiff] = useState(false);
  const [locked, setLocked] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setFields(buildFields(patientData, metrics, aiText, voxPlotData));
  }, [patientData, metrics, aiText, voxPlotData]);

  const updateField = (key: string, value: string) => {
    if (locked[key]) return;
    const newFields = fields.map(f => f.key === key ? { ...f, value } : f);
    setFields(newFields);
    const newHistory = history.slice(0, historyIdx + 1);
    newHistory.push(newFields);
    setHistory(newHistory);
    setHistoryIdx(newHistory.length - 1);
  };

  const undo = () => {
    if (historyIdx > 0) {
      setHistoryIdx(historyIdx - 1);
      setFields(history[historyIdx - 1]);
    }
  };

  const redo = () => {
    if (historyIdx < history.length - 1) {
      setHistoryIdx(historyIdx + 1);
      setFields(history[historyIdx + 1]);
    }
  };

  const saveVersion = () => {
    const ver: ReportVersion = {
      id: `v${versions.length + 1}_${Date.now()}`,
      timestamp: new Date().toISOString(),
      author: author || 'Sin autor',
      fields: [...fields],
      locked: false,
    };
    setVersions([...versions, ver]);
    onSave(fields, author);
  };

  const groupedFields = {
    patient: fields.filter(f => f.source === 'patient'),
    praat: fields.filter(f => f.source === 'praat'),
    manual: fields.filter(f => f.source === 'manual'),
    ai: fields.filter(f => f.source === 'ai'),
    system: fields.filter(f => f.source === 'system'),
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Edit3 className="w-5 h-5 text-sky-400" />
          <h2 className="text-lg font-bold text-slate-100">Editor de Informe</h2>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={undo} disabled={historyIdx <= 0} className="p-1.5 hover:bg-slate-800 rounded-lg disabled:opacity-30 transition-colors" title="Deshacer">
            <Undo2 className="w-4 h-4 text-slate-400" />
          </button>
          <button onClick={redo} disabled={historyIdx >= history.length - 1} className="p-1.5 hover:bg-slate-800 rounded-lg disabled:opacity-30 transition-colors" title="Rehacer">
            <Redo2 className="w-4 h-4 text-slate-400" />
          </button>
          <button onClick={() => setShowDiff(!showDiff)} className="p-1.5 hover:bg-slate-800 rounded-lg transition-colors" title="Comparar versiones">
            <Eye className="w-4 h-4 text-slate-400" />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <User className="w-4 h-4 text-slate-500" />
        <input type="text" value={author} onChange={(e) => setAuthor(e.target.value)}
          placeholder="Nombre del profesional que edita"
          className="flex-1 px-3 py-1.5 bg-slate-950/70 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500" />
      </div>

      {Object.entries(groupedFields).map(([source, srcFields]) => {
        if (srcFields.length === 0) return null;
        const srcMeta = SOURCE_LABELS[source] || SOURCE_LABELS.manual;
        return (
          <div key={source}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${srcMeta.color}`}>{srcMeta.label}</span>
              <span className="text-[10px] text-slate-600">{srcFields.length} campos</span>
            </div>
            <div className="space-y-2">
              {srcFields.map((field) => (
                <div key={field.key} className="flex items-start gap-2">
                  <div className="flex-1">
                    <label className="text-[11px] text-slate-400 font-medium">{field.label}</label>
                    {field.type === 'readonly' ? (
                      <div className="mt-0.5 px-3 py-1.5 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-300 font-mono">
                        {field.value}
                      </div>
                    ) : field.type === 'textarea' ? (
                      <textarea value={field.value} onChange={(e) => updateField(field.key, e.target.value)}
                        disabled={locked[field.key]}
                        rows={3}
                        className="mt-0.5 w-full px-3 py-1.5 bg-slate-950/70 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 disabled:opacity-50 resize-none" />
                    ) : (
                      <input type="text" value={field.value} onChange={(e) => updateField(field.key, e.target.value)}
                        disabled={locked[field.key]}
                        className="mt-0.5 w-full px-3 py-1.5 bg-slate-950/70 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 disabled:opacity-50" />
                    )}
                  </div>
                  {source !== 'praat' && source !== 'system' && (
                    <button onClick={() => setLocked({ ...locked, [field.key]: !locked[field.key] })}
                      className="mt-4 p-1 hover:bg-slate-800 rounded transition-colors" title={locked[field.key] ? 'Desbloquear' : 'Bloquear'}>
                      {locked[field.key] ? <Lock className="w-3.5 h-3.5 text-yellow-400" /> : <Unlock className="w-3.5 h-3.5 text-slate-500" />}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {versions.length > 0 && (
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Versiones guardadas</div>
          <div className="space-y-1">
            {versions.map((ver) => (
              <div key={ver.id} className="flex items-center justify-between px-3 py-1.5 bg-slate-900/40 border border-slate-800 rounded-lg text-[11px]">
                <span className="text-slate-400">{ver.id}</span>
                <span className="text-slate-500">{ver.author}</span>
                <span className="text-slate-600">{new Date(ver.timestamp).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={saveVersion}
          className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-xs text-slate-300 font-semibold flex items-center justify-center gap-2 transition-colors">
          <Save className="w-3.5 h-3.5" /> Guardar borrador
        </button>
        <button onClick={() => onExport(fields)}
          className="flex-1 py-2.5 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 rounded-xl text-xs text-white font-semibold flex items-center justify-center gap-2 transition-colors shadow-lg shadow-sky-500/20">
          <FileText className="w-3.5 h-3.5" /> Exportar PDF final
        </button>
      </div>
    </div>
  );
}
