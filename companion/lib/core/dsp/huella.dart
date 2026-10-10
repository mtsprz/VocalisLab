import 'dart:ffi';
import 'dart:io';
import 'dart:typed_data';

import 'package:sherpa_onnx/sherpa_onnx.dart' as so;

/// Huella vocal (embedding de timbre) con el modelo CAM++ de reconocimiento
/// de hablante (3D-Speaker, VoxCeleb, 16 kHz) vía sherpa-onnx. Offline.
/// Se usa dentro del isolate de análisis: [abrirExtractor] inicializa las
/// bindings FFI de ESE isolate.
const duracionTramoSeg = 1.5;

/// Windows trae su propio onnxruntime.dll en System32 (WinML), incompatible:
/// se precarga el que viaja junto al ejecutable (o en [dirNativo]) para que
/// sherpa-onnx enlace con ese.
void _precargarOnnxRuntimeWindows(String? dirNativo) {
  if (!Platform.isWindows) return;
  final dir = dirNativo ?? File(Platform.resolvedExecutable).parent.path;
  final f = File('$dir/onnxruntime.dll');
  if (f.existsSync()) {
    try {
      DynamicLibrary.open(f.path);
    } catch (_) {}
  }
}

so.SpeakerEmbeddingExtractor? abrirExtractor(String modelPath, {String? dirNativo}) {
  try {
    _precargarOnnxRuntimeWindows(dirNativo);
    so.initBindings(dirNativo);
    return so.SpeakerEmbeddingExtractor(
      config: so.SpeakerEmbeddingExtractorConfig(model: modelPath, numThreads: 2, debug: false),
    );
  } catch (_) {
    return null;
  }
}

/// Huella de un tramo de audio (muestras -1..1 a [sampleRate]); sherpa-onnx
/// remuestrea a 16 kHz. null si el tramo no alcanza para calcularla.
Float32List? huellaDe(so.SpeakerEmbeddingExtractor ex, Float32List muestras, int sampleRate) {
  final s = ex.createStream();
  try {
    s.acceptWaveform(samples: muestras, sampleRate: sampleRate);
    s.inputFinished();
    return ex.isReady(s) ? ex.compute(s) : null;
  } finally {
    s.free();
  }
}
