import 'dart:math' as math;
import 'dart:typed_data';

/// Decimación ×3 (44,1 kHz → 14,7 kHz) con filtro antialiasing FIR
/// (sinc enventanado Hamming, 63 coeficientes, corte 6,3 kHz).
///
/// Para medir F0 de voz (≤ ~600 Hz) no se pierde información, y YIN a
/// 14,7 kHz cuesta ~7 veces menos que a 44,1 kHz (ventana de 588 muestras en
/// vez de 1764 y rango de búsqueda 3 veces menor). 10 ms = 147 muestras
/// exactas. Procesa por fragmentos manteniendo el estado (sirve en vivo).
class Decimador3 {
  static const factor = 3;
  static const sampleRateEntrada = 44100;
  static const sampleRateSalida = 14700;
  static const _taps = 63;
  static final Float64List _h = _coeficientes();

  final Float64List _hist = Float64List(_taps - 1); // últimas entradas
  int _fase = 0; // muestras de entrada hasta la próxima salida

  static Float64List _coeficientes() {
    const fc = 6300 / sampleRateEntrada; // corte normalizado
    final h = Float64List(_taps);
    const m = (_taps - 1) / 2;
    var suma = 0.0;
    for (var n = 0; n < _taps; n++) {
      final x = n - m;
      final sinc = x == 0 ? 2 * fc : math.sin(2 * math.pi * fc * x) / (math.pi * x);
      final w = 0.54 - 0.46 * math.cos(2 * math.pi * n / (_taps - 1));
      h[n] = sinc * w;
      suma += h[n];
    }
    for (var n = 0; n < _taps; n++) {
      h[n] /= suma; // ganancia unitaria en continua
    }
    return h;
  }

  /// Agrega muestras a 44,1 kHz (-1..1) y devuelve las nuevas a 14,7 kHz.
  Float64List procesar(Float64List x) {
    final total = _hist.length + x.length;
    final ext = Float64List(total)
      ..setRange(0, _hist.length, _hist)
      ..setRange(_hist.length, total, x);
    final salidas = <double>[];
    var i = _hist.length + _fase;
    while (i < total) {
      var acc = 0.0;
      final base = i - (_taps - 1);
      for (var k = 0; k < _taps; k++) {
        acc += _h[k] * ext[base + k];
      }
      salidas.add(acc);
      i += factor;
    }
    _fase = i - total;
    _hist.setRange(0, _hist.length, ext, total - _hist.length);
    return Float64List.fromList(salidas);
  }
}
