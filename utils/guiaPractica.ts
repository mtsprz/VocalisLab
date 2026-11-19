/**
 * Camino de cada ejercicio de práctica guiada y métricas de la sesión.
 * Todo en semitonos respecto del tono base del ejercicio.
 */
export type Ejercicio = {
  bank_id?: string | null; nombre: string; guia: 'sostenida' | 'escalera' | 'rampa' | 'patron';
  base_hz: number; consigna?: string; repeticiones: number; tolerancia_cents: number;
  duracion_s?: number; amplitud?: number; semitonos?: number[]; nota_s?: number;
};

/** Duración de una pasada del ejercicio, en segundos. */
export function duracion(e: Ejercicio): number {
  if (e.guia === 'escalera' || e.guia === 'patron') return (e.semitonos?.length || 1) * (e.nota_s || 1.2);
  return e.duracion_s || 6;
}

/** Semitonos objetivo en el segundo t de la pasada. */
export function objetivoSemis(e: Ejercicio, t: number): number {
  const d = duracion(e);
  const u = Math.min(Math.max(t / d, 0), 1);
  if (e.guia === 'sostenida') return 0;
  if (e.guia === 'rampa') {
    const a = e.amplitud || 7;
    return u < 0.5 ? a * (u / 0.5) : a * (1 - (u - 0.5) / 0.5);
  }
  const s = e.semitonos || [0];
  return s[Math.min(s.length - 1, Math.floor(u * s.length))];
}

/** Rango vertical a mostrar (semitonos) con margen. */
export function rangoSemis(e: Ejercicio): [number, number] {
  const vals = e.guia === 'rampa' ? [0, e.amplitud || 7] : e.guia === 'sostenida' ? [0] : (e.semitonos || [0]);
  return [Math.min(...vals) - 4, Math.max(...vals) + 4];
}

export const semisDe = (hz: number, base: number) => 12 * Math.log2(hz / base);
export const hzDe = (semis: number, base: number) => base * Math.pow(2, semis / 12);

/** Acumula cuadros de voz y resume la práctica de un ejercicio. */
export class Medidor {
  cuadros = 0; conVoz = 0; dentro = 0; octava = 0; f0: number[] = []; errores: number[] = [];

  agregar(hz: number | null, objetivoHz: number, tolCents: number) {
    this.cuadros++;
    if (hz == null) return;
    this.conVoz++;
    this.f0.push(hz);
    const c = 1200 * Math.log2(hz / objetivoHz);
    this.errores.push(c);
    if (Math.abs(c) <= tolCents) this.dentro++;
    else if (Math.abs(Math.abs(c) - 1200) <= tolCents) this.octava++;
  }

  resumen(duracionS: number, repeticiones: number) {
    const r1 = (v: number) => Math.round(v * 10) / 10;
    const ord = [...this.f0].sort((a, b) => a - b);
    const med = ord.length ? ord[Math.floor(ord.length / 2)] : null;
    const prom = this.errores.length ? this.errores.reduce((a, b) => a + b, 0) / this.errores.length : 0;
    const sd = this.errores.length > 1
      ? Math.sqrt(this.errores.reduce((a, b) => a + (b - prom) ** 2, 0) / (this.errores.length - 1)) : null;
    return {
      repeticiones,
      dentro_pct: this.conVoz ? r1((100 * this.dentro) / this.conVoz) : null,
      voz_pct: this.cuadros ? r1((100 * this.conVoz) / this.cuadros) : null,
      octava_pct: this.conVoz ? r1((100 * this.octava) / this.conVoz) : null,
      f0_mediana_hz: med != null ? r1(med) : null,
      f0_min_hz: ord.length ? r1(ord[Math.floor(ord.length * 0.05)]) : null,
      f0_max_hz: ord.length ? r1(ord[Math.min(ord.length - 1, Math.floor(ord.length * 0.95))]) : null,
      desvio_cents: sd != null ? Math.round(sd) : null,
      duracion_s: r1(duracionS),
    };
  }
}

/** Timbre con armónicos (tipo voz/órgano): el parlante del celular no
 *  reproduce bien una senoidal grave y se escucha otra nota o nada. */
export function crearTimbre(ctx: AudioContext): PeriodicWave {
  const n = 10, real = new Float32Array(n), imag = new Float32Array(n);
  for (let k = 1; k < n; k++) imag[k] = 1 / Math.pow(k, 1.1);
  return ctx.createPeriodicWave(real, imag);
}

/** Toca el camino del ejercicio (modelo para escuchar) desde t0. Devuelve la duración. */
export function tocarCamino(ctx: AudioContext, e: Ejercicio, t0: number, volumen = 0.22): number {
  const d = duracion(e);
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.setPeriodicWave(crearTimbre(ctx));
  const f = o.frequency, gg = g.gain;
  gg.setValueAtTime(0, t0); gg.linearRampToValueAtTime(volumen, t0 + 0.06);
  if (e.guia === 'sostenida') {
    f.setValueAtTime(e.base_hz, t0);
  } else if (e.guia === 'rampa') {
    f.setValueAtTime(e.base_hz, t0);
    f.exponentialRampToValueAtTime(hzDe(e.amplitud || 7, e.base_hz), t0 + d / 2);
    f.exponentialRampToValueAtTime(e.base_hz, t0 + d);
  } else {
    const ns = e.nota_s || 1.2;
    (e.semitonos || [0]).forEach((s, i) => {
      const ti = t0 + i * ns;
      f.setValueAtTime(hzDe(s, e.base_hz), ti);
      if (i > 0) { gg.setValueAtTime(volumen * 0.55, ti); gg.linearRampToValueAtTime(volumen, ti + 0.08); }
    });
  }
  gg.setValueAtTime(volumen, t0 + d - 0.08); gg.linearRampToValueAtTime(0, t0 + d);
  o.connect(g).connect(ctx.destination);
  o.start(t0); o.stop(t0 + d + 0.05);
  return d;
}

/** Nota sola con el mismo timbre (nota de inicio). */
export function tocarNota(ctx: AudioContext, hz: number, seg = 2, volumen = 0.25) {
  const o = ctx.createOscillator(), g = ctx.createGain(), t0 = ctx.currentTime + 0.02;
  o.setPeriodicWave(crearTimbre(ctx)); o.frequency.value = hz;
  g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(volumen, t0 + 0.06);
  g.gain.setValueAtTime(volumen, t0 + seg - 0.15); g.gain.linearRampToValueAtTime(0, t0 + seg);
  o.connect(g).connect(ctx.destination); o.start(t0); o.stop(t0 + seg + 0.05);
}

/** Clic corto de cuenta regresiva. */
export function clic(ctx: AudioContext, t: number, agudo = false) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.frequency.value = agudo ? 1320 : 880;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.3, t + 0.005); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.09);
  o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + 0.1);
}

/** Distancia en semitonos y si parece un error de octava. */
export function compararTono(hz: number, objetivo: number) {
  const st = semisDe(hz, objetivo);
  return { st, octava: Math.abs(Math.abs(st) - 12) <= 1.5 ? (st > 0 ? 'arriba' : 'abajo') : null };
}
