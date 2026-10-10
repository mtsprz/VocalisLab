import 'dart:math' as math;

import 'yin.dart';

/// Perfil de tono de la voz del fonoaudiólogo/a (Ajustes → "Mi voz").
class PerfilVoz {
  final double medianaHz;
  final double sdSt;
  const PerfilVoz(this.medianaHz, this.sdSt);
}

/// Resultado de separar paciente / fonoaudiólogo en una grabación.
class Diarizacion {
  /// Segmentos del contrato (task_type conversacion_espontanea) que cubren
  /// toda la grabación, alternando 'paciente' / 'fonoaudiologo'.
  final List<Map<String, dynamic>> segmentos;

  /// Cuadros (10 ms) que caen en tramos del paciente, en orden.
  final List<YinFrame> cuadrosPaciente;

  /// Proporción del tiempo con voz atribuido al paciente (0..1).
  final double fraccionPaciente;

  /// 'alta' | 'media' | 'baja' | 'sin_perfil'.
  final String confianza;

  /// Distancia entre las dos voces en semitonos (null si no se pudo estimar).
  final double? separacionSt;

  const Diarizacion({
    required this.segmentos,
    required this.cuadrosPaciente,
    required this.fraccionPaciente,
    required this.confianza,
    this.separacionSt,
  });
}

double _st(double hz) => 12 * (math.log(hz / 100) / math.ln2);

double _mediana(List<double> v) {
  final s = List<double>.from(v)..sort();
  final n = s.length;
  return n.isOdd ? s[n ~/ 2] : (s[n ~/ 2 - 1] + s[n ~/ 2]) / 2;
}

/// Perfil de una grabación corta de la voz del fonoaudiólogo/a.
/// null si hay menos de 1 s de voz.
PerfilVoz? perfilDesdeCuadros(List<YinFrame> cuadros) {
  final f0 = medianFilter5(cuadros.map((c) => c.f0).toList()).where((f) => f > 0).toList();
  if (f0.length < 100) return null;
  final med = _mediana(f0);
  final sts = f0.map((f) => 12 * (math.log(f / med) / math.ln2)).toList();
  final m = sts.reduce((a, b) => a + b) / sts.length;
  final sd = math.sqrt(sts.map((s) => (s - m) * (s - m)).reduce((a, b) => a + b) / sts.length);
  return PerfilVoz(med, sd);
}

/// Separa las voces por altura tonal: cada ventana de 0,5 s con voz se
/// asigna a la voz más cercana (en desvíos) entre el perfil del
/// fonoaudiólogo/a y el rango esperado del paciente (sexo/edad). Si no hay
/// rango, el centro del paciente se estima con lo que queda lejos del perfil.
/// Tramos de menos de 1 s se funden con el anterior (evita saltos).
Diarizacion diarizar(
  List<YinFrame> cuadros, {
  PerfilVoz? fono,
  double? rangoMinHz,
  double? rangoMaxHz,
  double pasoSeg = 0.010,
}) {
  const vent = 50; // 0,5 s
  final f0 = medianFilter5(cuadros.map((c) => c.f0).toList());
  final dur = cuadros.length * pasoSeg;
  if (cuadros.isEmpty) {
    return const Diarizacion(
        segmentos: [], cuadrosPaciente: [], fraccionPaciente: 0, confianza: 'baja',);
  }

  // Sin perfil: no se puede distinguir; todo se toma como paciente.
  if (fono == null) {
    return Diarizacion(
      segmentos: [
        {'task_type': 'conversacion_espontanea', 'speaker': 'paciente', 'start_sec': 0.0, 'end_sec': dur},
      ],
      cuadrosPaciente: cuadros,
      fraccionPaciente: 1,
      confianza: 'sin_perfil',
    );
  }

  final ct = _st(fono.medianaHz);
  final sT = math.max(fono.sdSt, 1.0);
  double? cp;
  double sP = 2.0;
  if (rangoMinHz != null && rangoMaxHz != null && rangoMinHz > 0 && rangoMaxHz > rangoMinHz) {
    cp = _st(math.sqrt(rangoMinHz * rangoMaxHz));
    sP = math.max((_st(rangoMaxHz) - _st(rangoMinHz)) / 2, 1.5);
  } else {
    final lejos = [
      for (final f in f0)
        if (f > 0 && ((_st(f) - ct).abs() / sT) > 2.5) _st(f),
    ];
    final sonoros = f0.where((f) => f > 0).length;
    if (sonoros > 0 && lejos.length >= sonoros * 0.05) {
      lejos.sort();
      cp = lejos[lejos.length ~/ 2];
    }
  }

  // Etiqueta por ventana (true = paciente; null = sin voz).
  final nVent = (cuadros.length + vent - 1) ~/ vent;
  final etiquetas = List<bool?>.filled(nVent, null);
  for (var w = 0; w < nVent; w++) {
    var pac = 0, fon = 0;
    for (var i = w * vent; i < math.min((w + 1) * vent, cuadros.length); i++) {
      if (f0[i] <= 0) continue;
      final s = _st(f0[i]);
      final zt = (s - ct).abs() / sT;
      final esPaciente = cp == null ? zt > 2.0 : zt > (s - cp).abs() / sP;
      esPaciente ? pac++ : fon++;
    }
    if (pac + fon >= 5) etiquetas[w] = pac > fon;
  }
  // Ventanas sin voz heredan la anterior (o la primera con voz).
  final primera = etiquetas.firstWhere((e) => e != null, orElse: () => true)!;
  var actual = primera;
  for (var w = 0; w < nVent; w++) {
    etiquetas[w] ??= actual;
    actual = etiquetas[w]!;
  }
  // Tramos: fundir los de < 1 s (2 ventanas) con el anterior.
  final tramos = <(bool, int, int)>[]; // (paciente, ventanaIni, ventanaFin excl.)
  for (var w = 0; w < nVent; w++) {
    if (tramos.isNotEmpty && tramos.last.$1 == etiquetas[w]) {
      tramos[tramos.length - 1] = (tramos.last.$1, tramos.last.$2, w + 1);
    } else {
      tramos.add((etiquetas[w]!, w, w + 1));
    }
  }
  final fundidos = <(bool, int, int)>[];
  for (final t in tramos) {
    if (fundidos.isNotEmpty && (t.$3 - t.$2 < 2 || fundidos.last.$1 == t.$1)) {
      fundidos[fundidos.length - 1] = (fundidos.last.$1, fundidos.last.$2, t.$3);
    } else {
      fundidos.add(t);
    }
  }

  final segs = <Map<String, dynamic>>[];
  final pacienteFrames = <YinFrame>[];
  var sonorosPac = 0, sonorosTot = 0;
  for (final t in fundidos) {
    final a = t.$2 * vent;
    final b = math.min(t.$3 * vent, cuadros.length);
    segs.add({
      'task_type': 'conversacion_espontanea',
      'speaker': t.$1 ? 'paciente' : 'fonoaudiologo',
      'start_sec': a * pasoSeg,
      'end_sec': b * pasoSeg,
    });
    for (var i = a; i < b; i++) {
      if (cuadros[i].f0 > 0) {
        sonorosTot++;
        if (t.$1) sonorosPac++;
      }
      if (t.$1) pacienteFrames.add(cuadros[i]);
    }
  }

  double? sep;
  var conf = 'baja';
  if (cp != null) {
    sep = (cp - ct).abs();
    final d = sep / ((sT + sP) / 2);
    conf = d >= 2.5 ? 'alta' : (d >= 1.5 ? 'media' : 'baja');
  }
  return Diarizacion(
    segmentos: segs,
    cuadrosPaciente: pacienteFrames,
    fraccionPaciente: sonorosTot == 0 ? 0 : sonorosPac / sonorosTot,
    confianza: conf,
    separacionSt: sep,
  );
}
