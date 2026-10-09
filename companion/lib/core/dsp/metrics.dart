import 'dart:math' as math;
import 'yin.dart';

/// Agregación por tarea → exactamente los campos del contrato
/// (docs/companion-api.md §4). Solo tramos del PACIENTE (el llamador filtra).
///
/// - f0_sd_semitones = SD de st_i = 12·log2(f_i / f0_median), tramas sonoras.
/// - jitter/shimmer/HNR/MPT: solo si [sostenida] (vocal /a/).
/// - dB = dBFS relativo + [calibrationDbOffset] (offset de sonómetro).
/// - histograma: bins de 1 semitono relativos a la mediana (ref_hz).
/// - contorno: diezmado a ~20 Hz (1 de cada 5 cuadros de 10 ms), 0 = sordo.
class TaskMetrics {
  final double? f0MeanHz;
  final double? f0MedianHz;
  final double? f0SdHz;
  final double? f0SdSemitones;
  final double? f0P5Hz;
  final double? f0P95Hz;
  final double? f0MinHz;
  final double? f0MaxHz;
  final double voicedFraction;
  final double? intensityMeanDb;
  final double? intensitySdDb;
  final double? mptSec;
  final double? jitterPct;
  final double? shimmerPct;
  final double? hnrDb;
  final Map<String, int> histogramBins;
  final double histogramRefHz;
  final List<double> contour;

  const TaskMetrics({
    this.f0MeanHz,
    this.f0MedianHz,
    this.f0SdHz,
    this.f0SdSemitones,
    this.f0P5Hz,
    this.f0P95Hz,
    this.f0MinHz,
    this.f0MaxHz,
    required this.voicedFraction,
    this.intensityMeanDb,
    this.intensitySdDb,
    this.mptSec,
    this.jitterPct,
    this.shimmerPct,
    this.hnrDb,
    this.histogramBins = const {},
    this.histogramRefHz = 0,
    this.contour = const [],
  });

  Map<String, dynamic> toJson(String dspVersion) => {
        'f0_mean_hz': f0MeanHz,
        'f0_median_hz': f0MedianHz,
        'f0_sd_hz': f0SdHz,
        'f0_sd_semitones': f0SdSemitones,
        'f0_p5_hz': f0P5Hz,
        'f0_p95_hz': f0P95Hz,
        'f0_min_hz': f0MinHz,
        'f0_max_hz': f0MaxHz,
        'voiced_fraction': voicedFraction,
        'intensity_mean_db': intensityMeanDb,
        'intensity_sd_db': intensitySdDb,
        'mpt_sec': mptSec,
        'jitter_pct': jitterPct,
        'shimmer_pct': shimmerPct,
        'hnr_db': hnrDb,
        'f0_histogram': {
          'ref_hz': histogramRefHz,
          'bins': {for (final e in histogramBins.entries) '${e.key}': e.value},
        },
        'f0_contour': contour,
        'dsp_version': dspVersion,
      };
}

double _median(List<double> v) {
  final s = List<double>.from(v)..sort();
  final n = s.length;
  return n.isOdd ? s[n ~/ 2] : (s[n ~/ 2 - 1] + s[n ~/ 2]) / 2;
}

double _percentile(List<double> sorted, double p) {
  if (sorted.isEmpty) return 0.0;
  final k = (((p / 100) * (sorted.length - 1)).round().clamp(0, sorted.length - 1)).toInt();
  return sorted[k];
}

/// Calcula métricas desde cuadros YIN ya filtrados por mediana.
/// [frames]: un YinFrame cada 10 ms. [sostenida]: vocal /a/ (jitter/shimmer/HNR/MPT).
/// [mptSec]: duración máxima de la emisión (solo sostenida).
TaskMetrics computeTaskMetrics({
  required List<YinFrame> frames,
  bool sostenida = false,
  double? mptSec,
  double calibrationDbOffset = 0.0,
}) {
  final voiced = frames.where((f) => f.voiced).toList();
  final vf = frames.isEmpty ? 0.0 : voiced.length / frames.length;
  // Contorno diezmado ~20 Hz.
  final contour = <double>[];
  for (var i = 0; i < frames.length; i += 5) {
    contour.add(frames[i].voiced ? frames[i].f0 : 0.0);
  }
  if (voiced.isEmpty) {
    return TaskMetrics(voicedFraction: vf, contour: contour);
  }
  final f0s = voiced.map((f) => f.f0).toList();
  final mean = f0s.reduce((a, b) => a + b) / f0s.length;
  final median = _median(f0s);
  final variance = f0s.map((f) => (f - mean) * (f - mean)).reduce((a, b) => a + b) / f0s.length;
  final sorted = List<double>.from(f0s)..sort();
  // SD en semitonos vs. mediana.
  final sts = f0s.map((f) => 12 * (math.log(f / median) / math.ln2)).toList();
  final stMean = sts.reduce((a, b) => a + b) / sts.length;
  final stSd = math.sqrt(
      sts.map((s) => (s - stMean) * (s - stMean)).reduce((a, b) => a + b) / sts.length);
  // Intensidad dBFS + calibración.
  final dbs = voiced.map((f) => 20 * (math.log(f.rms) / math.ln10) + calibrationDbOffset).toList();
  final dbMean = dbs.reduce((a, b) => a + b) / dbs.length;
  final dbSd = math.sqrt(
      dbs.map((d) => (d - dbMean) * (d - dbMean)).reduce((a, b) => a + b) / dbs.length);
  // Histograma 1 semitono vs. mediana.
  final bins = <String, int>{};
  for (final f in f0s) {
    final st = (12 * (math.log(f / median) / math.ln2)).round();
    bins['$st'] = (bins['$st'] ?? 0) + 1;
  }
  double? jitter, shimmer, hnr;
  if (sostenida && voiced.length >= 3) {
    final periods = voiced.map((f) => 1.0 / f.f0).toList();
    final pMean = periods.reduce((a, b) => a + b) / periods.length;
    var jd = 0.0;
    for (var i = 1; i < periods.length; i++) {
      jd += (periods[i] - periods[i - 1]).abs();
    }
    jitter = jd / (periods.length - 1) / pMean * 100;
    final amps = voiced.map((f) => f.rms).toList();
    final aMean = amps.reduce((a, b) => a + b) / amps.length;
    var sd = 0.0;
    for (var i = 1; i < amps.length; i++) {
      sd += (amps[i] - amps[i - 1]).abs();
    }
    shimmer = sd / (amps.length - 1) / aMean * 100;
    // HNR estilo Praat: 10·log10(r/(1−r)) con r = pico autocorrelación medio.
    final rs = voiced.map((f) => (f.strength.clamp(0.0, 0.999)).toDouble()).toList();
    final rMean = rs.reduce((a, b) => a + b) / rs.length;
    hnr = 10 * (math.log(rMean / (1 - rMean)) / math.ln10);
  }
  return TaskMetrics(
    f0MeanHz: mean,
    f0MedianHz: median,
    f0SdHz: math.sqrt(variance),
    f0SdSemitones: stSd,
    f0P5Hz: _percentile(sorted, 5),
    f0P95Hz: _percentile(sorted, 95),
    f0MinHz: sorted.first,
    f0MaxHz: sorted.last,
    voicedFraction: vf,
    intensityMeanDb: dbMean,
    intensitySdDb: dbSd,
    mptSec: sostenida ? mptSec : null,
    jitterPct: jitter,
    shimmerPct: shimmer,
    hnrDb: hnr,
    histogramBins: bins,
    histogramRefHz: median,
    contour: contour,
  );
}
