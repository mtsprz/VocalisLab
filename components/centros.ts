/**
 * Centros de atención (misma lista que server_api/agenda_fonoar.py).
 * cuadernilloPropio: el centro entrega su propio cuadernillo (Fonoar), así
 * que la app no genera uno; solo hace el seguimiento del paciente.
 */
export interface Centro {
  id: string;
  nombre: string;
  cuadernilloPropio: boolean;
}

export const CENTROS: Centro[] = [
  { id: 'fonoar_la_plata', nombre: 'Fonoar La Plata', cuadernilloPropio: true },
  { id: 'due_brandsen', nombre: 'DUE Brandsen', cuadernilloPropio: false },
  { id: 'virtual', nombre: 'Atención virtual', cuadernilloPropio: false },
];

export function centroPorId(id?: string | null): Centro | undefined {
  return CENTROS.find(c => c.id === id);
}

export function nombreCentro(id?: string | null): string {
  return centroPorId(id)?.nombre || '';
}
