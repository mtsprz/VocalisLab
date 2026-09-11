import React, { useState } from 'react';
import {
  Upload, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp,
  ScanLine, Save, FileText
} from 'lucide-react';
import { useClinical } from './ClinicalContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  pacienteId: string | null;
}

const EDITABLE_FIELDS: { key: string; label: string; unit: string }[] = [
  { key: 'f0_mean', label: 'F0 media', unit: 'Hz' },
  { key: 'f0_min', label: 'F0 mínima', unit: 'Hz' },
  { key: 'f0_max', label: 'F0 máxima', unit: 'Hz' },
  { key: 'f0_sd', label: 'F0 DE', unit: 'Hz' },
  { key: 'jitter_local_pct', label: 'Jitter local', unit: '%' },
  { key: 'jitter_rap_pct', label: 'Jitter RAP', unit: '%' },
  { key: 'jitter_ppq5_pct', label: 'Jitter PPQ5', unit: '%' },
  { key: 'shimmer_local_pct', label: 'Shimmer local', unit: '%' },
  { key: 'shimmer_apq3_pct', label: 'Shimmer APQ3', unit: '%' },
  { key: 'shimmer_apq5_pct', label: 'Shimmer APQ5', unit: '%' },
  { key: 'hnr_db', label: 'HNR', unit: 'dB' },
  { key: 'nhr', label: 'NHR', unit: '' },
  { key: 'cpps_db', label: 'CPPS', unit: 'dB' },
  { key: 'avqi', label: 'AVQI', unit: '' },
  { key: 'mpt_s', label: 'TMF / MPT', unit: 's' },
  { key: 'dsi', label: 'DSI', unit: '' },
  { key: 'f1_hz', label: 'F1', unit: 'Hz' },
  { key: 'f2_hz', label: 'F2', unit: 'Hz' },
  { key: 'f3_hz', label: 'F3', unit: 'Hz' },
  { key: 'f4_hz', label: 'F4', unit: 'Hz' },
];

export default function ExternalAnalysisUpload({ pacienteId }: Props) {
  const clinical = useClinical();
  const [open, setOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [valores, setValores] = useState<Record<string, number | null> | null>(null);
  const [origen, setOrigen] = useState('');
  const [confianza, setConfianza] = useState('');
  const [observaciones, setObservaciones] = useState('');

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError('');
    setSaved(false);
    try {
      const fd = new FormData();
      fd.append('archivo', file, file.name);
      const r = await fetch(`${BACKEND_URL}/api/analisis-externo/ocr`, {
        method: 'POST', body: fd,
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) {
        throw new Error(data.error || data.detail || `Error del servidor (${r.status})`);
      }
      setValores(data.valores || {});
      setOrigen(data.origen_detectado || '');
      setConfianza(data.confianza || '');
      setObservaciones(data.observaciones || '');
    } catch (err: any) {
      setError(err.message || 'No se pudo procesar el archivo');
      setValores(null);
    }
    setUploading(false);
  };

  const setVal = (key: string, raw: string) => {
    const v = raw.trim() === '' ? null : Number(raw.replace(',', '.'));
    setValores(prev => ({ ...(prev || {}), [key]: v == null || isNaN(v as number) ? null : v }));
  };

  const volcarHistoria = async () => {
    if (!valores) return;
    setSaving(true);
    setError('');
    try {
      const flat: any = { ...valores };
      clinical.setAcustica({
        f0_mean: flat.f0_mean ?? undefined,
        f0_min: flat.f0_min ?? undefined,
        f0_max: flat.f0_max ?? undefined,
        f0_sd: flat.f0_sd ?? undefined,
        jitter_local_pct: flat.jitter_local_pct ?? undefined,
        shimmer_local_pct: flat.shimmer_local_pct ?? undefined,
        hnr_db: flat.hnr_db ?? undefined,
        cpps_db: flat.cpps_db ?? undefined,
        nhr: flat.nhr ?? undefined,
        avqi: flat.avqi ?? undefined,
        f1_hz: flat.f1_hz ?? undefined,
        f2_hz: flat.f2_hz ?? undefined,
        origen: `externo:${origen || 'otro profesional'}`,
      });
      clinical.markStep('analisis');

      if (pacienteId) {
        const fd = new FormData();
        fd.append('paciente_id', pacienteId);
        fd.append('metrics_json', JSON.stringify({
          f0_mean: flat.f0_mean, f0_min: flat.f0_min, f0_max: flat.f0_max,
          f0_sd: flat.f0_sd,
          jitter_local_pct: flat.jitter_local_pct,
          jitter_rap_pct: flat.jitter_rap_pct, jitter_ppq5_pct: flat.jitter_ppq5_pct,
          shimmer_local_pct: flat.shimmer_local_pct,
          shimmer_apq3_pct: flat.shimmer_apq3_pct, shimmer_apq5_pct: flat.shimmer_apq5_pct,
          hnr_db: flat.hnr_db, cpps_db: flat.cpps_db, nhr: flat.nhr,
          avqi: flat.avqi,
          f1_hz: flat.f1_hz, f2_hz: flat.f2_hz, f3_hz: flat.f3_hz, f4_hz: flat.f4_hz,
        }));
        fd.append('cross_check_json', JSON.stringify({
          origen_externo: origen || 'otro profesional',
          confianza_ocr: confianza, observaciones,
        }));
        fd.append('charts_json', '{}');
        fd.append('modo', 'externo');
        const r = await fetch(`${BACKEND_URL}/api/analisis_acusticos`, { method: 'POST', body: fd });
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || `Error guardando (${r.status})`);
        }
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (err: any) {
      setError(err.message || 'No se pudo volcar a la historia clínica');
    }
    setSaving(false);
  };

  const conValor = valores ? EDITABLE_FIELDS.filter(f => valores[f.key] != null) : [];
  const sinValor = valores ? EDITABLE_FIELDS.filter(f => valores[f.key] == null) : [];

  return (
    <div className="bg-white dark:bg-[#111827] border border-gray-200 dark:border-white/10 rounded-2xl shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
            <ScanLine size={20} />
          </div>
          <div>
            <h3 className="font-bold text-sm text-gray-900 dark:text-white">
              Análisis acústico externo (otro profesional)
            </h3>
            <p className="text-[11px] text-gray-500 dark:text-gray-400">
              Subí foto, captura o PDF del informe — la IA extrae los valores y los vuelca al paciente. Sin repetir Praat.
            </p>
          </div>
        </div>
        {open ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-100 dark:border-white/5 pt-4">
          <label className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700 hover:border-indigo-400 dark:hover:border-indigo-500 cursor-pointer text-xs font-bold text-gray-600 dark:text-gray-300 transition-all">
            {uploading
              ? <><Loader2 size={16} className="animate-spin" /> Procesando con IA…</>
              : <><Upload size={16} /> Subir informe (imagen PNG/JPG o PDF con texto)</>}
            <input type="file" accept="image/*,.pdf" className="hidden" onChange={handleFile} disabled={uploading} />
          </label>

          {error && (
            <p className="text-xs text-red-600 dark:text-red-400 font-semibold flex items-center gap-1">
              <AlertCircle size={14} /> {error}
            </p>
          )}

          {valores && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-700 dark:text-indigo-300 font-bold">
                  <FileText size={11} className="inline mr-1" />Origen: {origen || 'detectando…'}
                </span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300 font-bold">
                  Confianza OCR: {confianza || '—'}
                </span>
              </div>
              {observaciones && (
                <p className="text-[11px] text-gray-500 dark:text-gray-400 italic">{observaciones}</p>
              )}

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {conValor.map(f => (
                  <div key={f.key} className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-2">
                    <label className="block text-[10px] font-bold text-gray-500 dark:text-gray-400">
                      {f.label} ({f.unit})
                    </label>
                    <input
                      type="number" step="any"
                      value={valores[f.key] ?? ''}
                      onChange={e => setVal(f.key, e.target.value)}
                      className="w-full bg-transparent text-sm font-mono font-bold text-gray-900 dark:text-white focus:outline-none"
                    />
                  </div>
                ))}
              </div>
              {sinValor.length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-500 dark:text-gray-400 font-semibold">
                    Completar manualmente ({sinValor.length} no detectados)
                  </summary>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">
                    {sinValor.map(f => (
                      <div key={f.key} className="bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl p-2">
                        <label className="block text-[10px] font-bold text-gray-500 dark:text-gray-400">
                          {f.label} ({f.unit})
                        </label>
                        <input
                          type="number" step="any" placeholder="—"
                          value={valores[f.key] ?? ''}
                          onChange={e => setVal(f.key, e.target.value)}
                          className="w-full bg-transparent text-sm font-mono font-bold text-gray-900 dark:text-white focus:outline-none"
                        />
                      </div>
                    ))}
                  </div>
                </details>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={volcarHistoria}
                  disabled={saving}
                  className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-orange-500/20 active:scale-95 transition-all disabled:opacity-50"
                >
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {saving ? 'Volcando…' : 'Volcar a historia clínica y guardar'}
                </button>
                {saved && (
                  <span className="text-xs text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
                    <CheckCircle2 size={14} /> Volcado correcto
                  </span>
                )}
              </div>
              {!pacienteId && (
                <p className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold">
                  Sin paciente seleccionado: los valores se vuelcan al contexto, pero elegí un paciente para guardarlos en base.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
