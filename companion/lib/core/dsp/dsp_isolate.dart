import 'dart:io';
import 'dart:typed_data';

import 'metrics.dart';
import 'yin.dart';

/// Análisis de tono en isolate (no bloquea la UI).
///
/// Entrada: WAV PCM 16-bit mono 44.1 kHz + segmentos de la tarea.
/// Solo se analizan muestras de segmentos con speaker == 'paciente'.
/// Salida: mapa listo para `acoustics[]` del contrato.
/// Uso: `await Isolate.run(() => analizarTarea(job))`.
class DspJob {
  final String wavPath;
  final List<Map<String, dynamic>> segments;
  final String sexoReferencia;

  const DspJob({
    required this.wavPath,
    required this.segments,
    required this.sexoReferencia,
  });
}

/// Lee PCM16 mono de un WAV estándar (44 bytes de cabecera).
List<double> leerPcm16Mono(String path) {
  final bytes = File(path).readAsBytesSync();
  if (bytes.length < 44) return const [];
  final data = bytes.sublist(44);
  final n = data.length ~/ 2;
  final out = List<double>.filled(n, 0.0);
  final bd = ByteData.sublistView(data);
  for (var i = 0; i < n; i++) {
    out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
  }
  return out;
}

/// Punto de entrada del isolate. Debe ser función top-level.
Map<String, dynamic> analizarTarea(DspJob job) {
  const sr = 44100;
  final samples = leerPcm16Mono(job.wavPath);
  final tracker = YinTracker(
      sampleRate: sr, config: configParaSexo(job.sexoReferencia),);
  final win = (sr * 0.040).round();
  final step = (sr * 0.010).round();
  final all = <YinFrame>[];
  final wins = job.segments
      .where((s) => s['speaker'] == 'paciente')
      .map((s) => (
            ((s['start_sec'] as num).toDouble() * sr).round(),
            ((s['end_sec'] as num).toDouble() * sr).round()
          ),)
      .toList();
  for (final w in wins) {
    final start = ((w.$1.clamp(0, samples.length))).toInt();
    final end = ((w.$2.clamp(0, samples.length))).toInt();
    var pos = start;
    while (pos + win <= end) {
      all.add(tracker.process(samples.sublist(pos, pos + win)));
      pos += step;
    }
  }
  final f0 = medianFilter5(all.map((f) => f.f0).toList());
  final frames = List<YinFrame>.generate(
      all.length, (i) => YinFrame(f0[i], all[i].strength, all[i].rms),);
  final m = computeTaskMetrics(frames: frames);
  return {
    'metrics': m.toJson('companion-dsp/1.0'),
    'frames_total': all.length,
    'frames_voiced': all.where((f) => f.voiced).length,
  };
}
