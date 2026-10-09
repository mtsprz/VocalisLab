import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:workmanager/workmanager.dart';

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
      final docs = await getApplicationDocumentsDirectory();
      for (final s in await store.pendientes()) {
        final dsid = '${s['device_session_id']}';
        final m4a = File(p.join(docs.path, 'sesiones', dsid, 'sesion.m4a'));
        if (!await m4a.exists()) continue; // lo comprime el primer plano
        final clips = [
          for (final c in await store.clips(dsid))
            if (await File('${c['path']}').exists())
              {'task': '${c['task_type']}', 'path': '${c['path']}', 'mime': 'audio/wav'},
        ];
        try {
          await engine.sincronizar(dsid, {
            'audioPath': m4a.path,
            'audioMime': 'audio/mp4',
            'clips': clips,
            'wifiOnly': settings.wifiOnly,
          });
        } catch (_) {
          // Queda encolado para el próximo ciclo.
        }
      }
      await db.close();
      return Future.value(true);
    } catch (_) {
      return Future.value(false);
    }
  });
}

/// Registra la tarea periódica (cada 15 min, con conexión). Idempotente.
Future<void> programarSyncFondo() async {
  try {
    if (!Platform.isAndroid) return;
    await Workmanager().initialize(tareaFondoDispatcher, isInDebugMode: false);
    await Workmanager().registerPeriodicTask(
      'vocalis-sync',
      'syncPendientes',
      frequency: const Duration(minutes: 15),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
  } catch (_) {}
}
