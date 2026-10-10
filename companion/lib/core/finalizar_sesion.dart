import 'dart:convert';
import 'dart:io';

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

/// Finaliza una sesión: une bloques → separa automáticamente paciente /
/// fonoaudiólogo/a por perfil de voz y mide la altura tonal del paciente
/// (isolate, lectura por tramos, con avance) → cifra en reposo. Los bloques
/// planos se borran solo después de verificar el `.enc`. La usan Detener y
/// la recuperación tras un cierre forzado.
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
  await store.actualizar(dsid, {'audio_duration_sec': duracion});

  final res = await analizarSesionAutoEnIsolate(
    AutoJob(
      wavPath: plano,
      sexoReferencia: sexoReferencia,
      fonoMedianaHz: vozFonoHz,
      fonoSdSt: vozFonoSdSt,
      rangoMinHz: rangoMinHz,
      rangoMaxHz: rangoMaxHz,
    ),
    onProgreso ?? (_) {},
  );
  final segmentos = [
    for (final s in (res['segmentos'] as List)) Map<String, dynamic>.from(s as Map),
  ];
  if (segmentos.isEmpty) {
    segmentos.add({
      'task_type': 'conversacion_espontanea', 'speaker': 'paciente',
      'start_sec': 0.0, 'end_sec': duracion,
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
    },
  }),);

  // Cifrado en reposo del audio completo; luego se borran los planos.
  if (!yaCifrado) await vault.cifrarArchivo(wavPath);
  if (plano != wavPath) await File(plano).delete();
  if (await dirBloques.exists()) await dirBloques.delete(recursive: true);
  await store.actualizar(dsid, {'status': 'queued', 'finalized': 1});
}
