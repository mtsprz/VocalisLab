import 'dart:math' as math;
import 'dart:typed_data';

/// Separación paciente / fonoaudiólogo/a por HUELLA VOCAL (timbre), no por
/// altura tonal: distingue dos voces aunque estén en el mismo rango de Hz.
///
/// Entrada: un vector de timbre (embedding CAM++) por tramo de ~1,5 s con
/// voz, y la huella de "Mi voz". Algoritmo (2 grupos, uno anclado):
///  1. similitud coseno de cada tramo con la huella del fonoaudiólogo/a;
///  2. semilla del paciente = tramos claramente distintos (los menos
///     parecidos);
///  3. se asigna cada tramo al centro más parecido y se recalcula el centro
///     del paciente (el del fonoaudiólogo/a mezcla su huella con sus tramos),
///     hasta que no cambia (máx. 10 vueltas);
///  4. suavizado: un tramo aislado entre dos del otro hablante se corrige.

double coseno(Float32List a, Float32List b) {
  var dot = 0.0, na = 0.0, nb = 0.0;
  for (var i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  if (na == 0 || nb == 0) return 0;
  return dot / math.sqrt(na * nb);
}

Float32List normalizar(Float32List v) {
  var n = 0.0;
  for (final x in v) {
    n += x * x;
  }
  n = math.sqrt(n);
  final out = Float32List(v.length);
  if (n == 0) return out;
  for (var i = 0; i < v.length; i++) {
    out[i] = v[i] / n;
  }
  return out;
}

/// Promedio normalizado (centro de un grupo).
Float32List centro(Iterable<Float32List> vs) {
  Float32List? suma;
  for (final v in vs) {
    final u = normalizar(v);
    suma ??= Float32List(u.length);
    for (var i = 0; i < u.length; i++) {
      suma[i] += u[i];
    }
  }
  return suma == null ? Float32List(0) : normalizar(suma);
}

class AsignacionHuella {
  /// true = paciente, por tramo (mismo orden que la entrada).
  final List<bool> esPaciente;

  /// Similitud entre el centro del paciente y la huella del fonoaudiólogo/a
  /// (alta = voces parecidas; baja = bien diferenciadas).
  final double? similitudEntreVoces;

  /// 'alta' | 'media' | 'baja'.
  final String confianza;

  const AsignacionHuella(this.esPaciente, this.similitudEntreVoces, this.confianza);
}

AsignacionHuella asignarPorHuella(List<Float32List> tramos, Float32List huellaFono) {
  final n = tramos.length;
  if (n == 0) return const AsignacionHuella([], null, 'baja');
  final fono = normalizar(huellaFono);
  final simFono = [for (final t in tramos) coseno(t, fono)];

  // ¿Hay dos voces? Se compara el tercio más parecido a "Mi voz" con el
  // menos parecido (diferencia relativa, sin umbral absoluto: funciona igual
  // con voces de timbre parecido).
  final orden = List<int>.generate(n, (i) => i)..sort((a, b) => simFono[a].compareTo(simFono[b]));
  final k = math.max(1, (n * 0.3).round());
  double media(Iterable<int> idx) => idx.map((i) => simFono[i]).reduce((a, b) => a + b) / idx.length;
  final bajo = media(orden.take(k));
  final alto = media(orden.skip(n - k));
  if (n < 3 || alto - bajo < 0.12) {
    // Una sola voz: es la del fono si se parece a "Mi voz"; si no, del paciente.
    final mediana = simFono[orden[n ~/ 2]];
    final todoPaciente = mediana < 0.5;
    return AsignacionHuella(List.filled(n, todoPaciente), null, todoPaciente ? 'media' : 'baja');
  }
  final semilla = orden.take(k).toList();
  var cPac = centro(semilla.map((i) => tramos[i]));
  var cFono = fono;
  var esPac = List<bool>.filled(n, false);
  for (final i in semilla) {
    esPac[i] = true;
  }
  for (var vuelta = 0; vuelta < 10; vuelta++) {
    // El centro del fono mezcla la huella de "Mi voz" (ancla) con sus tramos.
    cFono = centro([fono, fono, for (var i = 0; i < n; i++) if (!esPac[i]) tramos[i]]);
    final nuevo = [for (final t in tramos) coseno(t, cPac) > coseno(t, cFono)];
    var cambios = 0;
    for (var i = 0; i < n; i++) {
      if (nuevo[i] != esPac[i]) cambios++;
    }
    esPac = nuevo;
    final pacs = [for (var i = 0; i < n; i++) if (esPac[i]) tramos[i]];
    if (pacs.isEmpty) break;
    cPac = centro(pacs);
    if (cambios == 0) break;
  }
  // Suavizado: tramo aislado entre dos vecinos iguales y distintos a él.
  final suave = List<bool>.from(esPac);
  for (var i = 1; i < n - 1; i++) {
    if (esPac[i - 1] == esPac[i + 1] && esPac[i] != esPac[i - 1]) suave[i] = esPac[i - 1];
  }
  // Confianza = nitidez de la separación: margen medio entre el parecido al
  // centro propio y al ajeno (no depende de cuán parecidas sean las voces).
  var margen = 0.0;
  for (final t in tramos) {
    margen += (coseno(t, cPac) - coseno(t, cFono)).abs();
  }
  margen /= n;
  final conf = margen >= 0.15 ? 'alta' : (margen >= 0.07 ? 'media' : 'baja');
  return AsignacionHuella(suave, coseno(cPac, fono), conf);
}
