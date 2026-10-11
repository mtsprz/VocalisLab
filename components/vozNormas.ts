/**
 * Normas de F0 y altura tonal compartidas por "Voz y sesiones" y el Pitch
 * Meter. Misma regla que el backend (server_api/companion.py
 * elegir_rango_normativo) y que Vocalis Companion (rangoPara); tabla en
 * supabase/companion_referencias_normativas.sql.
 */

export interface RangoNormativo {
  sexo_referencia: string;
  edad_min: number;
  edad_max: number;
  f0_min_hz: number;
  f0_max_hz: number;
  f0_promedio_min_hz?: number | null;
  f0_promedio_max_hz?: number | null;
  fuente?: string;
}

/** Respaldo si /referencias no responde: rangos generales adultos. */
export const RANGOS_RESPALDO: RangoNormativo[] = [
  { sexo_referencia: 'masculino', edad_min: 19, edad_max: 120, f0_min_hz: 100, f0_max_hz: 165, f0_promedio_min_hz: 132, f0_promedio_max_hz: 138.8, fuente: 'Rango general adulto' },
  { sexo_referencia: 'femenino', edad_min: 19, edad_max: 120, f0_min_hz: 190, f0_max_hz: 262, f0_promedio_min_hz: 209.3, f0_promedio_max_hz: 224, fuente: 'Rango general adulto' },
];

export function edadDesde(fechaNacimiento?: string | null): number | null {
  if (!fechaNacimiento) return null;
  const f = new Date(String(fechaNacimiento).slice(0, 10) + 'T00:00:00');
  if (isNaN(f.getTime())) return null;
  const h = new Date();
  let e = h.getFullYear() - f.getFullYear();
  if (h.getMonth() < f.getMonth() || (h.getMonth() === f.getMonth() && h.getDate() < f.getDate())) e--;
  return e < 0 ? null : e;
}

/** <= 18 años → fila 'ninex' de su edad (sin distinción de sexo); >= 19 → fila
 *  del sexo que contiene la edad (la más angosta); sin edad → la más amplia del
 *  sexo (rango general adulto); adulto sin sexo → null (no se supone un sexo). */
export function elegirRangoNormativo(rangos: any[], sexo: string, edad: number | null | undefined): RangoNormativo | null {
  const s = (sexo || '').toLowerCase();
  const buscado = s.startsWith('masc') || s === 'm' ? 'masculino' : (s.startsWith('fem') || s === 'f' ? 'femenino' : '');
  const ancho = (r: any) => (r.edad_max ?? 200) - (r.edad_min ?? 0);
  if (edad != null) {
    const tipo = edad <= 18 ? 'ninex' : buscado;
    if (!tipo) return null;
    const c = rangos.filter(r => r.sexo_referencia === tipo && edad >= (r.edad_min ?? 0) && edad <= (r.edad_max ?? 200))
      .sort((a, b) => ancho(a) - ancho(b));
    return c[0] || null;
  }
  if (!buscado) return null;
  return rangos.filter(r => r.sexo_referencia === buscado).sort((a, b) => ancho(b) - ancho(a))[0] || null;
}

export function promedioTexto(r?: RangoNormativo | null): string {
  if (!r || r.f0_promedio_min_hz == null) return '';
  const a = Math.round(r.f0_promedio_min_hz), b = Math.round(r.f0_promedio_max_hz ?? r.f0_promedio_min_hz);
  return a === b ? `${a}` : `${a}–${b}`;
}

export const NOTAS_ES = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si'];

/** Convención franco-belga / laringológica (Jackson Menaldi, Farías, Castelli),
 *  igual que Vocalis Companion: La3 = 440 Hz, Do3 = Do central, Do0 ≈ 33 Hz. */
export const CONVENCION_OCTAVAS = 'La3 = 440 Hz · Do3 = Do central';

export function notaDesdeMidi(midi: number): string {
  return `${NOTAS_ES[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 2}`;
}

/** Nota más cercana a una frecuencia (ej. 139 Hz → "Do#2"). */
export function notaEs(hz?: number | null): string {
  if (!hz || hz <= 0) return '';
  return notaDesdeMidi(69 + Math.round(12 * Math.log2(hz / 440)));
}
