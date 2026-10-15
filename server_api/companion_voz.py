"""Vocalis Companion — transcripción con separación de voces y altura tonal en el servidor.

Tres piezas, usadas por `companion._process_job`:

1. `procesar()`: transcribe y separa hablantes con AssemblyAI (diarización
   neuronal, español, 2 hablantes esperados). Requiere ASSEMBLYAI_API_KEY; sin
   ella el servidor sigue con Whisper (Groq) + la separación del teléfono.
   Tras leer el resultado se BORRA la transcripción en AssemblyAI (privacidad).
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
    with wave.open(wav_path, "rb") as w:
        sr = w.getframerate()
        total = w.getnframes()
        for a, b in intervalos:
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
    try:
        import companion_ia
    except Exception:
        return None
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
        txt = companion_ia._llm(prompt)
        m = re.search(r"\{.*\}", txt or "", re.DOTALL)
        d = json.loads(m.group(0)) if m else {}
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
    """Transcripción + hablantes con AssemblyAI → filas de session_transcripts."""
    utts = transcribir_assemblyai(prep["compacto"])
    if not utts:
        return []
    # Tono mediano de cada hablante (rango amplio) para el voto por tono.
    medianas = {}
    for letra in sorted({u["speaker"] for u in utts}):
        iv = [(u["start"], u["end"]) for u in utts if u["speaker"] == letra]
        f = [x for x in f0_cuadros(prep["wav"], iv[:200], 75.0, 600.0) if x > 0]
        medianas[letra] = _mediana(f) if len(f) > 50 else None
    mapa, pac, info = asignar_roles(utts, task_segs, medianas, _fono_hz(sb, ses))
    info["medianas_hz"] = {k: (round(v, 1) if v else None) for k, v in medianas.items()}
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
    ya = sb.table("session_acoustics").select("task_type").eq("session_id", sid).execute()
    if ya.data:
        return None   # la del teléfono manda (contrato)
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
