import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../core/dsp/modelo_huella.dart';
import '../core/finalizar_sesion.dart';
import '../data/settings_store.dart';
import 'summary_screen.dart' show edadDesde, rangoPara;

/// Rangos de referencia cacheados de /referencias (funciona sin internet).
Future<List<dynamic>> rangosCacheados() async {
  try {
    final f = File(p.join((await getApplicationDocumentsDirectory()).path, 'referencias.json'));
    if (await f.exists()) return jsonDecode(await f.readAsString()) as List<dynamic>;
  } catch (_) {}
  return const [];
}

/// Finaliza con todo el contexto offline: perfil "Mi voz", sexo/edad del
/// paciente y su rango esperado (si ya se descargó la tabla de referencias).
Future<void> finalizarConContexto({
  required Deps deps,
  required String dsid,
  required String sesDir,
  required String pacienteId,
  void Function(double)? onProgreso,
}) async {
  final ajustes = await AppSettings.load();
  var sexo = '';
  int? edad;
  try {
    final pac = (await deps.pacientes.listar()).firstWhere((e) => e.id == pacienteId);
    sexo = pac.sexoReferencia;
    edad = edadDesde(pac.fechaNacimiento);
  } catch (_) {}
  final ref = rangoPara(await rangosCacheados(), sexo, edad);
  final huellaValida = ajustes.vozFonoHuella != null && ajustes.vozFonoModelo == idModeloHuella;
  final modelo = huellaValida ? await rutaModeloHuella() : null;
  await finalizarSesion(
    store: deps.store,
    vault: deps.vault,
    dsid: dsid,
    sesDir: sesDir,
    sexoReferencia: sexo,
    vozFonoHz: ajustes.vozFonoHz,
    vozFonoSdSt: ajustes.vozFonoSdSt,
    rangoMinHz: (ref?['f0_min_hz'] as num?)?.toDouble(),
    rangoMaxHz: (ref?['f0_max_hz'] as num?)?.toDouble(),
    modeloHuella: modelo,
    huellaFono: huellaValida ? ajustes.vozFonoHuella : null,
    onProgreso: onProgreso,
  );
}
