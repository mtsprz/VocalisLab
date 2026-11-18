/**
 * Detección de F0 (YIN) y utilidades musicales, compartidas por la sala
 * virtual (profesional y paciente). Rango ampliable: voz hablada 60–600 Hz,
 * canto hasta 1200 Hz.
 */
export function yin(buffer: Float32Array, sampleRate: number, minHz = 60, maxHz = 600, umbral = 0.15): number | null {
  const half = Math.floor(buffer.length / 2);
  const minLag = Math.max(2, Math.floor(sampleRate / maxHz));
  const maxLag = Math.min(half - 1, Math.floor(sampleRate / minHz));
  const d = new Float32Array(maxLag + 2);
  for (let tau = 1; tau <= maxLag + 1; tau++) {
    let suma = 0;
    for (let j = 0; j < half; j++) {
      const delta = buffer[j] - buffer[j + tau];
      suma += delta * delta;
    }
    d[tau] = suma;
  }
  // Diferencia normalizada acumulada.
  let acumulado = 0;
  d[0] = 1;
  for (let tau = 1; tau <= maxLag + 1; tau++) {
    acumulado += d[tau];
    d[tau] = acumulado ? (d[tau] * tau) / acumulado : 1;
  }
  for (let tau = minLag; tau <= maxLag; tau++) {
    if (d[tau] < umbral) {
      while (tau + 1 <= maxLag && d[tau + 1] < d[tau]) tau++;
      // Interpolación parabólica para afinar el período.
      const a = d[tau - 1], b = d[tau], c = d[tau + 1];
      const den = a - 2 * b + c;
      const ajuste = den ? (a - c) / (2 * den) : 0;
      const f = sampleRate / (tau + ajuste);
      return f >= minHz && f <= maxHz ? f : null;
    }
  }
  return null;
}

/** Intensidad relativa (dBFS) de un bloque. */
export function dbfs(buffer: Float32Array): number {
  let s = 0;
  for (let i = 0; i < buffer.length; i++) s += buffer[i] * buffer[i];
  const rms = Math.sqrt(s / buffer.length);
  return rms > 0 ? 20 * Math.log10(rms) : -100;
}

// Convención franco-belga (La3 = 440 Hz, Do3 = Do central), como el resto de la app.
const NOTAS = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si'];

export function hzAMidi(hz: number): number {
  return 69 + 12 * Math.log2(hz / 440);
}

export function midiAHz(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

export function nombreNota(midi: number): string {
  const m = Math.round(midi);
  return `${NOTAS[((m % 12) + 12) % 12]}${Math.floor(m / 12) - 2}`;
}

/** Desvío en cents de `hz` respecto de `objetivoHz`. */
export function cents(hz: number, objetivoHz: number): number {
  return 1200 * Math.log2(hz / objetivoHz);
}

/** Lista de notas para elegir objetivo (Do1 a Do5). */
export function notasObjetivo(): { midi: number; nombre: string; hz: number }[] {
  const out = [];
  for (let m = 36; m <= 84; m++) out.push({ midi: m, nombre: nombreNota(m), hz: Math.round(midiAHz(m) * 10) / 10 });
  return out;
}

/** Convierte la URL del servidor (https) en la del WebSocket (wss). */
export function urlWs(backend: string, ruta: string): string {
  const base = backend || window.location.origin;
  return base.replace(/^http/, 'ws').replace(/\/$/, '') + ruta;
}
