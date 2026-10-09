// Utilidades PWA: lista mínima de pacientes + IndexedDB para audio offline.
// Sin dependencias. La lista mínima NUNCA lleva diagnósticos ni datos clínicos.

export const PAC_MIN_KEY = 'vocalislab_pacientes_min';
const PAC_MIN_TTL_MS = 7 * 24 * 3600 * 1000;

export interface PacienteMin {
  id: string;
  nombre: string; // abreviado: nombre + inicial apellido
  sexo_referencia: string;
  fecha_nacimiento: string;
}

export function nombreAbreviado(nombreCompleto: string): string {
  const p = (nombreCompleto || '').split(' ').filter(Boolean);
  if (!p.length) return '—';
  if (p.length === 1) return p[0];
  return `${p[0]} ${p[p.length - 1][0]}.`;
}

export function guardarPacientesMinimos(lista: any[]): void {
  try {
    const min: PacienteMin[] = (lista || []).map((p: any) => ({
      id: p.id,
      nombre: nombreAbreviado(p.nombre_completo || p.nombre || ''),
      sexo_referencia: p.sexo_referencia || p.sexo || '',
      fecha_nacimiento: p.fecha_nacimiento || '',
    })).filter((p) => p.id);
    localStorage.setItem(PAC_MIN_KEY, JSON.stringify({ ts: Date.now(), lista: min }));
  } catch {}
}

export function leerPacientesMinimos(): PacienteMin[] {
  try {
    const raw = localStorage.getItem(PAC_MIN_KEY);
    if (!raw) return [];
    const d = JSON.parse(raw);
    if (!d.ts || Date.now() - d.ts > PAC_MIN_TTL_MS) return [];
    return d.lista || [];
  } catch { return []; }
}

export function borrarPacientesMinimos(): void {
  try { localStorage.removeItem(PAC_MIN_KEY); } catch {}
}

// ─── IndexedDB mínima (trozos de audio del grabador de emergencia) ───
const DB = 'vocalis-emergencia';
const STORE = 'trozos';

function abrirDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const q = indexedDB.open(DB, 1);
    q.onupgradeneeded = () => {
      if (!q.result.objectStoreNames.contains(STORE)) {
        q.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    q.onsuccess = () => resolve(q.result);
    q.onerror = () => reject(q.error);
  });
}

export async function idbGuardar(item: any): Promise<number> {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    const rq = tx.objectStore(STORE).add(item);
    rq.onsuccess = () => resolve(rq.result as number);
    rq.onerror = () => reject(rq.error);
  });
}

export async function idbListar(): Promise<any[]> {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const rq = db.transaction(STORE, 'readonly').objectStore(STORE).getAll();
    rq.onsuccess = () => resolve(rq.result || []);
    rq.onerror = () => reject(rq.error);
  });
}

export async function idbBorrar(id: number): Promise<void> {
  const db = await abrirDB();
  return new Promise((resolve, reject) => {
    const rq = db.transaction(STORE, 'readwrite').objectStore(STORE).delete(id);
    rq.onsuccess = () => resolve();
    rq.onerror = () => reject(rq.error);
  });
}
