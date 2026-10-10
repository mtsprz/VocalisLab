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
    widget.deps.pacientes.listar().then((l) {
      if (mounted) setState(() => _lista = l);
    });
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
              ? const Center(child: Text('Sin pacientes en caché', style: TextStyle(fontSize: 17)))
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
