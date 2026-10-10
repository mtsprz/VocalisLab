import 'dart:io';

import 'package:flutter/services.dart' show rootBundle;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

/// Modelo CAM++ de huella vocal (asset de la app). sherpa-onnx necesita una
/// ruta de archivo: se copia una vez al almacenamiento de la app.
const assetModeloHuella = 'assets/models/campplus_sv_16k.onnx';
const idModeloHuella = 'campplus_sv_16k';

Future<String?> rutaModeloHuella() async {
  try {
    final dir = await getApplicationSupportDirectory();
    final f = File(p.join(dir.path, 'modelos', '$idModeloHuella.onnx'));
    final datos = await rootBundle.load(assetModeloHuella);
    if (!await f.exists() || await f.length() != datos.lengthInBytes) {
      await f.parent.create(recursive: true);
      await f.writeAsBytes(datos.buffer.asUint8List(datos.offsetInBytes, datos.lengthInBytes), flush: true);
    }
    return f.path;
  } catch (_) {
    return null; // sin modelo: se usa la separación por altura tonal
  }
}
