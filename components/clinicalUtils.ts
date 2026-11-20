import { edad } from '../utils/fechas';
/** Edad exacta en años cumplidos a partir de fecha ISO (YYYY-MM-DD).
 *  Resta simple de años falla cuando el cumpleaños aún no ocurrió este año.
 *  Devuelve null si la fecha es inválida o vacía. */
export function calcularEdad(fechaNacimiento: string | null | undefined): number | null {
  return edad(fechaNacimiento);
}

/** Firma profesional para mensajes/WhatsApp/Email (marca blanca personal). */
export function firmaProfesional(): string {
  try {
    const raw = localStorage.getItem('vocalislab_profesional');
    if (raw) {
      const p = JSON.parse(raw);
      const nom = String(p.profesional_nombre || '').trim();
      if (nom) return `— ${nom}`;
    }
  } catch {}
  return '— Matías Pérez, Fonoaudiólogo\nConsultorio de Voz y Rehabilitación Vocal';
}
