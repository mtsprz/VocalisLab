import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import '../app.dart';

const _labels = {
  'vocal_sostenida_a': 'Vocal /a/ sostenida',
  'conteo': 'Conteo',
  'lectura': 'Lectura',
  'conversacion_espontanea': 'Conversación espontánea',
};

String _f(dynamic v, [int d = 1]) =>
    v == null ? '—' : (v as num).toStringAsFixed(d);

/// Resumen inmediato: métricas por tarea + histograma F0 + comparación
/// con el rango esperado (caché de /referencias; funciona offline).
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
      required this.onVolver});

  @override
  State<SummaryScreen> createState() => _SummaryScreenState();
}

class _SummaryScreenState extends State<SummaryScreen> {
  List<Map<String, dynamic>> _ac = [];
  List<dynamic> _rangos = [];
  String _sexo = '';

  @override
  void initState() {
    super.initState();
    widget.deps.store.acustica(widget.deviceSessionId).then((rows) async {
      final list = [
        for (final r in rows)
          {'task_type': r['task_type'], ...(jsonDecode('${r['payload']}') as Map<String, dynamic>)}
      ];
      List<dynamic> rangos = [];
      try {
        final f = File('${(await getApplicationDocumentsDirectory()).path}/referencias.json');
        if (await f.exists()) {
          rangos = jsonDecode(await f.readAsString()) as List<dynamic>;
        }
      } catch (_) {}
      // Refrescar caché si hay red (no bloquea).
      widget.deps.api.getReferencias().then((r) async {
        final rr = (r['rangos'] as List?) ?? [];
        if (rr.isNotEmpty) {
          try {
            final f = File('${(await getApplicationDocumentsDirectory()).path}/referencias.json');
            await f.writeAsString(jsonEncode(rr));
          } catch (_) {}
          if (mounted) setState(() => _rangos = rr);
        }
      }).catchError((_) {});
      String sexo = '';
      try {
        final ps = await widget.deps.pacientes.listar();
        sexo = ps.firstWhere((e) => e.id == widget.pacienteId).sexoReferencia;
      } catch (_) {}
      if (mounted) {
        setState(() {
          _ac = list;
          _rangos = rangos;
          _sexo = sexo;
        });
      }
    });
  }

  Map<String, dynamic>? _rangoPara(String sexo) {
    final s = sexo.toLowerCase();
    for (final r in _rangos) {
      final m = r as Map<String, dynamic>;
      if (s.startsWith('masc') && m['sexo_referencia'] == 'masculino') return m;
      if (s.startsWith('fem') && m['sexo_referencia'] == 'femenino') return m;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Resumen de la sesión')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
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
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_labels[task] ?? task,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Wrap(spacing: 16, runSpacing: 6, children: [
            _met('F0 med', '${_f(a['f0_median_hz'], 0)} Hz'),
            _met('SD', '${_f(a['f0_sd_semitones'], 2)} st'),
            _met('dB', _f(a['intensity_mean_db'])),
            if (a['jitter_pct'] != null) _met('Jitter', '${_f(a['jitter_pct'], 2)} %'),
            if (a['shimmer_pct'] != null) _met('Shimmer', '${_f(a['shimmer_pct'], 2)} %'),
            if (a['hnr_db'] != null) _met('HNR', '${_f(a['hnr_db'])} dB'),
            if (a['mpt_sec'] != null) _met('MPT', '${_f(a['mpt_sec'])} s'),
          ]),
          const SizedBox(height: 8),
          _Histograma(
            hist: (a['f0_histogram'] as Map?)?.cast<String, dynamic>() ?? {},
            ref: _rangoPara(_sexo),
          ),
        ]),
      ),
    );
  }

  Widget _met(String k, String v) => RichText(
        text: TextSpan(
          style: const TextStyle(fontSize: 17, color: Color(0xFF2E2A26)),
          children: [
            TextSpan(text: '$k: '),
            TextSpan(text: v, style: const TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
      );
}

class _Histograma extends StatelessWidget {
  final Map<String, dynamic> hist;
  final Map<String, dynamic>? ref;

  const _Histograma({required this.hist, required this.ref});

  @override
  Widget build(BuildContext context) {
    final bins = (hist['bins'] as Map?)?.cast<String, dynamic>() ?? {};
    final refHz = (hist['ref_hz'] as num?)?.toDouble() ?? 0;
    if (bins.isEmpty || refHz <= 0) {
      return const Text('Sin histograma', style: TextStyle(fontSize: 15));
    }
    final keys = bins.keys.map(int.parse).toList()..sort();
    final max = keys.map((k) => (bins['$k'] as num).toDouble()).reduce((a, b) => a > b ? a : b);
    double hz(int st) => refHz * _pow2(st / 12);
    final rMin = (ref?['f0_min_hz'] as num?)?.toDouble();
    final rMax = (ref?['f0_max_hz'] as num?)?.toDouble();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      CustomPaint(
        size: const Size(double.infinity, 110),
        painter: _HistPainter(keys, bins, max, hz, rMin, rMax),
      ),
      Text('Ref: ${rMin?.toStringAsFixed(0) ?? '—'}–${rMax?.toStringAsFixed(0) ?? '—'} Hz (orientativo)',
          style: const TextStyle(fontSize: 14, color: Colors.black54)),
    ]);
  }

  double _pow2(double e) {
    var r = 1.0;
    final n = e.abs().floor();
    for (var i = 0; i < n; i++) {
      r *= 2;
    }
    final f = e.abs() - n;
    if (f > 0) r *= 1 + 0.6931 * f; // aprox. suficiente para el gráfico
    return e < 0 ? 1 / r : r;
  }
}

class _HistPainter extends CustomPainter {
  final List<int> keys;
  final Map<String, dynamic> bins;
  final double max;
  final double Function(int) hz;
  final double? rMin, rMax;

  _HistPainter(this.keys, this.bins, this.max, this.hz, this.rMin, this.rMax);

  @override
  void paint(Canvas canvas, Size size) {
    final bw = size.width / keys.length;
    for (var i = 0; i < keys.length; i++) {
      final v = (bins['${keys[i]}'] as num).toDouble();
      final h = (v / max) * (size.height - 16);
      final dentro = rMin != null &&
          rMax != null &&
          hz(keys[i] + 1) >= rMin! &&
          hz(keys[i]) <= rMax!;
      final paint = Paint()..color = dentro ? const Color(0xFF0284C7) : const Color(0xFFCBD5E1);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(i * bw + 1, size.height - h, bw - 2, h),
            const Radius.circular(2)),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => true;
}
