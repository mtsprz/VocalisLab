import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:vocalis_companion/core/finalizar_sesion.dart';
import 'package:vocalis_companion/data/audio_vault.dart';

List<int> _clave(int semilla) {
  final r = Random(semilla);
  return List<int>.generate(32, (_) => r.nextInt(256));
}

void main() {
  late Directory dir;
  setUp(() async => dir = await Directory.systemTemp.createTemp('vault'));
  tearDown(() async => dir.delete(recursive: true));

  Future<File> plano(int n) async {
    final f = File('${dir.path}/sesion.wav');
    await f.writeAsBytes(List<int>.generate(n, (i) => i % 251));
    return f;
  }

  test('cifra (varios bloques), borra el plano y descifra idéntico', () async {
    final vault = AudioVault(() async => _clave(1));
    final f = await plano(AudioVault.chunkSize * 2 + 77);
    final original = await f.readAsBytes();
    final enc = await vault.cifrarArchivo(f.path);
    expect(await f.exists(), false);
    expect(enc, '${f.path}.enc');
    final out = await vault.descifrarA(enc, tmpDir: '${dir.path}/tmp');
    expect(await File(out).readAsBytes(), original);
  });

  test('archivo vacío', () async {
    final vault = AudioVault(() async => _clave(1));
    final f = await plano(0);
    final enc = await vault.cifrarArchivo(f.path);
    final out = await vault.descifrarA(enc, tmpDir: '${dir.path}/tmp');
    expect(await File(out).length(), 0);
  });

  test('clave distinta (clave perdida/regenerada) → ClaveAudioInvalida y el .enc queda', () async {
    final f = await plano(5000);
    final enc = await AudioVault(() async => _clave(1)).cifrarArchivo(f.path);
    await expectLater(
        AudioVault(() async => _clave(2)).descifrarA(enc, tmpDir: '${dir.path}/tmp'),
        throwsA(isA<ClaveAudioInvalida>()),);
    expect(await File(enc).exists(), true);
  });

  test('manipulación y truncado se detectan', () async {
    final vault = AudioVault(() async => _clave(1));
    final f = await plano(AudioVault.chunkSize + 10);
    final enc = await vault.cifrarArchivo(f.path);
    final bytes = await File(enc).readAsBytes();
    // Un bit cambiado.
    final mod = List<int>.from(bytes)..[100] ^= 1;
    await File(enc).writeAsBytes(mod);
    await expectLater(vault.descifrarA(enc, tmpDir: '${dir.path}/t'),
        throwsA(isA<ClaveAudioInvalida>()),);
    // Truncado en el límite de bloque (sin el bloque final).
    const primerBloque = 8 + 12 + 4 + AudioVault.chunkSize + 16;
    await File(enc).writeAsBytes(bytes.sublist(0, primerBloque));
    await expectLater(vault.descifrarA(enc, tmpDir: '${dir.path}/t'), throwsA(anything));
  });

  test('rutaPlana: prefiere .enc y acepta planos previos al cifrado', () async {
    final vault = AudioVault(() async => _clave(1));
    final f = await plano(100);
    expect(await rutaPlana(vault, f.path, tmpDir: '${dir.path}/t'), f.path);
    await vault.cifrarArchivo(f.path);
    final r = await rutaPlana(vault, f.path, tmpDir: '${dir.path}/t');
    expect(r, startsWith('${dir.path}/t'));
    expect(await rutaPlana(vault, '${dir.path}/nada.wav', tmpDir: '${dir.path}/t'), isNull);
  });

  test('marcas recuperadas tras cierre forzado cierran la tarea abierta', () async {
    await File('${dir.path}/$archivoMarcas').writeAsString('''
{"t": 42.0, "speaker": "paciente", "inicio_turno": 30.0,
 "marcas": [{"task_type":"conteo","speaker":"paciente","start_sec":1.0,"end_sec":10.0}],
 "turnos": [],
 "abierta": {"task":"lectura","speaker":"paciente","inicio":30.0}}''');
    final segs = await marcasRecuperadas(dir.path);
    expect(segs.length, 2);
    expect(segs.last['task_type'], 'lectura');
    expect(segs.last['end_sec'], 42.0);
  });

  test('sin tareas: los turnos pasan a conversación espontánea', () {
    final s = segmentosFinales([], [
      {'speaker': 'paciente', 'start_sec': 0.0, 'end_sec': 5.0},
    ]);
    expect(s.single['task_type'], 'conversacion_espontanea');
  });
}
