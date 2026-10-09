import 'dart:async';
import 'dart:io' show Directory, File, Platform;
import 'dart:isolate';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../app.dart';
import '../config.dart';
import '../core/audio/recorder_service.dart';
import '../core/audio/wav.dart';
import '../core/dsp/dsp_isolate.dart';
import '../sync/foreground_service.dart';
import 'summary_screen.dart';

const _tareas = [
  ('vocal_sostenida_a', 'Vocal /a/ sostenida'),
  ('conteo', 'Conteo'),
  ('lectura', 'Lectura'),
  ('conversacion_espontanea', 'Conversación espontánea'),
];

class _Marca {
  String task;
  String speaker;
  double inicio;
  _Marca(this.task, this.speaker, this.inicio);
}

/// Paso 3: grabación con línea de tiempo por tareas y hablante.
class RecordingScreen extends StatefulWidget {
  final Deps deps;
  final String pacienteId;
  final bool consent;
  final void Function(String deviceSessionId) onTerminar;

  const RecordingScreen({
    super.key,
    required this.deps,
    required this.pacienteId,
    required this.consent,
    required this.onTerminar,
  });

  @override
  State<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends State<RecordingScreen> {
  final _rec = RecorderService();
  final _nivel = ValueNotifier<double>(-60.0);
  bool _grabando = false;
  bool _procesando = false;
  String _speaker = 'paciente';
  _Marca? _abierta;
  final List<Map<String, dynamic>> _marcas = [];
  DateTime? _t0;
  Duration _transcurrido = Duration.zero;
  Timer? _timer;
  String? _error;
  late String _dsid;
  late String _dirBloques;

  @override
  void dispose() {
    _timer?.cancel();
    _nivel.dispose();
    _rec.dispose();
    super.dispose();
  }

  double get _segundos =>
      _t0 == null ? 0 : DateTime.now().difference(_t0!).inMilliseconds / 1000;

  Future<void> _iniciar() async {
    setState(() => _error = null);
    if (!await _rec.tienePermiso()) {
      setState(() => _error = 'Sin permiso de micrófono');
      return;
    }
    final docs = await getApplicationDocumentsDirectory();
    _dsid = _nuevoId();
    _dirBloques = p.join(docs.path, 'sesiones', _dsid, 'bloques');
    await _rec.iniciar(_dirBloques);
    _rec.onLevelDb = (db) => _nivel.value = db;
    try {
      await WakelockPlus.enable();
    } catch (_) {}
    try {
      await ForegroundGuard.iniciar(titulo: 'Grabando sesión vocal');
    } catch (_) {}
    setState(() {
      _grabando = true;
      _t0 = DateTime.now();
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _transcurrido = Duration(seconds: _segundos.round()));
    });
  }

  String _nuevoId() {
    final ahora = DateTime.now();
    final f = '${ahora.year}${_d2(ahora.month)}${_d2(ahora.day)}-'
        '${_d2(ahora.hour)}${_d2(ahora.minute)}${_d2(ahora.second)}';
    return 'ses-$f-${const Uuid().v4().substring(0, 8)}';
  }

  String _d2(int n) => n.toString().padLeft(2, '0');

  void _toggleTarea(String task) {
    if (!_grabando) return;
    final ahora = _segundos;
    setState(() {
      if (_abierta != null) {
        _marcas.add({
          'task_type': _abierta!.task,
          'speaker': _abierta!.speaker,
          'start_sec': _abierta!.inicio,
          'end_sec': ahora,
        });
      }
      if (_abierta?.task == task) {
        _abierta = null; // segundo toque: solo cierra
      } else {
        _abierta = _Marca(task, _speaker, ahora);
      }
    });
  }

  Future<void> _detener() async {
    if (_abierta != null) {
      _marcas.add({
        'task_type': _abierta!.task,
        'speaker': _abierta!.speaker,
        'start_sec': _abierta!.inicio,
        'end_sec': _segundos,
      });
      _abierta = null;
    }
    await _rec.detener();
    try {
      await WakelockPlus.disable();
    } catch (_) {}
    try {
      await ForegroundGuard.detener();
    } catch (_) {}
    _timer?.cancel();
    setState(() {
      _grabando = false;
      _procesando = true;
    });
    try {
      await _finalizar();
    } catch (e) {
      setState(() {
        _error = 'Error al procesar: $e';
        _procesando = false;
      });
    }
  }

  Future<void> _finalizar() async {
    // 1. Recuperar + concatenar bloques en sesion.wav
    final dir = Directory(_dirBloques);
    var bloques = await recuperarBloques(dir);
    if (bloques.isEmpty) throw Exception('No quedó audio grabado');
    final docs = await getApplicationDocumentsDirectory();
    final sesDir = p.join(docs.path, 'sesiones', _dsid);
    final wavPath = p.join(sesDir, 'sesion.wav');
    await concatenarBloques(bloques, wavPath);
    final duracion = await _duracionWav(wavPath);

    // 2. Guardar sesión + segmentos
    await widget.deps.store.crear({
      'device_session_id': _dsid,
      'patient_id': widget.pacienteId,
      'recorded_at': DateTime.now().toIso8601String(),
      'audio_duration_sec': duracion,
      'audio_codec': 'pcm',
      'audio_bitrate_kbps': 1411,
      'dsp_version': AppConfig.dspVersion,
      'device_info': _deviceInfo(),
      'consent_recorded': widget.consent ? 1 : 0,
      'status': 'ready',
      'blocks_dir': _dirBloques,
      'finalized': 1,
      'created_at': DateTime.now().toIso8601String(),
    });
    await widget.deps.store.guardarSegmentos(_dsid, _marcas);

    // 3. DSP por tarea (isolate, solo tramos del paciente)
    final cal = await _leerCalibracion();
    final porTarea = <String, List<Map<String, dynamic>>>{};
    for (final m in _marcas) {
      porTarea.putIfAbsent('${m['task_type']}', () => []).add(m);
    }
    for (final entry in porTarea.entries) {
      final sostenida = entry.key == 'vocal_sostenida_a';
      double? mpt;
      if (sostenida) {
        mpt = entry.value
            .where((m) => m['speaker'] == 'paciente')
            .map((m) => (m['end_sec'] as num).toDouble() - (m['start_sec'] as num).toDouble())
            .fold(0.0, (a, b) => a > b ? a : b);
      }
      final res = await Isolate.run(() => analizarTarea(DspJob(
            wavPath: wavPath,
            segments: entry.value,
            sexoReferencia: await _sexoReferencia(),
            sostenida: sostenida,
            mptSec: mpt,
            calibrationDbOffset: cal,
          )));
      final metrics = Map<String, dynamic>.from(res['metrics'] as Map);
      await widget.deps.store.guardarAcustica(_dsid, entry.key, metrics);
    }

    // 4. Clips WAV ~10 s de vocal sostenida (para jitter/shimmer/HNR)
    final sost = porTarea['vocal_sostenida_a']
            ?.where((m) => m['speaker'] == 'paciente')
            .toList() ??
        [];
    if (sost.isNotEmpty) {
      final m0 = sost.first;
      final ini = (m0['start_sec'] as num).toDouble();
      final fin = (m0['end_sec'] as num).toDouble();
      final segundos = ((fin - ini).clamp(0, 30)).toDouble();
      if (segundos >= 5) {
        final clipPath = p.join(sesDir, 'clip_sostenida.wav');
        final seg10 = ((segundos.clamp(0, 10))).toDouble();
        await recortarWav(
            origen: wavPath, desdeSec: ini, segundos: seg10, destino: clipPath);
        await widget.deps.store.agregarClip(
            _dsid, 'vocal_sostenida_a', clipPath, seg10);
      }
    }

    await widget.deps.store.estado(_dsid, 'queued');
    widget.onTerminar(_dsid);
  }

  Future<double> _duracionWav(String path) async {
    final bytes = await File(path).length();
    if (bytes <= 44) return 0;
    return (bytes - 44) / 2 / AppConfig.sampleRate;
  }

  String _deviceInfo() =>
      '{"modelo":"${Platform.operatingSystem}","so":"${Platform.operatingSystemVersion.replaceAll('"', '')}","microfono":"no especificado","distancia_cm":null,"calibracion_db":null}';

  Future<double> _leerCalibracion() async {
    try {
      final f = File(
          '${(await getApplicationDocumentsDirectory()).path}/ajustes.json');
      if (!await f.exists()) return 0.0;
      final m = await f.readAsString();
      final v = RegExp(r'"calibrationDbOffset"\s*:\s*(-?[\d.]+)').firstMatch(m);
      return double.tryParse(v?.group(1) ?? '0') ?? 0.0;
    } catch (_) {
      return 0.0;
    }
  }

  Future<String> _sexoReferencia() async {
    try {
      final lista = await widget.deps.pacientes.listar();
      final p = lista.firstWhere((e) => e.id == widget.pacienteId);
      return p.sexoReferencia;
    } catch (_) {
      return '';
    }
  }

  String _mmss(Duration d) =>
      '${d.inMinutes.remainder(60).toString().padLeft(2, '0')}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(
            child: Text(_mmss(_transcurrido),
                style: const TextStyle(fontSize: 40, fontWeight: FontWeight.bold)),
          ),
          if (_grabando)
            const Row(children: [
              Icon(Icons.fiber_manual_record, color: Colors.red, size: 28),
              SizedBox(width: 6),
              Text('GRABANDO', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.red)),
            ]),
        ]),
        const SizedBox(height: 8),
        // Medidor de nivel anti-saturación
        ValueListenableBuilder<double>(
          valueListenable: _nivel,
          builder: (_, db, __) {
            final t = (((db + 60) / 60).clamp(0.0, 1.0)).toDouble();
            final color = db > -6 ? Colors.red : (db > -18 ? Colors.orange : const Color(0xFF5C7A57));
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                height: 22,
                decoration: BoxDecoration(
                    border: Border.all(color: Colors.black26), borderRadius: BorderRadius.circular(8)),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: t,
                  child: Container(
                      decoration: BoxDecoration(
                          color: color, borderRadius: BorderRadius.circular(7))),
                ),
              ),
              Text('${db.toStringAsFixed(0)} dBFS${db > -6 ? ' — ¡BAJÁ EL VOLUMEN!' : ''}',
                  style: TextStyle(fontSize: 15, color: color, fontWeight: FontWeight.bold)),
            ]);
          },
        ),
        const SizedBox(height: 12),
        // Alternancia de hablante
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'paciente', label: Text('Paciente habla', style: TextStyle(fontSize: 17))),
            ButtonSegment(value: 'fonoaudiologo', label: Text('Fonoaudiólogo', style: TextStyle(fontSize: 17))),
          ],
          selected: {_speaker},
          onSelectionChanged: (s) => setState(() => _speaker = s.first),
        ),
        const SizedBox(height: 12),
        const Text('Tareas (tocá para marcar inicio/fin):',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Expanded(
          child: ListView.separated(
            itemCount: _tareas.length,
            separatorBuilder: (_, __) => const SizedBox(height: 10),
            itemBuilder: (_, i) {
              final id = _tareas[i].$1;
              final label = _tareas[i].$2;
              final activa = _abierta?.task == id;
              return ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: activa ? const Color(0xFFC96F4A) : null,
                  foregroundColor: activa ? Colors.white : null,
                  padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 18),
                  alignment: Alignment.centerLeft,
                ),
                onPressed: _grabando && !_procesando ? () => _toggleTarea(id) : null,
                child: Text('${activa ? '■ ' : ''}$label',
                    style: const TextStyle(fontSize: 19)),
              );
            },
          ),
        ),
        if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 16)),
        const SizedBox(height: 8),
        if (!_grabando && !_procesando)
          ElevatedButton.icon(
            onPressed: _iniciar,
            icon: const Icon(Icons.mic, size: 28),
            label: const Text('Iniciar sesión'),
          ),
        if (_grabando)
          ElevatedButton.icon(
            onPressed: _detener,
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red.shade700, foregroundColor: Colors.white),
            icon: const Icon(Icons.stop, size: 28),
            label: const Text('Detener'),
          ),
        if (_procesando)
          const Padding(
            padding: EdgeInsets.all(12),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              CircularProgressIndicator(),
              SizedBox(width: 12),
              Text('Midiendo el tono…', style: TextStyle(fontSize: 18)),
            ]),
          ),
      ]),
    );
  }
}
