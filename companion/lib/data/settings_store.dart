import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// Ajustes persistentes sin dependencias (JSON en documentos):
/// solo-WiFi, retención local en días, offset de calibración dB.
class AppSettings {
  bool wifiOnly;
  int localRetentionDays;
  double calibrationDbOffset;

  AppSettings({
    this.wifiOnly = true,
    this.localRetentionDays = 30,
    this.calibrationDbOffset = 0.0,
  });

  static Future<File> _file() async {
    final d = await getApplicationDocumentsDirectory();
    return File(p.join(d.path, 'ajustes.json'));
  }

  static Future<AppSettings> load() async {
    try {
      final f = await _file();
      if (!await f.exists()) return AppSettings();
      final m = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      return AppSettings(
        wifiOnly: (m['wifiOnly'] as bool?) ?? true,
        localRetentionDays: (m['localRetentionDays'] as int?) ?? 30,
        calibrationDbOffset: ((m['calibrationDbOffset'] as num?) ?? 0).toDouble(),
      );
    } catch (_) {
      return AppSettings();
    }
  }

  Future<void> save() async {
    final f = await _file();
    await f.writeAsString(jsonEncode({
      'wifiOnly': wifiOnly,
      'localRetentionDays': localRetentionDays,
      'calibrationDbOffset': calibrationDbOffset,
    }));
  }
}
