import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:vocalis_companion/core/audio/wav.dart';

Future<void> main() async {
  group('WavBlockWriter', () {
    test('escribe, finaliza y se lee igual', () async {
      final dir = await Directory.systemTemp.createTemp('wavtest');
      final path = '${dir.path}/b0.wav';
      final w = WavBlockWriter(path);
      await w.open();
      final bd = ByteData(4410 * 2);
      for (var i = 0; i < 4410; i++) {
        bd.setInt16(i * 2, 1000, Endian.little);
      }
      await w.appendBytes(bd.buffer.asUint8List());
      await w.close();
      final pcm = leerPcmNormalizado(path);
      expect(pcm.length, 4410);
      expect(pcm.first, closeTo(1000 / 32768.0, 1e-6));
      await dir.delete(recursive: true);
    });

    test('recuperarBloques finaliza cabeceras huérfanas', () async {
      final dir = await Directory.systemTemp.createTemp('wavrec');
      // Simular cierre forzado: 44 bytes de cabecera sin parchar + datos.
      final path = p.join(dir.path, 'b0.wav'); // separador nativo (Windows)
      final raf = await File(path).open(mode: FileMode.write);
      await raf.writeFrom(List<int>.filled(44, 0));
      await raf.writeFrom(List<int>.filled(90000 * 2, 7));
      await raf.close();
      final rec = await recuperarBloques(dir);
      expect(rec, contains(path));
      final pcm = leerPcmNormalizado(path);
      expect(pcm.length, 90000);
      await dir.delete(recursive: true);
    });

    test('bloques vacíos se descartan', () async {
      final dir = await Directory.systemTemp.createTemp('wavempty');
      final w = WavBlockWriter('${dir.path}/vacio.wav');
      await w.open();
      await w.close();
      // 0 bytes de datos: recuperar lo ignora (queda el archivo, sin audio útil)
      final rec = await recuperarBloques(dir);
      expect(rec, isEmpty);
      await dir.delete(recursive: true);
    });
  });
}
