import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// Ajustes persistentes sin dependencias (JSON en documentos):
/// solo-WiFi, retención local en días y perfil de "Mi voz" (solo números:
/// mediana en Hz y dispersión en semitonos; el audio de muestra se borra).
class AppSettings {
  bool wifiOnly;
  int localRetentionDays;
  double? vozFonoHz;
  double? vozFonoSdSt;

  AppSettings({
    this.wifiOnly = true,
    this.localRetentionDays = 30,
    this.vozFonoHz,
    this.vozFonoSdSt,
  });

  bool get tienePerfilVoz => vozFonoHz != null && vozFonoHz! > 0;

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
        vozFonoHz: (m['vozFonoHz'] as num?)?.toDouble(),
        vozFonoSdSt: (m['vozFonoSdSt'] as num?)?.toDouble(),
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
      if (vozFonoHz != null) 'vozFonoHz': vozFonoHz,
      if (vozFonoSdSt != null) 'vozFonoSdSt': vozFonoSdSt,
    }),);
  }
}
