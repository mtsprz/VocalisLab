import 'dart:isolate';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'diarizacion.dart';
import 'diarizacion_huella.dart';
import 'huella.dart';
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
List<YinFrame> _cuadros(RandomAccessFile f, int inicio, int fin, YinTracker t,
    {void Function(int muestra)? avance,}) {
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
    avance?.call(pos);
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

/// Trabajo de análisis automático (sesión completa, sin marcas manuales).
class AutoJob {
  final String wavPath;
  final String sexoReferencia;
  final double? fonoMedianaHz;
  final double? fonoSdSt;
  final double? rangoMinHz;
  final double? rangoMaxHz;

  /// Modelo CAM++ (archivo .onnx) y huella de "Mi voz": si están, la
  /// separación es por timbre (huella); si no, por altura tonal (respaldo).
  final String? modeloHuella;
  final Float32List? huellaFono;

  const AutoJob({
    required this.wavPath,
    required this.sexoReferencia,
    this.fonoMedianaHz,
    this.fonoSdSt,
    this.rangoMinHz,
    this.rangoMaxHz,
    this.modeloHuella,
    this.huellaFono,
  });
}

/// Rango de YIN del paciente, ampliado para no perder la voz del
/// fonoaudiólogo/a si cae fuera (si no, no se la podría separar).
YinConfig _configAuto(AutoJob job) {
  final c = configParaSexo(job.sexoReferencia);
  final fono = job.fonoMedianaHz;
  if (fono == null) return c;
  return YinConfig(
    threshold: c.threshold,
    energyGateRms: c.energyGateRms,
    minHz: math.max(60, math.min(c.minHz, fono * 0.6)),
    maxHz: math.min(1000, math.max(c.maxHz, fono * 1.6)),
  );
}

Float32List _aFloat32(Float64List v) {
  final out = Float32List(v.length);
  for (var i = 0; i < v.length; i++) {
    out[i] = v[i];
  }
  return out;
}

/// Huellas por tramo de 1,5 s con voz (>= 30 % de cuadros sonoros).
/// Devuelve {índice de tramo: huella}. null si el modelo no carga.
Map<int, Float32List>? _huellasPorTramo(RandomAccessFile f, int total, List<YinFrame> cuadros,
    String modelo, void Function(double) avance,) {
  final ex = abrirExtractor(modelo);
  if (ex == null) return null;
  try {
    final porTramo = (duracionTramoSeg * 100).round(); // cuadros de 10 ms
    final muestrasTramo = (duracionTramoSeg * _sr).round();
    final nTramos = (cuadros.length + porTramo - 1) ~/ porTramo;
    final out = <int, Float32List>{};
    for (var t = 0; t < nTramos; t++) {
      final a = t * porTramo;
      final b = math.min(a + porTramo, cuadros.length);
      var sonoros = 0;
      for (var i = a; i < b; i++) {
        if (cuadros[i].f0 > 0) sonoros++;
      }
      if (sonoros >= porTramo * 0.3) {
        final ini = t * muestrasTramo;
        final n = math.min(muestrasTramo, total - ini);
        if (n > _sr ~/ 2) {
          final h = huellaDe(ex, _aFloat32(leerRango(f, ini, n)), _sr);
          if (h != null) out[t] = h;
        }
      }
      avance((t + 1) / nTramos);
    }
    return out;
  } finally {
    ex.free();
  }
}

/// Separación por huella: etiqueta tramos de 1,5 s y arma segmentos y
/// cuadros del paciente.
Map<String, dynamic>? _separarPorHuella(List<YinFrame> cuadros, Map<int, Float32List> huellas,
    Float32List huellaFono,) {
  if (huellas.length < 2) return null;
  final indices = huellas.keys.toList()..sort();
  final asig = asignarPorHuella([for (final i in indices) huellas[i]!], huellaFono);
  // Si la huella no encontró ningún tramo del paciente, no se arriesga una
  // medición vacía: se usa la separación por altura tonal.
  if (!asig.esPaciente.contains(true)) return null;
  final porTramo = (duracionTramoSeg * 100).round();
  final nTramos = (cuadros.length + porTramo - 1) ~/ porTramo;
  final etiqueta = List<bool?>.filled(nTramos, null);
  for (var k = 0; k < indices.length; k++) {
    etiqueta[indices[k]] = asig.esPaciente[k];
  }
  // Tramos sin voz heredan el anterior (o el primero con voz).
  var actual = etiqueta.firstWhere((e) => e != null, orElse: () => true)!;
  for (var t = 0; t < nTramos; t++) {
    etiqueta[t] ??= actual;
    actual = etiqueta[t]!;
  }
  final segs = <Map<String, dynamic>>[];
  final pac = <YinFrame>[];
  var sonPac = 0, sonTot = 0;
  for (var t = 0; t < nTramos; t++) {
    final esPac = etiqueta[t]!;
    final a = t * porTramo;
    final b = math.min(a + porTramo, cuadros.length);
    final ini = a * 0.010, fin = b * 0.010;
    final quien = esPac ? 'paciente' : 'fonoaudiologo';
    if (segs.isNotEmpty && segs.last['speaker'] == quien) {
      segs.last['end_sec'] = fin;
    } else {
      segs.add({'task_type': 'conversacion_espontanea', 'speaker': quien, 'start_sec': ini, 'end_sec': fin});
    }
    for (var i = a; i < b; i++) {
      if (cuadros[i].f0 > 0) {
        sonTot++;
        if (esPac) sonPac++;
      }
      if (esPac) pac.add(cuadros[i]);
    }
  }
  return {
    'metrics': _metricas(pac),
    'segmentos': segs,
    'fraccion_paciente': sonTot == 0 ? 0.0 : sonPac / sonTot,
    'confianza': asig.confianza,
    'similitud_voces': asig.similitudEntreVoces,
    'metodo': 'huella',
  };
}

/// Sesión completa: una pasada YIN → separación de voces (por huella vocal si
/// hay modelo y "Mi voz"; si no, por altura tonal) → métricas de F0 solo del
/// paciente. Devuelve {'metrics', 'segmentos', 'fraccion_paciente',
/// 'confianza', 'metodo', ...}.
Map<String, dynamic> analizarSesionAuto(AutoJob job, {void Function(double)? progreso}) {
  final tracker = YinTracker(sampleRate: _sr, config: _configAuto(job));
  final f = File(job.wavPath).openSync();
  try {
    final total = math.max(0, (f.lengthSync() - _cabecera) ~/ 2);
    final conHuella = job.modeloHuella != null && job.huellaFono != null;
    final pesoYin = conHuella ? 0.5 : 1.0;
    final cuadros = _cuadros(f, 0, total, tracker,
        avance: (m) => progreso?.call(total == 0 ? pesoYin : pesoYin * m / total),);
    if (conHuella) {
      final huellas = _huellasPorTramo(f, total, cuadros, job.modeloHuella!,
          (v) => progreso?.call(pesoYin + (1 - pesoYin) * v),);
      if (huellas != null) {
        final r = _separarPorHuella(cuadros, huellas, job.huellaFono!);
        if (r != null) return r;
      }
    }
    final fono = job.fonoMedianaHz == null
        ? null
        : PerfilVoz(job.fonoMedianaHz!, job.fonoSdSt ?? 1.0);
    final d = diarizar(cuadros,
        fono: fono, rangoMinHz: job.rangoMinHz, rangoMaxHz: job.rangoMaxHz,);
    return {
      'metrics': _metricas(d.cuadrosPaciente),
      'segmentos': d.segmentos,
      'fraccion_paciente': d.fraccionPaciente,
      'confianza': d.confianza,
      'separacion_st': d.separacionSt,
      'metodo': conHuella ? 'tono_respaldo' : 'tono',
    };
  } finally {
    f.closeSync();
  }
}

/// Perfil de la voz del fonoaudiólogo/a desde una grabación corta: altura
/// tonal + huella vocal (si se pasa el modelo).
Map<String, dynamic>? analizarPerfilVoz(String wavPath, {String? modeloHuella}) {
  final tracker = YinTracker(sampleRate: _sr, config: const YinConfig(minHz: 60, maxHz: 600));
  final f = File(wavPath).openSync();
  try {
    final total = math.max(0, (f.lengthSync() - _cabecera) ~/ 2);
    final cuadros = _cuadros(f, 0, total, tracker);
    final p = perfilDesdeCuadros(cuadros);
    if (p == null) return null;
    Float32List? huella;
    if (modeloHuella != null) {
      final hs = _huellasPorTramo(f, total, cuadros, modeloHuella, (_) {});
      if (hs != null && hs.isNotEmpty) huella = centro(hs.values);
    }
    return {
      'mediana_hz': p.medianaHz,
      'sd_st': p.sdSt,
      if (huella != null) 'huella': huella,
    };
  } finally {
    f.closeSync();
  }
}

/// Entrada del isolate: función de nivel superior para que el mensaje no
/// arrastre el contexto del llamador (una pantalla no se puede enviar).
void _entradaAuto((SendPort, AutoJob) m) {
  final (puerto, trabajo) = m;
  try {
    var ultimo = -1;
    final r = analizarSesionAuto(trabajo, progreso: (p) {
      final pct = (p * 100).floor();
      if (pct != ultimo) {
        ultimo = pct;
        puerto.send(p);
      }
    },);
    puerto.send({'ok': r});
  } catch (e) {
    puerto.send({'error': '$e'});
  }
}

/// Corre [analizarSesionAuto] en otro isolate informando el avance (0..1).
Future<Map<String, dynamic>> analizarSesionAutoEnIsolate(
    AutoJob job, void Function(double) onProgreso,) async {
  final rp = ReceivePort();
  await Isolate.spawn<(SendPort, AutoJob)>(_entradaAuto, (rp.sendPort, job));
  await for (final msg in rp) {
    if (msg is double) {
      onProgreso(msg);
    } else if (msg is Map) {
      rp.close();
      if (msg['error'] != null) throw Exception(msg['error']);
      return Map<String, dynamic>.from(msg['ok'] as Map);
    }
  }
  throw Exception('El análisis terminó sin resultado');
}

Map<String, dynamic>? _entradaPerfil(String wav, String? modelo) =>
    analizarPerfilVoz(wav, modeloHuella: modelo);

/// [analizarPerfilVoz] en otro isolate (solo viajan rutas de archivo).
Future<Map<String, dynamic>?> analizarPerfilVozEnIsolate(String wavPath, {String? modeloHuella}) =>
    Isolate.run(() => _entradaPerfil(wavPath, modeloHuella));
