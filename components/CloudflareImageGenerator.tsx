import React, { useState } from 'react';
import { Sparkles, Loader2, Download, Copy, CheckCircle2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_BACKEND_URL || '';

const PRESET_PROMPTS: { label: string; prompt: string }[] = [
  { label: 'Agua / Hidratación', prompt: 'a person holding a clear glass with water, transparent silicone tube submerged exactly 1.5 cm below the surface, realistic water bubbles rising, clinical demonstration photo' },
  { label: 'Respiración', prompt: 'human torso side view showing diaphragmatic breathing with visible abdominal expansion, anatomically accurate musculature, clinical illustration' },
  { label: 'Masaje laríngeo', prompt: 'hands gently massaging the front of the human neck over the laryngeal area, anatomically correct hand and neck anatomy, clinical demonstration' },
  { label: 'Cuerdas vocales', prompt: 'superior view of healthy human vocal folds in closed phonation position, anatomically accurate laryngeal anatomy, endoscopic style medical illustration' },
  { label: 'Glissandos', prompt: 'singer performing ascending vocal glissando with open mouth posture, side profile, anatomically correct facial anatomy, clinical demonstration photo' },
];

const CATEGORIAS = [
  { id: '', label: 'Auto-detectar' },
  { id: 'MANUAL_THERAPY', label: 'Terapia manual' },
  { id: 'TVSO', label: 'TVSO / Dispositivos' },
  { id: 'POSTURE', label: 'Postura' },
  { id: 'RESONANCE', label: 'Resonancia' },
  { id: 'ANATOMY', label: 'Atlas anatómico' },
];

export default function CloudflareImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [estilo, setEstilo] = useState<'realista' | 'lineart'>('realista');
  const [categoria, setCategoria] = useState('');
  const [loading, setLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [modelo, setModelo] = useState('');
  const [categoriaOut, setCategoriaOut] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    const p = prompt.trim();
    if (!p) return;
    setLoading(true);
    setError('');
    setImageUrl('');
    setModelo('');
    setCategoriaOut('');
    try {
      const res = await fetch(`${API_BASE}/api/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: p, style: estilo, categoria }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al generar imagen');
      if (data.image_base64) {
        setImageUrl(data.image_base64);
        if (data.modelo) setModelo(String(data.modelo).replace('@cf/', ''));
        if (data.categoria_label) setCategoriaOut(data.categoria_label);
      } else {
        throw new Error('Respuesta sin imagen');
      }
    } catch (e: any) {
      setError(e.message || 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  const downloadImage = () => {
    if (!imageUrl) return;
    const a = document.createElement('a');
    a.href = imageUrl;
    a.download = `imagen_${Date.now()}.png`;
    a.click();
  };

  const copyPrompt = () => {
    navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 flex items-center justify-center shadow-lg">
          <Sparkles className="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-800 dark:text-white">Generador de Imágenes</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Cloudflare Workers AI · FLUX.1 Schnell clínico</p>
        </div>
      </div>

      {/* Style selector */}
      <div className="flex gap-2">
        {([
          { id: 'realista', label: 'Clínico realista', desc: 'Fotorrealista, anatomía precisa' },
          { id: 'lineart', label: 'Line-art', desc: 'Trazo simple para impresión' },
        ] as const).map((s) => (
          <button
            key={s.id}
            onClick={() => setEstilo(s.id)}
            className={`flex-1 px-3 py-2.5 rounded-xl border text-left transition-all ${
              estilo === s.id
                ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20 shadow-sm'
                : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-600'
            }`}
          >
            <p className={`text-xs font-bold ${estilo === s.id ? 'text-violet-700 dark:text-violet-300' : 'text-slate-700 dark:text-slate-300'}`}>{s.label}</p>
            <p className="text-[10px] text-slate-400 dark:text-slate-500">{s.desc}</p>
          </button>
        ))}
      </div>

      {/* Presets */}
      <div className="flex flex-wrap gap-2">
        {PRESET_PROMPTS.map((p) => (
          <button
            key={p.label}
            onClick={() => setPrompt(p.prompt)}
            className="text-xs px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors border border-slate-200 dark:border-slate-700"
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Category selector (motor de mediación) */}
      <div>
        <p className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1.5">Categoría clínica (mediación de prompt)</p>
        <div className="flex flex-wrap gap-2">
          {CATEGORIAS.map((c) => (
            <button
              key={c.id || 'auto'}
              onClick={() => setCategoria(c.id)}
              className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                categoria === c.id
                  ? 'bg-emerald-600 border-emerald-600 text-white font-semibold'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-emerald-400'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Prompt input */}
      <div className="relative">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe la anatomía o el ejercicio (ej: vista superior de cuerdas vocales sanas en cierre fonatorio)..."
          rows={3}
          className="w-full px-4 py-3 pr-24 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 text-sm placeholder-slate-400 dark:placeholder-slate-500 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400 dark:focus:ring-indigo-500 transition-shadow"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) generate();
          }}
        />
        <div className="absolute right-2 bottom-2 flex gap-1">
          <button
            onClick={copyPrompt}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
            title="Copiar prompt"
          >
            {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Generate button */}
      <button
        onClick={generate}
        disabled={loading || !prompt.trim()}
        className="w-full py-3 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white font-semibold text-sm shadow-lg shadow-violet-500/25 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Generando...
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            Generar Imagen
          </>
        )}
      </button>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Image result */}
      {imageUrl && (
        <div className="relative group rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-xl">
          <img
            src={imageUrl}
            alt="Imagen generada"
            className="w-full h-auto"
          />
          <div className="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={downloadImage}
              className="p-2 rounded-lg bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm transition-colors"
              title="Descargar"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>
          {modelo && (
            <div className="absolute bottom-3 left-3 px-2.5 py-1 rounded-lg bg-black/60 text-white text-[10px] font-medium backdrop-blur-sm">
              {modelo} · {estilo === 'realista' ? 'clínico realista' : 'line-art'}{categoriaOut ? ` · ${categoriaOut}` : ''}
            </div>
          )}
        </div>
      )}

      {/* Skeleton while loading */}
      {loading && !imageUrl && (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 h-64 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-slate-400 dark:text-slate-500">
            <Loader2 className="w-8 h-8 animate-spin" />
            <p className="text-xs font-medium">Generando imagen con Cloudflare AI...</p>
          </div>
        </div>
      )}
    </div>
  );
}
