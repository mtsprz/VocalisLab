import 'dart:math' as math;

/// Estimador de F0 por YIN (de Cheveigné & Kawahara 2002), en Dart puro.
///
/// Parámetros fijados por contrato:
/// - ventana 40 ms, paso 10 ms, umbral de periodicidad 0.15,
/// - interpolación parabólica del mínimo, corrección de octava,
/// - compuerta de energía (silencio → 0 = sordo).
///
/// Devuelve Hz, o 0.0 si el cuadro es sordo/no periódico.
class YinConfig {
  final double threshold;
  final double energyGateRms;
  final double minHz;
  final double maxHz;

  const YinConfig({
    this.threshold = 0.15,
    this.energyGateRms = 0.015,
    this.minHz = 75,
    this.maxHz = 600,
  });
}

/// Rango de búsqueda según sexo de referencia (contrato).
/// varón ~75–300 Hz · mujer ~100–500 Hz · niñez ~150–600 Hz.
YinConfig configParaSexo(String sexoReferencia) {
  final s = sexoReferencia.toLowerCase();
  if (s.startsWith('masc') || s.startsWith('varon') || s == 'm') {
    return const YinConfig(minHz: 75, maxHz: 300);
  }
  if (s.startsWith('fem') || s.startsWith('mujer') || s == 'f') {
    return const YinConfig(minHz: 100, maxHz: 500);
  }
  return const YinConfig(minHz: 150, maxHz: 600); // niñez / desconocido
}

class YinFrame {
  /// F0 en Hz (0 = sordo).
  final double f0;

  /// Pico de autocorrelación normalizada (0..1). Sirve para HNR.
  final double strength;

  /// RMS del cuadro (para shimmer/intensidad).
  final double rms;

  const YinFrame(this.f0, this.strength, this.rms);

  bool get voiced => f0 > 0;
}

class YinTracker {
  final int sampleRate;
  final YinConfig config;
  final int windowSize;
  final int tauMin;
  final int tauMax;
  final List<double> _diff;

  YinTracker({required this.sampleRate, YinConfig? config})
      : config = config ?? const YinConfig(),
        windowSize = (sampleRate * 0.040).round(),
        tauMin = (sampleRate / (config ?? const YinConfig()).maxHz).floor(),
        tauMax = (sampleRate / (config ?? const YinConfig()).minHz).ceil(),
        _diff = List<double>.filled(
            (sampleRate / (config ?? const YinConfig()).minHz).ceil() + 2, 0.0);

  /// `frame` debe tener al menos [windowSize] muestras normalizadas (-1..1).
  YinFrame process(List<double> frame) {
    final n = windowSize;
    double sumSq = 0.0;
    for (var i = 0; i < n; i++) {
      sumSq += frame[i] * frame[i];
    }
    final rms = math.sqrt(sumSq / n);
    if (rms < config.energyGateRms) {
      return YinFrame(0.0, 0.0, rms);
    }
    // 1. Función diferencia.
    for (var tau = 0; tau <= tauMax + 1; tau++) {
      var s = 0.0;
      for (var j = 0; j < n - tauMax - 1; j++) {
        final d = frame[j] - frame[j + tau];
        s += d * d;
      }
      _diff[tau] = s;
    }
    // 2. Normalización por media acumulada.
    _diff[0] = 1.0;
    var running = 0.0;
    for (var tau = 1; tau <= tauMax + 1; tau++) {
      running += _diff[tau];
      _diff[tau] = running == 0 ? 1.0 : _diff[tau] * tau / running;
    }
    // 3. Umbral absoluto: primer mínimo bajo el umbral desde tauMin.
    var tau = tauMin;
    while (tau <= tauMax && _diff[tau] >= config.threshold) {
      tau++;
    }
    if (tau > tauMax) {
      return YinFrame(0.0, 0.0, rms);
    }
    // Avanzar al mínimo local.
    while (tau + 1 <= tauMax + 1 && _diff[tau + 1] < _diff[tau]) {
      tau++;
    }
    // 4. Corrección de octava (error "una octava arriba", período mitad):
    // si el doble del período es igual de periódico, preferirlo.
    var best = tau;
    if (best * 2 <= tauMax && _diff[best * 2] < _diff[best]) {
      best = best * 2;
      while (best + 1 <= tauMax + 1 && _diff[best + 1] < _diff[best]) {
        best++;
      }
    }
    // 5. Interpolación parabólica.
    final t0 = math.max(best - 1, 1);
    final t2 = math.min(best + 1, tauMax + 1);
    final y0 = _diff[t0], y1 = _diff[best], y2 = _diff[t2];
    var denom = (y0 + y2 - 2 * y1);
    var shift = 0.0;
    if (denom.abs() > 1e-9) {
      shift = 0.5 * (y0 - y2) / denom;
      shift = shift.clamp(-1.0, 1.0);
    }
    final period = best + shift;
    if (period <= 0) return YinFrame(0.0, 0.0, rms);
    final strength = (1.0 - y1).clamp(0.0, 1.0);
    return YinFrame(sampleRate / period, strength, rms);
  }
}

/// Filtro de mediana de 5 cuadros sobre F0 (suaviza saltos aislados).
/// Ventana con mayoría sorda → 0 (no inventa sonoridad).
List<double> medianFilter5(List<double> f0) {
  final out = List<double>.filled(f0.length, 0.0);
  for (var i = 0; i < f0.length; i++) {
    final win = <double>[];
    for (var k = -2; k <= 2; k++) {
      final j = i + k;
      if (j >= 0 && j < f0.length && f0[j] > 0) win.add(f0[j]);
    }
    if (win.length >= 3) {
      win.sort();
      out[i] = win[win.length ~/ 2];
    } else {
      out[i] = 0.0;
    }
  }
  return out;
}
