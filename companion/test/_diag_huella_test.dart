import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:vocalis_companion/core/audio/wav.dart';
import 'package:vocalis_companion/core/dsp/diarizacion_huella.dart';
import 'package:vocalis_companion/core/dsp/dsp_isolate.dart';
import 'package:vocalis_companion/core/dsp/huella.dart';

const _modelo = 'assets/models/campplus_sv_16k.onnx';

Float32List _ruido(Float32List base, double sigma, math.Random r) {
  final out = Float32List(base.length);
  for (var i = 0; i < base.length; i++) {
    out[i] = base[i] + sigma * (r.nextDouble() * 2 - 1);
  }
  return out;
}

/// Voz sintética: tren glótico a [f0] Hz (con jitter leve) filtrado por 3
/// formantes [fs] (resonadores de 2º orden). Mismo f0 + distintos formantes
/// = mismo tono, distinto timbre (como dos personas de igual altura tonal).
Float64List _voz(double f0, List<double> fs, double seg, math.Random r) {
  const sr = 44100;
  final n = (seg * sr).round();
  var x = Float64List(n);
  var fase = 0.0;
  for (var i = 0; i < n; i++) {
    fase += f0 * (1 + 0.004 * (r.nextDouble() - 0.5)) / sr;
    if (fase >= 1) fase -= 1;
    x[i] = fase < 0.4 ? math.sin(math.pi * fase / 0.4) : 0.0; // pulso glótico
  }
  for (final fc in fs) {
    const bw = 90.0;
    final rr = math.exp(-math.pi * bw / sr);
    final a1 = -2 * rr * math.cos(2 * math.pi * fc / sr), a2 = rr * rr;
    final y = Float64List(n);
    for (var i = 0; i < n; i++) {
      y[i] = x[i] - a1 * (i > 0 ? y[i - 1] : 0) - a2 * (i > 1 ? y[i - 2] : 0);
    }
    x = y;
  }
  var mx = 0.0;
  for (final v in x) {
    mx = math.max(mx, v.abs());
  }
  return Float64List.fromList([for (final v in x) 0.4 * v / mx]);
}

Future<String> _wav(Directory dir, List<Float64List> partes, String nombre) async {
  final path = p.join(dir.path, nombre);
  final w = WavBlockWriter(path);
  await w.open();
  for (final x in partes) {
    final bd = ByteData(x.length * 2);
    for (var i = 0; i < x.length; i++) {
      bd.setInt16(i * 2, (x[i] * 32767).round(), Endian.little);
    }
    await w.appendBytes(bd.buffer.asUint8List());
  }
  await w.close();
  return path;
}

void mainOriginal() {
  group('agrupamiento por huella (Dart puro)', () {
    final r = math.Random(7);
    Float32List base(int semilla) {
      final rr = math.Random(semilla);
      return normalizar(Float32List.fromList(List.generate(192, (_) => rr.nextDouble() * 2 - 1)));
    }

    test('dos voces distintas: separa y confianza alta', () {
      final fono = base(1), pac = base(2);
      final tramos = [
        for (var i = 0; i < 20; i++) _ruido(fono, 0.05, r),
        for (var i = 0; i < 30; i++) _ruido(pac, 0.05, r),
        for (var i = 0; i < 10; i++) _ruido(fono, 0.05, r),
      ];
      final a = asignarPorHuella(tramos, fono);
      final esperado = [...List.filled(20, false), ...List.filled(30, true), ...List.filled(10, false)];
      final aciertos = [for (var i = 0; i < tramos.length; i++) a.esPaciente[i] == esperado[i]].where((x) => x).length;
      expect(aciertos, tramos.length);
      expect(a.confianza, 'alta');
    });

    test('voces parecidas (coseno ~0,5): igual separa sin umbral fijo', () {
      final fono = base(1);
      final otra = base(3);
      // Paciente = mezcla: comparte la mitad del "timbre" con el fono.
      final pac = normalizar(Float32List.fromList([for (var i = 0; i < 192; i++) fono[i] + otra[i]]));
      expect(coseno(pac, fono), greaterThan(0.6));
      final tramos = [
        for (var i = 0; i < 25; i++) _ruido(fono, 0.04, r),
        for (var i = 0; i < 25; i++) _ruido(pac, 0.04, r),
      ];
      final a = asignarPorHuella(tramos, fono);
      final aciertos = [
        for (var i = 0; i < 50; i++) a.esPaciente[i] == (i >= 25),
      ].where((x) => x).length;
      expect(aciertos, greaterThanOrEqualTo(48));
    });

    test('una sola voz distinta de "Mi voz" → todo es del paciente', () {
      final fono = base(1), pac = base(2);
      final a = asignarPorHuella([for (var i = 0; i < 10; i++) _ruido(pac, 0.03, r)], fono);
      expect(a.esPaciente.every((x) => x), true);
    });

    test('solo habla el fono → nada se atribuye al paciente', () {
      final fono = base(1);
      final a = asignarPorHuella([for (var i = 0; i < 10; i++) _ruido(fono, 0.03, r)], fono);
      expect(a.esPaciente.every((x) => !x), true);
    });
  });

  group('modelo CAM++ real (sherpa-onnx)', () {
    // En `flutter test` la DLL nativa no está en el PATH (en la app compilada
    // sí): SHERPA_ONNX_DIR = carpeta windows/ del paquete sherpa_onnx_windows.
    final dirNativo = Platform.environment['SHERPA_ONNX_DIR'];
    final extractor =
        File(_modelo).existsSync() ? abrirExtractor(_modelo, dirNativo: dirNativo) : null;
    final sinModelo = extractor == null
        ? 'sherpa-onnx o el modelo no cargan en este entorno de test'
        : null;
    extractor?.free();

    test('mismo tono (100 Hz), distinto timbre: separa al paciente', () async {
      final dir = await Directory.systemTemp.createTemp('huella');
      final r = math.Random(3);
      const fonoF = [730.0, 1090.0, 2440.0];      // tracto vocal "A"
      const pacF = [570.0, 840.0, 2410.0];        // tracto "B" (más largo)
      final voz = await _wav(dir, [_voz(100, fonoF, 12, r)], 'mi_voz.wav');
      final perfil = analizarPerfilVoz(voz, modeloHuella: _modelo)!;
      expect(perfil['huella'], isA<Float32List>());
      final ses = await _wav(dir, [
        _voz(100, fonoF, 9, r), _voz(100, pacF, 15, r), _voz(100, fonoF, 6, r),
      ], 'sesion.wav',);
      final res = analizarSesionAuto(AutoJob(
        wavPath: ses,
        sexoReferencia: 'masculino',
        fonoMedianaHz: perfil['mediana_hz'] as double,
        fonoSdSt: perfil['sd_st'] as double,
        modeloHuella: _modelo,
        huellaFono: perfil['huella'] as Float32List,
      ),);
      expect(res['metodo'], 'huella');
      final segs = (res['segmentos'] as List).cast<Map<String, dynamic>>();
      final pac = segs.where((s) => s['speaker'] == 'paciente').toList();
      expect(pac, isNotEmpty, reason: 'segmentos=$segs');
      // El tramo del paciente (9-24 s) debe quedar identificado (±1,5 s).
      final ini = pac.map((s) => s['start_sec'] as double).reduce(math.min);
      final fin = pac.map((s) => s['end_sec'] as double).reduce(math.max);
      expect((ini - 9).abs() <= 1.5, true, reason: 'inicio paciente=$ini; $segs');
      expect((fin - 24).abs() <= 1.5, true, reason: 'fin paciente=$fin; $segs');
      await dir.delete(recursive: true);
    }, skip: sinModelo, timeout: const Timeout(Duration(minutes: 5)),);
  });
}

void main() {
  test('diag similitudes', () async {
    final ex = abrirExtractor(_modelo, dirNativo: Platform.environment['SHERPA_ONNX_DIR'])!;
    final r = math.Random(3);
    const fonoF = [730.0, 1090.0, 2440.0];
    const pacF = [570.0, 840.0, 2410.0];
    Float32List h(Float64List x) => huellaDe(ex, Float32List.fromList(x.map((v) => v.toDouble()).toList()), 44100)!;
    final fono = centro([for (var i = 0; i < 6; i++) h(_voz(100, fonoF, 1.5, r))]);
    final sf = [for (var i = 0; i < 6; i++) coseno(h(_voz(100, fonoF, 1.5, r)), fono)];
    final sp = [for (var i = 0; i < 6; i++) coseno(h(_voz(100, pacF, 1.5, r)), fono)];
    final sp2 = [for (var i = 0; i < 6; i++) coseno(h(_voz(130, [850.0, 1220.0, 2810.0], 1.5, r)), fono)];
    print('fono vs fono: ${sf.map((v) => v.toStringAsFixed(3)).join(' ')}');
    print('pac(100Hz otros formantes) vs fono: ${sp.map((v) => v.toStringAsFixed(3)).join(' ')}');
    print('otra voz (130Hz, otros formantes) vs fono: ${sp2.map((v) => v.toStringAsFixed(3)).join(' ')}');
  });
}
