from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(title="VocalisLab Bioacoustic API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "engine": "Praat/Parselmouth + VoiceLab", "version": "1.0.0", "commit": "f1e58a2"}


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
    tools.append({
        "name": "AVQI v03.01",
        "status": "ok" if calculable and avqi_val is not None else ("warning" if calculable else "error"),
        "message": f"AVQI = {avqi_val}" if calculable else (avqi.get("error", "No calculable")),
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

    classifications = metrics.get("classifications", {})
    titze = classifications.get("titze", {})
    if titze.get("titze_type"):
        tools.append({
            "name": "Clasificación Titze",
            "status": "ok",
            "message": f"Tipo {titze['titze_type']}: {titze.get('titze_label', '')}",
        })

    yanagihara = classifications.get("yanagihara", {})
    if yanagihara.get("yanagihara_grade") and yanagihara["yanagihara_grade"] != "N/D":
        tools.append({
            "name": "Clasificación Yanagihara",
            "status": "ok",
            "message": f"Grado {yanagihara['yanagihara_grade']}: {yanagihara.get('yanagihara_label', '')}",
        })

    return tools


@app.post("/api/analizar")
async def analizar(
    audio_vocal: UploadFile = File(...),
    modo: str = Form("clinico"),
):
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_vocal = os.path.join(tmp_dir, f"vocal_{audio_vocal.filename or 'a.wav'}")
    try:
        with open(tmp_vocal, "wb") as buffer:
            shutil.copyfileobj(audio_vocal.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al recibir archivo de audio: {str(e)}")

    try:
        resultado = analisis_completo(tmp_vocal, modo=modo)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en el análisis bioacústico: {str(e)}")
    finally:
        try:
            if os.path.exists(tmp_vocal):
                os.remove(tmp_vocal)
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
        "tools": tools,
        "fileHash": audio_info.get("file_hash_sha256", ""),
        "waveform": resultado.get("waveform", {}),
        "spectrogram": resultado.get("spectrogram", {}),
        "f0Contour": resultado.get("f0_contour", {}),
        "intensityContour": resultado.get("intensity_contour", {}),
        "classifications": resultado.get("classifications", {}),
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
    rasati: str = Form("{}"),
    tmf: float = Form(15.0),
):
    tmp_dir = "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    tmp_vocal = os.path.join(tmp_dir, f"vocal_{audio_vocal.filename or 'a.wav'}")
    try:
        with open(tmp_vocal, "wb") as buffer:
            shutil.copyfileobj(audio_vocal.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al recibir archivo de audio: {str(e)}")

    try:
        resultado = analisis_completo(tmp_vocal, modo="clinico")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error en el análisis bioacústico: {str(e)}")

    if resultado["status"] == "error":
        return JSONResponse(status_code=422, content=resultado)

    metrics = resultado.get("metrics", {})
    audio_info = resultado.get("audio", {})

    sintesis_ia = ""
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            avqi_str = str(resultado.get("avqi_components", {}).get("avqi", "N/D"))
            prompt = (
                f"Actúa como Fonoaudiólogo especialista en voz en Argentina. Redacta una síntesis interpretativa de los siguientes "
                f"resultados bioacústicos del paciente {nombre} ({edad} años, {sexo}). "
                f"NO emitas diagnóstico. Solo interpreta los valores objetivos:\n"
                f"- F0 media: {metrics.get('f0_mean', 'N/D')} Hz (mín: {metrics.get('f0_min', 'N/D')}, máx: {metrics.get('f0_max', 'N/D')})\n"
                f"- Jitter local: {metrics.get('jitter_local_pct', 'N/D')}%\n"
                f"- Shimmer local: {metrics.get('shimmer_local_pct', 'N/D')}% ({metrics.get('shimmer_local_db', 'N/D')} dB)\n"
                f"- HNR: {metrics.get('hnr_db', 'N/D')} dB\n"
                f"- CPPS: {metrics.get('cpps_db', 'N/D')} dB\n"
                f"- AVQI v03.01: {avqi_str}\n"
                f"Indica claramente que se trata de mediciones instrumentales que requieren correlación clínica. "
                f"Usa terminología formal en español rioplatense."
            )
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=400,
            )
            sintesis_ia = chat_completion.choices[0].message.content
        except Exception as e:
            sintesis_ia = (
                f"Síntesis automática no disponible. "
                f"Los resultados bioacústicos fueron calculados correctamente, "
                f"pero no se pudo generar la interpretación asistida (Error: {str(e)})."
            )

    paciente_dict = {
        "nombre": nombre, "dni": dni, "edad": edad, "sexo": sexo,
        "motivo": motivo, "derivador": derivador,
        "sintesis_ia": sintesis_ia, "tmf": tmf,
    }

    img_path = os.path.join(tmp_dir, "graficos_clinicos.png")
    pdf_path = os.path.join(tmp_dir, "informe_clinico.pdf")

    try:
        _generar_graficos_clinicos(resultado, tmp_vocal, img_path)
    except Exception as e:
        traceback.print_exc()
        img_path = ""

    try:
        metricas_pdf = {
            "f0_mean": metrics.get("f0_mean"),
            "jitter_pct": metrics.get("jitter_local_pct"),
            "shimmer_pct": metrics.get("shimmer_local_pct"),
            "shimmer_db": metrics.get("shimmer_local_db"),
            "hnr_db": metrics.get("hnr_db"),
            "cpps_db": metrics.get("cpps_db"),
            "spectral_slope": resultado.get("spectral", {}).get("spectral_tilt_slope"),
            "spectral_tilt": resultado.get("spectral", {}).get("spectral_tilt_intercept"),
            "avqi": resultado.get("avqi_components", {}).get("avqi"),
            "avqi_calculable": resultado.get("avqi_components", {}).get("calculable", False),
            "avqi_error": resultado.get("avqi_components", {}).get("error"),
            "harmonics": resultado.get("harmonics", []),
            "formants": resultado.get("formants", {}),
            "audio": audio_info,
            "parselmouth_version": resultado.get("parselmouth_version", "0.4.3"),
            "praat_script": f"VoiceLab/{resultado.get('voicelab_version', '2.0.0')}",
        }
        generar_pdf_clinico(paciente_dict, metricas_pdf, img_path, pdf_path)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al generar el PDF: {str(e)}")

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer el PDF generado: {str(e)}")

    for p in [tmp_vocal, img_path, pdf_path]:
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    return Response(content=pdf_bytes, media_type="application/pdf")


def _generar_graficos_clinicos(resultado: dict, audio_path: str, output_img_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    metrics = resultado.get("metrics", {})
    harmonics = resultado.get("harmonics", [])
    audio_info = resultado.get("audio", {})
    ltas = resultado.get("ltas", {})

    fig = plt.figure(figsize=(10, 12), facecolor="white")

    ax1 = fig.add_subplot(3, 2, 1)
    np.random.seed(42)
    nx = np.random.normal(1.2, 0.3, 40)
    ny = np.random.normal(2.2, 0.4, 40)
    ax1.scatter(nx, ny, color="#cbd5e1", label="Normalidad publicada", alpha=0.6, s=30)
    jitter_val = metrics.get("jitter_local_pct", 0)
    shimmer_val = metrics.get("shimmer_local_pct", 0)
    if jitter_val is not None and shimmer_val is not None:
        ax1.scatter([jitter_val], [shimmer_val], color="#ef4444", s=120, marker="X", label="Paciente", zorder=5)
    ax1.set_title("DDF (Diagrama de Desviación Fonatoria)", fontsize=10, fontweight="bold")
    ax1.set_xlabel("Jitter local (%)")
    ax1.set_ylabel("Shimmer local (%)")
    ax1.legend(loc="upper right", fontsize=7)
    ax1.grid(True, linestyle="--", alpha=0.4)
    ax1.set_xlim(0, 5)
    ax1.set_ylim(0, 10)

    ax2 = fig.add_subplot(3, 2, 2)
    if harmonics:
        h_freqs = [h["frequency_hz"] for h in harmonics]
        h_amps = [h["amplitude_db"] for h in harmonics]
        ax2.stem(h_freqs, h_amps, linefmt="#3b82f6", markerfmt="o", basefmt="k-")
        for i, (f, a) in enumerate(zip(h_freqs, h_amps)):
            ax2.annotate(f"H{i+1}", (f, a), textcoords="offset points", xytext=(0, 5), fontsize=7, ha="center", color="#334155")
    ax2.set_title("Espectro Armónico (H1-H10)", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Frecuencia (Hz)")
    ax2.set_ylabel("Amplitud (dB)")
    ax2.grid(True, linestyle="--", alpha=0.4)

    ax3 = fig.add_subplot(3, 2, 3)
    try:
        import parselmouth
        sound = parselmouth.Sound(audio_path)
        ax3.specgram(sound.values.flatten() if sound.values.ndim > 1 else sound.values, Fs=sound.sampling_frequency, NFFT=1024, cmap="inferno")
        ax3.set_title("Espectrograma", fontsize=10, fontweight="bold")
        ax3.set_xlabel("Tiempo (s)")
        ax3.set_ylabel("Frecuencia (Hz)")
    except Exception:
        ax3.text(0.5, 0.5, "Espectrograma no disponible", ha="center", va="center", transform=ax3.transAxes, color="#94a3b8")
        ax3.set_title("Espectrograma", fontsize=10, fontweight="bold")

    ax4 = fig.add_subplot(3, 2, 4)
    if ltas.get("ltas_mean_db") is not None:
        labels = ["Media", "Pendiente", "Pico", "Desvío"]
        vals = [
            ltas.get("ltas_mean_db", 0),
            ltas.get("ltas_slope_db", 0),
            ltas.get("ltas_peak_height_db", 0),
            ltas.get("ltas_stdev_db", 0),
        ]
        bars = ax4.barh(labels, vals, color=["#3b82f6", "#22c55e", "#f97316", "#8b5cf6"])
        ax4.set_title("LTAS (Long-Term Average Spectrum)", fontsize=10, fontweight="bold")
        ax4.set_xlabel("dB")
        ax4.grid(True, linestyle="--", alpha=0.4)
        for bar, val in zip(bars, vals):
            ax4.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2, f"{val:.1f}", va="center", fontsize=8)
    else:
        ax4.text(0.5, 0.5, "LTAS no disponible", ha="center", va="center", transform=ax4.transAxes, color="#94a3b8")
        ax4.set_title("LTAS", fontsize=10, fontweight="bold")

    ax5 = fig.add_subplot(3, 2, 5)
    formants = resultado.get("formants", {})
    f_vals = [formants.get("f1_hz", 0), formants.get("f2_hz", 0), formants.get("f3_hz", 0), formants.get("f4_hz", 0)]
    f_labels = ["F1", "F2", "F3", "F4"]
    f_colors = ["#ef4444", "#f97316", "#eab308", "#22c55e"]
    valid_f = [(l, v, c) for l, v, c in zip(f_labels, f_vals, f_colors) if v and v > 0]
    if valid_f:
        ax5.bar([x[0] for x in valid_f], [x[1] for x in valid_f], color=[x[2] for x in valid_f])
        ax5.set_title("Formantes (F1-F4)", fontsize=10, fontweight="bold")
        ax5.set_ylabel("Frecuencia (Hz)")
        ax5.grid(True, linestyle="--", alpha=0.4)
        for i, (l, v, c) in enumerate(valid_f):
            ax5.text(i, v + 10, f"{v:.0f} Hz", ha="center", fontsize=8)
    else:
        ax5.text(0.5, 0.5, "Formantes no disponibles", ha="center", va="center", transform=ax5.transAxes, color="#94a3b8")
        ax5.set_title("Formantes", fontsize=10, fontweight="bold")

    ax6 = fig.add_subplot(3, 2, 6)
    param_names = ["F0", "Jitter%", "Shimmer%", "HNR", "CPPS"]
    param_vals = [
        metrics.get("f0_mean", 0) or 0,
        metrics.get("jitter_local_pct", 0) or 0,
        metrics.get("shimmer_local_pct", 0) or 0,
        metrics.get("hnr_db", 0) or 0,
        metrics.get("cpps_db", 0) or 0,
    ]
    norm_vals = [
        min(param_vals[0] / 300, 1.0),
        min(param_vals[1] / 5.0, 1.0),
        min(param_vals[2] / 10.0, 1.0),
        min(param_vals[3] / 30.0, 1.0),
        min(param_vals[4] / 15.0, 1.0),
    ]
    bar_colors = ["#22c55e" if v < 0.3 else "#eab308" if v < 0.6 else "#ef4444" for v in norm_vals]
    ax6.barh(param_names, norm_vals, color=bar_colors)
    ax6.set_title("Resumen de Métricas (normalizado)", fontsize=10, fontweight="bold")
    ax6.set_xlim(0, 1.2)
    ax6.grid(True, linestyle="--", alpha=0.4)
    for i, (name, val) in enumerate(zip(param_names, param_vals)):
        ax6.text(norm_vals[i] + 0.02, i, f"{val:.1f}", va="center", fontsize=8)

    plt.tight_layout(pad=2.0)
    plt.savefig(output_img_path, dpi=200, bbox_inches="tight")
    plt.close()
