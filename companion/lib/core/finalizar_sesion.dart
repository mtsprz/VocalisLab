import 'dart:convert';
import 'dart:io';
import 'dart:isolate';

import 'package:path/path.dart' as p;

import '../config.dart';
import '../data/audio_vault.dart';
import '../data/session_store.dart';
import 'audio/wav.dart';
import 'dsp/dsp_isolate.dart';

/// Análisis de todos los tramos del paciente juntos (solo local, no se envía).
const archivoTonoGlobal = 'tono_global.json';

/// Marcas persistidas durante la grabación (para recuperar tras cierre forzado).
const archivoMarcas = 'marcas.json';

/// device_session_id que se está grabando ahora (no ofrecer "recuperar").
String? sesionEnCurso;

/// Segmentos para el contrato: las marcas de tareas; si no se marcó ninguna,
/// los turnos de hablante como conversación espontánea (el servidor exige
/// `segments` no vacío y `task_type` válido).
List<Map<String, dynamic>> segmentosFinales(
    List<Map<String, dynamic>> marcas, List<Map<String, dynamic>> turnos,) {
  if (marcas.isNotEmpty) return marcas;
  return [
    for (final t in turnos) {'task_type': 'conversacion_espontanea', ...t},
  ];
}

/// Lee `marcas.json` y cierra la marca/turno abiertos en el último instante
/// guardado. Devuelve los segmentos finales (vacío si no hay archivo).
Future<List<Map<String, dynamic>>> marcasRecuperadas(String sesDir) async {
  final f = File(p.join(sesDir, archivoMarcas));
  if (!await f.exists()) return [];
  try {
    final m = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
    final t = (m['t'] as num?)?.toDouble() ?? 0;
    final marcas = [
      for (final x in (m['marcas'] as List? ?? [])) Map<String, dynamic>.from(x as Map),
    ];
    final turnos = [
      for (final x in (m['turnos'] as List? ?? [])) Map<String, dynamic>.from(x as Map),
    ];
    final ab = m['abierta'] as Map?;
    if (ab != null && t > (ab['inicio'] as num).toDouble()) {
      marcas.add({
        'task_type': ab['task'],
        'speaker': ab['speaker'],
        'start_sec': (ab['inicio'] as num).toDouble(),
        'end_sec': t,
      });
    }
    final it = (m['inicio_turno'] as num?)?.toDouble() ?? 0;
    if (t > it) turnos.add({'speaker': m['speaker'] ?? 'paciente', 'start_sec': it, 'end_sec': t});
    return segmentosFinales(marcas, turnos);
  } catch (_) {
    return [];
  }
}

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

/// Finaliza una sesión: une bloques → mide tono por tarea y global (isolate,
/// solo tramos del paciente) → clip de vocal sostenida → cifra en reposo.
/// Los bloques planos se borran solo después de verificar el `.enc`.
Future<void> finalizarSesion({
  required SessionStore store,
  required AudioVault vault,
  required String dsid,
  required String sesDir,
  required String sexoReferencia,
  required List<Map<String, dynamic>> segmentos,
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
  await store.guardarSegmentos(dsid, segmentos);

  // DSP por tarea. El closure de Isolate.run solo captura valores simples.
  List<Map<String, dynamic>> soloTiempos(Iterable<Map<String, dynamic>> ms) => [
        for (final m in ms)
          {
            'speaker': '${m['speaker']}',
            'start_sec': (m['start_sec'] as num).toDouble(),
            'end_sec': (m['end_sec'] as num).toDouble(),
          },
      ];
  final porTarea = <String, List<Map<String, dynamic>>>{};
  for (final m in segmentos) {
    porTarea.putIfAbsent('${m['task_type']}', () => []).add(m);
  }
  for (final entry in porTarea.entries) {
    final segs = soloTiempos(entry.value);
    final res = await Isolate.run(() => analizarTarea(
        DspJob(wavPath: plano, segments: segs, sexoReferencia: sexoReferencia),),);
    await store.guardarAcustica(
        dsid, entry.key, Map<String, dynamic>.from(res['metrics'] as Map),);
  }
  // Todos los tramos del paciente juntos: métrica principal si no hubo
  // conversación espontánea. Solo local.
  final todos = soloTiempos(segmentos);
  final global = await Isolate.run(() => analizarTarea(
      DspJob(wavPath: plano, segments: todos, sexoReferencia: sexoReferencia),),);
  await File(p.join(sesDir, archivoTonoGlobal)).writeAsString(jsonEncode(global['metrics']));

  // Clip WAV ~10 s de vocal sostenida (revisión auditiva en la ficha).
  final sost = segmentos
      .where((m) => m['task_type'] == 'vocal_sostenida_a' && m['speaker'] == 'paciente')
      .toList();
  final clipPath = p.join(sesDir, 'clip_sostenida.wav');
  if (sost.isNotEmpty && (await store.clips(dsid)).isEmpty) {
    final ini = (sost.first['start_sec'] as num).toDouble();
    final fin = (sost.first['end_sec'] as num).toDouble();
    final segundos = (fin - ini).clamp(0.0, 30.0);
    if (segundos >= 5) {
      final seg10 = segundos.clamp(0.0, 10.0);
      await recortarWav(origen: plano, desdeSec: ini, segundos: seg10, destino: clipPath);
      await vault.cifrarArchivo(clipPath);
      await store.agregarClip(dsid, 'vocal_sostenida_a', clipPath, seg10);
    }
  }

  // Cifrado en reposo del audio completo; luego se borran los planos.
  if (!yaCifrado) await vault.cifrarArchivo(wavPath);
  if (plano != wavPath) await File(plano).delete();
  if (await dirBloques.exists()) await dirBloques.delete(recursive: true);
  await store.actualizar(dsid, {'status': 'queued', 'finalized': 1});
}
