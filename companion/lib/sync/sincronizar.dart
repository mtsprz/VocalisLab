import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../app.dart';
import '../config.dart';
import '../core/audio/compressor.dart';
import '../core/finalizar_sesion.dart' show sesionEnCurso, sesionesEnSegundoPlano;
import '../data/audio_vault.dart';
import '../data/settings_store.dart';
import 'sync_engine.dart';

/// Sincronización automática (sin pasar por la pestaña Sincronizar), como un
/// grabador de reuniones: al terminar de grabar o importar, la sesión sube
/// sola apenas hay conexión. Una sesión nunca se sube dos veces a la vez.
final Set<String> _enCurso = {};

/// Avisa a la pestaña Sincronizar que cambió algún estado.
final ValueNotifier<int> cambiosSync = ValueNotifier(0);

/// Tipos de archivo que se pueden importar.
const extensionesImportables = ['m4a', 'mp3', 'wav', 'ogg', 'opus', 'webm', 'aac', 'mp4'];

String mimeDe(String ruta) => switch (p.extension(ruta).toLowerCase().replaceFirst('.', '')) {
      'm4a' || 'mp4' => 'audio/mp4',
      'mp3' => 'audio/mpeg',
      'wav' => 'audio/wav',
      'ogg' || 'opus' => 'audio/ogg',
      'webm' => 'audio/webm',
      'aac' => 'audio/aac',
      _ => 'audio/mp4',
    };

Future<String> _dirSesion(String dsid) async =>
    p.join((await getApplicationDocumentsDirectory()).path, 'sesiones', dsid);

Future<String> _tmpDir(String dsid) async =>
    p.join((await getTemporaryDirectory()).path, 'vocalis_tmp', dsid);

Map<String, dynamic> _info(Map<String, dynamic> fila) {
  try {
    return Map<String, dynamic>.from(jsonDecode('${fila['device_info'] ?? '{}'}') as Map);
  } catch (_) {
    return {};
  }
}

/// m4a ~48 kbps listo para subir (copia descifrada en [tmp]). Si aún no
/// existe, comprime desde el WAV y guarda el m4a cifrado (.enc).
Future<String> rutaComprimida(Deps deps, String dsid, String tmp) async {
  final dir = await _dirSesion(dsid);
  final vault = deps.vault;
  final m4a = await rutaPlana(vault, p.join(dir, 'sesion.m4a'), tmpDir: tmp);
  if (m4a != null) return m4a;
  final wav = await rutaPlana(vault, p.join(dir, 'sesion.wav'), tmpDir: tmp);
  if (wav == null) throw Exception('Falta el audio local de la sesión');
  final destino = p.join(dir, 'sesion.m4a');
  await AudioCompressor.platform().compressToM4a(
    wavPath: wav,
    outPath: destino,
    bitrateKbps: AppConfig.aacBitrate ~/ 1000,
  );
  await vault.cifrarArchivo(destino);
  return (await rutaPlana(vault, destino, tmpDir: tmp))!;
}

Future<List<Map<String, dynamic>>> _clipsParaSubir(Deps deps, String dsid, String tmp) async {
  final clips = await deps.store.clips(dsid);
  return [
    for (final c in clips)
      if (await rutaPlana(deps.vault, '${c['path']}', tmpDir: tmp) case final ruta?)
        {'task': '${c['task_type']}', 'path': ruta, 'mime': 'audio/wav'},
  ];
}

/// Sube una sesión (grabada o importada). Lanza el error para quien quiera
/// mostrarlo; [SyncPendiente] = sin Wi-Fi o sin vincular (queda en cola).
Future<void> sincronizarSesion(Deps deps, String dsid) async {
  if (dsid == sesionEnCurso || sesionesEnSegundoPlano.contains(dsid)) return;
  if (!_enCurso.add(dsid)) return;
  final tmp = await _tmpDir(dsid);
  try {
    final fila = await deps.store.leer(dsid);
    if (fila == null) return;
    final ajustes = await AppSettings.load();
    if ('${fila['audio_codec']}' == 'importado') {
      final info = _info(fila);
      final ruta = await rutaPlana(deps.vault, '${info['archivo_local']}', tmpDir: tmp);
      if (ruta == null) throw Exception('Falta el archivo importado en el dispositivo');
      await deps.sync.sincronizarImportada(
        dsid,
        crear: () => deps.api.crearImportacion({
          'device_session_id': dsid,
          'patient_id': fila['patient_id'],
          'recorded_at': fila['recorded_at'],
          'consent_recorded': (fila['consent_recorded'] ?? 0) == 1,
          'nombre_archivo': info['nombre'] ?? '',
          if (info['fono_mediana_hz'] != null) 'fono_mediana_hz': info['fono_mediana_hz'],
        }),
        audioPath: ruta,
        audioMime: mimeDe(ruta),
        wifiOnly: ajustes.wifiOnly,
      );
    } else {
      await deps.sync.sincronizar(dsid, {
        'audioPath': await rutaComprimida(deps, dsid, tmp),
        'audioMime': 'audio/mp4',
        'clips': await _clipsParaSubir(deps, dsid, tmp),
        'wifiOnly': ajustes.wifiOnly,
      });
    }
  } finally {
    _enCurso.remove(dsid);
    cambiosSync.value++;
    try {
      // Solo copias descifradas temporales; el audio cifrado queda.
      await Directory(tmp).delete(recursive: true);
    } catch (_) {}
  }
}

/// Sincroniza todo lo pendiente. Devuelve (ok, con error, último error).
Future<(int, int, String?)> sincronizarPendientes(Deps deps) async {
  var ok = 0, fail = 0;
  String? ultimo;
  for (final s in await deps.store.pendientes()) {
    try {
      await sincronizarSesion(deps, '${s['device_session_id']}');
      ok++;
    } catch (e) {
      fail++;
      ultimo = e is SyncPendiente ? e.message : '$e';
    }
  }
  return (ok, fail, ultimo);
}

/// Auto: no muestra errores (la pestaña Sincronizar los lista).
void sincronizarEnFondo(Deps deps, [String? dsid]) {
  Future<void> correr() async {
    try {
      if (dsid == null) {
        await sincronizarPendientes(deps);
      } else {
        await sincronizarSesion(deps, dsid);
      }
    } catch (_) {}
  }

  unawaited(correr());
}

/// Importa un archivo de audio de otra grabadora (p. ej. la Grabadora de voz
/// de Windows): lo guarda cifrado en el dispositivo, crea la sesión local y
/// la sube. El análisis lo hace el servidor (Praat + separación de voces).
Future<String> importarArchivo(
  Deps deps, {
  required String origen,
  required String pacienteId,
  required bool consentimiento,
  DateTime? grabadoEl,
}) async {
  final f = File(origen);
  if (!await f.exists()) throw Exception('No se encontró el archivo');
  final ext = p.extension(origen).toLowerCase();
  final ahora = DateTime.now();
  final dsid = 'imp-${ahora.millisecondsSinceEpoch}-${const Uuid().v4().substring(0, 6)}';
  final dir = await _dirSesion(dsid);
  await Directory(dir).create(recursive: true);
  var destino = p.join(dir, 'importado$ext');
  final tam = await f.length();
  if (tam > AppConfig.maxUploadBytes) {
    // Archivos grandes (WAV sin comprimir): a AAC antes de subir.
    final m4a = p.join(dir, 'importado.m4a');
    try {
      await AudioCompressor.platform().compressToM4a(
          wavPath: origen, outPath: m4a, bitrateKbps: AppConfig.aacBitrate ~/ 1000,);
    } catch (e) {
      await Directory(dir).delete(recursive: true);
      throw Exception('El archivo pesa ${(tam / 1048576).round()} MB (máx. 45 MB) y no se pudo '
          'comprimir: $e');
    }
    destino = m4a;
  } else {
    await f.copy(destino);
  }
  await deps.vault.cifrarArchivo(destino);
  final ajustes = await AppSettings.load();
  final fecha = (grabadoEl ?? await f.lastModified()).toIso8601String();
  await deps.store.crear({
    'device_session_id': dsid,
    'patient_id': pacienteId,
    'recorded_at': fecha,
    'audio_codec': 'importado',
    'dsp_version': 'servidor-praat/1.0',
    'device_info': jsonEncode({
      'origen': 'importado',
      'nombre': p.basename(origen),
      'archivo_local': destino,
      if (ajustes.vozFonoHz != null) 'fono_mediana_hz': ajustes.vozFonoHz,
    }),
    'consent_recorded': consentimiento ? 1 : 0,
    'status': 'queued',
    'finalized': 1,
    'created_at': ahora.toIso8601String(),
  });
  cambiosSync.value++;
  sincronizarEnFondo(deps, dsid);
  return dsid;
}
