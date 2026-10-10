import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:vocalis_companion/core/audio/wav.dart';
import 'package:vocalis_companion/core/dsp/dsp_isolate.dart';

/// WAV con tramos de tono puro: [(segundos, Hz)].
Future<String> _wav(Directory dir, List<(double, double)> tramos) async {
  const sr = 44100;
  final path = p.join(dir.path, 'sesion.wav');
  final w = WavBlockWriter(path);
  await w.open();
  for (final (seg, hz) in tramos) {
    final n = (seg * sr).round();
    final bd = ByteData(n * 2);
    for (var i = 0; i < n; i++) {
      bd.setInt16(i * 2, (0.5 * 32767 * math.sin(2 * math.pi * hz * i / sr)).round(), Endian.little);
    }
    await w.appendBytes(bd.buffer.asUint8List());
  }
  await w.close();
  return path;
}

void main() {
  test('una pasada por tramos: por tarea, global y solo paciente', () async {
    final dir = await Directory.systemTemp.createTemp('dspses');
    // 0-7 s: 200 Hz (lectura, cruza el tramo de lectura de 5 s)
    // 7-9 s: 400 Hz (fonoaudiólogo, se ignora)
    // 9-12 s: 250 Hz (conversación)
    final wav = await _wav(dir, [(7, 200), (2, 400), (3, 250)]);
    final r = analizarSesion(DspJob(
      wavPath: wav,
      sexoReferencia: 'femenino',
      segments: [
        {'task_type': 'lectura', 'speaker': 'paciente', 'start_sec': 0.0, 'end_sec': 7.0},
        {'task_type': 'conversacion_espontanea', 'speaker': 'fonoaudiologo', 'start_sec': 7.0, 'end_sec': 9.0},
        {'task_type': 'conversacion_espontanea', 'speaker': 'paciente', 'start_sec': 9.0, 'end_sec': 12.0},
      ],
    ),);
    final tareas = (r['por_tarea'] as Map).cast<String, dynamic>();
    final lect = (tareas['lectura'] as Map)['f0_median_hz'] as double;
    final conv = (tareas['conversacion_espontanea'] as Map)['f0_median_hz'] as double;
    expect((lect - 200).abs() <= 2, true, reason: 'lectura=$lect');
    expect((conv - 250).abs() <= 2.5, true, reason: 'conversacion=$conv');
    // Global: 7 s a 200 Hz + 3 s a 250 Hz → mediana 200; el 400 no entra.
    final g = (r['global'] as Map).cast<String, dynamic>();
    expect(((g['f0_median_hz'] as double) - 200).abs() <= 2, true);
    expect((g['f0_max_hz'] as double) < 300, true, reason: 'no debe incluir 400 Hz');
    // Cuadros contiguos a través del límite de 5 s: ~700 cuadros en lectura.
    final cont = (tareas['lectura'] as Map)['f0_contour'] as List;
    expect(cont.length, closeTo(700 / 5, 2));
    await dir.delete(recursive: true);
  });

  test('recortarWav copia bytes del rango sin cargar el archivo', () async {
    final dir = await Directory.systemTemp.createTemp('clip');
    final wav = await _wav(dir, [(3, 220)]);
    final clip = p.join(dir.path, 'clip.wav');
    await recortarWav(origen: wav, desdeSec: 1, segundos: 1.5, destino: clip);
    expect(await File(clip).length(), 44 + (1.5 * 44100).round() * 2);
    final orig = await File(wav).readAsBytes();
    final rec = await File(clip).readAsBytes();
    expect(rec.sublist(44, 144), orig.sublist(44 + 44100 * 2, 44 + 44100 * 2 + 100));
    await dir.delete(recursive: true);
  });
}
