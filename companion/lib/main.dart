import 'package:flutter/material.dart';

import 'app.dart';
import 'data/db.dart';
import 'data/settings_store.dart';
import 'sync/tareas_fondo.dart';
import 'ui/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final db = await openAppDb();
  temaApp.value = temaDesde((await AppSettings.load()).tema);
  // Segundo plano (Android): no bloquea el arranque si falla.
  try {
    await programarSyncFondo();
  } catch (_) {}
  runApp(CompanionApp(db: db));
}
