import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/dsp/nota.dart';
import 'package:vocalis_companion/ui/summary_screen.dart' show edadDesde, rangoPara;

void main() {
  group('notaDesdeHz (franco-belga: La3 = 440 Hz, Do3 = Do central)', () {
    test('referencias exactas', () {
      expect(notaDesdeHz(440), 'La3');
      expect(notaDesdeHz(261.63), 'Do3');
      expect(notaDesdeHz(220), 'La2');
      expect(notaDesdeHz(110), 'La1');
      expect(notaDesdeHz(246.94), 'Si2'); // cambio de octava en Do
      expect(notaDesdeHz(32.7), 'Do0'); // Do0 ≈ 33 Hz
    });

    test('coincide con la tabla normativa de Wilson (1973)', () {
      expect(notaDesdeHz(445), 'La3');
      expect(notaDesdeHz(400), 'Sol3');
      expect(notaDesdeHz(375), 'Fa#3');
      expect(notaDesdeHz(350), 'Fa3');
      expect(notaDesdeHz(325), 'Mi3');
      expect(notaDesdeHz(295), 'Re3');
      expect(notaDesdeHz(260), 'Do3');
    });

    test('139 Hz → Do#2', () {
      expect(notaDesdeHz(139), 'Do#2');
      expect(alturaTonal(139), 'Do#2 · 139 Hz');
    });

    test('redondeo al semitono más cercano', () {
      expect(notaDesdeHz(452), 'La3'); // +0,47 st
      expect(notaDesdeHz(454), 'La#3'); // +0,54 st
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

  group('tabla normativa completa (companion_referencias_normativas.sql)', () {
    Map<String, dynamic> f(String sx, int a, int b, num mn, num mx, num pa, num pb) => {
          'sexo_referencia': sx, 'edad_min': a, 'edad_max': b,
          'f0_min_hz': mn, 'f0_max_hz': mx, 'f0_promedio_min_hz': pa, 'f0_promedio_max_hz': pb,
        };
    final t = [
      f('ninex', 3, 3, 340, 460, 400, 400),
      f('ninex', 16, 18, 100, 180, 125, 150),
      f('masculino', 19, 120, 100, 165, 132, 138.8),
      f('masculino', 40, 49, 100, 165, 100, 107),
      f('femenino', 19, 120, 190, 262, 209.3, 224),
      f('femenino', 60, 69, 175, 262, 175, 200),
    ];
    test('niño de 3 años: Wilson, sin importar el sexo', () {
      expect(rangoPara(t, 'masculino', 3)?['f0_min_hz'], 340);
    });
    test('18 años: todavía tabla de adolescencia', () {
      expect(rangoPara(t, 'femenino', 18)?['f0_max_hz'], 180);
    });
    test('hombre de 45: década 40-49 (la franja más angosta)', () {
      expect(rangoPara(t, 'masculino', 45)?['f0_promedio_max_hz'], 107);
    });
    test('mujer de 65: presbifonía, límite inferior 175 Hz', () {
      expect(rangoPara(t, 'femenino', 65)?['f0_min_hz'], 175);
    });
    test('sin fecha de nacimiento: rango general adulto del sexo', () {
      expect(rangoPara(t, 'femenino', null)?['f0_min_hz'], 190);
    });
    test('adulto sin sexo: no se compara (no se supone un sexo)', () {
      expect(rangoPara(t, '', 40), isNull);
      expect(rangoPara(t, '', null), isNull);
    });
  });
}
