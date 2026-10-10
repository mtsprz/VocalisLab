import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/dsp/metrics.dart';
import 'package:vocalis_companion/core/dsp/yin.dart';

List<YinFrame> _planos(int n, double f0, double rms, {double strength = 0.99}) =>
    List<YinFrame>.generate(n, (_) => YinFrame(f0, strength, rms));

void main() {
  group('computeTaskMetrics', () {
    test('tono 200 Hz estable: media, histograma y contorno', () {
      final frames = _planos(100, 200.0, 0.1);
      final m = computeTaskMetrics(frames: frames);
      expect(m.f0MeanHz!, closeTo(200.0, 0.5));
      expect(m.f0MedianHz!, closeTo(200.0, 0.5));
      expect(m.f0SdSemitones!, closeTo(0.0, 0.05));
      expect(m.voicedFraction, closeTo(1.0, 0.001));
      expect(m.histogramRefHz, closeTo(200.0, 0.5));
      expect(m.histogramBins['0'], 100);
      expect(m.contour.length, 20); // 100 cuadros / 5 = ~20 Hz
    });

    test('payload: campos fuera de alcance viajan como null', () {
      final j = computeTaskMetrics(frames: _planos(50, 210.0, 0.1)).toJson('dsp-test');
      expect(j['dsp_version'], 'dsp-test');
      for (final k in [
        'jitter_pct', 'shimmer_pct', 'hnr_db', 'mpt_sec',
        'intensity_mean_db', 'intensity_sd_db',
      ]) {
        expect(j.containsKey(k), true, reason: k);
        expect(j[k], isNull, reason: k);
      }
      for (final k in [
        'f0_mean_hz', 'f0_median_hz', 'f0_p5_hz', 'f0_p95_hz', 'f0_min_hz',
        'f0_max_hz', 'voiced_fraction', 'f0_sd_semitones', 'f0_sd_hz',
      ]) {
        expect(j[k], isNotNull, reason: k);
      }
      expect((j['f0_histogram'] as Map)['ref_hz'], closeTo(210.0, 0.01));
      expect(j['f0_contour'], isA<List<double>>());
    });

    test('SD en semitonos de serie conocida', () {
      // Alternancia 200/212.13 Hz: separadas 1 semitono, o sea ±0,5 st
      // alrededor de la mediana → SD = 0,5 st (la versión anterior del test
      // esperaba 1,0 por error).
      final frames = <YinFrame>[];
      for (var i = 0; i < 100; i++) {
        frames.add(YinFrame(i.isEven ? 200.0 : 212.13, 0.9, 0.1));
      }
      final m = computeTaskMetrics(frames: frames);
      expect(m.f0SdSemitones!, closeTo(0.5, 0.02));
    });

    test('percentiles, mín/máx y sordos', () {
      final frames = [
        for (var f = 100; f < 200; f++) YinFrame(f.toDouble(), 0.9, 0.1),
        for (var i = 0; i < 100; i++) const YinFrame(0, 0, 0.001),
      ];
      final m = computeTaskMetrics(frames: frames);
      expect(m.voicedFraction, closeTo(0.5, 1e-9));
      expect(m.f0MinHz, 100.0);
      expect(m.f0MaxHz, 199.0);
      expect(m.f0P5Hz!, closeTo(105.0, 1.0));
      expect(m.f0P95Hz!, closeTo(194.0, 1.0));
      expect(m.f0MedianHz!, closeTo(149.5, 0.01));
    });

    test('todo sordo: fracción 0 y nulos seguros', () {
      final frames = List<YinFrame>.generate(50, (_) => const YinFrame(0, 0, 0.001));
      final m = computeTaskMetrics(frames: frames);
      expect(m.voicedFraction, 0.0);
      expect(m.f0MeanHz, isNull);
      expect(m.f0MedianHz, isNull);
    });
  });
}
