import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../app.dart';
import '../config.dart';
import '../core/audio/recorder_service.dart';
import '../core/dsp/dsp_isolate.dart' show AnalisisEnVivo;
import '../core/finalizar_sesion.dart';
import '../data/settings_store.dart';
import '../sync/foreground_service.dart';
import '../sync/sincronizar.dart';
import 'finalizar_ui.dart';

/// Grabación de la sesión con un solo botón. Al detener, la app separa sola
/// la voz del paciente de la del fonoaudiólogo/a (perfil "Mi voz") y mide su
/// altura tonal; no hay que marcar tareas ni quién habla.
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
  final _nivel = ValueNotifier<double>(0.0);
  final _saturaHasta = ValueNotifier<DateTime?>(null);
  bool _grabando = false;
  bool _procesando = false;
  double _progreso = 0;
  DateTime? _t0;
  Duration _transcurrido = Duration.zero;
  Timer? _timer;
  String? _error;
  String _nombre = '';
  bool _tienePerfil = true;
  late String _dsid;
  late String _sesDir;
  AnalisisEnVivo? _vivo;

  @override
  void initState() {
    super.initState();
    widget.deps.pacientes.listar().then((l) {
      final p = l.where((e) => e.id == widget.pacienteId);
      if (mounted && p.isNotEmpty) setState(() => _nombre = p.first.nombreAbreviado);
    });
    AppSettings.load().then((s) {
      if (mounted) setState(() => _tienePerfil = s.tienePerfilVoz);
    });
  }

  @override
  void dispose() {
    _vivo?.cancelar();
    _timer?.cancel();
    _nivel.dispose();
    _saturaHasta.dispose();
    _rec.dispose();
    super.dispose();
  }

  double get _segundos =>
      _t0 == null ? 0 : DateTime.now().difference(_t0!).inMilliseconds / 1000;

  Future<void> _iniciar() async {
    setState(() => _error = null);
    if (!await _rec.tienePermiso()) {
      setState(() => _error = 'Sin permiso de micrófono: habilitalo en Ajustes del teléfono.');
      return;
    }
    try {
      final docs = await getApplicationDocumentsDirectory();
      _dsid = _nuevoId();
      _sesDir = p.join(docs.path, 'sesiones', _dsid);
      final ahora = DateTime.now().toIso8601String();
      // La fila existe desde el primer segundo: si la app muere, la sesión
      // aparece como "interrumpida" y se recupera desde Sincronizar.
      await widget.deps.store.crear({
        'device_session_id': _dsid,
        'patient_id': widget.pacienteId,
        'recorded_at': ahora,
        'audio_codec': 'aac',
        'audio_bitrate_kbps': AppConfig.aacBitrate ~/ 1000,
        'dsp_version': AppConfig.dspVersion,
        'device_info': _deviceInfo((await AppSettings.load()).vozFonoHz),
        'consent_recorded': widget.consent ? 1 : 0,
        'status': 'recording',
        'blocks_dir': p.join(_sesDir, 'bloques'),
        'finalized': 0,
        'created_at': ahora,
      });
      sesionEnCurso = _dsid;
      // Análisis EN VIVO: tono y huella se calculan mientras se graba, así
      // al detener el resumen está listo en 1-2 s. Si no arranca, se usa el
      // análisis desde archivo al final (más lento, mismo resultado).
      try {
        _vivo = await AnalisisEnVivo.iniciar(await configAnalisis(widget.deps, widget.pacienteId));
        _rec.onPcm = _vivo!.agregar;
      } catch (_) {
        _vivo = null;
        _rec.onPcm = null;
      }
      await _rec.iniciar(p.join(_sesDir, 'bloques'));
      _rec.onNivel = (nivel, satura) {
        _nivel.value = nivel;
        if (satura) _saturaHasta.value = DateTime.now().add(const Duration(milliseconds: 1500));
      };
    } catch (e) {
      setState(() => _error = 'No se pudo empezar a grabar: $e');
      return;
    }
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

  Future<void> _detener() async {
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
      _progreso = 0;
    });
    final vivo = _vivo;
    _vivo = null;
    _rec.onPcm = null;
    if (vivo != null) {
      try {
        final res = await vivo.terminar();
        await guardarResultado(store: widget.deps.store, dsid: _dsid, sesDir: _sesDir, res: res);
        sesionEnCurso = null;
        // Unir bloques + cifrar en segundo plano: ya se puede atender al
        // siguiente paciente. Si falla, la sesión queda para "recuperar".
        // Al quedar lista, sube sola (si hay Wi-Fi/conexión y está vinculada).
        final deps = widget.deps;
        final dsid = _dsid;
        unawaited(completarAudio(
          store: deps.store, vault: deps.vault, dsid: dsid, sesDir: _sesDir,
        ).then((_) => sincronizarEnFondo(deps, dsid)).catchError((_) {}),);
        widget.onTerminar(_dsid);
        return;
      } catch (_) {
        // Sigue con el análisis desde archivo.
      }
    }
    try {
      await finalizarConContexto(
        deps: widget.deps,
        dsid: _dsid,
        sesDir: _sesDir,
        pacienteId: widget.pacienteId,
        onProgreso: (v) {
          if (mounted) setState(() => _progreso = v);
        },
      );
      sesionEnCurso = null;
      sincronizarEnFondo(widget.deps, _dsid);
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

  String _deviceInfo(double? fonoHz) => jsonEncode({
        'modelo': Platform.operatingSystem,
        'so': Platform.operatingSystemVersion,
        'microfono': 'no especificado',
        'distancia_cm': null,
        'calibracion_db': null,
        if (fonoHz != null) 'fono_mediana_hz': double.parse(fonoHz.toStringAsFixed(1)),
      });

  String _hhmmss(Duration d) {
    String dd(int n) => n.toString().padLeft(2, '0');
    final h = d.inHours;
    return h > 0
        ? '$h:${dd(d.inMinutes.remainder(60))}:${dd(d.inSeconds % 60)}'
        : '${dd(d.inMinutes)}:${dd(d.inSeconds % 60)}';
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(_nombre.isEmpty ? 'Sesión' : 'Sesión con $_nombre',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),),
        if (!_tienePerfil && !_grabando && !_procesando)
          Container(
            margin: const EdgeInsets.only(top: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFC96F4A)),
            ),
            child: const Text(
              'Todavía no grabaste "Mi voz" (Ajustes). Sin eso la app no puede '
              'separar tu voz de la del paciente: la altura tonal incluiría las dos.',
              style: TextStyle(fontSize: 16),
            ),
          ),
        const Spacer(),
        Center(
          child: Text(_hhmmss(_transcurrido),
              style: const TextStyle(fontSize: 56, fontWeight: FontWeight.bold),),
        ),
        const SizedBox(height: 24),
        if (_procesando)
          Column(children: [
            LinearProgressIndicator(value: _progreso > 0 ? _progreso : null, minHeight: 10),
            const SizedBox(height: 12),
            Text(
              'Separando voces y midiendo el tono del paciente… ${(_progreso * 100).round()} %',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 18),
            ),
            const SizedBox(height: 4),
            Text('Puede tardar unos minutos en sesiones largas. No cierres la app.',
                textAlign: TextAlign.center, style: TextStyle(fontSize: 15, color: Theme.of(context).colorScheme.onSurfaceVariant),),
          ],)
        else
          Center(
            child: SizedBox(
              width: 180,
              height: 180,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  shape: const CircleBorder(),
                  backgroundColor: _grabando ? Colors.red.shade700 : const Color(0xFFC96F4A),
                  foregroundColor: Colors.white,
                ),
                onPressed: _grabando ? _detener : _iniciar,
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Icon(_grabando ? Icons.stop : Icons.mic, size: 64),
                  Text(_grabando ? 'Detener' : 'Grabar', style: const TextStyle(fontSize: 22)),
                ],),
              ),
            ),
          ),
        const SizedBox(height: 24),
        if (_grabando) _indicadorMicrofono(),
        const Spacer(),
        if (_error != null)
          Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 16)),
      ],),
    );
  }

  /// Aviso simple: si el sonido llega bien o si satura (sin cifras).
  Widget _indicadorMicrofono() {
    return ValueListenableBuilder<DateTime?>(
      valueListenable: _saturaHasta,
      builder: (_, hasta, __) => ValueListenableBuilder<double>(
        valueListenable: _nivel,
        builder: (_, nivel, __) {
          final satura = hasta != null && DateTime.now().isBefore(hasta);
          final color = satura ? Colors.red : const Color(0xFF5C7A57);
          return Column(children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: nivel,
                minHeight: 14,
                color: color,
                backgroundColor: Theme.of(context).dividerColor,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              satura
                  ? 'Muy fuerte: alejá un poco el teléfono'
                  : 'Micrófono funcionando (la barra se mueve con la voz)',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: color, fontWeight: FontWeight.w600),
            ),
          ],);
        },
      ),
    );
  }
}
