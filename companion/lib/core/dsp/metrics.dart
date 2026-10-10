import 'dart:math' as math;
import 'yin.dart';

/// Agregación por tarea → campos de F0 del contrato
/// (docs/companion-api.md §4). Solo tramos del PACIENTE (el llamador filtra).
///
/// Alcance actual: solo altura tonal (F0 en Hz). jitter/shimmer/HNR/MPT e
/// intensidad en dB NO se calculan: viajan como null (el contrato los admite).
///
/// - f0_sd_semitones = SD de st_i = 12·log2(f_i / f0_median), tramas sonoras.
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
        // Fuera de alcance: el contrato los admite nulos.
        'intensity_mean_db': null,
        'intensity_sd_db': null,
        'mpt_sec': null,
        'jitter_pct': null,
        'shimmer_pct': null,
        'hnr_db': null,
        'f0_histogram': {
          'ref_hz': histogramRefHz,
          'bins': {for (final e in histogramBins.entries) e.key: e.value},
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

/// Calcula métricas de F0 desde cuadros YIN ya filtrados por mediana.
/// [frames]: un YinFrame cada 10 ms.
TaskMetrics computeTaskMetrics({required List<YinFrame> frames}) {
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
      sts.map((s) => (s - stMean) * (s - stMean)).reduce((a, b) => a + b) / sts.length,);
  // Histograma 1 semitono vs. mediana.
  final bins = <String, int>{};
  for (final f in f0s) {
    final st = (12 * (math.log(f / median) / math.ln2)).round();
    bins['$st'] = (bins['$st'] ?? 0) + 1;
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
    histogramBins: bins,
    histogramRefHz: median,
    contour: contour,
  );
}
