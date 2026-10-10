import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/dsp/dsp_isolate.dart';

/// Validación contra Praat/SpeechPitch con grabaciones reales.
/// Solo F0 mediana y media; tolerancia ±1 Hz o ±1 %.
/// Valores a completar en test/fixtures/referencias_praat.json.
void main() {
  final ref = File('test/fixtures/referencias_praat.json');
  final casos = (jsonDecode(ref.readAsStringSync())['casos'] as List).cast<Map<String, dynamic>>();

  for (final c in casos) {
    final archivo = File('test/fixtures/${c['archivo']}');
    final med = (c['f0_median_hz'] as num?)?.toDouble();
    final media = (c['f0_mean_hz'] as num?)?.toDouble();
    final pendiente = med == null || media == null
        ? 'faltan valores de ${c['herramienta']} en referencias_praat.json'
        : (!archivo.existsSync() ? 'falta ${archivo.path}' : null);

    test('${c['archivo']} vs ${c['herramienta']}', () {
      final h = ByteData.sublistView(archivo.readAsBytesSync(), 0, 44);
      expect(h.getUint16(22, Endian.little), 1, reason: 'debe ser mono');
      expect(h.getUint32(24, Endian.little), 44100, reason: 'debe ser 44100 Hz');
      expect(h.getUint16(34, Endian.little), 16, reason: 'debe ser PCM 16-bit');
      final dur = (archivo.lengthSync() - 44) / 2 / 44100;
      final r = analizarTarea(DspJob(
        wavPath: archivo.path,
        segments: [
          {'speaker': 'paciente', 'start_sec': 0.0, 'end_sec': dur},
        ],
        sexoReferencia: '${c['sexo_referencia']}',
      ),);
      final m = r['metrics'] as Map<String, dynamic>;
      void cerca(String campo, double esperado) {
        final v = (m[campo] as num).toDouble();
        final tol = math.max(1.0, esperado * 0.01);
        expect((v - esperado).abs() <= tol, true,
            reason: '$campo=${v.toStringAsFixed(2)} esperado=$esperado tol=±${tol.toStringAsFixed(2)}',);
      }

      cerca('f0_median_hz', med!);
      cerca('f0_mean_hz', media!);
    }, skip: pendiente,);
  }
}
