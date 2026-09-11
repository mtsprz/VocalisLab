/** Edad exacta en años cumplidos a partir de fecha ISO (YYYY-MM-DD).
 *  Resta simple de años falla cuando el cumpleaños aún no ocurrió este año.
 *  Devuelve null si la fecha es inválida o vacía. */
export function calcularEdad(fechaNacimiento: string | null | undefined): number | null {
  if (!fechaNacimiento) return null;
  const nac = new Date(fechaNacimiento);
  if (isNaN(nac.getTime())) return null;
  const hoy = new Date();
  let edad = hoy.getFullYear() - nac.getFullYear();
  const m = hoy.getMonth() - nac.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < nac.getDate())) edad--;
  return edad;
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
  return '— Lic. Matías Pérez\nConsultorio de Voz y Rehabilitación Vocal';
}
