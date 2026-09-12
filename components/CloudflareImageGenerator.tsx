import React, { useState } from 'react';
import { Sparkles, Loader2, Download, Copy, CheckCircle2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || '';

const PRESET_PROMPTS: { label: string; prompt: string }[] = [
  { label: 'Agua / Hidratación', prompt: 'Minimalist 2D medical line art illustration of a clear glass with water and a silicone tube bubbling at 1.5 cm depth, clean black strokes on white background, simple pedagogical style, vector icon style, no shading, no colors, high legibility' },
  { label: 'Respiración', prompt: 'Minimalist 2D medical line art illustration of a human torso side-view showing abdominal expansion arrows during diaphragmatic breathing, clean black strokes on white background, simple pedagogical style, vector icon style, no shading, no colors' },
  { label: 'Masaje laríngeo', prompt: 'Minimalist 2D medical line art illustration of hands gently massaging the front of the neck in the laryngeal area, clean black strokes on white background, simple pedagogical style, vector icon style, no shading, no colors' },
  { label: 'Glissandos', prompt: 'Minimalist 2D medical line art illustration of five ascending musical stairs with notes going up and down for vocal glissando exercise, clean black strokes on white background, simple pedagogical style, vector icon style, no shading, no colors' },
];

export default function CloudflareImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const generate = async () => {
    const p = prompt.trim();
    if (!p) return;
    setLoading(true);
    setError('');
    setImageUrl('');
    try {
      const res = await fetch(`${API_BASE}/api/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: p }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Error al generar imagen');
      if (data.image_base64) {
        setImageUrl(data.image_base64);
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
          <p className="text-xs text-slate-500 dark:text-slate-400">Cloudflare Workers AI · Stable Diffusion XL Lightning</p>
        </div>
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

      {/* Prompt input */}
      <div className="relative">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe la ilustración que deseas generar..."
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
