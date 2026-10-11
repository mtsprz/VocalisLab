import 'dart:async';
import 'dart:io';
import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:sherpa_onnx/sherpa_onnx.dart' as so;

import 'decimador.dart';
import 'diarizacion.dart';
import 'diarizacion_huella.dart';
import 'huella.dart';
import 'metrics.dart';
import 'yin.dart';

/// Análisis de altura tonal (no bloquea la UI).
///
/// Todo pasa por [AnalizadorStream]: audio 44,1 kHz → decimación ×3 a
/// 14,7 kHz (antialiasing) → YIN cada 10 ms (ventana 40 ms) → huella vocal
/// cada 1,5 s con voz. El mismo código corre:
///  - EN VIVO durante la grabación ([AnalisisEnVivo]): al tocar Detener solo
///    falta agrupar voces y calcular la mediana (1-2 s, dure lo que dure);
///  - desde archivo (recuperación tras cierre forzado, "Mi voz", fixtures),
///    leyendo por tramos de 5 s (nunca el WAV entero en RAM: equipo de 2 GB).
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
  return pcm16AFloat(f.readSync(n * 2));
}

Float64List pcm16AFloat(Uint8List bytes) {
  final bd = ByteData.sublistView(bytes);
  final m = bytes.length ~/ 2;
  final out = Float64List(m);
  for (var i = 0; i < m; i++) {
    out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
  }
  return out;
}

/// Analizador incremental: [agregar] por fragmentos (44,1 kHz), [terminar]
/// al final. Expone [cuadros] (uno cada 10 ms) y [huellas] por tramo de
/// 1,5 s (solo tramos con ≥ 30 % de cuadros sonoros).
class AnalizadorStream {
  static const sr = Decimador3.sampleRateSalida; // 14,7 kHz
  static const hop = 147; // 10 ms
  static const muestrasTramo = 22050; // 1,5 s
  static const cuadrosPorTramo = 150;

  final YinTracker _yin;
  final so.SpeakerEmbeddingExtractor? _ex;
  final _dec = Decimador3();
  final cuadros = <YinFrame>[];
  final huellas = <int, Float32List>{};

  Float64List _buf = Float64List(0);
  int _bufIni = 0; // índice absoluto (a 14,7 kHz) de _buf[0]
  int _proximo = 0; // inicio absoluto del próximo cuadro
  final _tramo = <double>[];
  int _tramoIdx = 0;

  AnalizadorStream(YinConfig config, {so.SpeakerEmbeddingExtractor? extractor})
      : _yin = YinTracker(sampleRate: sr, config: config),
        _ex = extractor;

  int get _win => _yin.windowSize;

  void agregar(Float64List x44k) {
    final d = _dec.procesar(x44k);
    if (d.isEmpty) return;
    if (_ex != null) _tramo.addAll(d);
    final nuevo = Float64List(_buf.length + d.length)
      ..setRange(0, _buf.length, _buf)
      ..setRange(_buf.length, _buf.length + d.length, d);
    _buf = nuevo;
    while (_proximo + _win <= _bufIni + _buf.length) {
      final off = _proximo - _bufIni;
      cuadros.add(_yin.process(Float64List.sublistView(_buf, off, off + _win)));
      _proximo += hop;
    }
    final descartar = _proximo - _bufIni;
    if (descartar > 0) {
      _buf = Float64List.fromList(Float64List.sublistView(_buf, descartar));
      _bufIni += descartar;
    }
    // Huellas por tramo completo (cuando sus 150 cuadros ya están calculados).
    while (_ex != null &&
        _tramo.length >= muestrasTramo &&
        cuadros.length >= (_tramoIdx + 1) * cuadrosPorTramo) {
      _cerrarTramo(_tramo.sublist(0, muestrasTramo));
      _tramo.removeRange(0, muestrasTramo);
    }
  }

  void _cerrarTramo(List<double> muestras) {
    final a = _tramoIdx * cuadrosPorTramo;
    final b = math.min(a + cuadrosPorTramo, cuadros.length);
    var sonoros = 0;
    for (var i = a; i < b; i++) {
      if (cuadros[i].f0 > 0) sonoros++;
    }
    if (sonoros >= cuadrosPorTramo * 0.3 && muestras.length >= sr ~/ 2) {
      final h = huellaDe(_ex!, Float32List.fromList(muestras), sr);
      if (h != null) huellas[_tramoIdx] = h;
    }
    _tramoIdx++;
  }

  /// Cierra el último tramo parcial (si tiene ≥ 0,5 s).
  void terminar() {
    if (_ex != null && _tramo.isNotEmpty) {
      _cerrarTramo(List<double>.from(_tramo));
      _tramo.clear();
    }
  }
}

Map<String, dynamic> _metricas(List<YinFrame> crudos) {
  final f0 = medianFilter5(crudos.map((f) => f.f0).toList());
  final frames = List<YinFrame>.generate(
      crudos.length, (i) => YinFrame(f0[i], crudos[i].strength, crudos[i].rms),);
  return computeTaskMetrics(frames: frames).toJson('companion-dsp/1.1');
}

/// Cuadros de [inicio, fin) (muestras a 44,1 kHz) leyendo el archivo por tramos.
List<YinFrame> _cuadrosDeArchivo(RandomAccessFile f, int inicio, int fin, YinConfig cfg) {
  final a = AnalizadorStream(cfg);
  var pos = inicio;
  while (pos < fin) {
    final n = math.min(_tramoLectura, fin - pos);
    a.agregar(leerRango(f, pos, n));
    pos += n;
  }
  return a.cuadros;
}

/// Una sola pasada sobre la sesión, por segmentos marcados. Devuelve
/// `{'por_tarea': {task_type: metrics}, 'global': metrics}`.
Map<String, dynamic> analizarSesion(DspJob job) {
  final cfg = configParaSexo(job.sexoReferencia);
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
      final c = _cuadrosDeArchivo(f, a, b, cfg);
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

/// Configuración del análisis automático (sesión completa, sin marcas).
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

  bool get conHuella => modeloHuella != null && huellaFono != null;
}

/// Rango de YIN del paciente, ampliado para no perder la voz del
/// fonoaudiólogo/a si cae fuera (si no, no se la podría separar).
YinConfig configAuto(AutoJob job) {
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

/// Separación por huella: etiqueta tramos de 1,5 s y arma segmentos y
/// cuadros del paciente. null si no se puede (y se usa la altura tonal).
Map<String, dynamic>? _separarPorHuella(List<YinFrame> cuadros, Map<int, Float32List> huellas,
    Float32List huellaFono,) {
  if (huellas.length < 2) return null;
  final indices = huellas.keys.toList()..sort();
  final asig = asignarPorHuella([for (final i in indices) huellas[i]!], huellaFono);
  // Si la huella no encontró ningún tramo del paciente, no se arriesga una
  // medición vacía: se usa la separación por altura tonal.
  if (!asig.esPaciente.contains(true)) return null;
  const porTramo = AnalizadorStream.cuadrosPorTramo;
  final nTramos = (cuadros.length + porTramo - 1) ~/ porTramo;
  final etiqueta = List<bool?>.filled(nTramos, null);
  for (var k = 0; k < indices.length; k++) {
    if (indices[k] < nTramos) etiqueta[indices[k]] = asig.esPaciente[k];
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

/// Resultado final a partir de lo acumulado (en vivo o desde archivo).
Map<String, dynamic> resultadoDe(AnalizadorStream a, AutoJob job) {
  if (job.conHuella && a.huellas.isNotEmpty) {
    final r = _separarPorHuella(a.cuadros, a.huellas, job.huellaFono!);
    if (r != null) return r;
  }
  final fono = job.fonoMedianaHz == null ? null : PerfilVoz(job.fonoMedianaHz!, job.fonoSdSt ?? 1.0);
  final d = diarizar(a.cuadros, fono: fono, rangoMinHz: job.rangoMinHz, rangoMaxHz: job.rangoMaxHz);
  return {
    'metrics': _metricas(d.cuadrosPaciente),
    'segmentos': d.segmentos,
    'fraccion_paciente': d.fraccionPaciente,
    'confianza': d.confianza,
    'separacion_st': d.separacionSt,
    'metodo': job.conHuella ? 'tono_respaldo' : 'tono',
  };
}

so.SpeakerEmbeddingExtractor? _extractorPara(AutoJob job) =>
    job.conHuella ? abrirExtractor(job.modeloHuella!) : null;

/// Sesión completa desde archivo (recuperación / respaldo).
Map<String, dynamic> analizarSesionAuto(AutoJob job, {void Function(double)? progreso}) {
  final ex = _extractorPara(job);
  final f = File(job.wavPath).openSync();
  try {
    final a = AnalizadorStream(configAuto(job), extractor: ex);
    final total = math.max(0, (f.lengthSync() - _cabecera) ~/ 2);
    var pos = 0;
    while (pos < total) {
      final n = math.min(_tramoLectura, total - pos);
      a.agregar(leerRango(f, pos, n));
      pos += n;
      progreso?.call(total == 0 ? 1 : pos / total);
    }
    a.terminar();
    return resultadoDe(a, job);
  } finally {
    f.closeSync();
    ex?.free();
  }
}

/// Perfil de la voz del fonoaudiólogo/a desde una grabación corta: altura
/// tonal + huella vocal (si se pasa el modelo). Mismo flujo que la sesión,
/// para que la huella de "Mi voz" sea comparable con la de cada tramo.
Map<String, dynamic>? analizarPerfilVoz(String wavPath, {String? modeloHuella}) {
  final ex = modeloHuella == null ? null : abrirExtractor(modeloHuella);
  final f = File(wavPath).openSync();
  try {
    final a = AnalizadorStream(const YinConfig(minHz: 60, maxHz: 600), extractor: ex);
    final total = math.max(0, (f.lengthSync() - _cabecera) ~/ 2);
    var pos = 0;
    while (pos < total) {
      final n = math.min(_tramoLectura, total - pos);
      a.agregar(leerRango(f, pos, n));
      pos += n;
    }
    a.terminar();
    final p = perfilDesdeCuadros(a.cuadros);
    if (p == null) return null;
    return {
      'mediana_hz': p.medianaHz,
      'sd_st': p.sdSt,
      if (a.huellas.isNotEmpty) 'huella': centro(a.huellas.values),
    };
  } finally {
    f.closeSync();
    ex?.free();
  }
}

// ─── Isolates ───────────────────────────────────────────────────────────────
// Entradas de nivel superior: el mensaje no arrastra el contexto del llamador
// (una pantalla no se puede enviar a otro isolate).

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

void _entradaEnVivo((SendPort, AutoJob) m) {
  final (puerto, job) = m;
  final rp = ReceivePort();
  puerto.send(rp.sendPort);
  final ex = _extractorPara(job);
  final a = AnalizadorStream(configAuto(job), extractor: ex);
  var resto = Uint8List(0); // byte suelto entre fragmentos
  rp.listen((msg) {
    try {
      if (msg is TransferableTypedData) {
        var bytes = msg.materialize().asUint8List();
        if (resto.isNotEmpty) {
          bytes = Uint8List.fromList([...resto, ...bytes]);
          resto = Uint8List(0);
        }
        if (bytes.length.isOdd) {
          resto = Uint8List.fromList([bytes.last]);
          bytes = Uint8List.sublistView(bytes, 0, bytes.length - 1);
        }
        a.agregar(pcm16AFloat(bytes));
      } else if (msg == 'fin') {
        a.terminar();
        puerto.send({'ok': resultadoDe(a, job)});
        ex?.free();
        rp.close();
      } else if (msg == 'cancelar') {
        ex?.free();
        rp.close();
      }
    } catch (e) {
      puerto.send({'error': '$e'});
      ex?.free();
      rp.close();
    }
  });
}

/// Análisis EN VIVO durante la grabación: [agregar] con cada fragmento PCM16
/// del micrófono; [terminar] devuelve el resultado en 1-2 s.
class AnalisisEnVivo {
  final ReceivePort _rp;
  final Completer<SendPort> _puerto = Completer();
  final Completer<Map<String, dynamic>> _resultado = Completer();

  AnalisisEnVivo._(this._rp) {
    _rp.listen((msg) {
      if (msg is SendPort) {
        _puerto.complete(msg);
      } else if (msg is Map && !_resultado.isCompleted) {
        if (msg['error'] != null) {
          _resultado.completeError(Exception(msg['error']));
        } else {
          _resultado.complete(Map<String, dynamic>.from(msg['ok'] as Map));
        }
        _rp.close();
      }
    });
  }

  static Future<AnalisisEnVivo> iniciar(AutoJob job) async {
    final v = AnalisisEnVivo._(ReceivePort());
    await Isolate.spawn<(SendPort, AutoJob)>(_entradaEnVivo, (v._rp.sendPort, job));
    return v;
  }

  /// Los fragmentos se encolan en orden aunque el isolate todavía no respondió.
  void agregar(Uint8List pcm16) {
    final datos = TransferableTypedData.fromList([pcm16]);
    _puerto.future.then((p) => p.send(datos));
  }

  Future<Map<String, dynamic>> terminar() async {
    (await _puerto.future).send('fin');
    return _resultado.future.timeout(const Duration(minutes: 2));
  }

  void cancelar() {
    _puerto.future.then((p) => p.send('cancelar'));
  }
}
