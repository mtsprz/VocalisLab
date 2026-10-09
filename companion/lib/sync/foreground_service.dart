import 'package:flutter_foreground_task/flutter_foreground_task.dart';

/// Servicio en primer plano durante grabación/sincronización (Android).
/// Envuelto en try/catch: si el plugin falla, la app sigue con Wake Lock.
/// iOS/Windows: no-op seguro.
class ForegroundGuard {
  static bool _activo = false;

  static Future<void> iniciar({required String titulo}) async {
    if (_activo) return;
    try {
      FlutterForegroundTask.init(
        androidNotificationOptions: AndroidNotificationOptions(
          channelId: 'vocalis_grabacion',
          channelName: 'Grabación de sesión',
          channelDescription: 'Mantiene la grabación aunque bloquees la pantalla',
          channelImportance: NotificationChannelImportance.LOW,
          priority: NotificationPriority.LOW,
        ),
        iosNotificationOptions: const IOSNotificationOptions(),
        foregroundTaskOptions: const ForegroundTaskOptions(
          interval: 5000,
          isOnceEvent: false,
          autoRunOnBoot: false,
          allowWakeLock: true,
          allowWifiLock: true,
        ),
      );
      await FlutterForegroundTask.startService(
        notificationTitle: titulo,
        notificationText: 'Grabando sesión vocal',
      );
      _activo = true;
    } catch (_) {
      // Sin foreground service: el Wake Lock de la UI igual protege en uso.
    }
  }

  static Future<void> detener() async {
    if (!_activo) return;
    try {
      await FlutterForegroundTask.stopService();
    } catch (_) {}
    _activo = false;
  }
}
