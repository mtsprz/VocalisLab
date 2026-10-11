import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../core/dsp/nota.dart';
import '../core/finalizar_sesion.dart' show archivoTonoGlobal;

const _labels = {
  'vocal_sostenida_a': 'Vocal /a/ sostenida',
  'conteo': 'Conteo',
  'lectura': 'Lectura',
  'conversacion_espontanea': 'Conversación espontánea',
};

String _promedio(Map<String, dynamic> r) {
  final a = (r['f0_promedio_min_hz'] as num?)?.round();
  final b = (r['f0_promedio_max_hz'] as num?)?.round();
  return a == b || b == null ? '$a' : '$a–$b';
}

String _hz(dynamic v) => v == null ? '—' : '${(v as num).round()}';

/// Edad en años cumplidos desde 'AAAA-MM-DD' (null si no se puede leer).
int? edadDesde(String fechaNacimiento, {DateTime? hoy}) {
  final f = DateTime.tryParse(fechaNacimiento);
  if (f == null) return null;
  final h = hoy ?? DateTime.now();
  var e = h.year - f.year;
  if (h.month < f.month || (h.month == f.month && h.day < f.day)) e--;
  return e < 0 ? null : e;
}

/// Rango de referencia (misma regla que backend y web; ver
/// supabase/companion_referencias_normativas.sql): <= 18 años → fila 'ninex'
/// de su edad (sin distinción de sexo); >= 19 → fila del sexo cuya franja
/// contiene la edad (la más angosta); sin edad → franja más amplia del sexo
/// (rango general adulto); adulto sin sexo → null (no se supone un sexo).
Map<String, dynamic>? rangoPara(List<dynamic> rangos, String sexo, int? edad) {
  final s = sexo.toLowerCase();
  final buscado = s.startsWith('masc') || s == 'm'
      ? 'masculino'
      : (s.startsWith('fem') || s == 'f' ? 'femenino' : '');
  final filas = rangos.whereType<Map>().map((m) => m.cast<String, dynamic>()).toList();
  int ini(Map m) => (m['edad_min'] as num?)?.toInt() ?? 0;
  int fin(Map m) => (m['edad_max'] as num?)?.toInt() ?? 200;
  int ancho(Map m) => fin(m) - ini(m);
  if (edad != null) {
    final tipo = edad <= 18 ? 'ninex' : buscado;
    if (tipo.isEmpty) return null;
    final c = filas.where((m) => m['sexo_referencia'] == tipo && edad >= ini(m) && edad <= fin(m)).toList()
      ..sort((x, y) => ancho(x).compareTo(ancho(y)));
    return c.isEmpty ? null : c.first;
  }
  if (buscado.isEmpty) return null;
  final c = filas.where((m) => m['sexo_referencia'] == buscado).toList()
    ..sort((x, y) => ancho(y).compareTo(ancho(x)));
  return c.isEmpty ? null : c.first;
}

/// Resumen inmediato: altura tonal principal (mediana en Hz + nota),
/// rango p5–p95, histograma de F0 y comparación con el rango esperado
/// (caché de /referencias; funciona sin internet).
class SummaryScreen extends StatefulWidget {
  final Deps deps;
  final String deviceSessionId;
  final String pacienteId;
  final VoidCallback onVolver;

  const SummaryScreen(
      {super.key,
      required this.deps,
      required this.deviceSessionId,
      this.pacienteId = '',
      required this.onVolver,});

  @override
  State<SummaryScreen> createState() => _SummaryScreenState();
}

class _SummaryScreenState extends State<SummaryScreen> {
  List<Map<String, dynamic>> _ac = [];
  Map<String, dynamic>? _global;
  List<dynamic> _rangos = [];
  String _sexo = '';
  int? _edad;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    final rows = await widget.deps.store.acustica(widget.deviceSessionId);
    final list = [
      for (final r in rows)
        {'task_type': r['task_type'], ...(jsonDecode('${r['payload']}') as Map<String, dynamic>)},
    ];
    final docs = (await getApplicationDocumentsDirectory()).path;
    Map<String, dynamic>? global;
    try {
      final f = File(p.join(docs, 'sesiones', widget.deviceSessionId, archivoTonoGlobal));
      if (await f.exists()) global = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
    } catch (_) {}
    List<dynamic> rangos = [];
    final cache = File(p.join(docs, 'referencias.json'));
    try {
      if (await cache.exists()) rangos = jsonDecode(await cache.readAsString()) as List<dynamic>;
    } catch (_) {}
    // Refrescar caché si hay red (no bloquea).
    widget.deps.api.getReferencias().then((r) async {
      final rr = (r['rangos'] as List?) ?? [];
      if (rr.isNotEmpty) {
        try {
          await cache.writeAsString(jsonEncode(rr));
        } catch (_) {}
        if (mounted) setState(() => _rangos = rr);
      }
    }).catchError((_) {});
    var sexo = '';
    int? edad;
    try {
      final ps = await widget.deps.pacientes.listar();
      final pac = ps.firstWhere((e) => e.id == widget.pacienteId);
      sexo = pac.sexoReferencia;
      edad = edadDesde(pac.fechaNacimiento);
    } catch (_) {}
    if (mounted) {
      setState(() {
        _ac = list;
        _global = global;
        _rangos = rangos;
        _sexo = sexo;
        _edad = edad;
      });
    }
  }

  /// Métrica principal: conversación espontánea; si no hubo, todos los
  /// tramos del paciente.
  (String, Map<String, dynamic>?) _principal() {
    for (final a in _ac) {
      if (a['task_type'] == 'conversacion_espontanea' && a['f0_median_hz'] != null) {
        return ('Conversación espontánea', a);
      }
    }
    return ('Todos los tramos del paciente', _global);
  }

  @override
  Widget build(BuildContext context) {
    final (origen, m) = _principal();
    final ref = rangoPara(_rangos, _sexo, _edad);
    return Scaffold(
      appBar: AppBar(title: const Text('Resumen de la sesión')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          _Principal(origen: origen, m: m, ref: ref,
              diar: (_global?['diarizacion'] as Map?)?.cast<String, dynamic>(),),
          const SizedBox(height: 16),
          for (final a in _ac) _tarjeta(a),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: widget.onVolver,
            icon: const Icon(Icons.check),
            label: const Text('Guardar y ver pendientes'),
          ),
        ],
      ),
    );
  }

  Widget _tarjeta(Map<String, dynamic> a) {
    final task = '${a['task_type']}';
    final med = (a['f0_median_hz'] as num?)?.toDouble();
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(_labels[task] ?? task, style: const TextStyle(fontSize: 18)),
        subtitle: Text('Rango ${_hz(a['f0_p5_hz'])}–${_hz(a['f0_p95_hz'])} Hz',
            style: const TextStyle(fontSize: 15),),
        trailing: Text(alturaTonal(med),
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),),
      ),
    );
  }
}

class _Principal extends StatelessWidget {
  final String origen;
  final Map<String, dynamic>? m;
  final Map<String, dynamic>? ref;
  final Map<String, dynamic>? diar;

  const _Principal({required this.origen, required this.m, required this.ref, this.diar});

  @override
  Widget build(BuildContext context) {
    final med = (m?['f0_median_hz'] as num?)?.toDouble();
    final nota = notaDesdeHz(med);
    final rMin = (ref?['f0_min_hz'] as num?)?.toDouble();
    final rMax = (ref?['f0_max_hz'] as num?)?.toDouble();
    String comparacion;
    if (med == null) {
      comparacion = 'Sin tramos sonoros del paciente: no se pudo medir el tono.';
    } else if (rMin == null || rMax == null) {
      comparacion = 'Sin rango de referencia para el sexo/edad del paciente '
          '(se descarga de /referencias la primera vez que hay conexión).';
    } else if (med < rMin) {
      comparacion = 'Por debajo del rango esperado (${rMin.round()}–${rMax.round()} Hz).';
    } else if (med > rMax) {
      comparacion = 'Por encima del rango esperado (${rMin.round()}–${rMax.round()} Hz).';
    } else {
      comparacion = 'Dentro del rango esperado (${rMin.round()}–${rMax.round()} Hz).';
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Altura tonal · $origen', style: const TextStyle(fontSize: 16, color: Colors.black54)),
          const SizedBox(height: 6),
          Text(med == null ? '— Hz' : '${med.round()} Hz',
              style: const TextStyle(fontSize: 48, fontWeight: FontWeight.bold),),
          if (nota != null)
            Text(alturaTonal(med), style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          Text('Rango (p5–p95): ${_hz(m?['f0_p5_hz'])}–${_hz(m?['f0_p95_hz'])} Hz',
              style: const TextStyle(fontSize: 18),),
          const SizedBox(height: 10),
          _Histograma(
            hist: (m?['f0_histogram'] as Map?)?.cast<String, dynamic>() ?? {},
            rMin: rMin,
            rMax: rMax,
          ),
          const SizedBox(height: 8),
          Text(comparacion, style: const TextStyle(fontSize: 17)),
          if (ref?['f0_promedio_min_hz'] != null)
            Text(
              'Promedio esperado: ${_promedio(ref!)} Hz'
              '${ref?['fuente'] != null ? ' · ${ref!['fuente']}' : ''}',
              style: const TextStyle(fontSize: 15, color: Colors.black54),
            ),
          if (diar != null) _lineaDiarizacion(diar!),
          const Text('Referencia orientativa: no reemplaza el criterio clínico.',
              style: TextStyle(fontSize: 14, color: Colors.black54),),
          const SizedBox(height: 4),
          const Text(convencionOctavas, style: TextStyle(fontSize: 12, color: Colors.black45)),
        ],),
      ),
    );
  }
}

/// Cómo salió la separación automática de voces (orientativo).
Widget _lineaDiarizacion(Map<String, dynamic> d) {
  final conf = '${d['confianza'] ?? ''}';
  final metodo = '${d['metodo'] ?? 'tono'}';
  final frac = (d['fraccion_paciente'] as num?)?.toDouble();
  final pct = frac == null ? '' : ' · paciente ${(frac * 100).round()} % del tiempo con voz';
  final como = metodo == 'huella' ? 'por huella vocal (timbre)' : 'por altura tonal';
  final (texto, color) = switch (conf) {
    'sin_perfil' => ('Sin "Mi voz" en Ajustes: se midió TODA la voz grabada, incluida la tuya.',
        const Color(0xFFC96F4A)),
    'alta' => ('Voces separadas $como, confianza alta$pct', const Color(0xFF5C7A57)),
    'media' => ('Voces separadas $como, confianza media$pct', const Color(0xFF8A6D3B)),
    _ => (metodo == 'huella'
        ? 'Las dos voces tienen timbre parecido: separación $como con confianza baja$pct.'
        : 'Separación $como con confianza baja (tonos parecidos)$pct. '
            'Volvé a grabar "Mi voz" para separar por huella vocal.', const Color(0xFFC96F4A)),
  };
  return Padding(
    padding: const EdgeInsets.only(top: 6),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(texto, style: TextStyle(fontSize: 15, color: color)),
      if (metodo == 'tono_respaldo')
        const Text('No se pudo usar la huella vocal en este equipo; se usó la altura tonal.',
            style: TextStyle(fontSize: 14, color: Color(0xFFC96F4A)),),
    ],),
  );
}

class _Histograma extends StatelessWidget {
  final Map<String, dynamic> hist;
  final double? rMin, rMax;

  const _Histograma({required this.hist, required this.rMin, required this.rMax});

  @override
  Widget build(BuildContext context) {
    final bins = (hist['bins'] as Map?)?.cast<String, dynamic>() ?? {};
    final refHz = (hist['ref_hz'] as num?)?.toDouble() ?? 0;
    if (bins.isEmpty || refHz <= 0) {
      return const Text('Sin histograma', style: TextStyle(fontSize: 15));
    }
    final keys = bins.keys.map(int.parse).toList()..sort();
    final max = keys.map((k) => (bins['$k'] as num).toDouble()).reduce(math.max);
    double hz(num st) => refHz * math.pow(2, st / 12);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Histograma de F0 (1 barra = 1 semitono; azul = dentro del rango esperado)',
          style: TextStyle(fontSize: 13, color: Colors.black54),),
      const SizedBox(height: 4),
      CustomPaint(
        size: const Size(double.infinity, 110),
        painter: _HistPainter(keys, bins, max, hz, rMin, rMax),
      ),
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text('${hz(keys.first - 0.5).round()} Hz', style: const TextStyle(fontSize: 13)),
        Text('${hz(keys.last + 0.5).round()} Hz', style: const TextStyle(fontSize: 13)),
      ],),
    ],);
  }
}

class _HistPainter extends CustomPainter {
  final List<int> keys;
  final Map<String, dynamic> bins;
  final double max;
  final double Function(num) hz;
  final double? rMin, rMax;

  _HistPainter(this.keys, this.bins, this.max, this.hz, this.rMin, this.rMax);

  @override
  void paint(Canvas canvas, Size size) {
    final bw = size.width / keys.length;
    for (var i = 0; i < keys.length; i++) {
      final v = (bins['${keys[i]}'] as num).toDouble();
      final h = (v / max) * (size.height - 16);
      final centro = hz(keys[i]);
      final dentro = rMin != null && rMax != null && centro >= rMin! && centro <= rMax!;
      final paint = Paint()..color = dentro ? const Color(0xFF0284C7) : const Color(0xFFCBD5E1);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(i * bw + 1, size.height - h, bw - 2, h),
            const Radius.circular(2),),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => true;
}
