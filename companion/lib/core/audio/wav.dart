import 'dart:io';
import 'dart:typed_data';

/// WAV PCM 16-bit mono 44.1 kHz con cabecera recuperable.
///
/// Estrategia anti-pérdida: cada bloque de 30 s se escribe con cabecera
/// placeholder válida; al cerrar se parchan los tamaños. Si la app muere
/// (batería/cierre), [recuperarBloques] finaliza las cabeceras huérfanas.
class WavBlockWriter {
  final String path;
  final int sampleRate;
  RandomAccessFile? _f;
  int _dataBytes = 0;

  WavBlockWriter(this.path, {this.sampleRate = 44100});

  Future<void> open() async {
    _f = await File(path).open(mode: FileMode.write);
    await _f!.writeFrom(_cabecera(0));
    _dataBytes = 0;
  }

  /// Anexa PCM16 little-endian mono.
  Future<void> appendBytes(List<int> pcm16) async {
    if (_f == null) throw StateError('WavBlockWriter no abierto');
    await _f!.writeFrom(pcm16);
    _dataBytes += pcm16.length;
  }

  Future<void> close() async {
    final f = _f;
    _f = null;
    if (f == null) return;
    await f.setPosition(0);
    await f.writeFrom(_cabecera(_dataBytes));
    await f.close();
  }

  List<int> _cabecera(int dataBytes) {
    final b = ByteData(44);
    void s(int o, String v) {
      for (var i = 0; i < v.length; i++) {
        b.setUint8(o + i, v.codeUnitAt(i));
      }
    }

    s(0, 'RIFF');
    b.setUint32(4, 36 + dataBytes, Endian.little);
    s(8, 'WAVE');
    s(12, 'fmt ');
    b.setUint32(16, 16, Endian.little);
    b.setUint16(20, 1, Endian.little); // PCM
    b.setUint16(22, 1, Endian.little); // mono
    b.setUint32(24, sampleRate, Endian.little);
    b.setUint32(28, sampleRate * 2, Endian.little);
    b.setUint16(32, 2, Endian.little);
    b.setUint16(34, 16, Endian.little);
    s(36, 'data');
    b.setUint32(40, dataBytes, Endian.little);
    return b.buffer.asUint8List();
  }
}

/// Finaliza cabeceras de bloques huérfanos (recuperación post-cierre).
/// Devuelve la lista de bloques recuperados y válidos (>1 s de audio).
Future<List<String>> recuperarBloques(Directory dir) async {
  final out = <String>[];
  if (!await dir.exists()) return out;
  await for (final e in dir.list()) {
    if (e is! File || !e.path.endsWith('.wav')) continue;
    try {
      final raf = await e.open(mode: FileMode.append);
      final len = await raf.length();
      await raf.close();
      if (len <= 44) {
        await e.delete();
        continue;
      }
      final dataBytes = len - 44;
      final rw = await e.open(mode: FileMode.writeOnly);
      await rw.setPosition(4);
      final fix = ByteData(4)..setUint32(0, 36 + dataBytes, Endian.little);
      await rw.writeFrom(fix.buffer.asUint8List());
      await rw.setPosition(40);
      final fix2 = ByteData(4)..setUint32(0, dataBytes, Endian.little);
      await rw.writeFrom(fix2.buffer.asUint8List());
      await rw.close();
      // Validez mínima: >1 s a 44.1 kHz mono 16-bit.
      if (dataBytes > 44100 * 2) out.add(e.path);
    } catch (_) {
      // Bloque corrupto: se deja para revisión manual, no se borra.
    }
  }
  out.sort();
  return out;
}

/// Concatena bloques WAV (misma geometría) en un único WAV válido.
Future<String> concatenarBloques(List<String> bloques, String destino,
    {int sampleRate = 44100}) async {
  final w = WavBlockWriter(destino, sampleRate: sampleRate);
  await w.open();
  for (final b in bloques) {
    final bytes = await File(b).readAsBytes();
    if (bytes.length > 44) {
      await w.appendBytes(bytes.sublist(44));
    }
  }
  await w.close();
  return destino;
}

/// Lee PCM16 mono normalizado de un WAV estándar (para DSP y clips).
List<double> leerPcmNormalizado(String path, {int sampleRateEsperado = 44100}) {
  final bytes = File(path).readAsBytesSync();
  if (bytes.length < 44) return const [];
  final data = bytes.sublist(44);
  final n = data.length ~/ 2;
  final bd = ByteData.sublistView(data);
  final out = List<double>.filled(n, 0.0);
  for (var i = 0; i < n; i++) {
    out[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
  }
  return out;
}

/// Recorta [segundos] de PCM a un WAV nuevo (clips de vocal sostenida).
Future<String> recortarWav({
  required String origen,
  required double desdeSec,
  required double segundos,
  required String destino,
  int sampleRate = 44100,
}) async {
  final pcm = leerPcmNormalizado(origen, sampleRateEsperado: sampleRate);
  final a = (((desdeSec * sampleRate).round().clamp(0, pcm.length))).toInt();
  final b = ((((desdeSec + segundos) * sampleRate).round().clamp(0, pcm.length))).toInt();
  final w = WavBlockWriter(destino, sampleRate: sampleRate);
  await w.open();
  final bd = ByteData((b - a) * 2);
  for (var i = a; i < b; i++) {
    bd.setInt16((i - a) * 2, (pcm[i].clamp(-1.0, 1.0) * 32767).round(), Endian.little);
  }
  await w.appendBytes(bd.buffer.asUint8List());
  await w.close();
  return destino;
}
