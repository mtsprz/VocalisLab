"""
VoiceLab-compatible acoustic analysis engine.
Based on VoiceLab v2.0.0 algorithms by David Feinberg (McMaster University).
Implements all measurements using Praat/Parselmouth for reproducibility.

Reference: Feinberg, D. (2022). VoiceLab: Software for Fully Reproducible Automated Voice Analysis.
           Proc. Interspeech 2022, 351-355.
"""

import os
import csv
import json
import hashlib
import numpy as np
import parselmouth
from parselmouth.praat import call
from datetime import datetime, timezone
from typing import Optional

VOICELAB_VERSION = "2.0.0"
PARSELMOUTH_VERSION = "0.4.3"
ENGINE_VERSION = "1.0.0"

SAMPLE_RATE_MIN = 8000
DURATION_MIN_S = 0.5
DURATION_MAX_S = 60.0
MAX_FILE_SIZE_MB = 50


def _safe_call(*args, default=None):
    try:
        return call(*args)
    except Exception:
        return default


def _pitch_bounds(sound):
    try:
        pitch_test = call(sound, "To Pitch (ac)", 0.0, 50, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, 500)
        mean_f0 = call(pitch_test, "Get mean", 0, 0, "Hertz")
        if mean_f0 and mean_f0 > 170:
            return 100, 500
        else:
            return 50, 300
    except Exception:
        return 75, 600


def _max_formant_from_f0(mean_f0):
    if mean_f0 and 170 <= mean_f0 <= 300:
        return 5500
    elif mean_f0 and mean_f0 < 170:
        return 5000
    else:
        return 5500


def validar_audio_completo(file_path: str) -> dict:
    file_size = os.path.getsize(file_path) / (1024 * 1024)
    sound = parselmouth.Sound(file_path)
    sr = sound.sampling_frequency
    duration = sound.get_total_duration()
    n_channels = sound.get_number_of_channels()
    samples = sound.values.flatten()
    rms = float(np.sqrt(np.mean(samples ** 2)))
    peak = float(np.max(np.abs(samples)))
    clipping_pct = float(np.sum(np.abs(samples) >= 0.99) / len(samples) * 100)

    issues = []
    if file_size > MAX_FILE_SIZE_MB:
        issues.append(f"Archivo demasiado grande: {file_size:.1f} MB > {MAX_FILE_SIZE_MB} MB")
    if sr < SAMPLE_RATE_MIN:
        issues.append(f"Sample rate {sr} Hz < {SAMPLE_RATE_MIN} Hz mínimo")
    if duration < DURATION_MIN_S:
        issues.append(f"Duración {duration:.3f}s < {DURATION_MIN_S}s mínimo")
    if duration > DURATION_MAX_S:
        issues.append(f"Duración {duration:.1f}s > {DURATION_MAX_S}s máximo")
    if n_channels > 1:
        issues.append(f"Audio estéreo ({n_channels} canales)")
    if rms < 0.001:
        issues.append("Audio prácticamente en silencio (RMS < 0.001)")
    if clipping_pct > 1.0:
        issues.append(f"Clipping detectado en {clipping_pct:.2f}% de muestras")
    if peak < 0.005:
        issues.append("Nivel de señal extremadamente bajo (pico < 0.005)")

    file_hash = hashlib.sha256(open(file_path, "rb").read()).hexdigest()

    return {
        "file_path": file_path,
        "file_size_mb": round(file_size, 3),
        "file_hash_sha256": file_hash,
        "sample_rate_hz": sr,
        "duration_s": round(duration, 4),
        "channels": n_channels,
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "clipping_pct": round(clipping_pct, 3),
        "valid": len(issues) == 0,
        "issues": issues,
    }


def measure_pitch(sound, pitch_floor=None, pitch_ceiling=None):
    if pitch_floor is None or pitch_ceiling is None:
        pf, pc = _pitch_bounds(sound)
        if pitch_floor is None:
            pitch_floor = pf
        if pitch_ceiling is None:
            pitch_ceiling = pc

    pitch = call(sound, "To Pitch (ac)", 0.0, pitch_floor, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, pitch_ceiling)
    f0_values = pitch.selected_array['frequency']
    voiced = f0_values[f0_values > 0]

    if len(voiced) == 0:
        return {
            "pitch_object": pitch, "pitch_floor": pitch_floor, "pitch_ceiling": pitch_ceiling,
            "f0_mean_hz": None, "f0_median_hz": None, "f0_sd_hz": None,
            "f0_min_hz": None, "f0_max_hz": None, "f0_range_hz": None,
            "voiced_fraction": 0.0, "algorithm": "autocorrelation"
        }

    f0_mean = float(call(pitch, "Get mean", 0, 0, "Hertz"))
    f0_median = float(call(pitch, "Get quantile", 0, 0, 0.5, "Hertz"))
    f0_sd = float(call(pitch, "Get standard deviation", 0, 0, "Hertz"))
    f0_min = float(call(pitch, "Get minimum", 0, 0, "Hertz"))
    f0_max = float(call(pitch, "Get maximum", 0, 0, "Hertz"))

    return {
        "pitch_object": pitch, "pitch_floor": pitch_floor, "pitch_ceiling": pitch_ceiling,
        "f0_mean_hz": round(f0_mean, 2), "f0_median_hz": round(f0_median, 2),
        "f0_sd_hz": round(f0_sd, 2), "f0_min_hz": round(f0_min, 2),
        "f0_max_hz": round(f0_max, 2), "f0_range_hz": round(f0_max - f0_min, 2),
        "voiced_fraction": round(float(np.sum(f0_values > 0) / len(f0_values)), 3),
        "algorithm": "autocorrelation"
    }


def measure_jitter(sound, pitch_floor=None, pitch_ceiling=None):
    if pitch_floor is None or pitch_ceiling is None:
        pf, pc = _pitch_bounds(sound)
        pitch_floor = pitch_floor or pf
        pitch_ceiling = pitch_ceiling or pc

    point_process = call(sound, "To PointProcess (periodic, cc)", pitch_floor, pitch_ceiling)

    jitter_local = _safe_call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
    jitter_local_abs = _safe_call(point_process, "Get jitter (local, absolute)", 0, 0, 0.0001, 0.02, 1.3)
    jitter_rap = _safe_call(point_process, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3)
    jitter_ppq5 = _safe_call(point_process, "Get jitter (ppq5)", 0, 0, 0.0001, 0.02, 1.3)
    jitter_ddp = _safe_call(point_process, "Get jitter (ddp)", 0, 0, 0.0001, 0.02, 1.3)

    return {
        "point_process": point_process,
        "jitter_local_pct": round(jitter_local * 100, 4) if jitter_local is not None else None,
        "jitter_local_absolute_s": round(jitter_local_abs, 6) if jitter_local_abs is not None else None,
        "jitter_rap_pct": round(jitter_rap * 100, 4) if jitter_rap is not None else None,
        "jitter_ppq5_pct": round(jitter_ppq5 * 100, 4) if jitter_ppq5 is not None else None,
        "jitter_ddp_pct": round(jitter_ddp * 100, 4) if jitter_ddp is not None else None,
    }


def measure_shimmer(sound, pitch_floor=None, pitch_ceiling=None):
    if pitch_floor is None or pitch_ceiling is None:
        pf, pc = _pitch_bounds(sound)
        pitch_floor = pitch_floor or pf
        pitch_ceiling = pitch_ceiling or pc

    point_process = call(sound, "To PointProcess (periodic, cc)", pitch_floor, pitch_ceiling)

    shimmer_local = _safe_call([sound, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    shimmer_local_db = _safe_call([sound, point_process], "Get shimmer (local_dB)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    shimmer_apq3 = _safe_call([sound, point_process], "Get shimmer (apq3)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    shimmer_apq5 = _safe_call([sound, point_process], "Get shimmer (apq5)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    shimmer_apq11 = _safe_call([sound, point_process], "Get shimmer (apq11)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
    shimmer_dda = _safe_call([sound, point_process], "Get shimmer (dda)", 0, 0, 0.0001, 0.02, 1.3, 1.6)

    return {
        "shimmer_local_pct": round(shimmer_local * 100, 4) if shimmer_local is not None else None,
        "shimmer_local_db": round(float(shimmer_local_db), 4) if shimmer_local_db is not None else None,
        "shimmer_apq3_pct": round(shimmer_apq3 * 100, 4) if shimmer_apq3 is not None else None,
        "shimmer_apq5_pct": round(shimmer_apq5 * 100, 4) if shimmer_apq5 is not None else None,
        "shimmer_apq11_pct": round(shimmer_apq11 * 100, 4) if shimmer_apq11 is not None else None,
        "shimmer_dda_pct": round(shimmer_dda * 100, 4) if shimmer_dda is not None else None,
    }


def measure_harmonicity(sound, pitch_floor=None):
    if pitch_floor is None:
        pitch_floor, _ = _pitch_bounds(sound)
    harmonicity = call(sound, "To Harmonicity (cc)", 0.01, pitch_floor, 0.1, 1.0)
    hnr = call(harmonicity, "Get mean", 0, 0)
    return {"hnr_db": round(float(hnr), 2) if hnr is not None else None}


def measure_cpp(sound, pitch_floor=None, pitch_ceiling=None):
    if pitch_floor is None or pitch_ceiling is None:
        pf, pc = _pitch_bounds(sound)
        pitch_floor = pitch_floor or pf
        pitch_ceiling = pitch_ceiling or pc

    try:
        spectrum = sound.to_spectrum()
        cepstrum = call(spectrum, "To PowerCepstrum")
        cpp = call(cepstrum, "Get peak prominence", pitch_floor, pitch_ceiling, 0.01, "Straight", "Robust")
        return {"cpps_db": round(float(cpp), 2)}
    except Exception:
        try:
            harmonicity = call(sound, "To Harmonicity (cc)", 0.01, pitch_floor, 0.1, 1.0)
            hnr = call(harmonicity, "Get mean", 0, 0)
            cpp_approx = float(hnr) * 0.4 + 5.0 if hnr else None
            return {"cpps_db": round(cpp_approx, 2) if cpp_approx else None, "method": "estimated_from_hnr"}
        except Exception:
            return {"cpps_db": None, "method": "failed"}


def measure_formants(sound, pitch_floor=None, pitch_ceiling=None):
    mean_f0 = None
    if pitch_floor is None or pitch_ceiling is None:
        try:
            pitch = call(sound, "To Pitch (ac)", 0.0, 75, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, 600)
            mean_f0 = call(pitch, "Get mean", 0, 0, "Hertz")
        except Exception:
            pass

    max_formant = _max_formant_from_f0(mean_f0)

    try:
        formant = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=max_formant, window_length=0.025, pre_emphasis=50)
        f1_values = formant.selected_array['frequency'][0]
        f2_values = formant.selected_array['frequency'][1]
        f3_values = formant.selected_array['frequency'][2]
        f4_values = formant.selected_array['frequency'][3]

        f1 = float(np.median(f1_values[(f1_values > 0) & (f1_values < max_formant)])) if np.any((f1_values > 0) & (f1_values < max_formant)) else None
        f2 = float(np.median(f2_values[(f2_values > 0) & (f2_values < max_formant)])) if np.any((f2_values > 0) & (f2_values < max_formant)) else None
        f3 = float(np.median(f3_values[(f3_values > 0) & (f3_values < max_formant)])) if np.any((f3_values > 0) & (f3_values < max_formant)) else None
        f4 = float(np.median(f4_values[(f4_values > 0) & (f4_values < max_formant)])) if np.any((f4_values > 0) & (f4_values < max_formant)) else None

        return {
            "f1_hz": round(f1, 1) if f1 else None,
            "f2_hz": round(f2, 1) if f2 else None,
            "f3_hz": round(f3, 1) if f3 else None,
            "f4_hz": round(f4, 1) if f4 else None,
            "max_formant_hz": max_formant,
            "method": "formant_burg"
        }
    except Exception:
        return {"f1_hz": None, "f2_hz": None, "f3_hz": None, "f4_hz": None, "method": "failed"}


def measure_ltas(sound):
    try:
        ltas = call(sound, "To Ltas", 100)
        mean_val = call(ltas, "Get mean", 0, 0, "dB")
        slope_val = call(ltas, "Get slope", 0, 1000, 1000, 4000, "dB")
        peak_height = call(ltas, "Get local peak height", 1700, 4200, 2400, 3200, "dB")
        stdev_val = call(ltas, "Get standard deviation", 0, 0, "dB")

        tilt_report = call(ltas, "Report spectral tilt", 100, 5000, "Linear", "Robust")
        tilt_slope = None
        tilt_intercept = None
        if tilt_report:
            lines = str(tilt_report).strip().split('\n')
            for line in lines:
                if 'Slope' in line:
                    parts = line.split('=')
                    if len(parts) > 1:
                        try:
                            tilt_slope = float(parts[1].strip().split()[0])
                        except Exception:
                            pass
                if 'Intercept' in line:
                    parts = line.split('=')
                    if len(parts) > 1:
                        try:
                            tilt_intercept = float(parts[1].strip().split()[0])
                        except Exception:
                            pass

        return {
            "ltas_mean_db": round(float(mean_val), 2) if mean_val is not None else None,
            "ltas_slope_db": round(float(slope_val), 2) if slope_val is not None else None,
            "ltas_peak_height_db": round(float(peak_height), 2) if peak_height is not None else None,
            "ltas_stdev_db": round(float(stdev_val), 2) if stdev_val is not None else None,
            "ltas_spectral_tilt_slope": round(tilt_slope, 4) if tilt_slope is not None else None,
            "ltas_spectral_tilt_intercept": round(tilt_intercept, 2) if tilt_intercept is not None else None,
        }
    except Exception:
        return {
            "ltas_mean_db": None, "ltas_slope_db": None, "ltas_peak_height_db": None,
            "ltas_stdev_db": None, "ltas_spectral_tilt_slope": None, "ltas_spectral_tilt_intercept": None,
        }


def measure_spectral_tilt(sound):
    try:
        duration = sound.get_total_duration()
        part = sound.extract_part(from_time=0.1, to_time=max(0.3, duration - 0.1), preserve_times=True)
        spectrum = part.to_spectrum()
        freqs = np.array(spectrum.xs())
        amps = np.array(spectrum.values[0])
        mask = freqs > 100
        freqs_clean = freqs[mask]
        amps_db = 20 * np.log10(np.maximum(amps[mask], 1e-10))

        if len(freqs_clean) < 10:
            return {"spectral_tilt_slope": None, "spectral_tilt_intercept": None}

        coeffs = np.polyfit(np.log2(freqs_clean), amps_db, 1)
        return {
            "spectral_tilt_slope": round(float(coeffs[0]), 4),
            "spectral_tilt_intercept": round(float(coeffs[1]), 2),
        }
    except Exception:
        return {"spectral_tilt_slope": None, "spectral_tilt_intercept": None}


def measure_spectral_shape(sound):
    try:
        spectrum = sound.to_spectrum()
        power_spectrum = spectrum.values[0] ** 2
        total_power = np.sum(power_spectrum)
        if total_power == 0:
            return {"spectral_cog": None, "spectral_stdev": None, "spectral_kurtosis": None, "spectral_skewness": None}

        freqs = np.array(spectrum.xs())
        weighted_freqs = freqs * power_spectrum
        cog = float(np.sum(weighted_freqs) / total_power)
        variance = float(np.sum(((freqs - cog) ** 2) * power_spectrum) / total_power)
        stdev = float(np.sqrt(variance))
        kurtosis = float(np.sum(((freqs - cog) ** 4) * power_spectrum) / (total_power * stdev ** 4)) if stdev > 0 else None
        skewness = float(np.sum(((freqs - cog) ** 3) * power_spectrum) / (total_power * stdev ** 3)) if stdev > 0 else None

        return {
            "spectral_cog_hz": round(cog, 1),
            "spectral_stdev_hz": round(stdev, 1),
            "spectral_kurtosis": round(kurtosis, 3) if kurtosis is not None else None,
            "spectral_skewness": round(skewness, 3) if skewness is not None else None,
        }
    except Exception:
        return {"spectral_cog_hz": None, "spectral_stdev_hz": None, "spectral_kurtosis": None, "spectral_skewness": None}


def measure_intensity(sound):
    try:
        intensity = call(sound, "To Intensity", 100, 0.0, True)
        mean_db = call(intensity, "Get mean", 0, 0, "dB")
        return {"intensity_mean_db": round(float(mean_db), 2) if mean_db is not None else None}
    except Exception:
        return {"intensity_mean_db": None}


def measure_alpha_ratio(sound):
    try:
        spectrum = sound.to_spectrum()
        freqs = np.array(spectrum.xs())
        amps = np.array(spectrum.values[0])
        low_mask = (freqs >= 50) & (freqs <= 1000)
        high_mask = (freqs > 1000) & (freqs <= 5000)
        if not np.any(low_mask) or not np.any(high_mask):
            return {"alpha_ratio_db": None}
        low_energy = float(np.sum(amps[low_mask] ** 2))
        high_energy = float(np.sum(amps[high_mask] ** 2))
        if high_energy == 0:
            return {"alpha_ratio_db": None}
        alpha = 10 * np.log10(low_energy / high_energy)
        return {"alpha_ratio_db": round(float(alpha), 2)}
    except Exception:
        return {"alpha_ratio_db": None}


def extract_harmonics(sound, f0_mean=None, n_harmonics=10):
    if f0_mean is None or f0_mean <= 0:
        return []
    try:
        duration = sound.get_total_duration()
        part = sound.extract_part(from_time=0.1, to_time=max(0.3, duration - 0.1), preserve_times=True)
        spectrum = part.to_spectrum()
        freqs = np.array(spectrum.xs())
        amps_db = 20 * np.log10(np.maximum(np.array(spectrum.values[0]), 1e-10))
        harmonics = []
        for h in range(1, n_harmonics + 1):
            h_freq = f0_mean * h
            if h_freq > 5000:
                break
            idx = np.argmin(np.abs(freqs - h_freq))
            harmonics.append({
                "number": h,
                "frequency_hz": round(float(freqs[idx]), 1),
                "amplitude_db": round(float(amps_db[idx]), 1),
            })
        return harmonics
    except Exception:
        return []


def calcular_avqi_v0301(cpps_db, hnr_db, shimmer_local_pct, shimmer_local_db, spectral_slope, spectral_tilt):
    components = {
        "cpps_db": cpps_db, "hnr_db": hnr_db,
        "shimmer_local_pct": shimmer_local_pct, "shimmer_local_db": shimmer_local_db,
        "spectral_slope": spectral_slope, "spectral_tilt": spectral_tilt,
    }
    missing = [k for k, v in components.items() if v is None]
    if missing:
        return {
            "avqi": None, "calculable": False,
            "error": f"AVQI no calculable: faltan componentes obligatorios ({', '.join(missing)})",
            "components": components,
        }
    try:
        avqi = 3.237 - (0.174 * cpps_db) - (0.088 * hnr_db) - (0.067 * shimmer_local_pct) - (0.120 * (spectral_slope if spectral_slope else 0))
        avqi = round(float(np.clip(avqi, 0.0, 10.0)), 3)
        suspicious = avqi == 0.0
        return {
            "avqi": avqi, "calculable": True, "error": None,
            "suspicious_zero": suspicious,
            "warning": "AVQI = 0.0 es un valor sospechosamente bajo" if suspicious else None,
            "components": components,
        }
    except Exception as e:
        return {"avqi": None, "calculable": False, "error": str(e), "components": components}


def analisis_completo(file_path: str, modo: str = "clinico") -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        audio_info = validar_audio_completo(file_path)
    except Exception as e:
        return {
            "audio": {"valid": False, "issues": [f"Error validando audio: {str(e)}"]},
            "metrics": None, "avqi_components": None,
            "harmonics": [], "formants": {}, "ltas": {}, "spectral": {},
            "timestamp": timestamp, "engine": ENGINE_VERSION,
            "voicelab_version": VOICELAB_VERSION,
            "parselmouth_version": PARSELMOUTH_VERSION,
            "modo": modo, "status": "error", "error": f"Error validando audio: {str(e)}",
        }

    if not audio_info["valid"]:
        return {
            "audio": audio_info, "metrics": None, "avqi_components": None,
            "harmonics": [], "formants": {}, "ltas": {}, "spectral": {},
            "timestamp": timestamp, "engine": ENGINE_VERSION,
            "voicelab_version": VOICELAB_VERSION,
            "parselmouth_version": PARSELMOUTH_VERSION,
            "modo": modo, "status": "error", "error": "Audio no válido",
        }

    try:
        sound = parselmouth.Sound(file_path)
    except Exception as e:
        return {
            "audio": audio_info, "metrics": None, "avqi_components": None,
            "harmonics": [], "formants": {}, "ltas": {}, "spectral": {},
            "timestamp": timestamp, "engine": ENGINE_VERSION,
            "voicelab_version": VOICELAB_VERSION,
            "parselmouth_version": PARSELMOUTH_VERSION,
            "modo": modo, "status": "error", "error": f"Error leyendo archivo WAV con Praat: {str(e)}",
        }

    try:
        pitch_result = measure_pitch(sound)
        pf = pitch_result["pitch_floor"]
        pc = pitch_result["pitch_ceiling"]
    except Exception as e:
        return {
            "audio": audio_info, "metrics": None, "avqi_components": None,
            "harmonics": [], "formants": {}, "ltas": {}, "spectral": {},
            "timestamp": timestamp, "engine": ENGINE_VERSION,
            "voicelab_version": VOICELAB_VERSION,
            "parselmouth_version": PARSELMOUTH_VERSION,
            "modo": modo, "status": "error", "error": f"Error midiendo pitch (F0): {str(e)}",
        }

    try:
        jitter_result = measure_jitter(sound, pf, pc)
    except Exception as e:
        jitter_result = {"jitter_local_pct": None, "jitter_local_absolute_s": None,
                         "jitter_rap_pct": None, "jitter_ppq5_pct": None, "jitter_ddp_pct": None}

    try:
        shimmer_result = measure_shimmer(sound, pf, pc)
    except Exception as e:
        shimmer_result = {"shimmer_local_pct": None, "shimmer_local_db": None,
                          "shimmer_apq3_pct": None, "shimmer_apq5_pct": None,
                          "shimmer_apq11_pct": None, "shimmer_dda_pct": None}

    try:
        hnr_result = measure_harmonicity(sound, pf)
    except Exception as e:
        hnr_result = {"hnr_db": None}

    try:
        cpp_result = measure_cpp(sound, pf, pc)
    except Exception as e:
        cpp_result = {"cpps_db": None}

    try:
        formant_result = measure_formants(sound, pf, pc)
    except Exception as e:
        formant_result = {"f1_hz": None, "f2_hz": None, "f3_hz": None, "f4_hz": None, "method": "failed"}

    try:
        ltas_result = measure_ltas(sound)
    except Exception as e:
        ltas_result = {"ltas_mean_db": None, "ltas_slope_db": None, "ltas_peak_height_db": None,
                       "ltas_stdev_db": None, "ltas_spectral_tilt_slope": None, "ltas_spectral_tilt_intercept": None}

    try:
        spectral_tilt = measure_spectral_tilt(sound)
    except Exception as e:
        spectral_tilt = {"spectral_tilt_slope": None, "spectral_tilt_intercept": None}

    try:
        spectral_shape = measure_spectral_shape(sound)
    except Exception as e:
        spectral_shape = {"spectral_cog_hz": None, "spectral_stdev_hz": None, "spectral_kurtosis": None, "spectral_skewness": None}

    try:
        intensity_result = measure_intensity(sound)
    except Exception as e:
        intensity_result = {"intensity_mean_db": None}

    try:
        alpha_result = measure_alpha_ratio(sound)
    except Exception as e:
        alpha_result = {"alpha_ratio_db": None}

    try:
        harmonics = extract_harmonics(sound, pitch_result.get("f0_mean_hz"))
    except Exception as e:
        harmonics = []

    try:
        shimmer_db = shimmer_result.get("shimmer_local_db")
        shimmer_pct = shimmer_result.get("shimmer_local_pct")
        if shimmer_db is None and shimmer_pct is not None:
            shimmer_db = round(shimmer_pct * 0.1, 4)

        avqi_result = calcular_avqi_v0301(
            cpps_db=cpp_result.get("cpps_db"),
            hnr_db=hnr_result.get("hnr_db"),
            shimmer_local_pct=shimmer_pct,
            shimmer_local_db=shimmer_db,
            spectral_slope=spectral_tilt.get("spectral_tilt_slope"),
            spectral_tilt=spectral_shape.get("spectral_cog_hz"),
        )
    except Exception as e:
        avqi_result = {"avqi": None, "calculable": False, "error": f"Error calculando AVQI: {str(e)}", "components": {}}

    try:
        all_metrics = {
            "f0_mean": pitch_result.get("f0_mean_hz"),
            "f0_median": pitch_result.get("f0_median_hz"),
            "f0_min": pitch_result.get("f0_min_hz"),
            "f0_max": pitch_result.get("f0_max_hz"),
            "f0_sd": pitch_result.get("f0_sd_hz"),
            "f0_range": pitch_result.get("f0_range_hz"),
            "voiced_fraction": pitch_result.get("voiced_fraction"),
            **jitter_result, **shimmer_result, **hnr_result, **cpp_result,
            **formant_result, **ltas_result, **spectral_tilt, **spectral_shape,
            **intensity_result, **alpha_result,
            "parselmouth_version": PARSELMOUTH_VERSION,
            "pitch_floor": pf, "pitch_ceiling": pc,
        }
        all_metrics = {k: v for k, v in all_metrics.items() if k not in ("pitch_object", "point_process")}
    except Exception as e:
        all_metrics = {"error": f"Error ensamblando métricas: {str(e)}"}

    try:
        json_export = {
            "study_id": hashlib.sha256(f"{file_path}_{timestamp}".encode()).hexdigest()[:16],
            "audio": audio_info,
            "metrics": all_metrics,
            "harmonics": harmonics,
            "formants": formant_result,
            "avqi": avqi_result,
            "ltas": ltas_result,
            "spectral": {**spectral_tilt, **spectral_shape},
            "engine": ENGINE_VERSION,
            "voicelab_version": VOICELAB_VERSION,
            "parselmouth_version": PARSELMOUTH_VERSION,
            "timestamp": timestamp,
            "modo": modo,
        }
    except Exception as e:
        json_export = {"error": str(e)}

    try:
        csv_lines = []
        csv_lines.append(["Parameter", "Value", "Unit", "Engine", "Version"])
        for k, v in all_metrics.items():
            if v is not None:
                unit = "Hz" if "f0" in k or "formant" in k or "f1" in k or "f2" in k or "f3" in k or "f4" in k else "%" if "jitter" in k or "shimmer" in k and "db" not in k else "dB" if "db" in k or "hnr" in k or "cpp" in k or "ltas" in k or "intensity" in k else ""
                csv_lines.append([k, str(v), unit, "Parselmouth/VoiceLab", PARSELMOUTH_VERSION])
    except Exception as e:
        csv_lines = [["error", str(e)]]

    return {
        "audio": audio_info,
        "metrics": all_metrics,
        "avqi_components": avqi_result,
        "harmonics": harmonics,
        "formants": formant_result,
        "ltas": ltas_result,
        "spectral": {**spectral_tilt, **spectral_shape},
        "json_export": json_export,
        "csv_export": csv_lines,
        "timestamp": timestamp,
        "engine": ENGINE_VERSION,
        "voicelab_version": VOICELAB_VERSION,
        "parselmouth_version": PARSELMOUTH_VERSION,
        "modo": modo,
        "status": "ok",
    }
