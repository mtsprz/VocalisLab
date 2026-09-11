from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import shutil
import os
import sys
import traceback
import json
import csv
import io

sys.path.insert(0, os.path.dirname(__file__))

from voicelab_analysis import analisis_completo, validar_audio_completo
from reportes_pdf import generar_pdf_clinico
from api_clinica import router as clinica_router
from anamnesis_engine import transcribir_audio_groq, estructurar_anamnesis_llm, generar_muestra_vocal_prompt
from cuadernillo_pdf import generar_cuadernillo_pdf
from recomendar_motor import generar_recomendacion_terapeutica
from google_auth import router as google_auth_router
from google_calendar import router as google_calendar_router
from ai_clinical import router as ai_clinical_router
from externo_ocr import router as externo_ocr_router

DB_PATH = os.path.join(os.path.dirname(__file__), "vocal_pathology_db.json")

def _load_pathology_db() -> dict:
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _f0_normative_for_age_sex(edad, sexo, db=None):
    """Return F0 normative data (typical, min, max, severity thresholds) for a given age and sex.
    References: Colton, Casper & Leonard (2011) cited by Farías (2012, 2016); Paolini et al. (2018).
    Returns dict with keys: typical_hz, min_hz, max_hz, mild_pct, moderate_pct, severe_pct, note, source.
    """
    if db is None:
        db = _load_pathology_db()
    f0_db = db.get("normative_ranges", {}).get("f0_by_age_sex", {})
    severity_pct = f0_db.get("severity_thresholds_pct", {})
    mild_pct = severity_pct.get("mild_pct", 15)
    moderate_pct = severity_pct.get("moderate_pct", 30)
    severe_pct = severity_pct.get("severe_pct", 50)

    if not sexo:
        return {"typical_hz": None, "min_hz": None, "max_hz": None, "mild_pct": mild_pct, "moderate_pct": moderate_pct, "severe_pct": severe_pct, "note": "Sexo no especificado", "source": "N/D"}

    sexo_lower = sexo.lower()
    if "masc" in sexo_lower or "hombre" in sexo_lower or "male" in sexo_lower or "varon" in sexo_lower:
        sex_key = "male"
    elif "fem" in sexo_lower or "mujer" in sexo_lower or "female" in sexo_lower or "inf" in sexo_lower or "niñ" in sexo_lower or "child" in sexo_lower:
        sex_key = "female"
    else:
        return {"typical_hz": None, "min_hz": None, "max_hz": None, "mild_pct": mild_pct, "moderate_pct": moderate_pct, "severe_pct": severe_pct, "note": "Sexo no reconocido", "source": "N/D"}

    age_entries = f0_db.get(sex_key, [])
    if not age_entries:
        return {"typical_hz": None, "min_hz": None, "max_hz": None, "mild_pct": mild_pct, "moderate_pct": moderate_pct, "severe_pct": severe_pct, "note": "Sin datos normativos", "source": "N/D"}

    try:
        age_num = int(edad) if edad else None
    except (ValueError, TypeError):
        age_num = None

    if age_num is None:
        if sex_key == "male":
            return {"typical_hz": 120, "min_hz": 85, "max_hz": 165, "mild_pct": mild_pct, "moderate_pct": moderate_pct, "severe_pct": severe_pct, "note": "Edad no especificada - usando rango adulto masculino típico", "source": "Colton et al. (2011)"}
        else:
            return {"typical_hz": 200, "min_hz": 145, "max_hz": 255, "mild_pct": mild_pct, "moderate_pct": moderate_pct, "severe_pct": severe_pct, "note": "Edad no especificada - usando rango adulto femenino típico", "source": "Colton et al. (2011)"}

    for entry in age_entries:
        if entry["age_min"] <= age_num <= entry["age_max"]:
            return {
                "typical_hz": entry["typical_hz"],
                "min_hz": entry["min_hz"],
                "max_hz": entry["max_hz"],
                "mild_pct": mild_pct,
                "moderate_pct": moderate_pct,
                "severe_pct": severe_pct,
                "note": entry.get("note", ""),
                "source": "Colton et al. (2011) / Farías (2012, 2016)",
            }

    last = age_entries[-1]
    return {
        "typical_hz": last["typical_hz"],
        "min_hz": last["min_hz"],
        "max_hz": last["max_hz"],
        "mild_pct": mild_pct,
        "moderate_pct": moderate_pct,
        "severe_pct": severe_pct,
        "note": f"Edad {age_num} fuera de rangos tabulados - usando el más cercano",
        "source": "Colton et al. (2011)",
    }


def _f0_severity(f0_mean, normative):
    """Classify F0 deviation severity based on age/sex normative data.
    Returns (severity_level, label, color_hex) where severity_level is 0-3.
    """
    if f0_mean is None or normative is None or normative.get("typical_hz") is None:
        return (None, "N/D", "#94a3b8")

    typical = normative["typical_hz"]
    if typical <= 0:
        return (None, "N/D", "#94a3b8")

    deviation_pct = abs(f0_mean - typical) / typical * 100
    mild = normative.get("mild_pct", 15)
    moderate = normative.get("moderate_pct", 30)
    severe = normative.get("severe_pct", 50)

    if deviation_pct <= mild:
        return (0, "Normal", "#22c55e")
    elif deviation_pct <= moderate:
        return (1, "Leve", "#eab308")
    elif deviation_pct <= severe:
        return (2, "Moderado", "#f97316")
    else:
        return (3, "Marcado", "#ef4444")

def _cross_check_acoustics_vs_perceptual(metrics: dict, grbas: dict, rasati: dict, db: dict, edad: str = None, sexo: str = None) -> dict:
    """Cross-check acoustic measurements with GRBAS/RASATI perceptual scales using the pathology database."""
    result = {
        "acoustic_indicators": [],
        "pathology_matches": [],
        "perceptual_acoustic_consistency": "N/D",
        "clinical_observations": [],
        "alerts": [],
        "f0_normative": None,
    }

    f0_norm = _f0_normative_for_age_sex(edad, sexo, db)
    result["f0_normative"] = f0_norm

    corr = db.get("grbas_acoustic_correlation", {})
    rules = db.get("clinical_interpretation_rules", {})
    paths = db.get("pathology_profiles", {})

    f0 = metrics.get("f0_mean")
    jitter = metrics.get("jitter_local_pct")
    shimmer = metrics.get("shimmer_local_pct")
    hnr = metrics.get("hnr_db")
    cpps = metrics.get("cpps_db")
    nhr = metrics.get("nhr")
    nne = metrics.get("nne_db")
    tilt_slope = None
    spectral_data = metrics.get("spectral") if isinstance(metrics.get("spectral"), dict) else None
    if spectral_data:
        tilt_slope = spectral_data.get("spectral_tilt_slope")

    g_val = grbas.get("G", 0)
    r_val = grbas.get("R", 0)
    b_val = grbas.get("B", 0)
    a_val = grbas.get("A", 0)
    s_val = grbas.get("S", 0)

    if g_val == 0 and jitter is not None and shimmer is not None:
        if jitter > 1.5 or shimmer > 5.0:
            result["alerts"].append("GRBAS G=0 pero jitter/shimmer elevados: posible subdiagnóstico perceptual o fase temprana.")
    if g_val >= 2 and jitter is not None and jitter < 0.5 and shimmer is not None and shimmer < 3.0:
        result["alerts"].append("GRBAS G≥2 pero jitter/shimmer dentro de norma: considerar factores psicogénicos o fatiga intermitente.")

    if r_val >= 2:
        if cpps is not None and cpps < 10:
            result["acoustic_indicators"].append("CPPS bajo (<10 dB): correlaciona con R≥2 (ronquedad moderada-severa).")
        if hnr is not None and hnr < 15:
            result["acoustic_indicators"].append("HNR bajo (<15 dB): indica componente aperiódico significativo.")
    if r_val == 0:
        if cpps is not None and cpps < 14.47:
            result["alerts"].append("R=0 pero CPPS bajo: posible ronquedad subclínica no percibida.")
        if hnr is not None and hnr < 18:
            result["alerts"].append("R=0 pero HNR borderline: componente de ruido presente pero no percibido.")

    if b_val >= 2:
        if hnr is not None and hnr < 12:
            result["acoustic_indicators"].append("HNR bajo (<12 dB): correlaciona con B≥2 (breathiness moderada-severa).")
        if nhr is not None and nhr > 0.15:
            result["acoustic_indicators"].append("NHR alto (>0.15): confirma componente de ruido respiratorio.")
    if b_val == 0:
        if hnr is not None and hnr < 15:
            result["alerts"].append("B=0 pero HNR<15 dB: posible breathiness subclínica.")

    if f0 is not None and f0_norm.get("typical_hz") is not None:
        f0_sev, f0_label, f0_color = _f0_severity(f0, f0_norm)
        typical = f0_norm["typical_hz"]
        deviation = abs(f0 - typical)
        deviation_pct = round(deviation / typical * 100, 1)
        direction = "por encima" if f0 > typical else "por debajo"
        if f0_sev is not None and f0_sev > 0:
            result["acoustic_indicators"].append(
                f"F0={f0} Hz ({f0_label}): {deviation_pct}% {direction} del típico ({typical} Hz para {sexo or 'N/D'} de {edad or 'N/D'} años). "
                f"Rango normativo: {f0_norm['min_hz']}-{f0_norm['max_hz']} Hz."
            )
        else:
            result["acoustic_indicators"].append(
                f"F0={f0} Hz (Normal): dentro del rango normativo para {sexo or 'N/D'} de {edad or 'N/D'} años (típico={typical} Hz, rango={f0_norm['min_hz']}-{f0_norm['max_hz']} Hz)."
            )

    if a_val >= 2:
        if f0 is not None:
            result["acoustic_indicators"].append(f"F0={f0} Hz: evaluar rango dinámico paraasténico (A≥2).")
    if s_val >= 2:
        if jitter is not None and jitter > 2.0:
            result["acoustic_indicators"].append("Jitter elevado (>2%): correlaciona con S≥2 (tensión).")

    matched_paths = []
    for key, prof in paths.items():
        score = 0
        notes = []
        pattern = prof.get("acoustic_pattern", {})
        exp_grbas = prof.get("expected_grbas", {})

        if jitter is not None:
            if "aumento_moderado" in pattern.get("jitter", "") or "aumento_severo" in pattern.get("jitter", ""):
                if jitter > 1.5:
                    score += 1
                    notes.append(f"Jitter ({jitter}%) >1.5%")
            if "leve_aumento" in pattern.get("jitter", ""):
                if 0.5 < jitter <= 1.5:
                    score += 0.5

        if shimmer is not None:
            if "aumento_moderado" in pattern.get("shimmer", "") or "aumento_severo" in pattern.get("shimmer", ""):
                if shimmer > 5.0:
                    score += 1
                    notes.append(f"Shimmer ({shimmer}%) >5%")
            if "leve_aumento" in pattern.get("shimmer", ""):
                if 3.0 < shimmer <= 5.0:
                    score += 0.5

        if hnr is not None:
            if "disminuido" in pattern.get("hnr", "") or "severamente_disminuido" in pattern.get("hnr", ""):
                if hnr < 15:
                    score += 1
                    notes.append(f"HNR ({hnr} dB) <15 dB")
            if "leve_disminución" in pattern.get("hnr", ""):
                if 15 <= hnr < 20:
                    score += 0.5

        if cpps is not None:
            if "disminuido" in pattern.get("cpps", "") or "severamente_disminuido" in pattern.get("cpps", ""):
                if cpps < 12:
                    score += 1
                    notes.append(f"CPPS ({cpps} dB) <12 dB")
            if "leve_disminución" in pattern.get("cpps", ""):
                if 10 <= cpps < 14.47:
                    score += 0.5

        if score >= 2:
            matched_paths.append({
                "key": key,
                "name": prof["name"],
                "match_score": round(score, 1),
                "matching_indicators": notes,
                "clinical_notes": prof.get("clinical_notes", ""),
            })

    matched_paths.sort(key=lambda x: x["match_score"], reverse=True)
    result["pathology_matches"] = matched_paths[:3]

    for rule_key, rule in rules.items():
        cond = rule.get("pattern", "")
        if rule_key == "high_jitter_high_shimmer":
            if jitter is not None and shimmer is None:
                continue
            if jitter is not None and shimmer is not None and jitter > 1.5 and shimmer > 5.0:
                result["clinical_observations"].append({
                    "pattern": cond,
                    "etiologies": rule.get("possible_etiologies", []),
                    "suggestion": rule.get("clinical_suggestion", ""),
                })
        elif rule_key == "low_hnr_low_cpps":
            if hnr is not None and cpps is not None and hnr < 15 and cpps < 12:
                result["clinical_observations"].append({
                    "pattern": cond,
                    "etiologies": rule.get("possible_etiologies", []),
                    "suggestion": rule.get("clinical_suggestion", ""),
                })
        elif rule_key == "high_jitter_normal_shimmer":
            if jitter is not None and shimmer is not None and jitter > 1.5 and shimmer <= 3.81:
                result["clinical_observations"].append({
                    "pattern": cond,
                    "etiologies": rule.get("possible_etiologies", []),
                    "suggestion": rule.get("clinical_suggestion", ""),
                })
        elif rule_key == "normal_jitter_high_shimmer":
            if jitter is not None and shimmer is not None and jitter <= 1.04 and shimmer > 5.0:
                result["clinical_observations"].append({
                    "pattern": cond,
                    "etiologies": rule.get("possible_etiologies", []),
                    "suggestion": rule.get("clinical_suggestion", ""),
                })
        elif rule_key == "very_low_f0_female":
            if f0 is not None and f0 < 140:
                result["clinical_observations"].append({
                    "pattern": cond,
                    "etiologies": rule.get("possible_etiologies", []),
                    "suggestion": rule.get("clinical_suggestion", ""),
                })
        elif rule_key == "very_high_f0_male":
            if f0 is not None and f0 > 250:
                result["clinical_observations"].append({
                    "pattern": cond,
                    "etiologies": rule.get("possible_etiologies", []),
                    "suggestion": rule.get("clinical_suggestion", ""),
                })

    if grbas and f0 is not None and jitter is not None:
        acoustic_score = 0
        if jitter > 1.5: acoustic_score += 1
        if shimmer is not None and shimmer > 5.0: acoustic_score += 1
        if hnr is not None and hnr < 15: acoustic_score += 1
        if cpps is not None and cpps < 12: acoustic_score += 1
        perceptual_score = g_val

        if abs(acoustic_score - perceptual_score) <= 1:
            result["perceptual_acoustic_consistency"] = "Consistente"
        elif acoustic_score > perceptual_score:
            result["perceptual_acoustic_consistency"] = "Acústica sugiere mayor severidad que la percepción"
        else:
            result["perceptual_acoustic_consistency"] = "Percepción sugiere mayor severidad que la acústica"

    return result

app = FastAPI(title="VocalisLab Bioacoustic API")

ALLOWED_ORIGINS = [
    "https://vocalis-lab.vercel.app",
    "https://vocalis-lab-*.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://vocalis-lab-.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "https://vocalis-lab.vercel.app",
            "Access-Control-Allow-Credentials": "true",
        },
    )

app.include_router(clinica_router)
app.include_router(google_auth_router)
app.include_router(google_calendar_router)
app.include_router(ai_clinical_router)
app.include_router(externo_ocr_router)


@app.get("/api/health")
def health_check():
    import subprocess
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(__file__), text=True).strip()
    except Exception:
        commit = "unknown"
    return {"status": "ok", "engine": "Praat/Parselmouth + VoiceLab", "version": "1.0.0", "commit": commit}


def _build_tools_list(metrics: dict, avqi: dict, audio_info: dict) -> list:
    tools = []
    audio_ok = audio_info.get("valid", False)
    tools.append({
        "name": "Validación de Audio",
        "status": "ok" if audio_ok else "error",
        "message": "Audio clínicamente válido" if audio_ok else "; ".join(audio_info.get("issues", [])),
    })

    f0 = metrics.get("f0_mean")
    tools.append({
        "name": "Medición de F0 (Parselmouth)",
        "status": "ok" if f0 else "error",
        "message": f"F0 media = {f0} Hz" if f0 else "No se pudo medir F0",
    })

    jitter = metrics.get("jitter_local_pct")
    tools.append({
        "name": "Jitter (5 métodos)",
        "status": "ok" if jitter is not None else "error",
        "message": f"Jitter local = {jitter}%" if jitter is not None else "No disponible",
    })

    shimmer = metrics.get("shimmer_local_pct")
    tools.append({
        "name": "Shimmer (6 métodos)",
        "status": "ok" if shimmer is not None else "error",
        "message": f"Shimmer local = {shimmer}%" if shimmer is not None else "No disponible",
    })

    hnr = metrics.get("hnr_db")
    tools.append({
        "name": "HNR (Harmonicity)",
        "status": "ok" if hnr is not None else "warning",
        "message": f"HNR = {hnr} dB" if hnr is not None else "No disponible",
    })

    cpps = metrics.get("cpps_db")
    tools.append({
        "name": "CPPS (Cepstral Peak Prominence)",
        "status": "ok" if cpps is not None else "warning",
        "message": f"CPPS = {cpps} dB" if cpps is not None else "No disponible",
    })

    avqi_val = avqi.get("avqi")
    calculable = avqi.get("calculable", False)
    avqi_status = avqi.get("status", "ok")
    if calculable and avqi_val is not None:
        avqi_tool_status = "ok"
    elif avqi_status == "untestable_requires_continuous_speech":
        avqi_tool_status = "warning"
    elif calculable and avqi_val is None:
        avqi_tool_status = "warning"
    else:
        avqi_tool_status = "warning"
    tools.append({
        "name": "AVQI v03.01",
        "status": avqi_tool_status,
        "message": f"AVQI = {avqi_val}" if calculable else (avqi.get("error", "No calculable (requiere habla continua)")),
    })

    f1 = metrics.get("f1_hz")
    tools.append({
        "name": "Formantes (Burg)",
        "status": "ok" if f1 else "warning",
        "message": f"F1={f1}, F2={metrics.get('f2_hz')}" if f1 else "No disponibles",
    })

    ltas_mean = metrics.get("ltas", {}).get("ltas_mean_db") if isinstance(metrics.get("ltas"), dict) else None
    tools.append({
        "name": "LTAS (Long-Term Average Spectrum)",
        "status": "ok" if ltas_mean is not None else "warning",
        "message": f"Media = {ltas_mean} dB" if ltas_mean is not None else "No disponible",
    })

    tilt = metrics.get("spectral", {}).get("spectral_tilt_slope") if isinstance(metrics.get("spectral"), dict) else None
    tools.append({
        "name": "Pendiente Espectral (Spectral Tilt)",
        "status": "ok" if tilt is not None else "warning",
        "message": f"Pendiente = {tilt}" if tilt is not None else "No disponible",
    })

    nhr = metrics.get("nhr")
    tools.append({
        "name": "NHR (Noise-to-Harmonics Ratio)",
        "status": "ok" if nhr is not None else "warning",
        "message": f"NHR = {nhr}" if nhr is not None else "No disponible",
    })

    return tools


@app.post("/api/analizar")
async def analizar(
    audio_vocal: UploadFile = File(None),
    audio: UploadFile = File(None),
    audio_habla: UploadFile = File(None),
    modo: str = Form("clinico"),
    sexo: str = Form(""),
    edad: str = Form(""),
    grbas: str = Form("{}"),
    rasati: str = Form("{}"),
    pitch_floor: Optional[float] = Form(None),
    pitch_ceiling: Optional[float] = Form(None),
):
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    vocal_file = audio_vocal or audio
    if vocal_file is None or not getattr(vocal_file, "filename", None):
        raise HTTPException(status_code=422, detail="Falta el archivo de audio vocal (campo audio_vocal)")

    tmp_vocal = os.path.join(tmp_dir, f"vocal_{vocal_file.filename or 'a.wav'}")
    tmp_habla = os.path.join(tmp_dir, f"habla_{audio_habla.filename}") if audio_habla and audio_habla.filename else None

    try:
        with open(tmp_vocal, "wb") as buffer:
            shutil.copyfileobj(vocal_file.file, buffer)
        if tmp_habla and audio_habla:
            with open(tmp_habla, "wb") as buffer:
                shutil.copyfileobj(audio_habla.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al recibir archivo de audio: {str(e)}")

    try:
        resultado = analisis_completo(
            tmp_vocal,
            file_path_habla=tmp_habla,
            modo=modo,
            sexo=sexo,
            pitch_floor=pitch_floor if pitch_floor and pitch_floor > 0 else None,
            pitch_ceiling=pitch_ceiling if pitch_ceiling and pitch_ceiling > 0 else None,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en el análisis bioacústico: {str(e)}")
    finally:
        try:
            if os.path.exists(tmp_vocal): os.remove(tmp_vocal)
            if tmp_habla and os.path.exists(tmp_habla): os.remove(tmp_habla)
        except Exception:
            pass

    if resultado.get("status") == "error":
        return JSONResponse(status_code=422, content=resultado)

    if resultado.get("metrics") is None:
        return JSONResponse(status_code=500, content={
            "error": "El análisis no produjo resultados",
            "detail": resultado.get("error", "Error desconocido"),
            "audio": resultado.get("audio"),
        })

    metrics_raw = resultado.get("metrics", {})
    avqi = resultado.get("avqi_components", {})
    harmonics = resultado.get("harmonics", [])
    formants = resultado.get("formants", {})
    audio_info = resultado.get("audio", {})

    json_export = resultado.get("json_export", {})
    csv_export = resultado.get("csv_export", [])

    # --- Cross-check acoustics vs GRBAS/RASATI (heredados del módulo clínico) ---
    try:
        pathology_db = _load_pathology_db()
        try:
            g_dict = json.loads(grbas) if isinstance(grbas, str) and grbas.startswith("{") else {}
        except Exception:
            g_dict = {}
        try:
            r_dict = json.loads(rasati) if isinstance(rasati, str) and rasati.startswith("{") else {}
        except Exception:
            r_dict = {}
        cross_check = _cross_check_acoustics_vs_perceptual(metrics_raw, g_dict, r_dict, pathology_db, edad=edad, sexo=sexo)
    except Exception as e:
        traceback.print_exc()
        cross_check = {"perceptual_acoustic_consistency": "N/D", "acoustic_indicators": [], "pathology_matches": [], "clinical_observations": [], "alerts": []}

    metrics = {
        "f0_mean": metrics_raw.get("f0_mean"),
        "f0_min": metrics_raw.get("f0_min"),
        "f0_max": metrics_raw.get("f0_max"),
        "f0_sd": metrics_raw.get("f0_sd"),
        "f0_range": metrics_raw.get("f0_range"),
        "f0_median": metrics_raw.get("f0_median"),
        "voiced_fraction": metrics_raw.get("voiced_fraction"),
        "jitter_pct": metrics_raw.get("jitter_local_pct"),
        "jitter_local_absolute_s": metrics_raw.get("jitter_local_absolute_s"),
        "jitter_rap_pct": metrics_raw.get("jitter_rap_pct"),
        "jitter_ppq5_pct": metrics_raw.get("jitter_ppq5_pct"),
        "jitter_ddp_pct": metrics_raw.get("jitter_ddp_pct"),
        "shimmer_pct": metrics_raw.get("shimmer_local_pct"),
        "shimmer_db": metrics_raw.get("shimmer_local_db"),
        "shimmer_apq3_pct": metrics_raw.get("shimmer_apq3_pct"),
        "shimmer_apq5_pct": metrics_raw.get("shimmer_apq5_pct"),
        "shimmer_apq11_pct": metrics_raw.get("shimmer_apq11_pct"),
        "shimmer_dda_pct": metrics_raw.get("shimmer_dda_pct"),
        "hnr_db": metrics_raw.get("hnr_db"),
        "cpps_db": metrics_raw.get("cpps_db"),
        "nhr": metrics_raw.get("nhr"),
        "nne_db": metrics_raw.get("nne_db"),
        "f1_hz": formants.get("f1_hz"),
        "f2_hz": formants.get("f2_hz"),
        "f3_hz": formants.get("f3_hz"),
        "f4_hz": formants.get("f4_hz"),
        "f1_bandwidth_hz": metrics_raw.get("f1_bandwidth_hz"),
        "f2_bandwidth_hz": metrics_raw.get("f2_bandwidth_hz"),
        "intensity_mean_db": metrics_raw.get("intensity_mean_db"),
        "alpha_ratio_db": metrics_raw.get("alpha_ratio_db"),
        "harmonics": harmonics,
        "formants": formants,
        "ltas": resultado.get("ltas", {}),
        "spectral": resultado.get("spectral", {}),
        "classifications": resultado.get("classifications", {}),
        "parselmouth_version": resultado.get("parselmouth_version"),
        "praat_script": f"VoiceLab/{resultado.get('voicelab_version', '2.0.0')}",
        "pitch_floor": metrics_raw.get("pitch_floor"),
        "pitch_ceiling": metrics_raw.get("pitch_ceiling"),
    }

    tools = _build_tools_list(metrics_raw, avqi, audio_info)

    response = {
        "status": "ok",
        "timestamp": resultado.get("timestamp"),
        "engineVersion": resultado.get("engine"),
        "voicelab_version": resultado.get("voicelab_version"),
        "scriptVersion": f"VoiceLab/{resultado.get('voicelab_version', '2.0.0')}",
        "parselmouth_version": resultado.get("parselmouth_version"),
        "modo": resultado.get("modo"),
        "audio": audio_info,
        "metrics": metrics,
        "avqiComponents": avqi,
        "avqi_status": avqi.get("status", "ok"),
        "tools": tools,
        "fileHash": audio_info.get("file_hash_sha256", ""),
        "waveform": resultado.get("waveform", {}),
        "spectrogram": resultado.get("spectrogram", {}),
        "glottalPulses": resultado.get("glottal_pulses", []),
        "formantTracks": resultado.get("formant_tracks", {}),
        "f0Contour": resultado.get("f0_contour", {}),
        "intensityContour": resultado.get("intensity_contour", {}),
        "classifications": resultado.get("classifications", {}),
        "voxplot": resultado.get("voxplot", {}),
        "charts": resultado.get("charts", {}),
        "crossCheck": cross_check,
        "jsonExport": json_export,
        "csvExport": json.dumps(csv_export),
    }

    return JSONResponse(content=response)


@app.post("/api/analizar-y-reportar")
async def analizar_y_reportar(
    audio_vocal: UploadFile = File(...),
    audio_habla: UploadFile = File(None),
    nombre: str = Form("Paciente Anónimo"),
    dni: str = Form("00000000"),
    edad: str = Form("30"),
    sexo: str = Form("Femenino"),
    motivo: str = Form("Evaluación vocal"),
    derivador: str = Form("Auto"),
    grbas: str = Form("{}"),
    rasati: str = Form("{}"),
    tmf: float = Form(15.0),
    profesional_nombre: str = Form(""),
    profesional_titulo: str = Form("Lic. en Fonoaudiología"),
    profesional_matricula: str = Form(""),
    profesional_centro: str = Form(""),
    profesional_email: str = Form(""),
    pitch_floor: Optional[float] = Form(None),
    pitch_ceiling: Optional[float] = Form(None),
):
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_vocal = os.path.join(tmp_dir, f"vocal_{audio_vocal.filename or 'a.wav'}")
    tmp_habla = os.path.join(tmp_dir, f"habla_{audio_habla.filename}") if audio_habla and audio_habla.filename else None

    try:
        with open(tmp_vocal, "wb") as buffer:
            shutil.copyfileobj(audio_vocal.file, buffer)
        if tmp_habla and audio_habla:
            with open(tmp_habla, "wb") as buffer:
                shutil.copyfileobj(audio_habla.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al recibir archivo de audio: {str(e)}")

    try:
        resultado = analisis_completo(
            tmp_vocal,
            file_path_habla=tmp_habla,
            modo="clinico",
            sexo=sexo,
            pitch_floor=pitch_floor if pitch_floor and pitch_floor > 0 else None,
            pitch_ceiling=pitch_ceiling if pitch_ceiling and pitch_ceiling > 0 else None,
        )
    except Exception as e:
        traceback.print_exc()
        try:
            if os.path.exists(tmp_vocal): os.remove(tmp_vocal)
            if tmp_habla and os.path.exists(tmp_habla): os.remove(tmp_habla)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Error en el análisis bioacústico: {str(e)}")

    if resultado["status"] == "error":
        return JSONResponse(status_code=422, content=resultado)

    metrics = resultado.get("metrics", {})
    audio_info = resultado.get("audio", {})

    # --- Cross-check acoustics vs GRBAS/RASATI ---
    pathology_db = _load_pathology_db()
    g_dict = {}
    r_dict = {}
    try:
        g_dict = json.loads(grbas) if grbas.startswith('{') else {}
    except Exception:
        pass
    try:
        r_dict = json.loads(rasati) if rasati.startswith('{') else {}
    except Exception:
        pass

    try:
        cross_check = _cross_check_acoustics_vs_perceptual(metrics, g_dict, r_dict, pathology_db, edad=edad, sexo=sexo)
    except Exception as e:
        traceback.print_exc()
        cross_check = {"perceptual_acoustic_consistency": "N/D", "acoustic_indicators": [], "pathology_matches": [], "clinical_observations": [], "alerts": []}

    sintesis_ia = ""
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key, timeout=20.0)
            avqi_str = str(resultado.get("avqi_components", {}).get("avqi", "N/D"))
            avqi_status = resultado.get("avqi_components", {}).get("status", "ok")

            cc_text = ""
            if cross_check.get("acoustic_indicators"):
                cc_text += "\nIndicadores acústicos relevantes:\n" + "\n".join(f"- {x}" for x in cross_check["acoustic_indicators"])
            if cross_check.get("pathology_matches"):
                cc_text += "\n\nPerfiles clínicos compatibles (no diagnósticos):\n"
                for m in cross_check["pathology_matches"][:2]:
                    cc_text += f"- {m['name']} (coincidencia {m['match_score']}/3): {'; '.join(m['matching_indicators'])}\n  Nota: {m['clinical_notes']}\n"
            if cross_check.get("clinical_observations"):
                cc_text += "\nObservaciones clínicas:\n"
                for obs in cross_check["clinical_observations"][:2]:
                    cc_text += f"- Patrón: {obs['pattern']}\n  Etiologías posibles: {', '.join(obs['etiologies'])}\n  Sugerencia: {obs['suggestion']}\n"
            if cross_check.get("alerts"):
                cc_text += "\nAlertas:\n" + "\n".join(f"- {a}" for a in cross_check["alerts"])
            if cross_check.get("perceptual_acoustic_consistency") != "N/D":
                cc_text += f"\n\nConsistencia percepción-acústica: {cross_check['perceptual_acoustic_consistency']}"

            grbas_line = f"GRBAS: G{g_dict.get('G',0)} R{g_dict.get('R',0)} B{g_dict.get('B',0)} A{g_dict.get('A',0)} S{g_dict.get('S',0)}" if g_dict else "GRBAS no disponible"
            rasati_line = f"RASATI: R{r_dict.get('R',0)} A{r_dict.get('A',0)} S{r_dict.get('S',0)} A2{r_dict.get('A2',0)} T{r_dict.get('T',0)} I{r_dict.get('I',0)}" if r_dict else "RASATI no disponible"

            prompt = (
                f"Eres un sistema de apoyo fonoaudiológico clínico. Actúa como Fonoaudiólogo especialista en voz.\n\n"
                f"IMPORTANTE: NO emitas diagnóstico médico etiológico (ej. 'nodo cordal', 'pólipo'). "
                f"Describe el PATRÓN ACÚSTICO FONOAUDIOLÓGICO y su correlación con la evaluación perceptual.\n"
                f"El informe es para ser revisado por el profesional tratante.\n\n"
                f"--- DATOS DEL PACIENTE ---\n"
                f"Nombre: {nombre} | Edad: {edad} años | Sexo: {sexo}\n"
                f"Motivo de consulta: {motivo}\n"
                f"Derivador: {derivador}\n"
                f"Tiempo máximo de fonación (TMF): {tmf} s\n\n"
                f"--- EVALUACIÓN PERCEPTUAL ---\n"
                f"{grbas_line}\n"
                f"{rasati_line}\n\n"
                f"--- MEDICIONES BIOACÚSTICAS (Parselmouth/VoiceLab) ---\n"
                f"F0 media: {metrics.get('f0_mean', 'N/D')} Hz | Mín: {metrics.get('f0_min', 'N/D')} | Máx: {metrics.get('f0_max', 'N/D')} | DE: {metrics.get('f0_sd', 'N/D')} | Rango: {metrics.get('f0_range', 'N/D')} Hz\n"
                f"Referencia F0 para {sexo} de {edad} años: típico={cross_check.get('f0_normative', {}).get('typical_hz', 'N/D')} Hz, "
                f"rango={cross_check.get('f0_normative', {}).get('min_hz', 'N/D')}-{cross_check.get('f0_normative', {}).get('max_hz', 'N/D')} Hz "
                f"(Colton et al. 2011 / Farías 2012)\n"
                f"Jitter: local={metrics.get('jitter_local_pct', 'N/D')}% | RAP={metrics.get('jitter_rap_pct', 'N/D')}% | PPQ5={metrics.get('jitter_ppq5_pct', 'N/D')}% | DDP={metrics.get('jitter_ddp_pct', 'N/D')}%\n"
                f"Shimmer: local={metrics.get('shimmer_local_pct', 'N/D')}% ({metrics.get('shimmer_local_db', 'N/D')} dB) | APQ3={metrics.get('shimmer_apq3_pct', 'N/D')}% | APQ5={metrics.get('shimmer_apq5_pct', 'N/D')}% | APQ11={metrics.get('shimmer_apq11_pct', 'N/D')}%\n"
                f"HNR: {metrics.get('hnr_db', 'N/D')} dB | CPPS: {metrics.get('cpps_db', 'N/D')} dB\n"
                f"NHR: {metrics.get('nhr', 'N/D')} | NNE: {metrics.get('nne_db', 'N/D')} dB\n"
                f"Formantes: F1={metrics.get('f1_hz', 'N/D')} | F2={metrics.get('f2_hz', 'N/D')} | F3={metrics.get('f3_hz', 'N/D')} | F4={metrics.get('f4_hz', 'N/D')}\n"
                f"Pendiente espectral: {resultado.get('spectral', {}).get('spectral_tilt_slope', 'N/D')}\n"
                f"AVQI v03.01: {avqi_str} (Estado: {avqi_status})\n"
                f"{cc_text}\n\n"
                f"--- INSTRUCCIONES PARA EL INFORME ---\n"
                f"1. Correlaciona los hallazgos acústicos con la escala GRBAS ingresada.\n"
                f"2. Si hay inconsistencia entre percepción y acústica, señálala como hallazgo clínico relevante.\n"
                f"3. Describe qué parámetros acústicos sugieren qué tipo de alteración fonoaudiológica (ronquedad, breathiness, astenia, tensión).\n"
                f"4. Indica qué estudios complementarios podrían complementar la evaluación.\n"
                f"5. Formato: 3-4 párrafos, tono formal técnico fonoaudiológico latinoamericano.\n"
                f"6. Incluye al final: 'Interpretación generada por IA — Requiere correlación clínica del profesional tratante.'\n"
            )
            from llm_client import groq_chat
            sintesis_ia, _model = groq_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.15,
                max_tokens=600,
            )
        except Exception as e:
            traceback.print_exc()
            sintesis_ia = "Síntesis descriptiva no disponible temporalmente. Los resultados bioacústicos fueron calculados correctamente."

    # Parse GRBAS and RASATI formatted strings
    try:
        g_dict = json.loads(grbas) if grbas.startswith('{') else {}
        grbas_str = f"G{g_dict.get('G',0)} R{g_dict.get('R',0)} B{g_dict.get('B',0)} A{g_dict.get('A',0)} S{g_dict.get('S',0)}" if g_dict else grbas
    except Exception:
        grbas_str = grbas

    try:
        r_dict = json.loads(rasati) if rasati.startswith('{') else {}
        rasati_str = f"R{r_dict.get('R',0)} A{r_dict.get('A',0)} S{r_dict.get('S',0)} A2{r_dict.get('A2',0)} T{r_dict.get('T',0)} I{r_dict.get('I',0)}" if r_dict else rasati
    except Exception:
        rasati_str = rasati

    paciente_dict = {
        "nombre": nombre, "dni": dni, "edad": edad, "sexo": sexo,
        "motivo": motivo, "derivador": derivador,
        "grbas": grbas_str, "rasati": rasati_str,
        "sintesis_ia": sintesis_ia, "tmf": tmf,
        "profesional_nombre": profesional_nombre,
        "profesional_titulo": profesional_titulo,
        "profesional_matricula": profesional_matricula,
        "profesional_centro": profesional_centro,
        "profesional_email": profesional_email,
    }

    img_path = os.path.join(tmp_dir, "graficos_clinicos.png")
    pdf_path = os.path.join(tmp_dir, "informe_clinico.pdf")

    charts = resultado.get("charts", {})

    try:
        _generar_graficos_clinicos(resultado, tmp_vocal, img_path, charts=charts)
    except Exception as e:
        traceback.print_exc()
        img_path = ""

    try:
        formants = resultado.get("formants", {}) if isinstance(resultado.get("formants"), dict) else {}
        metricas_pdf = {
            "f0_mean": metrics.get("f0_mean"),
            "f0_min": metrics.get("f0_min"),
            "f0_max": metrics.get("f0_max"),
            "f0_sd": metrics.get("f0_sd"),
            "f0_range": metrics.get("f0_range"),
            "f0_median": metrics.get("f0_median"),
            "jitter_pct": metrics.get("jitter_local_pct"),
            "jitter_rap_pct": metrics.get("jitter_rap_pct"),
            "jitter_ppq5_pct": metrics.get("jitter_ppq5_pct"),
            "jitter_ddp_pct": metrics.get("jitter_ddp_pct"),
            "shimmer_pct": metrics.get("shimmer_local_pct"),
            "shimmer_db": metrics.get("shimmer_local_db"),
            "shimmer_apq3_pct": metrics.get("shimmer_apq3_pct"),
            "shimmer_apq5_pct": metrics.get("shimmer_apq5_pct"),
            "shimmer_apq11_pct": metrics.get("shimmer_apq11_pct"),
            "shimmer_dda_pct": metrics.get("shimmer_dda_pct"),
            "hnr_db": metrics.get("hnr_db"),
            "cpps_db": metrics.get("cpps_db"),
            "nhr": metrics.get("nhr"),
            "nne_db": metrics.get("nne_db"),
            "f1_hz": formants.get("f1_hz") or metrics.get("f1_hz"),
            "f2_hz": formants.get("f2_hz") or metrics.get("f2_hz"),
            "f3_hz": formants.get("f3_hz") or metrics.get("f3_hz"),
            "f4_hz": formants.get("f4_hz") or metrics.get("f4_hz"),
            "intensity_mean_db": metrics.get("intensity_mean_db"),
            "alpha_ratio_db": metrics.get("alpha_ratio_db"),
            "spectral_slope": resultado.get("spectral", {}).get("spectral_tilt_slope"),
            "spectral_tilt": resultado.get("spectral", {}).get("spectral_tilt_intercept"),
            "avqi": resultado.get("avqi_components", {}).get("avqi"),
            "avqi_calculable": resultado.get("avqi_components", {}).get("calculable", False),
            "avqi_error": resultado.get("avqi_components", {}).get("error"),
            "avqi_status": resultado.get("avqi_components", {}).get("status", "ok"),
            "harmonics": resultado.get("harmonics", []),
            "formants": formants,
            "audio": audio_info,
            "resultado_raw": resultado,
            "parselmouth_version": resultado.get("parselmouth_version", "0.4.3"),
            "praat_script": f"VoiceLab/{resultado.get('voicelab_version', '2.0.0')}",
        }
        generar_pdf_clinico(paciente_dict, metricas_pdf, img_path, pdf_path, charts=charts, cross_check=cross_check)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al generar el PDF: {str(e)}")

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer el PDF generado: {str(e)}")

    try:
        if os.path.exists(tmp_vocal): os.remove(tmp_vocal)
        if tmp_habla and os.path.exists(tmp_habla): os.remove(tmp_habla)
        if img_path and os.path.exists(img_path): os.remove(img_path)
        if os.path.exists(pdf_path): os.remove(pdf_path)
    except Exception:
        pass

    return Response(content=pdf_bytes, media_type="application/pdf")


def _generar_graficos_clinicos(resultado: dict, audio_path: str, output_img_path: str, charts: dict = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import numpy as np
    import parselmouth
    from parselmouth.praat import call

    metrics = resultado.get("metrics", {})
    voxplot = resultado.get("voxplot", {})
    sound = parselmouth.Sound(audio_path)
    sr = sound.sampling_frequency
    dur = sound.get_total_duration()
    samples = sound.values.flatten()
    times = sound.xs()

    fig = plt.figure(figsize=(12, 14), facecolor="white")
    gs = gridspec.GridSpec(4, 2, height_ratios=[1.2, 1.8, 1.8, 2.2], hspace=0.35, wspace=0.25)

    # ---------------- 1. PRAAT SOUND EDITOR: WAVEFORM + GLOTTAL PULSES ----------------
    ax_wave = fig.add_subplot(gs[0, :])
    ax_wave.plot(times, samples, color="black", linewidth=0.6)
    ax_wave.set_facecolor("#f8fafc")
    ax_wave.set_xlim(0, dur)
    max_amp = float(np.max(np.abs(samples))) if len(samples) > 0 else 1.0
    ax_wave.set_ylim(-max_amp * 1.1, max_amp * 1.1)
    ax_wave.set_title("Praat Sound Editor — Forma de Onda y Pulsos Glóticos", fontsize=10, fontweight="bold", loc="left", color="#0f172a")

    # Overlay glottal pulses
    try:
        pitch = call(sound, "To Pitch (ac)", 0.0, 75, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, 600)
        point_proc = call(pitch, "To PointProcess")
        num_points = call(point_proc, "Get number of points")
        if num_points and num_points > 0:
            pulse_times = [call(point_proc, "Get time from index", i) for i in range(1, min(num_points + 1, 1500))]
            ax_wave.vlines(pulse_times, -max_amp * 0.9, max_amp * 0.9, color="#2563eb", linewidth=0.5, alpha=0.7, label="Pulsos glóticos")
    except Exception:
        pass
    ax_wave.set_ylabel("Amplitud", fontsize=8)
    ax_wave.tick_params(labelsize=7)
    ax_wave.grid(True, linestyle=":", alpha=0.3)

    # ---------------- 2. PRAAT SOUND EDITOR: SPECTROGRAM + F0 + INTENSITY + FORMANTS ----------------
    ax_spec = fig.add_subplot(gs[1, :])
    try:
        # Narrow-band spectrogram with proper NFFT
        nfft = int(0.030 * sr)
        Pxx, freqs, bins, im = ax_spec.specgram(samples, Fs=sr, NFFT=nfft, noverlap=int(nfft * 0.8), cmap="Greys", vmin=-60, vmax=20)
        ax_spec.set_ylim(0, 5000)
        ax_spec.set_xlim(0, dur)
        ax_spec.set_ylabel("Frecuencia (Hz)", fontsize=8, color="#0f172a")
        ax_spec.set_xlabel("Tiempo (s)", fontsize=8)
        ax_spec.set_title("Praat — Espectrograma con Pitch (azul), Intensidad (amarillo) y Formantes F1-F4 (rojo)", fontsize=10, fontweight="bold", loc="left", color="#0f172a")

        # Pitch contour overlay (Blue)
        pitch = call(sound, "To Pitch (ac)", 0.0, 75, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, 600)
        f0_vals = pitch.selected_array['frequency']
        p_times = pitch.xs()
        f0_clean = [v if v > 0 else np.nan for v in f0_vals]
        ax_spec_f0 = ax_spec.twinx()
        ax_spec_f0.plot(p_times, f0_clean, color="#0284c7", linewidth=2.0, label="F0 Pitch (Hz)")
        ax_spec_f0.set_ylim(50, 500)
        ax_spec_f0.set_ylabel("F0 (Hz)", fontsize=8, color="#0284c7")
        ax_spec_f0.tick_params(colors="#0284c7", labelsize=7)

        # Intensity contour overlay (Yellow/Green)
        intensity = call(sound, "To Intensity", 100, 0.0, True)
        int_vals = intensity.values.flatten()
        i_times = intensity.xs()
        ax_spec_int = ax_spec.twinx()
        ax_spec_int.spines["right"].set_position(("axes", 1.08))
        ax_spec_int.plot(i_times, int_vals, color="#eab308", linewidth=1.5, linestyle="--", label="Intensidad (dB)")
        ax_spec_int.set_ylim(40, 100)
        ax_spec_int.set_ylabel("Intensidad (dB)", fontsize=8, color="#ca8a04")
        ax_spec_int.tick_params(colors="#ca8a04", labelsize=7)

        # Formant tracks overlay (Red dots, pre_emphasis_from=50)
        formant = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=5500, pre_emphasis_from=50)
        f_times = [formant.get_time_from_frame_number(i) for i in range(1, formant.get_number_of_frames() + 1)]
        for f_num in [1, 2, 3, 4]:
            f_vals = [formant.get_value_at_time(f_num, t) for t in f_times]
            f_vals = [v if (v and not np.isnan(v) and v < 5000) else np.nan for v in f_vals]
            ax_spec.scatter(f_times, f_vals, color="#dc2626", s=2.5, alpha=0.8)
    except Exception as e:
        ax_spec.text(0.5, 0.5, f"Espectrograma Praat: {str(e)}", ha="center", va="center", transform=ax_spec.transAxes, color="#94a3b8")

    # ---------------- 3. VOXPLOT ACOUSTIC QUALITY PROFILE: TABLE & METRICS ----------------
    ax_table = fig.add_subplot(gs[2, 0])
    ax_table.axis("off")
    ax_table.set_title("VOXplot — Acoustic Voice Quality Profile", fontsize=10, fontweight="bold", loc="left", color="#0f172a")

    v_table = voxplot.get("table", [])
    if v_table:
        col_labels = ["Parámetro", "Valor", "Norma", "Estado"]
        cell_data = []
        cell_colors = []
        for row in v_table[:14]:
            val_str = f"{row['value']} {row.get('unit','')}".strip()
            norm_str = row.get("norm", "—")
            is_norm = row.get("is_normal", True)
            stat_str = "OK" if is_norm else "PATOLÓGICO"
            color_row = ["#ffffff", "#ffffff", "#ffffff", "#dcfce7" if is_norm else "#fee2e2"]
            cell_data.append([row["parameter"], val_str, norm_str, stat_str])
            cell_colors.append(color_row)

        table_obj = ax_table.table(cellText=cell_data, colLabels=col_labels, cellColours=cell_colors, colColours=["#f1f5f9"]*4, loc="center", cellLoc="left")
        table_obj.auto_set_font_size(False)
        table_obj.set_fontsize(6.5)
        table_obj.scale(1.0, 1.15)
    else:
        ax_table.text(0.5, 0.5, "Tabla VOXplot calculada", ha="center", va="center")

    # ---------------- 4. VOXPLOT HARMONICS / LTAS ----------------
    ax_harm = fig.add_subplot(gs[2, 1])
    harmonics = resultado.get("harmonics", [])
    if harmonics:
        h_freqs = [h["frequency_hz"] for h in harmonics]
        h_amps = [h["amplitude_db"] for h in harmonics]
        ax_harm.stem(h_freqs, h_amps, linefmt="#0284c7", markerfmt="o", basefmt="k-")
        for i, (f, a) in enumerate(zip(h_freqs, h_amps)):
            ax_harm.annotate(f"H{i+1}", (f, a), textcoords="offset points", xytext=(0, 4), fontsize=6.5, ha="center", color="#334155")
        ax_harm.set_title("Espectro Armónico H1-H10 (H1-H2)", fontsize=10, fontweight="bold", color="#0f172a")
        ax_harm.set_xlabel("Frecuencia (Hz)", fontsize=7.5)
        ax_harm.set_ylabel("Amplitud (dB)", fontsize=7.5)
        ax_harm.grid(True, linestyle="--", alpha=0.3)
    else:
        ax_harm.text(0.5, 0.5, "Armónicos no disponibles", ha="center", va="center", color="#94a3b8")

    # ---------------- 5. VOXPLOT EXACT 6-AXIS RADAR / SPIDER CHART ----------------
    ax_radar = fig.add_subplot(gs[3, :], polar=True)
    radar_axes = voxplot.get("radar_axes", [])

    if radar_axes:
        categories = [r["label"] for r in radar_axes]
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]

        # Normal boundary (Radius = 1.0)
        norm_values = [1.0] * N + [1.0]
        # Patient values
        patient_values = [r.get("norm_ratio", 1.0) for r in radar_axes]
        patient_values += patient_values[:1]

        ax_radar.set_theta_offset(np.pi / 2)
        ax_radar.set_theta_direction(-1)
        ax_radar.set_xticks(angles[:-1])
        ax_radar.set_xticklabels(categories, fontsize=9, fontweight="bold", color="#0f172a")

        # Circular green disk for normal zone
        circle_theta = np.linspace(0, 2 * np.pi, 200)
        ax_radar.fill(circle_theta, [1.0]*200, color="#22c55e", alpha=0.25, label="Región Normal (Norm)")
        ax_radar.plot(circle_theta, [1.0]*200, color="#16a34a", linewidth=1.5, linestyle="--")

        # Patient red deviation polygon
        ax_radar.fill(angles, patient_values, color="#ef4444", alpha=0.55, label="Perfil Acústico del Paciente")
        ax_radar.plot(angles, patient_values, color="#b91c1c", linewidth=2.0)
        ax_radar.scatter(angles[:-1], patient_values[:-1], color="#991b1b", s=40, zorder=10)

        # Concentric rings
        ax_radar.set_ylim(0, 2.8)
        ax_radar.set_yticks([0.5, 1.0, 1.5, 2.0, 2.5])
        ax_radar.set_yticklabels(["0.5", "1.0 (Norm)", "1.5", "2.0", "2.5"], fontsize=6.5, color="#64748b")
        ax_radar.grid(color="#cbd5e1", linestyle="--", linewidth=0.6)

        # Annotations: Hoarseness vs Breathiness
        ax_radar.text(-np.pi/4, 2.7, "Hoarseness", fontsize=11, fontweight="bold", color="#b45309", ha="center")
        ax_radar.text(np.pi/4, 2.7, "Breathiness", fontsize=11, fontweight="bold", color="#1d4ed8", ha="center")
        ax_radar.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1), fontsize=8)
        ax_radar.set_title("VOXplot Radar Chart — Severidad Multifactorial", fontsize=11, fontweight="bold", pad=20, color="#0f172a")

    plt.tight_layout()
    plt.savefig(output_img_path, dpi=220, bbox_inches="tight")
    plt.close()


# ─── ANAMNESIS INTELIGENTE ──────────────────────────────────

@app.post("/api/anamnesis/transcribir")
async def transcribir_anamnesis(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        if len(audio_bytes) < 100:
            raise HTTPException(status_code=400, detail="Audio demasiado corto o vacío")
        if len(audio_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Audio demasiado grande (máx 25MB)")

        result = transcribir_audio_groq(audio_bytes, audio.filename or "anamnesis.wav")
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error transcribiendo: {str(e)}")


@app.post("/api/anamnesis/estructurar")
async def estructurar_anamnesis_endpoint(
    transcripcion: str = Form(...),
):
    try:
        result = estructurar_anamnesis_llm(transcripcion)
        return JSONResponse(content=result)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error estructurando: {str(e)}")


@app.post("/api/anamnesis/completa")
async def anamnesis_completa(
    audio: UploadFile = File(...),
    paciente_id: str = Form(""),
):
    try:
        audio_bytes = await audio.read()
        if len(audio_bytes) < 100:
            raise HTTPException(status_code=400, detail="Audio demasiado corto o vacío")

        transcription = transcribir_audio_groq(audio_bytes, audio.filename or "anamnesis.wav")
        if transcription.get("error"):
            return JSONResponse(content={"transcripcion": transcription, "estructuracion": {}, "muestra_vocal": {}})

        estructuracion = estructurar_anamnesis_llm(transcription.get("transcripcion", ""))
        muestra = generar_muestra_vocal_prompt(estructuracion)

        return JSONResponse(content={
            "transcripcion": transcription,
            "estructuracion": estructuracion if "error" not in estructuracion else {},
            "muestra_vocal": muestra,
        })
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en anamnesis completa: {str(e)}")


# ─── CUADERNILLO TERAPÉUTICO PDF ────────────────────────────

@app.post("/api/cuadernillo/generar")
async def generar_cuadernillo_endpoint(
    paciente_nombre: str = Form(""),
    titulo: str = Form("Cuadernillo Terapéutico Vocal"),
    sesiones: int = Form(8),
    ejercicios_json: str = Form("[]"),
    contrato_json: str = Form("{}"),
    notas: str = Form(""),
):
    try:
        ejercicios = json.loads(ejercicios_json) if ejercicios_json.startswith("[") else []
        contrato = json.loads(contrato_json) if contrato_json.startswith("{") else {}
    except Exception:
        ejercicios, contrato = [], {}

    pdf_path = generar_cuadernillo_pdf(
        paciente_nombre=paciente_nombre,
        titulo=titulo,
        sesiones=sesiones,
        ejercicios=ejercicios,
        contrato=contrato,
        notas=notas,
    )

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    try:
        os.unlink(pdf_path)
    except Exception:
        pass

    import base64
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    return JSONResponse(content={
        "ok": True,
        "pdf_base64": pdf_b64,
        "filename": f"{titulo.replace(' ', '_')}.pdf",
        "size_bytes": len(pdf_bytes),
    })


# ─── MOTOR DE RECOMENDACIÓN IA TERAPÉUTICO ─────────────────

@app.post("/api/recomendar-terapia")
async def recomendar_terapia_endpoint(
    paciente_json: str = Form("{}"),
    anamnesis_json: str = Form("{}"),
    riesgo_vocal_json: str = Form("{}"),
    escalas_json: str = Form("{}"),
    acustica_json: str = Form("{}"),
):
    try:
        paciente = json.loads(paciente_json) if paciente_json.startswith("{") else {}
        anamnesis = json.loads(anamnesis_json) if anamnesis_json.startswith("{") else {}
        riesgo_vocal = json.loads(riesgo_vocal_json) if riesgo_vocal_json.startswith("{") else {}
        escalas = json.loads(escalas_json) if escalas_json.startswith("{") else {}
        acustica = json.loads(acustica_json) if acustica_json.startswith("{") else {}
    except Exception:
        paciente, anamnesis, riesgo_vocal, escalas, acustica = {}, {}, {}, {}, {}

    try:
        recomendacion = generar_recomendacion_terapeutica(
            paciente=paciente,
            anamnesis=anamnesis,
            riesgo_vocal=riesgo_vocal,
            escalas=escalas,
            acustica=acustica
        )
        return JSONResponse(content={"ok": True, "recomendacion": recomendacion})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en recomendación IA: {str(e)}")
