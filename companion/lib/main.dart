import 'package:flutter/material.dart';

import 'app.dart';
import 'data/db.dart';
import 'sync/tareas_fondo.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final db = await openAppDb();
  // Segundo plano (Android): no bloquea el arranque si falla.
  try {
    await programarSyncFondo();
  } catch (_) {}
  runApp(CompanionApp(db: db));
}
