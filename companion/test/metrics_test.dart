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
      // jitter/shimmer/HNR solo en sostenida
      expect(m.jitterPct, isNull);
      expect(m.shimmerPct, isNull);
      expect(m.hnrDb, isNull);
      expect(m.mptSec, isNull);
      final j = m.toJson('dsp-test');
      expect(j['dsp_version'], 'dsp-test');
      expect(j['jitter_pct'], isNull);
    });

    test('sostenida: jitter~0, shimmer~0, HNR alto, MPT pasa', () {
      final frames = _planos(200, 210.0, 0.1);
      final m = computeTaskMetrics(frames: frames, sostenida: true, mptSec: 18.2);
      expect(m.jitterPct!, closeTo(0.0, 0.05));
      expect(m.shimmerPct!, closeTo(0.0, 0.05));
      expect(m.hnrDb!, greaterThan(15.0));
      expect(m.mptSec, 18.2);
    });

    test('SD en semitonos de serie conocida', () {
      // Alternancia 200/212.13 Hz ≈ ±1 semitono → SD ≈ 1.0 st.
      final frames = <YinFrame>[];
      for (var i = 0; i < 100; i++) {
        frames.add(YinFrame(i.isEven ? 200.0 : 212.13, 0.9, 0.1));
      }
      final m = computeTaskMetrics(frames: frames);
      expect(m.f0SdSemitones!, closeTo(1.0, 0.15));
    });

    test('todo sordo: fracción 0 y nulos seguros', () {
      final frames = List<YinFrame>.generate(50, (_) => const YinFrame(0, 0, 0.001));
      final m = computeTaskMetrics(frames: frames, sostenida: true, mptSec: 5);
      expect(m.voicedFraction, 0.0);
      expect(m.f0MeanHz, isNull);
      expect(m.jitterPct, isNull);
    });

    test('dB con offset de calibración', () {
      final frames = _planos(20, 200.0, 0.1);
      final a = computeTaskMetrics(frames: frames);
      final b = computeTaskMetrics(frames: frames, calibrationDbOffset: 10.0);
      expect(b.intensityMeanDb! - a.intensityMeanDb!, closeTo(10.0, 0.001));
    });
  });
}
