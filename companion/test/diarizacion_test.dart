import 'dart:io';
import 'dart:isolate';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:vocalis_companion/core/audio/wav.dart';
import 'package:vocalis_companion/core/dsp/diarizacion.dart';
import 'package:vocalis_companion/core/dsp/dsp_isolate.dart';
import 'package:vocalis_companion/core/dsp/yin.dart';

/// WAV con tramos de tono (vibrato leve para parecer voz): [(segundos, Hz)].
Future<String> _wav(Directory dir, List<(double, double)> tramos, {String nombre = 's.wav'}) async {
  const sr = 44100;
  final path = p.join(dir.path, nombre);
  final w = WavBlockWriter(path);
  await w.open();
  var fase = 0.0;
  for (final (seg, hz) in tramos) {
    final n = (seg * sr).round();
    final bd = ByteData(n * 2);
    for (var i = 0; i < n; i++) {
      final f = hz <= 0 ? 0.0 : hz * (1 + 0.01 * math.sin(2 * math.pi * 5 * i / sr));
      fase += 2 * math.pi * f / sr;
      final v = hz <= 0 ? 0.0 : 0.4 * math.sin(fase);
      bd.setInt16(i * 2, (v * 32767).round(), Endian.little);
    }
    await w.appendBytes(bd.buffer.asUint8List());
  }
  await w.close();
  return path;
}

void main() {
  late Directory dir;
  setUp(() async => dir = await Directory.systemTemp.createTemp('diar'));
  tearDown(() async => dir.delete(recursive: true));

  test('perfil "Mi voz" desde una grabación corta', () async {
    final wav = await _wav(dir, [(3, 210)]);
    final perfil = analizarPerfilVoz(wav)!;
    expect(((perfil['mediana_hz'] as double) - 210).abs() < 3, true);
    expect((perfil['sd_st'] as double) < 0.5, true);
  });

  test('separa fono (200 Hz) y paciente (120 Hz) y mide solo al paciente', () async {
    final wav = await _wav(dir, [(5, 200), (7, 120), (3, 200)]);
    final r = analizarSesionAuto(const AutoJob(
      wavPath: '',
      sexoReferencia: 'masculino',
    ).copiaCon(wav), );
    final m = r['metrics'] as Map<String, dynamic>;
    expect(((m['f0_median_hz'] as double) - 120).abs() < 2, true, reason: 'mediana=${m['f0_median_hz']}');
    expect((m['f0_max_hz'] as double) < 160, true, reason: 'no debe incluir la voz del fono');
    final segs = (r['segmentos'] as List).cast<Map<String, dynamic>>();
    expect(segs.map((s) => s['speaker']).toList(), ['fonoaudiologo', 'paciente', 'fonoaudiologo']);
    expect(((segs[1]['start_sec'] as double) - 5).abs() <= 0.5, true);
    expect(((segs[1]['end_sec'] as double) - 12).abs() <= 0.5, true);
    expect(r['confianza'], 'alta');
    expect(((r['fraccion_paciente'] as double) - 7 / 15).abs() < 0.05, true);
  });

  test('por isolate, con avance que referencia algo no enviable (como una pantalla)', () async {
    final noEnviable = ReceivePort(); // un ReceivePort no se puede mandar a otro isolate
    final avances = <double>[];
    final wav = await _wav(dir, [(5, 200), (7, 120)]);
    final perfil = await analizarPerfilVozEnIsolate(await _wav(dir, [(3, 200)], nombre: 'voz.wav'));
    expect(perfil, isNotNull);
    final r = await analizarSesionAutoEnIsolate(
      AutoJob(
        wavPath: wav,
        sexoReferencia: 'masculino',
        fonoMedianaHz: perfil!['mediana_hz'] as double,
        fonoSdSt: perfil['sd_st'] as double,
        rangoMinHz: 100,
        rangoMaxHz: 130,
      ),
      (v) {
        noEnviable.hashCode; // la función captura el objeto no enviable
        avances.add(v);
      },
    );
    noEnviable.close();
    expect(avances, isNotEmpty);
    expect((r['metrics'] as Map)['f0_median_hz'], closeTo(120, 2));
  });

  test('sin rango de referencia: estima al paciente con lo que no es la voz del fono', () {
    final cuadros = [
      for (var i = 0; i < 400; i++) const YinFrame(200, 0.9, 0.1),
      for (var i = 0; i < 600; i++) const YinFrame(300, 0.9, 0.1),
    ];
    final d = diarizar(cuadros, fono: const PerfilVoz(200, 0.5));
    expect(d.segmentos.map((s) => s['speaker']).toList(), ['fonoaudiologo', 'paciente']);
    expect(d.cuadrosPaciente.length, 600);
  });

  test('sin perfil de voz: todo es paciente y se avisa', () {
    final d = diarizar(List.filled(300, const YinFrame(150, 0.9, 0.1)));
    expect(d.confianza, 'sin_perfil');
    expect(d.segmentos.single['speaker'], 'paciente');
  });

  test('voces parecidas → confianza baja', () {
    final d = diarizar(
      [for (var i = 0; i < 500; i++) const YinFrame(200, 0.9, 0.1)],
      fono: const PerfilVoz(205, 1.0),
      rangoMinHz: 190,
      rangoMaxHz: 225,
    );
    expect(d.confianza, 'baja');
  });

  test('tramos cortos (< 1 s) no generan cambios de hablante', () {
    final cuadros = [
      for (var i = 0; i < 300; i++) const YinFrame(120, 0.9, 0.1),
      for (var i = 0; i < 40; i++) const YinFrame(200, 0.9, 0.1), // 0,4 s
      for (var i = 0; i < 300; i++) const YinFrame(120, 0.9, 0.1),
    ];
    final d = diarizar(cuadros, fono: const PerfilVoz(200, 0.5), rangoMinHz: 100, rangoMaxHz: 130);
    expect(d.segmentos.length, 1);
    expect(d.segmentos.single['speaker'], 'paciente');
  });
}

extension on AutoJob {
  AutoJob copiaCon(String wav) => AutoJob(
        wavPath: wav,
        sexoReferencia: sexoReferencia,
        fonoMedianaHz: 200,
        fonoSdSt: 0.5,
        rangoMinHz: 100,
        rangoMaxHz: 130,
      );
}
