import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../config.dart';
import '../core/audio/compressor.dart';
import '../data/settings_store.dart';

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
  }

  Future<void> _recargar() async {
    final l = await widget.deps.store.pendientes();
    final todas = await _todas();
    if (mounted) {
      setState(() {
        _lista = [...l, ...todas.where((s) =>
            (s['status'] == 'synced') &&
            !l.any((x) => x['device_session_id'] == s['device_session_id']))];
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
      final settings = await AppSettings.load();
      final pend = await widget.deps.store.pendientes();
      var ok = 0, fail = 0;
      for (final s in pend) {
        final dsid = '${s['device_session_id']}';
        try {
          await _prepararActivos(dsid);
          await widget.deps.sync.sincronizar(dsid, {
            'audioPath': await _rutaComprimida(dsid),
            'audioMime': 'audio/mp4',
            'clips': await _clipsParaSubir(dsid),
            'wifiOnly': settings.wifiOnly,
          });
          ok++;
        } catch (e) {
          fail++;
          _msg = '$e';
        }
        if (mounted) await _recargar();
      }
      if (mounted) {
        setMsg('Listo: $ok sincronizada(s)${fail > 0 ? ', $fail con error' : ''}');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void setMsg(String m) => setState(() => _msg = m);

  /// Comprime la sesión a m4a ~48 kbps si aún no existe (Fase 3).
  Future<String> _rutaComprimida(String dsid) async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory(p.join(docs.path, 'sesiones', dsid));
    final wav = File(p.join(dir.path, 'sesion.wav'));
    final m4a = File(p.join(dir.path, 'sesion.m4a'));
    if (await m4a.exists()) return m4a.path;
    if (!await wav.exists()) throw Exception('Falta sesion.wav local');
    await AudioCompressor.platform().compressToM4a(
      wavPath: wav.path,
      outPath: m4a.path,
      bitrateKbps: AppConfig.aacBitrate ~/ 1000,
    );
    return m4a.path;
  }

  Future<List<Map<String, dynamic>>> _clipsParaSubir(String dsid) async {
    final clips = await widget.deps.store.clips(dsid);
    return [
      for (final c in clips)
        if (await File('${c['path']}').exists())
          {'task': '${c['task_type']}', 'path': '${c['path']}', 'mime': 'audio/wav'},
    ];
  }

  /// Garantiza clips WAV de la vocal sostenida antes de subir.
  Future<void> _prepararActivos(String dsid) async {
    // Los clips ya se extraen al detener (recording_screen). Acá solo se valida.
    final fila = await widget.deps.store.leer(dsid);
    if (fila == null) throw Exception('Sesión inexistente');
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
        const Text('Solo Wi-Fi por defecto. SYNCED = el servidor devolvió processed.',
            style: TextStyle(fontSize: 15, color: Colors.black54)),
        const SizedBox(height: 12),
        if (_msg != null)
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
                color: const Color(0xFFF7F3EA),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.black12)),
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
        ]),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: _busy ? null : _limpiarAntiguas,
          icon: const Icon(Icons.cleaning_services),
          label: const Text('Liberar espacio (synced + retención)',
              style: TextStyle(fontSize: 16)),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: _lista.isEmpty
              ? const Center(
                  child: Text('Sin sesiones pendientes', style: TextStyle(fontSize: 17)))
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
                                      color: color.withOpacity(0.12),
                                      borderRadius: BorderRadius.circular(10),
                                      border: Border.all(color: color)),
                                  child: Text(st.toUpperCase(),
                                      style: TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.bold,
                                          color: color)),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text('${s['device_session_id']}',
                                      style: const TextStyle(fontSize: 14, color: Colors.black54)),
                                ),
                              ]),
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
                                        style: TextStyle(fontSize: 16)),
                                  ),
                              ],
                              TextButton.icon(
                                onPressed: () {
                                  Clipboard.setData(ClipboardData(
                                      text:
                                          'https://vocalis-lab.vercel.app/?paciente=${s['patient_id']}'));
                                  ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(
                                          content: Text('Enlace a la ficha copiado')));
                                },
                                icon: const Icon(Icons.open_in_new),
                                label: const Text('Abrir ficha en la web',
                                    style: TextStyle(fontSize: 16)),
                              ),
                            ]),
                      ),
                    );
                  },
                ),
        ),
      ]),
    );
  }
}
