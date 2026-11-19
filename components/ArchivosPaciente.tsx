import React, { useEffect, useState } from 'react';
import { X, Upload, Loader2, ExternalLink, Trash2, FileText, Image as ImageIcon, Film, Music, FolderOpen, AlertTriangle } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

interface Props {
  paciente: { id: string; nombre_completo: string };
  onClose: () => void;
}

const TIPOS: Record<string, string> = {
  informe_orl: 'Informe ORL', estudio: 'Estudio / evaluación', foto: 'Foto',
  video: 'Video', audio: 'Audio', documento: 'Documento',
};
const ORIGENES: Record<string, string> = {
  whatsapp_paciente: 'WhatsApp del paciente', whatsapp_orl: 'WhatsApp del ORL',
  orl: 'ORL (otro medio)', consultorio: 'Consultorio', otro: 'Otro',
};

/** Tipo sugerido según el archivo elegido (se puede cambiar). */
function tipoSugerido(f: File): string {
  if (f.type.startsWith('video/')) return 'video';
  if (f.type.startsWith('audio/')) return 'audio';
  if (f.type.startsWith('image/')) return 'foto';
  if (f.type === 'application/pdf') return 'informe_orl';
  return 'documento';
}

function icono(tipo: string, mime: string) {
  if (tipo === 'video' || mime.startsWith('video/')) return <Film size={16} className="text-purple-500" />;
  if (tipo === 'audio' || mime.startsWith('audio/')) return <Music size={16} className="text-emerald-500" />;
  if (tipo === 'foto' || mime.startsWith('image/')) return <ImageIcon size={16} className="text-sky-500" />;
  return <FileText size={16} className="text-indigo-500" />;
}

function tamano(b: number) {
  return b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
}

/**
 * Archivos de la ficha del paciente (informes ORL, fotos, videos y audios
 * que llegan por WhatsApp). Se guardan en el Google Drive del profesional,
 * en una carpeta por paciente; acá se listan con su tipo, origen y fecha.
 */
export default function ArchivosPaciente({ paciente, onClose }: Props) {
  const [archivos, setArchivos] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState('');
  const [error, setError] = useState('');
  const [archivo, setArchivo] = useState<File | null>(null);
  const [tipo, setTipo] = useState('documento');
  const [origen, setOrigen] = useState('whatsapp_paciente');
  const [titulo, setTitulo] = useState('');
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [notas, setNotas] = useState('');
  const [subiendo, setSubiendo] = useState(false);
  const [hecho, setHecho] = useState('');

  const cargar = async () => {
    setCargando(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/pacientes/${paciente.id}/archivos`);
      const d = await r.json();
      setArchivos(d.archivos || []);
      setAviso(d.aviso || '');
    } catch {
      setError('No se pudo cargar la lista de archivos.');
    }
    setCargando(false);
  };

  useEffect(() => { cargar(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [paciente.id]);

  const elegir = (f: File | null) => {
    setArchivo(f);
    setError('');
    if (f) {
      setTipo(tipoSugerido(f));
      if (!titulo) setTitulo(f.name.replace(/\.[^.]+$/, ''));
    }
  };

  const subir = async () => {
    if (!archivo) return;
    if (archivo.size > 300 * 1024 * 1024) { setError('El archivo supera 300 MB.'); return; }
    setSubiendo(true);
    setError('');
    setHecho('');
    const fd = new FormData();
    fd.append('archivo', archivo);
    fd.append('tipo', tipo);
    fd.append('origen', origen);
    fd.append('titulo', titulo);
    fd.append('fecha', fecha);
    fd.append('notas', notas);
    try {
      const r = await fetch(`${BACKEND_URL}/api/pacientes/${paciente.id}/archivos`, { method: 'POST', body: fd });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      setArchivo(null); setTitulo(''); setNotas('');
      const n = Number(d.imagenes_extraidas) || 0;
      setHecho(n ? `Subido. Se separaron ${n} imagen${n === 1 ? '' : 'es'} del PDF y quedaron en la galería de la ficha integral.` : 'Subido.');
      await cargar();
    } catch (e: any) {
      setError(e?.message || 'No se pudo subir el archivo.');
    }
    setSubiendo(false);
  };

  const borrar = async (a: any) => {
    if (!confirm(`¿Quitar «${a.titulo || a.nombre_archivo}» de la ficha?\nSe manda a la papelera de Google Drive (se puede recuperar durante 30 días).`)) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/archivos/${a.id}`, { method: 'DELETE' });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || `Error ${r.status}`);
      await cargar();
    } catch (e: any) {
      setError(e?.message || 'No se pudo quitar el archivo.');
    }
  };

  const carpeta = archivos.find(a => a.drive_carpeta_url)?.drive_carpeta_url;
  const campo = 'w-full px-3 py-2 border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b0f19] text-slate-900 dark:text-slate-100 rounded-xl text-xs';

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-[#111827] rounded-2xl border border-slate-200 dark:border-white/10 w-full max-w-3xl max-h-[90vh] overflow-y-auto p-5 shadow-2xl">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <FolderOpen size={18} className="text-indigo-500" /> Archivos de {paciente.nombre_completo}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10"><X size={16} /></button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          Informes del ORL, fotos, videos y audios (por ejemplo, los que llegan por WhatsApp). Se guardan en tu Google
          Drive, en una carpeta de este paciente.
          {carpeta && <> {' '}<a href={carpeta} target="_blank" rel="noreferrer" className="text-indigo-600 underline">Abrir carpeta en Drive</a></>}
        </p>

        {aviso && <p className="mb-3 text-xs text-amber-700 dark:text-amber-300 flex gap-1.5"><AlertTriangle size={13} />{aviso}</p>}

        {/* Carga */}
        <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-4 space-y-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-200 cursor-pointer">
            <Upload size={15} className="text-indigo-500" />
            {archivo ? `${archivo.name} (${tamano(archivo.size)})` : 'Elegir archivo (PDF, foto, video o audio, hasta 300 MB)'}
            <input type="file" className="hidden" accept="image/*,video/*,audio/*,application/pdf,.doc,.docx"
              onChange={e => elegir(e.target.files?.[0] || null)} />
          </label>
          {archivo && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <select value={tipo} onChange={e => setTipo(e.target.value)} className={campo}>
                  {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <select value={origen} onChange={e => setOrigen(e.target.value)} className={campo}>
                  {Object.entries(ORIGENES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <input type="date" value={fecha} onChange={e => setFecha(e.target.value)} className={campo} title="Fecha del estudio o de recepción" />
              </div>
              <input value={titulo} onChange={e => setTitulo(e.target.value)} placeholder="Título (ej. Videolaringoscopia Dr. …)" className={campo} />
              <textarea value={notas} onChange={e => setNotas(e.target.value)} rows={2} placeholder="Notas (opcional)" className={campo} />
              <div className="flex justify-end">
                <button onClick={subir} disabled={subiendo}
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50">
                  {subiendo ? <><Loader2 size={13} className="animate-spin" /> Subiendo a Drive…</> : <><Upload size={13} /> Guardar en la ficha</>}
                </button>
              </div>
            </>
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
          {hecho && <p className="text-xs text-emerald-600">{hecho}</p>}
        </div>

        {/* Lista */}
        <div className="mt-4">
          {cargando ? (
            <p className="text-xs text-slate-500 flex items-center gap-1.5"><Loader2 size={13} className="animate-spin" /> Cargando…</p>
          ) : archivos.length === 0 ? (
            <p className="text-xs text-slate-500">Todavía no hay archivos en la ficha de este paciente.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-white/5">
              {archivos.map(a => (
                <li key={a.id} className="py-2.5 flex items-start gap-3">
                  <div className="mt-0.5">{icono(a.tipo, a.mime || '')}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-900 dark:text-white truncate">{a.titulo || a.nombre_archivo}</p>
                    <p className="text-[11px] text-slate-500">
                      {TIPOS[a.tipo] || a.tipo} · {ORIGENES[a.origen] || a.origen} · {a.fecha}
                      {a.tamano_bytes ? ` · ${tamano(a.tamano_bytes)}` : ''}
                    </p>
                    {a.notas && <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-0.5">{a.notas}</p>}
                  </div>
                  {a.drive_url && (
                    <a href={a.drive_url} target="_blank" rel="noreferrer" title="Abrir en Google Drive"
                      className="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                      <ExternalLink size={15} />
                    </a>
                  )}
                  <button onClick={() => borrar(a)} title="Quitar de la ficha"
                    className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
