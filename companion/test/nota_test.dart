import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/dsp/nota.dart';
import 'package:vocalis_companion/ui/summary_screen.dart' show edadDesde, rangoPara;

void main() {
  group('notaDesdeHz (La4 = 440 Hz, Do4 = Do central)', () {
    test('referencias exactas', () {
      expect(notaDesdeHz(440), 'La4');
      expect(notaDesdeHz(261.63), 'Do4');
      expect(notaDesdeHz(220), 'La3');
      expect(notaDesdeHz(110), 'La2');
      expect(notaDesdeHz(196), 'Sol3');
      expect(notaDesdeHz(246.94), 'Si3'); // cambio de octava en Do
      expect(notaDesdeHz(277.18), 'Do#4');
    });

    test('ejemplo de la consigna: 139 Hz → Do#3', () {
      expect(notaDesdeHz(139), 'Do#3');
      expect(alturaTonal(139), 'Do#3 · 139 Hz');
    });

    test('redondeo al semitono más cercano', () {
      expect(notaDesdeHz(452), 'La4'); // +0,47 st
      expect(notaDesdeHz(454), 'La#4'); // +0,54 st
    });

    test('sin F0', () {
      expect(notaDesdeHz(null), isNull);
      expect(notaDesdeHz(0), isNull);
      expect(alturaTonal(null), '— Hz');
    });
  });

  group('rango de referencia por sexo y edad', () {
    final rangos = [
      {'sexo_referencia': 'masculino', 'edad_min': 18, 'edad_max': 99, 'f0_min_hz': 100, 'f0_max_hz': 130},
      {'sexo_referencia': 'femenino', 'edad_min': 18, 'edad_max': 99, 'f0_min_hz': 190, 'f0_max_hz': 225},
      {'sexo_referencia': 'ninex', 'edad_min': 4, 'edad_max': 10, 'f0_min_hz': 240, 'f0_max_hz': 300},
    ];

    test('adultos por sexo', () {
      expect(rangoPara(rangos, 'femenino', 35)?['f0_min_hz'], 190);
      expect(rangoPara(rangos, 'masculino', 40)?['f0_max_hz'], 130);
    });

    test('niñez por edad, sin importar el sexo', () {
      expect(rangoPara(rangos, 'masculino', 7)?['sexo_referencia'], 'ninex');
    });

    test('edad fuera de toda fila → sin rango; sin edad → solo sexo', () {
      expect(rangoPara(rangos, 'femenino', 14), isNull);
      expect(rangoPara(rangos, 'femenino', null)?['f0_min_hz'], 190);
    });

    test('edadDesde', () {
      final hoy = DateTime(2026, 10, 9);
      expect(edadDesde('1990-10-09', hoy: hoy), 36);
      expect(edadDesde('1990-10-10', hoy: hoy), 35);
      expect(edadDesde('', hoy: hoy), isNull);
    });
  });
}
