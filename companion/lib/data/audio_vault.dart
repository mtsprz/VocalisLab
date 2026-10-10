import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:path/path.dart' as p;

/// Cifrado autenticado de audio en reposo: AES-256-GCM por bloques.
///
/// Formato `.enc` (v1):
///   'VCE1' | chunkSize u32 LE |
///   por bloque: nonce(12) | len u32 LE | cifrado(len) | tag(16)
/// AAD de cada bloque = 'VCE1' | índice u64 LE | final u8. Así se detecta
/// manipulación, bloques reordenados y archivos truncados (el último bloque
/// debe tener final=1). Nonce aleatorio de 96 bits por bloque.
///
/// La clave (32 bytes) vive en almacenamiento seguro (Keystore/DPAPI). Si se
/// pierde, los `.enc` locales son irrecuperables: ver README §Seguridad.
class AudioVault {
  static const _magic = [0x56, 0x43, 0x45, 0x31]; // 'VCE1'
  static const extension = '.enc';
  static const chunkSize = 1024 * 1024;

  final Future<List<int>> Function() _leerClave;
  final AesGcm _aes = AesGcm.with256bits();

  AudioVault(this._leerClave);

  List<int> _aad(int index, bool last) {
    final b = ByteData(13)
      ..setUint64(4, index, Endian.little)
      ..setUint8(12, last ? 1 : 0);
    final out = b.buffer.asUint8List();
    out.setRange(0, 4, _magic);
    return out;
  }

  /// Cifra [plano] → `plano.enc`, verifica leyendo y autenticando todo el
  /// `.enc`, y recién entonces borra el plano. Devuelve la ruta `.enc`.
  Future<String> cifrarArchivo(String plano) async {
    final destino = '$plano$extension';
    final tmp = '$destino.part';
    final key = SecretKey(await _leerClave());
    final src = await File(plano).open();
    final out = await File(tmp).open(mode: FileMode.write);
    try {
      final total = await src.length();
      final head = ByteData(8)..setUint32(4, chunkSize, Endian.little);
      final h = head.buffer.asUint8List()..setRange(0, 4, _magic);
      await out.writeFrom(h);
      var leido = 0;
      var i = 0;
      do {
        final buf = await src.read(chunkSize);
        leido += buf.length;
        final last = leido >= total;
        final box = await _aes.encrypt(buf,
            secretKey: key, nonce: _aes.newNonce(), aad: _aad(i, last),);
        final len = ByteData(4)..setUint32(0, box.cipherText.length, Endian.little);
        await out.writeFrom(box.nonce);
        await out.writeFrom(len.buffer.asUint8List());
        await out.writeFrom(box.cipherText);
        await out.writeFrom(box.mac.bytes);
        i++;
      } while (leido < total);
      await out.flush();
    } finally {
      await src.close();
      await out.close();
    }
    await File(tmp).rename(destino);
    // Verificación completa antes de tocar el original.
    await _procesar(destino, null);
    await File(plano).delete();
    return destino;
  }

  /// Descifra [cifrado] a [destino] (o a un temporal junto a [tmpDir]).
  /// Lanza [ClaveAudioInvalida] si la clave no corresponde o hay manipulación.
  Future<String> descifrarA(String cifrado, {required String tmpDir}) async {
    await Directory(tmpDir).create(recursive: true);
    var nombre = p.basename(cifrado);
    if (nombre.endsWith(extension)) {
      nombre = nombre.substring(0, nombre.length - extension.length);
    }
    final destino = p.join(tmpDir, '${DateTime.now().microsecondsSinceEpoch}_$nombre');
    final out = await File(destino).open(mode: FileMode.write);
    try {
      await _procesar(cifrado, out);
    } catch (_) {
      await out.close();
      await File(destino).delete();
      rethrow;
    }
    await out.close();
    return destino;
  }

  /// Recorre y autentica todos los bloques; si [out] no es null escribe el plano.
  Future<void> _procesar(String cifrado, RandomAccessFile? out) async {
    final key = SecretKey(await _leerClave());
    final f = await File(cifrado).open();
    try {
      final total = await f.length();
      final head = await f.read(8);
      if (head.length < 8 || !_eq(head.sublist(0, 4), _magic)) {
        throw const FormatException('No es un audio cifrado VCE1');
      }
      var i = 0;
      var visto = false;
      while (await f.position() < total) {
        if (visto) throw const FormatException('Datos después del bloque final');
        final nonce = await f.read(12);
        final lenB = await f.read(4);
        if (nonce.length < 12 || lenB.length < 4) {
          throw const FormatException('Audio cifrado truncado');
        }
        final len = ByteData.sublistView(lenB).getUint32(0, Endian.little);
        final ct = await f.read(len);
        final tag = await f.read(16);
        if (ct.length < len || tag.length < 16) {
          throw const FormatException('Audio cifrado truncado');
        }
        final last = await f.position() >= total;
        try {
          final plano = await _aes.decrypt(
              SecretBox(ct, nonce: nonce, mac: Mac(tag)),
              secretKey: key,
              aad: _aad(i, last),);
          if (out != null) await out.writeFrom(plano);
        } on SecretBoxAuthenticationError {
          throw const ClaveAudioInvalida();
        }
        visto = last;
        i++;
      }
      if (!visto) throw const FormatException('Audio cifrado sin bloque final');
    } finally {
      await f.close();
    }
  }

  static bool _eq(List<int> a, List<int> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}

/// La clave guardada no descifra el archivo (clave perdida/regenerada o
/// archivo alterado). El `.enc` NO se borra: queda para recuperación manual.
class ClaveAudioInvalida implements Exception {
  const ClaveAudioInvalida();
  @override
  String toString() => 'ClaveAudioInvalida: la clave de cifrado local no '
      'corresponde a este audio (¿se reinstaló la app o se borraron sus datos?)';
}

/// Ruta utilizable de un audio local: si existe el `.enc` lo descifra a
/// [tmpDir]; si solo existe el plano (sesiones previas al cifrado), lo
/// devuelve tal cual. null si no hay ninguno.
Future<String?> rutaPlana(AudioVault vault, String plano, {required String tmpDir}) async {
  final enc = File('$plano${AudioVault.extension}');
  if (await enc.exists()) return vault.descifrarA(enc.path, tmpDir: tmpDir);
  if (await File(plano).exists()) return plano;
  return null;
}
