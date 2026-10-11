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
/// - `onNivel` entrega un nivel 0..1 y aviso de saturación (sin cifras de dB).
class RecorderService {
  final AudioRecorder _rec = AudioRecorder();
  StreamSubscription<Uint8List>? _sub;
  WavBlockWriter? _writer;
  String _blocksDir = '';
  int _blockIndex = 0;
  int _bytesInBlock = 0;
  final int _bytesPerBlock = 44100 * 2 * 30;

  bool get isRecording => _recorderBusy;

  bool _recorderBusy = false;

  // Escrituras en serie: RandomAccessFile no admite operaciones solapadas y
  // el stream entrega trozos sin esperar a que termine el anterior.
  Future<void> _cola = Future.value();

  /// Nivel de entrada del último trozo para el indicador anti-saturación:
  /// [nivel] 0..1 (escala visual, sin cifras) y [satura] si algún pico
  /// llegó al tope digital.
  void Function(double nivel, bool satura)? onNivel;

  /// Cada fragmento PCM16 tal como se escribe a disco (para el análisis en
  /// vivo: al detener, la altura tonal ya está casi calculada).
  void Function(Uint8List pcm16)? onPcm;

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
    // Android: además de apagar los efectos (record los crea con
    // enabled=false), se usa la fuente VOICE_RECOGNITION: el CDD de Android
    // exige que no aplique AGC ni reducción de ruido, a diferencia de
    // DEFAULT/MIC, que puede traer procesamiento del fabricante.
    const config = RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: 44100,
      numChannels: 1,
      autoGain: false,
      echoCancel: false,
      noiseSuppress: false,
      androidConfig: AndroidRecordConfig(
        audioSource: AndroidAudioSource.voiceRecognition,
      ),
    );
    final stream = await _rec.startStream(config);
    _recorderBusy = true;
    await _abrirBloque();
    _sub = stream.listen(
      (c) => _cola = _cola.then((_) => _onChunk(c)).catchError((_) {}),
      onError: (_) {},
      cancelOnError: false,
    );
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
    // Indicador de nivel: RMS en escala logarítmica de 60 pasos → 0..1,
    // y saturación si algún pico toca el tope (≥ 98 % de escala).
    var sum = 0.0;
    var pico = 0.0;
    final n = chunk.length ~/ 2;
    final bd = ByteData.sublistView(chunk);
    for (var i = 0; i < n; i++) {
      final v = bd.getInt16(i * 2, Endian.little) / 32768.0;
      sum += v * v;
      if (v.abs() > pico) pico = v.abs();
    }
    final rms = n == 0 ? 0.0 : math.sqrt(sum / n);
    final log = rms <= 0 ? -60.0 : 20 * (math.log(rms) / math.ln10);
    onNivel?.call((((log + 60) / 60).clamp(0.0, 1.0)).toDouble(), pico >= 0.98);
    try {
      onPcm?.call(chunk);
    } catch (_) {
      // El análisis en vivo nunca puede frenar la grabación.
    }
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
    await _cola; // terminar de escribir lo recibido antes de cerrar
    await _writer?.close();
    _writer = null;
  }

  Future<void> dispose() async {
    await detener();
    _rec.dispose();
  }
}
