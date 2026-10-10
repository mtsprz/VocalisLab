import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'metrics.dart';
import 'yin.dart';

/// Análisis de tono en isolate (no bloquea la UI).
///
/// Entrada: WAV PCM 16-bit mono 44.1 kHz (cabecera de 44 bytes) + segmentos.
/// Solo se analizan muestras de segmentos con speaker == 'paciente'.
///
/// Pensado para equipos con poca RAM (Galaxy A02: 1,9 GB, 32 bits): el WAV
/// se lee por tramos de 5 s desde disco, nunca completo (una sesión de
/// 45 min ocuparía ~950 MB como doubles). Cada tramo se analiza UNA vez y sus
/// cuadros se reusan para la métrica por tarea y para la global.
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

const _sr = 44100;
const _cabecera = 44;
const _tramoLectura = _sr * 5;

/// Lee [n] muestras desde [desde] (en muestras) normalizadas a -1..1.
Float64List leerRango(RandomAccessFile f, int desde, int n) {
  f.setPositionSync(_cabecera + desde * 2);
  final bytes = f.readSync(n * 2);
  final bd = ByteData.sublistView(bytes);
  final m = bytes.length ~/ 2;
  final out = Float64List(m);
  for (var i = 0; i < m; i++) {
    out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
  }
  return out;
}

/// Cuadros YIN (10 ms) de las muestras [inicio, fin) leyendo por tramos.
List<YinFrame> _cuadros(RandomAccessFile f, int inicio, int fin, YinTracker t) {
  final win = t.windowSize;
  final step = (_sr * 0.010).round();
  final out = <YinFrame>[];
  var pos = inicio;
  while (pos + win <= fin) {
    final nCuadros = math.min((fin - win - pos) ~/ step + 1, _tramoLectura ~/ step);
    final buf = leerRango(f, pos, (nCuadros - 1) * step + win);
    for (var k = 0; k < nCuadros; k++) {
      final a = k * step;
      if (a + win > buf.length) break;
      out.add(t.process(Float64List.sublistView(buf, a, a + win)));
    }
    pos += nCuadros * step;
  }
  return out;
}

Map<String, dynamic> _metricas(List<YinFrame> crudos) {
  final f0 = medianFilter5(crudos.map((f) => f.f0).toList());
  final frames = List<YinFrame>.generate(
      crudos.length, (i) => YinFrame(f0[i], crudos[i].strength, crudos[i].rms),);
  return computeTaskMetrics(frames: frames).toJson('companion-dsp/1.0');
}

/// Una sola pasada sobre la sesión. Devuelve
/// `{'por_tarea': {task_type: metrics}, 'global': metrics}`; global = todos los
/// tramos del paciente en orden cronológico. Debe ser función top-level.
Map<String, dynamic> analizarSesion(DspJob job) {
  final tracker = YinTracker(sampleRate: _sr, config: configParaSexo(job.sexoReferencia));
  final f = File(job.wavPath).openSync();
  try {
    final total = math.max(0, (f.lengthSync() - _cabecera) ~/ 2);
    final porTarea = <String, List<YinFrame>>{};
    final global = <YinFrame>[];
    for (final s in job.segments) {
      final tarea = '${s['task_type'] ?? ''}';
      final lista = porTarea.putIfAbsent(tarea, () => []);
      if (s['speaker'] != 'paciente') continue;
      final a = (((s['start_sec'] as num).toDouble() * _sr).round().clamp(0, total)).toInt();
      final b = (((s['end_sec'] as num).toDouble() * _sr).round().clamp(0, total)).toInt();
      final c = _cuadros(f, a, b, tracker);
      lista.addAll(c);
      global.addAll(c);
    }
    return {
      'por_tarea': {for (final e in porTarea.entries) e.key: _metricas(e.value)},
      'global': _metricas(global),
    };
  } finally {
    f.closeSync();
  }
}

/// Compatibilidad: una tarea (o el WAV entero) → `{'metrics': ...}`.
Map<String, dynamic> analizarTarea(DspJob job) {
  final r = analizarSesion(job);
  return {'metrics': r['global']};
}
