/**
 * Indicaciones habladas de la práctica guiada.
 *
 * 1. Si el profesional grabó la frase con su voz, suena esa grabación.
 * 2. Si no, la voz más natural del dispositivo en español (prefiere las
 *    voces "naturales"/neuronales y las de Argentina o Latinoamérica).
 *
 * `decir` devuelve una promesa que se resuelve CUANDO TERMINA de sonar: así
 * el micrófono nunca mide mientras suena una indicación (si no, el tono de la
 * voz sintetizada se mezclaba con el del paciente y se leía una octava arriba).
 */
export type Fuente = (clave: string) => Promise<ArrayBuffer | null>;

const PREFERIDAS = [/natural|neural|online|enhanced|premium/i];
const IDIOMAS = ['es-AR', 'es-419', 'es-US', 'es-MX', 'es-UY', 'es-CL', 'es-CO', 'es-ES', 'es'];

export function mejorVoz(): SpeechSynthesisVoice | null {
  if (!('speechSynthesis' in window)) return null;
  const voces = window.speechSynthesis.getVoices().filter(v => v.lang?.toLowerCase().startsWith('es'));
  if (!voces.length) return null;
  const puntaje = (v: SpeechSynthesisVoice) => {
    const idioma = IDIOMAS.findIndex(l => v.lang.toLowerCase() === l.toLowerCase() || v.lang.toLowerCase().startsWith(l.toLowerCase()));
    return (PREFERIDAS.some(r => r.test(v.name)) ? 0 : 100) + (idioma < 0 ? 50 : idioma) + (v.localService ? 0 : -1);
  };
  return [...voces].sort((a, b) => puntaje(a) - puntaje(b))[0];
}

export class Locutor {
  private clips = new Map<string, AudioBuffer>();
  private sonando: AudioBufferSourceNode | null = null;
  activo = true;
  constructor(private ctx: () => AudioContext, private fuente: Fuente | null, private claves: string[] = []) {
    try { window.speechSynthesis?.getVoices(); } catch {}
  }

  /** Descarga y decodifica las frases grabadas (una vez). */
  async precargar() {
    if (!this.fuente) return;
    await Promise.all(this.claves.map(async c => {
      try {
        const datos = await this.fuente!(c);
        if (datos) this.clips.set(c, await this.ctx().decodeAudioData(datos.slice(0)));
      } catch {}
    }));
  }

  tiene(clave: string) { return this.clips.has(clave); }

  /** Las frases van en fila: una nueva NUNCA corta a la que está sonando,
   *  espera a que termine. Solo `callar()` (salir del ejercicio) interrumpe. */
  private fila: Promise<void> = Promise.resolve();
  private generacion = 0;

  /** Dice la frase y espera a que termine (más un margen de silencio). */
  decir(clave: string, texto: string, margenMs = 250): Promise<void> {
    const gen = this.generacion;
    const p = this.fila.then(() => (gen === this.generacion ? this.sonar(clave, texto, margenMs, gen) : undefined));
    this.fila = p.catch(() => {});
    return p;
  }

  private async sonar(clave: string, texto: string, margenMs: number, gen: number): Promise<void> {
    if (!this.activo) return;
    const clip = this.clips.get(clave);
    if (clip) {
      await new Promise<void>(res => {
        const ctx = this.ctx();
        const s = ctx.createBufferSource(), g = ctx.createGain();
        g.gain.value = 1;
        s.buffer = clip; s.connect(g).connect(ctx.destination);
        s.onended = () => { this.sonando = null; res(); };
        this.sonando = s;
        s.start();
        setTimeout(res, clip.duration * 1000 + 500);  // por si onended no llega
      });
    } else if ('speechSynthesis' in window && texto) {
      // Si la frase anterior todavía suena (el navegador no avisó el final), se le da
      // un momento para terminar; recién ahí se limpia el motor de voz.
      for (let i = 0; i < 15 && window.speechSynthesis.speaking; i++) await new Promise(r => setTimeout(r, 100));
      try { window.speechSynthesis.cancel(); } catch {}
      if (gen !== this.generacion) return;
      await new Promise<void>(res => {
        try {
          const u = new SpeechSynthesisUtterance(texto);
          const v = mejorVoz();
          if (v) { u.voice = v; u.lang = v.lang; } else u.lang = 'es-AR';
          u.rate = 0.95; u.pitch = 1;
          let listo = false;
          const s = window.speechSynthesis;
          const t0 = Date.now();
          let vigia: ReturnType<typeof setInterval> | undefined;
          let tope: ReturnType<typeof setTimeout> | undefined;
          const fin = () => { if (!listo) { listo = true; clearInterval(vigia); clearTimeout(tope); res(); } };
          u.onend = fin; u.onerror = fin;
          s.speak(u);
          // Algunos navegadores no avisan el final: se vigila que realmente haya
          // dejado de hablar, en vez de suponer una duración (antes se cortaban
          // las frases largas porque arrancaba la cuenta o la frase siguiente).
          vigia = setInterval(() => { if (Date.now() - t0 > 600 && !s.speaking && !s.pending) fin(); }, 120);
          // Red de seguridad si el navegador nunca avisa: ~85 ms por letra a esta velocidad, con holgura.
          tope = setTimeout(fin, 1800 + texto.length * 85);
        } catch { res(); }
      });
    }
    await new Promise(r => setTimeout(r, margenMs));
  }

  callar() {
    this.generacion++;   // lo que estaba en fila ya no suena
    try { window.speechSynthesis?.cancel(); } catch {}
    try { this.sonando?.stop(); } catch {}
    this.sonando = null;
  }
}
