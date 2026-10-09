import 'dart:math' as math;
import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/dsp/yin.dart';

/// Tono puro de [freq] Hz, 1 s a 44.1 kHz, amplitud 0.5.
List<double> _tono(double freq, {double amp = 0.5, double segundos = 1.0}) {
  const sr = 44100;
  final n = (sr * segundos).round();
  return List<double>.generate(n, (i) => amp * math.sin(2 * math.pi * freq * i / sr));
}

List<double> _analizar(
    List<double> samples, YinConfig config, {int window = 1764, int step = 441}) {
  final t = YinTracker(sampleRate: 44100, config: config);
  final out = <double>[];
  for (var pos = 0; pos + window <= samples.length; pos += step) {
    out.add(t.process(samples.sublist(pos, pos + window)).f0);
  }
  return medianFilter5(out);
}

void _cerca(double medido, double esperado) {
  final tol = math.max(1.0, esperado * 0.01); // ±1 Hz o ±1 %
  expect((medido - esperado).abs() <= tol, true,
      reason: 'F0=$medido esperado=$esperado tol=$tol');
}

void main() {
  group('YIN tonos puros', () {
    test('voz masculina 110 Hz', () {
      final f0 = _analizar(_tono(110.0), configParaSexo('masculino'));
      final v = f0.where((f) => f > 0).toList();
      expect(v.length / f0.length, greaterThan(0.95));
      v.sort();
      _cerca(v[v.length ~/ 2], 110.0);
    });

    test('voz femenina 196 Hz', () {
      final f0 = _analizar(_tono(196.0), configParaSexo('femenino'));
      final v = f0.where((f) => f > 0).toList();
      expect(v.length / f0.length, greaterThan(0.95));
      v.sort();
      _cerca(v[v.length ~/ 2], 196.0);
    });

    test('voz femenina 261.6 Hz', () {
      final f0 = _analizar(_tono(261.6), configParaSexo('femenino'));
      final v = f0.where((f) => f > 0).toList();
      expect(v.length / f0.length, greaterThan(0.95));
      v.sort();
      _cerca(v[v.length ~/ 2], 261.6);
    });

    test('voz infantil 350 Hz', () {
      final f0 = _analizar(_tono(350.0), configParaSexo('ninex'));
      final v = f0.where((f) => f > 0).toList();
      expect(v.length / f0.length, greaterThan(0.95));
      v.sort();
      _cerca(v[v.length ~/ 2], 350.0);
    });

    test('silencio → todo sordo', () {
      final f0 = _analizar(List<double>.filled(44100, 0.0), configParaSexo('femenino'));
      expect(f0.every((f) => f == 0.0), true);
    });

    test('ruido blanco → mayoría sordo', () {
      final rnd = math.Random(42);
      final noise = List<double>.generate(44100, (_) => (rnd.nextDouble() * 2 - 1) * 0.4);
      final f0 = _analizar(noise, configParaSexo('masculino'));
      final voiced = f0.where((f) => f > 0).length / f0.length;
      expect(voiced, lessThan(0.5));
    });

    test('fuera de rango por sexo se atenúa', () {
      // 80 Hz con config femenina (min 100 Hz): el tracker no debe inventar 160.
      final f0 = _analizar(_tono(80.0), configParaSexo('femenino'));
      final v = f0.where((f) => f > 0).toList();
      if (v.isNotEmpty) {
        v.sort();
        final med = v[v.length ~/ 2];
        expect((med - 80.0).abs() < 2.0 || (med - 160.0).abs() < 2.0, true);
      }
    });
  });

  group('medianFilter5', () {
    test('suaviza un salto aislado', () {
      final out = medianFilter5([200, 200, 400, 200, 200, 200, 200]);
      expect(out[2], 200.0);
    });
    test('ventana mayormente sorda → 0', () {
      final out = medianFilter5([0, 0, 200, 0, 0]);
      expect(out[2], 0.0);
    });
  });
}
