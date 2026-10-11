import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:workmanager/workmanager.dart';

import '../data/audio_vault.dart';
import '../data/db.dart';
import '../data/secure_store.dart';
import '../data/session_store.dart';
import '../data/settings_store.dart';
import 'api_client.dart';
import 'sync_engine.dart';
import 'tus_client.dart';

/// Sincronización en segundo plano (Android workmanager).
/// Solo continúa sesiones con audio ya comprimido (la compresión con
/// MethodChannel no es segura en el isolate de fondo).
@pragma('vm:entry-point')
void tareaFondoDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    try {
      final db = await openAppDb();
      final store = SessionStore(db);
      final secure = SecureStore();
      final settings = await AppSettings.load();
      final engine = SyncEngine(
        api: ApiClient(secure: secure),
        tus: TusClient(),
        store: store,
        leerToken: secure.readDeviceToken,
      );
      final vault = AudioVault(secure.audioKey);
      final docs = await getApplicationDocumentsDirectory();
      final tmpBase = (await getTemporaryDirectory()).path;
      for (final s in await store.pendientes()) {
        final dsid = '${s['device_session_id']}';
        final tmp = p.join(tmpBase, 'vocalis_tmp', 'fondo_$dsid');
        try {
          final m4a = await rutaPlana(
              vault, p.join(docs.path, 'sesiones', dsid, 'sesion.m4a'), tmpDir: tmp,);
          if (m4a == null) continue; // lo comprime el primer plano
          final clips = [
            for (final c in await store.clips(dsid))
              if (await rutaPlana(vault, '${c['path']}', tmpDir: tmp) case final ruta?)
                {'task': '${c['task_type']}', 'path': ruta, 'mime': 'audio/wav'},
          ];
          await engine.sincronizar(dsid, {
            'audioPath': m4a,
            'audioMime': 'audio/mp4',
            'clips': clips,
            'wifiOnly': settings.wifiOnly,
          });
        } catch (_) {
          // Queda encolado para el próximo ciclo.
        } finally {
          try {
            await Directory(tmp).delete(recursive: true);
          } catch (_) {}
        }
      }
      // NO cerrar la base: en Android sqflite comparte la misma conexión
      // nativa por ruta entre motores del mismo proceso. Si la app está
      // abierta, cerrarla aquí la deja sin base (database_closed) en plena
      // grabación.
      return true;
    } catch (_) {
      return false;
    }
  });
}

/// Registra la tarea periódica (cada 15 min, con conexión). Idempotente.
Future<void> programarSyncFondo() async {
  try {
    if (!Platform.isAndroid) return;
    await Workmanager().initialize(tareaFondoDispatcher);
    await Workmanager().registerPeriodicTask(
      'vocalis-sync',
      'syncPendientes',
      frequency: const Duration(minutes: 15),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingPeriodicWorkPolicy.keep,
    );
  } catch (_) {}
}
