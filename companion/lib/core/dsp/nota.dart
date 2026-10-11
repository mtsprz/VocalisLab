import 'dart:math' as math;

/// Altura tonal como nota musical (solo presentación; no se envía al backend).
///
/// Convención franco-belga / laringológica (Jackson Menaldi, Farías,
/// Castelli), la de la bibliografía fonoaudiológica en español:
/// La3 = 440 Hz · Do3 = Do central (≈261,6 Hz) · Do0 ≈ 33 Hz.
/// n = round(12·log2(f/440)) semitonos respecto de La3; la octava cambia en
/// Do (Si2 → Do3). Misma convención que VocalisLab (components/vozNormas.ts).
const nombresNota = [
  'Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si',
];

/// Convención mostrada en pantalla.
const convencionOctavas = 'Octavas franco-belgas: La3 = 440 Hz · Do3 = Do central';

/// Nombre de la nota más cercana a [hz] (ej. 139 Hz → "Do#2"), o null si
/// [hz] no es positivo.
String? notaDesdeHz(double? hz) {
  if (hz == null || hz <= 0 || hz.isNaN || hz.isInfinite) return null;
  final n = (12 * (math.log(hz / 440) / math.ln2)).round();
  // Índice MIDI (La 440 = 69; índice 0 = Do). Octava franco-belga = MIDI/12 − 2.
  final midi = 69 + n;
  final nombre = nombresNota[midi % 12];
  final octava = (midi ~/ 12) - 2;
  return '$nombre$octava';
}

/// "Do#2 · 139 Hz" (o "— Hz" si no hay F0).
String alturaTonal(double? hz) {
  final nota = notaDesdeHz(hz);
  if (nota == null) return '— Hz';
  return '$nota · ${hz!.round()} Hz';
}
