import React, { useState, useRef } from 'react';
import { Upload, FileSpreadsheet, CheckCircle2, AlertTriangle, X } from 'lucide-react';

interface VoxPlotVariable {
  key: string;
  label: string;
  unit: string;
  category: 'sv' | 'cs' | 'mx' | 'global';
  value: number | null;
}

interface VoxPlotImportProps {
  onImport: (data: { variables: VoxPlotVariable[]; rawCsv: string; fileName: string }) => void;
  onClose?: () => void;
}

const EXPECTED_VARIABLES: Record<string, { label: string; unit: string; category: 'sv' | 'cs' | 'mx' | 'global' }> = {
  sv_meanPitch: { label: 'F0 media vocal sostenida', unit: 'Hz', category: 'sv' },
  cs_meanPitch: { label: 'F0 media habla continua', unit: 'Hz', category: 'cs' },
  mx_meanPitch: { label: 'F0 media muestra mixta', unit: 'Hz', category: 'mx' },
  sv_jitterLocal: { label: 'Jitter local SV', unit: '%', category: 'sv' },
  cs_jitterLocal: { label: 'Jitter local CS', unit: '%', category: 'cs' },
  mx_jitterLocal: { label: 'Jitter local MX', unit: '%', category: 'mx' },
  sv_shimmerLocal: { label: 'Shimmer local SV', unit: '%', category: 'sv' },
  cs_shimmerLocal: { label: 'Shimmer local CS', unit: '%', category: 'cs' },
  sv_hnr: { label: 'HNR SV', unit: 'dB', category: 'sv' },
  cs_hnr: { label: 'HNR CS', unit: 'dB', category: 'cs' },
  mx_hnr: { label: 'HNR MX', unit: 'dB', category: 'mx' },
  sv_cpps: { label: 'CPPS SV', unit: 'dB', category: 'sv' },
  cs_cpps: { label: 'CPPS CS', unit: 'dB', category: 'cs' },
  mx_cpps: { label: 'CPPS MX', unit: 'dB', category: 'mx' },
  avqi: { label: 'AVQI', unit: '', category: 'global' },
  abi: { label: 'ABI', unit: '', category: 'global' },
  sv_slope: { label: 'Slope SV', unit: 'dB/oct', category: 'sv' },
  cs_slope: { label: 'Slope CS', unit: 'dB/oct', category: 'cs' },
  sv_tilt: { label: 'Tilt SV', unit: 'dB', category: 'sv' },
  cs_tilt: { label: 'Tilt CS', unit: 'dB', category: 'cs' },
  sv_h1h2: { label: 'H1-H2 SV', unit: 'dB', category: 'sv' },
  cs_h1h2: { label: 'H1-H2 CS', unit: 'dB', category: 'cs' },
  sv_shimmerDb: { label: 'Shimmer dB SV', unit: 'dB', category: 'sv' },
  cs_shimmerDb: { label: 'Shimmer dB CS', unit: 'dB', category: 'cs' },
  sv_jitterPPQ5: { label: 'Jitter PPQ5 SV', unit: '%', category: 'sv' },
  cs_jitterPPQ5: { label: 'Jitter PPQ5 CS', unit: '%', category: 'cs' },
  sv_hnrD: { label: 'HNR-D SV', unit: 'dB', category: 'sv' },
  cs_hnrD: { label: 'HNR-D CS', unit: 'dB', category: 'cs' },
  sv_gne: { label: 'GNE SV', unit: '', category: 'sv' },
  cs_gne: { label: 'GNE CS', unit: '', category: 'cs' },
  sv_psd: { label: 'PSD SV', unit: 'dB', category: 'sv' },
  cs_psd: { label: 'PSD CS', unit: 'dB', category: 'cs' },
  sv_hfNoise: { label: 'HF Noise SV', unit: 'dB', category: 'sv' },
  cs_hfNoise: { label: 'HF Noise CS', unit: 'dB', category: 'cs' },
  sv_voiceBreaks: { label: 'Voice Breaks SV', unit: '', category: 'sv' },
  cs_voiceBreaks: { label: 'Voice Breaks CS', unit: '', category: 'cs' },
};

function parseVoxPlotCsv(csvText: string): VoxPlotVariable[] {
  const lines = csvText.trim().split('\n');
  if (lines.length < 2) return [];

  const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
  const values = lines[1].split(',').map(v => v.trim().replace(/"/g, ''));

  const variables: VoxPlotVariable[] = [];
  for (let i = 0; i < headers.length; i++) {
    const key = headers[i];
    const val = values[i];
    const meta = EXPECTED_VARIABLES[key];
    if (meta) {
      variables.push({
        key,
        label: meta.label,
        unit: meta.unit,
        category: meta.category,
        value: val && val !== '' && val !== 'NA' && val !== 'N/A' ? parseFloat(val) : null,
      });
    } else if (key && val && val !== '' && val !== 'NA') {
      const numVal = parseFloat(val);
      variables.push({
        key,
        label: key,
        unit: '',
        category: 'global',
        value: isNaN(numVal) ? null : numVal,
      });
    }
  }
  return variables;
}

export default function VoxPlotImport({ onImport, onClose }: VoxPlotImportProps) {
  const [variables, setVariables] = useState<VoxPlotVariable[]>([]);
  const [rawCsv, setRawCsv] = useState('');
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState('');
  const [parsed, setParsed] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setError('');

    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      setRawCsv(text);
      try {
        const vars = parseVoxPlotCsv(text);
        if (vars.length === 0) {
          setError('No se encontraron variables reconocidas en el CSV. Verifique el formato.');
          return;
        }
        setVariables(vars);
        setParsed(true);
      } catch (err) {
        setError('Error al parsear el archivo CSV.');
      }
    };
    reader.readAsText(file);
  };

  const handleConfirm = () => {
    onImport({ variables, rawCsv, fileName });
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl p-5 rounded-2xl shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-sky-400" />
          <h3 className="text-sm font-bold text-slate-100">Importar datos VOXplot</h3>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded-lg transition-colors">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        )}
      </div>

      {!parsed ? (
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            Suba el CSV exportado desde VOXplot. El sistema reconocerá automáticamente las variables de SV (vocal sostenida), CS (habla continua) y MX (mixta).
          </p>
          <input ref={fileRef} type="file" accept=".csv,.txt" onChange={handleFile} className="hidden" />
          <button onClick={() => fileRef.current?.click()}
            className="w-full py-8 border-2 border-dashed border-slate-700 hover:border-sky-500/50 rounded-xl flex flex-col items-center gap-2 transition-colors">
            <Upload className="w-6 h-6 text-slate-500" />
            <span className="text-xs text-slate-400">Arrastre o seleccione un archivo CSV</span>
          </button>
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
              <span className="text-xs text-red-300">{error}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-xs font-medium">{variables.length} variables reconocidas de {fileName}</span>
          </div>

          {(['sv', 'cs', 'mx', 'global'] as const).map((cat) => {
            const catVars = variables.filter(v => v.category === cat);
            if (catVars.length === 0) return null;
            const catLabels = { sv: 'Vocal Sostenida (SV)', cs: 'Habla Continua (CS)', mx: 'Muestra Mixta (MX)', global: 'Global' };
            return (
              <div key={cat}>
                <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">{catLabels[cat]}</div>
                <div className="grid grid-cols-2 gap-1">
                  {catVars.map((v) => (
                    <div key={v.key} className="flex items-center justify-between px-2 py-1 bg-slate-950/50 rounded text-xs">
                      <span className="text-slate-400 truncate">{v.label}</span>
                      <span className="text-slate-200 font-mono ml-2">{v.value !== null ? `${v.value}${v.unit}` : 'N/D'}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          <div className="flex gap-2">
            <button onClick={() => { setParsed(false); setVariables([]); setRawCsv(''); }}
              className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors">
              Cancelar
            </button>
            <button onClick={handleConfirm}
              className="flex-1 py-2 bg-sky-500 hover:bg-sky-400 rounded-lg text-xs text-white font-semibold transition-colors">
              Importar datos
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
