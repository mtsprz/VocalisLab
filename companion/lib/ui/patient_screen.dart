import 'dart:async';
import 'dart:convert';
import 'dart:io' show File, SocketException;

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../sync/api_client.dart';

/// Paso 1: elegir paciente desde la caché local (funciona sin internet).
class PatientScreen extends StatefulWidget {
  final Deps deps;
  final ValueChanged<String> onSelect;

  /// Cambia cada vez que se entra a la pestaña Grabar → recarga la lista.
  final int recarga;

  const PatientScreen({super.key, required this.deps, required this.onSelect, this.recarga = 0});

  @override
  State<PatientScreen> createState() => _PatientScreenState();
}

class _PatientScreenState extends State<PatientScreen> {
  List<dynamic> _lista = [];
  String _q = '';
  String? _aviso;
  bool _cargando = false;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  @override
  void didUpdateWidget(covariant PatientScreen old) {
    super.didUpdateWidget(old);
    if (old.recarga != widget.recarga) _cargar();
  }

  /// Muestra la caché al instante; si hay vinculación y red, la actualiza
  /// en segundo plano (sin internet, sigue la lista guardada).
  Future<void> _cargar() async {
    final l = await widget.deps.pacientes.listar();
    if (mounted) setState(() => _lista = l);
    final token = await widget.deps.secure.readDeviceToken();
    if (token == null || token.isEmpty) return;
    if (mounted) setState(() => _cargando = true);
    String? aviso;
    try {
      await widget.deps.pacientes.sincronizar(widget.deps.api.pacientes);
      await _cachearReferencias();
      final nueva = await widget.deps.pacientes.listar();
      if (mounted) setState(() => _lista = nueva);
      if (nueva.isEmpty) aviso = 'El servidor no devolvió pacientes activos.';
    } on SocketException {
      aviso = 'Sin conexión: se muestra la lista guardada.';
    } on TimeoutException {
      aviso = 'El servidor tardó demasiado (puede estar despertando). Probá "Actualizar".';
    } on ApiException catch (e) {
      aviso = 'No se pudo actualizar la lista: ${e.message} (HTTP ${e.status}).';
    } catch (e) {
      aviso = 'No se pudo actualizar la lista: $e';
    }
    if (mounted) {
      setState(() {
        _aviso = aviso;
        _cargando = false;
      });
    }
  }

  /// Tabla de rangos por sexo/edad para la separación de voces offline.
  Future<void> _cachearReferencias() async {
    try {
      final r = await widget.deps.api.getReferencias();
      final rr = (r['rangos'] as List?) ?? [];
      if (rr.isEmpty) return;
      final f = File(p.join((await getApplicationDocumentsDirectory()).path, 'referencias.json'));
      await f.writeAsString(jsonEncode(rr));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final q = _q.toLowerCase();
    final vis = _lista
        .where((p) => q.isEmpty || (p.nombreAbreviado as String).toLowerCase().contains(q))
        .toList();
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Elegir paciente', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        const Text('Lista local (caché). Sin internet igual funciona.',
            style: TextStyle(fontSize: 15, color: Colors.black54),),
        const SizedBox(height: 12),
        TextField(
          style: const TextStyle(fontSize: 18),
          decoration: const InputDecoration(
              labelText: 'Buscar', border: OutlineInputBorder(), prefixIcon: Icon(Icons.search),),
          onChanged: (v) => setState(() => _q = v),
        ),
        Row(children: [
          Expanded(
            child: Text(_aviso ?? '', style: const TextStyle(fontSize: 15, color: Color(0xFFC96F4A))),
          ),
          TextButton.icon(
            onPressed: _cargando ? null : _cargar,
            icon: _cargando
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.refresh),
            label: const Text('Actualizar', style: TextStyle(fontSize: 16)),
          ),
        ],),
        const SizedBox(height: 4),
        Expanded(
          child: vis.isEmpty
              ? const Center(
                  child: Text(
                    'Todavía no hay pacientes guardados en este equipo.\n\n'
                    'Ajustes → Vincular → Entrar con Google (una vez, con internet) '
                    'y la lista se descarga para usarla sin conexión.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 17),
                  ),
                )
              : ListView.separated(
                  itemCount: vis.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (_, i) {
                    final p = vis[i];
                    return ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        alignment: Alignment.centerLeft,
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                      ),
                      onPressed: () => widget.onSelect(p.id as String),
                      child: Text(p.nombreAbreviado as String),
                    );
                  },
                ),
        ),
      ],),
    );
  }
}
