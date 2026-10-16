"""Vocalis Companion — transcripción con separación de voces y altura tonal en el servidor.

Tres piezas, usadas por `companion._process_job`:

1. `procesar()`: transcribe y separa hablantes. Dos caminos:
   - AssemblyAI (si ASSEMBLYAI_API_KEY): diarización neuronal del proveedor.
     Tras leer el resultado se BORRA la transcripción allá (privacidad).
   - Sin clave: Whisper (Groq) con tiempos por palabra → turnos cortados en
     las pausas → huella vocal de cada turno (CAM++, el mismo modelo que el
     teléfono, sherpa-onnx) → agrupamiento en 2 voces (k-medias coseno).
2. `asignar_roles()`: decide qué hablante (A/B…) es el fonoaudiólogo/a por
   voto ponderado de tres evidencias independientes:
     - IA por contenido (consignas/preguntas vs. respuestas/síntomas),
     - tramos del teléfono (huella vocal "Mi voz"), si los hay,
     - altura tonal de cada hablante vs. el perfil "Mi voz" (Praat).
   Se guarda el método y si las evidencias coincidieron.
3. `acustica_si_falta()`: si la sesión no trae altura tonal (audio importado
   o grabado en la web), la calcula con Praat (autocorrelación, paso 10 ms)
   SOLO sobre los tramos del paciente. Mismo formato que el teléfono:
   mediana, media, SD Hz/semitonos, p5–p95, histograma por semitono y contorno.
   Si el teléfono ya mandó acústica, se respeta la del teléfono.
"""
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
import wave

DSP_VERSION = "servidor-praat/1.0"
TAREA = "conversacion_espontanea"
LIMITE_WHISPER = 20 * 1024 * 1024

# Vocabulario de consultorio: mejora la transcripción de términos técnicos.
TERMINOS = [
    "fonoaudiología", "fonoaudióloga", "fonoaudiólogo", "disfonía", "afonía",
    "nódulos", "pólipo", "edema de Reinke", "laringe", "pliegues vocales",
    "cuerdas vocales", "glotis", "hiperfunción", "fatiga vocal", "carraspeo",
    "reflujo", "otorrinolaringólogo", "laringoscopía", "estroboscopía",
    "resonancia", "tracto vocal semiocluido", "tubo de resonancia",
    "vibración de labios", "apoyo respiratorio", "respiración costodiafragmática",
    "vocalización", "sirenas", "glissando", "hidratación", "higiene vocal",
    "altura tonal", "intensidad", "timbre", "voz soplada", "voz áspera",
    "tiempo máximo de fonación", "vocal sostenida", "presbifonía", "muda vocal",
]


def disponible() -> bool:
    return bool(os.environ.get("ASSEMBLYAI_API_KEY", "").strip())


def _base() -> str:
    return os.environ.get("ASSEMBLYAI_BASE_URL", "https://api.assemblyai.com").rstrip("/")


# ─── Audio ───
def _ffmpeg() -> str:
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("ffmpeg no disponible en el servidor")


def _convertir(src: str, sufijo: str, args: list) -> str:
    dst = tempfile.NamedTemporaryFile(suffix=sufijo, delete=False).name
    r = subprocess.run([_ffmpeg(), "-y", "-i", src, "-vn", "-map_metadata", "-1", *args, dst],
                       capture_output=True, timeout=900)
    if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 100:
        try:
            os.unlink(dst)
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg falló: {r.stderr.decode(errors='ignore')[-300:]}")
    return dst


def a_wav(src: str, sr: int = 16000) -> str:
    """WAV PCM16 mono (para Praat). Acepta m4a/mp3/webm/ogg/wav."""
    return _convertir(src, ".wav", ["-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le"])


def compacto(src: str) -> str:
    """AAC mono 16 kHz 32 kb/s: 30 min ≈ 7 MB (cabe en Whisper y sube rápido).
    Solo para transcribir; la altura tonal se mide sobre el WAV sin comprimir."""
    return _convertir(src, ".m4a", ["-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "32k"])


def duracion(wav_path: str) -> float:
    with wave.open(wav_path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


# ─── AssemblyAI ───
def transcribir_assemblyai(path: str, timeout_s: int = 1800) -> list:
    """[{speaker:'A', start, end, text}] en segundos."""
    import httpx
    h = {"authorization": os.environ.get("ASSEMBLYAI_API_KEY", "").strip()}
    with open(path, "rb") as f:
        up = httpx.post(f"{_base()}/v2/upload", headers=h, content=f.read(), timeout=600)
    up.raise_for_status()
    body = {
        "audio_url": up.json()["upload_url"],
        "language_code": "es",
        "speaker_labels": True,
        "speakers_expected": 2,
        "punctuate": True,
        "format_text": True,
        "keyterms_prompt": TERMINOS,
    }
    r = httpx.post(f"{_base()}/v2/transcript", headers=h, json=body, timeout=60)
    if r.status_code == 400 and "keyterms" in r.text:
        body.pop("keyterms_prompt")   # modelo sin soporte de vocabulario
        r = httpx.post(f"{_base()}/v2/transcript", headers=h, json=body, timeout=60)
    r.raise_for_status()
    tid = r.json()["id"]
    t0 = time.time()
    try:
        while True:
            g = httpx.get(f"{_base()}/v2/transcript/{tid}", headers=h, timeout=60).json()
            st = g.get("status")
            if st == "completed":
                break
            if st == "error":
                raise RuntimeError(f"AssemblyAI: {g.get('error')}")
            if time.time() - t0 > timeout_s:
                raise RuntimeError("AssemblyAI: tiempo agotado")
            time.sleep(4)
    finally:
        try:   # no dejar audio ni texto del paciente en el proveedor
            httpx.delete(f"{_base()}/v2/transcript/{tid}", headers=h, timeout=30)
        except Exception:
            pass
    out = []
    for u in (g.get("utterances") or []):
        txt = (u.get("text") or "").strip()
        if txt:
            out.append({"speaker": str(u.get("speaker") or "A"),
                        "start": float(u.get("start") or 0) / 1000.0,
                        "end": float(u.get("end") or 0) / 1000.0, "text": txt})
    if not out and (g.get("text") or "").strip():
        out.append({"speaker": "A", "start": 0.0,
                    "end": float(g.get("audio_duration") or 0), "text": g["text"].strip()})
    return out


# ─── Whisper con tiempos por palabra (Groq) ───
def transcribir_whisper(path: str) -> list:
    """Turnos [{start, end, text}]: cada segmento de Whisper se corta donde
    hay una pausa ≥ 0,6 s entre palabras (allí suele cambiar el hablante)."""
    import httpx
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY ausente")
    with open(path, "rb") as f:
        datos = f.read()
    ultimo = None
    for intento in range(3):
        try:
            r = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                data={"model": "whisper-large-v3", "language": "es",
                      "response_format": "verbose_json", "temperature": "0",
                      "prompt": "Sesión de fonoaudiología: " + ", ".join(TERMINOS[:25]),
                      "timestamp_granularities[]": ["segment", "word"]},
                files={"file": ("audio.m4a", datos, "audio/mp4")},
                timeout=600)
            r.raise_for_status()
            d = r.json()
            break
        except Exception as e:
            ultimo = e
            time.sleep(3 * (intento + 1))
    else:
        raise RuntimeError(f"Whisper falló: {ultimo}")
    palabras = [w for w in (d.get("words") or []) if w.get("end") is not None]
    turnos = []
    for s in (d.get("segments") or []):
        a, b = float(s.get("start", 0)), float(s.get("end", 0))
        ws = [w for w in palabras if a - 0.05 <= float(w["start"]) < b]
        cortes, actual = [], []
        for w in ws:
            if actual and float(w["start"]) - float(actual[-1]["end"]) >= 0.6:
                cortes.append(actual)
                actual = []
            actual.append(w)
        if actual:
            cortes.append(actual)
        if len(cortes) <= 1:
            txt = (s.get("text") or "").strip()
            if txt:
                turnos.append({"start": a, "end": b, "text": txt})
        else:
            for c in cortes:
                txt = " ".join(str(w.get("word", "")).strip() for w in c).strip()
                if txt:
                    turnos.append({"start": float(c[0]["start"]), "end": float(c[-1]["end"]),
                                   "text": txt})
    if not turnos and (d.get("text") or "").strip():
        turnos.append({"start": 0.0, "end": float(d.get("duration") or 0), "text": d["text"].strip()})
    return turnos


# ─── Huella vocal (CAM++) y agrupamiento en 2 voces ───
_EXTRACTOR = None


def _ruta_modelo() -> str:
    for c in (os.environ.get("CAMPP_MODEL", ""),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "campplus_sv_16k.onnx"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "companion", "assets",
                           "models", "campplus_sv_16k.onnx")):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("Modelo de huella vocal (campplus_sv_16k.onnx) no encontrado")


def _extractor():
    global _EXTRACTOR
    if _EXTRACTOR is None:
        import sherpa_onnx
        cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=_ruta_modelo(), num_threads=1, debug=False, provider="cpu")
        if not cfg.validate():
            raise RuntimeError("Configuración de huella vocal inválida")
        _EXTRACTOR = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
    return _EXTRACTOR


def huellas(wav_path: str, turnos: list, min_seg: float = 0.7, max_seg: float = 8.0) -> list:
    """Vector unitario por turno (None si el turno es muy corto)."""
    import numpy as np
    ext = _extractor()
    out = []
    with wave.open(wav_path, "rb") as w:
        sr, total = w.getframerate(), w.getnframes()
        for t in turnos:
            a, b = float(t["start"]), float(t["end"])
            if b - a < min_seg:
                out.append(None)
                continue
            if b - a > max_seg:   # el centro del turno: menos riesgo de solape
                m = (a + b) / 2
                a, b = m - max_seg / 2, m + max_seg / 2
            i0, i1 = max(0, int(a * sr)), min(total, int(b * sr))
            w.setpos(i0)
            x = np.frombuffer(w.readframes(i1 - i0), dtype="<i2").astype(np.float32) / 32768.0
            st = ext.create_stream()
            st.accept_waveform(sr, x)
            st.input_finished()
            if not ext.is_ready(st):
                out.append(None)
                continue
            v = np.array(ext.compute(st), dtype=np.float32)
            n = float(np.linalg.norm(v))
            out.append(v / n if n > 0 else None)
    return out


def agrupar_dos(vecs: list, pesos: list) -> tuple:
    """k-medias coseno (k=2), iniciado con el par más distante. Devuelve
    (etiquetas 'A'/'B'/None, similitud entre centros)."""
    import numpy as np
    idx = [i for i, v in enumerate(vecs) if v is not None]
    if len(idx) < 4:
        return [("A" if v is not None else None) for v in vecs], 1.0
    X = np.stack([vecs[i] for i in idx])
    W = np.array([max(0.3, pesos[i]) for i in idx])
    # Par más distante sobre una muestra (rápido aun con 1000 turnos).
    muestra = X[:: max(1, len(X) // 300)]
    s = muestra @ muestra.T
    i, j = np.unravel_index(np.argmin(s), s.shape)
    c = np.stack([muestra[i], muestra[j]])
    for _ in range(20):
        lab = np.argmax(X @ c.T, axis=1)
        nuevo = []
        for k in (0, 1):
            m = (X[lab == k] * W[lab == k, None]).sum(axis=0) if (lab == k).any() else c[k]
            nuevo.append(m / (np.linalg.norm(m) or 1.0))
        nuevo = np.stack(nuevo)
        if np.allclose(nuevo, c, atol=1e-5):
            break
        c = nuevo
    etiquetas = [None] * len(vecs)
    for pos, k in zip(idx, lab):
        etiquetas[pos] = "AB"[int(k)]
    return etiquetas, float(c[0] @ c[1])


def _rellenar(etiquetas: list, turnos: list) -> list:
    """Turnos muy cortos ("sí", "ajá"): toman la voz del turno más cercano."""
    out = list(etiquetas)
    con = [i for i, e in enumerate(etiquetas) if e]
    for i, e in enumerate(etiquetas):
        if e or not con:
            continue
        cerca = min(con, key=lambda k: abs(float(turnos[k]["start"]) - float(turnos[i]["start"])))
        out[i] = etiquetas[cerca]
    return [e or "A" for e in out]


def diarizar_whisper(prep: dict) -> tuple:
    """(utterances [{speaker, start, end, text}], info del agrupamiento)."""
    turnos = transcribir_whisper(prep["compacto"])
    if not turnos:
        return [], {}
    vecs = huellas(prep["wav"], turnos)
    pesos = [float(t["end"]) - float(t["start"]) for t in turnos]
    etiquetas, sim = agrupar_dos(vecs, pesos)
    etiquetas = _rellenar(etiquetas, turnos)
    utts = [dict(t, speaker=e) for t, e in zip(turnos, etiquetas)]
    # Fusionar turnos contiguos de la misma voz (lectura más clara).
    fusion = []
    for u in utts:
        if fusion and fusion[-1]["speaker"] == u["speaker"] and u["start"] - fusion[-1]["end"] < 1.0 \
                and fusion[-1]["end"] - fusion[-1]["start"] < 25:
            fusion[-1]["end"] = u["end"]
            fusion[-1]["text"] = (fusion[-1]["text"] + " " + u["text"]).strip()
        else:
            fusion.append(dict(u))
    return fusion, {"proveedor": "whisper+huella_campp", "similitud_centros": round(sim, 3),
                    "turnos": len(turnos)}


# ─── LLM con respaldo (Gemini ↔ Groq) ───
def llm_json(prompt: str, max_tokens: int = 4000) -> dict:
    """JSON del primer proveedor que responda. Gemini primero para textos
    largos (cuota por minuto mayor); Groq (varios modelos) de respaldo."""
    errores = []
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        import httpx
        modelos = [m for m in (os.environ.get("AI_MODEL", ""), "gemini-2.5-flash", "gemini-2.0-flash")
                   if m and m.startswith("gemini")]
        for m in dict.fromkeys(modelos):
            try:
                r = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}",
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                               "maxOutputTokens": max_tokens}},
                    timeout=180)
                cands = r.json().get("candidates") or []
                parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
                txt = "".join(p.get("text", "") for p in parts)
                d = _json_de(txt)
                if d:
                    return d
                errores.append(f"{m}: sin JSON ({r.status_code})")
            except Exception as e:
                errores.append(f"{m}: {e}")
    if os.environ.get("GROQ_API_KEY", "").strip():
        try:
            from llm_client import groq_chat
            txt, _modelo = groq_chat([{"role": "user", "content": prompt}], temperature=0.0,
                                     max_tokens=max_tokens, response_format={"type": "json_object"},
                                     timeout=180)
            d = _json_de(txt)
            if d:
                return d
            errores.append("groq: sin JSON")
        except Exception as e:
            errores.append(f"groq: {e}")
    raise RuntimeError("Ningún LLM respondió: " + " | ".join(errores)[:500])


def _json_de(txt: str) -> dict:
    m = re.search(r"\{.*\}", txt or "", re.DOTALL)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# ─── Altura tonal (Praat) ───
def rango_busqueda(sexo: str, edad) -> tuple:
    """Mismo rango que el teléfono (yin.dart: configParaSexo)."""
    if edad is not None and edad <= 12:
        return 150.0, 600.0
    s = (sexo or "").lower()
    if s.startswith(("masc", "varon", "varón")) or s == "m":
        return 75.0, 300.0
    if s.startswith(("fem", "mujer")) or s == "f":
        return 100.0, 500.0
    return 75.0, 600.0


def f0_cuadros(wav_path: str, intervalos: list, floor: float, ceiling: float) -> list:
    """F0 cada 10 ms (0 = sordo) sobre los intervalos [(a, b)] en segundos.
    Lee cada tramo por separado: memoria acotada aunque la sesión dure 1 h."""
    import numpy as np
    import parselmouth
    out = []
    # Tramos largos en piezas de ≤30 s: memoria acotada (Render 512 MB).
    piezas = []
    for a, b in intervalos:
        while b - a > 30.0:
            piezas.append((a, a + 30.0))
            a += 30.0
        piezas.append((a, b))
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        total = w.getnframes()
        for a, b in piezas:
            i0, i1 = max(0, int(a * sr)), min(total, int(b * sr))
            if (i1 - i0) < int(sr * 3.0 / floor) + 1:
                continue
            w.setpos(i0)
            x = np.frombuffer(w.readframes(i1 - i0), dtype="<i2").astype(np.float64) / 32768.0
            snd = parselmouth.Sound(x, sampling_frequency=sr)
            p = snd.to_pitch_ac(time_step=0.01, pitch_floor=floor, pitch_ceiling=ceiling)
            out.extend(float(v) for v in p.selected_array["frequency"])
    return out


def _mediana(v: list) -> float:
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def metricas(cuadros: list) -> dict:
    """Espejo de metrics.dart (computeTaskMetrics) para filas comparables."""
    sonoros = [f for f in cuadros if f > 0]
    vf = (len(sonoros) / len(cuadros)) if cuadros else 0.0
    contorno = [round(cuadros[i], 2) if cuadros[i] > 0 else 0.0 for i in range(0, len(cuadros), 5)]
    fila = {"task_type": TAREA, "voiced_fraction": round(vf, 4), "f0_contour": contorno[:20000],
            "dsp_version": DSP_VERSION, "validada": True,
            "intensity_mean_db": None, "intensity_sd_db": None, "mpt_sec": None,
            "jitter_pct": None, "shimmer_pct": None, "hnr_db": None}
    if not sonoros:
        fila.update({k: None for k in ("f0_mean_hz", "f0_median_hz", "f0_sd_hz", "f0_sd_semitones",
                                       "f0_p5_hz", "f0_p95_hz", "f0_min_hz", "f0_max_hz")})
        fila["f0_histogram"] = {"ref_hz": 0, "bins": {}}
        return fila
    n = len(sonoros)
    media = sum(sonoros) / n
    med = _mediana(sonoros)
    sd = math.sqrt(sum((f - media) ** 2 for f in sonoros) / n)
    sts = [12 * math.log2(f / med) for f in sonoros]
    stm = sum(sts) / n
    sd_st = math.sqrt(sum((s - stm) ** 2 for s in sts) / n)
    s = sorted(sonoros)
    pct = lambda p: s[max(0, min(n - 1, int(round((p / 100) * (n - 1)))))]
    bins = {}
    for st in sts:
        k = str(int(round(st)))
        bins[k] = bins.get(k, 0) + 1
    fila.update({"f0_mean_hz": round(media, 2), "f0_median_hz": round(med, 2),
                 "f0_sd_hz": round(sd, 2), "f0_sd_semitones": round(sd_st, 3),
                 "f0_p5_hz": round(pct(5), 2), "f0_p95_hz": round(pct(95), 2),
                 "f0_min_hz": round(s[0], 2), "f0_max_hz": round(s[-1], 2),
                 "f0_histogram": {"ref_hz": round(med, 3), "bins": bins}})
    return fila


# ─── Quién es quién ───
def _solape(a, b, c, d) -> float:
    return max(0.0, min(b, d) - max(a, c))


def _hablado(utts: list) -> dict:
    t = {}
    for u in utts:
        t[u["speaker"]] = t.get(u["speaker"], 0.0) + max(0.0, u["end"] - u["start"])
    return t


def _voto_telefono(utts: list, task_segs: list):
    """Letra del fono según los tramos del teléfono (huella "Mi voz")."""
    if not task_segs or not any(s.get("speaker") == "fonoaudiologo" for s in task_segs):
        return None
    prop = {}
    for u in utts:
        fono = pac = 0.0
        for s in task_segs:
            ov = _solape(u["start"], u["end"], float(s.get("start_sec", 0)), float(s.get("end_sec", 0)))
            if s.get("speaker") == "fonoaudiologo":
                fono += ov
            else:
                pac += ov
        f, p = prop.get(u["speaker"], (0.0, 0.0))
        prop[u["speaker"]] = (f + fono, p + pac)
    ratios = {k: f / (f + p) for k, (f, p) in prop.items() if f + p > 1.0}
    if len(ratios) < 2:
        return None
    orden = sorted(ratios.items(), key=lambda kv: -kv[1])
    margen = orden[0][1] - orden[1][1]
    return (orden[0][0], min(1.0, margen / 0.4)) if margen >= 0.15 else None


def _voto_tono(medianas: dict, fono_hz):
    """Letra cuyo tono mediano está más cerca del perfil "Mi voz"."""
    if not fono_hz or len(medianas) < 2:
        return None
    dist = {k: abs(12 * math.log2(v / fono_hz)) for k, v in medianas.items() if v}
    if len(dist) < 2:
        return None
    orden = sorted(dist.items(), key=lambda kv: kv[1])
    cerca, otro = orden[0], orden[1]
    if cerca[1] > 3.0 or (otro[1] - cerca[1]) < 1.5:
        return None   # voces de altura parecida: el tono no decide
    return cerca[0], min(1.0, (otro[1] - cerca[1]) / 4.0)


def _voto_ia(utts: list):
    """La IA lee la conversación y dice qué letra es el fonoaudiólogo/a."""
    letras = sorted({u["speaker"] for u in utts})
    # Muestra repartida a lo largo de toda la sesión (máx ~160 frases).
    paso = max(1, len(utts) // 160)
    muestra = "\n".join(f"{u['speaker']}: {u['text'][:220]}" for u in utts[::paso][:160])
    prompt = (
        "Transcripción de una sesión de fonoaudiología (terapia de voz). Cada línea es "
        "HABLANTE: texto. Hablantes: " + ", ".join(letras) + ". El FONOAUDIOLOGO/A da "
        "consignas, explica ejercicios, pregunta y evalúa; el PACIENTE responde, cuenta "
        "síntomas e historia y realiza los ejercicios. Puede haber un acompañante.\n"
        "Respondé SOLO JSON: {\"fonoaudiologo\": \"<letra>\", \"paciente\": \"<letra>\", "
        "\"confianza\": <0..1>}\n\n" + muestra)
    try:
        d = llm_json(prompt, max_tokens=300)
        f = str(d.get("fonoaudiologo") or "").strip().upper()
        if f not in letras:
            return None
        c = float(d.get("confianza") or 0.6)
        return f, max(0.0, min(1.0, c))
    except Exception:
        traceback.print_exc()
        return None


def asignar_roles(utts: list, task_segs: list, medianas: dict, fono_hz) -> tuple:
    """(mapa letra→rol, letra_paciente, info). Voto ponderado: IA 1.0,
    teléfono 0.8, tono 0.6 (× confianza de cada uno)."""
    letras = sorted({u["speaker"] for u in utts})
    hablado = _hablado(utts)
    votos = {"ia_contenido": _voto_ia(utts) if len(letras) > 1 else None,
             "huella_telefono": _voto_telefono(utts, task_segs),
             "tono_perfil": _voto_tono(medianas, fono_hz)}
    pesos = {"ia_contenido": 1.0, "huella_telefono": 0.8, "tono_perfil": 0.6}
    puntaje = {}
    for k, v in votos.items():
        if v:
            puntaje[v[0]] = puntaje.get(v[0], 0.0) + pesos[k] * v[1]
    if len(letras) == 1:
        fono = None
    elif puntaje:
        fono = max(puntaje.items(), key=lambda kv: kv[1])[0]
    else:
        fono = None
    otros = [l for l in letras if l != fono]
    pac = max(otros, key=lambda l: hablado.get(l, 0.0)) if otros else None
    usados = {k: v[0] for k, v in votos.items() if v}
    acuerdo = len(set(usados.values())) <= 1 if usados else False
    info = {"proveedor": "assemblyai", "hablantes": len(letras),
            "votos": usados, "acuerdo": acuerdo,
            "certeza": ("alta" if acuerdo and len(usados) >= 2 else
                        "media" if usados else "baja"),
            "fono": fono, "paciente": pac,
            "otros": [l for l in otros if l != pac]}
    mapa = {l: ("fonoaudiologo" if l == fono else "paciente") for l in letras}
    return mapa, pac, info


# ─── Datos del paciente / perfil ───
def _paciente(sb, pid: str) -> tuple:
    try:
        import companion as comp
        r = sb.table("pacientes").select("*").eq("id", pid).execute()
        p = (r.data or [{}])[0]
        sexo = p.get("sexo_referencia") or p.get("sexo") or ""
        return sexo, comp._edad(p.get("fecha_nacimiento") or "")
    except Exception:
        return "", None


def _fono_hz(sb, ses: dict):
    """Perfil "Mi voz": el que viajó con la sesión o el último conocido."""
    info = ses.get("device_info") or {}
    if isinstance(info, str):
        try:
            info = json.loads(info)
        except Exception:
            info = {}
    v = info.get("fono_mediana_hz")
    if v:
        return float(v)
    try:
        r = sb.table("companion_sessions").select("device_info")\
            .eq("profesional_google_id", ses.get("profesional_google_id"))\
            .order("created_at", desc=True).limit(30).execute()
        for row in (r.data or []):
            d = row.get("device_info") or {}
            if isinstance(d, dict) and d.get("fono_mediana_hz"):
                return float(d["fono_mediana_hz"])
    except Exception:
        pass
    return None


def _guardar_info(sb, ses: dict, clave: str, valor: dict):
    try:
        info = ses.get("device_info") or {}
        if not isinstance(info, dict):
            info = {}
        info = dict(info, **{clave: valor})
        sb.table("companion_sessions").update({"device_info": info}).eq("id", ses["id"]).execute()
        ses["device_info"] = info
    except Exception as e:
        print(f"[companion_voz] no se pudo guardar {clave}: {e}")


# ─── Entradas para companion._process_job ───
def preparar(audio_path: str) -> dict:
    """WAV para Praat + versión compacta para transcribir (una sola vez)."""
    wav = a_wav(audio_path)
    comp_path = compacto(audio_path)
    return {"wav": wav, "compacto": comp_path, "duracion": duracion(wav)}


def procesar(sb, ses: dict, prep: dict, task_segs: list) -> list:
    """Transcripción + hablantes → filas de session_transcripts.
    AssemblyAI si hay clave; si no, Whisper + huella vocal CAM++."""
    extra = {}
    if disponible():
        utts = transcribir_assemblyai(prep["compacto"])
        extra = {"proveedor": "assemblyai"}
    else:
        utts, extra = diarizar_whisper(prep)
    if not utts:
        return []
    # Tono mediano de cada hablante (rango amplio) para el voto por tono.
    medianas = {}
    for letra in sorted({u["speaker"] for u in utts}):
        iv = [(u["start"], u["end"]) for u in utts if u["speaker"] == letra]
        f = [x for x in f0_cuadros(prep["wav"], iv[:200], 75.0, 600.0) if x > 0]
        medianas[letra] = _mediana(f) if len(f) > 50 else None
    mapa, pac, info = asignar_roles(utts, task_segs, medianas, _fono_hz(sb, ses))
    info.update(extra)
    info["medianas_hz"] = {k: (round(v, 1) if v else None) for k, v in medianas.items()}
    # Dos "voces" casi iguales para la huella: probablemente una sola persona
    # o un audio muy reverberante; se avisa en vez de afirmar.
    if extra.get("similitud_centros", 0) > 0.85:
        info["certeza"] = "baja"
        info["aviso"] = "Las dos voces detectadas son muy parecidas: revisar la atribución."
    _guardar_info(sb, ses, "diarizacion", info)
    ses["_letra_paciente"] = pac
    ses["_utts"] = utts
    # source ∈ ('ai','manual') por CHECK de la tabla; "_otro" (acompañante)
    # se usa acá y se quita antes de insertar.
    return [{"speaker": mapa[u["speaker"]], "start_sec": u["start"], "end_sec": u["end"],
             "text": u["text"], "source": "ai",
             "_otro": u["speaker"] not in (pac, info["fono"])}
            for u in utts]


def acustica_si_falta(sb, ses: dict, prep: dict, trs: list):
    """Altura tonal del paciente con Praat si la sesión no la trae."""
    sid = ses["id"]
    ya = sb.table("session_acoustics").select("task_type, dsp_version").eq("session_id", sid).execute()
    if any(not str(a.get("dsp_version") or "").startswith("servidor-praat") for a in (ya.data or [])):
        return None   # la del teléfono manda (contrato); la del servidor se recalcula
    if ses.get("_utts") and ses.get("_letra_paciente"):
        iv = [(u["start"], u["end"]) for u in ses["_utts"] if u["speaker"] == ses["_letra_paciente"]]
    else:
        iv = [(t["start_sec"], t["end_sec"]) for t in trs if t.get("speaker") == "paciente"]
    if not iv:
        return None
    sexo, edad = _paciente(sb, ses.get("patient_id"))
    floor, ceiling = rango_busqueda(sexo, edad)
    fila = metricas(f0_cuadros(prep["wav"], iv, floor, ceiling))
    sb.table("session_acoustics").upsert(dict(fila, session_id=sid),
                                         on_conflict="session_id,task_type").execute()
    segs = sb.table("session_segments").select("id").eq("session_id", sid).limit(1).execute()
    if not segs.data:
        for t in trs:
            if t.get("_otro"):
                continue
            try:
                sb.table("session_segments").insert({
                    "session_id": sid, "task_type": TAREA, "speaker": t["speaker"],
                    "start_sec": float(t["start_sec"]), "end_sec": float(t["end_sec"])}).execute()
            except Exception:
                break
    return fila


# ─── Análisis clínico con IA (resumen de sesión + VHI) ───
# Ítems del VHI-30 (Jacobson et al., 1997; versión española Núñez-Batalla
# et al., 2007), descriptos en forma breve para que la IA los reconozca en la
# conversación. Escala 0 nunca · 1 casi nunca · 2 a veces · 3 casi siempre ·
# 4 siempre. El puntaje lo suma el servidor, no la IA.
VHI_ITEMS = {
    "F1": "la gente lo/la oye con dificultad por su voz",
    "F2": "le entienden con dificultad en lugares ruidosos",
    "F3": "su familia no lo/la oye cuando llama desde otra parte de la casa",
    "F4": "usa el teléfono menos de lo que quisiera",
    "F5": "evita grupos de personas por su voz",
    "F6": "habla menos con amigos, vecinos o familiares",
    "F7": "le piden que repita lo que dice cara a cara",
    "F8": "la voz limita su vida personal y social",
    "F9": "se siente desplazado/a de las conversaciones",
    "F10": "el problema de voz le hace perder ingresos o afecta su trabajo",
    "P1": "se queda sin aire al hablar",
    "P2": "su voz varía a lo largo del día",
    "P3": "la gente le pregunta qué le pasa en la voz",
    "P4": "la voz suena áspera, ronca o seca",
    "P5": "siente que tiene que esforzarse para que salga la voz",
    "P6": "la claridad de la voz es impredecible",
    "P7": "trata de cambiar la voz para que suene diferente",
    "P8": "se esfuerza mucho para hablar",
    "P9": "la voz empeora por la tarde o la noche",
    "P10": "la voz se corta o falla en medio de una frase",
    "E1": "se pone tenso/a al hablar con otros por su voz",
    "E2": "la gente parece irritarse con su voz",
    "E3": "siente que los demás no comprenden su problema de voz",
    "E4": "su problema de voz le molesta o preocupa",
    "E5": "sale menos por su problema de voz",
    "E6": "la voz le hace sentir discapacitado/a",
    "E7": "le molesta cuando le piden que repita",
    "E8": "le da vergüenza cuando le piden que repita",
    "E9": "la voz le hace sentir incompetente",
    "E10": "se avergüenza de su problema de voz",
}
VHI10 = ("F1", "F2", "F8", "F9", "F10", "P5", "P6", "P10", "E3", "E9")  # Rosen et al., 2004
ESCALA = {0: "nunca", 1: "casi nunca", 2: "a veces", 3: "casi siempre", 4: "siempre"}


def puntuar_vhi(items: list, version: str = "") -> dict:
    """Totales y subescalas calculados acá (la IA solo propone cada ítem)."""
    vals = {}
    for it in items or []:
        cod = str(it.get("codigo") or "").upper().strip()
        try:
            v = int(it.get("puntaje"))
        except Exception:
            continue
        if cod in VHI_ITEMS and 0 <= v <= 4:
            vals[cod] = v
    sub = {n: sum(v for k, v in vals.items() if k.startswith(p))
           for n, p in (("funcional", "F"), ("fisica", "P"), ("emocional", "E"))}
    n = len(vals)
    total = sum(vals.values())
    es10 = version.upper() == "VHI-10" or (version.upper() != "VHI-30" and n and n <= 10 and all(k in VHI10 for k in vals))
    res = {"respondidos": n, "total": total, "subescalas": sub, "puntajes": vals}
    if es10:
        res["instrumento"] = "VHI-10"
        res["completo"] = n == 10
        res["interpretacion"] = ("por encima del corte de normalidad (>11)" if total > 11
                                 else "dentro del rango normal (≤11)") + " · Rosen et al., 2004"
    else:
        res["instrumento"] = "VHI-30"
        res["completo"] = n == 30
        if n == 30:
            res["interpretacion"] = ("leve" if total <= 30 else "moderado" if total <= 60
                                     else "severo" if total <= 90 else "grave") + \
                " (0–30 leve · 31–60 moderado · 61–90 severo · 91–120 grave; orientativo)"
        else:
            res["interpretacion"] = f"incompleto ({n}/30 ítems): el total no es comparable con normas"
    return res


def analisis_clinico(sb, ses: dict, trs: list) -> dict:
    """Resumen clínico de la sesión + instrumentos detectados (VHI) +
    comparación con la sesión anterior del mismo paciente."""
    if not trs:
        return {}
    lineas = []
    for t in trs:
        if t.get("_otro"):
            quien = "OTRO"
        else:
            quien = "FONO" if t["speaker"] == "fonoaudiologo" else "PACIENTE"
        m, s = divmod(int(float(t["start_sec"])), 60)
        lineas.append(f"[{m:02d}:{s:02d}] {quien}: {t['text']}")
    texto = "\n".join(lineas)[:90000]
    items_txt = "\n".join(f"{k}: {v}" for k, v in VHI_ITEMS.items())
    prompt = (
        "Sos fonoaudiólogo/a especialista en voz. Analizá la transcripción de una sesión "
        "(FONO = profesional, PACIENTE = paciente; la atribución automática puede tener "
        "errores: usá el contenido). Respondé SOLO JSON con esta forma:\n"
        "{\"tipo_sesion\": \"evaluacion_inicial|anamnesis|aplicacion_instrumento|terapia|control|otra\",\n"
        " \"resumen\": \"4-6 oraciones clínicas\",\n"
        " \"motivo_o_objetivo\": \"\", \"sintomas_referidos\": [\"\"], \"habitos_y_factores\": [\"\"],\n"
        " \"ejercicios_realizados\": [\"\"], \"indicaciones_para_casa\": [\"\"],\n"
        " \"observaciones_voz\": \"lo que el/la profesional comenta de la voz\",\n"
        " \"alertas\": [\"signos que justifiquen derivación ORL u otra consulta\"],\n"
        " \"proximos_pasos\": [\"\"],\n"
        " \"vhi\": {\"aplicado\": true|false, \"version\": \"VHI-30|VHI-10|otra\",\n"
        "   \"items\": [{\"codigo\": \"F1\", \"pregunta_detectada\": \"\", \"respuesta_textual\": \"\",\n"
        "              \"puntaje\": 0, \"confianza\": \"alta|media|baja\", \"minuto\": \"mm:ss\"}]}}\n"
        "Reglas VHI: solo incluí ítems que efectivamente se preguntaron y respondieron. "
        "Mapeá cada pregunta al código cuyo contenido coincide (lista abajo). Escala: "
        "0 nunca, 1 casi nunca, 2 a veces, 3 casi siempre, 4 siempre. Si la respuesta es "
        "ambigua, poné tu mejor estimación con confianza baja. No inventes ítems.\n"
        "Sin diagnósticos médicos definitivos. Español rioplatense.\n\n"
        "ÍTEMS VHI:\n" + items_txt + "\n\nTRANSCRIPCIÓN:\n" + texto)
    d = llm_json(prompt, max_tokens=6000)
    vhi = d.get("vhi") or {}
    if vhi.get("aplicado") and vhi.get("items"):
        vhi["resultado"] = puntuar_vhi(vhi["items"], str(vhi.get("version") or ""))
    d["vhi"] = vhi
    d["generado"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    d["comparacion"] = _comparar_previa(sb, ses, d)
    _guardar_info(sb, ses, "analisis_ia", d)
    return d


def _comparar_previa(sb, ses: dict, actual: dict) -> dict:
    """Diferencias con la sesión anterior (calculadas, no por IA)."""
    try:
        r = sb.table("companion_sessions").select("id, recorded_at, device_info")\
            .eq("patient_id", ses["patient_id"]).lt("recorded_at", ses.get("recorded_at") or "9999")\
            .order("recorded_at", desc=True).limit(1).execute()
        if not r.data:
            return {"hay_previa": False}
        prev = r.data[0]
        out = {"hay_previa": True, "fecha_previa": (prev.get("recorded_at") or "")[:10]}

        def f0(sid):
            a = sb.table("session_acoustics").select("f0_median_hz")\
                .eq("session_id", sid).eq("task_type", TAREA).execute()
            return (a.data or [{}])[0].get("f0_median_hz")
        f_act, f_prev = f0(ses["id"]), f0(prev["id"])
        if f_act and f_prev:
            out["f0_mediana_hz"] = {"previa": f_prev, "actual": f_act,
                                    "cambio_st": round(12 * math.log2(float(f_act) / float(f_prev)), 2)}
        pv = ((prev.get("device_info") or {}).get("analisis_ia") or {}).get("vhi") or {}
        av = (actual.get("vhi") or {})
        if (pv.get("resultado") or {}).get("total") is not None and (av.get("resultado") or {}).get("total") is not None:
            out["vhi_total"] = {"previa": pv["resultado"]["total"], "actual": av["resultado"]["total"]}
        return out
    except Exception as e:
        return {"error": str(e)[:200]}
