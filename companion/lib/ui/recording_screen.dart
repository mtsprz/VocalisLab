import 'dart:async';
import 'dart:convert';
import 'dart:io' show File, Platform;

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../app.dart';
import '../config.dart';
import '../core/audio/recorder_service.dart';
import '../core/finalizar_sesion.dart';
import '../sync/foreground_service.dart';

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
  final _nivel = ValueNotifier<(double, bool)>((0.0, false));
  bool _grabando = false;
  bool _procesando = false;
  String _speaker = 'paciente';
  _Marca? _abierta;
  final List<Map<String, dynamic>> _marcas = [];
  // Turnos de hablante de toda la sesión (para cuando no se marcan tareas).
  final List<Map<String, dynamic>> _turnos = [];
  double _inicioTurno = 0;
  DateTime? _t0;
  Duration _transcurrido = Duration.zero;
  Timer? _timer;
  String? _error;
  late String _dsid;
  late String _sesDir;

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
    _sesDir = p.join(docs.path, 'sesiones', _dsid);
    final ahora = DateTime.now().toIso8601String();
    // La fila existe desde el primer segundo: si la app muere, la sesión
    // aparece como "interrumpida" y se puede recuperar desde Sincronizar.
    await widget.deps.store.crear({
      'device_session_id': _dsid,
      'patient_id': widget.pacienteId,
      'recorded_at': ahora,
      'audio_codec': 'aac',
      'audio_bitrate_kbps': AppConfig.aacBitrate ~/ 1000,
      'dsp_version': AppConfig.dspVersion,
      'device_info': _deviceInfo(),
      'consent_recorded': widget.consent ? 1 : 0,
      'status': 'recording',
      'blocks_dir': p.join(_sesDir, 'bloques'),
      'finalized': 0,
      'created_at': ahora,
    });
    sesionEnCurso = _dsid;
    await _rec.iniciar(p.join(_sesDir, 'bloques'));
    _rec.onNivel = (nivel, satura) => _nivel.value = (nivel, satura);
    try {
      await WakelockPlus.enable();
    } catch (_) {}
    try {
      await ForegroundGuard.iniciar(titulo: 'Grabando sesión vocal');
    } catch (_) {}
    setState(() {
      _grabando = true;
      _t0 = DateTime.now();
      _inicioTurno = 0;
    });
    var tick = 0;
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _transcurrido = Duration(seconds: _segundos.round()));
      if (++tick % 5 == 0) _guardarMarcas();
    });
    await _guardarMarcas();
  }

  /// Persiste marcas y turnos (cada 5 s y en cada cambio) para poder
  /// recuperar los tramos tras un cierre forzado.
  Future<void> _guardarMarcas() async {
    try {
      await File(p.join(_sesDir, archivoMarcas)).writeAsString(jsonEncode({
        't': _segundos,
        'marcas': _marcas,
        'turnos': _turnos,
        'speaker': _speaker,
        'inicio_turno': _inicioTurno,
        'abierta': _abierta == null
            ? null
            : {'task': _abierta!.task, 'speaker': _abierta!.speaker, 'inicio': _abierta!.inicio},
      }),);
    } catch (_) {}
  }

  String _nuevoId() {
    final ahora = DateTime.now();
    final f = '${ahora.year}${_d2(ahora.month)}${_d2(ahora.day)}-'
        '${_d2(ahora.hour)}${_d2(ahora.minute)}${_d2(ahora.second)}';
    return 'ses-$f-${const Uuid().v4().substring(0, 8)}';
  }

  String _d2(int n) => n.toString().padLeft(2, '0');

  /// Cierra la marca abierta en [fin] (descarta tramos de duración 0:
  /// el servidor exige end_sec > start_sec).
  void _cerrarMarca(double fin) {
    final a = _abierta;
    if (a == null) return;
    if (fin > a.inicio) {
      _marcas.add({
        'task_type': a.task,
        'speaker': a.speaker,
        'start_sec': a.inicio,
        'end_sec': fin,
      });
    }
    _abierta = null;
  }

  void _cerrarTurno(double fin) {
    if (fin > _inicioTurno) {
      _turnos.add({'speaker': _speaker, 'start_sec': _inicioTurno, 'end_sec': fin});
    }
    _inicioTurno = fin;
  }

  void _toggleTarea(String task) {
    if (!_grabando) return;
    final ahora = _segundos;
    setState(() {
      final misma = _abierta?.task == task;
      _cerrarMarca(ahora);
      if (!misma) _abierta = _Marca(task, _speaker, ahora); // segundo toque: solo cierra
    });
    _guardarMarcas();
  }

  /// Cambio de hablante: corta el tramo en curso para que cada segmento
  /// tenga un único hablante (el DSP solo usa los de "paciente").
  void _cambiarHablante(String s) {
    if (s == _speaker) return;
    if (!_grabando) {
      setState(() => _speaker = s);
      return;
    }
    final ahora = _segundos;
    setState(() {
      final task = _abierta?.task;
      _cerrarMarca(ahora);
      _cerrarTurno(ahora);
      _speaker = s;
      if (task != null) _abierta = _Marca(task, s, ahora);
    });
    _guardarMarcas();
  }

  Future<void> _detener() async {
    final fin = _segundos;
    _cerrarMarca(fin);
    _cerrarTurno(fin);
    await _guardarMarcas();
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
      await finalizarSesion(
        store: widget.deps.store,
        vault: widget.deps.vault,
        dsid: _dsid,
        sesDir: _sesDir,
        sexoReferencia: await _sexoReferencia(),
        segmentos: segmentosFinales(_marcas, _turnos),
      );
      sesionEnCurso = null;
      widget.onTerminar(_dsid);
    } catch (e) {
      sesionEnCurso = null;
      setState(() {
        _error = 'Error al procesar: $e (la grabación quedó guardada; '
            'podés recuperarla desde Sincronizar)';
        _procesando = false;
      });
    }
  }

  String _deviceInfo() =>
      '{"modelo":"${Platform.operatingSystem}","so":"${Platform.operatingSystemVersion.replaceAll('"', '')}","microfono":"no especificado","distancia_cm":null,"calibracion_db":null}';

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
                style: const TextStyle(fontSize: 40, fontWeight: FontWeight.bold),),
          ),
          if (_grabando)
            const Row(children: [
              Icon(Icons.fiber_manual_record, color: Colors.red, size: 28),
              SizedBox(width: 6),
              Text('GRABANDO', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.red)),
            ],),
        ],),
        const SizedBox(height: 8),
        // Indicador simple de nivel de entrada (anti-saturación, sin cifras)
        ValueListenableBuilder<(double, bool)>(
          valueListenable: _nivel,
          builder: (_, v, __) {
            final (t, satura) = v;
            final color = satura ? Colors.red : (t > 0.8 ? Colors.orange : const Color(0xFF5C7A57));
            return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                height: 22,
                decoration: BoxDecoration(
                    border: Border.all(color: Colors.black26), borderRadius: BorderRadius.circular(8),),
                child: FractionallySizedBox(
                  alignment: Alignment.centerLeft,
                  widthFactor: t,
                  child: Container(
                      decoration: BoxDecoration(
                          color: color, borderRadius: BorderRadius.circular(7),),),
                ),
              ),
              Text(satura ? '¡SATURA! Alejá el micrófono' : 'Nivel de entrada',
                  style: TextStyle(fontSize: 15, color: color, fontWeight: FontWeight.bold),),
            ],);
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
          onSelectionChanged: _procesando ? null : (s) => _cambiarHablante(s.first),
        ),
        const SizedBox(height: 12),
        const Text('Tareas (tocá para marcar inicio/fin):',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),),
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
                    style: const TextStyle(fontSize: 19),),
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
            ],),
          ),
      ],),
    );
  }
}
