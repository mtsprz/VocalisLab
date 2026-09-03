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
        "glottalPulses": resultado.get("glottal_pulses", []),
        "formantTracks": resultado.get("formant_tracks", {}),
        "f0Contour": resultado.get("f0_contour", {}),
        "intensityContour": resultado.get("intensity_contour", {}),
        "classifications": resultado.get("classifications", {}),
        "voxplot": resultado.get("voxplot", {}),
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
        # Spectrogram
        Pxx, freqs, bins, im = ax_spec.specgram(samples, Fs=sr, NFFT=1024, noverlap=800, cmap="Greys", vmin=-60, vmax=20)
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

        # Formant tracks overlay (Red dots)
        formant = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=5500)
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
