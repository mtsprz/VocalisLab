/**
 * Filtros de la agenda en hora de Argentina.
 *
 * Antes la vista "día/semana/mes" solo cambiaba el título: la lista mostraba
 * todos los turnos (un miércoles aparecían los de DUE del lunes). Además los
 * días se agrupaban en UTC, así que un turno de las 21 h o más tarde caía
 * en el día siguiente.
 */
export const ZONA_AR = 'America/Argentina/Buenos_Aires';

export type FormatoVista = 'dia' | 'semana' | 'mes';
export type FiltroCentro = 'TODOS' | 'fonoar_la_plata' | 'due_brandsen' | 'virtual' | 'CANTO';

/** 'AAAA-MM-DD' del instante en hora de Argentina. */
export function diaLocal(fecha: string | Date): string {
  return new Date(fecha).toLocaleDateString('en-CA', { timeZone: ZONA_AR });
}

function sumarDias(clave: string, n: number): string {
  const [a, m, d] = clave.split('-').map(Number);
  const f = new Date(Date.UTC(a, m - 1, d + n));
  return f.toISOString().slice(0, 10);
}

/** Rango de días (inclusive) que muestra la vista. Semana: lunes a domingo. */
export function rangoVista(fecha: Date, formato: FormatoVista): { desde: string; hasta: string } {
  const hoy = diaLocal(fecha);
  if (formato === 'dia') return { desde: hoy, hasta: hoy };
  if (formato === 'semana') {
    const [a, m, d] = hoy.split('-').map(Number);
    const dow = new Date(Date.UTC(a, m - 1, d)).getUTCDay(); // 0 = domingo
    const lunes = sumarDias(hoy, -((dow + 6) % 7));
    return { desde: lunes, hasta: sumarDias(lunes, 6) };
  }
  const [a, m] = hoy.split('-').map(Number);
  const ultimo = new Date(Date.UTC(a, m, 0)).getUTCDate();
  return { desde: `${a}-${String(m).padStart(2, '0')}-01`, hasta: `${a}-${String(m).padStart(2, '0')}-${ultimo}` };
}

export function esVirtual(t: any): boolean {
  return (t.modalidad || '').toUpperCase() === 'VIRTUAL' || Boolean(t.meet_link);
}

/** Clase de canto (alumno) en lugar de paciente de voz. */
export function esCanto(t: any): boolean {
  return /canto/i.test(`${t.motivo || ''} ${t.notas || ''} ${t.pacientes?.tipo_atencion || ''}`);
}

/** Centro del turno: virtual si la modalidad es virtual; si no, el del paciente. */
export function centroTurno(t: any): string {
  if (esVirtual(t)) return 'virtual';
  return t.pacientes?.centro || t.centro || '';
}

export function pasaFiltroCentro(t: any, filtro: FiltroCentro): boolean {
  if (filtro === 'TODOS') return true;
  if (filtro === 'CANTO') return esCanto(t);
  return centroTurno(t) === filtro;
}
