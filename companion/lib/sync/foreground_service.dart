import 'dart:io' show Platform;

import 'package:flutter_foreground_task/flutter_foreground_task.dart';

/// Servicio en primer plano durante grabación/sincronización (Android).
/// Envuelto en try/catch: si el plugin falla, la app sigue con Wake Lock.
/// Windows/iOS: no-op (en escritorio no hay suspensión de apps en segundo plano).
class ForegroundGuard {
  static bool _activo = false;

  static Future<void> iniciar({required String titulo}) async {
    if (_activo || !Platform.isAndroid) return;
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
        foregroundTaskOptions: ForegroundTaskOptions(
          eventAction: ForegroundTaskEventAction.repeat(5000),
          autoRunOnBoot: false,
          allowWakeLock: true,
          allowWifiLock: true,
        ),
      );
      // Android 13+: sin este permiso el servicio corre pero la notificación
      // no se ve. Se pide al empezar la primera grabación.
      if (await FlutterForegroundTask.checkNotificationPermission() !=
          NotificationPermission.granted) {
        await FlutterForegroundTask.requestNotificationPermission();
      }
      // Samsung One UI duerme las apps en segundo plano y corta el micrófono y
      // la sincronización. Se pide una vez quedar fuera de la optimización.
      if (!await FlutterForegroundTask.isIgnoringBatteryOptimizations) {
        await FlutterForegroundTask.requestIgnoreBatteryOptimization();
      }
      // 8.x no lanza excepción al fallar: devuelve ServiceRequestFailure.
      final r = await FlutterForegroundTask.startService(
        notificationTitle: titulo,
        notificationText: 'Grabando sesión vocal',
      );
      _activo = r is ServiceRequestSuccess;
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
