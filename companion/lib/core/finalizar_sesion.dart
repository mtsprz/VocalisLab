import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path/path.dart' as p;

import '../config.dart';
import '../data/audio_vault.dart';
import '../data/session_store.dart';
import 'audio/wav.dart';
import 'dsp/dsp_isolate.dart';

/// Resultado del análisis automático (solo local): métricas del paciente +
/// datos de la separación de voces (confianza, % de tiempo del paciente).
const archivoTonoGlobal = 'tono_global.json';

/// device_session_id que se está grabando ahora (no ofrecer "recuperar").
String? sesionEnCurso;

/// Sesiones que se están completando en segundo plano (unión de bloques +
/// cifrado): no se ofrecen para "recuperar" ni se sincronizan todavía.
final Set<String> sesionesEnSegundoPlano = {};

/// Segundos de audio en los bloques de una sesión (por tamaño de archivo:
/// sirve aunque las cabeceras no se hayan parchado).
Future<double> duracionBloques(String sesDir) async {
  final d = Directory(p.join(sesDir, 'bloques'));
  if (!await d.exists()) return 0;
  var bytes = 0;
  await for (final e in d.list()) {
    if (e is File && e.path.endsWith('.wav')) {
      final n = await e.length();
      if (n > 44) bytes += n - 44;
    }
  }
  return bytes / 2 / AppConfig.sampleRate;
}

/// Paso 1 (inmediato): guarda segmentos y altura tonal del paciente para
/// mostrar el resumen. [res] = resultado del análisis (en vivo o de archivo).
Future<void> guardarResultado({
  required SessionStore store,
  required String dsid,
  required String sesDir,
  required Map<String, dynamic> res,
  double? duracion,
}) async {
  final dur = duracion ?? await duracionBloques(sesDir);
  await store.actualizar(dsid, {'audio_duration_sec': dur});
  final segmentos = [
    for (final s in (res['segmentos'] as List)) Map<String, dynamic>.from(s as Map),
  ];
  if (segmentos.isEmpty) {
    segmentos.add({
      'task_type': 'conversacion_espontanea', 'speaker': 'paciente',
      'start_sec': 0.0, 'end_sec': dur,
    });
  }
  await store.guardarSegmentos(dsid, segmentos);
  final metricas = Map<String, dynamic>.from(res['metrics'] as Map);
  await store.guardarAcustica(dsid, 'conversacion_espontanea', metricas);
  await File(p.join(sesDir, archivoTonoGlobal)).writeAsString(jsonEncode({
    ...metricas,
    'diarizacion': {
      'confianza': res['confianza'],
      'fraccion_paciente': res['fraccion_paciente'],
      'separacion_st': res['separacion_st'],
      'similitud_voces': res['similitud_voces'],
      'metodo': res['metodo'],
    },
  }),);
}

/// Paso 2 (segundo plano): une los bloques, cifra el audio en reposo y borra
/// los planos (solo después de verificar el `.enc`). Recién ahí la sesión
/// queda en cola para sincronizar. Si la app muere en el medio, los bloques
/// siguen en disco y la sesión aparece como "interrumpida" para recuperar.
Future<void> completarAudio({
  required SessionStore store,
  required AudioVault vault,
  required String dsid,
  required String sesDir,
}) async {
  sesionesEnSegundoPlano.add(dsid);
  try {
    final dirBloques = Directory(p.join(sesDir, 'bloques'));
    final wavPath = p.join(sesDir, 'sesion.wav');
    if (!await File('$wavPath${AudioVault.extension}').exists()) {
      final bloques = await recuperarBloques(dirBloques);
      if (bloques.isEmpty) throw Exception('No quedó audio grabado');
      await concatenarBloques(bloques, wavPath);
      await vault.cifrarArchivo(wavPath);
    }
    if (await dirBloques.exists()) await dirBloques.delete(recursive: true);
    await store.actualizar(dsid, {'status': 'queued', 'finalized': 1});
  } finally {
    sesionesEnSegundoPlano.remove(dsid);
  }
}

/// Finaliza desde archivo (recuperación tras cierre forzado o si falló el
/// análisis en vivo): analiza el WAV (decimado, rápido) y completa el audio.
Future<void> finalizarSesion({
  required SessionStore store,
  required AudioVault vault,
  required String dsid,
  required String sesDir,
  required String sexoReferencia,
  double? vozFonoHz,
  double? vozFonoSdSt,
  double? rangoMinHz,
  double? rangoMaxHz,
  String? modeloHuella,
  Float32List? huellaFono,
  void Function(double)? onProgreso,
}) async {
  final dirBloques = Directory(p.join(sesDir, 'bloques'));
  final wavPath = p.join(sesDir, 'sesion.wav');
  final yaCifrado = await File('$wavPath${AudioVault.extension}').exists();
  if (!yaCifrado) {
    final bloques = await recuperarBloques(dirBloques);
    if (bloques.isEmpty) throw Exception('No quedó audio grabado');
    await concatenarBloques(bloques, wavPath);
  }
  final plano = yaCifrado
      ? await vault.descifrarA('$wavPath${AudioVault.extension}',
          tmpDir: p.join(sesDir, 'tmp'),)
      : wavPath;
  final bytes = await File(plano).length();
  final duracion = bytes <= 44 ? 0.0 : (bytes - 44) / 2 / AppConfig.sampleRate;
  final res = await analizarSesionAutoEnIsolate(
    AutoJob(
      wavPath: plano,
      sexoReferencia: sexoReferencia,
      fonoMedianaHz: vozFonoHz,
      fonoSdSt: vozFonoSdSt,
      rangoMinHz: rangoMinHz,
      rangoMaxHz: rangoMaxHz,
      modeloHuella: modeloHuella,
      huellaFono: huellaFono,
    ),
    onProgreso ?? (_) {},
  );
  await guardarResultado(store: store, dsid: dsid, sesDir: sesDir, res: res, duracion: duracion);
  if (!yaCifrado) await vault.cifrarArchivo(wavPath);
  if (plano != wavPath) await File(plano).delete();
  if (await dirBloques.exists()) await dirBloques.delete(recursive: true);
  await store.actualizar(dsid, {'status': 'queued', 'finalized': 1});
}
