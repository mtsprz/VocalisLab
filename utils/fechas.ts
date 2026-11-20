/**
 * Fechas del consultorio, siempre en hora de Argentina.
 *
 * Errores que evita:
 * - `new Date('2026-11-20')` es medianoche UTC = 19/11 21:00 en Argentina:
 *   una fecha sola se mostraba un día antes (y las edades cambiaban un día tarde).
 * - `new Date().toISOString().slice(0, 10)` es el día en UTC: después de las
 *   21 h ya figuraba "mañana".
 * - Cortar un timestamp de Supabase ("…T01:30:00+00:00".slice(0, 10)) da el día UTC.
 */
export const ZONA_AR = 'America/Argentina/Buenos_Aires';

const SOLO_FECHA = /^\d{4}-\d{2}-\d{2}$/;

/** Instante de un valor; una fecha sola se toma al mediodía argentino (no cambia de día). */
export function aFecha(v: string | number | Date | null | undefined): Date | null {
  if (v === null || v === undefined || v === '') return null;
  if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
  const s = String(v).trim();
  const d = SOLO_FECHA.test(s) ? new Date(`${s}T12:00:00-03:00`) : new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

/** 'AAAA-MM-DD' del día en Argentina. */
export function diaAR(v: string | number | Date | null | undefined = new Date()): string {
  const d = aFecha(v);
  return d ? d.toLocaleDateString('en-CA', { timeZone: ZONA_AR }) : '';
}

/** Hoy en Argentina, 'AAAA-MM-DD' (para inputs type=date). */
export const hoyAR = () => diaAR(new Date());

/** '20/11/2026' (o '—'). */
export function fechaCorta(v: any): string {
  const d = aFecha(v);
  return d ? d.toLocaleDateString('es-AR', { timeZone: ZONA_AR, day: '2-digit', month: '2-digit', year: 'numeric' }) : '—';
}

/** '20/11/2026 10:30' (una fecha sola, sin hora). */
export function fechaHora(v: any): string {
  if (v && SOLO_FECHA.test(String(v).trim())) return fechaCorta(v);
  const d = aFecha(v);
  if (!d) return '—';
  const hora = d.toLocaleTimeString('es-AR', { timeZone: ZONA_AR, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  return `${fechaCorta(d)} ${hora}`;
}

/** Años cumplidos hoy (en Argentina) a partir de la fecha de nacimiento. */
export function edad(nacimiento: any): number | null {
  const n = diaAR(nacimiento ? String(nacimiento).slice(0, 10) : null);
  if (!n) return null;
  const [an, mn, dn] = n.split('-').map(Number);
  const [ah, mh, dh] = hoyAR().split('-').map(Number);
  let e = ah - an;
  if (mh < mn || (mh === mn && dh < dn)) e--;
  return e >= 0 && e < 130 ? e : null;
}
