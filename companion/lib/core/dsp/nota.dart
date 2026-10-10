import 'dart:math' as math;

/// Altura tonal como nota musical (solo presentación; no se envía al backend).
///
/// n = round(12·log2(f/440)) semitonos respecto de La4 = 440 Hz.
/// Octava en notación científica: Do4 = Do central (≈261,6 Hz); la octava
/// cambia en Do (Si3 → Do4).
const nombresNota = [
  'Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si',
];

/// Convención mostrada en pantalla.
const convencionOctavas = 'Octavas en notación científica: La4 = 440 Hz · Do4 = Do central';

/// Nombre de la nota más cercana a [hz] (ej. 139 Hz → "Do#3"), o null si
/// [hz] no es positivo.
String? notaDesdeHz(double? hz) {
  if (hz == null || hz <= 0 || hz.isNaN || hz.isInfinite) return null;
  final n = (12 * (math.log(hz / 440) / math.ln2)).round();
  // MIDI: La4 = 69; índice 0 = Do.
  final midi = 69 + n;
  final nombre = nombresNota[midi % 12];
  final octava = (midi ~/ 12) - 1;
  return '$nombre$octava';
}

/// "Do#3 · 139 Hz" (o "— Hz" si no hay F0).
String alturaTonal(double? hz) {
  final nota = notaDesdeHz(hz);
  if (nota == null) return '— Hz';
  return '$nota · ${hz!.round()} Hz';
}
