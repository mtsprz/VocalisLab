/**
 * Camino de cada ejercicio de práctica guiada y métricas de la sesión.
 * Todo en semitonos respecto del tono base del ejercicio.
 */
export type Medida = 'tono' | 'sostenido' | 'flujo' | 'intensidad' | 'pulsos' | 'libre';
export type Ejercicio = {
  bank_id?: string | null; nombre: string; guia: 'sostenida' | 'escalera' | 'rampa' | 'patron';
  base_hz: number; consigna?: string; repeticiones: number; tolerancia_cents: number;
  duracion_s?: number; amplitud?: number; semitonos?: number[]; nota_s?: number;
  medida?: Medida; modelo?: 'sonoro' | 'sin_modelo'; con_tono?: boolean;
  duracion_objetivo_s?: number; margen_db?: number; patron_intensidad?: 'pareja' | 'arco';
  pulsos?: number; tempo_bpm?: number;
};

export const medidaDe = (e: Ejercicio): Medida => e.medida || 'tono';
/** El ejercicio tiene altura objetivo (camino de notas). */
export const usaTono = (e: Ejercicio) => medidaDe(e) === 'tono' || (medidaDe(e) === 'sostenido' && !!e.con_tono);

/** Duración de una pasada del ejercicio, en segundos. */
export function duracion(e: Ejercicio): number {
  const m = medidaDe(e);
  if (m === 'pulsos') return (e.pulsos || 6) * 60 / (e.tempo_bpm || 80) + 0.6;
  if (m === 'sostenido' || m === 'flujo' || m === 'libre') return e.duracion_objetivo_s || e.duracion_s || (m === 'libre' ? 20 : 8);
  if (m === 'intensidad') return e.duracion_s || 8;
  if (e.guia === 'escalera' || e.guia === 'patron') return (e.semitonos?.length || 1) * (e.nota_s || 1.2);
  return e.duracion_s || 6;
}

/** Intensidad objetivo (dB respecto de su nivel cómodo) en el segundo t. */
export function objetivoDb(e: Ejercicio, t: number): number {
  if (e.patron_intensidad !== 'arco') return 0;
  const u = Math.min(Math.max(t / duracion(e), 0), 1);
  return -4 + 10 * Math.sin(Math.PI * u);   // suave, +6 dB en el medio, suave
}

/** Momentos (s) de cada pulso dentro de la pasada. */
export function tiemposPulsos(e: Ejercicio): number[] {
  const p = 60 / (e.tempo_bpm || 80);
  return Array.from({ length: e.pulsos || 6 }, (_, i) => 0.3 + i * p);
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

/**
 * Analizador de una práctica: no solo la altura. Registra cuándo hay sonido
 * (sobre el ruido del lugar), su intensidad y estabilidad, cortes, tramo más
 * largo, pulsos y su regularidad, cuánto del sonido tiene altura medible
 * (periodicidad) y, si corresponde, la precisión tonal. Si el sonido es ruido
 * sin altura (tubo en agua, fricativas), la altura se marca «no medible» y no
 * cuenta como error.
 */
export class Analizador {
  private cuadros = 0; private sonando = 0; private conTono = 0; private dentroTono = 0; private octava = 0;
  private dentroDb = 0; private dbs: number[] = []; private f0: number[] = []; private errCents: number[] = [];
  private tramo = 0; private tramoMax = 0; private silencio = 0; private cortes = 0; private huboSonido = false;
  private enPulso = false; private onsets: number[] = []; private dt: number;
  constructor(private e: Ejercicio, private ambiente: number, private referencia: number, dtSeg = 0.04) { this.dt = dtSeg; }

  umbralSonido() { return Math.max(this.ambiente + 6, -62); }

  /** Un cuadro: t (s), hz (null sin altura), db (dBFS). Devuelve el estado para la pantalla. */
  cuadro(t: number, hz: number | null, db: number) {
    this.cuadros++;
    const suena = db > this.umbralSonido();
    const r: any = { suena, dbRel: db - this.referencia, dentroTono: null as boolean | null, dentroDb: null as boolean | null, cents: 0 };
    // Pulsos: ataque con histéresis (sube 10 dB sobre el ambiente, baja a 5 dB).
    if (!this.enPulso && db > Math.max(this.ambiente + 10, -55)) {
      if (!this.onsets.length || t - this.onsets[this.onsets.length - 1] > 0.12) this.onsets.push(t);
      this.enPulso = true; r.pulso = true;
    } else if (this.enPulso && db < this.ambiente + 5) this.enPulso = false;
    if (suena) {
      this.sonando++; this.huboSonido = true; this.dbs.push(db - this.ambiente);
      // Un hueco menor a 0,2 s (burbujeo, micro-baches) no corta el tramo.
      if (this.silencio >= 0.2) { this.cortes++; this.tramo = 0; } else this.tramo += this.silencio;
      this.silencio = 0; this.tramo += this.dt; this.tramoMax = Math.max(this.tramoMax, this.tramo);
      if (hz) {
        this.conTono++; this.f0.push(hz);
        if (usaTono(this.e)) {
          const obj = hzDe(objetivoSemis(this.e, t), this.e.base_hz);
          const c = 1200 * Math.log2(hz / obj); r.cents = c;
          this.errCents.push(c);
          r.dentroTono = Math.abs(c) <= this.e.tolerancia_cents;
          if (r.dentroTono) this.dentroTono++;
          else if (Math.abs(Math.abs(c) - 1200) <= this.e.tolerancia_cents) { this.octava++; r.octava = true; }
        }
      }
      const margen = this.e.margen_db || 6;
      r.dentroDb = Math.abs((db - this.referencia) - objetivoDb(this.e, t)) <= margen;
      if (r.dentroDb) this.dentroDb++;
    } else {
      if (this.huboSonido) this.silencio += this.dt;
      if (this.silencio >= 0.2) this.tramo = 0;
    }
    return r;
  }

  /** Separa repeticiones: el silencio entre ellas no es un corte. */
  nuevaRepeticion() { this.silencio = 0; this.tramo = 0; this.huboSonido = false; this.enPulso = false; }

  resumen(duracionS: number, repeticiones: number) {
    const r1 = (v: number) => Math.round(v * 10) / 10;
    const pct = (a: number, b: number) => (b ? r1((100 * a) / b) : null);
    const ord = [...this.f0].sort((a, b) => a - b), od = [...this.dbs].sort((a, b) => a - b);
    const q = (a: number[], p: number) => a[Math.min(a.length - 1, Math.floor(a.length * p))];
    const media = od.length ? od.reduce((a, b) => a + b, 0) / od.length : null;
    const sdDb = od.length > 1 && media != null ? Math.sqrt(od.reduce((a, b) => a + (b - media) ** 2, 0) / (od.length - 1)) : null;
    const pe = this.errCents.length ? this.errCents.reduce((a, b) => a + b, 0) / this.errCents.length : 0;
    const sdC = this.errCents.length > 1 ? Math.sqrt(this.errCents.reduce((a, b) => a + (b - pe) ** 2, 0) / (this.errCents.length - 1)) : null;
    const iv = this.onsets.slice(1).map((x, i) => x - this.onsets[i]).filter(x => x < 3);
    const mi = iv.length ? iv.reduce((a, b) => a + b, 0) / iv.length : 0;
    const cv = iv.length > 1 && mi ? Math.sqrt(iv.reduce((a, b) => a + (b - mi) ** 2, 0) / (iv.length - 1)) / mi : null;
    const periodicidad = pct(this.conTono, this.sonando);
    const m = medidaDe(this.e);
    const alturaNoMedible = usaTono(this.e) && this.sonando > 10 && (periodicidad || 0) < 40;
    const objetivo = duracion(this.e);
    const sonidoS = this.sonando * this.dt;
    let logro: number | null = null;
    if (m === 'tono') logro = alturaNoMedible ? pct(Math.min(sonidoS, objetivo * repeticiones), objetivo * repeticiones) : pct(this.dentroTono, this.conTono);
    else if (m === 'sostenido' || m === 'flujo') logro = r1(Math.min(100, (this.tramoMax / objetivo) * 100) * (this.cortes > repeticiones * 2 ? 0.85 : 1));
    else if (m === 'intensidad') logro = pct(this.dentroDb, this.sonando);
    else if (m === 'pulsos') {
      const esperados = (this.e.pulsos || 6) * repeticiones;
      logro = r1(Math.min(100, (this.onsets.length / esperados) * 100) * (cv != null ? Math.max(0.5, 1 - cv) : 1));
    } else logro = pct(this.sonando, this.cuadros);
    return {
      medida: m, repeticiones, logro_pct: logro,
      dentro_pct: usaTono(this.e) && !alturaNoMedible ? pct(this.dentroTono, this.conTono) : null,
      octava_pct: usaTono(this.e) && !alturaNoMedible ? pct(this.octava, this.conTono) : null,
      f0_mediana_hz: ord.length >= 5 ? r1(q(ord, 0.5)) : null,
      f0_min_hz: ord.length >= 5 ? r1(q(ord, 0.05)) : null,
      f0_max_hz: ord.length >= 5 ? r1(q(ord, 0.95)) : null,
      desvio_cents: sdC != null && !alturaNoMedible ? Math.round(sdC) : null,
      altura_no_medible: alturaNoMedible,
      voz_pct: pct(this.sonando, this.cuadros),
      periodicidad_pct: periodicidad,
      sonido_s: r1(sonidoS), tramo_max_s: r1(this.tramoMax), cortes: this.cortes,
      intensidad_media_db: media != null ? r1(media) : null,
      intensidad_rango_db: od.length >= 5 ? r1(q(od, 0.95) - q(od, 0.05)) : null,
      intensidad_sd_db: sdDb != null ? r1(sdDb) : null,
      intensidad_dentro_pct: m === 'intensidad' || m === 'sostenido' || m === 'flujo' ? pct(this.dentroDb, this.sonando) : null,
      pulsos: this.onsets.length,
      pulsos_regularidad_pct: cv != null ? r1(Math.max(0, 100 * (1 - cv))) : null,
      duracion_s: r1(duracionS),
    };
  }
}
