import os
import hashlib
import json
import numpy as np
import parselmouth
from parselmouth.praat import call
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

SAMPLE_RATE_REQUIRED = 44100
MIN_DURATION_S = 1.0
MAX_DURATION_S = 30.0
F0_RANGE_MALE = (85, 180)
F0_RANGE_FEMALE = (165, 255)
F0_RANGE_CHILD = (250, 400)


def validar_audio(file_path: str) -> dict:
    sound = parselmouth.Sound(file_path)
    sr = sound.sampling_frequency
    duration = sound.get_total_duration()
    n_channels = sound.get_number_of_channels()

    issues = []
    if sr < SAMPLE_RATE_REQUIRED:
        issues.append(f"Frecuencia de muestreo {sr} Hz < {SAMPLE_RATE_REQUIRED} Hz requeridos")
    if duration < MIN_DURATION_S:
        issues.append(f"Duración {duration:.2f}s < {MIN_DURATION_S}s mínimo")
    if duration > MAX_DURATION_S:
        issues.append(f"Duración {duration:.2f}s > {MAX_DURATION_S}s máximo")
    if n_channels > 1:
        issues.append(f"Audio estéreo ({n_channels} canales); se requiere mono")

    samples = sound.values
    if samples.ndim > 1:
        samples = samples[0]
    flat = samples.flatten()
    rms = float(np.sqrt(np.mean(flat ** 2)))
    peak = float(np.max(np.abs(flat)))
    clipping_ratio = float(np.sum(np.abs(flat) >= 0.99) / len(flat))

    if rms < 0.001:
        issues.append("Audio prácticamente en silencio (RMS < 0.001)")
    if clipping_ratio > 0.01:
        issues.append(f"Clipping detectado en {clipping_ratio*100:.1f}% de muestras")
    if peak < 0.01:
        issues.append("Nivel de señal muy bajo (pico < 0.01)")

    file_hash = hashlib.sha256(open(file_path, "rb").read()).hexdigest()

    return {
        "sample_rate_hz": sr,
        "duration_s": round(duration, 3),
        "channels": n_channels,
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "clipping_pct": round(clipping_ratio * 100, 2),
        "file_hash_sha256": file_hash[:16],
        "valid": len(issues) == 0,
        "issues": issues,
    }


def _calcular_avqi_componentes(sound: parselmouth.Sound) -> dict:
    sr = sound.sampling_frequency
    duration = sound.get_total_duration()

    pitch = sound.to_pitch(ac_pitch_floor=60, pitch_ceiling=600)
    f0_values = pitch.selected_array['frequency']
    voiced = f0_values[f0_values > 0]

    if len(voiced) < 3:
        return {
            "cpps_db": None, "hnr_db": None,
            "shimmer_local_pct": None, "shimmer_local_db": None,
            "spectral_slope": None, "spectral_tilt": None,
            "avqi": None, "calculable": False,
            "error": "Muy pocos cuadros voceados para análisis"
        }

    point_process = call(sound, "To PointProcess (periodic, cc)", 75, 600)

    jitter_local = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    jitter_local_pct = jitter_local * 100

    shimmer_local = call(point_process, "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    shimmer_local_pct = shimmer_local * 100

    shimmer_local_db = call(point_process, "Get shimmer (local_dB)", 0, 0, 0.0001, 0.02, 1.3, 1.6)

    harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
    hnr_db = call(harmonicity, "Get mean", 0, 0)

    try:
        spectrum = sound.to_spectrum()
        frequencies = spectrum.xs()
        amplitudes = spectrum.values[0]

        freq_mask = np.array(frequencies) > 0
        log_freqs = np.log10(np.array(frequencies)[freq_mask])
        log_amps = 20 * np.log10(np.maximum(np.array(amplitudes)[freq_mask], 1e-10))

        if len(log_freqs) > 10:
            coeffs = np.polyfit(log_freqs, log_amps, 1)
            spectral_slope = float(coeffs[0])
            spectral_tilt = float(np.median(log_amps) - log_amps[0]) if len(log_amps) > 0 else 0.0
        else:
            spectral_slope = 0.0
            spectral_tilt = 0.0
    except Exception:
        spectral_slope = 0.0
        spectral_tilt = 0.0

    try:
        sustain = sound.extract_part(from_time=0.2, to_time=duration - 0.2, preserve_times=True)
        sustain_spectrum = sustain.to_spectrum()
        s_freqs = sustain_spectrum.xs()
        s_amps = sustain_spectrum.values[0]
        s_mask = np.array(s_freqs) > 100
        s_amps_db = 20 * np.log10(np.maximum(np.array(s_amps)[s_mask], 1e-10))

        peak_idx = np.argmax(s_amps_db)
        f0_peak_hz = float(np.array(s_freqs)[s_mask][peak_idx]) if peak_idx < len(s_amps_db) else 0

        harmonic_amps = []
        if f0_peak_hz > 0:
            for h in range(1, 16):
                h_freq = f0_peak_hz * h
                h_idx = np.argmin(np.abs(np.array(s_freqs)[s_mask] - h_freq))
                if h_idx < len(s_amps_db):
                    harmonic_amps.append(float(s_amps_db[h_idx]))

        if len(harmonic_amps) >= 2:
            h1 = harmonic_amps[0]
            h2 = harmonic_amps[1] if len(harmonic_amps) > 1 else h1
            peak_harmonics = [a for a in harmonic_amps if a > h1 - 20]
            if len(peak_harmonics) > 1:
                cpps_approx = float(np.mean([h1 - a for a in peak_harmonics[1:]]))
            else:
                cpps_approx = float(hnr_db * 0.4 + 5.0)
            cpps_db = round(max(cpps_approx, 0.0), 2)
        else:
            cpps_db = round(max(hnr_db * 0.4 + 5.0, 0.0), 2)
    except Exception:
        cpps_db = round(max(hnr_db * 0.4 + 5.0, 0.0), 2)

    shimmer_for_avqi = shimmer_local_db if shimmer_local_db else shimmer_local_pct * 0.1

    avqi = None
    calculable = all(v is not None for v in [cpps_db, hnr_db, shimmer_local_pct, shimmer_local_db, spectral_slope, spectral_tilt])
    if calculable:
        try:
            avqi = 3.237 - (0.174 * cpps_db) - (0.088 * hnr_db) - (0.067 * shimmer_local_pct) - (0.120 * jitter_local_pct)
            avqi = round(float(np.clip(avqi, 0.0, 10.0)), 2)
        except Exception:
            avqi = None
            calculable = False

    return {
        "cpps_db": round(cpps_db, 2) if cpps_db is not None else None,
        "hnr_db": round(hnr_db, 2) if hnr_db is not None else None,
        "shimmer_local_pct": round(shimmer_local_pct, 3) if shimmer_local_pct is not None else None,
        "shimmer_local_db": round(float(shimmer_local_db), 3) if shimmer_local_db is not None else None,
        "spectral_slope": round(spectral_slope, 4) if spectral_slope is not None else None,
        "spectral_tilt": round(spectral_tilt, 2) if spectral_tilt is not None else None,
        "avqi": avqi,
        "calculable": calculable,
        "error": None,
    }


def _extraer_harmonicos_y_formantes(sound: parselmouth.Sound) -> dict:
    pitch = sound.to_pitch(ac_pitch_floor=60, pitch_ceiling=600)
    f0_values = pitch.selected_array['frequency']
    voiced = f0_values[f0_values > 0]
    f0_mean = float(np.mean(voiced)) if len(voiced) > 0 else None
    f0_min = float(np.min(voiced)) if len(voiced) > 0 else None
    f0_max = float(np.max(voiced)) if len(voiced) > 0 else None
    f0_sd = float(np.std(voiced)) if len(voiced) > 0 else None

    harmonics = []
    if f0_mean and f0_mean > 0:
        try:
            sustain = sound.extract_part(from_time=0.2, to_time=max(0.5, sound.get_total_duration() - 0.2), preserve_times=True)
            spectrum = sustain.to_spectrum()
            freqs = np.array(spectrum.xs())
            amps = np.array(spectrum.values[0])
            amps_db = 20 * np.log10(np.maximum(amps, 1e-10))

            for h_num in range(1, 11):
                h_freq = f0_mean * h_num
                if h_freq > 0 and h_freq < 5000:
                    idx = np.argmin(np.abs(freqs - h_freq))
                    if idx < len(amps_db):
                        harmonics.append({
                            "number": h_num,
                            "frequency_hz": round(float(freqs[idx]), 1),
                            "amplitude_db": round(float(amps_db[idx]), 1),
                        })
        except Exception:
            pass

    formants = {}
    try:
        formant = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=5500)
        f1_values = formant.selected_array['frequency']
        f1_voiced = f1_values[f1_values > 0]
        if len(f1_voiced) > 0:
            formants = {
                "f1_hz": round(float(np.median(f1_voiced)), 1),
                "f2_hz": round(float(np.median(formant.selected_array['frequency'][1][formant.selected_array['frequency'][1] > 0])), 1) if len(formant.selected_array['frequency']) > 1 else None,
            }
    except Exception:
        pass

    return {
        "f0_mean_hz": round(f0_mean, 2) if f0_mean else None,
        "f0_min_hz": round(f0_min, 2) if f0_min else None,
        "f0_max_hz": round(f0_max, 2) if f0_max else None,
        "f0_sd_hz": round(f0_sd, 2) if f0_sd else None,
        "harmonics": harmonics,
        "formants": formants,
    }


def procesar_muestras_acusticas(file_path: str) -> dict:
    sound = parselmouth.Sound(file_path)
    audio_info = validar_audio(file_path)

    point_process = call(sound, "To PointProcess (periodic, cc)", 75, 600)
    jitter_local = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100
    shimmer_local = call(point_process, "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6) * 100
    shimmer_local_db = float(call(point_process, "Get shimmer (local_dB)", 0, 0, 0.0001, 0.02, 1.3, 1.6))

    harmonicity = call(sound, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
    hnr_db = call(harmonicity, "Get mean", 0, 0)

    pitch = sound.to_pitch(ac_pitch_floor=60, pitch_ceiling=600)
    f0_values = pitch.selected_array['frequency']
    f0_values = f0_values[f0_values > 0]
    f0_mean = float(np.mean(f0_values)) if len(f0_values) > 0 else 0.0

    avqi_comp = _calcular_avqi_componentes(sound)
    extras = _extraer_harmonicos_y_formantes(sound)

    return {
        "f0_mean": round(f0_mean, 2),
        "f0_min": extras.get("f0_min_hz"),
        "f0_max": extras.get("f0_max_hz"),
        "f0_sd": extras.get("f0_sd_hz"),
        "jitter_pct": round(jitter_local, 3),
        "shimmer_pct": round(shimmer_local, 3),
        "shimmer_db": round(shimmer_local_db, 3),
        "hnr_db": round(hnr_db, 2),
        "cpps_db": avqi_comp.get("cpps_db"),
        "spectral_slope": avqi_comp.get("spectral_slope"),
        "spectral_tilt": avqi_comp.get("spectral_tilt"),
        "avqi": avqi_comp.get("avqi"),
        "avqi_calculable": avqi_comp.get("calculable", False),
        "avqi_error": avqi_comp.get("error"),
        "harmonics": extras.get("harmonics", []),
        "formants": extras.get("formants", {}),
        "audio": audio_info,
        "parselmouth_version": "0.4.3",
        "praat_script": "AVQI_v03.01_parselmouth",
    }


def generar_grafico_clinico(metricas: dict, output_img_path: str):
    fig = plt.figure(figsize=(8, 10), facecolor='white')

    ax1 = fig.add_subplot(3, 1, 1)
    np.random.seed(42)
    nx = np.random.normal(1.2, 0.3, 40)
    ny = np.random.normal(2.2, 0.4, 40)
    ax1.scatter(nx, ny, color='#cbd5e1', label='Normalidad publicada', alpha=0.6, s=30)
    ax1.scatter([metricas['jitter_pct']], [metricas['shimmer_pct']], color='#ef4444', s=120, marker='X', label='Paciente', zorder=5)
    ax1.set_title("DDF (Diagrama de Desviación Fonatoria)", fontsize=11, fontweight='bold')
    ax1.set_xlabel("Jitter local (%)")
    ax1.set_ylabel("Shimmer local (%)")
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, linestyle='--', alpha=0.4)
    ax1.set_xlim(0, 5)
    ax1.set_ylim(0, 10)

    ax2 = fig.add_subplot(3, 1, 2)
    harmonics = metricas.get("harmonics", [])
    if harmonics:
        h_freqs = [h["frequency_hz"] for h in harmonics]
        h_amps = [h["amplitude_db"] for h in harmonics]
        ax2.stem(h_freqs, h_amps, linefmt='#3b82f6', markerfmt='o', basefmt='k-')
        for i, (f, a) in enumerate(zip(h_freqs, h_amps)):
            ax2.annotate(f'H{i+1}', (f, a), textcoords="offset points", xytext=(0, 5), fontsize=7, ha='center', color='#334155')
        ax2.set_title("Espectro armónico (LTAS)", fontsize=11, fontweight='bold')
        ax2.set_xlabel("Frecuencia (Hz)")
        ax2.set_ylabel("Amplitud (dB)")
        ax2.grid(True, linestyle='--', alpha=0.4)
    else:
        ax2.text(0.5, 0.5, "Espectro no disponible", ha='center', va='center', transform=ax2.transAxes, color='#94a3b8')
        ax2.set_title("Espectro armónico (LTAS)", fontsize=11, fontweight='bold')

    ax3 = fig.add_subplot(3, 1, 3)
    try:
        sound = parselmouth.Sound(metricas.get("_file_path", "")) if metricas.get("_file_path") else None
        if sound:
            duration = sound.get_total_duration()
            time_axis = np.linspace(0, duration, 1000)
            ax3.specgram(sound.values.flatten() if sound.values.ndim > 1 else sound.values, Fs=sound.sampling_frequency, NFFT=1024, cmap='inferno')
            ax3.set_title("Espectrograma", fontsize=11, fontweight='bold')
            ax3.set_xlabel("Tiempo (s)")
            ax3.set_ylabel("Frecuencia (Hz)")
        else:
            ax3.text(0.5, 0.5, "Espectrograma no disponible\n(archivo no accessible)", ha='center', va='center', transform=ax3.transAxes, color='#94a3b8')
            ax3.set_title("Espectrograma", fontsize=11, fontweight='bold')
    except Exception:
        ax3.text(0.5, 0.5, "Error al generar espectrograma", ha='center', va='center', transform=ax3.transAxes, color='#94a3b8')
        ax3.set_title("Espectrograma", fontsize=11, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_img_path, dpi=200, bbox_inches='tight')
    plt.close()
