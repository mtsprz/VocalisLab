import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:path/path.dart' as p;
import 'package:record/record.dart';

import 'wav.dart';

/// Grabación PCM 16-bit mono 44.1 kHz en bloques WAV de 30 s.
///
/// - Sin AGC, sin supresión de ruido, sin cancelación de eco (config explícita).
/// - Cada bloque se finaliza al rotar; ante un cierre forzado los bloques
///   quedan con cabecera recuperable ([recuperarBloques]).
/// - `onLevelDb` entrega dBFS del trozo para el medidor anti-saturación.
class RecorderService {
  final AudioRecorder _rec = AudioRecorder();
  StreamSubscription<Uint8List>? _sub;
  WavBlockWriter? _writer;
  String _blocksDir = '';
  int _blockIndex = 0;
  int _bytesInBlock = 0;
  int _bytesPerBlock = 44100 * 2 * 30;

  bool get isRecording => _recorderBusy;

  bool _recorderBusy = false;

  /// RMS→dBFS del último trozo (para UI).
  void Function(double dbfs)? onLevelDb;

  Future<bool> tienePermiso() => _rec.hasPermission();

  Future<void> iniciar(String blocksDir) async {
    if (_recorderBusy) return;
    _blocksDir = blocksDir;
    await Directory(blocksDir).create(recursive: true);
    // Continuar numeración si ya había bloques (reanudación tras cierre).
    _blockIndex = 0;
    await for (final e in Directory(blocksDir).list()) {
      if (e is File && e.path.endsWith('.wav')) _blockIndex++;
    }
    const config = RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: 44100,
      numChannels: 1,
      autoGain: false,
      echoCancel: false,
      noiseSuppress: false,
    );
    final stream = await _rec.startStream(config);
    _recorderBusy = true;
    await _abrirBloque();
    _sub = stream.listen(_onChunk, onError: (_) {}, cancelOnError: false);
  }

  Future<void> _abrirBloque() async {
    await _writer?.close();
    final name = 'b${_blockIndex.toString().padLeft(3, '0')}.wav';
    _writer = WavBlockWriter(p.join(_blocksDir, name));
    await _writer!.open();
    _bytesInBlock = 0;
    _blockIndex++;
  }

  Future<void> _onChunk(Uint8List chunk) async {
    // Medidor de nivel (RMS → dBFS).
    var sum = 0.0;
    final n = chunk.length ~/ 2;
    final bd = ByteData.sublistView(chunk);
    for (var i = 0; i < n; i++) {
      final v = bd.getInt16(i * 2, Endian.little) / 32768.0;
      sum += v * v;
    }
    final rms = n == 0 ? 0.0 : math.sqrt(sum / n);
    final db = rms <= 0 ? -90.0 : 20 * (math.log(rms) / math.ln10);
    onLevelDb?.call(db.clamp(-90.0, 0.0));
    // Rotación por tamaño (≈30 s).
    var resto = chunk;
    while (resto.isNotEmpty) {
      final falta = _bytesPerBlock - _bytesInBlock;
      if (resto.length <= falta) {
        await _writer?.appendBytes(resto);
        _bytesInBlock += resto.length;
        resto = Uint8List(0);
      } else {
        await _writer?.appendBytes(resto.sublist(0, falta));
        await _abrirBloque();
      }
    }
  }

  Future<void> pausar() async {
    if (_recorderBusy) {
      try {
        await _rec.pause();
      } catch (_) {}
    }
  }

  Future<void> reanudar() async {
    if (_recorderBusy) {
      try {
        await _rec.resume();
      } catch (_) {}
    }
  }

  Future<void> detener() async {
    try {
      await _sub?.cancel();
    } catch (_) {}
    _sub = null;
    try {
      await _rec.stop();
    } catch (_) {}
    _recorderBusy = false;
    await _writer?.close();
    _writer = null;
  }

  Future<void> dispose() async {
    await detener();
    _rec.dispose();
  }
}
