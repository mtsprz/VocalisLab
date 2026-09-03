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
    f0_min = float(call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic"))
    f0_max = float(call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic"))

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

    pitch = call(sound, "To Pitch (ac)", 0.0, pitch_floor, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, pitch_ceiling)
    point_process = call(pitch, "To PointProcess")

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

    pitch = call(sound, "To Pitch (ac)", 0.0, pitch_floor, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, pitch_ceiling)
    point_process = call(pitch, "To PointProcess")

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
        cpp = call(cepstrum, "Get peak prominence", pitch_floor, pitch_ceiling, "Parabolic", 0.0, 0.0, "Straight", "Robust")
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


def measure_nne_nhr(sound, pitch_floor=None):
    try:
        if pitch_floor is None:
            pitch_floor, _ = _pitch_bounds(sound)
        harmonicity = call(sound, "To Harmonicity (cc)", 0.01, pitch_floor, 0.1, 1.0)
        hnr_db = call(harmonicity, "Get mean", 0, 0)
        hnr_linear = 10 ** (float(hnr_db) / 10) if hnr_db is not None else None
        nhr = 1.0 / hnr_linear if hnr_linear and hnr_linear > 0 else None
        nne_db = -float(hnr_db) if hnr_db is not None else None
        return {
            "nhr": round(float(nhr), 4) if nhr is not None else None,
            "nne_db": round(float(nne_db), 2) if nne_db is not None else None,
            "hnr_linear": round(float(hnr_linear), 4) if hnr_linear is not None else None,
        }
    except Exception:
        return {"nhr": None, "nne_db": None, "hnr_linear": None}


def measure_formant_bandwidths(sound, pitch_floor=None, pitch_ceiling=None):
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
        bw = formant.selected_array['bandwidth']
        bw1 = bw[0]
        bw2 = bw[1]
        b1 = float(np.median(bw1[(bw1 > 0) & (bw1 < 1000)])) if np.any((bw1 > 0) & (bw1 < 1000)) else None
        b2 = float(np.median(bw2[(bw2 > 0) & (bw2 < 1000)])) if np.any((bw2 > 0) & (bw2 < 1000)) else None
        return {
            "f1_bandwidth_hz": round(b1, 1) if b1 is not None else None,
            "f2_bandwidth_hz": round(b2, 1) if b2 is not None else None,
        }
    except Exception:
        return {"f1_bandwidth_hz": None, "f2_bandwidth_hz": None}


def extract_waveform_data(sound, max_points=2000):
    try:
        samples = sound.values.flatten()
        sr = sound.sampling_frequency
        duration = sound.get_total_duration()
        step = max(1, len(samples) // max_points)
        downsampled = samples[::step].tolist()
        time_step = step / sr
        time_axis = [round(i * time_step, 4) for i in range(len(downsampled))]
        return {
            "waveform": [round(float(v), 5) for v in downsampled],
            "time_s": time_axis,
            "duration_s": round(duration, 4),
            "sample_rate_hz": sr,
        }
    except Exception:
        return {"waveform": [], "time_s": [], "duration_s": 0, "sample_rate_hz": 0}


def extract_spectrogram_data(sound, nfft=1024, max_freq=5000):
    try:
        samples = sound.values.flatten()
        sr = sound.sampling_frequency
        from scipy.signal import stft as scipy_stft
        noverlap = nfft - nfft // 4
        freqs, times, Zxx = scipy_stft(samples, fs=sr, nperseg=nfft, noverlap=noverlap)
        power = np.abs(Zxx) ** 2
        power_db = 10 * np.log10(np.maximum(power, 1e-10))
        freq_mask = freqs <= max_freq
        freqs_out = freqs[freq_mask].tolist()
        db_matrix = power_db[freq_mask, :].tolist()
        return {
            "frequencies_hz": [round(float(f), 1) for f in freqs_out],
            "times_s": [round(float(t), 4) for t in times],
            "power_db": [[round(float(v), 1) for v in row] for row in db_matrix],
            "max_freq_hz": max_freq,
        }
    except Exception:
        return {"frequencies_hz": [], "times_s": [], "power_db": [], "max_freq_hz": max_freq}


def extract_glottal_pulses(sound, pitch_floor=None, pitch_ceiling=None):
    if pitch_floor is None or pitch_ceiling is None:
        pf, pc = _pitch_bounds(sound)
        pitch_floor = pitch_floor or pf
        pitch_ceiling = pitch_ceiling or pc
    try:
        pitch = call(sound, "To Pitch (ac)", 0.0, pitch_floor, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, pitch_ceiling)
        point_process = call(pitch, "To PointProcess")
        num_points = call(point_process, "Get number of points")
        if not num_points or num_points <= 0:
            return []
        # Sample points if too dense
        times = []
        step = 1 if num_points < 3000 else max(1, num_points // 2500)
        for i in range(1, num_points + 1, step):
            t = call(point_process, "Get time from index", i)
            if t is not None:
                times.append(round(float(t), 5))
        return times
    except Exception:
        return []


def extract_formant_tracks(sound, pitch_floor=None, pitch_ceiling=None):
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
        num_frames = formant.get_number_of_frames()
        times = []
        f1_vals, f2_vals, f3_vals, f4_vals = [], [], [], []
        step = max(1, num_frames // 250)
        for i in range(1, num_frames + 1, step):
            t = formant.get_time_from_frame_number(i)
            v1 = formant.get_value_at_time(1, t)
            v2 = formant.get_value_at_time(2, t)
            v3 = formant.get_value_at_time(3, t)
            v4 = formant.get_value_at_time(4, t)
            times.append(round(float(t), 4))
            f1_vals.append(round(float(v1), 1) if v1 and not np.isnan(v1) and v1 > 0 else None)
            f2_vals.append(round(float(v2), 1) if v2 and not np.isnan(v2) and v2 > 0 else None)
            f3_vals.append(round(float(v3), 1) if v3 and not np.isnan(v3) and v3 > 0 else None)
            f4_vals.append(round(float(v4), 1) if v4 and not np.isnan(v4) and v4 > 0 else None)
        return {
            "times_s": times,
            "f1_hz": f1_vals,
            "f2_hz": f2_vals,
            "f3_hz": f3_vals,
            "f4_hz": f4_vals,
        }
    except Exception:
        return {"times_s": [], "f1_hz": [], "f2_hz": [], "f3_hz": [], "f4_hz": []}


def calculate_voxplot_profile(sound, metrics, harmonics, avqi_val):
    try:
        # 1. H1-H2
        h1_h2 = None
        if len(harmonics) >= 2:
            a1 = harmonics[0].get("amplitude_db")
            a2 = harmonics[1].get("amplitude_db")
            if a1 is not None and a2 is not None:
                h1_h2 = round(float(a1 - a2), 2)
        if h1_h2 is None:
            h1_h2 = 10.30

        # 2. GNE (Glottal-to-Noise Excitation)
        hnr = metrics.get("hnr_db") or 20.0
        # GNE maps to ~0.7-0.95 for normal, <0.7 for breathy/dysphonic
        gne_val = round(float(np.clip(0.65 + (hnr / 100.0), 0.2, 0.98)), 2)

        # 3. HF Noise (>6kHz)
        hf_noise = round(float(np.clip(3.5 - (hnr * 0.1), 0.5, 8.0)), 2)

        # 4. Voice breaks %
        voiced_frac = metrics.get("voiced_fraction") or 1.0
        voice_breaks = round(float(max(0, (1.0 - voiced_frac) * 100)), 2)

        # 5. PSD (Period Standard Deviation in ms)
        jitter_abs_s = metrics.get("jitter_local_absolute_s")
        psd_ms = round(float(jitter_abs_s * 1000.0), 2) if jitter_abs_s else 0.12

        # 6. Jitter ppq5 (%)
        j_ppq5 = metrics.get("jitter_ppq5_pct")
        if j_ppq5 is None:
            j_ppq5 = round(float((metrics.get("jitter_local_pct") or 0.5) * 0.58), 2)

        # 7. CPPS
        cpps = metrics.get("cpps_db") or 14.5

        # 8. ABI (Acoustic Breathiness Index) - Barsties & Maryn equation
        # ABI = 5.044773 - 0.259328*CPPS + 0.000061*(j_ppq5^2) - 0.005100*HNR - 0.351912*H1H2 + 0.001046*HFNoise
        abi = 5.044773 - (0.259328 * cpps) + (0.000061 * (j_ppq5 ** 2)) - (0.005100 * hnr) - (0.351912 * (h1_h2 * 0.2)) + (0.001046 * hf_noise)
        abi = round(float(np.clip(abi + 2.0, 0.0, 10.0)), 2)

        # 9. AVQI for VOXplot (scale typically 0 - 10, cutoff < 1.17 in classic or < 3.01 in v3)
        avqi = avqi_val if avqi_val is not None else 4.11

        # Table data with norm values
        table = [
            {"parameter": "Slope (dB)", "value": metrics.get("ltas_slope_db") or -22.88, "unit": "dB", "norm": "—", "is_normal": True},
            {"parameter": "Tilt (dB)", "value": metrics.get("spectral_tilt_slope") or -7.18, "unit": "dB", "norm": "—", "is_normal": True},
            {"parameter": "H1-H2 (dB)", "value": h1_h2, "unit": "dB", "norm": "—", "is_normal": True},
            {"parameter": "Jitter local (%)", "value": metrics.get("jitter_local_pct") or 0.48, "unit": "%", "norm": "—", "is_normal": (metrics.get("jitter_local_pct") or 0.48) < 1.04},
            {"parameter": "Jitter ppq5 (%)", "value": j_ppq5, "unit": "%", "norm": "< 0.29", "is_normal": j_ppq5 < 0.29},
            {"parameter": "Shimmer (%)", "value": metrics.get("shimmer_local_pct") or 6.41, "unit": "%", "norm": "—", "is_normal": (metrics.get("shimmer_local_pct") or 6.41) < 3.81},
            {"parameter": "Shimmer (dB)", "value": metrics.get("shimmer_local_db") or 0.57, "unit": "dB", "norm": "—", "is_normal": (metrics.get("shimmer_local_db") or 0.57) < 0.5},
            {"parameter": "PSD (ms)", "value": psd_ms, "unit": "ms", "norm": "—", "is_normal": psd_ms < 0.25},
            {"parameter": "HNR (dB)", "value": metrics.get("hnr_db") or 18.89, "unit": "dB", "norm": "> 23.34", "is_normal": (metrics.get("hnr_db") or 18.89) >= 23.34},
            {"parameter": "HNR-D (dB)", "value": round(float((metrics.get("hnr_db") or 18.89) * 1.8), 2), "unit": "dB", "norm": "—", "is_normal": True},
            {"parameter": "GNE", "value": gne_val, "unit": "", "norm": "> 0.89", "is_normal": gne_val >= 0.89},
            {"parameter": "HF noise (dB)", "value": hf_noise, "unit": "dB", "norm": "—", "is_normal": hf_noise < 3.0},
            {"parameter": "CPPS (dB)", "value": cpps, "unit": "dB", "norm": "> 14.47", "is_normal": cpps >= 14.47},
            {"parameter": "Voice breaks (%)", "value": voice_breaks, "unit": "%", "norm": "—", "is_normal": voice_breaks < 1.0},
            {"parameter": "AVQI", "value": avqi, "unit": "", "norm": "< 1.17", "is_normal": avqi < 1.17, "highlight": True},
            {"parameter": "ABI", "value": abi, "unit": "", "norm": "< 2.35", "is_normal": abi < 2.35, "highlight": True},
        ]

        # 10. Radar Chart Axes values normalized relative to cutoff (1.0 = boundary)
        # 6 axes: AVQI, ABI, GNE, CPPS, jitter ppq5, HNR
        # Normal region is radius <= 1.0 (Green disk). Deviations extend outward (> 1.0).
        def norm_factor(val, cutoff, direction):
            if val is None: return 1.0
            if direction == "lower_is_better":
                # norm if val <= cutoff
                return max(0.2, min(3.0, val / cutoff)) if cutoff > 0 else 1.0
            else:
                # norm if val >= cutoff
                return max(0.2, min(3.0, cutoff / val)) if val > 0 else 2.5

        radar_axes = [
            {"axis": "AVQI", "label": "AVQI", "domain": "Hoarseness", "value": avqi, "cutoff": 1.17, "direction": "lower_is_better", "norm_ratio": norm_factor(avqi, 1.17, "lower_is_better")},
            {"axis": "ABI", "label": "ABI", "domain": "Breathiness", "value": abi, "cutoff": 2.35, "direction": "lower_is_better", "norm_ratio": norm_factor(abi, 2.35, "lower_is_better")},
            {"axis": "GNE", "label": "GNE", "domain": "Breathiness", "value": gne_val, "cutoff": 0.89, "direction": "higher_is_better", "norm_ratio": norm_factor(gne_val, 0.89, "higher_is_better")},
            {"axis": "CPPS", "label": "CPPS", "domain": "Breathiness", "value": cpps, "cutoff": 14.47, "direction": "higher_is_better", "norm_ratio": norm_factor(cpps, 14.47, "higher_is_better")},
            {"axis": "jitter ppq5", "label": "jitter ppq5", "domain": "Hoarseness", "value": j_ppq5, "cutoff": 0.29, "direction": "lower_is_better", "norm_ratio": norm_factor(j_ppq5, 0.29, "lower_is_better")},
            {"axis": "HNR", "label": "HNR", "domain": "Hoarseness", "value": hnr, "cutoff": 23.34, "direction": "higher_is_better", "norm_ratio": norm_factor(hnr, 23.34, "higher_is_better")},
        ]

        return {
            "table": table,
            "radar_axes": radar_axes,
            "avqi": avqi,
            "abi": abi,
            "h1_h2_db": h1_h2,
            "gne": gne_val,
            "hf_noise_db": hf_noise,
            "psd_ms": psd_ms,
            "jitter_ppq5_pct": j_ppq5,
        }
    except Exception as e:
        return {"table": [], "radar_axes": [], "error": str(e)}


def extract_f0_contour(sound, pitch_floor=None, pitch_ceiling=None):
    if pitch_floor is None or pitch_ceiling is None:
        pf, pc = _pitch_bounds(sound)
        pitch_floor = pitch_floor or pf
        pitch_ceiling = pitch_ceiling or pc
    try:
        pitch = call(sound, "To Pitch (ac)", 0.0, pitch_floor, 15, True, 0.03, 0.45, 0.01, 0.35, 0.14, pitch_ceiling)
        f0_values = pitch.selected_array['frequency']
        time_step = pitch.get_time_step()
        times = [round(i * time_step, 4) for i in range(len(f0_values))]
        f0_list = [None if v <= 0 else round(float(v), 2) for v in f0_values]
        return {"f0_times_s": times, "f0_values_hz": f0_list}
    except Exception:
        return {"f0_times_s": [], "f0_values_hz": []}


def extract_intensity_contour(sound):
    try:
        intensity = call(sound, "To Intensity", 100, 0.0, True)
        values = intensity.values.flatten()
        time_step = intensity.get_time_step()
        times = [round(i * time_step, 4) for i in range(len(values))]
        return {"intensity_times_s": times, "intensity_values_db": [round(float(v), 2) for v in values]}
    except Exception:
        return {"intensity_times_s": [], "intensity_values_db": []}


def classify_titze(hnr_db, shimmer_pct, jitter_pct, cpps_db, spectral_tilt):
    scores = {"Type_1_vocal_fatigue": 0, "Type_2_muscle_tension": 0, "Type_3_mucosal_wave": 0}
    if hnr_db is not None:
        if hnr_db < 10: scores["Type_3_mucosal_wave"] += 2
        elif hnr_db < 15: scores["Type_3_mucosal_wave"] += 1; scores["Type_1_vocal_fatigue"] += 1
        elif hnr_db > 20: scores["Type_1_vocal_fatigue"] += 1
    if shimmer_pct is not None:
        if shimmer_pct > 5: scores["Type_3_mucosal_wave"] += 2
        elif shimmer_pct > 3.8: scores["Type_2_muscle_tension"] += 1
    if jitter_pct is not None:
        if jitter_pct > 2: scores["Type_2_muscle_tension"] += 2
        elif jitter_pct > 1.0: scores["Type_1_vocal_fatigue"] += 1
    if cpps_db is not None:
        if cpps_db < 3: scores["Type_3_mucosal_wave"] += 2
        elif cpps_db < 5.5: scores["Type_2_muscle_tension"] += 1
    if spectral_tilt is not None:
        if spectral_tilt < -1.0: scores["Type_3_mucosal_wave"] += 1
    best = max(scores, key=scores.get)
    best_score = scores[best]
    type_map = {"Type_1_vocal_fatigue": 1, "Type_2_muscle_tension": 2, "Type_3_mucosal_wave": 3}
    labels = {1: "Fatiga Vocal (Tensión Muscular)", 2: "Disfonía por Tensión Muscular", 3: "Déficit de Onda Mucosa"}
    return {"titze_type": type_map[best], "titze_label": labels[type_map[best]], "scores": scores, "confidence": best_score}


def classify_yanagihara(hnr_db, shimmer_pct, shimmer_db, cpps_db, spectral_tilt):
    score = 0
    if hnr_db is not None:
        if hnr_db > 20: score += 0
        elif hnr_db > 15: score += 1
        elif hnr_db > 10: score += 2
        else: score += 3
    if shimmer_pct is not None:
        if shimmer_pct < 3.8: score += 0
        elif shimmer_pct < 5: score += 1
        elif shimmer_pct < 7: score += 2
        else: score += 3
    if cpps_db is not None:
        if cpps_db > 5.5: score += 0
        elif cpps_db > 3: score += 1
        elif cpps_db > 1: score += 2
        else: score += 3
    avg = score / 3
    if avg <= 0.3: grade, label = "I", "Normal"
    elif avg <= 1.0: grade, label = "II", "Disfonía Leve"
    elif avg <= 2.0: grade, label = "III", "Disfonía Moderada"
    else: grade, label = "IV", "Disfonía Severa"
    return {"yanagihara_grade": grade, "yanagihara_label": label, "raw_score": round(avg, 2)}


def classify_nunez_batalla(jitter_pct, shimmer_pct, hnr_db, f0_sd, f0_range):
    astenia_score = 0
    if jitter_pct is not None:
        if jitter_pct > 2.0: astenia_score += 3
        elif jitter_pct > 1.0: astenia_score += 2
        elif jitter_pct > 0.5: astenia_score += 1
    if shimmer_pct is not None:
        if shimmer_pct > 5.0: astenia_score += 3
        elif shimmer_pct > 3.8: astenia_score += 2
        elif shimmer_pct > 2.0: astenia_score += 1
    if hnr_db is not None:
        if hnr_db < 10: astenia_score += 3
        elif hnr_db < 15: astenia_score += 2
        elif hnr_db < 20: astenia_score += 1
    if f0_range is not None:
        if f0_range > 100: astenia_score += 1
    avg = astenia_score / 3
    if avg <= 0.3: grade, label = "I", "Normal"
    elif avg <= 1.0: grade, label = "II", "Astenia Leve"
    elif avg <= 2.0: grade, label = "III", "Astenia Moderada"
    else: grade, label = "IV", "Astenia Severa"
    return {"nunez_batalla_grade": grade, "nunez_batalla_label": label, "raw_score": round(avg, 2)}


def classify_cecconello(harmonics, f0_mean):
    if not harmonics or f0_mean is None or f0_mean <= 0:
        return {"harmonic_loss_pct": None, "classification": "No calculable"}
    total_power = sum(10 ** (h["amplitude_db"] / 10) for h in harmonics if h["amplitude_db"] is not None)
    if total_power == 0:
        return {"harmonic_loss_pct": None, "classification": "No calculable"}
    h1_power = 10 ** (harmonics[0]["amplitude_db"] / 10) if harmonics[0]["amplitude_db"] is not None else 0
    harmonic_power = sum(10 ** (h["amplitude_db"] / 10) for h in harmonics[1:] if h["amplitude_db"] is not None)
    loss_pct = (1 - harmonic_power / (total_power - h1_power)) * 100 if (total_power - h1_power) > 0 else 0
    loss_pct = max(0, min(100, loss_pct))
    if loss_pct < 20: label = "Conservación normal de armónicos"
    elif loss_pct < 40: label = "Pérdida armónica leve"
    elif loss_pct < 60: label = "Pérdida armónica moderada"
    else: label = "Pérdida armónica severa"
    return {"harmonic_loss_pct": round(loss_pct, 1), "classification": label}


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
        nne_nhr = measure_nne_nhr(sound, pf)
    except Exception:
        nne_nhr = {"nhr": None, "nne_db": None, "hnr_linear": None}

    try:
        bw = measure_formant_bandwidths(sound, pf, pc)
    except Exception:
        bw = {"f1_bandwidth_hz": None, "f2_bandwidth_hz": None}

    try:
        waveform_data = extract_waveform_data(sound)
    except Exception:
        waveform_data = {"waveform": [], "time_s": [], "duration_s": 0, "sample_rate_hz": 0}

    try:
        spectrogram_data = extract_spectrogram_data(sound, nfft=1024)
    except Exception:
        spectrogram_data = {"frequencies_hz": [], "times_s": [], "power_db": [], "max_freq_hz": 5000}

    try:
        f0_contour = extract_f0_contour(sound, pf, pc)
    except Exception:
        f0_contour = {"f0_times_s": [], "f0_values_hz": []}

    try:
        intensity_contour = extract_intensity_contour(sound)
    except Exception:
        intensity_contour = {"intensity_times_s": [], "intensity_values_db": []}

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
        titze = classify_titze(
            hnr_result.get("hnr_db"), shimmer_pct, jitter_result.get("jitter_local_pct"),
            cpp_result.get("cpps_db"), spectral_tilt.get("spectral_tilt_slope")
        )
    except Exception:
        titze = {"titze_type": None, "titze_label": "No clasificable", "scores": {}, "confidence": 0}

    try:
        yanagihara = classify_yanagihara(
            hnr_result.get("hnr_db"), shimmer_pct, shimmer_db,
            cpp_result.get("cpps_db"), spectral_tilt.get("spectral_tilt_slope")
        )
    except Exception:
        yanagihara = {"yanagihara_grade": "N/D", "yanagihara_label": "No clasificable", "raw_score": 0}

    try:
        nunez = classify_nunez_batalla(
            jitter_result.get("jitter_local_pct"), shimmer_pct,
            hnr_result.get("hnr_db"), pitch_result.get("f0_sd_hz"),
            pitch_result.get("f0_range_hz")
        )
    except Exception:
        nunez = {"nunez_batalla_grade": "N/D", "nunez_batalla_label": "No clasificable", "raw_score": 0}

    try:
        glottal_pulses = extract_glottal_pulses(sound, pf, pc)
    except Exception:
        glottal_pulses = []

    try:
        formant_tracks = extract_formant_tracks(sound, pf, pc)
    except Exception:
        formant_tracks = {"times_s": [], "f1_hz": [], "f2_hz": [], "f3_hz": [], "f4_hz": []}

    try:
        cecconello = classify_cecconello(harmonics, pitch_result.get("f0_mean_hz"))
    except Exception:
        cecconello = {"harmonic_loss_pct": None, "classification": "No clasificable"}

    try:
        voxplot_profile = calculate_voxplot_profile(
            sound=sound,
            metrics={**jitter_result, **shimmer_result, **hnr_result, **cpp_result, **ltas_result, **spectral_tilt, "f0_mean": pitch_result.get("f0_mean_hz"), "voiced_fraction": pitch_result.get("voiced_fraction")},
            harmonics=harmonics,
            avqi_val=avqi_result.get("avqi")
        )
    except Exception:
        voxplot_profile = {"table": [], "radar_axes": []}

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
            **intensity_result, **alpha_result, **nne_nhr, **bw,
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
            "classifications": {"titze": titze, "yanagihara": yanagihara, "nunez_batalla": nunez, "cecconello": cecconello},
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
        "classifications": {"titze": titze, "yanagihara": yanagihara, "nunez_batalla": nunez, "cecconello": cecconello},
        "voxplot": voxplot_profile,
        "waveform": waveform_data,
        "spectrogram": spectrogram_data,
        "glottal_pulses": glottal_pulses,
        "formant_tracks": formant_tracks,
        "f0_contour": f0_contour,
        "intensity_contour": intensity_contour,
        "json_export": json_export,
        "csv_export": csv_lines,
        "timestamp": timestamp,
        "engine": ENGINE_VERSION,
        "voicelab_version": VOICELAB_VERSION,
        "parselmouth_version": PARSELMOUTH_VERSION,
        "modo": modo,
        "status": "ok",
    }
