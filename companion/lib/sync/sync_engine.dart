import 'dart:async';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';

import '../config.dart';
import '../data/session_store.dart';
import 'api_client.dart';
import 'tus_client.dart';

/// Motor de sincronización. Orden estricto del contrato:
/// health → sessions → uploads → TUS → confirm → seguimiento.
/// SYNCED solo con `processed` del servidor. Reintentos con backoff.
/// No borra nada local: la retención la decide la UI (processed + N días).
class SyncEngine {
  final CompanionApi api;
  final TusGateway tus;
  final SessionStore store;
  final Future<String?> Function() leerToken;
  final Future<bool> Function()? hayRed;

  SyncEngine({
    required this.api,
    required this.tus,
    required this.store,
    required this.leerToken,
    this.hayRed,
  });

  Future<T> _conBackoff<T>(Future<T> Function() fn, {String? paso}) async {
    Object? last;
    for (var i = 0; i <= AppConfig.backoffSeconds.length; i++) {
      try {
        return await fn();
      } catch (e) {
        last = e;
        if (e is ApiException && e.status >= 400 && e.status < 500 && e.status != 409) {
          rethrow; // 4xx (salvo 409) no se reintenta
        }
        if (i < AppConfig.backoffSeconds.length) {
          await Future.delayed(Duration(seconds: AppConfig.backoffSeconds[i]));
        }
      }
    }
    throw last ?? Exception('Fallo en $paso');
  }

  Future<bool> _wifiOk(bool wifiOnly) async {
    if (!wifiOnly) return true;
    try {
      if (hayRed != null) return await hayRed!();
      final res = await Connectivity().checkConnectivity();
      return res.contains(ConnectivityResult.wifi) ||
          res.contains(ConnectivityResult.ethernet);
    } catch (_) {
      return true; // ante la duda, intentar igual
    }
  }

  /// Sincroniza una sesión lista. [assets]: {audioPath, audioMime,
  /// clips:[{task,path,mime}], wifiOnly}.
  Future<void> sincronizar(String deviceSessionId, Map<String, dynamic> assets) async {
    final wifiOnly = assets['wifiOnly'] as bool? ?? AppConfig.wifiOnlyDefault;
    if (!await _wifiOk(wifiOnly)) {
      throw const SyncPendiente('Sin Wi-Fi (configurado solo Wi-Fi)');
    }
    final token = await leerToken();
    if (token == null || token.isEmpty) {
      throw const SyncPendiente('Sin emparejar');
    }
    final payload = await store.payloadParaServidor(deviceSessionId);
    try {
      // 1. Despertar + crear/actualizar sesión (idempotente).
      await store.estado(deviceSessionId, 'uploading');
      await _conBackoff(() => api.health(), paso: 'health');
      final created = await _conBackoff(
          () => api.postSessions(payload), paso: 'sessions');
      final serverId = '${created['session_id'] ?? ''}';
      if (serverId.isNotEmpty) {
        await store.guardarServidor(deviceSessionId, serverId);
      }

      // 2. Audio principal por TUS.
      await _subirArchivo(
        deviceSessionId: deviceSessionId,
        kind: 'session_audio',
        path: assets['audioPath'] as String,
        mime: assets['audioMime'] as String? ?? 'audio/mp4',
      );
      // 3. Clips WAV.
      for (final c in (assets['clips'] as List? ?? [])) {
        await _subirArchivo(
          deviceSessionId: deviceSessionId,
          kind: 'clip',
          task: c['task'] as String?,
          path: c['path'] as String,
          mime: c['mime'] as String? ?? 'audio/wav',
        );
      }
      // 4. Confirmar → el servidor encola el procesamiento.
      await _conBackoff(
          () => api.confirmUpload({'device_session_id': deviceSessionId, 'kind': 'session_audio'}),
          paso: 'confirm');
      await store.estado(deviceSessionId, 'watching');
      // 5. Seguimiento hasta processed/error (máx. 30 min).
      await _esperarProcesado(deviceSessionId, serverId);
    } on ApiException catch (e) {
      if (e.needsAction) {
        await store.estado(deviceSessionId, 'error',
            error: 'ACCION_REQUERIDA: ${e.message}');
      } else {
        await store.estado(deviceSessionId, 'error', error: e.message);
      }
      rethrow;
    } catch (e) {
      await store.estado(deviceSessionId, 'error', error: '$e');
      rethrow;
    }
  }

  Future<void> _subirArchivo({
    required String deviceSessionId,
    required String kind,
    String? task,
    required String path,
    required String mime,
  }) async {
    final file = File(path);
    final size = await file.length();
    if (size > AppConfig.maxUploadBytes) {
      throw ApiException(413, 'Archivo supera 45 MB: $path');
    }
    final up = await _conBackoff(
        () => api.postUploads({
              'device_session_id': deviceSessionId,
              'kind': kind,
              if (task != null) 'task_type': task,
              'mime': mime,
              'size_bytes': size,
            }),
        paso: 'uploads');
    final uploadUrl = '${up['upload_url']}';
    final token = await leerToken() ?? '';
    final loc = await _conBackoff(
        () => tus.create(uploadUrl, size, path.split('/').last),
        paso: 'tus-create');
    var off = 0;
    try {
      off = await tus.offset(loc, bearerToken: token);
    } catch (_) {
      off = 0; // el servidor no conserva offset: empezar de cero
    }
    await tus.uploadFile(loc, file, offset: off, bearerToken: token);
    if (kind == 'clip') {
      await _conBackoff(
          () => api.confirmUpload({
                'device_session_id': deviceSessionId,
                'kind': 'clip',
                'task_type': task,
              }),
          paso: 'confirm-clip');
    }
  }

  Future<void> _esperarProcesado(String deviceSessionId, String serverId) async {
    final limite = DateTime.now().add(Duration(minutes: AppConfig.pollMinutesMax));
    var espera = 5;
    while (DateTime.now().isBefore(limite)) {
      await Future.delayed(Duration(seconds: espera));
      espera = ((espera * 2).clamp(5, 60)).toInt();
      final d = await _conBackoff(() => api.getSession(serverId), paso: 'poll');
      final st = (d['status'] ?? d['sesion']?['status'] ?? '').toString();
      if (st == 'processed') {
        await store.estado(deviceSessionId, 'synced');
        return;
      }
      if (st == 'error') {
        final det = (d['error_detail'] ?? d['sesion']?['error_detail'] ?? 'error remoto').toString();
        await store.estado(deviceSessionId, 'error', error: det);
        throw Exception('Servidor: $det');
      }
    }
    await store.estado(deviceSessionId, 'watching',
        error: 'Sigue en proceso; se reintentará el seguimiento');
  }

  /// Reproceso tras corregir (ej. consentimiento): reenvía metadata con
  /// consent_recorded=true y confirma con reprocesar:true.
  Future<void> reprocesarConConsentimiento(
      String deviceSessionId, Map<String, dynamic> payload) async {
    final p = Map<String, dynamic>.from(payload)..['consent_recorded'] = true;
    await _conBackoff(() => api.postSessions(p), paso: 'sessions');
    await _conBackoff(
        () => api.confirmUpload(
            {'device_session_id': deviceSessionId, 'kind': 'session_audio', 'reprocesar': true}),
        paso: 'confirm');
    await store.estado(deviceSessionId, 'watching');
    final fila = await store.leer(deviceSessionId);
    final serverId = '${fila?['server_session_id'] ?? ''}';
    if (serverId.isNotEmpty) {
      await _esperarProcesado(deviceSessionId, serverId);
    }
  }
}

class SyncPendiente implements Exception {
  final String message;
  const SyncPendiente(this.message);
  @override
  String toString() => 'SyncPendiente: $message';
}
