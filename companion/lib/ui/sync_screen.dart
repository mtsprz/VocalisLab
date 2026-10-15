import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../core/finalizar_sesion.dart' show sesionEnCurso, sesionesEnSegundoPlano;
import '../data/settings_store.dart';
import '../sync/sincronizar.dart';
import 'finalizar_ui.dart';

const _estadoColor = {
  'recording': Colors.red,
  'ready': Colors.orange,
  'queued': Colors.blue,
  'uploading': Colors.blue,
  'confirming': Colors.blue,
  'watching': Colors.purple,
  'synced': Colors.green,
  'error': Colors.red,
};

/// Cola persistente: QUEUED/UPLOADING/SYNCED/ERROR, backoff, idempotencia.
/// SYNCED solo con `processed` del servidor. Sin bloquear la app.
class SyncScreen extends StatefulWidget {
  final Deps deps;
  const SyncScreen({super.key, required this.deps});

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  List<Map<String, dynamic>> _lista = [];
  String? _msg;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _recargar();
    cambiosSync.addListener(_alCambiar);
  }

  @override
  void dispose() {
    cambiosSync.removeListener(_alCambiar);
    super.dispose();
  }

  void _alCambiar() {
    if (mounted) _recargar();
  }

  Future<void> _recargar() async {
    final l = await widget.deps.store.pendientes();
    // Interrumpidas por cierre forzado (no la que se está grabando ahora).
    final inc = (await widget.deps.store.incompletas())
        .where((s) => s['device_session_id'] != sesionEnCurso &&
            !sesionesEnSegundoPlano.contains(s['device_session_id']),)
        .toList();
    final todas = await _todas();
    if (mounted) {
      setState(() {
        _lista = [...inc, ...l, ...todas.where((s) =>
            (s['status'] == 'synced') &&
            !l.any((x) => x['device_session_id'] == s['device_session_id']),),];
      });
    }
  }

  Future<List<Map<String, dynamic>>> _todas() async {
    // Las synced recientes (últimas 20) para contexto.
    try {
      final db = widget.deps.db;
      return await db.query('sessions', orderBy: 'created_at DESC', limit: 20);
    } catch (_) {
      return [];
    }
  }

  Future<void> _sincronizarTodo() async {
    setState(() {
      _busy = true;
      _msg = null;
    });
    try {
      final (ok, fail, ultimo) = await sincronizarPendientes(widget.deps);
      if (mounted) {
        setMsg('Listo: $ok sincronizada(s)'
            '${fail > 0 ? ', $fail pendiente(s): ${ultimo ?? ''}' : ''}');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
      if (mounted) await _recargar();
    }
  }

  void setMsg(String m) => setState(() => _msg = m);

  /// Termina una sesión interrumpida (cierre forzado / batería) con los
  /// bloques que quedaron en disco: misma separación automática de voces.
  Future<void> _recuperar(Map<String, dynamic> s) async {
    final dsid = '${s['device_session_id']}';
    setState(() {
      _busy = true;
      _msg = 'Recuperando: separando voces y midiendo el tono…';
    });
    try {
      final docs = await getApplicationDocumentsDirectory();
      await finalizarConContexto(
        deps: widget.deps,
        dsid: dsid,
        sesDir: p.join(docs.path, 'sesiones', dsid),
        pacienteId: '${s['patient_id']}',
        onProgreso: (v) {
          if (mounted) setMsg('Recuperando… ${(v * 100).round()} %');
        },
      );
      setMsg('Sesión recuperada ✓ (queda en cola para sincronizar)');
    } catch (e) {
      setMsg('No se pudo recuperar: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
      _recargar();
    }
  }

  Future<void> _reprocesar(String dsid) async {
    setState(() => _busy = true);
    try {
      final payload = await widget.deps.store.payloadParaServidor(dsid);
      await widget.deps.sync.reprocesarConConsentimiento(dsid, payload);
      setMsg('Reprocesada ✓');
    } catch (e) {
      setMsg('$e');
    } finally {
      setState(() => _busy = false);
      _recargar();
    }
  }

  Future<void> _limpiarAntiguas() async {
    final settings = await AppSettings.load();
    final limite =
        DateTime.now().subtract(Duration(days: settings.localRetentionDays));
    final todas = await _todas();
    var n = 0;
    for (final s in todas) {
      if (s['status'] != 'synced') continue;
      DateTime? creada;
      try {
        creada = DateTime.parse('${s['created_at']}');
      } catch (_) {}
      if (creada == null || creada.isAfter(limite)) continue;
      final dsid = '${s['device_session_id']}';
      final docs = await getApplicationDocumentsDirectory();
      final dir = Directory(p.join(docs.path, 'sesiones', dsid));
      try {
        if (await dir.exists()) await dir.delete(recursive: true);
        await widget.deps.store.borrarSesionLocal(dsid);
        n++;
      } catch (_) {}
    }
    setMsg('Limpieza: $n sesión(es) anterior(es) a $limite eliminadas localmente.');
    _recargar();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Sincronización', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        Text('Solo Wi-Fi por defecto. SYNCED = el servidor devolvió processed.',
            style: TextStyle(fontSize: 15, color: Theme.of(context).colorScheme.onSurfaceVariant),),
        const SizedBox(height: 12),
        if (_msg != null)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Theme.of(context).dividerColor),),
            child: Text(_msg!, style: const TextStyle(fontSize: 16)),
          ),
        Row(children: [
          Expanded(
            child: ElevatedButton.icon(
              onPressed: _busy ? null : _sincronizarTodo,
              icon: const Icon(Icons.cloud_upload, size: 26),
              label: Text(_busy ? 'Sincronizando…' : 'Sincronizar todo'),
            ),
          ),
        ],),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: _busy ? null : _limpiarAntiguas,
          icon: const Icon(Icons.cleaning_services),
          label: const Text('Liberar espacio (synced + retención)',
              style: TextStyle(fontSize: 16),),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: _lista.isEmpty
              ? const Center(
                  child: Text('Sin sesiones pendientes', style: TextStyle(fontSize: 17)),)
              : ListView.separated(
                  itemCount: _lista.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (_, i) {
                    final s = _lista[i];
                    final st = '${s['status']}';
                    final color = _estadoColor[st] ?? Colors.grey;
                    final err = '${s['error_detail'] ?? ''}';
                    final necesitaAccion = err.startsWith('ACCION_REQUERIDA:');
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                  decoration: BoxDecoration(
                                      color: color.withValues(alpha: 0.12),
                                      borderRadius: BorderRadius.circular(10),
                                      border: Border.all(color: color),),
                                  child: Text(st.toUpperCase(),
                                      style: TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.bold,
                                          color: color,),),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text('${s['device_session_id']}',
                                      style: TextStyle(fontSize: 14, color: Theme.of(context).colorScheme.onSurfaceVariant),),
                                ),
                              ],),
                              if (st == 'recording')
                                TextButton.icon(
                                  onPressed: _busy ? null : () => _recuperar(s),
                                  icon: const Icon(Icons.restore),
                                  label: const Text('Grabación interrumpida: recuperar',
                                      style: TextStyle(fontSize: 16),),
                                ),
                              if (err.isNotEmpty) ...[
                                const SizedBox(height: 6),
                                Text(
                                  necesitaAccion
                                      ? err.replaceFirst('ACCION_REQUERIDA: ', '')
                                      : err,
                                  style: const TextStyle(fontSize: 15),
                                ),
                                if (necesitaAccion)
                                  TextButton.icon(
                                    onPressed: () => _reprocesar('${s['device_session_id']}'),
                                    icon: const Icon(Icons.refresh),
                                    label: const Text('Marcar consentimiento y reprocesar',
                                        style: TextStyle(fontSize: 16),),
                                  ),
                              ],
                              TextButton.icon(
                                onPressed: () {
                                  Clipboard.setData(ClipboardData(
                                      text:
                                          'https://vocalis-lab.vercel.app/?paciente=${s['patient_id']}',),);
                                  ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                          content: Text('Enlace a la ficha copiado'),),);
                                },
                                icon: const Icon(Icons.open_in_new),
                                label: const Text('Abrir ficha en la web',
                                    style: TextStyle(fontSize: 16),),
                              ),
                            ],),
                      ),
                    );
                  },
                ),
        ),
      ],),
    );
  }
}
