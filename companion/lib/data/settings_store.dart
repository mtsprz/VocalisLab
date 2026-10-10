import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

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

  /// Huella vocal (timbre) de "Mi voz" y modelo con que se calculó.
  Float32List? vozFonoHuella;
  String? vozFonoModelo;

  AppSettings({
    this.wifiOnly = true,
    this.localRetentionDays = 30,
    this.vozFonoHz,
    this.vozFonoSdSt,
    this.vozFonoHuella,
    this.vozFonoModelo,
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
        vozFonoHuella: m['vozFonoHuella'] is String
            ? Float32List.view(base64Decode(m['vozFonoHuella'] as String).buffer)
            : null,
        vozFonoModelo: m['vozFonoModelo'] as String?,
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
      if (vozFonoHuella != null)
        'vozFonoHuella': base64Encode(vozFonoHuella!.buffer.asUint8List(
            vozFonoHuella!.offsetInBytes, vozFonoHuella!.lengthInBytes,),),
      if (vozFonoModelo != null) 'vozFonoModelo': vozFonoModelo,
    }),);
  }
}
