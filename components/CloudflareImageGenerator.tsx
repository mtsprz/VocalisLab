import React, { useState } from 'react';
import { Sparkles, Loader2, AlertCircle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

export default function CloudflareImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [image, setImage] = useState<string | null>(null);
  const [error, setError] = useState('');

  const generar = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError('');
    setImage(null);
    try {
      const r = await fetch(`${BACKEND_URL}/api/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt.trim() }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || !data.ok) {
        throw new Error(data.detail || data.error || `Error ${r.status}`);
      }
      setImage(data.image_base64);
    } catch (e: any) {
      setError(e.message || 'No se pudo generar la imagen');
    }
    setLoading(false);
  };

  return (
    <div className="max-w-2xl mx-auto bg-white dark:bg-[#111827] rounded-2xl border border-gray-200 dark:border-white/10 p-6 shadow-sm space-y-4">
      <h2 className="text-sm font-bold text-gray-900 dark:text-white flex items-center gap-2">
        <Sparkles size={16} className="text-purple-500" /> Generador de Imágenes — Cloudflare Workers AI
      </h2>
      <p className="text-[11px] text-gray-500 dark:text-gray-400">
        Escribí un prompt descriptivo. El backend lo envía a Cloudflare de forma segura (sin exponer tu API Token).
      </p>

      <div className="flex gap-2">
        <input
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && generar()}
          placeholder="Ej: Minimalist line art of a glass with water, bubbling tube..."
          className="flex-1 px-3 py-2.5 bg-gray-50 dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl text-xs text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        />
        <button
          onClick={generar}
          disabled={loading || !prompt.trim()}
          className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center gap-2 disabled:opacity-50 shrink-0"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {loading ? 'Generando…' : 'Generar'}
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <Loader2 size={14} className="animate-spin" /> Procesando imagen en Cloudflare…
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 dark:text-red-400 font-semibold flex items-center gap-1">
          <AlertCircle size={14} /> {error}
        </p>
      )}

      {image && (
        <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-black/20 p-2">
          <img src={image} alt="Generada por Cloudflare Workers AI" className="w-full rounded-lg" />
        </div>
      )}
    </div>
  );
}
