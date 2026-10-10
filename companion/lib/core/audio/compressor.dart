import 'dart:io';

import 'package:flutter/services.dart';

/// Compresión de la sesión a AAC/m4a mono ~48 kbps.
///
/// Decisión documentada (README §compresión):
/// - Android: MediaCodec vía MethodChannel (sin dependencias nativas extra).
/// - Windows: `ffmpeg.exe` empaquetado junto al ejecutable (o en PATH).
/// - No se usa ffmpeg_kit_flutter (discontinuado).
/// - Si no hay compresor disponible se lanza [SinCompresor] con mensaje claro.
abstract class AudioCompressor {
  Future<String> compressToM4a({
    required String wavPath,
    required String outPath,
    int bitrateKbps = 48,
  });

  factory AudioCompressor.platform() {
    if (Platform.isAndroid) return _MediaCodecCompressor();
    if (Platform.isWindows) return _FfmpegCompressor();
    return _SinSoporte();
  }
}

class _SinSoporte implements AudioCompressor {
  @override
  Future<String> compressToM4a(
      {required String wavPath, required String outPath, int bitrateKbps = 48,}) {
    throw const SinCompresor(
        'Compresión no disponible en esta plataforma (solo Android/Windows)',);
  }
}

class SinCompresor implements Exception {
  final String message;
  const SinCompresor(this.message);
  @override
  String toString() => 'SinCompresor: $message';
}

class _MediaCodecCompressor implements AudioCompressor {
  static const _ch = MethodChannel('vocalis_companion/audio');

  @override
  Future<String> compressToM4a(
      {required String wavPath, required String outPath, int bitrateKbps = 48,}) async {
    // Implementación nativa en android/.../MainActivity.kt (method 'compressToAac').
    final ok = await _ch.invokeMethod<bool>('compressToAac', {
      'in': wavPath,
      'out': outPath,
      'bitrate': bitrateKbps * 1000,
    });
    if (ok != true) throw Exception('MediaCodec devolvió false');
    return outPath;
  }
}

class _FfmpegCompressor implements AudioCompressor {
  @override
  Future<String> compressToM4a(
      {required String wavPath, required String outPath, int bitrateKbps = 48,}) async {
    final exe = _buscarFfmpeg();
    if (exe == null) {
      throw const SinCompresor(
          'Falta ffmpeg.exe junto a la app o en PATH (ver README §Windows)',);
    }
    final r = await Process.run(exe, [
      '-y', '-i', wavPath, '-ac', '1', '-ar', '44100',
      '-c:a', 'aac', '-b:a', '${bitrateKbps}k', outPath,
    ]);
    if (r.exitCode != 0) {
      throw Exception('ffmpeg falló (${r.exitCode}): ${r.stderr}');
    }
    return outPath;
  }

  String? _buscarFfmpeg() {
    final exeDir = File(Platform.resolvedExecutable).parent.path;
    for (final c in [
      '$exeDir/ffmpeg.exe',
      '${Directory.current.path}/ffmpeg.exe',
    ]) {
      if (File(c).existsSync()) return c;
    }
    // En PATH (where/which según plataforma).
    try {
      final probe = Process.runSync(
          Platform.isWindows ? 'where' : 'which', ['ffmpeg'],);
      if (probe.exitCode == 0) {
        final first = '${probe.stdout}'.split(RegExp(r'\r?\n')).first.trim();
        if (first.isNotEmpty) return first;
      }
    } catch (_) {}
    return null;
  }
}
