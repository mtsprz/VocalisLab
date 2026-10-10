import 'package:flutter/material.dart';

import '../app.dart';
import '../sync/pairing.dart';

/// Emparejamiento: la web genera un código de 10 min; acá se ingresa una vez.
class PairingScreen extends StatefulWidget {
  final Deps deps;
  final VoidCallback onListo;

  const PairingScreen({super.key, required this.deps, required this.onListo});

  @override
  State<PairingScreen> createState() => _PairingScreenState();
}

class _PairingScreenState extends State<PairingScreen> {
  final _code = TextEditingController();
  final _name = TextEditingController();
  bool _busy = false;
  String? _error;

  Future<void> _go() async {
    if (_code.text.trim().length < 4) {
      setState(() => _error = 'Ingresá el código de 6 caracteres');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await emparejar(
        api: widget.deps.api,
        secure: widget.deps.secure,
        code: _code.text,
        deviceName: _name.text.trim().isEmpty ? 'Companion' : _name.text.trim(),
      );
      widget.onListo();
    } catch (e) {
      setState(() => _error = '$e'.replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.link, size: 64, color: Color(0xFF5C7A57)),
            const SizedBox(height: 16),
            const Text('Emparejar dispositivo', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text(
              'En la web: Voz y sesiones → Dispositivos → Generar código. Ingresalo acá (vence en 10 minutos).',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 24),
            TextField(
              controller: _code,
              textCapitalization: TextCapitalization.characters,
              maxLength: 8,
              style: const TextStyle(fontSize: 26, letterSpacing: 6),
              textAlign: TextAlign.center,
              decoration: const InputDecoration(
                labelText: 'Código', border: OutlineInputBorder(),),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _name,
              style: const TextStyle(fontSize: 18),
              decoration: const InputDecoration(
                labelText: 'Nombre de este equipo (ej. Moto G consultorio)',
                border: OutlineInputBorder(),),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red, fontSize: 16)),
            ],
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _busy ? null : _go,
              child: Text(_busy ? 'Verificando…' : 'Emparejar'),
            ),
          ],),
        ),
      ),
    );
  }
}
