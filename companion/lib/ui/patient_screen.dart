import 'package:flutter/material.dart';

import '../app.dart';

/// Paso 1: elegir paciente desde la caché local (funciona sin internet).
class PatientScreen extends StatefulWidget {
  final Deps deps;
  final ValueChanged<String> onSelect;

  const PatientScreen({super.key, required this.deps, required this.onSelect});

  @override
  State<PatientScreen> createState() => _PatientScreenState();
}

class _PatientScreenState extends State<PatientScreen> {
  List<dynamic> _lista = [];
  String _q = '';

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  /// Muestra la caché al instante; si hay vinculación y red, la actualiza
  /// en segundo plano (sin internet, sigue la lista guardada).
  Future<void> _cargar() async {
    final l = await widget.deps.pacientes.listar();
    if (mounted) setState(() => _lista = l);
    final token = await widget.deps.secure.readDeviceToken();
    if (token == null || token.isEmpty) return;
    try {
      await widget.deps.pacientes.sincronizar(widget.deps.api.pacientes);
      final nueva = await widget.deps.pacientes.listar();
      if (mounted) setState(() => _lista = nueva);
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
        const SizedBox(height: 12),
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
