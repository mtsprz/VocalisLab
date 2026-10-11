import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/dsp/dsp_isolate.dart';
import 'package:vocalis_companion/core/dsp/yin.dart';

Float64List _tono(double hz, double seg, {double amp = 0.5}) {
  const sr = 44100;
  final n = (seg * sr).round();
  return Float64List.fromList(List.generate(n, (i) => amp * math.sin(2 * math.pi * hz * i / sr)));
}

double _mediana(List<YinFrame> c) {
  final v = medianFilter5(c.map((f) => f.f0).toList()).where((f) => f > 0).toList()..sort();
  return v[v.length ~/ 2];
}

void main() {
  group('decimación ×3 + YIN (14,7 kHz)', () {
    for (final (hz, sexo) in [(110.0, 'masculino'), (196.0, 'femenino'), (261.6, 'femenino'), (350.0, 'ninex')]) {
      test('$hz Hz dentro de ±1 Hz o ±1 %', () {
        final a = AnalizadorStream(configParaSexo(sexo))..agregar(_tono(hz, 1.0));
        final med = _mediana(a.cuadros);
        final tol = math.max(1.0, hz * 0.01);
        expect((med - hz).abs() <= tol, true, reason: 'medido=$med esperado=$hz');
        expect(a.cuadros.length, closeTo(100 - 4, 2)); // ~1 cuadro cada 10 ms
      });
    }

    test('en vivo (fragmentos irregulares) = de una vez', () {
      final x = _tono(180, 3.0);
      final entera = AnalizadorStream(configParaSexo('femenino'))..agregar(x);
      final vivo = AnalizadorStream(configParaSexo('femenino'));
      final r = math.Random(1);
      var i = 0;
      while (i < x.length) {
        final n = math.min(x.length - i, 200 + r.nextInt(5000)); // como el micrófono
        vivo.agregar(Float64List.sublistView(x, i, i + n));
        i += n;
      }
      expect(vivo.cuadros.length, entera.cuadros.length);
      for (var k = 0; k < entera.cuadros.length; k++) {
        expect(vivo.cuadros[k].f0, closeTo(entera.cuadros[k].f0, 1e-9));
      }
    });

    test('rendimiento: 60 s de audio', () {
      final x = _tono(150, 60);
      final sw = Stopwatch()..start();
      final a = AnalizadorStream(configParaSexo('masculino'))..agregar(x);
      sw.stop();
      // ignore: avoid_print
      print('60 s de audio analizados en ${sw.elapsedMilliseconds} ms (${a.cuadros.length} cuadros)');
      expect(a.cuadros.length, greaterThan(5900));
    });
  });
}
